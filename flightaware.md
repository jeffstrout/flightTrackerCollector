# FlightAware AeroAPI Integration for Helicopter Tracking

## Overview

This document outlines the research and planning for integrating FlightAware's AeroAPI as an additional data source for nationwide helicopter tracking in the Flight Tracker Collector system.

## FlightAware AeroAPI Capabilities (2024)

### Helicopter Support
- **Launch**: FlightAware added helicopter tracking in October 2023 with "Global for Helicopters" service
- **Technology**: Uses ADS-B transponders and Aireon's space-based receivers for 1090 MHz transponders
- **Coverage**: Nationwide and global coverage through terrestrial and space-based ADS-B networks
- **Features**: Supports custom/temporary landing sites using coordinates

### API Structure
- **Type**: RESTful API with JSON responses
- **Authentication**: API key via `x-apikey` header
- **Base URL**: `https://aeroapi.flightaware.com/aeroapi`
- **Documentation**: Available at FlightAware AeroAPI Developer Portal

## Key API Endpoints for Helicopter Tracking

### Primary Search Endpoint
```
GET /flights/search/advanced
```

**Parameters for Nationwide Helicopter Search**:
```json
{
    "latlong": "24.396308 -125.0 49.384358 -66.93457",  // Continental US bounds
    "type": "H*",                                        // Helicopter type filter (needs verification)
    "max_pages": 1,
    "unique_flights": true
}
```

### Alternative Search Endpoint
```
GET /flights/search
```
- Simplified query syntax compared to advanced search
- Uses query string format

## Data Format Mapping

### FlightAware Response Format
```json
{
    "ident": "N911MD",
    "aircraft_type": "EC35",
    "lat": 32.7767,
    "lon": -96.7970,
    "altitude": 1200,
    "groundspeed": 120,
    "track": 270,
    "registration": "N911MD",
    "origin": "KDFW",
    "destination": "KIAH"
}
```

### Mapping to Flight Tracker Format
```json
{
    "hex": "",                          // Need to derive from registration
    "flight": "N911MD",                 // From ident
    "lat": 32.7767,                     // Direct mapping
    "lon": -96.7970,                    // Direct mapping
    "alt_baro": 1200,                   // From altitude
    "gs": 120,                          // From groundspeed
    "track": 270,                       // Direct mapping
    "registration": "N911MD",           // Direct mapping
    "aircraft_type": "EC35",            // Direct mapping
    "data_source": "flightaware",       // Source identifier
    "distance_miles": 0,                // Calculate from region center
    "icao_aircraft_class": ""           // May need lookup
}
```

## Pricing Structure (2024)

### API Pricing Tiers
- **Free Tier**: 500 API calls/month (personal use only)
- **Basic Commercial**: $100/month for 10,000 API calls
- **Higher Tier**: $1,000/month for 100,000 API calls

### Cost Analysis for Nationwide Polling

**Polling Every Minute**:
- **Daily calls**: 1,440 calls/day
- **Monthly calls**: ~43,200 calls/month
- **Required tier**: $1,000/month plan (100,000 calls)
- **Annual cost**: $12,000/year

**Alternative Polling Frequencies**:
- **Every 5 minutes**: ~8,640 calls/month = $100/month plan = $1,200/year
- **Every 10 minutes**: ~4,320 calls/month = $100/month plan = $1,200/year
- **Every 15 minutes**: ~2,880 calls/month = $100/month plan = $1,200/year

## Implementation Strategy

### Collector Class Design
```python
# src/collectors/flightaware.py
class FlightAwareCollector:
    def __init__(self, config, region_config):
        self.api_key = config.get('api_key')
        self.base_url = "https://aeroapi.flightaware.com/aeroapi"
        self.headers = {"x-apikey": self.api_key}
        self.session = None
        
    async def fetch_helicopters_nationwide(self):
        """Fetch all helicopters from continental US"""
        params = {
            "latlong": "24.396308 -125.0 49.384358 -66.93457",  # CONUS bounds
            "unique_flights": True,
            "max_pages": 1
        }
        
        # Helicopter filtering strategies:
        # Option 1: API-level filtering (if supported)
        # params["type"] = "H*"
        
        # Option 2: Post-request filtering by aircraft type
        response = await self._make_request("/flights/search/advanced", params)
        all_flights = response.get('flights', [])
        helicopters = self._filter_helicopters(all_flights)
        return self._normalize_aircraft_data(helicopters)
    
    def _filter_helicopters(self, flights):
        """Filter flights to include only helicopters"""
        helicopter_types = {
            'H60', 'EC30', 'EC35', 'EC45', 'B407', 'B429', 
            'AS50', 'R44', 'R66', 'S76', 'AW139', 'MD500'
        }
        
        helicopters = []
        for flight in flights:
            aircraft_type = flight.get('aircraft_type', '').upper()
            if any(helo_type in aircraft_type for helo_type in helicopter_types):
                helicopters.append(flight)
        
        return helicopters
    
    def _normalize_aircraft_data(self, flights):
        """Convert FlightAware format to our standard format"""
        aircraft_list = []
        for flight in flights:
            aircraft = Aircraft(
                hex=self._registration_to_hex(flight.get('registration', '')),
                flight=flight.get('ident', ''),
                lat=flight.get('lat'),
                lon=flight.get('lon'),
                alt_baro=flight.get('altitude'),
                gs=flight.get('groundspeed'),
                track=flight.get('track'),
                registration=flight.get('registration', ''),
                aircraft_type=flight.get('aircraft_type', ''),
                data_source="flightaware"
            )
            aircraft_list.append(aircraft)
        
        return aircraft_list
```

### Configuration Updates
```yaml
# config/collectors.yaml - Add FlightAware collector
regions:
  nationwide:
    enabled: true
    name: "United States"
    timezone: "America/New_York"
    center:
      lat: 39.8283
      lon: -98.5795
    radius_miles: 2000
    collectors:
      - type: "flightaware"
        enabled: true
        api_key: ${FLIGHTAWARE_API_KEY}
        polling_interval: 300  # 5 minutes to stay in $100/month tier

collector_types:
  flightaware:
    class: "FlightAwareCollector"
    rate_limit: 10000  # API calls per month
    helicopter_only: true
```

## Technical Considerations

### Advantages
- **Nationwide Coverage**: Single API call covers entire continental US
- **Space-based ADS-B**: Comprehensive coverage via Aireon satellite network
- **Established API**: Mature, well-documented API with good reliability
- **Historical Data**: Access to flight data back to 2011
- **Real-time Updates**: Live flight tracking capabilities
- **Custom Landing Sites**: Support for helicopter-specific landing locations

### Challenges
- **Cost**: $12,000/year for minute-level polling, $1,200/year for 5-minute intervals
- **Helicopter Filtering**: Specific helicopter filters not clearly documented - may need post-processing
- **Rate Limits**: Need careful management to stay within API quotas
- **Data Redundancy**: Potential overlap with existing OpenSky/dump1090 data in covered regions
- **ICAO Hex Mapping**: Need to convert N-numbers to ICAO hex codes for consistency

### Integration Strategy
1. **Phase 1**: Implement FlightAware collector with 5-minute polling intervals
2. **Phase 2**: Test helicopter filtering accuracy and coverage
3. **Phase 3**: Optimize data blending to avoid duplicates with existing sources
4. **Phase 4**: Consider increasing frequency based on budget and requirements

## Next Steps

1. **Contact FlightAware Sales**: Clarify helicopter-specific filtering capabilities and negotiate pricing
2. **Prototype Development**: Create FlightAware collector class for testing
3. **Regional Testing**: Start with East Texas region to validate integration
4. **Cost-Benefit Analysis**: Compare coverage improvement vs. cost increase
5. **Helicopter Type Database**: Build comprehensive list of helicopter aircraft types for filtering

## Research Notes

- FlightAware's helicopter tracking service launched October 2023
- API documentation suggests aircraft type filtering but specific helicopter parameters need verification
- GitHub repository (flightaware/aeroapps) provides sample code for getting started
- OpenAPI specification available but detailed helicopter filtering examples not found in public documentation
- Contact with FlightAware technical team recommended for implementation details

## Budget Recommendations

**Conservative Approach**: Start with $100/month plan and 5-minute polling to evaluate:
- Data quality and helicopter detection accuracy
- Coverage improvement over existing sources
- Integration complexity and maintenance overhead

**Production Approach**: If testing shows significant value, consider upgrading to minute-level polling with $1,000/month plan for comprehensive nationwide helicopter tracking.