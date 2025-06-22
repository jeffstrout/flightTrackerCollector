import logging
from typing import List, Dict, Optional
from datetime import datetime

from ..models.aircraft import Aircraft
from .aircraft_db import AircraftDatabase

logger = logging.getLogger(__name__)


class DataBlender:
    """Blends aircraft data from multiple sources with intelligent prioritization"""
    
    def __init__(self, helicopter_patterns: List[dict], redis_service=None):
        self.helicopter_patterns = helicopter_patterns
        self.aircraft_db = AircraftDatabase(redis_service)
    
    def blend_aircraft_data(self, 
                           pi_station_aircraft: List[Aircraft],
                           dump1090_aircraft: List[Aircraft], 
                           opensky_aircraft: List[Aircraft]) -> List[Aircraft]:
        """Blend aircraft data with Pi station priority - Pi stations > dump1090 > OpenSky"""
        blended = {}
        stats = {
            'pi_station_priority': 0,
            'dump1090_priority': 0,
            'opensky_only': 0,
            'pi_station_updated': 0,
            'dump1090_updated': 0,
            'total': 0
        }
        
        # First pass: Add OpenSky aircraft as base data (lowest priority)
        for aircraft in opensky_aircraft:
            hex_code = aircraft.hex.upper()
            if hex_code:
                aircraft.data_source = "opensky"
                blended[hex_code] = aircraft
                stats['opensky_only'] += 1
        
        # Second pass: dump1090 aircraft override OpenSky data (medium priority)
        for aircraft in dump1090_aircraft:
            hex_code = aircraft.hex.upper()
            if hex_code and self._is_quality_aircraft_data(aircraft):
                if hex_code in blended:
                    # Update existing OpenSky record with dump1090 data
                    aircraft.data_source = "dump1090"
                    blended[hex_code] = aircraft
                    stats['dump1090_updated'] += 1
                    stats['opensky_only'] -= 1  # No longer OpenSky-only
                else:
                    # New aircraft from dump1090
                    aircraft.data_source = "dump1090"
                    blended[hex_code] = aircraft
                
                stats['dump1090_priority'] += 1
        
        # Third pass: Pi station aircraft override all other data (highest priority)
        for aircraft in pi_station_aircraft:
            hex_code = aircraft.hex.upper()
            if hex_code and self._is_quality_aircraft_data(aircraft):
                if hex_code in blended:
                    # Update existing record with Pi station data
                    # Keep original Pi station data_source (e.g., "pi_station_ETEX01")
                    blended[hex_code] = aircraft
                    stats['pi_station_updated'] += 1
                    # Adjust previous counts
                    if aircraft.data_source.startswith('pi_station'):
                        if 'dump1090_priority' in stats and stats['dump1090_priority'] > 0:
                            stats['dump1090_priority'] -= 1
                        elif 'opensky_only' in stats and stats['opensky_only'] > 0:
                            stats['opensky_only'] -= 1
                else:
                    # New aircraft from Pi station
                    blended[hex_code] = aircraft
                
                stats['pi_station_priority'] += 1
        
        stats['total'] = len(blended)
        
        # Convert back to list and sort by priority
        aircraft_list = list(blended.values())
        aircraft_list.sort(key=self._get_aircraft_priority_score)
        
        # Enrich with aircraft database information
        self._enrich_aircraft_data(aircraft_list)
        
        logger.info(f"🔀 Blend Stats: {stats['pi_station_priority']} pi_stations | "
                   f"{stats['dump1090_priority']} dump1090 | {stats['opensky_only']} opensky | "
                   f"{stats['pi_station_updated']} pi_updated | {stats['dump1090_updated']} dump_updated | "
                   f"{stats['total']} total")
        
        return aircraft_list
    
    def identify_helicopters(self, aircraft_list: List[Aircraft]) -> List[Aircraft]:
        """Identify helicopters based on patterns"""
        helicopters = []
        total_checked = 0
        icao_class_helicopters = 0
        pattern_helicopters = 0
        
        for aircraft in aircraft_list:
            total_checked += 1
            is_helo = self._is_helicopter(aircraft)
            if is_helo:
                helicopters.append(aircraft)
                # Check which method identified it
                if aircraft.icao_aircraft_class and aircraft.icao_aircraft_class.startswith('H'):
                    icao_class_helicopters += 1
                else:
                    pattern_helicopters += 1
        
        logger.info(f"🚁 Helicopter identification: {len(helicopters)}/{total_checked} aircraft | "
                   f"ICAO class: {icao_class_helicopters} | Pattern: {pattern_helicopters}")
        
        return helicopters
    
    def _is_helicopter(self, aircraft: Aircraft) -> bool:
        """Check if aircraft is a helicopter using ICAO aircraft class only"""
        # ONLY check ICAO aircraft class - most reliable method
        if aircraft.icao_aircraft_class and aircraft.icao_aircraft_class.startswith('H'):
            logger.debug(f"✅ Helicopter identified by ICAO class: {aircraft.hex} - {aircraft.icao_aircraft_class}")
            return True
        
        # Log for debugging when no helicopter detected
        if aircraft.icao_aircraft_class:
            logger.debug(f"❌ Not helicopter (ICAO class: {aircraft.icao_aircraft_class}): {aircraft.hex}")
        else:
            logger.debug(f"⚠️  No ICAO class for aircraft: {aircraft.hex}")
        
        return False
    
    def _is_quality_aircraft_data(self, aircraft: Aircraft) -> bool:
        """Check if aircraft has high-quality position and movement data"""
        return (
            aircraft.lat is not None and 
            aircraft.lon is not None and
            aircraft.alt_baro is not None and
            aircraft.gs is not None and
            aircraft.track is not None
        )
    
    def _get_aircraft_priority_score(self, aircraft: Aircraft) -> float:
        """Calculate priority score for sorting (lower = higher priority)"""
        score = 0
        
        # Data source priority
        if aircraft.data_source.startswith('pi_station'):
            score += 0  # Highest priority - Pi stations (local ADS-B)
        elif aircraft.data_source == 'dump1090':
            score += 50  # Medium priority - Local dump1090 collectors
        else:  # opensky
            score += 100  # Lowest priority - Global network
        
        # Distance penalty (closer = higher priority)
        if aircraft.distance_miles is not None:
            score += aircraft.distance_miles * 10
        else:
            score += 10000  # No position = lowest priority
        
        return score
    
    def _enrich_aircraft_data(self, aircraft_list: List[Aircraft]):
        """Enrich aircraft with database information using batch lookups"""
        # Batch lookup all hex codes at once
        hex_codes = [aircraft.hex for aircraft in aircraft_list if aircraft.hex]
        if not hex_codes:
            return
            
        # Get all aircraft info in one batch operation
        aircraft_info_batch = self.aircraft_db.batch_lookup_aircraft(hex_codes)
        
        # Apply enrichment to each aircraft
        for aircraft in aircraft_list:
            if not aircraft.hex:
                continue
                
            info = aircraft_info_batch.get(aircraft.hex, {})
            
            # Add database fields to aircraft
            aircraft.registration = info.get('registration', '')
            aircraft.manufacturer = info.get('manufacturerName', '') 
            aircraft.model = info.get('model', '')
            aircraft.typecode = info.get('typecode', '')
            aircraft.operator = info.get('operator', '')
            aircraft.owner = info.get('owner', '')
            aircraft.icao_aircraft_class = info.get('icaoAircraftClass', '')
            
            # Also populate the aircraft_type field for compatibility
            if info.get('model'):
                aircraft.aircraft_type = f"{info.get('manufacturerName', '')} {info.get('model', '')}".strip()
            else:
                aircraft.aircraft_type = info.get('icaoAircraftClass', '')