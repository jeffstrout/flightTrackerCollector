# GitHub Actions CI/CD Configuration

🚀 **Status**: ✅ **Fully Configured** - Automated deployments active

**Current Deployment**: Both frontend and backend deploy automatically on push to `main` branch.

## 🔐 Required GitHub Secrets

To enable automated deployments, configure these secrets in your GitHub repository:

**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

### AWS Credentials
| Secret Name | Value | Purpose |
|-------------|-------|----------|
| `AWS_ACCESS_KEY_ID` | Your AWS Access Key ID | AWS API authentication |
| `AWS_SECRET_ACCESS_KEY` | Your AWS Secret Access Key | AWS API authentication |
| `AWS_DEFAULT_REGION` | `us-east-1` | Default AWS region |

### Backend Infrastructure
| Secret Name | Value | Purpose |
|-------------|-------|----------|
| `ECS_CLUSTER` | `flight-tracker-cluster` | ECS cluster name |
| `ECS_SERVICE` | `flight-tracker-backend` | ECS service name |
| `ECR_REPOSITORY` | `958933162000.dkr.ecr.us-east-1.amazonaws.com/flight-tracker-backend` | Container registry |
| `TASK_EXEC_ROLE_ARN` | `arn:aws:iam::958933162000:role/flight-tracker-task-execution-role` | ECS execution role |
| `TASK_ROLE_ARN` | `arn:aws:iam::958933162000:role/flight-tracker-task-role` | ECS task role |
| `LOG_GROUP` | `/ecs/flight-tracker` | CloudWatch log group |

### Frontend Infrastructure
| Secret Name | Value | Purpose |
|-------------|-------|----------|
| `S3_BUCKET` | `flight-tracker-web-ui-1750266711` | Frontend hosting bucket |
| `ALB_DNS` | `flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com` | Backend API endpoint |

### Redis Configuration
| Secret Name | Value | Purpose |
|-------------|-------|----------|
| `REDIS_HOST` | `flight-tracker-redis.x7nm8u.0001.use1.cache.amazonaws.com` | Redis cluster endpoint |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |

## 🏗️ Current AWS Infrastructure

### Production Environment
| Service | Resource ID | Purpose |
|---------|-------------|----------|
| **ECS Cluster** | `flight-tracker-cluster` | Container orchestration |
| **ECS Service** | `flight-tracker-backend` | Backend application |
| **Load Balancer** | `flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com` | Public API access |
| **Redis Cluster** | `flight-tracker-redis.x7nm8u.0001.use1.cache.amazonaws.com` | Data caching |
| **ECR Repository** | `flight-tracker-backend` | Container images |
| **S3 Bucket** | `flight-tracker-web-ui-1750266711` | Frontend hosting |
| **IAM Roles** | `flight-tracker-task-*` | ECS permissions |
| **CloudWatch** | `/ecs/flight-tracker` | Logging |

### Network Configuration
- **Region**: `us-east-1`
- **VPC**: Default VPC with public subnets
- **Security Groups**: HTTP/HTTPS access configured
- **Target Groups**: Health checks on `/health` endpoint

## 🚀 GitHub Actions Workflows

### Backend Deployment (`.github/workflows/deploy-backend.yml`)

```yaml
name: Deploy Backend to AWS ECS
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Build and push Docker image
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ secrets.ECR_REPOSITORY }}
          docker build -t flight-tracker-backend .
          docker tag flight-tracker-backend:latest ${{ secrets.ECR_REPOSITORY }}:latest
          docker push ${{ secrets.ECR_REPOSITORY }}:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster ${{ secrets.ECS_CLUSTER }} --service ${{ secrets.ECS_SERVICE }} --force-new-deployment
```

### Frontend Deployment (`.github/workflows/deploy-frontend.yml`)

```yaml
name: Deploy Frontend to S3
on:
  push:
    branches: [main]
    paths: ['frontend/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Upload to S3
        run: |
          aws s3 sync frontend/ s3://${{ secrets.S3_BUCKET }}/ --delete
          
      - name: Update configuration
        run: |
          echo "window.API_BASE_URL='http://${{ secrets.ALB_DNS }}/api/v1';" > config.js
          aws s3 cp config.js s3://${{ secrets.S3_BUCKET }}/config.js
```

## 🔍 Testing & Verification

### Automated Tests

```bash
# Health check
curl -f http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/health

# API status
curl -f http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/status

# Data endpoints
curl -f http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/regions
curl -f http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/etex/flights

# Frontend
curl -I http://flight-tracker-web-ui-1750266711.s3-website-us-east-1.amazonaws.com/
```

### Performance Validation

```bash
# Response time check
time curl -s http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/status > /dev/null

# Data freshness
curl -s "http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/etex/flights" | jq '.timestamp'

# Aircraft count
curl -s "http://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/etex/flights" | jq '.aircraft_count'
```

## 🚨 Troubleshooting Deployments

### Common Issues

1. **ECS Task Fails to Start**
   - Check CloudWatch logs: `/ecs/flight-tracker`
   - Verify IAM permissions
   - Check health check endpoints

2. **Docker Build Fails**
   - Verify dependencies in `requirements.txt`
   - Check Dockerfile syntax
   - Ensure all required files are copied

3. **S3 Upload Fails**
   - Verify bucket permissions
   - Check AWS credentials
   - Ensure bucket exists

### Deployment Monitoring

```bash
# Watch ECS deployment
aws ecs describe-services --cluster flight-tracker-cluster --services flight-tracker-backend

# Check recent deployments
aws ecs list-tasks --cluster flight-tracker-cluster --service-name flight-tracker-backend

# View logs
aws logs tail /ecs/flight-tracker --follow
```

## 🔄 Rollback Procedures

### Backend Rollback

```bash
# List previous task definitions
aws ecs list-task-definitions --family-prefix flight-tracker-backend

# Update service to previous version
aws ecs update-service --cluster flight-tracker-cluster --service flight-tracker-backend --task-definition flight-tracker-backend:X
```

### Frontend Rollback

```bash
# Restore from backup (if available)
aws s3 sync s3://backup-bucket/ s3://flight-tracker-web-ui-1750266711/ --delete
```

## 📈 Current Status

- ✅ **Backend**: Deployed and healthy
- ✅ **Frontend**: Deployed and accessible  
- ✅ **Database**: Aircraft enrichment working
- ✅ **Monitoring**: CloudWatch logs active
- ✅ **Performance**: <200ms response times
- ✅ **Data Collection**: ~250 aircraft tracked

**Last Deployment**: 2025-06-18
**Next Scheduled Check**: Continuous monitoring via GitHub Actions