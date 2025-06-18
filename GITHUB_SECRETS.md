# GitHub Secrets Configuration - Backend

To enable automated backend deployments, add these secrets to your GitHub repository:

## Required GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each:

### AWS Credentials (same as frontend)
- **Name**: `AWS_ACCESS_KEY_ID`
- **Value**: Your AWS Access Key ID

- **Name**: `AWS_SECRET_ACCESS_KEY`
- **Value**: Your AWS Secret Access Key

### Backend Configuration
- **Name**: `ECS_CLUSTER`
- **Value**: `flight-tracker-cluster`

- **Name**: `TASK_EXEC_ROLE_ARN`
- **Value**: `arn:aws:iam::958933162000:role/flight-tracker-task-execution-role`

- **Name**: `LOG_GROUP`
- **Value**: `/ecs/flight-tracker`

- **Name**: `REDIS_CLUSTER_ID`
- **Value**: `flight-tracker-redis`

- **Name**: `ALB_DNS`
- **Value**: `flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com`

## Current Infrastructure

- **ECR Repository**: 958933162000.dkr.ecr.us-east-1.amazonaws.com/flight-tracker-backend
- **ECS Cluster**: flight-tracker-cluster
- **ALB URL**: http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com
- **Redis Cluster**: flight-tracker-redis
- **Region**: us-east-1

## Testing the API

Once deployed, test the API:
```bash
# Check status
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/status

# Get regions
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/regions

# Get flights (once collector is running)
curl http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/etex/flights
```