"""Security middleware for Flight Tracker Collector"""
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware with rate limiting and security headers"""
    
    def __init__(self, app, rate_limit_requests: int = 100, rate_limit_window: int = 60):
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window  # seconds
        self.request_counts: Dict[str, List[float]] = defaultdict(list)
        self.security_events: List[Dict] = []
        self.max_security_events = 100  # Keep last 100 events
        
        # CloudFront IP ranges that should be whitelisted for frontend access
        # These are common CloudFront edge server IP ranges
        self.cloudfront_ip_ranges = [
            "107.131.",     # Common CloudFront range
            "13.32.",       # AWS CloudFront
            "13.35.",       # AWS CloudFront
            "18.64.",       # AWS CloudFront
            "52.85.",       # AWS CloudFront
            "54.192.",      # AWS CloudFront
            "54.230.",      # AWS CloudFront
            "54.239.",      # AWS CloudFront
            "99.84.",       # AWS CloudFront
            "204.246.",     # AWS CloudFront
            "205.251.",     # AWS CloudFront
        ]
        
        # Frontend endpoints that need higher rate limits (requests per minute)
        self.frontend_endpoints = {
            "/api/v1/regions": 60,           # Initial load, occasional refresh
            "/api/v1/status": 60,            # Periodic health checks
            "/api/v1/etex/flights": 240,     # Every 3 seconds = 20/min, allow 4x buffer
            "/api/v1/etex/choppers": 240,    # Helicopter tracking, same frequency
            "/api/v1/socal/flights": 240,    # SoCal region if enabled
            "/api/v1/socal/choppers": 240,   # SoCal helicopters
        }
        
        # Suspicious patterns to detect
        self.suspicious_patterns = [
            ".env", ".git", ".aws", "wp-admin", "phpmyadmin", "admin.php",
            "XDEBUG", "phpstorm", "eval(", "base64", "shell_exec",
            "../", "..\\", "%2e%2e", "etc/passwd", "proc/self"
        ]
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, considering proxy headers"""
        # Check X-Forwarded-For header (from ALB)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Use the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection IP
        return request.client.host if request.client else "unknown"
    
    def _is_cloudfront_ip(self, client_ip: str) -> bool:
        """Check if IP address is from CloudFront"""
        return any(client_ip.startswith(prefix) for prefix in self.cloudfront_ip_ranges)
    
    def _get_rate_limit_for_path(self, path: str, is_cloudfront: bool) -> int:
        """Get appropriate rate limit for the path"""
        if is_cloudfront and path in self.frontend_endpoints:
            return self.frontend_endpoints[path]
        return self.rate_limit_requests
    
    def _is_rate_limited(self, client_ip: str, request_path: str) -> bool:
        """Check if client IP is rate limited"""
        now = time.time()
        
        # Determine if this is a CloudFront IP and get appropriate rate limit
        is_cloudfront = self._is_cloudfront_ip(client_ip)
        rate_limit = self._get_rate_limit_for_path(request_path, is_cloudfront)
        
        # Clean old requests outside the window
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if now - req_time < self.rate_limit_window
        ]
        
        # Check if over limit
        if len(self.request_counts[client_ip]) >= rate_limit:
            return True
        
        # Add current request
        self.request_counts[client_ip].append(now)
        return False
    
    def _is_suspicious_request(self, request: Request) -> Optional[str]:
        """Check if request contains suspicious patterns"""
        # Check URL path
        path = request.url.path.lower()
        query = str(request.url.query).lower()
        
        for pattern in self.suspicious_patterns:
            if pattern in path or pattern in query:
                return f"Suspicious pattern detected: {pattern}"
        
        # Check for common vulnerability scanners
        user_agent = request.headers.get("User-Agent", "").lower()
        if any(scanner in user_agent for scanner in ["nikto", "sqlmap", "nmap", "masscan"]):
            return f"Vulnerability scanner detected: {user_agent}"
        
        return None
    
    def _log_security_event(self, event_type: str, client_ip: str, details: Dict):
        """Log security event for monitoring"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "client_ip": client_ip,
            "details": details
        }
        
        self.security_events.append(event)
        
        # Keep only recent events
        if len(self.security_events) > self.max_security_events:
            self.security_events = self.security_events[-self.max_security_events:]
        
        logger.warning(f"Security event: {event_type} from {client_ip} - {details}")
    
    def get_security_events(self, limit: int = 10) -> List[Dict]:
        """Get recent security events for status endpoint"""
        return self.security_events[-limit:]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with security checks"""
        client_ip = self._get_client_ip(request)
        is_cloudfront = self._is_cloudfront_ip(client_ip)
        
        # Log CloudFront detection for debugging (all API requests for now)
        if request.url.path.startswith("/api/v1/"):
            rate_limit = self._get_rate_limit_for_path(request.url.path, is_cloudfront)
            logger.info(f"API request: {client_ip} -> {request.url.path} (CloudFront: {is_cloudfront}, rate limit: {rate_limit}/min)")
        
        # Skip rate limiting for health checks from internal AWS IPs
        if request.url.path == "/health" and client_ip.startswith(("172.", "10.")):
            response = await call_next(request)
            return self._add_security_headers(response)
        
        # Check rate limiting
        if self._is_rate_limited(client_ip, request.url.path):
            is_cloudfront = self._is_cloudfront_ip(client_ip)
            rate_limit = self._get_rate_limit_for_path(request.url.path, is_cloudfront)
            
            self._log_security_event(
                "rate_limit_exceeded",
                client_ip,
                {
                    "path": request.url.path, 
                    "method": request.method,
                    "is_cloudfront": is_cloudfront,
                    "rate_limit_used": rate_limit,
                    "user_agent": request.headers.get("User-Agent", "")[:100]
                }
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(self.rate_limit_window)}
            )
        
        # Check for suspicious requests
        suspicious_reason = self._is_suspicious_request(request)
        if suspicious_reason:
            self._log_security_event(
                "suspicious_request",
                client_ip,
                {
                    "path": request.url.path,
                    "method": request.method,
                    "reason": suspicious_reason,
                    "user_agent": request.headers.get("User-Agent", "")
                }
            )
            
            # Return 404 for suspicious requests to not reveal information
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        return self._add_security_headers(response)
    
    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; img-src 'self' data: fastapi.tiangolo.com"
        
        # Remove server header if present
        if "Server" in response.headers:
            del response.headers["Server"]
        
        return response


class CloudWatchAlarmsService:
    """Service to fetch CloudWatch alarms"""
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize CloudWatch client"""
        try:
            import boto3
            self.client = boto3.client('cloudwatch', region_name='us-east-1')
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
    
    def get_recent_alarms(self, limit: int = 10) -> List[Dict]:
        """Get recent CloudWatch alarms"""
        # Temporarily disabled - ECS task role lacks CloudWatch permissions
        # This prevents log spam while we focus on blending logic
        return []
        
        # TODO: Add CloudWatch permissions to ECS task role to re-enable
        # Required permissions: cloudwatch:DescribeAlarmHistory
        if not self.client:
            return []
        
        try:
            # Get alarm history for the last 24 hours
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            
            # First get all alarm names, then filter for flight-tracker related ones
            response = self.client.describe_alarm_history(
                StartDate=start_time,
                EndDate=end_time,
                MaxRecords=limit * 2  # Get more to filter
            )
            
            alarms = []
            for item in response.get('AlarmHistoryItems', []):
                # Filter for flight-tracker related alarms
                alarm_name = item['AlarmName']
                if 'flight-tracker' in alarm_name.lower() or 'flight_tracker' in alarm_name.lower():
                    alarm = {
                        "timestamp": item['Timestamp'].isoformat(),
                        "alarm_name": alarm_name,
                        "state": item['HistorySummary'],
                        "reason": item.get('HistoryData', '')
                    }
                    alarms.append(alarm)
                    
                    # Limit to requested number
                    if len(alarms) >= limit:
                        break
            
            return alarms
            
        except Exception as e:
            logger.error(f"Error fetching CloudWatch alarms: {e}")
            return []