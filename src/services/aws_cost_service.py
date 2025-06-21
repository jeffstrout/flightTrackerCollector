"""
AWS Cost Explorer Service for Flight Tracker Collector

Provides AWS cost monitoring capabilities including:
- Current month cost retrieval
- Daily cost breakdown
- Budget status monitoring  
- Cost forecasting
"""

import boto3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


class AWSCostService:
    """Service for retrieving AWS cost and billing information"""
    
    def __init__(self):
        """Initialize AWS Cost Explorer and Budgets clients"""
        try:
            self.ce_client = boto3.client('ce', region_name='us-east-1')
            self.budgets_client = boto3.client('budgets', region_name='us-east-1')
            self.account_id = boto3.client('sts').get_caller_identity()['Account']
            logger.info("AWS Cost Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AWS Cost Service: {e}")
            raise
    
    def _get_date_range_current_month(self) -> tuple:
        """Get start and end dates for current month"""
        now = datetime.now()
        start_date = now.replace(day=1).strftime('%Y-%m-%d')
        
        # End date is today (for current costs) or end of month for forecasting
        end_date = now.strftime('%Y-%m-%d')
        
        return start_date, end_date
    
    def _decimal_to_float(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._decimal_to_float(v) for v in obj]
        return obj
    
    def get_current_month_costs(self) -> Dict:
        """Get current month's AWS costs with service breakdown"""
        try:
            start_date, end_date = self._get_date_range_current_month()
            
            # Get cost and usage data
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'SERVICE'
                    }
                ]
            )
            
            total_cost = 0.0
            service_costs = {}
            
            if response['ResultsByTime']:
                for group in response['ResultsByTime'][0]['Groups']:
                    service_name = group['Keys'][0]
                    cost_amount = float(group['Metrics']['BlendedCost']['Amount'])
                    
                    # Only include services with meaningful costs (> $0.001)
                    if cost_amount > 0.001:
                        service_costs[service_name] = round(cost_amount, 3)
                        total_cost += cost_amount
            
            # Get currency from the response
            currency = 'USD'
            if response['ResultsByTime'] and response['ResultsByTime'][0]['Groups']:
                currency = response['ResultsByTime'][0]['Groups'][0]['Metrics']['BlendedCost']['Unit']
            
            result = {
                'total': round(total_cost, 2),
                'currency': currency,
                'period': f"{start_date} to {end_date}",
                'breakdown': service_costs,
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved current month costs: ${total_cost:.2f}")
            return self._decimal_to_float(result)
            
        except Exception as e:
            logger.error(f"Error retrieving current month costs: {e}")
            raise
    
    def get_daily_costs(self, days_back: int = 30) -> Dict:
        """Get daily cost breakdown for the last N days"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost']
            )
            
            daily_costs = []
            total_period_cost = 0.0
            
            for result in response['ResultsByTime']:
                date_str = result['TimePeriod']['Start']
                cost_amount = float(result['Total']['BlendedCost']['Amount'])
                
                daily_costs.append({
                    'date': date_str,
                    'cost': round(cost_amount, 3)
                })
                total_period_cost += cost_amount
            
            # Calculate average daily cost
            avg_daily_cost = total_period_cost / len(daily_costs) if daily_costs else 0
            
            result = {
                'daily_costs': daily_costs,
                'total_period_cost': round(total_period_cost, 2),
                'average_daily_cost': round(avg_daily_cost, 3),
                'period_days': days_back,
                'currency': 'USD',
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved {len(daily_costs)} days of cost data")
            return self._decimal_to_float(result)
            
        except Exception as e:
            logger.error(f"Error retrieving daily costs: {e}")
            raise
    
    def get_budget_status(self) -> Dict:
        """Get budget information and status"""
        try:
            # List all budgets for the account
            response = self.budgets_client.describe_budgets(
                AccountId=self.account_id
            )
            
            if not response['Budgets']:
                return {
                    'status': 'no_budget',
                    'message': 'No budgets configured for this account',
                    'budgets': []
                }
            
            budget_info = []
            overall_status = 'healthy'
            
            for budget in response['Budgets']:
                budget_name = budget['BudgetName']
                budget_limit = float(budget['BudgetLimit']['Amount'])
                currency = budget['BudgetLimit']['Unit']
                
                # Get actual spending for this budget
                try:
                    actual_response = self.budgets_client.describe_budget(
                        AccountId=self.account_id,
                        BudgetName=budget_name
                    )
                    
                    actual_spend = 0.0
                    if 'CalculatedSpend' in actual_response['Budget']:
                        actual_spend = float(
                            actual_response['Budget']['CalculatedSpend']['ActualSpend']['Amount']
                        )
                    
                    # Calculate percentage used
                    percentage_used = (actual_spend / budget_limit * 100) if budget_limit > 0 else 0
                    
                    # Determine status
                    if percentage_used >= 90:
                        status = 'critical'
                        overall_status = 'critical'
                    elif percentage_used >= 75:
                        status = 'warning'
                        if overall_status == 'healthy':
                            overall_status = 'warning'
                    else:
                        status = 'healthy'
                    
                    budget_info.append({
                        'name': budget_name,
                        'limit': budget_limit,
                        'used': round(actual_spend, 2),
                        'percentage': round(percentage_used, 1),
                        'currency': currency,
                        'status': status,
                        'remaining': round(budget_limit - actual_spend, 2)
                    })
                    
                except Exception as budget_error:
                    logger.warning(f"Could not get details for budget {budget_name}: {budget_error}")
                    budget_info.append({
                        'name': budget_name,
                        'limit': budget_limit,
                        'currency': currency,
                        'status': 'unknown',
                        'error': str(budget_error)
                    })
            
            result = {
                'overall_status': overall_status,
                'budget_count': len(budget_info),
                'budgets': budget_info,
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved budget status for {len(budget_info)} budgets")
            return self._decimal_to_float(result)
            
        except Exception as e:
            logger.error(f"Error retrieving budget status: {e}")
            # Return a graceful fallback
            return {
                'status': 'error',
                'message': f'Could not retrieve budget information: {str(e)}',
                'budgets': [],
                'last_updated': datetime.now().isoformat()
            }
    
    def get_cost_forecast(self, days_ahead: int = 30) -> Dict:
        """Get cost forecast for the next N days"""
        try:
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days_ahead)
            
            response = self.ce_client.get_cost_forecast(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Metric='BLENDED_COST',
                Granularity='MONTHLY'
            )
            
            forecast_amount = 0.0
            confidence_level = 'UNKNOWN'
            
            if response['Total']:
                forecast_amount = float(response['Total']['Amount'])
                confidence_level = response.get('ForecastResultsByTime', [{}])[0].get('MeanValue', 'UNKNOWN')
            
            # Calculate daily average from forecast
            daily_forecast = forecast_amount / days_ahead if days_ahead > 0 else 0
            
            # Get current month actual costs for comparison
            current_month_data = self.get_current_month_costs()
            current_month_total = current_month_data.get('total', 0)
            
            # Calculate monthly projection based on current spending pattern
            now = datetime.now()
            days_in_month = (now.replace(month=now.month+1, day=1) - timedelta(days=1)).day
            days_elapsed = now.day
            
            monthly_projection = 0
            if days_elapsed > 0:
                monthly_projection = (current_month_total / days_elapsed) * days_in_month
            
            result = {
                'forecast_amount': round(forecast_amount, 2),
                'forecast_period_days': days_ahead,
                'daily_forecast': round(daily_forecast, 3),
                'monthly_projection': round(monthly_projection, 2),
                'current_month_actual': current_month_total,
                'confidence_level': confidence_level,
                'currency': 'USD',
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"Generated cost forecast: ${forecast_amount:.2f} for {days_ahead} days")
            return self._decimal_to_float(result)
            
        except Exception as e:
            logger.error(f"Error generating cost forecast: {e}")
            raise
    
    def get_comprehensive_cost_summary(self) -> Dict:
        """Get a comprehensive cost summary including all metrics"""
        try:
            current_costs = self.get_current_month_costs()
            budget_status = self.get_budget_status()
            forecast = self.get_cost_forecast()
            daily_costs = self.get_daily_costs(7)  # Last 7 days
            
            # Calculate trend from daily costs
            trend = 'stable'
            if len(daily_costs['daily_costs']) >= 2:
                recent_avg = sum(d['cost'] for d in daily_costs['daily_costs'][-3:]) / 3
                earlier_avg = sum(d['cost'] for d in daily_costs['daily_costs'][:3]) / 3
                
                if recent_avg > earlier_avg * 1.1:
                    trend = 'increasing'
                elif recent_avg < earlier_avg * 0.9:
                    trend = 'decreasing'
            
            return {
                'current_month': current_costs,
                'budget': budget_status,
                'forecast': forecast,
                'recent_daily': daily_costs,
                'trend': trend,
                'summary': {
                    'status': budget_status.get('overall_status', 'unknown'),
                    'current_spend': current_costs.get('total', 0),
                    'monthly_projection': forecast.get('monthly_projection', 0),
                    'days_remaining_in_month': self._days_remaining_in_month(),
                    'last_updated': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive cost summary: {e}")
            raise
    
    def _days_remaining_in_month(self) -> int:
        """Calculate days remaining in current month"""
        now = datetime.now()
        next_month = now.replace(month=now.month+1, day=1) if now.month < 12 else now.replace(year=now.year+1, month=1, day=1)
        last_day = next_month - timedelta(days=1)
        return (last_day - now).days + 1