import math
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..models.aircraft import Aircraft

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Base class for all flight data collectors"""
    
    def __init__(self, collector_config: dict, region_config: dict):
        self.config = collector_config
        self.region_config = region_config
        self.name = collector_config.get("name", collector_config["type"])
        self.enabled = collector_config.get("enabled", True)
        self.url = collector_config["url"]
        
        # Region center for distance calculations
        self.center_lat = region_config["center"]["lat"]
        self.center_lon = region_config["center"]["lon"]
        self.radius_miles = region_config["radius_miles"]
        
        # Statistics
        self.stats = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "last_fetch": None,
            "last_aircraft_count": 0
        }
    
    @abstractmethod
    async def fetch_data(self) -> Optional[List[Aircraft]]:
        """Fetch aircraft data from the source"""
        pass
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return float('inf')
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 3956  # Radius of earth in miles
        return c * r
    
    def calculate_bounding_box(self) -> Tuple[float, float, float, float]:
        """Calculate bounding box for the region"""
        # Approximate conversion: 1 degree ≈ 69 miles
        degree_offset = self.radius_miles / 69.0
        
        lat_min = self.center_lat - degree_offset
        lat_max = self.center_lat + degree_offset
        lon_min = self.center_lon - degree_offset
        lon_max = self.center_lon + degree_offset
        
        return lat_min, lat_max, lon_min, lon_max
    
    def add_distance_and_filter(self, aircraft_list: List[Aircraft]) -> List[Aircraft]:
        """Add distance calculation and filter by radius"""
        filtered_aircraft = []
        
        for aircraft in aircraft_list:
            if aircraft.lat is None or aircraft.lon is None:
                continue
            
            distance = self.calculate_distance(
                aircraft.lat, aircraft.lon, 
                self.center_lat, self.center_lon
            )
            
            if distance <= self.radius_miles:
                aircraft.distance_miles = round(distance, 1)
                filtered_aircraft.append(aircraft)
        
        return filtered_aircraft
    
    def sort_by_distance(self, aircraft_list: List[Aircraft]) -> List[Aircraft]:
        """Sort aircraft by distance from center"""
        return sorted(
            aircraft_list, 
            key=lambda a: a.distance_miles if a.distance_miles is not None else float('inf')
        )
    
    def update_stats(self, success: bool, aircraft_count: int = 0):
        """Update collector statistics"""
        self.stats["requests"] += 1
        self.stats["last_fetch"] = datetime.now().isoformat()
        
        if success:
            self.stats["successes"] += 1
            self.stats["last_aircraft_count"] = aircraft_count
        else:
            self.stats["failures"] += 1
    
    def get_stats(self) -> Dict:
        """Get collector statistics"""
        total_requests = self.stats["requests"]
        if total_requests > 0:
            success_rate = (self.stats["successes"] / total_requests) * 100
        else:
            success_rate = 0
        
        return {
            "collector": self.name,
            "type": self.config["type"],
            "enabled": self.enabled,
            "requests": total_requests,
            "success_rate": round(success_rate, 1),
            "last_fetch": self.stats["last_fetch"],
            "last_aircraft_count": self.stats["last_aircraft_count"]
        }