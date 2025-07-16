import time
from django.http import JsonResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware
    """
    
    def __init__(self, get_response=None):
        self.get_response = get_response
        
        # Rate limit settings
        self.RATE_LIMITS = {
            '/chat/messages/': (60, 60),  # 60 requests per minute
            '/chat/send_message/': (30, 60),  # 30 messages per minute
            '/chat/api/room/': (100, 60),  # 100 API calls per minute
            '/chat/get-agora-token/': (10, 60),  # 10 token requests per minute
        }
        
        # Global rate limit for all endpoints
        self.GLOBAL_RATE_LIMIT = (200, 60)  # 200 requests per minute per IP
        
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Check rate limits before processing request
        """
        if not self._should_rate_limit(request):
            return None
            
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check global rate limit
        if self._is_rate_limited(f"global:{client_ip}", *self.GLOBAL_RATE_LIMIT):
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': 60
            }, status=429)
        
        # Check endpoint-specific rate limit
        endpoint = self._get_endpoint_key(request.path)
        if endpoint in self.RATE_LIMITS:
            limit, window = self.RATE_LIMITS[endpoint]
            key = f"{endpoint}:{client_ip}"
            
            if request.user.is_authenticated:
                key = f"{endpoint}:user:{request.user.id}"
            
            if self._is_rate_limited(key, limit, window):
                return JsonResponse({
                    'error': f'Rate limit exceeded for this endpoint. Limit: {limit} requests per {window} seconds.',
                    'retry_after': window
                }, status=429)
        
        return None
    
    def _should_rate_limit(self, request):
        """
        Determine if request should be rate limited
        """
        # Skip rate limiting for superusers
        if request.user.is_authenticated and request.user.is_superuser:
            return False
            
        # Skip rate limiting for static files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return False
            
        # Only rate limit AJAX requests and API endpoints
        return (request.path.startswith('/chat/') and 
                (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                 request.path.startswith('/chat/api/')))
    
    def _get_client_ip(self, request):
        """
        Get client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_endpoint_key(self, path):
        """
        Get endpoint key for rate limiting
        """
        # Match exact paths or patterns
        for endpoint in self.RATE_LIMITS.keys():
            if path.startswith(endpoint):
                return endpoint
        return path
    
    def _is_rate_limited(self, key, limit, window):
        """
        Check if key is rate limited
        """
        try:
            # Get current count
            current_count = cache.get(key, 0)
            
            if current_count >= limit:
                return True
            
            # Increment count
            cache.set(key, current_count + 1, window)
            return False
            
        except Exception:
            # If cache fails, don't rate limit
            return False


class ChatRateLimitMiddleware(MiddlewareMixin):
    """
    Specialized rate limiting for chat-specific actions
    """
    
    def process_request(self, request):
        """
        Additional rate limiting for chat actions
        """
        if not request.user.is_authenticated:
            return None
            
        user_id = request.user.id
        
        # Rate limit message sending
        if request.path == '/chat/send_message/' and request.method == 'POST':
            key = f"send_message:user:{user_id}"
            if self._is_rate_limited(key, 20, 60):  # 20 messages per minute
                return JsonResponse({
                    'error': 'Sie senden zu viele Nachrichten. Bitte warten Sie einen Moment.',
                    'retry_after': 60
                }, status=429)
        
        # Rate limit call initiation
        if '/call/initiate/' in request.path and request.method == 'POST':
            key = f"call_initiate:user:{user_id}"
            if self._is_rate_limited(key, 5, 300):  # 5 calls per 5 minutes
                return JsonResponse({
                    'error': 'Sie haben zu viele Anrufe gestartet. Bitte warten Sie 5 Minuten.',
                    'retry_after': 300
                }, status=429)
        
        # Rate limit file uploads
        if request.path == '/chat/upload/' and request.method == 'POST':
            key = f"file_upload:user:{user_id}"
            if self._is_rate_limited(key, 10, 60):  # 10 uploads per minute
                return JsonResponse({
                    'error': 'Sie haben zu viele Dateien hochgeladen. Bitte warten Sie einen Moment.',
                    'retry_after': 60
                }, status=429)
        
        return None
    
    def _is_rate_limited(self, key, limit, window):
        """
        Check if key is rate limited using simple counter
        """
        try:
            current_count = cache.get(key, 0)
            
            if current_count >= limit:
                return True
            
            cache.set(key, current_count + 1, window)
            return False
            
        except Exception:
            return False