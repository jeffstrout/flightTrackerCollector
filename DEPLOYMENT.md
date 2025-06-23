# AWS Production Deployment Guide

🌐 **Live Production URLs:**
- **Web Interface**: http://flight-tracker-web-ui-1750266711.s3-website-us-east-1.amazonaws.com/
- **API Endpoint**: https://api.choppertracker.com/api/v1
- **API Documentation**: https://api.choppertracker.com/docs

## 🏗️ AWS Infrastructure

The Flight Tracker Collector is deployed on AWS using:

- **ECS Fargate**: Containerized backend services
- **Application Load Balancer**: Public API access
- **ElastiCache Redis**: High-performance data caching
- **ECR**: Container image registry
- **S3**: Frontend hosting and file storage
- **CloudWatch**: Logging and monitoring

### Infrastructure Components

| Service | Resource | Purpose |
|---------|----------|----------|
| **ECS Cluster** | `flight-tracker-cluster` | Container orchestration |
| **ECS Service** | `flight-tracker-backend` | Backend API and data collector |
| **Load Balancer** | `flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com` | Public API access |
| **Redis Cluster** | `flight-tracker-redis.x7nm8u.0001.use1.cache.amazonaws.com` | Data caching |
| **ECR Repository** | `958933162000.dkr.ecr.us-east-1.amazonaws.com/flight-tracker-backend` | Container images |
| **S3 Bucket** | `flight-tracker-web-ui-1750266711` | Frontend hosting |

## 🚀 Deployment Process

### Option 1: Automated GitHub Actions

1. **Configure GitHub Secrets** (see [GITHUB_SECRETS.md](GITHUB_SECRETS.md))
2. **Push to main branch** - triggers automatic deployment
3. **Monitor deployment** in GitHub Actions tab

### Option 2: Manual Deployment

#### Backend Deployment

```bash
# 1. Build and tag Docker image
docker build -t flight-tracker-backend .
docker tag flight-tracker-backend 958933162000.dkr.ecr.us-east-1.amazonaws.com/flight-tracker-backend:latest

# 2. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 958933162000.dkr.ecr.us-east-1.amazonaws.com
docker push 958933162000.dkr.ecr.us-east-1.amazonaws.com/flight-tracker-backend:latest

# 3. Update ECS service
aws ecs update-service --cluster flight-tracker-cluster --service flight-tracker-backend --force-new-deployment
```

#### Frontend Deployment

```bash
# Upload frontend files to S3
aws s3 sync frontend-dist/ s3://flight-tracker-web-ui-1750266711/ --delete

# Update configuration
aws s3 cp config.js s3://flight-tracker-web-ui-1750266711/config.js --content-type="application/javascript"
```

### Configuration Management

The application uses environment-specific configuration:

```yaml
# config/collectors.yaml (Production)
global:
  redis:
    host: flight-tracker-redis.x7nm8u.0001.use1.cache.amazonaws.com
    port: 6379
    db: 0
  logging:
    level: INFO

regions:
  etex:
    enabled: true
    name: "East Texas"
    center:
      lat: 32.3513
      lon: -95.3011
    radius_miles: 150
    collectors:
      - type: "opensky"
        enabled: true
        url: "https://opensky-network.org/api/states/all"
      - type: "dump1090"
        enabled: true
        url: "http://192.168.0.13/tar1090/data/aircraft.json"
```

## 🔍 Monitoring & Verification

### Health Checks

```bash
# Backend health
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/health

# System status
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/status

# Available regions
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/regions

# Live flight data
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/etex/flights
```

### AWS Monitoring

```bash
# Check ECS service status
aws ecs describe-services --cluster flight-tracker-cluster --services flight-tracker-backend

# View container logs
aws logs tail /ecs/flight-tracker --follow

# Check Redis cluster health
aws elasticache describe-cache-clusters --cache-cluster-id flight-tracker-redis
```

### Performance Metrics

- **Response Time**: API endpoints typically respond in <200ms
- **Data Collection**: Updates every 15-60 seconds depending on source
- **Cache Hit Rate**: Monitor Redis statistics via `/api/v1/status`
- **Aircraft Count**: Typically 200-300 aircraft in East Texas region

## 🤖 MCP Deployment

### MCP Integration Overview

The Flight Tracker Collector includes integrated **Model Context Protocol (MCP)** server functionality that runs within the main FastAPI application. MCP enables AI assistants like Claude to interact with live flight data through structured tools.

### MCP Production Deployment

**Integrated Mode** (Default):
- MCP server runs automatically within the FastAPI application
- Access MCP endpoints at: `https://api.choppertracker.com/mcp/*`
- No additional infrastructure required

**Available MCP Endpoints**:
- `GET /mcp/info` - Server information and capabilities
- `GET /mcp/tools` - List available tools for AI interaction
- `GET /mcp/resources` - List available data resources
- `POST /mcp/tool/{tool_name}` - Execute MCP tools
- `GET /mcp/resource?uri={uri}` - Read resource content

### MCP Configuration in Production

The MCP server is configured via the main configuration file:

```yaml
global:
  mcp:
    enabled: true
    server_name: "flight-tracker-mcp"
    server_version: "1.0.0"
    transport: "stdio"
    features:
      tools: true
      resources: true
      prompts: true
```

Environment variables for MCP:
- `MCP_ENABLED=true` - Enable MCP functionality (default: true)

### MCP Standalone Deployment (Optional)

For external MCP clients (like Claude Desktop), you can run a standalone MCP server:

```bash
# On production server
python run.py --mode mcp
```

This runs the MCP server with stdio transport for external integration.

### MCP Monitoring

Monitor MCP functionality through:
- **Health Endpoint**: `GET /mcp/info` - Check MCP server status
- **Application Logs**: MCP operations logged with main application
- **Tool Usage**: Monitor via CloudWatch logs for MCP tool execution

### MCP Security

- MCP endpoints inherit all security features from the main API
- Rate limiting applies to MCP endpoints
- Same CORS and security headers
- No additional authentication required for MCP endpoints (same as flight API)

## 🔧 Configuration Updates

### Adding New Regions

1. Edit `config/collectors.yaml`
2. Deploy updated configuration
3. Monitor logs for new region initialization

### Adding Data Sources

```yaml
# Add dump1090 receiver
collectors:
  - type: "dump1090"
    enabled: true
    url: "http://your-receiver-ip/tar1090/data/aircraft.json"
    name: "Your ADS-B Receiver"
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|----------|
| `REDIS_HOST` | Redis cluster endpoint | `flight-tracker-redis.x7nm8u.0001.use1.cache.amazonaws.com` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `CONFIG_FILE` | Configuration file | `collectors.yaml` |
| `OPENSKY_USERNAME` | OpenSky API username | (optional) |
| `OPENSKY_PASSWORD` | OpenSky API password | (optional) |
| `MCP_ENABLED` | Enable MCP server functionality | `true` |
| `MCP_HOST` | MCP WebSocket host (future) | `localhost` |
| `MCP_PORT` | MCP WebSocket port (future) | `8001` |

## 🚨 Troubleshooting

### Common Issues

#### 1. Frontend Shows "Offline"
- **Cause**: Frontend can't connect to backend API
- **Fix**: Check ALB URL in `config.js` configuration
- **Verify**: Test backend API directly

#### 2. No Aircraft Data
- **Cause**: Data collectors not working or Redis connectivity issues
- **Fix**: Check ECS logs for collector errors
- **Verify**: Test OpenSky API and dump1090 endpoints

#### 3. Aircraft Missing Enrichment Data
- **Cause**: Aircraft database not loaded
- **Fix**: See [AWS_DEPLOYMENT_FIX.md](AWS_DEPLOYMENT_FIX.md)
- **Verify**: Check for registration, model, operator fields

#### 4. High API Response Times
- **Cause**: Redis cache issues or high load
- **Fix**: Check Redis cluster performance
- **Verify**: Monitor cache hit rates

### Log Analysis

```bash
# Search for errors
aws logs filter-log-events --log-group-name /ecs/flight-tracker --filter-pattern "ERROR"

# Monitor data collection
aws logs filter-log-events --log-group-name /ecs/flight-tracker --filter-pattern "Blend Stats"

# Check aircraft database loading
aws logs filter-log-events --log-group-name /ecs/flight-tracker --filter-pattern "aircraft database"
```

## 🛡️ Security

- **API Access**: Public read-only endpoints
- **AWS IAM**: Minimal required permissions
- **Network**: ALB security groups restrict access
- **Data**: No sensitive information stored or transmitted
- **Redis**: Private subnet, VPC-only access

## 🔄 Backup & Recovery

- **Configuration**: Stored in Git repository
- **Aircraft Database**: Automatically reloaded on startup
- **Redis Data**: TTL-based, no persistent storage needed
- **Logs**: Retained for 30 days in CloudWatch

## 📈 Scaling

- **Horizontal**: Add more ECS tasks
- **Vertical**: Increase CPU/memory allocation
- **Redis**: Upgrade cluster instance type
- **Regional**: Deploy in multiple AWS regions