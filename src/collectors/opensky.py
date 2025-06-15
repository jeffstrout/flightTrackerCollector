import time
import logging
from typing import List, Optional
import httpx

from .base import BaseCollector
from ..models.aircraft import Aircraft

logger = logging.getLogger(__name__)


class OpenSkyCollector(BaseCollector):
    """OpenSky Network API collector"""
    
    def __init__(self, collector_config: dict, region_config: dict):
        super().__init__(collector_config, region_config)
        
        self.anonymous = collector_config.get("anonymous", True)
        self.username = collector_config.get("username")
        self.password = collector_config.get("password")
        
        # Rate limiting
        self.last_request_time = 0
        self.min_interval = 10  # Minimum 10 seconds between requests
        self.credits_remaining = None
        
        # Authentication setup
        self.auth = None
        if not self.anonymous and self.username and self.password:
            self.auth = (self.username, self.password)
            logger.info(f"OpenSky collector configured with authentication for {self.username}")
        else:
            logger.info("OpenSky collector configured for anonymous access")
    
    async def fetch_data(self) -> Optional[List[Aircraft]]:
        """Fetch data from OpenSky Network API"""
        if not self.enabled:
            return None
        
        # Rate limiting check
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_interval:
            logger.debug(f"OpenSky rate limit: waiting {self.min_interval - time_since_last:.1f}s")
            return None
        
        fetch_start = time.time()
        
        try:
            # Calculate bounding box
            lat_min, lat_max, lon_min, lon_max = self.calculate_bounding_box()
            
            # Build API parameters
            params = {
                'lamin': lat_min,
                'lamax': lat_max,
                'lomin': lon_min,
                'lomax': lon_max
            }
            
            logger.debug(f"OpenSky request: {params}")
            
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.url,
                    params=params,
                    auth=self.auth
                )
                
                response.raise_for_status()
                
                # Check for rate limit headers
                self.credits_remaining = response.headers.get('X-Rate-Limit-Remaining')
                if self.credits_remaining:
                    self.credits_remaining = int(self.credits_remaining)
                
                data = response.json()
            
            self.last_request_time = current_time
            fetch_time = time.time() - fetch_start
            
            # Convert OpenSky data to Aircraft objects
            aircraft_list = self._convert_opensky_data(data)
            
            # Add distance calculation (but don't filter - already filtered by bounding box)
            for aircraft in aircraft_list:
                if aircraft.lat is not None and aircraft.lon is not None:
                    distance = self.calculate_distance(
                        aircraft.lat, aircraft.lon, 
                        self.center_lat, self.center_lon
                    )
                    aircraft.distance_miles = round(distance, 1)
            
            # Sort by distance
            aircraft_list = self.sort_by_distance(aircraft_list)
            
            self.update_stats(True, len(aircraft_list))
            
            credits_msg = f", {self.credits_remaining} credits remaining" if self.credits_remaining else ""
            logger.info(f"OpenSky: {len(aircraft_list)} aircraft in {fetch_time:.2f}s{credits_msg}")
            
            return aircraft_list
            
        except httpx.HTTPStatusError as e:
            self.update_stats(False)
            if e.response.status_code == 429:
                logger.warning(f"OpenSky rate limited: {e}")
                # Increase minimum interval when rate limited
                self.min_interval = min(120, self.min_interval * 2)
            else:
                logger.error(f"OpenSky HTTP error {e.response.status_code}: {e}")
            return None
            
        except Exception as e:
            self.update_stats(False)
            logger.error(f"OpenSky fetch failed: {e}")
            return None
    
    def _convert_opensky_data(self, data: dict) -> List[Aircraft]:
        """Convert OpenSky state vectors to Aircraft objects"""
        aircraft_list = []
        
        states = data.get('states', [])
        if not states:
            return aircraft_list
        
        for state in states:
            try:
                # OpenSky state vector format (array indices)
                aircraft = Aircraft(
                    hex=state[0] if state[0] else '',  # icao24
                    flight=state[1].strip() if state[1] else '',  # callsign
                    lat=state[6] if state[6] is not None else None,  # latitude
                    lon=state[5] if state[5] is not None else None,  # longitude
                    alt_baro=self._meters_to_feet(state[7]) if state[7] is not None else None,  # baro alt
                    alt_geom=self._meters_to_feet(state[13]) if state[13] is not None else None,  # geo alt
                    gs=self._ms_to_knots(state[9]) if state[9] is not None else None,  # velocity
                    track=round(state[10], 1) if state[10] is not None else None,  # true track
                    baro_rate=self._ms_to_fpm(state[11]) if state[11] is not None else None,  # vertical rate
                    squawk=state[14] if state[14] else None,  # squawk
                    on_ground=state[8] if state[8] is not None else False,  # on ground
                    seen=int(time.time() - state[4]) if state[4] else None,  # time since last contact
                    data_source="opensky"
                )
                
                # Only include aircraft with position and hex code
                if aircraft.hex and aircraft.lat is not None and aircraft.lon is not None:
                    aircraft_list.append(aircraft)
                    
            except (IndexError, TypeError, ValueError) as e:
                logger.debug(f"Failed to parse OpenSky state vector: {e}")
                continue
        
        return aircraft_list
    
    @staticmethod
    def _meters_to_feet(meters: float) -> int:
        """Convert meters to feet"""
        return int(meters * 3.28084)
    
    @staticmethod
    def _ms_to_knots(ms: float) -> float:
        """Convert m/s to knots"""
        return round(ms * 1.94384, 1)
    
    @staticmethod
    def _ms_to_fpm(ms: float) -> float:
        """Convert m/s to ft/min"""
        return round(ms * 196.85, 1)
    
    def get_stats(self) -> dict:
        """Get collector statistics including OpenSky-specific info"""
        stats = super().get_stats()
        stats.update({
            "credits_remaining": self.credits_remaining,
            "authenticated": not self.anonymous,
            "min_interval": self.min_interval
        })
        return stats