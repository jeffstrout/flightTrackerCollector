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
                           dump1090_aircraft: List[Aircraft], 
                           opensky_aircraft: List[Aircraft]) -> List[Aircraft]:
        """Blend aircraft data with dump1090 priority"""
        blended = {}
        stats = {
            'dump1090_priority': 0,
            'opensky_only': 0,
            'blended': 0,
            'total': 0
        }
        
        # First pass: Add dump1090 aircraft (highest priority)
        for aircraft in dump1090_aircraft:
            hex_code = aircraft.hex.upper()
            if hex_code and self._is_quality_aircraft_data(aircraft):
                aircraft.data_source = "dump1090"
                blended[hex_code] = aircraft
                stats['dump1090_priority'] += 1
        
        # Second pass: Add OpenSky aircraft
        for aircraft in opensky_aircraft:
            hex_code = aircraft.hex.upper()
            if not hex_code:
                continue
            
            if hex_code in blended:
                # Aircraft already exists from dump1090
                # Merge useful missing information
                existing = blended[hex_code]
                if not existing.flight and aircraft.flight:
                    existing.flight = aircraft.flight
                    existing.data_source = "blended"
                    stats['blended'] += 1
            else:
                # New aircraft from OpenSky
                aircraft.data_source = "opensky"
                blended[hex_code] = aircraft
                stats['opensky_only'] += 1
        
        stats['total'] = len(blended)
        
        # Convert back to list and sort by priority
        aircraft_list = list(blended.values())
        aircraft_list.sort(key=self._get_aircraft_priority_score)
        
        # Enrich with aircraft database information
        self._enrich_aircraft_data(aircraft_list)
        
        logger.info(f"🔀 Blend Stats: {stats['dump1090_priority']} dump1090 | "
                   f"{stats['opensky_only']} opensky | {stats['blended']} blended | "
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
        if aircraft.data_source == 'dump1090':
            score += 0  # Highest priority
        elif aircraft.data_source == 'blended':
            score += 100
        else:  # opensky
            score += 200
        
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