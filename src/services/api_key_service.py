import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from ..models.api_key import ApiKeyInfo, ApiKeyValidationResult
from ..config.loader import load_config


class ApiKeyService:
    """Service for API key validation and management"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.collector_region = os.getenv('COLLECTOR_REGION', 'etex')
        self.valid_api_keys = self._load_api_keys()
        self.logger.info(f"ApiKeyService initialized for region '{self.collector_region}' with {len(self.valid_api_keys)} keys")
    
    def _load_api_keys(self) -> Dict[str, ApiKeyInfo]:
        """Load API keys from configuration file"""
        api_keys = {}
        
        try:
            # Load configuration from S3/file
            config = load_config()
            
            # Get region configuration
            region_config = config.regions.get(self.collector_region)
            if not region_config:
                self.logger.error(f"Region '{self.collector_region}' not found in configuration")
                return api_keys
            
            # Get Pi station configuration
            pi_stations_config = getattr(region_config, 'pi_stations', None)
            if not pi_stations_config or not getattr(pi_stations_config, 'enabled', False):
                self.logger.warning(f"Pi stations not enabled for region '{self.collector_region}'")
                return api_keys
            
            # Load API keys from configuration
            api_keys_list = getattr(pi_stations_config, 'api_keys', [])
            for key_data in api_keys_list:
                try:
                    # Convert dict-like object to dict if needed
                    if hasattr(key_data, '__dict__'):
                        key_dict = key_data.__dict__
                    else:
                        key_dict = dict(key_data)
                    
                    # Parse datetime strings
                    if 'created_at' in key_dict and isinstance(key_dict['created_at'], str):
                        key_dict['created_at'] = datetime.fromisoformat(key_dict['created_at'].replace('Z', '+00:00'))
                    
                    if 'expires_at' in key_dict and isinstance(key_dict['expires_at'], str):
                        key_dict['expires_at'] = datetime.fromisoformat(key_dict['expires_at'].replace('Z', '+00:00'))
                    
                    api_key_info = ApiKeyInfo(**key_dict)
                    api_keys[api_key_info.key] = api_key_info
                    
                except Exception as e:
                    self.logger.error(f"Failed to parse API key: {e}")
                    continue
            
            self.logger.info(f"Loaded {len(api_keys)} API keys from configuration for region '{self.collector_region}'")
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}", exc_info=True)
            
            # Fallback to development key
            if self.collector_region == 'etex':
                default_key = f"{self.collector_region}.development123testing456"
                api_key_info = ApiKeyInfo(
                    key=default_key,
                    name="Fallback Development Key",
                    description="Fallback development API key - REMOVE IN PRODUCTION",
                    created_at=datetime.utcnow()
                )
                api_keys[default_key] = api_key_info
                self.logger.warning(f"Using fallback development API key: {default_key}")
                
                # Also add the production keys as fallbacks
                production_keys = [
                    "etex.abc123def456ghi789jkl012",
                    "etex.xyz789mno456pqr123stu890"
                ]
                for prod_key in production_keys:
                    prod_key_info = ApiKeyInfo(
                        key=prod_key,
                        name=f"Fallback Production Key {prod_key[:8]}...",
                        description="Fallback production API key",
                        created_at=datetime.utcnow()
                    )
                    api_keys[prod_key] = prod_key_info
                
                self.logger.warning(f"Added {len(production_keys)} fallback production keys")
        
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