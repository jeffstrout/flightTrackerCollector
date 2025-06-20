# S3 Configuration Storage Setup

🗂️ **Status**: ✅ **Configured** - All configuration files now stored in S3

**S3 Bucket**: `flight-tracker-web-ui-1750266711`
**Config Directory**: `s3://flight-tracker-web-ui-1750266711/config/`

## 📁 Configuration Files in S3

| File | Size | Purpose |
|------|------|---------|
| `aircraftDatabase.csv` | 101.3 MiB | Aircraft enrichment data (registration, model, operator) |
| `collectors.yaml` | 3.4 KiB | Production regions, collectors, and airport configuration |
| `collectors-dev.yaml` | 2.0 KiB | Development environment configuration |
| `collectors-local.yaml` | 2.1 KiB | Local development configuration |

## 🔧 Configuration Management

### Using the Config Manager Script

```bash
# List all config files in S3
./scripts/config_manager.sh list

# Upload a specific config file
./scripts/config_manager.sh upload collectors.yaml

# Download a specific config file  
./scripts/config_manager.sh download aircraftDatabase.csv

# Upload all local configs to S3
./scripts/config_manager.sh sync-up

# Download all configs from S3
./scripts/config_manager.sh sync-down

# Compare local vs S3 version
./scripts/config_manager.sh diff collectors.yaml

# Show help
./scripts/config_manager.sh help
```

### Manual S3 Operations

```bash
# List config files
aws s3 ls s3://flight-tracker-web-ui-1750266711/config/ --human-readable

# Upload individual file
aws s3 cp config/collectors.yaml s3://flight-tracker-web-ui-1750266711/config/collectors.yaml

# Download individual file
aws s3 cp s3://flight-tracker-web-ui-1750266711/config/collectors.yaml config/collectors.yaml

# Sync entire config directory
aws s3 sync config/ s3://flight-tracker-web-ui-1750266711/config/
```

## 🚀 Production Deployment

### Automatic Configuration Download

The production deployment automatically downloads configuration files from S3 on startup:

1. **ECS Container Startup**: Runs `/app/scripts/download_config.sh`
2. **Downloads**: Both `aircraftDatabase.csv` and `collectors.yaml`
3. **Local Storage**: Files stored in `/app/config/` within container
4. **Application Load**: Config loader finds files automatically

### Startup Process

```bash
🚀 Starting Flight Tracker with Configuration Setup
🔧 Checking for configuration files...
📥 aircraftDatabase.csv not found locally, downloading from S3...
✅ aircraftDatabase.csv downloaded successfully
📊 File size: 1062695 lines
📥 collectors.yaml not found locally, downloading from S3...
✅ collectors.yaml downloaded successfully
📊 File size: 3454 bytes
🎯 All configuration files are ready!
🎯 Starting application: uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## 📝 Configuration Updates

### Updating Production Configuration

1. **Edit local config file**:
   ```bash
   # Edit the configuration
   nano config/collectors.yaml
   ```

2. **Upload to S3**:
   ```bash
   # Upload updated config
   ./scripts/config_manager.sh upload collectors.yaml
   ```

3. **Restart production service**:
   ```bash
   # Force ECS service restart to reload config
   aws ecs update-service --cluster flight-tracker-cluster --service flight-tracker-backend --force-new-deployment
   ```

### Adding New Regions

Example: Adding a new region to `collectors.yaml`:

```yaml
regions:
  # Existing East Texas region
  etex:
    enabled: true
    name: "East Texas"
    # ... existing config

  # New region
  houston:
    enabled: true
    name: "Houston Metro"
    timezone: "America/Chicago"
    center:
      lat: 29.7604  # Houston, TX
      lon: -95.3698
    radius_miles: 100
    collectors:
      - type: "opensky"
        enabled: true
        url: "https://opensky-network.org/api/states/all"
        anonymous: ${OPENSKY_ANONYMOUS:-true}
```

### Updating Aircraft Database

The aircraft database is automatically downloaded from S3. To update:

1. **Replace local file**:
   ```bash
   # Copy new database file
   cp /path/to/new/aircraftDatabase.csv config/
   ```

2. **Upload to S3**:
   ```bash
   # Upload updated database
   ./scripts/config_manager.sh upload aircraftDatabase.csv
   ```

3. **Restart services** to reload database

## 🔐 Security & Permissions

### Required AWS IAM Permissions

The ECS task role needs these S3 permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::flight-tracker-web-ui-1750266711",
                "arn:aws:s3:::flight-tracker-web-ui-1750266711/config/*"
            ]
        }
    ]
}
```

### S3 Bucket Configuration

- **Bucket**: `flight-tracker-web-ui-1750266711`
- **Region**: `us-east-1`
- **Access**: Private (IAM role access only)
- **Versioning**: Recommended for config files
- **Lifecycle**: Optional - old versions cleanup

## 🎯 Benefits

### Centralized Configuration
- ✅ Single source of truth for all environments
- ✅ Easy configuration updates without code changes
- ✅ Version control via S3 versioning
- ✅ Consistent configuration across deployments

### Simplified Deployment
- ✅ No configuration files needed in Docker images
- ✅ Automatic configuration download on startup
- ✅ Easy environment-specific configurations
- ✅ Reduced container image size

### Operational Benefits
- ✅ Hot configuration reloads via service restart
- ✅ Configuration backup and recovery
- ✅ Audit trail of configuration changes
- ✅ Easy rollback to previous configurations

## 🔍 Monitoring

### Configuration Health Checks

```bash
# Verify configs are downloaded
aws ecs exec-command --cluster flight-tracker-cluster --task TASK_ID --container web-api --command "ls -la /app/config/"

# Check config content
aws ecs exec-command --cluster flight-tracker-cluster --task TASK_ID --container web-api --command "head /app/config/collectors.yaml"

# Verify S3 access
aws logs filter-log-events --log-group-name /ecs/flight-tracker --filter-pattern "configuration"
```

### Troubleshooting

**Configuration not loading**:
1. Check ECS task logs for download errors
2. Verify IAM permissions for S3 access
3. Confirm S3 bucket and file paths
4. Test S3 access manually

**Old configuration still active**:
1. Force ECS service restart
2. Check if files are cached locally
3. Verify S3 file was actually updated
4. Monitor application restart logs

## 📋 Maintenance

### Regular Tasks
- ✅ Monitor S3 storage costs (minimal for config files)
- ✅ Review and update configurations as needed
- ✅ Test configuration backups and recovery
- ✅ Update IAM permissions if bucket changes

### Backup Strategy
- ✅ S3 versioning enabled for automatic backups
- ✅ Local copies maintained in Git repository
- ✅ Configuration changes tracked in commit history
- ✅ Easy rollback via S3 version management