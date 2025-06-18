#!/bin/bash
# Startup script that downloads aircraft database then starts the application

set -e

echo "🚀 Starting Flight Tracker with Aircraft Database"

# Download aircraft database from S3
/app/scripts/download_aircraft_db.sh

# Start the application with passed arguments
echo "🎯 Starting application: $@"
exec "$@"