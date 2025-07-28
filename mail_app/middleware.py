"""
Mail App Middleware - Error Handling and Request Processing
"""
import logging
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, IntegrityError
from .services.exceptions import TokenRefreshError, ReAuthorizationRequiredError

logger = logging.getLogger(__name__)


class MailAppErrorHandlingMiddleware:
    """
    Middleware for handling mail app specific errors and providing
    consistent error responses across the application.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """Handle exceptions specific to mail app"""
        
        # Only handle mail app requests
        if not request.path.startswith('/mail/'):
            return None
            
        logger.error(f"Mail app exception: {type(exception).__name__}: {str(exception)}", 
                    exc_info=True, extra={'request': request})
        
        # Determine if this is an API request
        is_api_request = (
            request.path.startswith('/mail/api/') or 
            request.headers.get('Accept', '').startswith('application/json') or
            request.headers.get('Content-Type', '').startswith('application/json')
        )
        
        # Handle OAuth/Authentication errors
        if isinstance(exception, (TokenRefreshError, ReAuthorizationRequiredError)):
            return self._handle_auth_error(request, exception, is_api_request)
            
        # Handle database errors
        if isinstance(exception, (DatabaseError, IntegrityError)):
            return self._handle_database_error(request, exception, is_api_request)
            
        # Handle permission errors
        if isinstance(exception, PermissionDenied):
            return self._handle_permission_error(request, exception, is_api_request)
            
        # Handle general exceptions in production
        if not settings.DEBUG:
            return self._handle_general_error(request, exception, is_api_request)
            
        # Let Django handle the exception in debug mode
        return None

    def _handle_auth_error(self, request, exception, is_api_request):
        """Handle OAuth and authentication related errors"""
        error_data = {
            'error': 'authentication_required',
            'message': 'Email account requires re-authentication',
            'redirect_url': '/mail/auth/authorize/',
            'details': str(exception)
        }
        
        if is_api_request:
            return JsonResponse(error_data, status=401)
        else:
            # Redirect to auth page for web requests
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.error(request, 'Ihr Email-Account muss neu authentifiziert werden.')
            return redirect('mail_app:oauth_authorize')

    def _handle_database_error(self, request, exception, is_api_request):
        """Handle database related errors"""
        error_data = {
            'error': 'database_error',
            'message': 'Ein Datenbankfehler ist aufgetreten',
            'details': str(exception) if settings.DEBUG else 'Database operation failed'
        }
        
        if is_api_request:
            return JsonResponse(error_data, status=500)
        else:
            return render(request, 'mail_app/error.html', {
                'error_title': 'Datenbankfehler',
                'error_message': 'Es gab ein Problem beim Zugriff auf die Datenbank. Bitte versuchen Sie es später erneut.',
                'show_details': settings.DEBUG,
                'error_details': str(exception) if settings.DEBUG else None
            }, status=500)

    def _handle_permission_error(self, request, exception, is_api_request):
        """Handle permission denied errors"""
        error_data = {
            'error': 'permission_denied',
            'message': 'Sie haben keine Berechtigung für diese Aktion',
            'details': str(exception)
        }
        
        if is_api_request:
            return JsonResponse(error_data, status=403)
        else:
            return render(request, 'mail_app/error.html', {
                'error_title': 'Zugriff verweigert',
                'error_message': 'Sie haben keine Berechtigung für diese Seite oder Aktion.',
                'show_details': False
            }, status=403)

    def _handle_general_error(self, request, exception, is_api_request):
        """Handle general exceptions in production"""
        error_data = {
            'error': 'internal_server_error',
            'message': 'Ein unerwarteter Fehler ist aufgetreten',
            'details': 'Internal server error'
        }
        
        if is_api_request:
            return JsonResponse(error_data, status=500)
        else:
            return render(request, 'mail_app/error.html', {
                'error_title': 'Unerwarteter Fehler',
                'error_message': 'Es ist ein unerwarteter Fehler aufgetreten. Bitte versuchen Sie es später erneut.',
                'show_details': False
            }, status=500)


class RequestLoggingMiddleware:
    """
    Middleware for logging mail app requests for debugging and monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only log mail app requests
        if request.path.startswith('/mail/'):
            start_time = logger.info(f"Mail request started: {request.method} {request.path}")
            
        response = self.get_response(request)
        
        if request.path.startswith('/mail/'):
            logger.info(f"Mail request completed: {request.method} {request.path} - Status: {response.status_code}")
            
        return response


class RateLimitingMiddleware:
    """
    Simple rate limiting for mail app API endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_counts = {}  # In production, use Redis or database
        self.rate_limit = 100  # requests per minute
        self.time_window = 60  # seconds

    def __call__(self, request):
        # Only apply to API endpoints
        if request.path.startswith('/mail/api/'):
            if not self._check_rate_limit(request):
                return JsonResponse({
                    'error': 'rate_limit_exceeded',
                    'message': 'Zu viele Anfragen. Bitte versuchen Sie es später erneut.'
                }, status=429)
                
        return self.get_response(request)

    def _check_rate_limit(self, request):
        """Simple in-memory rate limiting (use Redis in production)"""
        import time
        
        # Get client identifier (IP address + user ID if authenticated)
        client_id = request.META.get('REMOTE_ADDR', 'unknown')
        if hasattr(request, 'user') and request.user.is_authenticated:
            client_id += f"_{request.user.id}"
            
        current_time = time.time()
        
        # Clean old entries
        self.request_counts = {
            k: v for k, v in self.request_counts.items() 
            if current_time - v['last_request'] < self.time_window
        }
        
        # Check current client
        if client_id in self.request_counts:
            client_data = self.request_counts[client_id]
            if current_time - client_data['first_request'] < self.time_window:
                if client_data['count'] >= self.rate_limit:
                    return False
                client_data['count'] += 1
                client_data['last_request'] = current_time
            else:
                # Reset window
                self.request_counts[client_id] = {
                    'count': 1,
                    'first_request': current_time,
                    'last_request': current_time
                }
        else:
            self.request_counts[client_id] = {
                'count': 1,
                'first_request': current_time,
                'last_request': current_time
            }
            
        return True