import logging
import pandas as pd
from typing import Dict, Optional
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class AircraftDatabase:
    """Service for looking up aircraft information by ICAO hex code"""
    
    def __init__(self, redis_service=None):
        self.redis_service = redis_service
        self.aircraft_cache = {}
        self.cache_stats = {'hits': 0, 'misses': 0}
        self.aircraft_db = None
        self.db_file = Path(__file__).parent.parent.parent / "config" / "aircraftDatabase.csv"
        
        logger.info(f"Initializing aircraft database service")
        self.setup_database()
    
    def setup_database(self):
        """Setup aircraft database - try Redis first, then fallback to CSV"""
        # Check if we have aircraft data in Redis
        if self.redis_service and self._check_redis_database():
            logger.info("Using aircraft database from Redis")
            return
        
        # Otherwise, load from CSV and optionally import to Redis
        if self._load_csv_database():
            if self.redis_service:
                logger.info("Importing aircraft database to Redis for faster lookups")
                self._import_to_redis()
    
    def _check_redis_database(self) -> bool:
        """Check if aircraft database exists in Redis"""
        try:
            # Check for aircraft keys
            aircraft_keys = self.redis_service.redis_client.keys("aircraft_db:*")
            if len(aircraft_keys) > 1000:  # Threshold for valid database
                logger.info(f"Found {len(aircraft_keys)} aircraft records in Redis")
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking Redis database: {e}")
            return False
    
    def _load_csv_database(self) -> bool:
        """Load aircraft database from CSV file"""
        try:
            if not os.path.exists(self.db_file):
                logger.error(f"Aircraft database file not found: {self.db_file}")
                return False
            
            logger.info(f"Loading aircraft database from {self.db_file}")
            
            # Parse CSV with flexible quoting
            parse_attempts = [
                {'sep': ',', 'quoting': 1, 'skipinitialspace': True, 'on_bad_lines': 'skip'},
                {'sep': ',', 'quoting': 0, 'skipinitialspace': True, 'on_bad_lines': 'skip'},
                {'sep': ',', 'quoting': 1, 'skipinitialspace': True, 'encoding': 'utf-8-sig', 'on_bad_lines': 'skip'}
            ]
            
            df = None
            for params in parse_attempts:
                try:
                    df = pd.read_csv(self.db_file, dtype=str, **params)
                    break
                except Exception:
                    continue
            
            if df is None:
                logger.error("Failed to parse aircraft database CSV")
                return False
            
            # Clean column names
            df.columns = [col.strip().strip("'").strip('"') for col in df.columns]
            
            # Find ICAO column
            icao_col = None
            for col in ['icao24', 'ICAO24', 'icao', 'ICAO', 'hex', 'HEX']:
                if col in df.columns:
                    icao_col = col
                    break
            
            if not icao_col:
                logger.error("No ICAO column found in aircraft database")
                return False
            
            # Clean and index by ICAO
            df[icao_col] = df[icao_col].astype(str).str.upper().str.strip()
            df = df[df[icao_col].notna()]
            df = df[df[icao_col] != '']
            df = df[df[icao_col] != 'NAN']
            df.set_index(icao_col, inplace=True)
            
            self.aircraft_db = df
            logger.info(f"Loaded aircraft database with {len(df)} records")
            return True
            
        except Exception as e:
            logger.error(f"Error loading aircraft database: {e}")
            return False
    
    def _import_to_redis(self):
        """Import CSV database to Redis"""
        if not self.aircraft_db is not None or not self.redis_service:
            return
        
        try:
            imported = 0
            batch_size = 1000
            pipeline = self.redis_service.redis_client.pipeline()
            
            for icao, row in self.aircraft_db.iterrows():
                # Create aircraft data
                aircraft_data = {
                    'registration': str(row.get('registration', '')).strip(),
                    'manufacturerName': str(row.get('manufacturerName', '') or 
                                          row.get('manufacturerIcao', '') or 
                                          row.get('manufacturer', '')).strip(),
                    'model': str(row.get('model', '')).strip(),
                    'icaoAircraftClass': str(row.get('icaoAircraftClass', '') or 
                                           row.get('typecode', '')).strip(),
                    'typecode': str(row.get('typecode', '')).strip(),
                    'operator': str(row.get('operator', '')).strip(),
                    'owner': str(row.get('owner', '')).strip()
                }
                
                # Add to Redis pipeline
                key = f"aircraft_db:{icao}"
                pipeline.hset(key, mapping=aircraft_data)
                imported += 1
                
                # Execute batch
                if imported % batch_size == 0:
                    pipeline.execute()
                    pipeline = self.redis_service.redis_client.pipeline()
            
            # Execute remaining
            if imported % batch_size != 0:
                pipeline.execute()
            
            logger.info(f"Imported {imported} aircraft to Redis")
            
        except Exception as e:
            logger.error(f"Aircraft database import to Redis failed: {e}")
    
    def lookup_aircraft(self, hex_code: str) -> Dict[str, str]:
        """Look up aircraft information by hex code"""
        if not hex_code:
            return self._empty_result()
        
        # Check cache first
        if hex_code in self.aircraft_cache:
            self.cache_stats['hits'] += 1
            return self.aircraft_cache[hex_code]
        
        self.cache_stats['misses'] += 1
        
        # Try Redis lookup
        if self.redis_service:
            result = self._redis_lookup(hex_code)
            if result:
                self._cache_result(hex_code, result)
                return result
        
        # Fallback to pandas
        if self.aircraft_db is not None:
            result = self._pandas_lookup(hex_code)
            self._cache_result(hex_code, result)
            return result
        
        # No data available
        result = self._empty_result()
        self._cache_result(hex_code, result)
        return result
    
    def _redis_lookup(self, hex_code: str) -> Optional[Dict[str, str]]:
        """Look up aircraft in Redis"""
        try:
            hex_upper = hex_code.upper().replace('~', '').strip()
            redis_key = f"aircraft_db:{hex_upper}"
            redis_data = self.redis_service.redis_client.hgetall(redis_key)
            
            if redis_data:
                return {
                    'registration': redis_data.get('registration', ''),
                    'manufacturerName': redis_data.get('manufacturerName', ''),
                    'model': redis_data.get('model', ''),
                    'icaoAircraftClass': redis_data.get('icaoAircraftClass', ''),
                    'typecode': redis_data.get('typecode', ''),
                    'operator': redis_data.get('operator', ''),
                    'owner': redis_data.get('owner', '')
                }
            return None
        except Exception as e:
            logger.error(f"Redis lookup error for {hex_code}: {e}")
            return None
    
    def _pandas_lookup(self, hex_code: str) -> Dict[str, str]:
        """Look up aircraft in pandas dataframe"""
        try:
            hex_upper = hex_code.upper().replace('~', '').strip()
            
            if hex_upper in self.aircraft_db.index:
                aircraft_info = self.aircraft_db.loc[hex_upper]
                
                if isinstance(aircraft_info, pd.DataFrame):
                    aircraft_info = aircraft_info.iloc[0]
                
                return {
                    'registration': self._safe_get(aircraft_info, ['registration', 'Registration', 'reg']),
                    'manufacturerName': self._safe_get(aircraft_info, ['manufacturerName', 'manufacturerIcao', 'manufacturer', 'Manufacturer', 'mfr']),
                    'model': self._safe_get(aircraft_info, ['model', 'Model', 'type']),
                    'icaoAircraftClass': self._safe_get(aircraft_info, ['icaoAircraftClass', 'typecode', 'TypeCode', 'aircraft_type']),
                    'typecode': self._safe_get(aircraft_info, ['typecode', 'TypeCode', 'type_code']),
                    'operator': self._safe_get(aircraft_info, ['operator', 'Operator', 'airline']),
                    'owner': self._safe_get(aircraft_info, ['owner', 'Owner', 'registered_owner'])
                }
        except Exception as e:
            logger.error(f"Pandas lookup error for {hex_code}: {e}")
        
        return self._empty_result()
    
    def _safe_get(self, data, possible_keys):
        """Safely get value from data using multiple possible key names"""
        for key in possible_keys:
            if key in data and pd.notna(data[key]) and str(data[key]).strip() != '':
                return str(data[key]).strip()
        return ''
    
    def _empty_result(self) -> Dict[str, str]:
        """Return empty aircraft info structure"""
        return {
            'registration': '',
            'manufacturerName': '',
            'model': '',
            'icaoAircraftClass': '',
            'typecode': '',
            'operator': '',
            'owner': ''
        }
    
    def _cache_result(self, hex_code: str, result: Dict[str, str]):
        """Cache lookup result"""
        self.aircraft_cache[hex_code] = result
        
        # Prevent cache from growing too large
        if len(self.aircraft_cache) > 1000:
            # Remove oldest entries (first 200)
            keys_to_remove = list(self.aircraft_cache.keys())[:200]
            for key in keys_to_remove:
                del self.aircraft_cache[key]
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'cache_size': len(self.aircraft_cache)
        }