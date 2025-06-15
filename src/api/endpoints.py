import csv
import io
from typing import Dict, List
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from ..services.redis_service import RedisService
from ..services.collector_service import CollectorService
from ..models.aircraft import AircraftResponse

router = APIRouter()
redis_service = RedisService()


def format_tabular_data(data: Dict) -> str:
    """Convert aircraft data to CSV format"""
    if not data or not data.get('aircraft'):
        return "timestamp,hex,flight,registration,lat,lon,alt_baro,gs,track,distance_miles,data_source\n"
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'timestamp', 'hex', 'flight', 'registration', 'lat', 'lon', 
        'alt_baro', 'gs', 'track', 'distance_miles', 'data_source',
        'model', 'operator'
    ])
    
    # Write aircraft data
    for aircraft in data['aircraft']:
        writer.writerow([
            data.get('timestamp', ''),
            aircraft.get('hex', ''),
            aircraft.get('flight', ''),
            aircraft.get('registration', ''),
            aircraft.get('lat', ''),
            aircraft.get('lon', ''),
            aircraft.get('alt_baro', ''),
            aircraft.get('gs', ''),
            aircraft.get('track', ''),
            aircraft.get('distance_miles', ''),
            aircraft.get('data_source', ''),
            aircraft.get('model', ''),
            aircraft.get('operator', '')
        ])
    
    return output.getvalue()


@router.get("/status")
async def get_status() -> Dict:
    """Get system status and health information"""
    # Get Redis status
    redis_status = redis_service.get_system_status()
    
    # Get collector stats if available
    collector_stats = {}
    try:
        # Note: In a real implementation, you'd have access to the collector service instance
        # For now, we'll return basic status
        collector_stats = {"message": "Collector stats would be available here"}
    except Exception:
        pass
    
    return {
        "status": "healthy",
        "timestamp": redis_service.redis_client.time()[0] if redis_service.redis_client else None,
        "redis": redis_status,
        "collectors": collector_stats
    }


@router.get("/{region}/flights")
async def get_region_flights(region: str) -> Dict:
    """Get all flights for a region in JSON format"""
    data = redis_service.get_region_data(region, "flights")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No flight data found for region: {region}")
    
    return data


@router.get("/{region}/flights/tabular", response_class=PlainTextResponse)
async def get_region_flights_tabular(region: str) -> str:
    """Get all flights for a region in CSV format"""
    data = redis_service.get_region_data(region, "flights")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No flight data found for region: {region}")
    
    return format_tabular_data(data)


@router.get("/{region}/choppers")
async def get_region_helicopters(region: str) -> Dict:
    """Get helicopters only for a region in JSON format"""
    data = redis_service.get_region_data(region, "choppers")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No helicopter data found for region: {region}")
    
    return data


@router.get("/{region}/choppers/tabular", response_class=PlainTextResponse)
async def get_region_helicopters_tabular(region: str) -> str:
    """Get helicopters only for a region in CSV format"""
    data = redis_service.get_region_data(region, "choppers")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No helicopter data found for region: {region}")
    
    return format_tabular_data(data)


@router.get("/{region}/stats")
async def get_region_stats(region: str) -> Dict:
    """Get statistics for a specific region"""
    flights_data = redis_service.get_region_data(region, "flights")
    choppers_data = redis_service.get_region_data(region, "choppers")
    
    if not flights_data and not choppers_data:
        raise HTTPException(status_code=404, detail=f"No data found for region: {region}")
    
    stats = {
        "region": region,
        "flights": {
            "count": flights_data.get("aircraft_count", 0) if flights_data else 0,
            "last_update": flights_data.get("timestamp") if flights_data else None
        },
        "helicopters": {
            "count": choppers_data.get("aircraft_count", 0) if choppers_data else 0,
            "last_update": choppers_data.get("timestamp") if choppers_data else None
        }
    }
    
    return stats


@router.get("/debug/memory")
async def get_memory_debug() -> Dict:
    """Debug endpoint to see what's in memory"""
    return {
        "memory_store_keys": list(redis_service.memory_store.keys()),
        "memory_store_data": redis_service.memory_store
    }