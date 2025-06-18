# Flight Tracker Collector

A comprehensive Python application that collects flight data from multiple sources (OpenSky API, dump1090), merges the data in Redis cache, and provides both API endpoints and a web interface for viewing live aircraft tracking data.

## 🚁 Live Production Deployment

**Web Interface**: http://flight-tracker-web-ui-1750266711.s3-website-us-east-1.amazonaws.com/
**API Endpoint**: http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1
**API Documentation**: http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/docs

## 🏗️ Architecture

- **Backend**: FastAPI application running on AWS ECS Fargate
- **Frontend**: React application served from AWS S3
- **Data Store**: AWS ElastiCache Redis cluster
- **Data Sources**: OpenSky Network API + dump1090 ADS-B receivers
- **Infrastructure**: AWS ECS, ALB, ECR, S3, ElastiCache

## 📊 Features

- **Real-time flight tracking** for configured regions
- **Multi-source data blending** (dump1090 priority over OpenSky)
- **Aircraft database enrichment** (registration, model, operator)
- **Helicopter identification** using ICAO aircraft classification
- **RESTful API** with automatic documentation
- **Web dashboard** with interactive map
- **Rate limiting & caching** for optimal performance

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

- `GET /` - Root endpoint with API information
- `GET /health` - Health check
- `GET /config.js` - Frontend configuration
- `GET /api/v1/status` - System status and health
- `GET /api/v1/regions` - Available regions
- `GET /api/v1/{region}/flights` - All flights for region (JSON)
- `GET /api/v1/{region}/flights/tabular` - Flights in CSV format
- `GET /api/v1/{region}/choppers` - Helicopters only
- `GET /docs` - Interactive API documentation

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
```

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
**Last Updated**: 2025-06-18
**AWS Infrastructure**: ECS Fargate + ElastiCache + S3
**Status**: ✅ Live and operational
