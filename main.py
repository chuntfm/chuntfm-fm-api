from fastapi import FastAPI, Depends, HTTPException, Query, Header, APIRouter
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, DateTime, String, Integer, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timezone
from dateutil import parser
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import threading
import os
import httpx
import asyncio

try:
    from config import *
except ImportError:
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    API_TITLE = os.getenv("API_TITLE", "ChuntFM Schedule API")
    API_VERSION = os.getenv("API_VERSION", "0.1.0")
    API_PREFIX = os.getenv("API_PREFIX", "/fm")
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-this-api-key")
    SCHEDULE_API_NOW_ENDPOINT = os.getenv("SCHEDULE_API_NOW_ENDPOINT", "http://localhost:8000/schedule/now")
    JUKEBOX_API_ENDPOINT = os.getenv("JUKEBOX_API_ENDPOINT", "http://localhost:9000/jukebox/now-playing")
    RESTREAM_ENDPOINT = os.getenv("RESTREAM_ENDPOINT", "http://localhost:8080/restream.json")
    

app = FastAPI(
    title=API_TITLE, 
    version=API_VERSION,
    docs_url=f"{API_PREFIX}/docs" if API_PREFIX else "/docs",
    redoc_url=f"{API_PREFIX}/redoc" if API_PREFIX else "/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json" if API_PREFIX else "/openapi.json"
)
router = APIRouter()
class ChannelResponse(BaseModel):
    id: int
    name: str
    description: str

class StreamItem(BaseModel):
    url: str
    backup_url: Optional[str] = None
    format: str
    bitrate: int
    quality: str
    default: Optional[bool] = None

class ChannelDetailResponse(BaseModel):
    id: int
    name: str
    description: str
    streams: List[StreamItem]

class NowPlayingItem(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    show: Optional[str] = None
    source: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class ChannelStatus(BaseModel):
    state: str  # up, down, degraded
    mode: str   # live, restream, jukebox, offline
    is_playing: bool


class RestreamInfo(BaseModel):
    source_channel: Optional[int] = None
    target_channels: List[int] = []
    current_item: Optional[NowPlayingItem] = None
    is_active: bool = False

async def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass
    return None

async def get_schedule_now() -> List[Dict[str, Any]]:
    data = await fetch_json(SCHEDULE_API_NOW_ENDPOINT)
    return data if data else []

async def get_jukebox_now() -> Optional[Dict[str, Any]]:
    return await fetch_json(JUKEBOX_API_ENDPOINT)

async def get_restream_data() -> Optional[Dict[str, Any]]:
    return await fetch_json(RESTREAM_ENDPOINT)

@router.get("/channels", response_model=List[ChannelResponse])
async def list_channels():
    return [ChannelResponse(id=ch["id"], name=ch["name"], description=ch["description"]) 
            for ch in FM_CHANNELS.values()]

@router.get("/channels/{channel_id}", response_model=ChannelDetailResponse)
async def get_channel(channel_id: int):
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    streams = [StreamItem(**stream) for stream in ch["streams"]]
    return ChannelDetailResponse(
        id=ch["id"],
        name=ch["name"],
        description=ch["description"],
        streams=streams
    )

@router.get("/channels/{channel_id}/now-playing")
async def get_channel_now_playing(channel_id: int):
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    
    # Special logic for channel 1
    if channel_id == 1:
        schedule_data = await get_schedule_now()
        if len(schedule_data)>0:
            return schedule_data
        
        # If schedule is empty, fall back to restream current item
        restream_data = await get_restream_data()
        if restream_data and restream_data.get("current"):
            return [restream_data["current"]]
        
        return []
    
    # Jukebox mode for other channels
    if ch.get("jukebox_mode"):
        jukebox_data = await get_jukebox_now()
        if jukebox_data:
            return [jukebox_data]
        return []
    
    # Default fallback logic for other channels
    schedule_data = await get_schedule_now()
    if schedule_data:
        return schedule_data
    
    restream_data = await get_restream_data()
    if restream_data and restream_data.get("is_active") and channel_id in restream_data.get("target_channels", []):
        current = restream_data.get("current_item", {})
        return [current] if current else []
    
    return []

@router.get("/channels/{channel_id}/status", response_model=ChannelStatus)
async def get_channel_status(channel_id: int):
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    
    if ch.get("jukebox_mode"):
        jukebox_data = await get_jukebox_now()
        is_playing = jukebox_data is not None
        return ChannelStatus(
            state="up" if is_playing else "down",
            mode="jukebox",
            is_playing=is_playing
        )
    
    schedule_data = await get_schedule_now()
    if schedule_data:
        return ChannelStatus(
            state="up",
            mode="live",
            is_playing=True
        )
    
    restream_data = await get_restream_data()
    if restream_data and restream_data.get("is_active") and channel_id in restream_data.get("target_channels", []):
        return ChannelStatus(
            state="up",
            mode="restream",
            is_playing=True
        )
    
    return ChannelStatus(
        state="down",
        mode="offline",
        is_playing=False
    )

@router.get("/channels/{channel_id}/streams", response_model=List[StreamItem])
async def get_channel_streams(channel_id: int):
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    return [StreamItem(**stream) for stream in ch["streams"]]

@router.get("/channels/{channel_id}/stream/default", response_model=StreamItem)
async def get_channel_default_stream(channel_id: int):
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    for stream in ch["streams"]:
        if stream.get("default"):
            return StreamItem(**stream)
    
    # Fallback to first stream if no default set
    if ch["streams"]:
        return StreamItem(**ch["streams"][0])
    
    raise HTTPException(status_code=404, detail="No streams available")

@router.get("/channels/{channel_id}/stream/default/play",
           responses={
               302: {"description": "Redirect to default stream URL"},
               404: {"description": "Channel not found"}
           },
           response_class=RedirectResponse)
async def get_channel_default_stream_play(channel_id: int):
    """
    Play the default stream for a channel (via HTTP redirect).
    
    Args:
        channel_id: FM channel ID (1, 2, etc.)
    
    Returns HTTP 302 redirect to the actual stream URL. This allows clients
    to use stable API endpoints while the underlying stream URLs can change
    in configuration without breaking existing integrations.
    
    Use this endpoint directly in media players, browser audio elements, etc.
    Example: <audio src="/fm/channels/1/stream/default/play" controls>
    """
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    for stream in ch["streams"]:
        if stream.get("default"):
            return RedirectResponse(url=stream["url"], status_code=302)
    
    # Fallback to first stream if no default set
    if ch["streams"]:
        return RedirectResponse(url=ch["streams"][0]["url"], status_code=302)
    
    raise HTTPException(status_code=404, detail="No streams available")

@router.get("/channels/{channel_id}/stream/{quality}", response_model=StreamItem)
async def get_channel_quality_stream(channel_id: int, quality: str):
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    for stream in ch["streams"]:
        if stream["quality"] == quality:
            return StreamItem(**stream)
    
    raise HTTPException(status_code=404, detail=f"No {quality} quality stream available")

@router.get("/channels/{channel_id}/stream/{quality}/play",
           responses={
               302: {"description": "Redirect to quality-specific stream URL"},
               404: {"description": "Channel not found or quality not available"}
           },
           response_class=RedirectResponse)
async def get_channel_quality_stream_play(channel_id: int, quality: str):
    """
    Play a specific quality stream for a channel (via HTTP redirect).
    
    Args:
        channel_id: FM channel ID (1, 2, etc.)
        quality: Stream quality ("high", "low", "standard", etc.)
    
    Returns HTTP 302 redirect to the actual stream URL for the requested quality.
    This provides stable API endpoints while allowing stream URLs to change.
    
    Use this endpoint directly in media players for quality selection.
    Example: <audio src="/fm/channels/1/stream/high/play" controls>
    """
    if channel_id not in FM_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    ch = FM_CHANNELS[channel_id]
    for stream in ch["streams"]:
        if stream["quality"] == quality:
            return RedirectResponse(url=stream["url"], status_code=302)
    
    raise HTTPException(status_code=404, detail=f"No {quality} quality stream available")

@router.get("/restream/now-playing")
async def get_restream_now_playing():
    restream_data = await get_restream_data()
    if restream_data and restream_data.get("current"):
        return restream_data["current"]
    return None

app.include_router(router, prefix=API_PREFIX)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)