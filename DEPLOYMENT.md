# Production Deployment Guide

## Prerequisites
- Docker and Docker Compose installed on production server
- Access to centralized Redis instance (shared_redis)
- Git repository cloned on production server

## Deployment Steps

### 1. Update Production Configuration

**IMPORTANT**: The production config (`config/collectors.yaml`) needs your dump1090 receiver added!

Edit `config/collectors.yaml` on your production server and add the dump1090 collector:

```yaml
regions:
  etex:
    collectors:
      - type: "opensky"
        enabled: true
        url: "https://opensky-network.org/api/states/all"
        anonymous: ${OPENSKY_ANONYMOUS:-true}
        username: ${OPENSKY_USERNAME:-}
        password: ${OPENSKY_PASSWORD:-}
      
      # Add your dump1090 receiver
      - type: "dump1090"
        enabled: true
        url: "http://192.168.0.13/tar1090/data/aircraft.json"
        name: "Home ADS-B Receiver"
```

### 2. Pull Latest Code

```bash
cd /path/to/flightTrackerCollector
git pull origin main
```

### 3. Stop Existing Containers (if running)

```bash
docker-compose -f docker-compose.prod.yml down
```

### 4. Build New Images

```bash
docker-compose -f docker-compose.prod.yml build
```

### 5. Start Services

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 6. Verify Deployment

```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status
curl http://localhost:8000/api/v1/regions
```

## Configuration Management

### Option 1: Create Production-Specific Config
Create `config/collectors-prod.yaml` with your production settings:
```bash
cp config/collectors-local.yaml config/collectors-prod.yaml
# Edit to adjust for production (change Redis host, logging level, etc.)
```

Then update `docker-compose.prod.yml`:
```yaml
environment:
  - CONFIG_FILE=collectors-prod.yaml
```

### Option 2: Use Environment Variables
Keep sensitive data in `.env` file on production:
```bash
# .env file (DO NOT COMMIT)
OPENSKY_USERNAME=your_username
OPENSKY_PASSWORD=your_password
REDIS_HOST=shared_redis
LOG_LEVEL=INFO
```

## Network Considerations

If your dump1090 receiver at `192.168.0.13` is not accessible from the Docker container:

1. **If on same network**: No changes needed
2. **If on different network**: Use public IP or VPN
3. **If running on same host**: Use `host.docker.internal` (Docker Desktop) or actual host IP

## Monitoring

- Logs are stored in a Docker volume: `flight_logs`
- Access logs: `docker-compose -f docker-compose.prod.yml exec collector tail -f /app/logs/flight_collector.log`
- The application will automatically rotate logs at midnight

## Troubleshooting

### Container won't start
- Check logs: `docker-compose -f docker-compose.prod.yml logs collector`
- Verify Redis connectivity
- Ensure shared_services network exists

### No data from dump1090
- Verify the URL is accessible from production server
- Check firewall rules
- Test with curl: `curl http://192.168.0.13/tar1090/data/aircraft.json`

### API not accessible
- Check port 8000 is not already in use
- Verify firewall allows port 8000
- Check container is running: `docker ps`