import time
import logging
from typing import List, Optional
import httpx

from .base import BaseCollector
from ..models.aircraft import Aircraft
from ..exceptions import CollectorConnectionError, CollectorTimeout, DataValidationError

logger = logging.getLogger(__name__)


class Dump1090Collector(BaseCollector):
    """dump1090 ADS-B receiver collector"""
    
    def __init__(self, collector_config: dict, region_config: dict):
        super().__init__(collector_config, region_config)
        
        # dump1090 typically uses tar1090 format
        if not self.url.endswith('/data/aircraft.json'):
            if not self.url.endswith('/'):
                self.url += '/'
            self.url += 'data/aircraft.json'
        
        logger.info(f"dump1090 collector configured for {self.name} at {self.url}")
    
    async def fetch_data(self) -> Optional[List[Aircraft]]:
        """Fetch data from dump1090 receiver"""
        if not self.enabled:
            return None
        
        fetch_start = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                data = response.json()
            
            fetch_time = time.time() - fetch_start
            
            # Convert dump1090 data to Aircraft objects
            aircraft_list = self._convert_dump1090_data(data)
            
            # Filter by distance and add distance field
            aircraft_list = self.add_distance_and_filter(aircraft_list)
            
            # Sort by distance
            aircraft_list = self.sort_by_distance(aircraft_list)
            
            self.update_stats(True, len(aircraft_list))
            
            logger.info(f"dump1090 ({self.name}): {len(aircraft_list)} aircraft in {fetch_time:.2f}s")
            
            return aircraft_list
            
        except httpx.HTTPStatusError as e:
            self.update_stats(False)
            raise CollectorConnectionError(
                collector_name=self.name,
                endpoint=url,
                details={'status_code': e.response.status_code, 'response': str(e)}
            )
            
        except httpx.TimeoutException as e:
            self.update_stats(False)
            raise CollectorTimeout(
                collector_name=self.name,
                timeout=self.config.get('timeout', 5),
                details={'error': str(e)}
            )
            
        except Exception as e:
            self.update_stats(False)
            logger.error(f"dump1090 fetch failed: {e}")
            raise CollectorConnectionError(
                collector_name=self.name,
                endpoint=url,
                details={'error': str(e)}
            )
    
    def _convert_dump1090_data(self, data: dict) -> List[Aircraft]:
        """Convert dump1090 JSON data to Aircraft objects"""
        aircraft_list = []
        
        aircraft_data = data.get('aircraft', [])
        if not aircraft_data:
            return aircraft_list
        
        for aircraft_dict in aircraft_data:
            try:
                # dump1090 uses named JSON fields
                aircraft = Aircraft(
                    hex=aircraft_dict.get('hex', '').upper(),
                    flight=aircraft_dict.get('flight', '').strip() if aircraft_dict.get('flight') else '',
                    lat=aircraft_dict.get('lat'),
                    lon=aircraft_dict.get('lon'),
                    alt_baro=aircraft_dict.get('alt_baro'),
                    alt_geom=aircraft_dict.get('alt_geom'),
                    gs=aircraft_dict.get('gs'),  # Already in knots
                    track=aircraft_dict.get('track'),
                    baro_rate=aircraft_dict.get('baro_rate'),  # Already in ft/min
                    squawk=aircraft_dict.get('squawk'),
                    on_ground=aircraft_dict.get('on_ground', False),
                    seen=aircraft_dict.get('seen'),
                    rssi=aircraft_dict.get('rssi'),  # Signal strength
                    messages=aircraft_dict.get('messages'),  # Message count
                    data_source="dump1090"
                )
                
                # Only include aircraft with hex code
                if aircraft.hex:
                    aircraft_list.append(aircraft)
                    
            except (TypeError, ValueError) as e:
                logger.debug(f"Failed to parse dump1090 aircraft: {e}")
                continue
        
        return aircraft_list
    
    def get_stats(self) -> dict:
        """Get collector statistics including dump1090-specific info"""
        stats = super().get_stats()
        stats.update({
            "local_receiver": True,
            "url": self.url
        })
        return stats