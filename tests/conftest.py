"""
Pytest configuration and fixtures for Flight Tracker tests
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
import httpx
from fastapi.testclient import TestClient

from src.main import app
from src.config.loader import Config
from src.models.aircraft import Aircraft
from src.services.redis_service import RedisService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return Config(
        regions={
            "test": {
                "name": "test",
                "lat": 32.5,
                "lon": -95.5,
                "radius_miles": 50,
                "collectors": [
                    {
                        "name": "test-dump1090",
                        "type": "dump1090",
                        "url": "http://test-dump1090:8080",
                        "enabled": True,
                    },
                    {
                        "name": "test-opensky",
                        "type": "opensky",
                        "url": "https://opensky-network.org/api",
                        "enabled": True,
                    }
                ]
            }
        },
        app={
            "name": "Flight Tracker Test",
            "version": "1.0.0",
            "debug": False,
            "cors_origins": ["http://localhost:3000"],
        },
        redis={
            "host": "localhost",
            "port": 6379,
            "db": 1,  # Use different DB for testing
            "password": None,
        }
    )


@pytest.fixture
def mock_redis_service():
    """Mock Redis service for testing."""
    mock = Mock(spec=RedisService)
    mock.is_connected = True
    mock.get_aircraft = AsyncMock(return_value=[])
    mock.store_aircraft = AsyncMock()
    mock.get_data = AsyncMock(return_value=None)
    mock.store_data = AsyncMock()
    mock.get_stats = AsyncMock(return_value={})
    return mock


@pytest.fixture
def sample_aircraft():
    """Sample aircraft data for testing."""
    return [
        Aircraft(
            hex="ABC123",
            flight="TEST001",
            lat=32.5,
            lon=-95.5,
            alt_baro=35000,
            gs=450,
            track=90,
            on_ground=False,
            seen=5,
            rssi=-20.5,
            data_source="dump1090",
            icao_aircraft_class="L2J",
            registration="N12345",
            model="Boeing 737-800",
            operator="Test Airlines",
        ),
        Aircraft(
            hex="DEF456",
            flight="HELI01",
            lat=32.6,
            lon=-95.6,
            alt_baro=1500,
            gs=120,
            track=180,
            on_ground=False,
            seen=10,
            data_source="dump1090",
            icao_aircraft_class="H1T",
            model="Bell 206",
            operator="Test Helicopters",
        ),
        Aircraft(
            hex="GHI789",
            flight="CARGO99",
            lat=32.4,
            lon=-95.4,
            alt_baro=0,
            gs=0,
            track=0,
            on_ground=True,
            seen=2,
            data_source="opensky",
        ),
    ]


@pytest.fixture
async def mock_httpx_client():
    """Mock httpx client for testing external API calls."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={
        "aircraft": [
            {
                "hex": "ABC123",
                "flight": "TEST001",
                "lat": 32.5,
                "lon": -95.5,
                "alt_baro": 35000,
                "gs": 450,
                "track": 90,
                "on_ground": False,
                "seen": 5,
            }
        ]
    })
    
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    return mock_client


@pytest.fixture
def mock_aircraft_db():
    """Mock aircraft database for testing."""
    return {
        "ABC123": {
            "registration": "N12345",
            "model": "Boeing 737-800",
            "operator": "Test Airlines",
            "manufacturer": "Boeing",
            "typecode": "B738",
            "aircraft_type": "Boeing 737-800",
            "icao_aircraft_class": "L2J",
        },
        "DEF456": {
            "registration": "N67890",
            "model": "Bell 206",
            "operator": "Test Helicopters",
            "manufacturer": "Bell",
            "typecode": "B206",
            "aircraft_type": "Bell 206 JetRanger",
            "icao_aircraft_class": "H1T",
        }
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Reset any singleton instances here
    yield
    # Cleanup after test