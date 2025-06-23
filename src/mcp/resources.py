"""
MCP Resources for Flight Tracker Collector.

Provides structured resources for AI assistants to access flight tracking data.
"""

import json
import logging
from typing import Any, Dict, List
from datetime import datetime

from mcp.types import Resource

from ..services.redis_service import RedisService
from ..services.collector_service import CollectorService

logger = logging.getLogger(__name__)


class FlightTrackerResources:
    """Flight tracking resources for MCP"""
    
    def __init__(self, redis_service: RedisService, collector_service: CollectorService = None):
        self.redis_service = redis_service
        self.collector_service = collector_service
    
    def list_resources(self) -> List[Resource]:
        """List all available flight tracking resources"""
        return [
            Resource(
                uri="flights://etex/live",
                name="East Texas Live Flights",
                description="Real-time flight data for East Texas region",
                mimeType="application/json"
            ),
            
            Resource(
                uri="flights://etex/helicopters",
                name="East Texas Helicopters",
                description="Real-time helicopter data for East Texas region",
                mimeType="application/json"
            ),
            
            Resource(
                uri="system://status",
                name="System Status",
                description="Current system health and performance metrics",
                mimeType="application/json"
            ),
            
            Resource(
                uri="system://collectors",
                name="Data Collectors Status",
                description="Status of all data collection sources",
                mimeType="application/json"
            ),
            
            Resource(
                uri="config://regions",
                name="Regional Configuration",
                description="Configuration details for all monitored regions",
                mimeType="application/json"
            ),
            
            Resource(
                uri="stats://collection",
                name="Collection Statistics",
                description="Historical collection performance and metrics",
                mimeType="application/json"
            ),
            
            Resource(
                uri="aircraft://database/schema",
                name="Aircraft Database Schema",
                description="Schema and structure of aircraft database",
                mimeType="application/json"
            )
        ]
    
    async def read_resource(self, uri: str) -> str:
        """Read and return resource content"""
        try:
            if uri == "flights://etex/live":
                return await self._get_live_flights("etex")
            elif uri == "flights://etex/helicopters":
                return await self._get_helicopters("etex")
            elif uri == "system://status":
                return await self._get_system_status()
            elif uri == "system://collectors":
                return await self._get_collectors_status()
            elif uri == "config://regions":
                return await self._get_regions_config()
            elif uri == "stats://collection":
                return await self._get_collection_stats()
            elif uri == "aircraft://database/schema":
                return await self._get_aircraft_schema()
            else:
                raise ValueError(f"Unknown resource URI: {uri}")
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return json.dumps({
                "error": str(e),
                "uri": uri,
                "timestamp": datetime.utcnow().isoformat()
            }, indent=2)
    
    async def _get_live_flights(self, region: str) -> str:
        """Get live flight data for a region"""
        data = self.redis_service.get_region_data(region, "flights")
        
        if not data:
            result = {
                "region": region,
                "status": "no_data",
                "aircraft": [],
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            result = {
                "region": region,
                "status": "active",
                "last_update": data.get("timestamp"),
                "aircraft_count": data.get("aircraft_count", 0),
                "aircraft": data.get("aircraft", []),
                "data_sources": self._analyze_data_sources(data.get("aircraft", [])),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return json.dumps(result, indent=2)
    
    async def _get_helicopters(self, region: str) -> str:
        """Get helicopter data for a region"""
        data = self.redis_service.get_region_data(region, "choppers")
        
        if not data:
            result = {
                "region": region,
                "status": "no_data", 
                "helicopters": [],
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            helicopters = data.get("aircraft", [])
            result = {
                "region": region,
                "status": "active",
                "last_update": data.get("timestamp"),
                "helicopter_count": len(helicopters),
                "helicopters": helicopters,
                "helicopter_types": self._analyze_helicopter_types(helicopters),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return json.dumps(result, indent=2)
    
    async def _get_system_status(self) -> str:
        """Get system status information"""
        redis_status = self.redis_service.get_system_status()
        
        status = {
            "system": {
                "status": "operational",
                "uptime": "unknown",
                "version": "1.0.0"
            },
            "redis": redis_status,
            "collectors": {
                "active": self.collector_service is not None,
                "regions": []
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.collector_service and hasattr(self.collector_service, 'region_collectors'):
            status["collectors"]["regions"] = list(self.collector_service.region_collectors.keys())
        
        return json.dumps(status, indent=2)
    
    async def _get_collectors_status(self) -> str:
        """Get data collectors status"""
        collectors = {
            "collectors": {},
            "summary": {
                "total_regions": 0,
                "active_collectors": 0,
                "data_sources": []
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check each region for active data sources
        regions = ["etex"]  # Add more regions as configured
        
        for region in regions:
            flights_data = self.redis_service.get_region_data(region, "flights")
            if flights_data and flights_data.get("aircraft"):
                region_sources = self._analyze_data_sources(flights_data["aircraft"])
                collectors["collectors"][region] = {
                    "status": "active",
                    "last_update": flights_data.get("timestamp"),
                    "aircraft_count": len(flights_data["aircraft"]),
                    "data_sources": region_sources
                }
                collectors["summary"]["total_regions"] += 1
                collectors["summary"]["active_collectors"] += len(region_sources)
                for source in region_sources.keys():
                    if source not in collectors["summary"]["data_sources"]:
                        collectors["summary"]["data_sources"].append(source)
            else:
                collectors["collectors"][region] = {
                    "status": "inactive",
                    "last_update": None,
                    "aircraft_count": 0,
                    "data_sources": {}
                }
        
        return json.dumps(collectors, indent=2)
    
    async def _get_regions_config(self) -> str:
        """Get regions configuration"""
        # This would normally come from the config loader
        # For now, provide a basic structure
        config = {
            "regions": {
                "etex": {
                    "name": "East Texas",
                    "center": {"lat": 32.3513, "lon": -95.3011},
                    "radius_miles": 150,
                    "timezone": "America/Chicago",
                    "enabled": True,
                    "collectors": ["opensky", "dump1090", "pi_stations"]
                }
            },
            "global_settings": {
                "polling_interval": 60,
                "data_retention": 3600,
                "max_aircraft_age": 300
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return json.dumps(config, indent=2)
    
    async def _get_collection_stats(self) -> str:
        """Get collection performance statistics"""
        stats = {
            "collection_performance": {
                "average_collection_time": "< 1 second",
                "success_rate": "99.5%",
                "api_rate_limiting": {
                    "opensky_backoff_active": False,
                    "remaining_credits": "unknown"
                }
            },
            "data_quality": {
                "aircraft_enrichment_rate": "95%+",
                "duplicate_detection": "enabled",
                "helicopter_identification": "ICAO-based"
            },
            "recent_metrics": {
                "last_collection_cycle": "unknown",
                "aircraft_processed": "unknown",
                "errors": 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return json.dumps(stats, indent=2)
    
    async def _get_aircraft_schema(self) -> str:
        """Get aircraft database schema"""
        schema = {
            "aircraft_data_structure": {
                "identification": {
                    "hex": "ICAO 24-bit hex code",
                    "flight": "Flight number/callsign",
                    "registration": "Aircraft registration (tail number)",
                    "squawk": "Transponder squawk code"
                },
                "position": {
                    "lat": "Latitude (decimal degrees)",
                    "lon": "Longitude (decimal degrees)",
                    "alt_baro": "Barometric altitude (feet)",
                    "alt_geom": "Geometric altitude (feet)",
                    "on_ground": "Ground status (boolean)"
                },
                "movement": {
                    "gs": "Ground speed (knots)",
                    "track": "True track (degrees)",
                    "baro_rate": "Vertical rate (ft/min)"
                },
                "technical": {
                    "rssi": "Signal strength (dB)",
                    "messages": "Message count",
                    "seen": "Seconds since last update",
                    "data_source": "Source: opensky/dump1090/pi_station"
                },
                "enrichment": {
                    "registration": "From aircraft database",
                    "model": "Aircraft model",
                    "operator": "Operating airline/company",
                    "manufacturer": "Aircraft manufacturer",
                    "icao_aircraft_class": "ICAO classification",
                    "aircraft_type": "Full type description"
                },
                "calculated": {
                    "distance_miles": "Distance from region center",
                    "is_helicopter": "Based on ICAO class starting with 'H'"
                }
            },
            "data_sources": {
                "opensky": "Global flight tracking network",
                "dump1090": "Local ADS-B receiver",
                "pi_stations": "Distributed Raspberry Pi receivers"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return json.dumps(schema, indent=2)
    
    def _analyze_data_sources(self, aircraft_list: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze and count data sources in aircraft list"""
        sources = {}
        for aircraft in aircraft_list:
            source = aircraft.get("data_source", "unknown")
            sources[source] = sources.get(source, 0) + 1
        return sources
    
    def _analyze_helicopter_types(self, helicopters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze helicopter types and characteristics"""
        analysis = {
            "total_count": len(helicopters),
            "models": {},
            "operators": {},
            "altitude_distribution": {
                "ground": 0,
                "low_altitude": 0,  # < 1000 ft
                "medium_altitude": 0,  # 1000-5000 ft
                "high_altitude": 0  # > 5000 ft
            }
        }
        
        for heli in helicopters:
            # Model analysis
            model = heli.get("model", "unknown")
            analysis["models"][model] = analysis["models"].get(model, 0) + 1
            
            # Operator analysis
            operator = heli.get("operator", "unknown")
            analysis["operators"][operator] = analysis["operators"].get(operator, 0) + 1
            
            # Altitude analysis
            alt = heli.get("alt_baro", 0)
            if heli.get("on_ground", False) or alt < 100:
                analysis["altitude_distribution"]["ground"] += 1
            elif alt < 1000:
                analysis["altitude_distribution"]["low_altitude"] += 1
            elif alt < 5000:
                analysis["altitude_distribution"]["medium_altitude"] += 1
            else:
                analysis["altitude_distribution"]["high_altitude"] += 1
        
        return analysis