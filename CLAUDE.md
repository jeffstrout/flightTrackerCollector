# Flight Tracker Collector - Project Overview

## Purpose
A Python application that polls multiple flight data sources, merges the data in Redis cache, and provides a web interface to view the collected data.

## Architecture

### Core Components
1. **Data Collectors**: Poll various flight tracking APIs/sources
2. **Redis Cache**: Store and merge flight data from multiple sources
3. **Web Interface**: View collected flight data
4. **API Endpoints**: 
   - JSON format endpoint for programmatic access
   - Tabular format endpoint for human-readable display

### Key Design Decisions
- No database required - Redis serves as the primary data store
- Multiple data source support with pluggable collector architecture
- Real-time data merging from different sources
- RESTful API design with multiple output formats
- **Web Framework**: FastAPI chosen over Flask for:
  - Built-in async support for concurrent API polling
  - Automatic API documentation (Swagger/OpenAPI)
  - Type hints and Pydantic validation for data consistency
  - Better performance for API-heavy applications
  - Native WebSocket support for future real-time updates

### Data Flow
1. Collectors poll flight data sources on scheduled intervals
   - OpenSky: REST API calls using bounding box (lamin/lomin/lamax/lomax)
   - dump1090: JSON endpoint polling from local ADS-B receivers
2. Raw data is normalized into a common format
3. Helicopters identified using patterns (callsigns, ICAO codes, aircraft types)
4. Flight destinations estimated using airport database and heading
5. Data is merged in Redis with conflict resolution logic
6. Web interface queries Redis and presents data via API endpoints

### Logging Strategy
- **Rotating logs** - Rotate at midnight local time per region
- **Success entries** - Include timestamp, region, source, aircraft count, API credits remaining
- **Error entries** - Include full traceback, retry attempts, response codes
- **OpenSky specific** - Log remaining API credits from X-Rate-Limit-Remaining header
- **Format**: `2024-01-15 14:30:45 - socal.opensky - INFO - Collected 47 aircraft, 385 credits remaining`

### Redis Schema
- Flight data keyed by flight number + date
- Expiration set on entries to prevent unbounded growth
- Separate keys for metadata (last update time, source info)

### Web Interface Requirements
- Simple dashboard showing active flights
- Filter/search capabilities
- Auto-refresh functionality
- Two view modes: JSON and tabular

### API Endpoints
- `GET /status` - System health, collector status, and API rate limits
- `GET /{region}/flights` - Returns all flights for a region in JSON format
- `GET /{region}/flights/tabular` - Returns flights in tabular/CSV format
- `GET /{region}/choppers` - Returns helicopters only for a region
- `GET /{region}/choppers/tabular` - Returns helicopters in tabular format
- `GET /docs` - Auto-generated API documentation (FastAPI feature)
- `GET /redoc` - Alternative API documentation interface

### Testing Strategy
- Unit tests for collectors and data transformations
- Integration tests with Redis
- Mock external API responses
- End-to-end tests for web interface

### Technology Stack
- **Python 3.11+** - Modern Python features and performance
- **FastAPI** - Async web framework with automatic docs
- **Redis** - In-memory data store for caching flight data
- **Pydantic** - Data validation and settings management
- **httpx** - Async HTTP client for API calls
- **redis-py** - Redis client with async support

### Configuration Format (YAML)
The application uses YAML configuration files to define regions, collectors, and airports.

#### Example Configuration Structure:
```yaml
# config/collectors.yaml

# Global settings
global:
  redis:
    host: ${REDIS_HOST:-localhost}
    port: ${REDIS_PORT:-6379}
    db: ${REDIS_DB:-0}
  
  polling:
    default_interval: 30  # seconds
    retry_attempts: 3
    timeout: 10

# Region definitions with center point and radius
regions:
  socal:
    enabled: true
    name: "Southern California"
    center:
      lat: 34.0522  # Los Angeles
      lon: -118.2437
    radius_miles: 150
    collectors:
      - type: "opensky"
        enabled: true
        url: "https://opensky-network.org/api"
        anonymous: true
        
      - type: "dump1090"
        enabled: true
        url: "http://192.168.1.100:8080/data/aircraft.json"
        name: "Local ADS-B Receiver"
  
  norcal:
    enabled: true
    name: "Northern California"
    center:
      lat: 37.7749  # San Francisco
      lon: -122.4194
    radius_miles: 100
    collectors:
      - type: "dump1090"
        enabled: true
        url: "http://10.0.0.50:8080/data/aircraft.json"
        name: "Bay Area Receiver"

# Airport definitions for destination estimation
airports:
  LAX:
    name: "Los Angeles International"
    lat: 33.9425
    lon: -118.4081
    
  SFO:
    name: "San Francisco International"
    lat: 37.6213
    lon: -122.3790
    
  SAN:
    name: "San Diego International"
    lat: 32.7338
    lon: -117.1933
    
  LAS:
    name: "Las Vegas McCarran"
    lat: 36.0840
    lon: -115.1537
    
  PHX:
    name: "Phoenix Sky Harbor"
    lat: 33.4352
    lon: -112.0101

# Collector type definitions
collector_types:
  opensky:
    class: "OpenSkyCollector"
    rate_limit: 100  # requests per minute
    data_format: "json"
    
  dump1090:
    class: "Dump1090Collector"
    rate_limit: 600  # 10 requests per second for local
    data_format: "json"
    local: true  # No rate limiting for local receivers
```

#### Key Configuration Features:
1. **Region-based collection** - Each region has a center point and radius
2. **Multiple collector support** - OpenSky API and dump1090 receivers
3. **Airport database** - For destination estimation based on heading/position
4. **Environment variables** - For sensitive data like API keys
5. **Flexible collector URLs** - Support both local and remote data sources

### Commands
- `python -m pytest` - Run tests
- `python -m black .` - Format code
- `python -m flake8` - Lint code
- `uvicorn src.main:app --reload` - Run development server
- `uvicorn src.main:app --host 0.0.0.0 --port 8000` - Run production server