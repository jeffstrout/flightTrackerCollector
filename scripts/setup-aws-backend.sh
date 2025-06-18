#!/bin/bash

# Flight Tracker Backend AWS Setup Script
# This script creates the infrastructure for the backend services

set -e

# Configuration
PROJECT_NAME="flight-tracker"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TIMESTAMP=$(date +%s)

echo "🚀 Setting up AWS infrastructure for Flight Tracker Backend"
echo "=================================================="
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"

# Create ECR repository
echo "📦 Creating ECR repository for Docker images"
ECR_REPO_URI=$(aws ecr create-repository \
    --repository-name ${PROJECT_NAME}-backend \
    --region $REGION \
    --query 'repository.repositoryUri' \
    --output text 2>/dev/null || \
    aws ecr describe-repositories \
        --repository-names ${PROJECT_NAME}-backend \
        --region $REGION \
        --query 'repositories[0].repositoryUri' \
        --output text)

echo "ECR Repository: $ECR_REPO_URI"

# Create VPC and networking (or use default)
echo "🌐 Setting up networking"
DEFAULT_VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=is-default,Values=true" \
    --query 'Vpcs[0].VpcId' \
    --output text)

# Get default subnets
SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$DEFAULT_VPC_ID" \
    --query 'Subnets[*].SubnetId' \
    --output text | tr '\t' ',')

echo "Using VPC: $DEFAULT_VPC_ID"
echo "Subnets: $SUBNET_IDS"

# Create security groups
echo "🔒 Creating security groups"

# ALB Security Group
ALB_SG_ID=$(aws ec2 create-security-group \
    --group-name ${PROJECT_NAME}-alb-sg \
    --description "Security group for Flight Tracker ALB" \
    --vpc-id $DEFAULT_VPC_ID \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT_NAME}-alb-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

# Allow HTTP and HTTPS traffic to ALB
aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 2>/dev/null || true

aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 2>/dev/null || true

# ECS Security Group
ECS_SG_ID=$(aws ec2 create-security-group \
    --group-name ${PROJECT_NAME}-ecs-sg \
    --description "Security group for Flight Tracker ECS tasks" \
    --vpc-id $DEFAULT_VPC_ID \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT_NAME}-ecs-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

# Allow traffic from ALB to ECS
aws ec2 authorize-security-group-ingress \
    --group-id $ECS_SG_ID \
    --protocol tcp \
    --port 8000 \
    --source-group $ALB_SG_ID 2>/dev/null || true

# Redis Security Group
REDIS_SG_ID=$(aws ec2 create-security-group \
    --group-name ${PROJECT_NAME}-redis-sg \
    --description "Security group for Flight Tracker Redis" \
    --vpc-id $DEFAULT_VPC_ID \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT_NAME}-redis-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

# Allow traffic from ECS to Redis
aws ec2 authorize-security-group-ingress \
    --group-id $REDIS_SG_ID \
    --protocol tcp \
    --port 6379 \
    --source-group $ECS_SG_ID 2>/dev/null || true

# Create ElastiCache subnet group
echo "🗄️  Creating ElastiCache Redis cluster"
aws elasticache create-cache-subnet-group \
    --cache-subnet-group-name ${PROJECT_NAME}-redis-subnet \
    --cache-subnet-group-description "Subnet group for Flight Tracker Redis" \
    --subnet-ids ${SUBNET_IDS//,/ } 2>/dev/null || true

# Create ElastiCache Redis cluster
REDIS_ENDPOINT=$(aws elasticache create-cache-cluster \
    --cache-cluster-id ${PROJECT_NAME}-redis \
    --engine redis \
    --cache-node-type cache.t3.micro \
    --num-cache-nodes 1 \
    --cache-subnet-group-name ${PROJECT_NAME}-redis-subnet \
    --security-group-ids $REDIS_SG_ID \
    --query 'CacheCluster.CacheClusterId' \
    --output text 2>/dev/null || \
    aws elasticache describe-cache-clusters \
        --cache-cluster-id ${PROJECT_NAME}-redis \
        --show-cache-node-info \
        --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
        --output text)

echo "Redis cluster created: ${PROJECT_NAME}-redis"

# Create ECS cluster
echo "🚢 Creating ECS cluster"
aws ecs create-cluster \
    --cluster-name ${PROJECT_NAME}-cluster \
    --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1 2>/dev/null || true

# Create IAM roles
echo "👤 Creating IAM roles"

# Task execution role
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

TASK_EXEC_ROLE_ARN=$(aws iam create-role \
    --role-name ${PROJECT_NAME}-task-execution-role \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    --query 'Role.Arn' \
    --output text 2>/dev/null || \
    aws iam get-role \
        --role-name ${PROJECT_NAME}-task-execution-role \
        --query 'Role.Arn' \
        --output text)

# Attach policies
aws iam attach-role-policy \
    --role-name ${PROJECT_NAME}-task-execution-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true

# Create ALB
echo "⚖️  Creating Application Load Balancer"
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name ${PROJECT_NAME}-alb \
    --subnets ${SUBNET_IDS//,/ } \
    --security-groups $ALB_SG_ID \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text 2>/dev/null || \
    aws elbv2 describe-load-balancers \
        --names ${PROJECT_NAME}-alb \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --query 'LoadBalancers[0].DNSName' \
    --output text)

# Create target group
TARGET_GROUP_ARN=$(aws elbv2 create-target-group \
    --name ${PROJECT_NAME}-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id $DEFAULT_VPC_ID \
    --target-type ip \
    --health-check-path /api/v1/status \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text 2>/dev/null || \
    aws elbv2 describe-target-groups \
        --names ${PROJECT_NAME}-tg \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text)

# Create ALB listener
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN 2>/dev/null || true

# Create CloudWatch log group
echo "📊 Creating CloudWatch log group"
aws logs create-log-group \
    --log-group-name /ecs/${PROJECT_NAME} 2>/dev/null || true

# Save configuration
echo "💾 Saving configuration"
cat > .env.aws <<EOF
# AWS Backend Configuration (created by setup script)
AWS_ACCOUNT_ID=$ACCOUNT_ID
AWS_REGION=$REGION
ECR_REPO_URI=$ECR_REPO_URI
ECS_CLUSTER=${PROJECT_NAME}-cluster
ALB_DNS=$ALB_DNS
ALB_ARN=$ALB_ARN
TARGET_GROUP_ARN=$TARGET_GROUP_ARN
TASK_EXEC_ROLE_ARN=$TASK_EXEC_ROLE_ARN
VPC_ID=$DEFAULT_VPC_ID
SUBNET_IDS=$SUBNET_IDS
ECS_SG_ID=$ECS_SG_ID
REDIS_CLUSTER_ID=${PROJECT_NAME}-redis
REDIS_SG_ID=$REDIS_SG_ID
LOG_GROUP=/ecs/${PROJECT_NAME}
EOF

# Clean up
rm -f /tmp/trust-policy.json

echo "✅ Backend infrastructure setup complete!"
echo "=================================================="
echo "ECR Repository: $ECR_REPO_URI"
echo "ECS Cluster: ${PROJECT_NAME}-cluster"
echo "ALB URL: http://$ALB_DNS"
echo "Redis Cluster: ${PROJECT_NAME}-redis"
echo ""
echo "Configuration saved to .env.aws"
echo ""
echo "Next steps:"
echo "1. Wait 5-10 minutes for Redis cluster to be available"
echo "2. Build and push Docker image: ./scripts/deploy-backend.sh"
echo "3. Update frontend VITE_API_BASE_URL to: http://$ALB_DNS"