#!/usr/bin/env python3
"""
Simple Aircraft Forwarder - Minimal example
For Raspberry Pi with dump1090
"""

import requests
import time
from datetime import datetime

# Configuration - Update these values
API_URL = "http://api.choppertracker.com/api/v1/aircraft/bulk"
API_KEY = "etex.development123testing456"
STATION_ID = "my-pi-001"
STATION_NAME = "My Pi Station"
DUMP1090_URL = "http://localhost:8080/data/aircraft.json"

def send_aircraft():
    try:
        # Get data from dump1090
        response = requests.get(DUMP1090_URL, timeout=5)
        data = response.json()
        aircraft = data.get('aircraft', [])
        
        if not aircraft:
            print("No aircraft found")
            return
        
        # Prepare payload
        payload = {
            'station_id': STATION_ID,
            'station_name': STATION_NAME,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'aircraft': aircraft
        }
        
        # Send to API
        headers = {'X-API-Key': API_KEY}
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Sent {result['processed_count']} aircraft")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"✗ Error: {e}")

# Run every 30 seconds
if __name__ == "__main__":
    print(f"Starting forwarder for {STATION_NAME}")
    while True:
        send_aircraft()
        time.sleep(30)