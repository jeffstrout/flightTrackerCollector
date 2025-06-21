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
        self.last_429_time = 0  # Track when we last got rate limited
        
        # Authentication setup
        self.auth = None
        if not self.anonymous and self.username and self.password:
            self.auth = (self.username, self.password)
            logger.info(f"OpenSky collector configured with authentication for {self.username}")
        else:
            logger.info("OpenSky collector configured for anonymous access")
        
        # Log configuration details
        logger.info(f"OpenSky collector initialized:")
        logger.info(f"  - URL: {self.url}")
        logger.info(f"  - Region: {region_config.get('name', 'unknown')} "
                   f"(center: {self.center_lat:.3f}, {self.center_lon:.3f})")
        logger.info(f"  - Radius: {region_config.get('radius_miles', 'unknown')} miles")
        logger.info(f"  - Enabled: {self.enabled}")
        logger.info(f"  - Anonymous: {self.anonymous}")
    
    async def fetch_data(self) -> Optional[List[Aircraft]]:
        """Fetch data from OpenSky Network API"""
        if not self.enabled:
            return None
        
        # Rate limiting check - use 429 time if we're in backoff mode
        current_time = time.time()
        
        # If we're in 5-minute backoff mode after 429, use that timestamp
        if self.min_interval >= 300 and self.last_429_time > 0:
            time_since_429 = current_time - self.last_429_time
            if time_since_429 < self.min_interval:
                wait_time = self.min_interval - time_since_429
                logger.info(f"OpenSky 429 backoff active: waiting {wait_time:.1f}s (since 429: {time_since_429:.1f}s)")
                return None
            else:
                # Backoff period is over, reset to normal interval
                logger.info(f"OpenSky 429 backoff period ended, resetting to normal interval")
                self.min_interval = 10
                self.last_429_time = 0
        else:
            # Normal rate limiting based on last successful request
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                logger.info(f"OpenSky normal backoff active: waiting {wait_time:.1f}s")
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
            
            # Make API request with detailed error handling
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"Making OpenSky request to {self.url}")
                response = await client.get(
                    self.url,
                    params=params,
                    auth=self.auth
                )
                logger.debug(f"OpenSky response status: {response.status_code}")
                
                response.raise_for_status()
                
                # Check for rate limit headers
                self.credits_remaining = response.headers.get('X-Rate-Limit-Remaining')
                reset_time = response.headers.get('X-Rate-Limit-Reset')
                if self.credits_remaining:
                    self.credits_remaining = int(self.credits_remaining)
                
                data = response.json()
            
            # Only update last_request_time on successful requests
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
            
            # Enhanced logging with rate limit info
            rate_info = []
            if self.credits_remaining is not None:
                rate_info.append(f"{self.credits_remaining} credits remaining")
            if reset_time:
                rate_info.append(f"reset: {reset_time}")
            
            rate_msg = f" | {' | '.join(rate_info)}" if rate_info else ""
            logger.info(f"OpenSky: {len(aircraft_list)} aircraft in {fetch_time:.2f}s{rate_msg}")
            
            return aircraft_list
            
        except httpx.HTTPStatusError as e:
            self.update_stats(False)
            if e.response.status_code == 429:
                # Check rate limit headers from 429 response
                remaining = e.response.headers.get('X-Rate-Limit-Remaining', 'unknown')
                reset_time = e.response.headers.get('X-Rate-Limit-Reset', 'unknown')
                
                logger.warning(f"OpenSky rate limited: {e} | Remaining: {remaining} | Reset: {reset_time}")
                
                # Set backoff to 5 minutes when rate limited and track when it started
                old_interval = self.min_interval
                self.min_interval = 300  # 5 minutes
                self.last_429_time = current_time  # Remember when we got rate limited
                logger.warning(f"OpenSky backoff: {old_interval}s → {self.min_interval}s (5 minutes due to rate limit)")
            else:
                logger.error(f"OpenSky HTTP error {e.response.status_code}: {e}")
            return None
            
        except httpx.TimeoutException as e:
            self.update_stats(False)
            logger.error(f"OpenSky request timeout: {e}")
            return None
            
        except httpx.ConnectError as e:
            self.update_stats(False)
            logger.error(f"OpenSky connection error: {e}")
            return None
            
        except httpx.RequestError as e:
            self.update_stats(False)
            logger.error(f"OpenSky request error: {e}")
            return None
            
        except Exception as e:
            self.update_stats(False)
            logger.error(f"OpenSky fetch failed: {type(e).__name__}: {e}")
            logger.debug(f"OpenSky error details", exc_info=True)
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