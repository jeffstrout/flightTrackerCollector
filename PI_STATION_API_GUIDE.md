# Pi Station Data Push API Guide

## Overview
This guide explains how to send aircraft data from your Raspberry Pi running dump1090 to the Flight Tracker Collector API.

## API Endpoint

**URL**: `https://api.choppertracker.com/api/v1/aircraft/bulk`  
**Method**: `POST`  
**Authentication**: API Key via `X-API-Key` header

## Authentication

You need a regional API key to authenticate your Pi station. For the East Texas region:

**Development Key**: `etex.development123testing456`

> Note: In production, you'll receive a unique API key for your station.

## Request Format

### Headers
```
X-API-Key: etex.development123testing456
Content-Type: application/json
```

### Request Body Structure
```json
{
  "station_id": "unique-station-identifier",
  "station_name": "Friendly name for your station",
  "timestamp": "2025-06-20T15:30:00Z",
  "aircraft": [
    {
      "hex": "a12345",
      "flight": "UAL123",
      "lat": 32.3513,
      "lon": -95.3011,
      "alt_baro": 35000,
      "alt_geom": 35500,
      "gs": 450,
      "track": 270,
      "baro_rate": 0,
      "squawk": "1200",
      "rssi": -12.5,
      "messages": 150,
      "seen": 0.5
    }
  ],
  "metadata": {
    "pi_version": "1.0.0",
    "location": "Your station location"
  }
}
```

### Aircraft Data Fields

The API accepts aircraft data in dump1090 JSON format:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| hex | string | ICAO24 hex code | Yes |
| flight | string | Callsign/flight number | No |
| lat | float | Latitude | No |
| lon | float | Longitude | No |
| alt_baro | integer | Barometric altitude (feet) | No |
| alt_geom | integer | Geometric altitude (feet) | No |
| gs | float | Ground speed (knots) | No |
| track | float | True track (degrees) | No |
| baro_rate | integer | Vertical rate (ft/min) | No |
| squawk | string | Squawk code | No |
| rssi | float | Signal strength | No |
| messages | integer | Message count | No |
| seen | float | Seconds since last update | No |

## Response Format

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Successfully processed 15 aircraft from station Your Station Name",
  "aircraft_count": 15,
  "processed_count": 15,
  "errors": [],
  "request_id": "abc12345"
}
```

### Error Responses

**401 Unauthorized** - Invalid or missing API key
```json
{
  "detail": {
    "status": "error",
    "error_code": "UNAUTHORIZED",
    "message": "API key not found or invalid",
    "request_id": "xyz78901"
  }
}
```

**403 Forbidden** - Region mismatch
```json
{
  "detail": {
    "status": "error",
    "error_code": "REGION_MISMATCH",
    "message": "Region mismatch: key is for 'pacific', collector is for 'etex'",
    "details": {
      "collector_region": "etex",
      "provided_key_region": "pacific"
    },
    "request_id": "def45678"
  }
}
```

## Sample Python Script for Raspberry Pi

Save this as `aircraft_forwarder.py` on your Raspberry Pi:

```python
#!/usr/bin/env python3
"""
Aircraft Data Forwarder for Raspberry Pi with dump1090
Forwards aircraft data from dump1090 to Flight Tracker Collector API
"""

import json
import time
import requests
import logging
from datetime import datetime
from typing import List, Dict
import argparse
import os

# Configuration
API_ENDPOINT = "http://api.choppertracker.com/api/v1/aircraft/bulk"
API_KEY = "etex.development123testing456"  # Replace with your API key
STATION_ID = "pi-station-001"  # Unique identifier for your Pi
STATION_NAME = "East Texas Pi Station"  # Friendly name
DUMP1090_URL = "http://localhost:8080/data/aircraft.json"  # dump1090 JSON endpoint

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AircraftForwarder:
    def __init__(self, api_endpoint: str, api_key: str, station_id: str, station_name: str):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.station_id = station_id
        self.station_name = station_name
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        })
        
    def get_dump1090_data(self, url: str) -> List[Dict]:
        """Fetch aircraft data from dump1090"""
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # dump1090 returns data in {"now": timestamp, "aircraft": [...]} format
            aircraft = data.get('aircraft', [])
            logger.info(f"Retrieved {len(aircraft)} aircraft from dump1090")
            return aircraft
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch dump1090 data: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from dump1090: {e}")
            return []
    
    def filter_aircraft(self, aircraft: List[Dict]) -> List[Dict]:
        """Filter aircraft data to remove incomplete entries"""
        filtered = []
        
        for ac in aircraft:
            # Only include aircraft with a hex code (minimum requirement)
            if ac.get('hex'):
                # Clean up the data
                cleaned = {
                    'hex': ac.get('hex'),
                    'flight': ac.get('flight', '').strip() if ac.get('flight') else None,
                    'lat': ac.get('lat'),
                    'lon': ac.get('lon'),
                    'alt_baro': ac.get('alt_baro'),
                    'alt_geom': ac.get('alt_geom'),
                    'gs': ac.get('gs'),
                    'track': ac.get('track'),
                    'baro_rate': ac.get('baro_rate'),
                    'squawk': ac.get('squawk'),
                    'rssi': ac.get('rssi'),
                    'messages': ac.get('messages'),
                    'seen': ac.get('seen')
                }
                
                # Remove None values to reduce payload size
                cleaned = {k: v for k, v in cleaned.items() if v is not None}
                filtered.append(cleaned)
        
        logger.debug(f"Filtered {len(aircraft)} aircraft to {len(filtered)}")
        return filtered
    
    def send_aircraft_data(self, aircraft: List[Dict]) -> bool:
        """Send aircraft data to the API"""
        if not aircraft:
            logger.debug("No aircraft to send")
            return True
        
        payload = {
            'station_id': self.station_id,
            'station_name': self.station_name,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'aircraft': aircraft,
            'metadata': {
                'pi_version': '1.0.0',
                'dump1090_version': 'unknown',
                'location': 'East Texas'
            }
        }
        
        try:
            response = self.session.post(
                self.api_endpoint,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Successfully sent {data['processed_count']}/{data['aircraft_count']} aircraft. "
                    f"Request ID: {data['request_id']}"
                )
                return True
            else:
                logger.error(
                    f"API error {response.status_code}: {response.text}"
                )
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send data to API: {e}")
            return False
    
    def run_once(self, dump1090_url: str) -> bool:
        """Run a single collection and send cycle"""
        # Get aircraft from dump1090
        aircraft = self.get_dump1090_data(dump1090_url)
        
        # Filter and clean the data
        filtered_aircraft = self.filter_aircraft(aircraft)
        
        # Send to API
        return self.send_aircraft_data(filtered_aircraft)
    
    def run_continuous(self, dump1090_url: str, interval: int = 30):
        """Run continuous collection and sending"""
        logger.info(f"Starting continuous forwarding every {interval} seconds")
        logger.info(f"Station: {self.station_name} ({self.station_id})")
        logger.info(f"API Endpoint: {self.api_endpoint}")
        
        while True:
            try:
                success = self.run_once(dump1090_url)
                if not success:
                    logger.warning("Failed to send data, will retry next cycle")
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(
        description='Forward aircraft data from dump1090 to Flight Tracker API'
    )
    parser.add_argument(
        '--api-endpoint',
        default=API_ENDPOINT,
        help='API endpoint URL'
    )
    parser.add_argument(
        '--api-key',
        default=API_KEY,
        help='API key for authentication'
    )
    parser.add_argument(
        '--station-id',
        default=STATION_ID,
        help='Unique station identifier'
    )
    parser.add_argument(
        '--station-name',
        default=STATION_NAME,
        help='Friendly station name'
    )
    parser.add_argument(
        '--dump1090-url',
        default=DUMP1090_URL,
        help='dump1090 JSON data URL'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Send interval in seconds (default: 30)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit'
    )
    
    args = parser.parse_args()
    
    # Create forwarder instance
    forwarder = AircraftForwarder(
        api_endpoint=args.api_endpoint,
        api_key=args.api_key,
        station_id=args.station_id,
        station_name=args.station_name
    )
    
    # Run once or continuous
    if args.once:
        success = forwarder.run_once(args.dump1090_url)
        exit(0 if success else 1)
    else:
        forwarder.run_continuous(args.dump1090_url, args.interval)

if __name__ == '__main__':
    main()
```

## Installation and Usage

### 1. Install Requirements
```bash
# On your Raspberry Pi
sudo apt-get update
sudo apt-get install python3-pip
pip3 install requests
```

### 2. Save the Script
```bash
# Create directory for the forwarder
mkdir -p ~/aircraft-forwarder
cd ~/aircraft-forwarder

# Save the script as aircraft_forwarder.py
nano aircraft_forwarder.py
# Paste the script content and save
```

### 3. Test the Script
```bash
# Run once to test
python3 aircraft_forwarder.py --once

# Check the output for successful sending
```

### 4. Run Continuously
```bash
# Run with default 30-second interval
python3 aircraft_forwarder.py

# Or specify a custom interval (e.g., 60 seconds)
python3 aircraft_forwarder.py --interval 60
```

### 5. Run as a Service (Optional)

Create a systemd service to run automatically:

```bash
# Create service file
sudo nano /etc/systemd/system/aircraft-forwarder.service
```

Add this content:
```ini
[Unit]
Description=Aircraft Data Forwarder
After=network.target dump1090-fa.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/aircraft-forwarder
ExecStart=/usr/bin/python3 /home/pi/aircraft-forwarder/aircraft_forwarder.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl enable aircraft-forwarder.service
sudo systemctl start aircraft-forwarder.service

# Check status
sudo systemctl status aircraft-forwarder.service

# View logs
sudo journalctl -u aircraft-forwarder.service -f
```

## Configuration Options

### Environment Variables
You can use environment variables instead of command-line arguments:

```bash
export API_KEY="etex.your-unique-key"
export STATION_ID="your-pi-station"
export STATION_NAME="Your Station Name"
```

### Configuration File (Optional)
Create `config.json`:
```json
{
  "api_endpoint": "http://api.choppertracker.com/api/v1/aircraft/bulk",
  "api_key": "etex.development123testing456",
  "station_id": "pi-station-001",
  "station_name": "East Texas Pi Station",
  "dump1090_url": "http://localhost:8080/data/aircraft.json",
  "interval": 30
}
```

## Troubleshooting

### Common Issues

1. **Connection Refused to dump1090**
   - Ensure dump1090 is running: `sudo systemctl status dump1090-fa`
   - Check the URL: Default is usually `http://localhost:8080/data/aircraft.json`

2. **API Authentication Errors**
   - Verify your API key is correct
   - Ensure the key matches the region (etex.* for East Texas)

3. **No Aircraft Data**
   - Check if dump1090 is receiving data: Visit `http://localhost:8080` in a browser
   - Verify antenna connection

### Debug Mode
Run with debug logging:
```bash
python3 aircraft_forwarder.py --once 2>&1 | tee debug.log
```

## Data Flow & Processing

1. **dump1090** receives ADS-B data from aircraft
2. **aircraft_forwarder.py** polls dump1090's JSON endpoint every 15 seconds
3. Script filters and cleans the aircraft data
4. Data is sent to the Flight Tracker API via `POST /api/v1/aircraft/bulk`
5. API validates the regional API key and stores Pi station data in Redis
6. **Collector Service** retrieves Pi station data during its collection cycle
7. **Data Blending**: Pi station data gets **highest priority** in the blending process:
   - **Pi Stations** (highest priority) - Your local ADS-B data
   - **dump1090** (medium priority) - Other local collectors
   - **OpenSky** (lowest priority) - Global network data
8. **Aircraft Database Enrichment**: All aircraft get enriched with:
   - Registration numbers (e.g., N12345)
   - Aircraft models (e.g., Boeing 737-800)
   - Operators (e.g., United Airlines)
   - Manufacturers and ICAO classifications
9. **Helicopter Identification**: Automatic detection using ICAO aircraft classes
10. Final blended and enriched data appears in the web interface

## Data Priority & Quality

Your Pi station data has the **highest priority** in the system, meaning:
- When your Pi station sees an aircraft, it overrides OpenSky data for that aircraft
- Your local high-quality ADS-B data provides the most accurate position and speed information
- Multiple Pi stations can contribute data for better regional coverage
- All data sources are automatically enriched with aircraft registration and model information

## Support

For issues or questions:
- Check the API status: `GET https://api.choppertracker.com/api/v1/status`
- View API documentation: `https://api.choppertracker.com/docs`
- View your station's region: `GET http://api.choppertracker.com/api/v1/admin/region`
- Monitor logs: `sudo journalctl -u aircraft-forwarder.service -f`