#!/bin/bash
# Setup script for centralized Redis stack

set -e

echo "Setting up centralized Redis stack..."

# Create shared network if it doesn't exist
if ! docker network ls | grep -q shared_services; then
    echo "Creating shared_services network..."
    docker network create shared_services
else
    echo "Network shared_services already exists"
fi

# Create persistent volume if it doesn't exist
if ! docker volume ls | grep -q redis_data; then
    echo "Creating redis_data volume..."
    docker volume create redis_data
else
    echo "Volume redis_data already exists"
fi

# Start Redis stack
echo "Starting Redis stack..."
docker-compose up -d

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until docker exec shared_redis redis-cli ping > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo " Ready!"

# Show status
echo ""
echo "Redis Stack Status:"
docker-compose ps

echo ""
echo "Redis is available at:"
echo "  - Redis: localhost:6379"
echo "  - Redis Commander: http://localhost:8081"
echo "    Username: admin"
echo "    Password: admin (change in production!)"
echo ""
echo "Database allocation:"
echo "  - DB 0: Flight Tracker Collector"
echo "  - DB 1-14: Available for other apps"
echo "  - DB 15: Testing/Development"