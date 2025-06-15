import os
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path


def setup_logging():
    """Setup logging configuration with rotation"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation at midnight
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "flight_collector.log",
        when="midnight",
        interval=1,
        backupCount=7,  # Keep 7 days of logs
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from some loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logging.info(f"Logging initialized at {log_level} level")