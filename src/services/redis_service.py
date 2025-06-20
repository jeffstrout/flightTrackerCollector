import json
import logging
from typing import List, Dict, Optional
import redis
from datetime import datetime

from ..models.aircraft import Aircraft
from ..config.loader import get_redis_config

logger = logging.getLogger(__name__)


class RedisService:
    """Redis service for storing and retrieving flight data"""
    
    def __init__(self):
        self.redis_client = None
        # In-memory storage when Redis is unavailable
        self.memory_store = {}
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            config = get_redis_config()
            self.redis_client = redis.Redis(**config)
            self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            logger.warning("Running without Redis - data will not be persisted")
            self.redis_client = None
    
    def store_region_data(self, region: str, aircraft_list: List[Aircraft], 
                         helicopters: List[Aircraft], location: Dict):
        """Store aircraft data for a region"""
        
        try:
            timestamp = datetime.now().isoformat()
            
            # Pre-serialize aircraft data once
            enriched_aircraft = [aircraft.dict() for aircraft in aircraft_list]
            helicopter_data = [heli.dict() for heli in helicopters]
            
            # Store all flights
            flights_data = {
                'timestamp': timestamp,
                'aircraft_count': len(enriched_aircraft),
                'aircraft': enriched_aircraft,
                'location': location,
                'region': region
            }
            
            # Store helicopters only
            choppers_data = {
                'timestamp': timestamp,
                'aircraft_count': len(helicopter_data),
                'aircraft': helicopter_data,
                'location': location,
                'region': region
            }
            
            # Store in Redis if available, otherwise in memory
            if self.redis_client:
                pipeline = self.redis_client.pipeline()
                
                # Regional data
                pipeline.setex(f"{region}:flights", 300, json.dumps(flights_data))
                pipeline.setex(f"{region}:choppers", 300, json.dumps(choppers_data))
                
                # Individual aircraft for quick lookups
                for aircraft_data in enriched_aircraft:
                    key = f"aircraft_live:{aircraft_data['hex']}"
                    pipeline.setex(key, 300, json.dumps(aircraft_data))
                
                pipeline.execute()
            else:
                # Store in memory
                self.memory_store[f"{region}:flights"] = flights_data
                self.memory_store[f"{region}:choppers"] = choppers_data
            
            # Log closest aircraft
            if enriched_aircraft:
                closest = enriched_aircraft[0]
                distance = closest.get('distance_miles', 'unknown')
                flight = closest.get('flight', 'N/A').strip() or 'N/A'
                registration = closest.get('registration', 'N/A') or 'N/A'
                model = closest.get('model', 'N/A') or 'N/A'
                altitude = closest.get('alt_baro', 'N/A')
                
                logger.info(f"✈️  CLOSEST AIRCRAFT: {flight} ({registration}) - {model}")
                logger.info(f"📍 Distance: {distance} mi | Altitude: {altitude} ft | Hex: {closest.get('hex', 'N/A')}")
            
            logger.info(f"Stored {len(enriched_aircraft)} aircraft, {len(helicopter_data)} choppers for {region}")
            
        except Exception as e:
            logger.error(f"Failed to store region data in Redis: {e}")
    
    def store_data(self, key: str, data: Dict, ttl: int = 300):
        """Store arbitrary data with TTL"""
        try:
            if self.redis_client:
                self.redis_client.setex(key, ttl, json.dumps(data))
            else:
                self.memory_store[key] = data
            logger.debug(f"Stored data at key: {key}")
        except Exception as e:
            logger.error(f"Failed to store data at key {key}: {e}")
    
    def store_region_data(self, region: str, data_type: str, data: Dict, ttl: int = 300):
        """Store region data of a specific type"""
        key = f"{region}:{data_type}"
        self.store_data(key, data, ttl)
    
    def get_region_data(self, region: str, data_type: str = "flights") -> Optional[Dict]:
        """Get stored aircraft data for a region"""
        key = f"{region}:{data_type}"
        
        # Try Redis first
        if self.redis_client:
            try:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Failed to get region data from Redis: {e}")
        
        # Fallback to memory store
        return self.memory_store.get(key)
    
    
    def get_system_status(self) -> Dict:
        """Get system status information"""
        status = {
            'redis_connected': self.redis_client is not None,
            'cache_stats': {
                'hit_rate': 0,
                'total_lookups': 0,
                'cache_size': 0
            }
        }
        
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                status['redis_info'] = {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', 'unknown'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                }
            except Exception as e:
                logger.error(f"Failed to get Redis info: {e}")
        
        return status