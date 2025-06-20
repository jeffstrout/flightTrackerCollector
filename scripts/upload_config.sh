#!/bin/bash
# Upload configuration files to S3

S3_BUCKET="flight-tracker-web-ui-1750266711"
CONFIG_DIR="config"

echo "📤 Uploading configuration files to S3..."

# Function to upload file to S3
upload_to_s3() {
    local file_name="$1"
    local local_path="$CONFIG_DIR/$1"
    local s3_key="config/$1"
    
    if [ -f "$local_path" ]; then
        echo "📤 Uploading $file_name to S3..."
        
        aws s3 cp "$local_path" "s3://${S3_BUCKET}/${s3_key}"
        
        if [ $? -eq 0 ]; then
            echo "✅ $file_name uploaded successfully"
        else
            echo "❌ Failed to upload $file_name to S3"
            return 1
        fi
    else
        echo "⚠️  $file_name not found locally at $local_path"
        return 1
    fi
    return 0
}

# Upload aircraft database
upload_to_s3 "aircraftDatabase.csv"

# Upload collectors configuration  
upload_to_s3 "collectors.yaml"

# Upload other config files if they exist
for config_file in "$CONFIG_DIR"/*.yaml "$CONFIG_DIR"/*.yml; do
    if [ -f "$config_file" ]; then
        filename=$(basename "$config_file")
        if [ "$filename" != "collectors.yaml" ]; then
            echo "📤 Found additional config: $filename"
            upload_to_s3 "$filename"
        fi
    fi
done

echo "🎯 Configuration upload complete!"

# List uploaded files
echo "📋 Files in S3 config directory:"
aws s3 ls s3://${S3_BUCKET}/config/ --human-readable