"""
MCP Server implementation for Flight Tracker Collector.

Provides Model Context Protocol server functionality integrated with the flight tracker,
allowing AI assistants to interact with live flight data through structured tools.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional, Sequence
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource, 
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Prompt,
    PromptArgument,
    PromptMessage
)

from ..services.redis_service import RedisService
from ..services.collector_service import CollectorService
from .tools import FlightTrackerTools
from .resources import FlightTrackerResources

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server for Flight Tracker Collector"""
    
    def __init__(self, redis_service: RedisService = None, collector_service: CollectorService = None):
        """Initialize MCP server with flight tracker services"""
        self.redis_service = redis_service or RedisService()
        self.collector_service = collector_service
        self.server = Server("flight-tracker-mcp")
        self.tools = FlightTrackerTools(self.redis_service, self.collector_service)
        self.resources = FlightTrackerResources(self.redis_service, self.collector_service)
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register MCP server handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available flight data resources"""
            return self.resources.list_resources()
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read flight data resource content"""
            return await self.resources.read_resource(uri)
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available flight tracking tools"""
            return self.tools.list_tools()
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute flight tracking tool"""
            result = await self.tools.call_tool(name, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        @self.server.list_prompts()
        async def handle_list_prompts() -> List[Prompt]:
            """List available flight tracking prompts"""
            return [
                Prompt(
                    name="flight_analysis",
                    description="Analyze current flight activity in a region",
                    arguments=[
                        PromptArgument(
                            name="region",
                            description="Region to analyze (e.g., 'etex')",
                            required=True
                        ),
                        PromptArgument(
                            name="focus",
                            description="Analysis focus: 'overview', 'helicopters', 'commercial', 'patterns'",
                            required=False
                        )
                    ]
                ),
                Prompt(
                    name="system_health",
                    description="Check system health and data collection status",
                    arguments=[]
                ),
                Prompt(
                    name="aircraft_profile",
                    description="Get detailed aircraft information and history",
                    arguments=[
                        PromptArgument(
                            name="hex_code",
                            description="Aircraft ICAO hex code (e.g., 'a12345')",
                            required=True
                        )
                    ]
                )
            ]
        
        @self.server.get_prompt()
        async def handle_get_prompt(name: str, arguments: Dict[str, str]) -> PromptMessage:
            """Handle prompt requests"""
            if name == "flight_analysis":
                region = arguments.get("region", "etex")
                focus = arguments.get("focus", "overview")
                
                # Get flight data for analysis
                flights_data = await self.tools.call_tool("search_flights", {"region": region})
                stats = await self.tools.call_tool("get_region_stats", {"region": region})
                
                prompt_text = f"""Analyze the current flight activity in the {region} region.

Focus: {focus}

Current Flight Data:
{json.dumps(flights_data, indent=2)}

Regional Statistics:
{json.dumps(stats, indent=2)}

Please provide insights on:
1. Current aircraft activity levels
2. Notable aircraft or patterns
3. Data collection health
4. Any interesting observations
"""
                
                return PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text)
                )
            
            elif name == "system_health":
                status = await self.tools.call_tool("get_system_status", {})
                sources = await self.tools.call_tool("check_data_sources", {})
                
                prompt_text = f"""Check the health of the Flight Tracker system.

System Status:
{json.dumps(status, indent=2)}

Data Sources:
{json.dumps(sources, indent=2)}

Please analyze:
1. Overall system health
2. Data collection performance
3. Any issues or alerts
4. Recommendations for optimization
"""
                
                return PromptMessage(
                    role="user", 
                    content=TextContent(type="text", text=prompt_text)
                )
            
            elif name == "aircraft_profile":
                hex_code = arguments.get("hex_code", "")
                if not hex_code:
                    raise ValueError("hex_code argument is required")
                
                aircraft_info = await self.tools.call_tool("get_aircraft_details", {"hex_code": hex_code})
                
                prompt_text = f"""Provide a detailed profile for aircraft {hex_code}.

Aircraft Information:
{json.dumps(aircraft_info, indent=2)}

Please include:
1. Aircraft identification and registration
2. Technical specifications
3. Current status and location
4. Operational context
5. Any notable characteristics
"""
                
                return PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text)
                )
            
            else:
                raise ValueError(f"Unknown prompt: {name}")
    
    async def run_stdio(self):
        """Run MCP server with stdio transport"""
        logger.info("Starting Flight Tracker MCP server with stdio transport")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="flight-tracker",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                ),
            )
    
    async def run_websocket(self, host: str = "localhost", port: int = 8001):
        """Run MCP server with WebSocket transport"""
        # Note: WebSocket transport would require additional implementation
        # For now, focusing on stdio transport which is most common
        raise NotImplementedError("WebSocket transport not yet implemented")
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get information about the MCP server"""
        return {
            "name": "flight-tracker-mcp",
            "version": "1.0.0",
            "description": "MCP server for Flight Tracker Collector",
            "capabilities": {
                "tools": len(self.tools.list_tools()),
                "resources": len(self.resources.list_resources()),
                "prompts": 3
            },
            "transport": "stdio"
        }


# Standalone server entry point for testing
async def main():
    """Run standalone MCP server for testing"""
    server = MCPServer()
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())