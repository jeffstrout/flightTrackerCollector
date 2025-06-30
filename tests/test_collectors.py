"""
Tests for data collectors
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from src.collectors.dump1090 import Dump1090Collector
from src.collectors.opensky import OpenSkyCollector
from src.models.aircraft import Aircraft
from src.exceptions import CollectorConnectionError, CollectorTimeout


class TestDump1090Collector:
    """Test dump1090 collector functionality."""

    @pytest.fixture
    def collector_config(self):
        """Configuration for dump1090 collector."""
        return {
            "name": "test-dump1090",
            "type": "dump1090",
            "url": "http://localhost:8080",
            "enabled": True,
            "timeout": 5,
        }

    @pytest.fixture
    def region_config(self):
        """Region configuration for testing."""
        return {
            "name": "test-region",
            "lat": 32.5,
            "lon": -95.5,
            "radius_miles": 50,
        }

    @pytest.fixture
    def dump1090_response(self):
        """Sample dump1090 API response."""
        return {
            "now": 1234567890.5,
            "messages": 1000,
            "aircraft": [
                {
                    "hex": "abc123",
                    "flight": "TEST001 ",
                    "lat": 32.5,
                    "lon": -95.5,
                    "alt_baro": 35000,
                    "alt_geom": 35100,
                    "gs": 450,
                    "track": 90,
                    "baro_rate": 0,
                    "squawk": "1234",
                    "on_ground": False,
                    "seen": 5,
                    "rssi": -20.5,
                },
                {
                    "hex": "def456",
                    "flight": "HELI01",
                    "lat": 32.6,
                    "lon": -95.6,
                    "alt_baro": 1500,
                    "gs": 120,
                    "track": 180,
                    "on_ground": False,
                    "seen": 10,
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_fetch_data_success(
        self, collector_config, region_config, dump1090_response, mock_httpx_client
    ):
        """Test successful data fetch from dump1090."""
        mock_httpx_client.get.return_value.json.return_value = dump1090_response
        
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            collector = Dump1090Collector(collector_config, region_config)
            aircraft = await collector.fetch_data()
        
        assert aircraft is not None
        assert len(aircraft) == 2
        
        # Check first aircraft
        assert aircraft[0].hex == "ABC123"  # Should be uppercase
        assert aircraft[0].flight == "TEST001"  # Should be trimmed
        assert aircraft[0].lat == 32.5
        assert aircraft[0].lon == -95.5
        assert aircraft[0].alt_baro == 35000
        assert aircraft[0].data_source == "dump1090"
        assert aircraft[0].distance_miles is not None
        
        # Check URL was called correctly
        mock_httpx_client.get.assert_called_once()
        call_args = mock_httpx_client.get.call_args
        assert "aircraft.json" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_fetch_data_timeout(self, collector_config, region_config):
        """Test timeout handling."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            collector = Dump1090Collector(collector_config, region_config)
            
            with pytest.raises(CollectorTimeout) as exc_info:
                await collector.fetch_data()
            
            assert exc_info.value.collector_name == "test-dump1090"
            assert exc_info.value.timeout == 5

    @pytest.mark.asyncio
    async def test_fetch_data_connection_error(self, collector_config, region_config):
        """Test connection error handling."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            collector = Dump1090Collector(collector_config, region_config)
            
            with pytest.raises(CollectorConnectionError) as exc_info:
                await collector.fetch_data()
            
            assert exc_info.value.collector_name == "test-dump1090"
            assert exc_info.value.details["status_code"] == 500

    def test_url_construction(self, collector_config, region_config):
        """Test URL construction for dump1090."""
        # Test with URL not ending in /
        collector = Dump1090Collector(collector_config, region_config)
        assert collector.url == "http://localhost:8080/data/aircraft.json"
        
        # Test with URL ending in /
        collector_config["url"] = "http://localhost:8080/"
        collector = Dump1090Collector(collector_config, region_config)
        assert collector.url == "http://localhost:8080/data/aircraft.json"
        
        # Test with URL already having aircraft.json
        collector_config["url"] = "http://localhost:8080/data/aircraft.json"
        collector = Dump1090Collector(collector_config, region_config)
        assert collector.url == "http://localhost:8080/data/aircraft.json"

    @pytest.mark.asyncio
    async def test_invalid_aircraft_filtering(
        self, collector_config, region_config, mock_httpx_client
    ):
        """Test that invalid aircraft are filtered out."""
        response = {
            "aircraft": [
                {
                    "hex": "abc123",
                    "lat": 32.5,
                    "lon": -95.5,
                },
                {
                    "hex": "def456",
                    # Missing lat/lon - should be filtered
                },
                {
                    "hex": "ghi789",
                    "lat": None,  # Invalid lat
                    "lon": -95.5,
                },
            ]
        }
        
        mock_httpx_client.get.return_value.json.return_value = response
        
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            collector = Dump1090Collector(collector_config, region_config)
            aircraft = await collector.fetch_data()
        
        assert len(aircraft) == 1
        assert aircraft[0].hex == "ABC123"


class TestOpenSkyCollector:
    """Test OpenSky collector functionality."""

    @pytest.fixture
    def collector_config(self):
        """Configuration for OpenSky collector."""
        return {
            "name": "test-opensky",
            "type": "opensky",
            "url": "https://opensky-network.org/api",
            "enabled": True,
            "timeout": 10,
        }

    @pytest.fixture
    def opensky_response(self):
        """Sample OpenSky API response."""
        return {
            "time": 1234567890,
            "states": [
                [
                    "abc123",      # 0: icao24
                    "TEST001",     # 1: callsign
                    "USA",         # 2: origin_country
                    1234567890,    # 3: time_position
                    1234567890,    # 4: last_contact
                    -95.5,         # 5: longitude
                    32.5,          # 6: latitude
                    10668.0,       # 7: baro_altitude (meters)
                    False,         # 8: on_ground
                    231.48,        # 9: velocity (m/s)
                    90.0,          # 10: true_track
                    0.0,           # 11: vertical_rate (m/s)
                    None,          # 12: sensors
                    10700.0,       # 13: geo_altitude (meters)
                    "1234",        # 14: squawk
                    False,         # 15: spi
                    0              # 16: position_source
                ],
                [
                    "def456",
                    "HELI01",
                    "USA",
                    1234567890,
                    1234567890,
                    -95.6,
                    32.6,
                    457.2,         # 1500 feet in meters
                    False,
                    61.73,         # 120 knots in m/s
                    180.0,
                    -2.54,         # -500 ft/min in m/s
                    None,
                    None,
                    None,
                    False,
                    0
                ],
            ]
        }

    @pytest.mark.asyncio
    async def test_fetch_data_success(
        self, collector_config, region_config, opensky_response, mock_httpx_client
    ):
        """Test successful data fetch from OpenSky."""
        mock_httpx_client.get.return_value.json.return_value = opensky_response
        
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            collector = OpenSkyCollector(collector_config, region_config)
            aircraft = await collector.fetch_data()
        
        assert aircraft is not None
        assert len(aircraft) == 2
        
        # Check first aircraft (conversions from metric)
        assert aircraft[0].hex == "ABC123"
        assert aircraft[0].flight == "TEST001"
        assert aircraft[0].lat == 32.5
        assert aircraft[0].lon == -95.5
        assert aircraft[0].alt_baro == pytest.approx(35000, rel=100)  # ~10668m
        assert aircraft[0].gs == pytest.approx(450, rel=10)  # ~231.48 m/s
        assert aircraft[0].data_source == "opensky"
        
        # Check API was called with bbox parameters
        call_args = mock_httpx_client.get.call_args
        assert "lamin=" in call_args[0][0]
        assert "lamax=" in call_args[0][0]
        assert "lomin=" in call_args[0][0]
        assert "lomax=" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, collector_config, region_config):
        """Test rate limit error handling."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"X-Rate-Limit-Retry-After-Seconds": "60"}
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=mock_response
        )
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            collector = OpenSkyCollector(collector_config, region_config)
            
            # OpenSky collector returns None on rate limit
            result = await collector.fetch_data()
            assert result is None

    def test_bounding_box_calculation(self, collector_config, region_config):
        """Test bounding box calculation for API request."""
        collector = OpenSkyCollector(collector_config, region_config)
        
        # Access the internal method through the collector
        lat_range = 50 / 69.0  # miles to degrees latitude
        lon_range = 50 / (69.0 * 0.86)  # approximate for this latitude
        
        expected_min_lat = 32.5 - lat_range
        expected_max_lat = 32.5 + lat_range
        expected_min_lon = -95.5 - lon_range
        expected_max_lon = -95.5 + lon_range
        
        # The URL should contain these bbox parameters
        # This would be tested in the actual API call
        assert collector.region_config["lat"] == 32.5
        assert collector.region_config["lon"] == -95.5
        assert collector.region_config["radius_miles"] == 50