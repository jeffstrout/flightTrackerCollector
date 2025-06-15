#!/usr/bin/env python3
"""
Flight Tracker Collector CLI
Run the collector without the web API
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_config
from src.services.collector_service import CollectorService
from src.utils.logging_config import setup_logging


class CollectorCLI:
    def __init__(self):
        self.collector_service = None
        self.running = True
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def run(self):
        """Run the collector"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Load configuration
            config = load_config()
            
            # Initialize collector service
            self.collector_service = CollectorService(config)
            
            logging.info("🚀 Starting Flight Tracker Collector CLI")
            logging.info(f"📡 Configured regions: {list(config.regions.keys())}")
            
            # Run collection loop
            while self.running:
                try:
                    await self.collector_service.collect_all_regions()
                    
                    # Sleep for the dump1090 interval
                    dump1090_interval = config.global_config.polling.get('dump1090_interval', 15)
                    await asyncio.sleep(dump1090_interval)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logging.error(f"Error in collection loop: {e}")
                    await asyncio.sleep(5)  # Brief pause before retrying
            
        except Exception as e:
            logging.error(f"Failed to start collector: {e}")
            return 1
        
        logging.info("Flight Tracker Collector CLI stopped")
        return 0


def main():
    """Main entry point"""
    setup_logging()
    
    cli = CollectorCLI()
    exit_code = asyncio.run(cli.run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()