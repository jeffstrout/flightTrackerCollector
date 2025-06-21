# AWS Cost Monitoring Setup Guide

This guide covers setting up AWS cost monitoring for the Flight Tracker Collector application.

## Overview

The cost monitoring feature provides real-time AWS cost tracking through the following endpoints:

- `GET /api/v1/costs/current` - Current month costs with service breakdown
- `GET /api/v1/costs/daily` - Daily cost breakdown for last N days  
- `GET /api/v1/costs/budget` - Budget status and utilization
- `GET /api/v1/costs/forecast` - Cost forecast for next N days
- `GET /api/v1/costs/summary` - Comprehensive cost overview

## Prerequisites

1. **AWS Account**: Must have access to AWS Cost Explorer
2. **IAM Permissions**: Application needs specific Cost Explorer and Budgets permissions
3. **Cost Explorer**: Must be enabled in AWS console (free, but requires activation)
4. **Budgets** (Optional): For budget monitoring features

## Setup Instructions

### 1. Enable AWS Cost Explorer

1. Log into AWS Console
2. Navigate to AWS Cost Management > Cost Explorer
3. Click "Enable Cost Explorer" if not already enabled
4. Wait for data to populate (can take 24 hours for first-time setup)

### 2. Configure IAM Permissions

#### Option A: Update Existing ECS Task Role

Add the cost monitoring policy to your existing ECS task role:

```bash
# Get the current task role ARN from your task definition
aws ecs describe-task-definition --task-definition flight-tracker-backend

# Attach the cost monitoring policy
aws iam attach-role-policy \
    --role-name flight-tracker-task-role \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/FlightTrackerCostMonitoring
```

#### Option B: Create New IAM Policy

1. Use the provided `cost-monitoring-iam-policy.json` file
2. Create the policy in AWS:

```bash
aws iam create-policy \
    --policy-name FlightTrackerCostMonitoring \
    --policy-document file://cost-monitoring-iam-policy.json \
    --description "Cost monitoring permissions for Flight Tracker"
```

3. Attach to your ECS task role:

```bash
aws iam attach-role-policy \
    --role-name YOUR_ECS_TASK_ROLE \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/FlightTrackerCostMonitoring
```

### 3. Set Up AWS Budgets (Optional)

For budget monitoring features, create budgets in AWS Console:

1. Navigate to AWS Cost Management > Budgets
2. Create budget(s) for your account
3. Set appropriate limits and alerts
4. Budget data will automatically appear in the cost API

### 4. Update ECS Task Definition

The ECS task needs the updated IAM permissions. Update your task definition:

```json
{
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/YOUR_TASK_ROLE_WITH_COST_PERMISSIONS"
}
```

Deploy the updated task definition:

```bash
aws ecs update-service \
    --cluster flight-tracker-cluster \
    --service flight-tracker-backend \
    --force-new-deployment
```

## API Usage Examples

### Get Current Month Costs

```bash
curl -X GET "https://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/costs/current"
```

Response:
```json
{
  "total": 1.11,
  "currency": "USD",
  "period": "2025-06-01 to 2025-06-21",
  "breakdown": {
    "Amazon Elastic Compute Cloud - Compute": 0.35,
    "Amazon Virtual Private Cloud": 0.69,
    "Amazon Elastic Load Balancing": 0.07
  },
  "last_updated": "2025-06-21T10:30:00"
}
```

### Get Budget Status

```bash
curl -X GET "https://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/costs/budget"
```

Response:
```json
{
  "overall_status": "healthy",
  "budget_count": 1,
  "budgets": [
    {
      "name": "Monthly AWS Budget",
      "limit": 50.0,
      "used": 1.11,
      "percentage": 2.2,
      "currency": "USD",
      "status": "healthy",
      "remaining": 48.89
    }
  ],
  "last_updated": "2025-06-21T10:30:00"
}
```

### Get Comprehensive Summary

```bash
curl -X GET "https://flight-tracker-alb-790028972.us-east-1.elb.amazonaws.com/api/v1/costs/summary"
```

## Integration with Frontend

The cost data can be integrated into the frontend interface:

### Header Badge Example
```javascript
// Fetch budget status for header badge
fetch('/api/v1/costs/budget')
  .then(response => response.json())
  .then(data => {
    const status = data.overall_status;
    const percentage = data.budgets[0]?.percentage || 0;
    
    // Update header badge based on status
    updateBudgetBadge(status, percentage);
  });
```

### Settings Panel Example
```javascript
// Comprehensive cost overview for settings
fetch('/api/v1/costs/summary')
  .then(response => response.json())
  .then(data => {
    renderCostDashboard({
      currentSpend: data.current_month.total,
      budgetStatus: data.budget.overall_status,
      monthlyProjection: data.forecast.monthly_projection,
      trend: data.trend
    });
  });
```

## Error Handling

The cost endpoints include comprehensive error handling:

### Service Unavailable (503)
Returned when AWS Cost Explorer access is not configured:

```json
{
  "detail": {
    "error": "AWS Cost Service unavailable",
    "message": "AWS Cost Explorer access not configured or insufficient permissions",
    "required_permissions": [
      "ce:GetCostAndUsage",
      "ce:GetCostForecast"
    ]
  }
}
```

### Permission Errors (500)
Returned when AWS API calls fail due to permissions:

```json
{
  "detail": "Error retrieving current costs: AccessDenied: User is not authorized to perform ce:GetCostAndUsage"
}
```

## Monitoring and Alerts

### CloudWatch Integration
Cost monitoring activities are logged to CloudWatch under `/ecs/flight-tracker`:

- Successful cost retrievals
- Permission errors
- API rate limiting
- Service initialization status

### Rate Limiting
AWS Cost Explorer has API rate limits:
- 100 requests per second per account
- The application includes appropriate error handling for rate limits

## Security Considerations

1. **Least Privilege**: IAM policy grants only necessary Cost Explorer permissions
2. **Read-Only**: All permissions are read-only, no ability to modify costs or budgets
3. **Account Scope**: Permissions are scoped to the current AWS account only
4. **No Sensitive Data**: Cost data is financial metadata, not application secrets

## Troubleshooting

### Cost Service Not Available
- Check IAM permissions are attached to ECS task role
- Verify Cost Explorer is enabled in AWS console
- Check CloudWatch logs for initialization errors

### No Budget Data
- Ensure budgets are created in AWS Cost Management console
- Allow 24 hours for budget data to populate
- Check IAM permissions include `budgets:DescribeBudgets`

### Forecast Errors
- Cost forecasting requires at least 3 days of cost history
- New AWS accounts may not have sufficient data
- API will return graceful errors until data is available

## Cost Implications

The cost monitoring feature itself has minimal cost impact:

- **Cost Explorer API**: Free for up to 1000 requests per month
- **Budgets API**: Free for first 2 budgets per account
- **Additional Requests**: $0.01 per 1000 requests beyond free tier

Typical usage (checking costs a few times per day) will remain within free tiers.