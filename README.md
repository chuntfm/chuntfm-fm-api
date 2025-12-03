# ChuntFM Radio API

FastAPI read-only API for radio data.

## Setup

```bash
pip install -r requirements.txt
cp config.py.example config.py  # Edit config.py for your environment
```

## Development

```bash
python main.py
```

## Production Deployment

```bash
# Using gunicorn
gunicorn -c gunicorn.conf.py main:app

# Using environment variables
DATABASE_URL=postgresql://user:pass@localhost/db gunicorn -c gunicorn.conf.py main:app

# Run on root path (for reverse proxy routing)
API_PREFIX="" gunicorn -c gunicorn.conf.py main:app

# Using Docker (example)
docker run -e DATABASE_URL=postgresql://... -p 8000:8000 your-image
```
