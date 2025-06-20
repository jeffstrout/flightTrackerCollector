#!/bin/bash
# Startup script that downloads all configuration files then starts the application

set -e

echo "🚀 Starting Flight Tracker with Configuration Setup"

# Download all configuration files from S3
/app/scripts/download_config.sh

# Start the application with passed arguments
echo "🎯 Starting application: $@"
exec "$@"