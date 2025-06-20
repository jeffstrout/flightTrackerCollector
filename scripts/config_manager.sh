#!/bin/bash
# Configuration management script for S3-stored configs

S3_BUCKET="flight-tracker-web-ui-1750266711"
CONFIG_DIR="config"

show_help() {
    echo "🔧 Flight Tracker Configuration Manager"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  upload [file]     Upload config file(s) to S3"
    echo "  download [file]   Download config file(s) from S3"
    echo "  list              List all config files in S3"
    echo "  sync-up           Upload all local config files to S3"
    echo "  sync-down         Download all config files from S3"
    echo "  diff [file]       Compare local and S3 versions"
    echo ""
    echo "Examples:"
    echo "  $0 upload collectors.yaml"
    echo "  $0 download aircraftDatabase.csv"
    echo "  $0 list"
    echo "  $0 sync-up"
}

list_s3_configs() {
    echo "📋 Configuration files in S3:"
    aws s3 ls s3://${S3_BUCKET}/config/ --human-readable
}

upload_file() {
    local file_name="$1"
    local local_path="$CONFIG_DIR/$file_name"
    local s3_key="config/$file_name"
    
    if [ ! -f "$local_path" ]; then
        echo "❌ File not found: $local_path"
        exit 1
    fi
    
    echo "📤 Uploading $file_name to S3..."
    aws s3 cp "$local_path" "s3://${S3_BUCKET}/${s3_key}"
    
    if [ $? -eq 0 ]; then
        echo "✅ $file_name uploaded successfully"
    else
        echo "❌ Failed to upload $file_name"
        exit 1
    fi
}

download_file() {
    local file_name="$1"
    local local_path="$CONFIG_DIR/$file_name"
    local s3_key="config/$file_name"
    
    echo "📥 Downloading $file_name from S3..."
    mkdir -p "$CONFIG_DIR"
    aws s3 cp "s3://${S3_BUCKET}/${s3_key}" "$local_path"
    
    if [ $? -eq 0 ]; then
        echo "✅ $file_name downloaded successfully"
    else
        echo "❌ Failed to download $file_name"
        exit 1
    fi
}

sync_up() {
    echo "📤 Syncing all local configs to S3..."
    ./scripts/upload_config.sh
}

sync_down() {
    echo "📥 Syncing all configs from S3..."
    mkdir -p "$CONFIG_DIR"
    aws s3 sync s3://${S3_BUCKET}/config/ "$CONFIG_DIR/"
    echo "✅ All configs downloaded"
}

diff_file() {
    local file_name="$1"
    local local_path="$CONFIG_DIR/$file_name"
    local temp_file="/tmp/$file_name"
    
    if [ ! -f "$local_path" ]; then
        echo "❌ Local file not found: $local_path"
        exit 1
    fi
    
    echo "🔍 Comparing local and S3 versions of $file_name..."
    aws s3 cp "s3://${S3_BUCKET}/config/${file_name}" "$temp_file" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "📊 Differences (local vs S3):"
        diff "$local_path" "$temp_file" || echo "✅ Files are identical"
        rm -f "$temp_file"
    else
        echo "❌ S3 file not found or access error"
        exit 1
    fi
}

# Parse command line arguments
case "$1" in
    "list")
        list_s3_configs
        ;;
    "upload")
        if [ -z "$2" ]; then
            echo "❌ Please specify a file to upload"
            echo "Usage: $0 upload <filename>"
            exit 1
        fi
        upload_file "$2"
        ;;
    "download")
        if [ -z "$2" ]; then
            echo "❌ Please specify a file to download"
            echo "Usage: $0 download <filename>"
            exit 1
        fi
        download_file "$2"
        ;;
    "sync-up")
        sync_up
        ;;
    "sync-down")
        sync_down
        ;;
    "diff")
        if [ -z "$2" ]; then
            echo "❌ Please specify a file to compare"
            echo "Usage: $0 diff <filename>"
            exit 1
        fi
        diff_file "$2"
        ;;
    "help"|"-h"|"--help"|"")
        show_help
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac