import csv
import io
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..services.redis_service import RedisService
from ..services.collector_service import CollectorService
from ..models.aircraft import AircraftResponse
from ..config.loader import load_config

router = APIRouter()
redis_service = RedisService()


class CollectorInfo(BaseModel):
    """Information about a collector"""
    type: str
    enabled: bool
    url: str
    name: str | None = None


class RegionInfo(BaseModel):
    """Information about a configured region"""
    name: str
    enabled: bool
    center: Dict[str, float]  # lat, lon
    radius_miles: float
    collectors: List[CollectorInfo]


class RegionsResponse(BaseModel):
    """Response for regions endpoint"""
    regions: List[RegionInfo]
    total_regions: int


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


@router.get("/regions", response_model=RegionsResponse)
async def get_regions() -> RegionsResponse:
    """Get all configured regions with their collectors
    
    Returns a list of all regions configured in the system, including:
    - Region name and enabled status
    - Center coordinates (lat/lon)
    - Coverage radius in miles
    - List of data collectors (type, URL, enabled status)
    """
    try:
        # Load the configuration
        config = load_config()
        
        regions_list = []
        for region_key, region_config in config.regions.items():
            # Build collector info list
            collectors_info = []
            for collector in region_config.collectors:
                collector_info = CollectorInfo(
                    type=collector.type,
                    enabled=collector.enabled,
                    url=collector.url,
                    name=collector.name
                )
                collectors_info.append(collector_info)
            
            # Build region info
            region_info = RegionInfo(
                name=region_config.name,
                enabled=region_config.enabled,
                center=region_config.center,
                radius_miles=region_config.radius_miles,
                collectors=collectors_info
            )
            regions_list.append(region_info)
        
        return RegionsResponse(
            regions=regions_list,
            total_regions=len(regions_list)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")


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


@router.get("/debug/logs-info")
async def get_logs_debug_info() -> Dict:
    """Debug endpoint to check logging configuration and file locations"""
    import logging
    import os
    
    debug_info = {
        "current_working_directory": os.getcwd(),
        "environment_variables": {
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "not set")
        },
        "logging_handlers": [],
        "file_searches": {}
    }
    
    # Check current logging handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler_info = {
            "type": type(handler).__name__,
            "level": logging.getLevelName(handler.level)
        }
        if hasattr(handler, 'baseFilename'):
            handler_info["filename"] = handler.baseFilename
            handler_info["file_exists"] = Path(handler.baseFilename).exists()
        debug_info["logging_handlers"].append(handler_info)
    
    # Search for log files in various locations
    search_locations = [
        "/app/logs",
        "/app", 
        "logs",
        ".",
        "/tmp",
        "/var/log"
    ]
    
    for location in search_locations:
        path = Path(location)
        if path.exists() and path.is_dir():
            try:
                files = list(path.glob("**/*.log*"))
                debug_info["file_searches"][str(location)] = [str(f) for f in files]
            except:
                debug_info["file_searches"][str(location)] = "access denied"
        else:
            debug_info["file_searches"][str(location)] = "not found"
    
    return debug_info


async def get_cloudwatch_logs(lines: int = 100) -> str:
    """Fetch logs from AWS CloudWatch"""
    try:
        import boto3
        from datetime import datetime, timedelta
        
        # Initialize CloudWatch Logs client
        logs_client = boto3.client('logs')
        log_group_name = '/ecs/flight-tracker'
        
        # Get the most recent log streams
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=5  # Get latest 5 streams
        )
        
        if not streams_response['logStreams']:
            return "No log streams found in CloudWatch log group /ecs/flight-tracker"
        
        # Collect log events from recent streams
        all_events = []
        
        for stream in streams_response['logStreams']:
            stream_name = stream['logStreamName']
            
            try:
                # Get log events from this stream (last hour to avoid too much data)
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
                
                events_response = logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream_name,
                    startTime=int(start_time.timestamp() * 1000),
                    endTime=int(end_time.timestamp() * 1000),
                    limit=lines,  # Limit per stream
                    startFromHead=False  # Get most recent
                )
                
                for event in events_response['events']:
                    all_events.append({
                        'timestamp': event['timestamp'],
                        'message': event['message'],
                        'stream': stream_name
                    })
                    
            except Exception as stream_error:
                # Skip streams we can't access, but don't fail entirely
                continue
        
        # Sort by timestamp and get the most recent entries
        all_events.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_events = all_events[:lines]
        
        if not recent_events:
            return "No recent log events found in CloudWatch"
        
        # Format the log output
        log_output = []
        log_output.append(f"=== CloudWatch Logs (Last {len(recent_events)} entries) ===\n")
        
        for event in reversed(recent_events):  # Show chronologically
            # Convert timestamp to readable format
            dt = datetime.fromtimestamp(event['timestamp'] / 1000)
            formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Clean up the message (remove extra newlines/formatting)
            message = event['message'].rstrip()
            
            log_output.append(f"[{formatted_time}] {message}")
        
        return '\n'.join(log_output)
        
    except Exception as e:
        # If CloudWatch access fails, provide helpful error
        error_msg = str(e)
        if 'AccessDenied' in error_msg:
            return f"""CloudWatch Access Error: {error_msg}

The application needs CloudWatch Logs permissions. 
Please ensure the ECS task role has the following policy:

{{
    "Version": "2012-10-17",
    "Statement": [
        {{
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogStreams",
                "logs:GetLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/ecs/flight-tracker:*"
        }}
    ]
}}
"""
        else:
            return f"Error accessing CloudWatch logs: {error_msg}"


@router.get("/logs", response_class=PlainTextResponse)
async def get_logs(lines: int = 100) -> str:
    """Get the last N lines from the flight collector log file
    
    Args:
        lines: Number of lines to return (default: 100, max: 1000)
    
    Returns:
        Last N lines of the log file as plain text
    """
    # Limit the number of lines to prevent abuse
    lines = min(max(lines, 1), 1000)
    
    # Get actual log file from logging handlers
    import logging
    import os
    log_file = None
    
    # First, try to get the file from the current logging configuration
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if hasattr(handler, 'baseFilename'):
            potential_file = Path(handler.baseFilename)
            if potential_file.exists():
                log_file = potential_file
                break
    
    # If not found in handlers, try traditional locations
    if log_file is None:
        possible_paths = [
            Path("logs") / "flight_collector.log",  # Local development
            Path("/app/logs") / "flight_collector.log",  # Docker production
            Path("./logs") / "flight_collector.log",  # Relative path
        ]
        
        for path in possible_paths:
            if path.exists():
                log_file = path
                break
    
    # If still no log file found, check if we're in a production environment
    if log_file is None:
        # Check if we're running in AWS/Docker production
        is_production = (
            os.path.exists('/app') or 
            os.getenv('AWS_EXECUTION_ENV') or 
            os.getenv('ECS_CONTAINER_METADATA_URI')
        )
        
        if is_production:
            # Try to fetch from CloudWatch
            return await get_cloudwatch_logs(lines)
        
        # List available files for debugging in non-production
        debug_info = []
        for path in [Path("logs"), Path("/app/logs"), Path("./logs")]:
            if path.exists():
                try:
                    files = list(path.glob("*.log*"))
                    debug_info.append(f"{path}: {[f.name for f in files]}")
                except:
                    debug_info.append(f"{path}: access denied")
            else:
                debug_info.append(f"{path}: directory not found")
        
        raise HTTPException(
            status_code=404, 
            detail=f"Log file not found. Use /api/v1/debug/logs-info for detailed debugging. Quick check: {debug_info}"
        )
    
    try:
        # Read the last N lines efficiently using a deque (local file logging)
        from collections import deque
        
        with open(log_file, 'r', encoding='utf-8') as f:
            # Use deque with maxlen to efficiently keep only the last N lines
            last_lines = deque(f, maxlen=lines)
        
        # Join the lines and return as plain text
        return ''.join(last_lines)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file {log_file}: {str(e)}")