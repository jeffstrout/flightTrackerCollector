#!/usr/bin/env python3
"""
Check if your Pi station data is reaching the collector
"""

import requests
import json
from datetime import datetime

# Configuration - Update these to match your station
API_BASE = "http://api.choppertracker.com/api/v1"
STATION_ID = "my-pi-001"  # Update this to your station ID
REGION = "etex"

print("🔍 Checking Pi Station Data")
print("=" * 50)

# 1. Check overall flight data for the region
print(f"\n1. Checking {REGION} region flight data...")
try:
    response = requests.get(f"{API_BASE}/etex/flights", timeout=10)
    if response.status_code == 200:
        data = response.json()
        total_aircraft = data.get('aircraft_count', 0)
        print(f"✅ Total aircraft in region: {total_aircraft}")
        
        # Look for aircraft from your Pi station
        your_aircraft = []
        for aircraft in data.get('aircraft', []):
            if aircraft.get('station_id') == STATION_ID:
                your_aircraft.append(aircraft)
        
        if your_aircraft:
            print(f"✅ Found {len(your_aircraft)} aircraft from your station!")
            print("\nYour aircraft:")
            for ac in your_aircraft[:5]:  # Show first 5
                flight = ac.get('flight', 'N/A').strip() or 'N/A'
                hex_code = ac.get('hex', 'N/A')
                alt = ac.get('alt_baro', 'N/A')
                source = ac.get('data_source', 'N/A')
                print(f"   - {flight} ({hex_code}) at {alt} ft - Source: {source}")
            
            if len(your_aircraft) > 5:
                print(f"   ... and {len(your_aircraft) - 5} more")
        else:
            print(f"❌ No aircraft found from station '{STATION_ID}'")
            print("   This could mean:")
            print("   - The forwarder just started (wait 30 seconds)")
            print("   - No aircraft are currently visible to your station")
            print("   - The station_id doesn't match")
        
        # Show data sources
        sources = set()
        for ac in data.get('aircraft', []):
            source = ac.get('data_source', 'unknown')
            sources.add(source)
        
        print(f"\nData sources in feed: {', '.join(sources)}")
        
    else:
        print(f"❌ Failed to get flight data: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# 2. Check API status
print("\n2. Checking API Status...")
try:
    response = requests.get(f"{API_BASE}/status", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ API Status: {data.get('status', 'unknown')}")
        
        # Check Redis connection
        redis_info = data.get('redis', {})
        if redis_info.get('redis_connected'):
            print("✅ Redis connected (data is being stored)")
        else:
            print("❌ Redis not connected")
            
except Exception as e:
    print(f"❌ Error checking status: {e}")

# 3. Show sample of all aircraft with station info
print("\n3. Sample of Aircraft in Feed:")
try:
    response = requests.get(f"{API_BASE}/etex/flights", timeout=10)
    if response.status_code == 200:
        data = response.json()
        aircraft = data.get('aircraft', [])
        
        # Group by data source
        by_source = {}
        for ac in aircraft:
            source = ac.get('data_source', 'unknown')
            station = ac.get('station_id', 'none')
            key = f"{source} ({station})" if 'pi_station' in source else source
            
            if key not in by_source:
                by_source[key] = 0
            by_source[key] += 1
        
        print("\nAircraft by source:")
        for source, count in sorted(by_source.items()):
            print(f"   - {source}: {count} aircraft")
            
except Exception as e:
    print(f"❌ Error: {e}")

# 4. Show time information
print("\n4. Timing Information:")
try:
    response = requests.get(f"{API_BASE}/etex/flights", timeout=10)
    if response.status_code == 200:
        data = response.json()
        
        # API timestamp
        api_time = data.get('timestamp', 'N/A')
        print(f"API last update: {api_time}")
        
        # Look for Pi update time
        pi_update = data.get('last_pi_update', 'N/A')
        if pi_update != 'N/A':
            print(f"Last Pi update: {pi_update}")
        
        # Current time
        print(f"Current UTC: {datetime.utcnow().isoformat()}Z")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 50)
print("✅ Check complete!")
print("\nIf you don't see your aircraft:")
print("1. Verify your station_id matches in the forwarder")
print("2. Check that aircraft are visible to your antenna")
print("3. Wait 30-60 seconds for the next update cycle")
print("4. Check the forwarder logs for errors")