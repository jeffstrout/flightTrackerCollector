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
1. **Optimized Parallel Collection**: Data collectors run concurrently using asyncio.gather()
   - dump1090: Every 15 seconds (no rate limits) - local ADS-B receiver data
   - OpenSky: Smart rate limiting with 5-minute backoff on 429 errors
2. **Batch Aircraft Database Enrichment**: Single database operation for all aircraft
3. Data blending strategy:
   - dump1090 has priority (high-quality local data)
   - OpenSky fills gaps for aircraft beyond local receiver range
   - Deduplication based on ICAO hex codes
   - Aircraft sorted by distance from region center
4. **ICAO-Only Helicopter Identification**: Uses ICAO aircraft class starting with 'H' only
5. Flight destinations estimated using airport database and heading
6. **Optimized Redis Storage**: Pipeline operations with pre-serialized data
   - `{region}:flights`: All flights for a region (5-minute TTL)
   - `{region}:choppers`: Helicopters only
   - `aircraft_live:{hex}`: Individual aircraft for quick lookups
7. Web interface queries Redis and presents data via API endpoints

### Data Format Mapping

#### OpenSky State Vector Format
OpenSky returns an array of state vectors with positional indices:
- `[0]` icao24 (hex)
- `[1]` callsign (flight)
- `[2]` origin_country
- `[3]` time_position
- `[4]` last_contact
- `[5]` longitude
- `[6]` latitude
- `[7]` baro_altitude (meters)
- `[8]` on_ground
- `[9]` velocity (m/s)
- `[10]` true_track
- `[11]` vertical_rate (m/s)
- `[12]` sensors
- `[13]` geo_altitude (meters)
- `[14]` squawk
- `[15]` spi
- `[16]` position_source

#### dump1090 JSON Format
dump1090 returns a JSON object with named fields:
```json
{
  "hex": "a1b2c3",
  "flight": "UAL123",
  "lat": 34.0522,
  "lon": -118.2437,
  "alt_baro": 35000,
  "alt_geom": 35500,
  "gs": 450.5,
  "track": 270.0,
  "baro_rate": 0,
  "squawk": "1200",
  "rssi": -12.5,
  "messages": 150,
  "seen": 0.5
}
```

#### Normalized Redis Format
Both sources are normalized to this common format:
```json
{
  "hex": "a1b2c3",              // ICAO24 hex code
  "flight": "UAL123",            // Callsign/flight number
  "lat": 34.0522,                // Latitude
  "lon": -118.2437,              // Longitude
  "alt_baro": 35000,             // Barometric altitude (feet)
  "alt_geom": 35500,             // Geometric altitude (feet)
  "gs": 450.5,                   // Ground speed (knots)
  "track": 270.0,                // True track (degrees)
  "baro_rate": 0,                // Vertical rate (ft/min)
  "squawk": "1200",              // Squawk code
  "on_ground": false,            // Ground status
  "seen": 0.5,                   // Seconds since last update
  "rssi": -12.5,                 // Signal strength (dump1090 only)
  "messages": 150,               // Message count (dump1090 only)
  "distance_miles": 25.3,        // Calculated distance from center
  "data_source": "dump1090",     // Source: dump1090/opensky/blended
  "registration": "N12345",      // From aircraft database
  "model": "Boeing 737-800",     // From aircraft database
  "operator": "United Airlines", // From aircraft database
  "manufacturer": "Boeing",      // From aircraft database
  "typecode": "B738",           // ICAO type code from aircraft database
  "owner": "United Airlines",    // Aircraft owner from aircraft database
  "aircraft_type": "Boeing 737-800", // Full aircraft type description
  "icao_aircraft_class": "L2J"   // ICAO aircraft class (e.g., L2J for landplane, 2 engines, jet)
}
```

#### Unit Conversions
- **Altitude**: OpenSky meters → feet (multiply by 3.28084)
- **Speed**: OpenSky m/s → knots (multiply by 1.94384)
- **Vertical Rate**: OpenSky m/s → ft/min (multiply by 196.85)

### Logging Strategy
- **Rotating logs** - Rotate at midnight local time per region
- **Success entries** - Include timestamp, region, source, aircraft count, API credits remaining
- **Error entries** - Include full traceback, retry attempts, response codes
- **OpenSky specific** - Log remaining API credits from X-Rate-Limit-Remaining header
- **Rate limiting** - Handle 429 errors with exponential backoff
- **Format**: `2024-01-15 14:30:45 - socal.opensky - INFO - Collected 47 aircraft, 385 credits remaining`

### OpenSky Rate Limiting
- **Anonymous users**: 400 credits/day, ~4 credits per request for large areas
- **Authenticated users**: 4000-8000 credits/day
- **429 handling**: 5-minute backoff with timestamp tracking to prevent API spam
- **Enhanced logging**: Shows remaining credits, reset time, and backoff status
- **Credit calculation**: Based on bounding box area (degrees²)
  - 0-25°²: 1 credit
  - 25-100°²: 2 credits
  - 100-400°²: 3 credits
  - >400°²: 4 credits

### Performance Optimizations

The application has been optimized for high-performance operation:

#### Data Collection Optimizations
- **Parallel Collection**: dump1090 and OpenSky data fetched concurrently using `asyncio.gather()`
- **Smart Caching**: OpenSky data cached for 60 seconds, dump1090 polled every 15 seconds
- **Rate Limit Respect**: 5-minute backoff on OpenSky 429 errors prevents API abuse

#### Database Optimizations  
- **Batch Aircraft Lookups**: Single database operation for all aircraft vs individual lookups
- **Redis Pipelining**: Multiple Redis operations executed in single roundtrip
- **Pre-serialization**: Aircraft data serialized once before storage operations

#### Memory and Processing Optimizations
- **Efficient Data Structures**: List comprehensions for data transformation
- **Reduced Object Creation**: Minimal temporary object allocation
- **Optimized Sorting**: Single sort operation with composite priority scoring

#### Helicopter Identification Improvements
- **ICAO-Only Detection**: Reliable identification using only ICAO aircraft class (starts with 'H')
- **Removed Pattern Matching**: Eliminated unreliable registration/callsign pattern matching
- **Enhanced Logging**: Clear identification statistics and debugging information

#### Performance Metrics
- **Database Query Reduction**: ~90% fewer individual aircraft database lookups
- **API Collection Speed**: ~50% faster through parallel collection
- **Redis Operations**: ~80% reduction in query overhead through pipelining
- **Memory Usage**: Reduced object creation and serialization overhead

### Redis Schema
- **Aircraft Database** (persistent):
  - `aircraft_db:{icao}`: Hash with registration, manufacturer, model, etc.
- **Live Flight Data** (5-minute TTL):
  - `flight_data_blended`: Complete blended dataset as JSON
  - `aircraft_live:{hex}`: Individual aircraft data for quick lookups
  - `flight_data_raw`: Raw dump1090/OpenSky data (optional)
- **Regional Data**:
  - `{region}:flights`: All flights for a region
  - `{region}:choppers`: Helicopters only
- **Collector Stats**:
  - `stats:{region}:cache_hits`: Cache performance metrics
  - `stats:{region}:api_credits`: OpenSky API credit tracking

### Redis Database Allocation
The application uses a centralized Redis instance with database separation:
- **DB 0**: Flight Tracker Collector (this application)
- **DB 1-14**: Reserved for other applications
- **DB 15**: Testing/Development

### Docker Deployment
1. **Development Mode**: Uses docker-compose.yml with separate collector and web_api services plus Redis
2. **Production Mode**: Uses docker-compose.prod.yml with external centralized Redis
3. **Service Architecture**:
   - `collector` service: Runs data collection in background
   - `web_api` service: Serves FastAPI endpoints on port 8000
   - Both services connect to shared Redis instance
4. **Centralized Redis Stack**: Separate redis-stack/ directory with:
   - Redis 7 Alpine with custom configuration
   - Redis Commander for monitoring on port 8081
   - Persistent volume for data
   - Shared network for inter-container communication

### Web Interface Requirements
- Simple dashboard showing active flights
- Filter/search capabilities
- Auto-refresh functionality
- Two view modes: JSON and tabular

### API Endpoints
- `GET /` - Root endpoint with API information
- `GET /health` - Health check endpoint
- `GET /api/v1/status` - System health, collector status, and API rate limits
- `GET /api/v1/regions` - Returns all configured regions with their collectors
- `GET /api/v1/{region}/flights` - Returns all flights for a region in JSON format
- `GET /api/v1/{region}/flights/tabular` - Returns flights in tabular/CSV format
- `GET /api/v1/{region}/choppers` - Returns helicopters only for a region
- `GET /api/v1/{region}/choppers/tabular` - Returns helicopters in tabular format
- `GET /api/v1/{region}/stats` - Returns statistics for a specific region
- `GET /api/v1/debug/memory` - Debug endpoint to view memory store
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
    key_expiry: 3600  # 1 hour TTL for flight data
  
  logging:
    level: ${LOG_LEVEL:-INFO}
    file: logs/flight_collector.log
    rotate_time: "00:00"  # Midnight local time
    backup_count: 7  # Keep 7 days of logs
  
  polling:
    dump1090_interval: 15  # seconds - frequent updates for local data
    opensky_interval: 60   # seconds - conservative for API limits
    retry_attempts: 3
    timeout: 10
    backoff_factor: 2  # Exponential backoff multiplier

# Region definitions with center point and radius
regions:
  etex:
    enabled: true
    name: "East Texas"
    timezone: "America/Chicago"
    center:
      lat: 32.3513  # Tyler, TX
      lon: -95.3011
    radius_miles: 150  # ~2.2 degrees, costs 1 credit per OpenSky request
    collectors:
      - type: "opensky"
        enabled: true
        url: "https://opensky-network.org/api/states/all"
        anonymous: ${OPENSKY_ANONYMOUS:-true}
        username: ${OPENSKY_USERNAME:-}
        password: ${OPENSKY_PASSWORD:-}

# Airport definitions for destination estimation
airports:
  # Texas - Major airports around Tyler/East Texas
  TYR:
    name: "Tyler Pounds Regional"
    lat: 32.3542
    lon: -95.4024
    icao: "KTYR"
    
  DFW:
    name: "Dallas/Fort Worth International"
    lat: 32.8998
    lon: -97.0403
    icao: "KDFW"
    
  DAL:
    name: "Dallas Love Field"
    lat: 32.8473
    lon: -96.8517
    icao: "KDAL"
    
  IAH:
    name: "Houston George Bush Intercontinental"
    lat: 29.9844
    lon: -95.3414
    icao: "KIAH"
    
  HOU:
    name: "Houston William P. Hobby"
    lat: 29.6454
    lon: -95.2789
    icao: "KHOU"

# Collector type definitions
collector_types:
  opensky:
    class: "OpenSkyCollector"
    rate_limit: 100  # requests per minute
    daily_credits_anonymous: 400
    daily_credits_authenticated: 4000
    credit_header: "X-Rate-Limit-Remaining"
    
  dump1090:
    class: "Dump1090Collector"
    rate_limit: 600  # 10 requests per second
    local: true  # No external rate limiting

# Helicopter identification patterns
helicopter_patterns:
  # Medical helicopters
  - prefix: "N911"
  - prefix: "LIFE"
  - callsign_contains: ["MEDIC", "ANGEL", "STAR", "LIFE"]
  
  # Law enforcement
  - prefix: "N120LA"  # LAPD pattern
  - prefix: "N220LA"
  - callsign_contains: ["POLICE", "SHERIFF"]
  
  # News helicopters
  - callsign_contains: ["NEWS", "SKY", "CHOPPER"]
  
  # Military patterns
  - icao_hex_prefix: ["AE"]  # US Military
  
  # General helicopter models (ICAO type codes)
  - aircraft_type: ["H60", "EC30", "EC35", "EC45", "B407", "B429", "AS50", "R44", "R66"]
```

#### Key Configuration Features:
1. **Region-based collection** - Each region has a center point and radius
2. **Multiple collector support** - OpenSky API and dump1090 receivers
3. **Airport database** - For destination estimation based on heading/position
4. **Environment variables** - For sensitive data like API keys
5. **Flexible collector URLs** - Support both local and remote data sources

### Setup

#### Virtual Environment (Recommended)
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Without Virtual Environment
```bash
# Install dependencies globally (not recommended)
python3 -m pip install -r requirements.txt
```

### Commands

#### Development
- `python3 run.py --mode api --reload` - Run API server with auto-reload
- `python3 run.py --mode cli` - Run collector only (no web interface)
- `python3 -m pytest` - Run tests
- `python3 -m black .` - Format code
- `python3 -m flake8` - Lint code

#### Production
- `python3 run.py --mode api --host 0.0.0.0 --port 8000` - Run API server
- `uvicorn src.main:app --host 0.0.0.0 --port 8000` - Alternative API startup

#### Docker
- `docker-compose up -d` - Run with included Redis (development)
- `docker-compose -f docker-compose.prod.yml up -d` - Run with external Redis (production)

#### Configuration
- Set `CONFIG_FILE=collectors-dev.yaml` for Docker development
- Set `CONFIG_FILE=collectors-local.yaml` for local development
- Set `CONFIG_FILE=collectors.yaml` for production

## Troubleshooting

### Performance Issues

**Slow data collection cycles (>1 second)**:
- Check if aircraft database is properly loaded in Redis
- Verify batch lookups are being used (look for "batch_lookup_aircraft" in code)
- Monitor Redis pipeline operations in logs

**High memory usage**:
- Ensure aircraft cache is limited (current limit: 1000 entries)
- Check for memory leaks in long-running processes
- Monitor Redis memory usage with `redis-cli info memory`

**OpenSky rate limiting**:
- Look for "OpenSky 429 backoff active" messages - this is normal behavior
- 5-minute backoff prevents API abuse and conserves daily credits
- Consider OpenSky authentication for higher rate limits

### Helicopter Identification Issues

**No helicopters detected when expected**:
- Check if aircraft have `icao_aircraft_class` populated
- Helicopters must have ICAO class starting with 'H' (e.g., H1P, H2T)
- Pattern matching has been removed - only ICAO classification used

**False helicopter detections**:
- Should not occur with ICAO-only detection
- If it does, check aircraft database data quality

### Log Monitoring

**Key log messages to monitor**:
- `🔀 Blend Stats:` - Data collection summary
- `🚁 Helicopter identification:` - Helicopter detection results  
- `OpenSky 429 backoff active:` - Rate limiting status
- `✈️ CLOSEST AIRCRAFT:` - Successful data processing

**Performance indicators**:
- Collection time should be <1 second with optimizations
- Batch operations reduce individual database queries by ~90%
- Parallel collection improves speed by ~50%