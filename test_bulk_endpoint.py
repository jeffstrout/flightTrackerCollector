#!/usr/bin/env python3
"""
Test script for the bulk aircraft data endpoint
"""
import requests
import json
from datetime import datetime

# Test configuration
API_BASE_URL = "http://localhost:8000/api/v1"  # Change to production URL when testing
API_KEY = "etex.development123testing456"  # Development API key

# Sample aircraft data (similar to dump1090 format)
sample_aircraft = [
    {
        "hex": "a12345",
        "flight": "UAL123",
        "lat": 32.3513,
        "lon": -95.3011,
        "alt_baro": 35000,
        "gs": 450,
        "track": 270,
        "squawk": "1200",
        "seen": 1.2
    },
    {
        "hex": "b67890",
        "flight": "DAL456",
        "lat": 32.4000,
        "lon": -95.2500,
        "alt_baro": 28000,
        "gs": 420,
        "track": 180,
        "squawk": "2000",
        "seen": 0.8
    }
]

def test_region_info():
    """Test the region info endpoint"""
    print("🌐 Testing region info endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/admin/region")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Region: {data['collector_region']}")
            print(f"✅ API Key Format: {data['api_key_format']}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def test_api_key_stats():
    """Test the API key stats endpoint"""
    print("\n🔑 Testing API key stats endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/admin/api-keys/stats")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Region: {data['collector_region']}")
            print(f"✅ Total Keys: {data['total_keys']}")
            print(f"✅ Active Keys: {data['active_keys']}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def test_bulk_aircraft_invalid_key():
    """Test bulk endpoint with invalid API key"""
    print("\n🚫 Testing bulk endpoint with invalid API key...")
    
    payload = {
        "station_id": "test-pi-001",
        "station_name": "Test Pi Station",
        "timestamp": datetime.utcnow().isoformat(),
        "aircraft": sample_aircraft
    }
    
    headers = {
        "X-API-Key": "invalid.key123",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/aircraft/bulk", 
                               json=payload, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code in [401, 403]:
            data = response.json()
            print(f"✅ Expected error: {data['detail']['message']}")
            print(f"✅ Error code: {data['detail']['error_code']}")
        else:
            print(f"❌ Unexpected response: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def test_bulk_aircraft_valid_key():
    """Test bulk endpoint with valid API key"""
    print("\n✈️  Testing bulk endpoint with valid API key...")
    
    payload = {
        "station_id": "test-pi-001",
        "station_name": "Test Pi Station",
        "timestamp": datetime.utcnow().isoformat(),
        "aircraft": sample_aircraft,
        "metadata": {
            "pi_version": "1.0.0",
            "location": "East Texas Test Site"
        }
    }
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/aircraft/bulk", 
                               json=payload, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data['message']}")
            print(f"✅ Aircraft Count: {data['aircraft_count']}")
            print(f"✅ Processed Count: {data['processed_count']}")
            print(f"✅ Request ID: {data['request_id']}")
            if data['errors']:
                print(f"⚠️  Errors: {data['errors']}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def test_region_data():
    """Test that the region data includes our submitted aircraft"""
    print("\n📊 Testing region data retrieval...")
    try:
        response = requests.get(f"{API_BASE_URL}/etex/flights")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Total Aircraft: {data['aircraft_count']}")
            
            # Look for our test aircraft
            pi_aircraft = [a for a in data['aircraft'] if a.get('station_id') == 'test-pi-001']
            print(f"✅ Pi Station Aircraft: {len(pi_aircraft)}")
            
            if pi_aircraft:
                aircraft = pi_aircraft[0]
                print(f"✅ Sample Pi Aircraft: {aircraft.get('flight', 'N/A')} ({aircraft.get('hex', 'N/A')})")
                print(f"✅ Data Source: {aircraft.get('data_source', 'N/A')}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    print("🧪 Flight Tracker Bulk Endpoint Test")
    print("=" * 50)
    
    # Run tests
    test_region_info()
    test_api_key_stats()
    test_bulk_aircraft_invalid_key()
    test_bulk_aircraft_valid_key()
    test_region_data()
    
    print("\n✅ Tests completed!")