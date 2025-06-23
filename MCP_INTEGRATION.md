# MCP Integration for Flight Tracker Collector

## Overview

The Flight Tracker Collector now includes integrated **Model Context Protocol (MCP)** functionality, allowing AI assistants like Claude to interact with live flight tracking data through structured tools and resources.

## Features

### MCP Tools
- **search_flights** - Search for flights in regions with filtering options
- **get_aircraft_details** - Get detailed information about specific aircraft
- **track_helicopters** - Helicopter-specific tracking and analysis
- **get_region_stats** - Regional statistics and summaries
- **get_system_status** - System health and performance metrics
- **check_data_sources** - Data collection source status
- **get_aircraft_by_distance** - Find aircraft near specific coordinates

### MCP Resources
- **Live flight data** - Real-time flight information by region
- **Helicopter data** - Helicopter-specific data streams
- **System status** - Health and performance metrics
- **Configuration** - Regional and collector settings
- **Statistics** - Collection performance data
- **Aircraft database schema** - Data structure documentation

### MCP Prompts
- **flight_analysis** - Analyze current flight activity in a region
- **system_health** - Check system health and data collection status
- **aircraft_profile** - Get detailed aircraft information

## Usage Modes

### 1. Integrated with FastAPI (Recommended)
When running the main application, MCP server is automatically initialized:

```bash
python run.py --mode api
```

Access MCP endpoints:
- `GET /mcp/info` - Server information
- `GET /mcp/tools` - List available tools
- `GET /mcp/resources` - List available resources
- `POST /mcp/tool/{tool_name}` - Execute a tool
- `GET /mcp/resource?uri={uri}` - Read a resource

### 2. Standalone MCP Server
Run MCP server as a separate process for external clients:

```bash
python run.py --mode mcp
```

This runs the MCP server with stdio transport, suitable for Claude Desktop integration.

### 3. Direct Module Access
```bash
python -m src.mcp_runner
python src/mcp_runner.py
```

## Configuration

MCP settings are configured in the YAML config files:

```yaml
global:
  mcp:
    enabled: true
    server_name: "flight-tracker-mcp"
    server_version: "1.0.0"
    transport: "stdio"  # stdio or websocket
    websocket:
      host: "localhost"
      port: 8001
    features:
      tools: true
      resources: true
      prompts: true
```

Environment variables:
- `MCP_ENABLED` - Enable/disable MCP functionality
- `MCP_HOST` - WebSocket host (if using WebSocket transport)
- `MCP_PORT` - WebSocket port (if using WebSocket transport)

## Claude Desktop Integration

To use with Claude Desktop, add to your MCP configuration:

```json
{
  "mcpServers": {
    "flight-tracker": {
      "command": "python",
      "args": ["/path/to/flightTrackerCollector/run.py", "--mode", "mcp"],
      "env": {
        "CONFIG_FILE": "collectors-local.yaml"
      }
    }
  }
}
```

## Example Tool Usage

### Search for flights in East Texas
```json
{
  "tool": "search_flights",
  "arguments": {
    "region": "etex",
    "aircraft_type": "helicopters",
    "max_altitude": 5000
  }
}
```

### Get aircraft details
```json
{
  "tool": "get_aircraft_details", 
  "arguments": {
    "hex_code": "a12345"
  }
}
```

### Find aircraft near coordinates
```json
{
  "tool": "get_aircraft_by_distance",
  "arguments": {
    "region": "etex",
    "latitude": 32.3513,
    "longitude": -95.3011,
    "max_distance": 25,
    "limit": 10
  }
}
```

## Example Resource Access

### Read live flight data
```
URI: flights://etex/live
Returns: JSON with current flight data for East Texas region
```

### Read helicopter data
```
URI: flights://etex/helicopters
Returns: JSON with current helicopter data and analysis
```

### Read system status
```
URI: system://status
Returns: JSON with system health and performance metrics
```

## Benefits

1. **AI-Friendly Interface** - Structured tools for natural language queries
2. **Real-time Data Access** - Direct access to live flight tracking data
3. **No Additional Infrastructure** - Uses existing Redis and collector services
4. **Flexible Deployment** - Can run integrated or standalone
5. **Rich Functionality** - Comprehensive tools for flight analysis and monitoring

## Dependencies

The MCP integration requires:
- `mcp>=1.0.0` (added to requirements.txt)
- Existing Redis connection
- Flight tracker collector services

## Architecture

The MCP server:
- Shares Redis connections with the main application
- Accesses the same data as the web API
- Uses existing data models and services
- Maintains consistent data format and structure
- Supports both stdio and WebSocket transports (stdio implemented)

## Development

When developing MCP functionality:

1. **Test with development config**:
   ```bash
   CONFIG_FILE=collectors-dev.yaml python run.py --mode mcp
   ```

2. **Test individual tools**:
   ```bash
   curl -X POST http://localhost:8000/mcp/tool/search_flights \
        -H "Content-Type: application/json" \
        -d '{"region": "etex"}'
   ```

3. **Check server info**:
   ```bash
   curl http://localhost:8000/mcp/info
   ```

The MCP integration is designed to enhance the flight tracker's capabilities while maintaining compatibility with existing functionality.