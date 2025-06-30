import asyncio
import logging
import time
from typing import Dict, List
from datetime import datetime

from ..config.loader import Config
from ..collectors.opensky import OpenSkyCollector
from ..collectors.dump1090 import Dump1090Collector
from ..models.aircraft import Aircraft
from .blender import DataBlender
from .redis_service import RedisService

logger = logging.getLogger(__name__)


class CollectorService:
    """Main service that orchestrates data collection from multiple sources"""
    
    def __init__(self, config: Config):
        self.config = config
        self.redis_service = RedisService()
        self.blender = DataBlender(config.helicopter_patterns, redis_service=self.redis_service)
        
        # Initialize collectors for each region
        self.region_collectors = {}
        self._initialize_collectors()
        
        # Timing control
        self.last_opensky_fetch = {}  # Track per region
        self.opensky_data_cache = {}  # Cache OpenSky data per region
        self.dump1090_interval = config.global_config.polling.get('dump1090_interval', 15)
        self.opensky_interval = config.global_config.polling.get('opensky_interval', 60)
        
        logger.info(f"CollectorService initialized with {len(self.region_collectors)} regions")
        logger.info(f"Intervals: dump1090={self.dump1090_interval}s, opensky={self.opensky_interval}s")
    
    def _initialize_collectors(self):
        """Initialize collectors for each enabled region"""
        for region_name, region_config in self.config.regions.items():
            if not region_config.enabled:
                continue
            
            collectors = []
            for collector_config in region_config.collectors:
                if not collector_config.enabled:
                    continue
                
                try:
                    collector = self._create_collector(collector_config.dict(), region_config.dict())
                    if collector:
                        collectors.append(collector)
                        logger.info(f"Initialized {collector_config.type} collector for {region_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize {collector_config.type} for {region_name}: {e}")
            
            if collectors:
                self.region_collectors[region_name] = {
                    'collectors': collectors,
                    'config': region_config
                }
    
    def _create_collector(self, collector_config: dict, region_config: dict):
        """Create a collector instance based on type"""
        collector_type = collector_config['type']
        
        if collector_type == 'opensky':
            return OpenSkyCollector(collector_config, region_config)
        elif collector_type == 'dump1090':
            return Dump1090Collector(collector_config, region_config)
        else:
            logger.error(f"Unknown collector type: {collector_type}")
            return None
    
    async def collect_region_data(self, region_name: str) -> bool:
        """Collect data for a single region"""
        if region_name not in self.region_collectors:
            logger.error(f"Region {region_name} not configured")
            return False
        
        region_data = self.region_collectors[region_name]
        collectors = region_data['collectors']
        region_config = region_data['config']
        
        start_time = time.time()
        
        # Separate collectors by type
        dump1090_collectors = [c for c in collectors if isinstance(c, Dump1090Collector)]
        opensky_collectors = [c for c in collectors if isinstance(c, OpenSkyCollector)]
        
        # Collect from both sources in parallel
        collection_tasks = []
        
        # Add dump1090 collection tasks
        for collector in dump1090_collectors:
            collection_tasks.append(collector.fetch_data())
        
        # Handle OpenSky collection with timing control and caching
        current_time = time.time()
        should_fetch_opensky = (
            region_name not in self.last_opensky_fetch or
            (current_time - self.last_opensky_fetch.get(region_name, 0)) >= self.opensky_interval
        )
        
        if should_fetch_opensky and opensky_collectors:
            # Add OpenSky collection tasks
            for collector in opensky_collectors:
                collection_tasks.append(collector.fetch_data())
        
        # Execute all collection tasks in parallel
        collection_results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        
        # Process results
        dump1090_aircraft = []
        opensky_aircraft = []
        
        task_index = 0
        
        # Process dump1090 results
        for _ in dump1090_collectors:
            if task_index < len(collection_results):
                result = collection_results[task_index]
                if isinstance(result, Exception):
                    logger.error(f"dump1090 collection failed for {region_name}: {result}")
                elif result:
                    dump1090_aircraft.extend(result)
            task_index += 1
        
        # Process OpenSky results (if fetched)
        if should_fetch_opensky and opensky_collectors:
            for _ in opensky_collectors:
                if task_index < len(collection_results):
                    result = collection_results[task_index]
                    if isinstance(result, Exception):
                        logger.error(f"OpenSky collection failed for {region_name}: {result}")
                    elif result:
                        # Cache the data for this region
                        self.opensky_data_cache[region_name] = {
                            'aircraft': result,
                            'timestamp': current_time
                        }
                        opensky_aircraft.extend(result)
                        self.last_opensky_fetch[region_name] = current_time
                        logger.info(f"Cached {len(result)} OpenSky aircraft for region {region_name}")
                task_index += 1
        else:
            # Use cached data if available
            if region_name in self.opensky_data_cache:
                cached_data = self.opensky_data_cache[region_name]
                opensky_aircraft = cached_data['aircraft']
                cache_age = current_time - cached_data['timestamp']
                logger.info(f"Using cached OpenSky data: {len(opensky_aircraft)} aircraft (age: {cache_age:.0f}s)")
            else:
                logger.info("No cached OpenSky data available")
        
        logger.info(f"Total collected: dump1090={len(dump1090_aircraft)}, opensky={len(opensky_aircraft)}")
        logger.info(f"Condition check: dump1090_aircraft={bool(dump1090_aircraft)}, opensky_aircraft={bool(opensky_aircraft)}")
        logger.info(f"dump1090_aircraft type: {type(dump1090_aircraft)}, opensky_aircraft type: {type(opensky_aircraft)}")
        
        # Get Pi station data for this region
        pi_station_aircraft = self._get_pi_station_data(region_name)
        logger.info(f"Pi station data: {len(pi_station_aircraft)} aircraft")
        
        # Blend the data from all sources
        if dump1090_aircraft or opensky_aircraft or pi_station_aircraft:
            logger.info("Entering blending logic...")
            blended_aircraft = self.blender.blend_aircraft_data(pi_station_aircraft, dump1090_aircraft, opensky_aircraft)
            logger.info(f"Blending completed: {len(blended_aircraft)} aircraft")
            
            helicopters = self.blender.identify_helicopters(blended_aircraft)
            logger.info(f"Helicopter identification completed: {len(helicopters)} helicopters")
            
            # Store in Redis
            location = {
                'name': region_config.name,
                'lat': region_config.center['lat'],
                'lon': region_config.center['lon']
            }
            
            logger.info(f"About to store data: region={region_name}, aircraft={len(blended_aircraft)}, helicopters={len(helicopters)}")
            self.redis_service.store_region_data(region_name, blended_aircraft, helicopters, location)
            logger.info("Data storage completed")
            
            total_time = time.time() - start_time
            logger.info(f"Region {region_name}: {len(blended_aircraft)} aircraft, "
                       f"{len(helicopters)} helicopters in {total_time:.2f}s")
            
            logger.info("Returning True from collect_region_data")
            return True
        else:
            logger.warning(f"No data collected for region {region_name}")
            return False
    
    def _get_pi_station_data(self, region_name: str) -> List[Aircraft]:
        """Get Pi station data for a region from Redis"""
        pi_aircraft = []
        
        try:
            # Get all Pi station keys for this region
            pattern = f"pi_data:{region_name}:*"
            keys = self.redis_service.redis_client.keys(pattern)
            
            for key in keys:
                try:
                    # Get Pi station data
                    data = self.redis_service.redis_client.get(key)
                    if data:
                        import json
                        station_data = json.loads(data)
                        
                        # Convert Pi station aircraft to Aircraft objects
                        for aircraft_data in station_data.get('aircraft', []):
                            try:
                                # Create Aircraft object from Pi station data
                                aircraft = Aircraft(**aircraft_data)
                                
                                # Ensure data_source is preserved (e.g., "pi_station_ETEX01")
                                if not aircraft.data_source.startswith('pi_station'):
                                    aircraft.data_source = aircraft_data.get('data_source', f"pi_station_{station_data.get('station_id', 'unknown')}")
                                
                                pi_aircraft.append(aircraft)
                                
                            except Exception as e:
                                logger.warning(f"Error converting Pi station aircraft data: {e}")
                                continue
                                
                except Exception as e:
                    logger.warning(f"Error processing Pi station key {key}: {e}")
                    continue
                    
            logger.debug(f"Retrieved {len(pi_aircraft)} aircraft from {len(keys)} Pi stations for region {region_name}")
            
        except Exception as e:
            logger.error(f"Error fetching Pi station data for region {region_name}: {e}")
        
        return pi_aircraft
    
    async def collect_all_regions(self):
        """Collect data for all enabled regions"""
        start_time = time.time()
        
        # Collect data for all regions concurrently
        tasks = []
        for region_name in self.region_collectors.keys():
            task = asyncio.create_task(self.collect_region_data(region_name))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_regions = sum(1 for result in results if result is True)
        total_time = time.time() - start_time
        
        logger.info(f"Collected data for {successful_regions}/{len(self.region_collectors)} "
                   f"regions in {total_time:.2f}s")
    
    async def run_continuous(self):
        """Run continuous data collection"""
        logger.info("Starting continuous data collection...")
        
        while True:
            try:
                await self.collect_all_regions()
                await asyncio.sleep(self.dump1090_interval)
            except KeyboardInterrupt:
                logger.info("Shutting down collector service")
                break
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    def get_collector_stats(self) -> Dict:
        """Get statistics for all collectors"""
        stats = {
            'regions': {},
            'total_collectors': 0,
            'enabled_regions': len(self.region_collectors)
        }
        
        for region_name, region_data in self.region_collectors.items():
            region_stats = {
                'collectors': [],
                'total_collectors': len(region_data['collectors'])
            }
            
            for collector in region_data['collectors']:
                region_stats['collectors'].append(collector.get_stats())
                stats['total_collectors'] += 1
            
            stats['regions'][region_name] = region_stats
        
        return stats