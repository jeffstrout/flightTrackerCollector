#!/usr/bin/env python3
"""
Test Connection Script
Verify your Pi can connect to the API
"""

import requests
import json
from datetime import datetime

# Configuration
API_BASE = "http://api.choppertracker.com/api/v1"
API_KEY = "etex.development123testing456"

print("🧪 Testing Flight Tracker API Connection")
print("=" * 50)

# Test 1: Check API Status
print("\n1. Testing API Status...")
try:
    response = requests.get(f"{API_BASE}/status", timeout=5)
    if response.status_code == 200:
        print("✅ API is online")
        data = response.json()
        print(f"   Status: {data.get('status', 'unknown')}")
    else:
        print(f"❌ API returned status {response.status_code}")
except Exception as e:
    print(f"❌ Failed to connect: {e}")

# Test 2: Check Region Configuration
print("\n2. Testing Region Configuration...")
try:
    response = requests.get(f"{API_BASE}/admin/region", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Collector Region: {data['collector_region']}")
        print(f"   Expected Key Format: {data['api_key_format']}")
    else:
        print(f"❌ Failed to get region info: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Test Authentication
print("\n3. Testing API Key Authentication...")
test_payload = {
    "station_id": "test-pi",
    "station_name": "Connection Test",
    "timestamp": datetime.utcnow().isoformat() + 'Z',
    "aircraft": []
}

headers = {'X-API-Key': API_KEY, 'Content-Type': 'application/json'}

try:
    response = requests.post(
        f"{API_BASE}/aircraft/bulk",
        json=test_payload,
        headers=headers,
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Authentication successful!")
        print(f"   Request ID: {data.get('request_id', 'N/A')}")
    else:
        print(f"❌ Authentication failed: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Check dump1090
print("\n4. Testing dump1090 Connection...")
DUMP1090_URL = "http://localhost:8080/data/aircraft.json"
try:
    response = requests.get(DUMP1090_URL, timeout=2)
    if response.status_code == 200:
        data = response.json()
        aircraft_count = len(data.get('aircraft', []))
        print(f"✅ dump1090 is accessible")
        print(f"   Aircraft visible: {aircraft_count}")
    else:
        print(f"❌ dump1090 returned status {response.status_code}")
except Exception as e:
    print(f"❌ Cannot connect to dump1090: {e}")
    print("   Make sure dump1090 is running and accessible")

print("\n" + "=" * 50)
print("Test complete!")