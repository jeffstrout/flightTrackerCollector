import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse, Response

from .config.loader import load_config
from .services.collector_service import CollectorService
from .api.endpoints import router
from .utils.logging_config import setup_logging
from .version import VERSION_INFO


# Global collector service instance
collector_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    global collector_service
    
    # Startup
    logging.info("Starting Flight Tracker Collector API")
    logging.info(f"Flight Tracker Collector v{VERSION_INFO['version']}")
    logging.info(f"Git commit: {VERSION_INFO['commit']} ({VERSION_INFO['branch']})")
    logging.info(f"Build time: {VERSION_INFO['build_time']}")
    logging.info(f"Clean build: {VERSION_INFO['clean']}")
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize collector service
        collector_service = CollectorService(config)
        
        # Start background collection task
        collection_task = asyncio.create_task(collector_service.run_continuous())
        
        logging.info("Flight Tracker Collector API started successfully")
        
        yield
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        raise
    finally:
        # Shutdown
        logging.info("Shutting down Flight Tracker Collector API")
        if 'collection_task' in locals():
            collection_task.cancel()
            try:
                await collection_task
            except asyncio.CancelledError:
                pass


# Create FastAPI app
app = FastAPI(
    title="Flight Tracker Collector",
    description="Collects and aggregates flight data from multiple sources",
    version=VERSION_INFO['version'],
    lifespan=lifespan
)

# Add CORS middleware
origins = [
    "http://www.choppertracker.com",
    "http://choppertracker.com",
    "https://www.choppertracker.com",
    "https://choppertracker.com",
    "http://flight-tracker-web-ui-1750266711.s3-website-us-east-1.amazonaws.com",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Additional CORS handling for preflight requests
@app.options("/{full_path:path}")
async def options_handler(request):
    """Handle all OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

# Include API routes
app.include_router(router, prefix="/api/v1")

# Manual CORS preflight handler for additional coverage
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight requests"""
    return {"status": "ok"}

# Setup static file serving for frontend
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve config.js at root level
@app.get("/config.js", response_class=PlainTextResponse)
async def get_config():
    """Serve frontend configuration with version info"""
    config_js = f"""
window.FLIGHT_TRACKER_CONFIG = {{
    API_BASE_URL: 'https://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1',
    ENV: 'production',
    VERSION: {json.dumps(VERSION_INFO)},
    CACHE_BUST: '{int(time.time())}'
}};
"""
    return config_js

# Add root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Flight Tracker Collector API",
        "version": VERSION_INFO['version'],
        "docs": "/docs",
        "status": "/api/v1/status"
    }


# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    # Setup logging
    setup_logging()
    
    # For development only
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )