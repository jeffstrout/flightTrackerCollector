import os
import re
import yaml
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


def _expand_env_vars(text: str) -> str:
    """Expand environment variables including ${VAR:-default} syntax"""
    # Handle ${VAR:-default} syntax
    def replace_var(match):
        var_expr = match.group(1)
        if ':-' in var_expr:
            var_name, default_value = var_expr.split(':-', 1)
            return os.getenv(var_name, default_value)
        else:
            return os.getenv(var_expr, '')
    
    # Replace ${VAR:-default} and ${VAR}
    text = re.sub(r'\$\{([^}]+)\}', replace_var, text)
    
    # Handle simple $VAR syntax
    text = os.path.expandvars(text)
    
    return text


class GlobalConfig(BaseModel):
    redis: Dict[str, Any] = Field(default_factory=dict)
    logging: Dict[str, Any] = Field(default_factory=dict)
    polling: Dict[str, Any] = Field(default_factory=dict)


class CollectorConfig(BaseModel):
    type: str
    enabled: bool = True
    url: str
    name: Optional[str] = None
    anonymous: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None


class RegionConfig(BaseModel):
    enabled: bool = True
    name: str
    timezone: str
    center: Dict[str, float]  # lat, lon
    radius_miles: float
    collectors: List[CollectorConfig]


class AirportConfig(BaseModel):
    name: str
    lat: float
    lon: float
    icao: str


class CollectorTypeConfig(BaseModel):
    class_name: str = Field(alias="class")
    rate_limit: int
    daily_credits_anonymous: Optional[int] = None
    daily_credits_authenticated: Optional[int] = None
    credit_header: Optional[str] = None
    local: bool = False


class HelicopterPattern(BaseModel):
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    callsign_contains: Optional[List[str]] = None
    aircraft_type: Optional[List[str]] = None
    icao_hex_prefix: Optional[List[str]] = None


class Config(BaseModel):
    global_config: GlobalConfig = Field(alias="global")
    regions: Dict[str, RegionConfig]
    airports: Dict[str, AirportConfig]
    collector_types: Dict[str, CollectorTypeConfig]
    helicopter_patterns: List[HelicopterPattern] = Field(default_factory=list)


def load_config(config_file: Optional[str] = None) -> Config:
    """Load configuration from YAML file"""
    if config_file is None:
        config_file = os.getenv("CONFIG_FILE", "collectors.yaml")
    
    # Look for config file in config/ directory or current directory
    config_paths = [
        f"config/{config_file}",
        config_file,
        f"/app/config/{config_file}"  # Docker path
    ]
    
    config_path = None
    for path in config_paths:
        if os.path.exists(path):
            config_path = path
            break
    
    if not config_path:
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    logger.info(f"Loading configuration from {config_path}")
    
    with open(config_path, 'r') as f:
        # Expand environment variables in YAML
        yaml_content = f.read()
        yaml_content = _expand_env_vars(yaml_content)
        config_data = yaml.safe_load(yaml_content)
    
    return Config(**config_data)


def get_redis_config() -> Dict[str, Any]:
    """Get Redis connection configuration with environment variable defaults"""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": int(os.getenv("REDIS_DB", "0")),
        "decode_responses": True
    }