# Flight Tracker Collector

A comprehensive Python application that collects flight data from multiple sources (Pi stations, OpenSky API, dump1090), intelligently blends the data using priority-based merging, and provides both API endpoints and a web interface for real-time aircraft tracking.

## 🚁 Live Production Deployment

**Web Interface**: http://flight-tracker-web-ui-1750266711.s3-website-us-east-1.amazonaws.com/
**API Endpoint**: https://api.choppertracker.com/api/v1
**API Documentation**: https://api.choppertracker.com/docs

## 🏗️ Architecture

- **Backend**: FastAPI application running on AWS ECS Fargate
- **Frontend**: React application served from AWS S3
- **Data Store**: AWS ElastiCache Redis cluster
- **Data Sources**: Pi Station Network + OpenSky API + dump1090 ADS-B receivers
- **Infrastructure**: AWS ECS, ALB, ECR, S3, ElastiCache

## 📊 Features

- **Real-time flight tracking** for configured regions
- **Multi-source data blending** with intelligent priority (Pi stations > dump1090 > OpenSky)
- **Aircraft database enrichment** (registration, model, operator, manufacturer)
- **Helicopter identification** using ICAO aircraft classification
- **Pi Station Network** support for distributed ADS-B receivers
- **RESTful API** with automatic Swagger documentation
- **Web dashboard** with interactive map
- **MCP Integration** for AI assistant interaction (Claude Desktop compatible)
- **Rate limiting, security & caching** for optimal performance

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/jeffstrout/flightTrackerCollector.git
cd flightTrackerCollector

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run locally (requires Redis)
python run.py --mode api --reload
```

### Docker Development

```bash
# Start with included Redis
docker-compose up -d

# View logs
docker-compose logs -f

# Access API at http://localhost:8000
```

## 🔧 Configuration

The application uses YAML configuration files:
- `config/collectors.yaml` - Production configuration
- `config/collectors-local.yaml` - Local development
- `config/collectors-dev.yaml` - Docker development

Key configuration sections:
- **Regions**: Geographic areas to track (center point + radius)
- **Collectors**: Data sources (OpenSky API, dump1090 receivers)
- **Airports**: For destination estimation
- **Redis**: Connection and caching settings

## 📡 API Endpoints

### Flight Data API
- `GET /` - Root endpoint with API information
- `GET /health` - Health check
- `GET /config.js` - Frontend configuration
- `GET /api/v1/status` - System status and connected data sources
- `GET /api/v1/regions` - Available regions
- `GET /api/v1/{region}/flights` - All flights for region (blended data)
- `GET /api/v1/{region}/flights/tabular` - Flights in CSV format
- `GET /api/v1/{region}/choppers` - Helicopters only
- `POST /api/v1/aircraft/bulk` - **Pi Station API** for ADS-B data submission
- `GET /docs` - Interactive Swagger API documentation
- `GET /redoc` - Alternative ReDoc API documentation

### MCP (Model Context Protocol) Endpoints
- `GET /mcp/info` - MCP server information and capabilities
- `GET /mcp/tools` - List available MCP tools for AI interaction
- `GET /mcp/resources` - List available MCP resources
- `POST /mcp/tool/{tool_name}` - Execute MCP tool with arguments
- `GET /mcp/resource?uri={uri}` - Read MCP resource content

## 🛠️ Development

```bash
# Run tests
python -m pytest

# Format code
python -m black .

# Lint code
python -m flake8

# Run API server with auto-reload
python run.py --mode api --reload

# Run collector only (no web interface)
python run.py --mode cli

# Run MCP server for AI assistant integration
python run.py --mode mcp
```

## 🤖 MCP Integration (AI Assistant Support)

The Flight Tracker Collector includes integrated **Model Context Protocol (MCP)** support, enabling AI assistants like Claude to interact with live flight data through structured tools.

### MCP Tools Available
- **search_flights** - Search and filter flights by region, altitude, aircraft type
- **get_aircraft_details** - Get detailed information about specific aircraft
- **track_helicopters** - Helicopter-specific tracking and analysis
- **get_region_stats** - Regional statistics and data collection metrics
- **get_system_status** - System health and performance monitoring
- **check_data_sources** - Monitor data collection sources (Pi stations, OpenSky, dump1090)
- **get_aircraft_by_distance** - Find aircraft near specific coordinates

### MCP Usage Modes

**Integrated Mode** (Default - API endpoints available):
```bash
python run.py --mode api
# Access MCP via HTTP at /mcp/* endpoints
```

**Standalone MCP Server** (For Claude Desktop):
```bash
python run.py --mode mcp
# Runs stdio MCP server for external clients
```

### Claude Desktop Configuration
Add to your Claude Desktop MCP settings:
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

For detailed MCP documentation, see [MCP_INTEGRATION.md](MCP_INTEGRATION.md).

## 🚢 Deployment

See detailed deployment guides:
- [AWS Deployment](DEPLOYMENT.md) - Complete AWS infrastructure setup
- [GitHub Actions](GITHUB_SECRETS.md) - Automated CI/CD configuration
- [Troubleshooting](AWS_DEPLOYMENT_FIX.md) - Common deployment issues

## 📈 Performance

The application includes several optimizations:
- **Parallel data collection** using asyncio.gather()
- **Redis pipelining** for batch operations
- **Smart caching** with appropriate TTL values
- **Rate limit handling** with exponential backoff
- **Batch aircraft database lookups** (~90% query reduction)

## 🔍 Monitoring

- **Logs**: Rotating logs with timestamp, region, source, and performance metrics
- **Health Checks**: Built-in health endpoints for load balancer monitoring
- **API Credits**: OpenSky rate limiting and credit tracking
- **Cache Statistics**: Redis hit rates and memory usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[MIT](https://choosealicense.com/licenses/mit/)

## 🏷️ Version

**Current Version**: 1.0.0 - Production AWS Deployment
**Last Updated**: 2025-06-22
**AWS Infrastructure**: ECS Fargate + ElastiCache + S3
**Status**: ✅ Live and operational with Pi Station Network
