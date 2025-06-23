"""
MCP Tools for Flight Tracker Collector.

Provides structured tools for AI assistants to interact with flight tracking data.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp.types import Tool

from ..services.redis_service import RedisService
from ..services.collector_service import CollectorService

logger = logging.getLogger(__name__)


class FlightTrackerTools:
    """Flight tracking tools for MCP"""
    
    def __init__(self, redis_service: RedisService, collector_service: CollectorService = None):
        self.redis_service = redis_service
        self.collector_service = collector_service
    
    def list_tools(self) -> List[Tool]:
        """List all available flight tracking tools"""
        return [
            Tool(
                name="search_flights",
                description="Search for flights in a specific region with optional filtering",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "Region name (e.g., 'etex')",
                            "default": "etex"
                        },
                        "aircraft_type": {
                            "type": "string",
                            "description": "Filter by aircraft type: 'all', 'helicopters', 'fixed_wing'",
                            "enum": ["all", "helicopters", "fixed_wing"],
                            "default": "all"
                        },
                        "min_altitude": {
                            "type": "number",
                            "description": "Minimum altitude in feet",
                            "minimum": 0
                        },
                        "max_altitude": {
                            "type": "number", 
                            "description": "Maximum altitude in feet",
                            "maximum": 60000
                        },
                        "distance_radius": {
                            "type": "number",
                            "description": "Maximum distance from region center in miles",
                            "minimum": 1,
                            "maximum": 500
                        }
                    },
                    "required": ["region"]
                }
            ),
            
            Tool(
                name="get_aircraft_details",
                description="Get detailed information about a specific aircraft",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "hex_code": {
                            "type": "string",
                            "description": "Aircraft ICAO hex code (e.g., 'a12345')",
                            "pattern": "^[a-fA-F0-9]{6}$"
                        }
                    },
                    "required": ["hex_code"]
                }
            ),
            
            Tool(
                name="track_helicopters",
                description="Get helicopter-specific tracking data for a region",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string", 
                            "description": "Region name (e.g., 'etex')",
                            "default": "etex"
                        },
                        "include_details": {
                            "type": "boolean",
                            "description": "Include detailed aircraft information",
                            "default": True
                        }
                    },
                    "required": ["region"]
                }
            ),
            
            Tool(
                name="get_region_stats",
                description="Get statistics and summary for a specific region",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "Region name (e.g., 'etex')",
                            "default": "etex"
                        }
                    },
                    "required": ["region"]
                }
            ),
            
            Tool(
                name="get_system_status",
                description="Get overall system health and performance metrics",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            
            Tool(
                name="check_data_sources",
                description="Check status of all data collection sources",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "Filter by specific region (optional)"
                        }
                    }
                }
            ),
            
            Tool(
                name="get_aircraft_by_distance",
                description="Get aircraft sorted by distance from a point",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "Region name (e.g., 'etex')",
                            "default": "etex"
                        },
                        "latitude": {
                            "type": "number",
                            "description": "Reference latitude (-90 to 90)",
                            "minimum": -90,
                            "maximum": 90
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Reference longitude (-180 to 180)", 
                            "minimum": -180,
                            "maximum": 180
                        },
                        "max_distance": {
                            "type": "number",
                            "description": "Maximum distance in miles",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of aircraft to return",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 10
                        }
                    },
                    "required": ["region", "latitude", "longitude"]
                }
            )
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a flight tracking tool"""
        try:
            if name == "search_flights":
                return await self._search_flights(**arguments)
            elif name == "get_aircraft_details":
                return await self._get_aircraft_details(**arguments)
            elif name == "track_helicopters":
                return await self._track_helicopters(**arguments)
            elif name == "get_region_stats":
                return await self._get_region_stats(**arguments)
            elif name == "get_system_status":
                return await self._get_system_status()
            elif name == "check_data_sources":
                return await self._check_data_sources(**arguments)
            elif name == "get_aircraft_by_distance":
                return await self._get_aircraft_by_distance(**arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return {
                "error": str(e),
                "tool": name,
                "arguments": arguments,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _search_flights(self, region: str, aircraft_type: str = "all", 
                            min_altitude: Optional[float] = None,
                            max_altitude: Optional[float] = None,
                            distance_radius: Optional[float] = None) -> Dict[str, Any]:
        """Search for flights with filtering"""
        
        # Get flight data from Redis
        if aircraft_type == "helicopters":
            data = self.redis_service.get_region_data(region, "choppers")
        else:
            data = self.redis_service.get_region_data(region, "flights")
        
        if not data or not data.get("aircraft"):
            return {
                "region": region,
                "aircraft_type": aircraft_type,
                "aircraft": [],
                "count": 0,
                "filters_applied": {
                    "min_altitude": min_altitude,
                    "max_altitude": max_altitude,
                    "distance_radius": distance_radius
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
        aircraft = data["aircraft"]
        
        # Apply filters
        if aircraft_type == "fixed_wing":
            # Filter out helicopters (ICAO class starting with 'H')
            aircraft = [a for a in aircraft if not a.get("icao_aircraft_class", "").startswith("H")]
        
        if min_altitude is not None:
            aircraft = [a for a in aircraft if a.get("alt_baro", 0) >= min_altitude]
        
        if max_altitude is not None:
            aircraft = [a for a in aircraft if a.get("alt_baro", float('inf')) <= max_altitude]
        
        if distance_radius is not None:
            aircraft = [a for a in aircraft if a.get("distance_miles", float('inf')) <= distance_radius]
        
        return {
            "region": region,
            "aircraft_type": aircraft_type,
            "aircraft": aircraft,
            "count": len(aircraft),
            "total_before_filtering": len(data["aircraft"]),
            "filters_applied": {
                "min_altitude": min_altitude,
                "max_altitude": max_altitude,
                "distance_radius": distance_radius
            },
            "last_update": data.get("timestamp"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _get_aircraft_details(self, hex_code: str) -> Dict[str, Any]:
        """Get detailed information about a specific aircraft"""
        hex_code = hex_code.lower()
        
        # Look for aircraft in live data
        aircraft_key = f"aircraft_live:{hex_code}"
        aircraft_data = self.redis_service.get_data(aircraft_key)
        
        if not aircraft_data:
            # Search across all regions
            regions = ["etex"]  # Add more regions as configured
            for region in regions:
                flights_data = self.redis_service.get_region_data(region, "flights")
                if flights_data and flights_data.get("aircraft"):
                    for aircraft in flights_data["aircraft"]:
                        if aircraft.get("hex", "").lower() == hex_code:
                            aircraft_data = aircraft
                            break
                if aircraft_data:
                    break
        
        if not aircraft_data:
            return {
                "hex_code": hex_code,
                "found": False,
                "error": "Aircraft not found in current data",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return {
            "hex_code": hex_code,
            "found": True,
            "aircraft": aircraft_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _track_helicopters(self, region: str, include_details: bool = True) -> Dict[str, Any]:
        """Get helicopter tracking data"""
        data = self.redis_service.get_region_data(region, "choppers")
        
        if not data:
            return {
                "region": region,
                "helicopters": [],
                "count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        helicopters = data.get("aircraft", [])
        
        if not include_details:
            # Return simplified data
            helicopters = [
                {
                    "hex": h.get("hex"),
                    "flight": h.get("flight"),
                    "registration": h.get("registration"),
                    "lat": h.get("lat"),
                    "lon": h.get("lon"),
                    "alt_baro": h.get("alt_baro"),
                    "distance_miles": h.get("distance_miles")
                }
                for h in helicopters
            ]
        
        return {
            "region": region,
            "helicopters": helicopters,
            "count": len(helicopters),
            "last_update": data.get("timestamp"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _get_region_stats(self, region: str) -> Dict[str, Any]:
        """Get regional statistics"""
        flights_data = self.redis_service.get_region_data(region, "flights")
        choppers_data = self.redis_service.get_region_data(region, "choppers")
        
        stats = {
            "region": region,
            "flights": {
                "count": 0,
                "last_update": None
            },
            "helicopters": {
                "count": 0,
                "last_update": None
            },
            "data_sources": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if flights_data:
            stats["flights"]["count"] = flights_data.get("aircraft_count", 0)
            stats["flights"]["last_update"] = flights_data.get("timestamp")
            
            # Analyze data sources
            for aircraft in flights_data.get("aircraft", []):
                source = aircraft.get("data_source", "unknown")
                if source not in stats["data_sources"]:
                    stats["data_sources"][source] = 0
                stats["data_sources"][source] += 1
        
        if choppers_data:
            stats["helicopters"]["count"] = choppers_data.get("aircraft_count", 0)
            stats["helicopters"]["last_update"] = choppers_data.get("timestamp")
        
        return stats
    
    async def _get_system_status(self) -> Dict[str, Any]:
        """Get system health status"""
        redis_status = self.redis_service.get_system_status()
        
        status = {
            "system": "healthy",
            "redis": redis_status,
            "collectors": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.collector_service:
            # Get collector information
            status["collectors"] = {
                "regions": list(self.collector_service.region_collectors.keys()) if hasattr(self.collector_service, 'region_collectors') else [],
                "active": True
            }
        
        return status
    
    async def _check_data_sources(self, region: Optional[str] = None) -> Dict[str, Any]:
        """Check data source status"""
        sources = {
            "sources": {},
            "summary": {
                "total_sources": 0,
                "active_sources": 0,
                "regions": []
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        regions_to_check = [region] if region else ["etex"]
        
        for region_name in regions_to_check:
            flights_data = self.redis_service.get_region_data(region_name, "flights")
            if flights_data and flights_data.get("aircraft"):
                region_sources = {}
                for aircraft in flights_data["aircraft"]:
                    source = aircraft.get("data_source", "unknown")
                    if source not in region_sources:
                        region_sources[source] = {
                            "count": 0,
                            "last_seen": None
                        }
                    region_sources[source]["count"] += 1
                
                sources["sources"][region_name] = region_sources
                sources["summary"]["regions"].append(region_name)
                sources["summary"]["total_sources"] += len(region_sources)
                sources["summary"]["active_sources"] += len([s for s in region_sources.values() if s["count"] > 0])
        
        return sources
    
    async def _get_aircraft_by_distance(self, region: str, latitude: float, longitude: float,
                                      max_distance: float = 50, limit: int = 10) -> Dict[str, Any]:
        """Get aircraft sorted by distance from a point"""
        import math
        
        def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Calculate distance between two points in miles using Haversine formula"""
            R = 3959  # Earth's radius in miles
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat / 2) ** 2 +
                 math.cos(lat1_rad) * math.cos(lat2_rad) *
                 math.sin(delta_lon / 2) ** 2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            
            return R * c
        
        flights_data = self.redis_service.get_region_data(region, "flights")
        if not flights_data or not flights_data.get("aircraft"):
            return {
                "region": region,
                "reference_point": {"latitude": latitude, "longitude": longitude},
                "aircraft": [],
                "count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Calculate distances and filter
        aircraft_with_distance = []
        for aircraft in flights_data["aircraft"]:
            aircraft_lat = aircraft.get("lat")
            aircraft_lon = aircraft.get("lon")
            
            if aircraft_lat is not None and aircraft_lon is not None:
                distance = calculate_distance(latitude, longitude, aircraft_lat, aircraft_lon)
                if distance <= max_distance:
                    aircraft_copy = aircraft.copy()
                    aircraft_copy["calculated_distance"] = round(distance, 2)
                    aircraft_with_distance.append(aircraft_copy)
        
        # Sort by distance and limit results
        aircraft_with_distance.sort(key=lambda x: x["calculated_distance"])
        aircraft_with_distance = aircraft_with_distance[:limit]
        
        return {
            "region": region,
            "reference_point": {"latitude": latitude, "longitude": longitude},
            "max_distance": max_distance,
            "aircraft": aircraft_with_distance,
            "count": len(aircraft_with_distance),
            "total_in_region": len(flights_data["aircraft"]),
            "timestamp": datetime.utcnow().isoformat()
        }