#!/usr/bin/env python3
"""
Flight Tracker Collector startup script
Choose between API mode or CLI mode
"""

import sys
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(description="Flight Tracker Collector")
    parser.add_argument(
        "--mode", 
        choices=["api", "cli", "mcp"], 
        default="api",
        help="Run mode: api (web server), cli (collector only), or mcp (MCP server)"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="Host to bind (API mode only)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port to bind (API mode only)"
    )
    parser.add_argument(
        "--reload", 
        action="store_true",
        help="Enable auto-reload (API mode only)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    if args.mode == "api":
        # Run FastAPI server
        import uvicorn
        uvicorn.run(
            "src.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    elif args.mode == "cli":
        # Run CLI collector
        from src.cli import main as cli_main
        cli_main()
    elif args.mode == "mcp":
        # Run MCP server
        import asyncio
        from src.mcp_runner import main as mcp_main
        asyncio.run(mcp_main())


if __name__ == "__main__":
    main()