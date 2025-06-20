#!/usr/bin/env python3
"""
Real-time monitor for your Pi station data
Shows live updates of your aircraft in the collector
"""

import requests
import time
import os
from datetime import datetime

# Configuration - Update these
API_BASE = "http://api.choppertracker.com/api/v1"
STATION_ID = "my-pi-001"  # Your station ID
REFRESH_INTERVAL = 10  # Seconds between updates

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def get_station_aircraft():
    """Get aircraft from your station"""
    try:
        response = requests.get(f"{API_BASE}/etex/flights", timeout=5)
        if response.status_code == 200:
            data = response.json()
            all_aircraft = data.get('aircraft', [])
            
            # Filter for your station
            station_aircraft = [
                ac for ac in all_aircraft 
                if ac.get('station_id') == STATION_ID
            ]
            
            return station_aircraft, data.get('timestamp', 'N/A')
        return [], 'Error'
    except:
        return [], 'Connection Error'

def monitor():
    """Monitor your station's data"""
    print("Starting monitor... Press Ctrl+C to stop")
    time.sleep(2)
    
    while True:
        clear_screen()
        print("=" * 60)
        print(f"🛩️  Pi Station Monitor - {STATION_ID}")
        print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        aircraft, api_timestamp = get_station_aircraft()
        
        if aircraft:
            print(f"\n✅ {len(aircraft)} aircraft from your station:\n")
            print(f"{'Flight':<10} {'Hex':<8} {'Alt (ft)':<10} {'Speed (kt)':<10} {'Track':<6}")
            print("-" * 50)
            
            for ac in sorted(aircraft, key=lambda x: x.get('alt_baro', 0), reverse=True):
                flight = (ac.get('flight', '') or 'N/A').strip()[:9]
                hex_code = ac.get('hex', 'N/A')[:7]
                altitude = ac.get('alt_baro', 'N/A')
                speed = ac.get('gs', 'N/A')
                track = ac.get('track', 'N/A')
                
                # Format altitude and speed
                alt_str = f"{altitude:,}" if isinstance(altitude, (int, float)) else str(altitude)
                speed_str = f"{speed:.0f}" if isinstance(speed, (int, float)) else str(speed)
                track_str = f"{track:.0f}°" if isinstance(track, (int, float)) else str(track)
                
                print(f"{flight:<10} {hex_code:<8} {alt_str:<10} {speed_str:<10} {track_str:<6}")
        else:
            print("\n❌ No aircraft from your station currently in the feed")
            print("\nPossible reasons:")
            print("- No aircraft in range of your antenna")
            print("- Forwarder is not running")
            print("- Station ID mismatch")
        
        print(f"\nAPI Last Update: {api_timestamp}")
        print(f"Refreshing every {REFRESH_INTERVAL} seconds...")
        
        try:
            time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            break

if __name__ == "__main__":
    monitor()