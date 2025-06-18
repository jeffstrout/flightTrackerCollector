#!/bin/bash

# Flight Tracker Backend Deployment Script
# This script builds and deploys the backend to ECS

set -e

# Load AWS configuration
if [ ! -f .env.aws ]; then
    echo "❌ Error: .env.aws not found. Run setup-aws-backend.sh first."
    exit 1
fi

source .env.aws

echo "🚀 Deploying Flight Tracker Backend to AWS"
echo "=================================================="

# Get Redis endpoint
echo "🔍 Getting Redis endpoint..."
REDIS_ENDPOINT=$(aws elasticache describe-cache-clusters \
    --cache-cluster-id $REDIS_CLUSTER_ID \
    --show-cache-node-info \
    --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
    --output text)

if [ "$REDIS_ENDPOINT" == "null" ] || [ -z "$REDIS_ENDPOINT" ]; then
    echo "❌ Redis cluster not ready yet. Please wait a few minutes and try again."
    exit 1
fi

echo "Redis endpoint: $REDIS_ENDPOINT"

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI

# Build Docker image
echo "🏗️  Building Docker image..."
docker build -t flight-tracker-backend .

# Tag image
docker tag flight-tracker-backend:latest $ECR_REPO_URI:latest

# Push to ECR
echo "📤 Pushing image to ECR..."
docker push $ECR_REPO_URI:latest

# Create task definition
echo "📋 Creating ECS task definition..."
cat > /tmp/task-definition.json <<EOF
{
  "family": "flight-tracker-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "$TASK_EXEC_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "web-api",
      "image": "$ECR_REPO_URI:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "REDIS_HOST",
          "value": "$REDIS_ENDPOINT"
        },
        {
          "name": "REDIS_PORT",
          "value": "6379"
        },
        {
          "name": "REDIS_DB",
          "value": "0"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        },
        {
          "name": "CONFIG_FILE",
          "value": "collectors.yaml"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/status || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "$LOG_GROUP",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "web-api"
        }
      }
    },
    {
      "name": "collector",
      "image": "$ECR_REPO_URI:latest",
      "essential": true,
      "command": ["python", "-m", "src.main"],
      "environment": [
        {
          "name": "REDIS_HOST",
          "value": "$REDIS_ENDPOINT"
        },
        {
          "name": "REDIS_PORT",
          "value": "6379"
        },
        {
          "name": "REDIS_DB",
          "value": "0"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        },
        {
          "name": "CONFIG_FILE",
          "value": "collectors.yaml"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "$LOG_GROUP",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "collector"
        }
      }
    }
  ]
}
EOF

# Register task definition
TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "Task definition registered: $TASK_DEF_ARN"

# Create or update service
echo "🚢 Creating/updating ECS service..."
SERVICE_EXISTS=$(aws ecs describe-services \
    --cluster $ECS_CLUSTER \
    --services flight-tracker-backend \
    --query 'services[0].serviceName' \
    --output text 2>/dev/null || echo "")

if [ "$SERVICE_EXISTS" == "flight-tracker-backend" ]; then
    echo "Updating existing service..."
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service flight-tracker-backend \
        --task-definition flight-tracker-backend \
        --force-new-deployment
else
    echo "Creating new service..."
    aws ecs create-service \
        --cluster $ECS_CLUSTER \
        --service-name flight-tracker-backend \
        --task-definition flight-tracker-backend \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
        --load-balancers targetGroupArn=$TARGET_GROUP_ARN,containerName=web-api,containerPort=8000 \
        --health-check-grace-period-seconds 60
fi

# Wait for service to stabilize
echo "⏳ Waiting for service to stabilize (this may take 5-10 minutes)..."
aws ecs wait services-stable \
    --cluster $ECS_CLUSTER \
    --services flight-tracker-backend

# Clean up
rm -f /tmp/task-definition.json

echo "✅ Backend deployment complete!"
echo "=================================================="
echo "API URL: http://$ALB_DNS"
echo "API Status: http://$ALB_DNS/api/v1/status"
echo ""
echo "To check service status:"
echo "aws ecs describe-services --cluster $ECS_CLUSTER --services flight-tracker-backend"
echo ""
echo "To view logs:"
echo "aws logs tail $LOG_GROUP --follow"
echo ""
echo "Next step: Update frontend VITE_API_BASE_URL to http://$ALB_DNS"