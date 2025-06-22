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
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client IP is rate limited"""
        now = time.time()
        
        # Clean old requests outside the window
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if now - req_time < self.rate_limit_window
        ]
        
        # Check if over limit
        if len(self.request_counts[client_ip]) >= self.rate_limit_requests:
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
        
        # Skip rate limiting for health checks and internal AWS IPs
        if request.url.path in ["/health", "/api/v1/status"] and client_ip.startswith(("172.", "10.")):
            response = await call_next(request)
            return self._add_security_headers(response)
        
        # Check rate limiting
        if self._is_rate_limited(client_ip):
            self._log_security_event(
                "rate_limit_exceeded",
                client_ip,
                {"path": request.url.path, "method": request.method}
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
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        
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
        if not self.client:
            return []
        
        try:
            # Get alarm history for the last 24 hours
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            
            response = self.client.describe_alarm_history(
                AlarmNamePrefix='flight-tracker',
                StartDate=start_time,
                EndDate=end_time,
                MaxRecords=limit
            )
            
            alarms = []
            for item in response.get('AlarmHistoryItems', []):
                alarm = {
                    "timestamp": item['Timestamp'].isoformat(),
                    "alarm_name": item['AlarmName'],
                    "state": item['HistorySummary'],
                    "reason": item.get('HistoryData', {})
                }
                alarms.append(alarm)
            
            return alarms
            
        except Exception as e:
            logger.error(f"Error fetching CloudWatch alarms: {e}")
            return []