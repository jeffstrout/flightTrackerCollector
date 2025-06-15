import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.loader import load_config
from .services.collector_service import CollectorService
from .api.endpoints import router
from .utils.logging_config import setup_logging


# Global collector service instance
collector_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    global collector_service
    
    # Startup
    logging.info("Starting Flight Tracker Collector API")
    
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
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Add root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Flight Tracker Collector API",
        "version": "1.0.0",
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