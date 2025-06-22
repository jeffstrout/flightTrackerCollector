from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Aircraft(BaseModel):
    hex: str = Field(..., description="ICAO24 hex code")
    flight: Optional[str] = Field(None, description="Callsign/flight number")
    lat: Optional[float] = Field(None, description="Latitude")
    lon: Optional[float] = Field(None, description="Longitude")
    alt_baro: Optional[int] = Field(None, description="Barometric altitude (feet)")
    alt_geom: Optional[int] = Field(None, description="Geometric altitude (feet)")
    gs: Optional[float] = Field(None, description="Ground speed (knots)")
    track: Optional[float] = Field(None, description="True track (degrees)")
    baro_rate: Optional[float] = Field(None, description="Vertical rate (ft/min)")
    squawk: Optional[str] = Field(None, description="Squawk code")
    on_ground: bool = Field(False, description="Ground status")
    seen: Optional[float] = Field(None, description="Seconds since last update")
    rssi: Optional[float] = Field(None, description="Signal strength (dump1090 only)")
    messages: Optional[int] = Field(None, description="Message count (dump1090 only)")
    distance_miles: Optional[float] = Field(None, description="Distance from center")
    data_source: Literal["dump1090", "opensky"] = Field(..., description="Data source")
    registration: Optional[str] = Field(None, description="Aircraft registration")
    model: Optional[str] = Field(None, description="Aircraft model")
    operator: Optional[str] = Field(None, description="Airline/operator")
    manufacturer_name: Optional[str] = Field(None, description="Manufacturer name")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name", alias="manufacturerName")
    typecode: Optional[str] = Field(None, description="ICAO type code")
    owner: Optional[str] = Field(None, description="Aircraft owner")
    aircraft_type: Optional[str] = Field(None, description="Full aircraft type description")
    icao_aircraft_class: Optional[str] = Field(None, description="ICAO aircraft class code (e.g., H1P, H2T)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hex": "a1b2c3",
                "flight": "UAL123",
                "lat": 34.0522,
                "lon": -118.2437,
                "alt_baro": 35000,
                "gs": 450.5,
                "track": 270.0,
                "distance_miles": 25.3,
                "data_source": "dump1090",
                "registration": "N12345",
                "model": "Boeing 737-800",
                "operator": "United Airlines"
            }
        }


class AircraftResponse(BaseModel):
    timestamp: datetime
    aircraft_count: int
    aircraft: list[Aircraft]
    location: dict
    region: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2024-01-15T12:00:00",
                "aircraft_count": 42,
                "aircraft": [],
                "location": {
                    "name": "Southern California",
                    "lat": 34.0522,
                    "lon": -118.2437
                },
                "region": "socal"
            }
        }