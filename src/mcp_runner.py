#!/usr/bin/env python3
"""
Standalone MCP Server Runner for Flight Tracker Collector

This script runs the MCP server as a standalone process that can be used
with Claude Desktop or other MCP clients.

Usage:
    python -m src.mcp_runner
    python src/mcp_runner.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_config
from src.services.redis_service import RedisService
from src.services.collector_service import CollectorService
from src.mcp.server import MCPServer
from src.utils.logging_config import setup_logging


async def main():
    """Run standalone MCP server"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Flight Tracker MCP Server")
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize services
        redis_service = RedisService()
        
        # Optional: Initialize collector service for enhanced functionality
        # Note: In standalone mode, we rely on existing data in Redis
        # from a separately running collector service
        collector_service = None
        
        # Test Redis connection
        if not redis_service.test_connection():
            logger.error("Failed to connect to Redis. MCP server will have limited functionality.")
            logger.error("Make sure Redis is running and accessible.")
        
        # Initialize MCP server
        mcp_server = MCPServer(redis_service, collector_service)
        
        logger.info("MCP server initialized successfully")
        logger.info("Server info: %s", mcp_server.get_server_info())
        
        # Run the MCP server with stdio transport
        await mcp_server.run_stdio()
        
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error("Error running MCP server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    # Set environment variables if needed
    if "CONFIG_FILE" not in os.environ:
        os.environ["CONFIG_FILE"] = "collectors-local.yaml"
    
    asyncio.run(main())