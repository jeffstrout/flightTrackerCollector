import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from ..models.api_key import ApiKeyInfo, ApiKeyValidationResult


class ApiKeyService:
    """Service for API key validation and management"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.collector_region = os.getenv('COLLECTOR_REGION', 'etex')
        self.valid_api_keys = self._load_api_keys()
        self.logger.info(f"ApiKeyService initialized for region '{self.collector_region}' with {len(self.valid_api_keys)} keys")
    
    def _load_api_keys(self) -> Dict[str, ApiKeyInfo]:
        """Load API keys from environment or file"""
        api_keys = {}
        
        # Try loading from file first
        api_keys_file = os.getenv('API_KEYS_FILE', '/etc/collector/api-keys.json')
        if Path(api_keys_file).exists():
            try:
                with open(api_keys_file, 'r') as f:
                    data = json.load(f)
                    for key_data in data.get('api_keys', []):
                        api_key_info = ApiKeyInfo(**key_data)
                        api_keys[api_key_info.key] = api_key_info
                self.logger.info(f"Loaded {len(api_keys)} API keys from file: {api_keys_file}")
                return api_keys
            except Exception as e:
                self.logger.warning(f"Failed to load API keys from file {api_keys_file}: {e}")
        
        # Fallback to environment variable
        env_keys = os.getenv('VALID_API_KEYS', '')
        if env_keys:
            for key in env_keys.split(','):
                key = key.strip()
                if key:
                    # Create basic key info for environment-based keys
                    api_key_info = ApiKeyInfo(
                        key=key,
                        name=f"Environment Key {key[:8]}...",
                        description="API key loaded from environment variable",
                        created_at=datetime.utcnow()
                    )
                    api_keys[key] = api_key_info
            self.logger.info(f"Loaded {len(api_keys)} API keys from environment")
        
        # Default development key for testing
        if not api_keys and self.collector_region == 'etex':
            default_key = f"{self.collector_region}.development123testing456"
            api_key_info = ApiKeyInfo(
                key=default_key,
                name="Development Key",
                description="Default development API key - REMOVE IN PRODUCTION",
                created_at=datetime.utcnow()
            )
            api_keys[default_key] = api_key_info
            self.logger.warning(f"Using default development API key: {default_key}")
        
        return api_keys
    
    def validate_api_key(self, request_api_key: str) -> ApiKeyValidationResult:
        """Validate an API key for the current region"""
        if not request_api_key:
            return ApiKeyValidationResult(
                is_valid=False,
                message="API key is required",
                error_code="MISSING_API_KEY"
            )
        
        # Check format
        if '.' not in request_api_key:
            return ApiKeyValidationResult(
                is_valid=False,
                message="Invalid API key format - must be 'region.key'",
                error_code="INVALID_FORMAT"
            )
        
        # Extract region from API key
        key_region, key_value = request_api_key.split('.', 1)
        
        # Check region match
        if key_region != self.collector_region:
            return ApiKeyValidationResult(
                is_valid=False,
                message=f"Region mismatch: key is for '{key_region}', collector is for '{self.collector_region}'",
                error_code="REGION_MISMATCH"
            )
        
        # Check if key exists in valid keys list
        if request_api_key not in self.valid_api_keys:
            return ApiKeyValidationResult(
                is_valid=False,
                message="API key not found or invalid",
                error_code="UNAUTHORIZED"
            )
        
        # Get key info and check status/expiration
        key_info = self.valid_api_keys[request_api_key]
        
        if key_info.status != "active":
            return ApiKeyValidationResult(
                is_valid=False,
                message=f"API key is not active (status: {key_info.status})",
                error_code="KEY_INACTIVE"
            )
        
        if key_info.expires_at and key_info.expires_at < datetime.utcnow():
            return ApiKeyValidationResult(
                is_valid=False,
                message="API key has expired",
                error_code="KEY_EXPIRED"
            )
        
        # Valid key
        self.logger.debug(f"Valid API key used: {request_api_key[:8]}...{request_api_key[-4:]}")
        return ApiKeyValidationResult(
            is_valid=True,
            message="Valid API key",
            key_info=key_info
        )
    
    def get_collector_region(self) -> str:
        """Get the configured collector region"""
        return self.collector_region
    
    def get_api_key_stats(self) -> Dict:
        """Get statistics about API keys"""
        active_keys = sum(1 for key in self.valid_api_keys.values() if key.status == "active")
        return {
            "collector_region": self.collector_region,
            "total_keys": len(self.valid_api_keys),
            "active_keys": active_keys,
            "inactive_keys": len(self.valid_api_keys) - active_keys
        }
    
    def mask_api_key(self, api_key: str) -> str:
        """Mask an API key for logging purposes"""
        if len(api_key) <= 12:
            return api_key[:4] + "..." + api_key[-2:]
        return api_key[:8] + "..." + api_key[-4:]