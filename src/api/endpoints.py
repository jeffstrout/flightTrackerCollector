import csv
import io
import uuid
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, HTTPException, Response, Header, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from datetime import datetime

from ..services.redis_service import RedisService
from ..services.collector_service import CollectorService
from ..services.api_key_service import ApiKeyService
from ..services.aws_cost_service import AWSCostService
from ..models.aircraft import AircraftResponse
from ..models.api_key import BulkAircraftRequest, BulkAircraftResponse
from ..config.loader import load_config
from ..version import VERSION_INFO

router = APIRouter()
redis_service = RedisService()
api_key_service = ApiKeyService()

# Initialize AWS Cost Service (optional, requires AWS permissions)
try:
    aws_cost_service = AWSCostService()
except Exception as e:
    # Cost service initialization failed - endpoints will handle this gracefully
    aws_cost_service = None


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
        "version": VERSION_INFO,
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


@router.post("/aircraft/bulk", response_model=BulkAircraftResponse)
async def receive_bulk_aircraft_data(
    request: BulkAircraftRequest,
    x_api_key: str = Header(None, alias="X-API-Key")
) -> BulkAircraftResponse:
    """Receive bulk aircraft data from Pi stations
    
    This endpoint allows Raspberry Pi stations to submit aircraft data
    using regional API keys for authentication and validation.
    """
    import logging
    logger = logging.getLogger(__name__)
    request_id = str(uuid.uuid4())[:8]
    
    # Validate API key
    validation_result = api_key_service.validate_api_key(x_api_key)
    if not validation_result.is_valid:
        logger.warning(f"[{request_id}] API key validation failed: {validation_result.message}")
        
        # Determine appropriate HTTP status code
        status_code = 401  # Unauthorized
        if validation_result.error_code == "REGION_MISMATCH":
            status_code = 403  # Forbidden
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "status": "error",
                "error_code": validation_result.error_code,
                "message": validation_result.message,
                "details": {
                    "collector_region": api_key_service.get_collector_region(),
                    "provided_key_region": x_api_key.split('.')[0] if x_api_key and '.' in x_api_key else None,
                    "request_id": request_id
                }
            }
        )
    
    masked_key = api_key_service.mask_api_key(x_api_key)
    logger.info(f"[{request_id}] Processing bulk aircraft data from station '{request.station_name}' "
                f"(ID: {request.station_id}) with key {masked_key}")
    
    processed_count = 0
    errors = []
    
    try:
        # Process aircraft data
        if not request.aircraft:
            logger.warning(f"[{request_id}] No aircraft data provided")
            return BulkAircraftResponse(
                status="warning",
                message="No aircraft data provided",
                aircraft_count=0,
                processed_count=0,
                request_id=request_id
            )
        
        # Store aircraft data in Redis with station metadata
        redis_key = f"pi_data:{api_key_service.get_collector_region()}:{request.station_id}"
        
        # Enrich aircraft data with station information
        enriched_aircraft = []
        for aircraft in request.aircraft:
            try:
                # Add station metadata to aircraft data
                enriched_aircraft_data = {
                    **aircraft,
                    "data_source": f"pi_station_{request.station_id}",
                    "station_name": request.station_name,
                    "station_id": request.station_id,
                    "received_at": datetime.utcnow().isoformat(),
                    "region": api_key_service.get_collector_region()
                }
                enriched_aircraft.append(enriched_aircraft_data)
                processed_count += 1
                
            except Exception as e:
                error_msg = f"Error processing aircraft {aircraft.get('hex', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[{request_id}] {error_msg}")
        
        # Store processed data in Redis
        station_data = {
            "station_id": request.station_id,
            "station_name": request.station_name,
            "timestamp": request.timestamp.isoformat(),
            "aircraft_count": len(enriched_aircraft),
            "aircraft": enriched_aircraft,
            "metadata": request.metadata or {},
            "request_id": request_id
        }
        
        # Store with TTL (5 minutes like other flight data)
        redis_service.store_data(redis_key, station_data, ttl=300)
        
        # Also merge with main region data for immediate availability
        region = api_key_service.get_collector_region()
        existing_data = redis_service.get_region_data(region, "flights") or {"aircraft": []}
        
        # Merge Pi station data with existing data - replace old data from same station
        existing_aircraft = existing_data.get("aircraft", [])
        current_station_source = f"pi_station_{request.station_id}"
        
        # Filter out old data from this same Pi station
        filtered_aircraft = [
            aircraft for aircraft in existing_aircraft 
            if aircraft.get("data_source") != current_station_source
        ]
        
        # Add new data from this Pi station
        all_aircraft = filtered_aircraft + enriched_aircraft
        
        # Update region data with merged aircraft list
        merged_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "aircraft_count": len(all_aircraft),
            "aircraft": all_aircraft,
            "data_sources": ["pi_stations", "collectors"],
            "last_pi_update": request.timestamp.isoformat()
        }
        
        # Store merged data
        redis_service.store_region_data_generic(region, "flights", merged_data)
        
        logger.info(f"[{request_id}] Successfully processed {processed_count}/{len(request.aircraft)} "
                   f"aircraft from station {request.station_name}")
        
        return BulkAircraftResponse(
            status="success",
            message=f"Successfully processed {processed_count} aircraft from station {request.station_name}",
            aircraft_count=len(request.aircraft),
            processed_count=processed_count,
            errors=errors,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Error processing bulk aircraft data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error_code": "PROCESSING_ERROR",
                "message": f"Error processing aircraft data: {str(e)}",
                "request_id": request_id
            }
        )


@router.get("/admin/api-keys/stats")
async def get_api_key_stats() -> Dict:
    """Get API key statistics for the current collector region"""
    return api_key_service.get_api_key_stats()


@router.get("/admin/region")
async def get_collector_region() -> Dict:
    """Get the current collector region configuration"""
    return {
        "collector_region": api_key_service.get_collector_region(),
        "description": f"This collector accepts data for the '{api_key_service.get_collector_region()}' region",
        "api_key_format": f"{api_key_service.get_collector_region()}.{{random_string}}",
        "bulk_endpoint": "/api/v1/aircraft/bulk"
    }


# AWS Cost Monitoring Endpoints

@router.get("/costs/current")
async def get_current_costs() -> Dict:
    """Get current month AWS costs with service breakdown
    
    Returns:
        Dict containing:
        - total: Total cost for current month
        - currency: Currency (USD)
        - period: Date range string
        - breakdown: Cost breakdown by AWS service
        - last_updated: Timestamp of data retrieval
    """
    if aws_cost_service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AWS Cost Service unavailable",
                "message": "AWS Cost Explorer access not configured or insufficient permissions",
                "required_permissions": [
                    "ce:GetCostAndUsage",
                    "ce:GetCostForecast"
                ]
            }
        )
    
    try:
        return aws_cost_service.get_current_month_costs()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving current costs: {str(e)}"
        )


@router.get("/costs/daily")
async def get_daily_costs(days: int = 30) -> Dict:
    """Get daily cost breakdown for the last N days
    
    Args:
        days: Number of days to retrieve (default: 30, max: 365)
    
    Returns:
        Dict containing daily cost data and trends
    """
    if aws_cost_service is None:
        raise HTTPException(
            status_code=503,
            detail="AWS Cost Service unavailable - check AWS permissions"
        )
    
    # Limit days to reasonable range
    days = min(max(days, 1), 365)
    
    try:
        return aws_cost_service.get_daily_costs(days)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving daily costs: {str(e)}"
        )


@router.get("/costs/budget")
async def get_budget_status() -> Dict:
    """Get AWS budget status and utilization
    
    Returns:
        Dict containing:
        - overall_status: healthy/warning/critical
        - budgets: List of budget details with utilization
        - budget_count: Number of configured budgets
    """
    if aws_cost_service is None:
        raise HTTPException(
            status_code=503,
            detail="AWS Cost Service unavailable - check AWS permissions"
        )
    
    try:
        return aws_cost_service.get_budget_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving budget status: {str(e)}"
        )


@router.get("/costs/forecast")
async def get_cost_forecast(days: int = 30) -> Dict:
    """Get AWS cost forecast for the next N days
    
    Args:
        days: Number of days to forecast (default: 30, max: 365)
    
    Returns:
        Dict containing cost forecast and projections
    """
    if aws_cost_service is None:
        raise HTTPException(
            status_code=503,
            detail="AWS Cost Service unavailable - check AWS permissions"
        )
    
    # Limit days to reasonable range
    days = min(max(days, 1), 365)
    
    try:
        return aws_cost_service.get_cost_forecast(days)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving cost forecast: {str(e)}"
        )


@router.get("/costs/summary")
async def get_comprehensive_cost_summary() -> Dict:
    """Get comprehensive AWS cost summary including all metrics
    
    Returns:
        Complete cost overview with:
        - Current month costs
        - Budget status
        - Cost forecast
        - Recent daily trends
        - Overall financial health status
    """
    if aws_cost_service is None:
        raise HTTPException(
            status_code=503,
            detail="AWS Cost Service unavailable - check AWS permissions"
        )
    
    try:
        return aws_cost_service.get_comprehensive_cost_summary()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving cost summary: {str(e)}"
        )