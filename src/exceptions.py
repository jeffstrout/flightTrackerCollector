"""
Flight Tracker Exception Classes

This module defines custom exceptions for the flight tracker application
to provide better error handling and debugging capabilities.
"""

from typing import Optional, Dict, Any


class FlightTrackerError(Exception):
    """Base exception for all flight tracker errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CollectorError(FlightTrackerError):
    """Base exception for data collection errors"""
    pass


class CollectorTimeout(CollectorError):
    """Raised when a collector times out"""
    
    def __init__(self, collector_name: str, timeout: int, details: Optional[Dict[str, Any]] = None):
        message = f"Collector '{collector_name}' timed out after {timeout} seconds"
        super().__init__(message, details)
        self.collector_name = collector_name
        self.timeout = timeout


class CollectorConnectionError(CollectorError):
    """Raised when collector cannot connect to data source"""
    
    def __init__(self, collector_name: str, endpoint: str, details: Optional[Dict[str, Any]] = None):
        message = f"Collector '{collector_name}' failed to connect to {endpoint}"
        super().__init__(message, details)
        self.collector_name = collector_name
        self.endpoint = endpoint


class DataValidationError(FlightTrackerError):
    """Raised when aircraft data validation fails"""
    
    def __init__(self, field: str, value: Any, reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Validation failed for field '{field}' with value '{value}': {reason}"
        super().__init__(message, details)
        self.field = field
        self.value = value
        self.reason = reason


class ConfigurationError(FlightTrackerError):
    """Raised when configuration is invalid or missing"""
    
    def __init__(self, config_item: str, reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Configuration error for '{config_item}': {reason}"
        super().__init__(message, details)
        self.config_item = config_item
        self.reason = reason


class RedisConnectionError(FlightTrackerError):
    """Raised when Redis connection fails"""
    
    def __init__(self, operation: str, details: Optional[Dict[str, Any]] = None):
        message = f"Redis operation '{operation}' failed"
        super().__init__(message, details)
        self.operation = operation


class APIError(FlightTrackerError):
    """Raised for API-related errors"""
    
    def __init__(self, endpoint: str, status_code: Optional[int] = None, 
                 reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        message = f"API error at endpoint '{endpoint}'"
        if status_code:
            message += f" (status: {status_code})"
        if reason:
            message += f": {reason}"
        super().__init__(message, details)
        self.endpoint = endpoint
        self.status_code = status_code
        self.reason = reason


class AuthenticationError(APIError):
    """Raised when API authentication fails"""
    
    def __init__(self, endpoint: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(endpoint, 401, "Authentication failed", details)


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded"""
    
    def __init__(self, endpoint: str, retry_after: Optional[int] = None, 
                 details: Optional[Dict[str, Any]] = None):
        reason = "Rate limit exceeded"
        if retry_after:
            reason += f", retry after {retry_after} seconds"
        super().__init__(endpoint, 429, reason, details)
        self.retry_after = retry_after


class AircraftDatabaseError(FlightTrackerError):
    """Raised when aircraft database operations fail"""
    
    def __init__(self, operation: str, reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Aircraft database {operation} failed: {reason}"
        super().__init__(message, details)
        self.operation = operation
        self.reason = reason