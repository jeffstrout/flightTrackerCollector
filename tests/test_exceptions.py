"""
Tests for custom exception classes
"""

import pytest
from src.exceptions import (
    FlightTrackerError,
    CollectorError,
    CollectorTimeout,
    CollectorConnectionError,
    DataValidationError,
    ConfigurationError,
    RedisConnectionError,
    APIError,
    AuthenticationError,
    RateLimitError,
    AircraftDatabaseError,
)


class TestExceptions:
    """Test custom exception classes."""

    def test_flight_tracker_error(self):
        """Test base FlightTrackerError."""
        error = FlightTrackerError("Test error", {"key": "value"})
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_collector_timeout(self):
        """Test CollectorTimeout exception."""
        error = CollectorTimeout("test-collector", 30, {"url": "http://test.com"})
        assert "test-collector" in str(error)
        assert "30 seconds" in str(error)
        assert error.collector_name == "test-collector"
        assert error.timeout == 30
        assert error.details["url"] == "http://test.com"

    def test_collector_connection_error(self):
        """Test CollectorConnectionError exception."""
        error = CollectorConnectionError(
            "test-collector", 
            "http://test.com/api", 
            {"status": 500}
        )
        assert "test-collector" in str(error)
        assert "http://test.com/api" in str(error)
        assert error.collector_name == "test-collector"
        assert error.endpoint == "http://test.com/api"
        assert error.details["status"] == 500

    def test_data_validation_error(self):
        """Test DataValidationError exception."""
        error = DataValidationError(
            "altitude", 
            -1000, 
            "Altitude cannot be negative",
            {"aircraft_hex": "ABC123"}
        )
        assert "altitude" in str(error)
        assert "-1000" in str(error)
        assert "Altitude cannot be negative" in str(error)
        assert error.field == "altitude"
        assert error.value == -1000
        assert error.reason == "Altitude cannot be negative"

    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        error = ConfigurationError(
            "redis.host", 
            "Missing required configuration",
            {"config_file": "config.yaml"}
        )
        assert "redis.host" in str(error)
        assert "Missing required configuration" in str(error)
        assert error.config_item == "redis.host"
        assert error.reason == "Missing required configuration"

    def test_redis_connection_error(self):
        """Test RedisConnectionError exception."""
        error = RedisConnectionError("SETEX", {"key": "test:key"})
        assert "SETEX" in str(error)
        assert error.operation == "SETEX"
        assert error.details["key"] == "test:key"

    def test_api_error(self):
        """Test APIError exception."""
        # Test with all parameters
        error = APIError(
            "/api/v1/flights", 
            404, 
            "Endpoint not found",
            {"method": "GET"}
        )
        assert "/api/v1/flights" in str(error)
        assert "404" in str(error)
        assert "Endpoint not found" in str(error)
        assert error.endpoint == "/api/v1/flights"
        assert error.status_code == 404
        assert error.reason == "Endpoint not found"

        # Test with minimal parameters
        error2 = APIError("/api/v1/status")
        assert "/api/v1/status" in str(error2)
        assert error2.status_code is None
        assert error2.reason is None

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        error = AuthenticationError("/api/v1/admin", {"user": "test"})
        assert "/api/v1/admin" in str(error)
        assert "401" in str(error)
        assert "Authentication failed" in str(error)
        assert error.status_code == 401

    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        # Test with retry_after
        error = RateLimitError(
            "/api/v1/flights", 
            60, 
            {"requests_made": 100}
        )
        assert "/api/v1/flights" in str(error)
        assert "429" in str(error)
        assert "60 seconds" in str(error)
        assert error.retry_after == 60

        # Test without retry_after
        error2 = RateLimitError("/api/v1/status")
        assert "Rate limit exceeded" in str(error2)
        assert error2.retry_after is None

    def test_aircraft_database_error(self):
        """Test AircraftDatabaseError exception."""
        error = AircraftDatabaseError(
            "load", 
            "CSV file corrupted",
            {"file": "aircraft.csv", "line": 42}
        )
        assert "load" in str(error)
        assert "CSV file corrupted" in str(error)
        assert error.operation == "load"
        assert error.reason == "CSV file corrupted"
        assert error.details["line"] == 42

    def test_exception_inheritance(self):
        """Test that all exceptions inherit from FlightTrackerError."""
        exceptions = [
            CollectorError("Test"),
            CollectorTimeout("test", 30),
            CollectorConnectionError("test", "http://test"),
            DataValidationError("field", "value", "reason"),
            ConfigurationError("item", "reason"),
            RedisConnectionError("op"),
            APIError("/endpoint"),
            AuthenticationError("/endpoint"),
            RateLimitError("/endpoint"),
            AircraftDatabaseError("op", "reason"),
        ]

        for exc in exceptions:
            assert isinstance(exc, FlightTrackerError)
            assert isinstance(exc, Exception)