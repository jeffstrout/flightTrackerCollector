# AWS Aircraft Database Fix

## Problem
The aircraft database (aircraftDatabase.csv) is not loading on AWS, causing flight data to lack enrichment (registration, model, operator info).

## Root Causes
1. **File Path Issues**: CSV file path not accessible in Docker container
2. **Empty Redis**: New Redis instance doesn't have aircraft database pre-loaded
3. **File Permissions**: CSV file might not be readable in container

## Solution

### 1. Immediate Fix - Manual Database Load

SSH into your AWS instance and run this command to force-load the database:

```bash
# Navigate to your project directory
cd /path/to/flightTrackerCollector

# Run the manual database loader
docker-compose -f docker-compose.prod.yml exec collector python scripts/load_aircraft_db.py
```

### 2. Verify the Fix

Check if the database loaded successfully:

```bash
# Check logs for database loading messages
docker-compose -f docker-compose.prod.yml logs collector | grep -i "aircraft database"

# Test the API to see if aircraft have enrichment data
curl "http://localhost:8000/api/v1/etex/flights" | jq '.aircraft[0] | {hex, flight, registration, model, operator}'
```

### 3. Permanent Fix - Rebuild with Updated Code

The code has been updated to:
- Try multiple file paths for the CSV
- Provide better error messages
- Gracefully handle missing database files
- Add Docker build verification

Rebuild and redeploy:

```bash
# Pull latest code with fixes
git pull origin main

# Rebuild with updated code
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d

# Monitor startup logs
docker-compose -f docker-compose.prod.yml logs -f collector
```

### 4. Expected Log Messages

After the fix, you should see these messages:

✅ **Success:**
```
Found aircraft database at: /app/config/aircraftDatabase.csv
Aircraft database found: 1234567 lines
✅ Using aircraft database from Redis
```

OR (first time setup):
```
📤 Importing aircraft database to Redis for faster lookups
Imported 1234567 aircraft to Redis
```

❌ **If still failing:**
```
⚠️  No aircraft database available - aircraft enrichment will be limited
WARNING: Aircraft database not found at config/aircraftDatabase.csv
```

### 5. Troubleshooting

**If database still won't load:**

1. **Check file exists in container:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec collector ls -la config/
   docker-compose -f docker-compose.prod.yml exec collector wc -l config/aircraftDatabase.csv
   ```

2. **Check Redis connectivity:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec collector python -c "
   from src.services.redis_service import RedisService
   r = RedisService()
   print(f'Redis connected: {r.redis_client is not None}')
   "
   ```

3. **Manual verification:**
   ```bash
   # Check if Redis has aircraft data
   docker-compose -f docker-compose.prod.yml exec collector python -c "
   from src.services.redis_service import RedisService
   r = RedisService()
   if r.redis_client:
       keys = r.redis_client.keys('aircraft_db:*')
       print(f'Aircraft keys in Redis: {len(keys)}')
   "
   ```

### 6. Alternative: Copy Database Manually

If the automated loading fails, you can manually copy the database:

```bash
# Copy from local to AWS instance
scp config/aircraftDatabase.csv user@your-aws-instance:/path/to/flightTrackerCollector/config/

# Ensure proper permissions
chmod 644 config/aircraftDatabase.csv
```

## Expected Results

After applying the fix:
1. **Aircraft data will include:** registration, model, manufacturer, operator, owner
2. **Helicopter detection will work:** Uses ICAO aircraft class from database
3. **API responses will be enriched:** Full aircraft information available
4. **Logs will show success:** Clear messages about database status

## Verification Commands

```bash
# 1. Check aircraft enrichment
curl -s "http://localhost:8000/api/v1/etex/flights" | jq '.aircraft[0] | {hex, flight, registration, model, operator, manufacturer}'

# 2. Check helicopter detection
curl -s "http://localhost:8000/api/v1/etex/choppers" | jq '.aircraft_count'

# 3. Check system status
curl -s "http://localhost:8000/api/v1/status" | jq '.redis'
```

## Prevention

To prevent this issue in future deployments:
1. Always verify the config/ directory is copied to containers
2. Check Redis has sufficient memory for aircraft database (~100MB)
3. Monitor startup logs for database loading messages
4. Use the manual loader script after any Redis resets