#!/bin/bash
# Download aircraft database from S3 (always refresh on startup)

AIRCRAFT_DB_PATH="/app/config/aircraftDatabase.csv"
S3_BUCKET="flight-tracker-web-ui-1750266711"
S3_KEY="config/aircraftDatabase.csv"

echo "🔍 Downloading fresh aircraft database from S3..."

# Create config directory if it doesn't exist
mkdir -p /app/config

# Remove old version if it exists
if [ -f "$AIRCRAFT_DB_PATH" ]; then
    echo "🗑️  Removing old aircraft database..."
    rm "$AIRCRAFT_DB_PATH"
fi

# Download from S3 with retry logic
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "📥 Downloading aircraft database (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
    
    aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "$AIRCRAFT_DB_PATH" --no-progress
    
    if [ $? -eq 0 ] && [ -f "$AIRCRAFT_DB_PATH" ]; then
        echo "✅ Aircraft database downloaded successfully"
        LINES=$(wc -l < "$AIRCRAFT_DB_PATH" 2>/dev/null || echo "unknown")
        SIZE=$(du -h "$AIRCRAFT_DB_PATH" 2>/dev/null | cut -f1 || echo "unknown")
        echo "📊 File stats: $LINES lines, $SIZE"
        
        # Verify file has content
        if [ "$LINES" != "unknown" ] && [ "$LINES" -gt 10 ]; then
            echo "✅ Aircraft database appears valid"
            exit 0
        else
            echo "⚠️  Downloaded file seems too small ($LINES lines)"
        fi
    else
        echo "❌ Download attempt $((RETRY_COUNT + 1)) failed"
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "⏱️  Waiting 5 seconds before retry..."
        sleep 5
    fi
done

echo "❌ Failed to download aircraft database after $MAX_RETRIES attempts"
echo "⚠️  Flight tracking will continue without aircraft enrichment"
echo "🔧 Check S3 bucket: s3://${S3_BUCKET}/${S3_KEY}"
exit 1