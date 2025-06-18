#!/bin/bash
# Download aircraft database from S3 if not present locally

AIRCRAFT_DB_PATH="/app/config/aircraftDatabase.csv"
S3_BUCKET="flight-tracker-web-ui-1750266711"
S3_KEY="config/aircraftDatabase.csv"

echo "🔍 Checking for aircraft database..."

if [ ! -f "$AIRCRAFT_DB_PATH" ]; then
    echo "📥 Aircraft database not found locally, downloading from S3..."
    
    # Create config directory if it doesn't exist
    mkdir -p /app/config
    
    # Download from S3
    aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "$AIRCRAFT_DB_PATH"
    
    if [ $? -eq 0 ]; then
        echo "✅ Aircraft database downloaded successfully"
        echo "📊 File size: $(wc -l < $AIRCRAFT_DB_PATH) lines"
    else
        echo "❌ Failed to download aircraft database from S3"
        echo "⚠️  Flight tracking will continue without aircraft enrichment"
    fi
else
    echo "✅ Aircraft database found locally"
    echo "📊 File size: $(wc -l < $AIRCRAFT_DB_PATH) lines"
fi