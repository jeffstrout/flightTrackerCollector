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
API_ENDPOINT = "https://api.choppertracker.com/api/v1/aircraft/bulk"
API_KEY = "etex.abc123def456ghi789jkl012"
STATION_ID = "ETEX01"
STATION_NAME = "East Texas 01"
DUMP1090_URL = "http://localhost:8080/data/aircraft.json"

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
            if ac.get('hex'):
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
                logger.info(f"Successfully sent {data.get('processed_count', 'unknown')} aircraft. Request ID: {data.get('request_id', 'unknown')}")
                return True
            else:
                logger.error(f"API error {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send data to API: {e}")
            return False
    
    def run_once(self, dump1090_url: str) -> bool:
        """Run a single collection and send cycle"""
        aircraft = self.get_dump1090_data(dump1090_url)
        filtered_aircraft = self.filter_aircraft(aircraft)
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
    parser.add_argument('--api-endpoint', default=API_ENDPOINT, help='API endpoint URL')
    parser.add_argument('--api-key', default=API_KEY, help='API key for authentication')
    parser.add_argument('--station-id', default=STATION_ID, help='Unique station identifier')
    parser.add_argument('--station-name', default=STATION_NAME, help='Friendly station name')
    parser.add_argument('--dump1090-url', default=DUMP1090_URL, help='dump1090 JSON data URL')
    parser.add_argument('--interval', type=int, default=30, help='Send interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    forwarder = AircraftForwarder(
        api_endpoint=args.api_endpoint,
        api_key=args.api_key,
        station_id=args.station_id,
        station_name=args.station_name
    )
    
    if args.once:
        success = forwarder.run_once(args.dump1090_url)
        exit(0 if success else 1)
    else:
        forwarder.run_continuous(args.dump1090_url, args.interval)

if __name__ == '__main__':
    main()