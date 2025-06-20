import os
import subprocess
from datetime import datetime
from typing import Dict, Optional

def get_version_info() -> Dict[str, str]:
    """Get comprehensive version information"""
    version_info = {
        "commit": "unknown",
        "commit_full": "unknown", 
        "branch": "unknown",
        "build_time": datetime.utcnow().isoformat() + "Z",
        "clean": True,
        "version": "1.0.0"
    }
    
    try:
        # Try environment variables first (Docker build-time injection)
        if os.getenv('BUILD_COMMIT'):
            version_info["commit"] = os.getenv('BUILD_COMMIT', 'unknown')[:7]
            version_info["commit_full"] = os.getenv('BUILD_COMMIT', 'unknown')
            version_info["branch"] = os.getenv('BUILD_BRANCH', 'unknown')
            version_info["build_time"] = os.getenv('BUILD_TIME', version_info["build_time"])
            version_info["clean"] = os.getenv('BUILD_CLEAN', 'true').lower() == 'true'
        else:
            # Fallback to git commands (development)
            commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
            version_info["commit"] = commit_hash[:7]
            version_info["commit_full"] = commit_hash
            
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
            version_info["branch"] = branch
            
            # Check if working directory is clean
            status = subprocess.check_output(['git', 'status', '--porcelain']).decode().strip()
            version_info["clean"] = len(status) == 0
            
    except Exception as e:
        print(f"Warning: Could not get git version info: {e}")
    
    return version_info

# Get version info once at module load
VERSION_INFO = get_version_info()