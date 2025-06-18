#!/usr/bin/env python3
"""
Utility script to manually load aircraft database into Redis
This can be run to force-reload the aircraft database on AWS
"""

import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.aircraft_db import AircraftDatabase
from src.services.redis_service import RedisService
from src.utils.logging_config import setup_logging

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🔄 Manual aircraft database loader started")
    
    # Initialize Redis service
    redis_service = RedisService()
    if not redis_service.redis_client:
        logger.error("❌ Redis connection failed - cannot load database")
        return 1
    
    # Initialize aircraft database
    aircraft_db = AircraftDatabase(redis_service)
    
    # Check if database is loaded
    if aircraft_db.aircraft_db is not None:
        logger.info(f"✅ Aircraft database loaded with {len(aircraft_db.aircraft_db)} records")
        
        # Force import to Redis
        logger.info("🚀 Force importing to Redis...")
        aircraft_db._import_to_redis()
        
        # Verify Redis has the data
        if redis_service.redis_client:
            aircraft_keys = redis_service.redis_client.keys("aircraft_db:*")
            logger.info(f"✅ Redis now contains {len(aircraft_keys)} aircraft records")
        
        logger.info("🎉 Aircraft database loading completed successfully")
        return 0
    else:
        logger.error("❌ Failed to load aircraft database from CSV")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)