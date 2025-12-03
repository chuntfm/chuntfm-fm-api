# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Note:** When making significant architectural changes, new endpoints, or configuration updates, please update this CLAUDE.md file to reflect the current state of the codebase.

## Development Commands

**Run the API:**
```bash
python main.py
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Production deployment:**
```bash
gunicorn -c gunicorn.conf.py main:app
```

**Setup configuration:**
```bash
cp config.py.example config.py  # Edit for your environment
```

## Architecture Overview

This is a FastAPI-based radio API that aggregates data from multiple external sources. The architecture prioritizes simplicity (single main.py file) and flexibility (configurable external endpoints).

### Core Components

- **main.py**: Single-file FastAPI application with all endpoints and logic
- **config.py**: Configuration for channels, external API endpoints, and server settings

### External Data Sources

The API fetches data from three configurable external sources:
- **Schedule API** (`SCHEDULE_API_NOW_ENDPOINT`): Live show schedule data
- **Jukebox API** (`JUKEBOX_API_ENDPOINT`): 24/7 music jukebox current track
- **Restream API** (`RESTREAM_ENDPOINT`): JSON file with current restream information

### Channel Logic

**Channel 1 (Main)**: Priority flow for now-playing:
1. Check schedule API - if non-empty, return that data
2. If schedule empty, fall back to restream "current" data wrapped in list
3. Return empty list if neither available

**Channel 2 (Jukebox)**: Uses jukebox API for now-playing data

### Key Design Decisions

- **Raw data passthrough**: `/now-playing` endpoints return unmodified API responses (list/dict) rather than forcing through Pydantic models
- **Flexible stream configuration**: Each channel supports multiple stream URLs with different bitrates and qualities
- **Redirect endpoints**: `/url` endpoints return HTTP 302 redirects to actual stream URLs
- **Quality-specific endpoints**: Direct access via `/stream/high`, `/stream/low`, `/stream/default`