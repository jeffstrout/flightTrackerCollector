from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class ApiKeyInfo(BaseModel):
    """API key information model"""
    key: str
    name: str
    description: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    permissions: List[str] = ["aircraft:write"]
    rate_limits: dict = {
        "requests_per_minute": 1000,
        "burst_allowance": 100
    }
    status: str = "active"


class ApiKeyValidationResult(BaseModel):
    """Result of API key validation"""
    is_valid: bool
    message: str
    error_code: Optional[str] = None
    key_info: Optional[ApiKeyInfo] = None


class BulkAircraftRequest(BaseModel):
    """Request model for bulk aircraft data submission"""
    station_id: str
    station_name: str
    timestamp: datetime
    aircraft: List[dict]
    metadata: Optional[dict] = None


class BulkAircraftResponse(BaseModel):
    """Response model for bulk aircraft data submission"""
    status: str
    message: str
    aircraft_count: int
    processed_count: int
    errors: List[str] = []
    request_id: str