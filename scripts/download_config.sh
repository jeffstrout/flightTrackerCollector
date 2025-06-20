#!/bin/bash
# Download configuration files from S3 if not present locally

S3_BUCKET="flight-tracker-web-ui-1750266711"
CONFIG_DIR="/app/config"

echo "🔧 Checking for configuration files..."

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Function to download file from S3 if not present
download_if_missing() {
    local file_name="$1"
    local s3_key="config/$1"
    local local_path="$CONFIG_DIR/$1"
    
    if [ ! -f "$local_path" ]; then
        echo "📥 $file_name not found locally, downloading from S3..."
        
        aws s3 cp "s3://${S3_BUCKET}/${s3_key}" "$local_path"
        
        if [ $? -eq 0 ]; then
            echo "✅ $file_name downloaded successfully"
            if [[ "$file_name" == *.csv ]]; then
                echo "📊 File size: $(wc -l < $local_path) lines"
            else
                echo "📊 File size: $(wc -c < $local_path) bytes"
            fi
        else
            echo "❌ Failed to download $file_name from S3"
            return 1
        fi
    else
        echo "✅ $file_name found locally"
        if [[ "$file_name" == *.csv ]]; then
            echo "📊 File size: $(wc -l < $local_path) lines"
        else
            echo "📊 File size: $(wc -c < $local_path) bytes"
        fi
    fi
    return 0
}

# Download aircraft database
download_if_missing "aircraftDatabase.csv"

# Download collectors configuration
download_if_missing "collectors.yaml"

# Check if we have the essential files
if [ -f "$CONFIG_DIR/aircraftDatabase.csv" ] && [ -f "$CONFIG_DIR/collectors.yaml" ]; then
    echo "🎯 All configuration files are ready!"
else
    echo "⚠️  Some configuration files are missing, but continuing..."
fi