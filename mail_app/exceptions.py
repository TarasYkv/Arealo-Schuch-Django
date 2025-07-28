"""
Custom exception handlers for Mail App
"""
import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from .services.exceptions import (
    TokenRefreshError,
    ReAuthorizationRequiredError,
    EmailSyncError,
    ZohoAPIError,
    RateLimitExceededError,
    AuthenticationError
)

logger = logging.getLogger(__name__)


def handle_mail_app_exception(request, exception):
    """
    Central exception handler for mail app errors.
    
    Args:
        request: HTTP request object
        exception: Exception instance
        
    Returns:
        JsonResponse for AJAX requests, rendered page for regular requests
    """
    logger.error(f"Mail app exception: {type(exception).__name__}: {exception}")
    
    # Determine if this is an AJAX request
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Content-Type') == 'application/json' or
        'application/json' in request.headers.get('Accept', '')
    )
    
    # Handle specific exception types
    if isinstance(exception, ReAuthorizationRequiredError):
        return handle_reauth_required(request, exception, is_ajax)
    elif isinstance(exception, TokenRefreshError):
        return handle_token_error(request, exception, is_ajax)
    elif isinstance(exception, RateLimitExceededError):
        return handle_rate_limit(request, exception, is_ajax)
    elif isinstance(exception, AuthenticationError):
        return handle_auth_error(request, exception, is_ajax)
    elif isinstance(exception, EmailSyncError):
        return handle_sync_error(request, exception, is_ajax)
    elif isinstance(exception, ZohoAPIError):
        return handle_api_error(request, exception, is_ajax)
    elif isinstance(exception, PermissionDenied):
        return handle_permission_denied(request, exception, is_ajax)
    else:
        return handle_generic_error(request, exception, is_ajax)


def handle_reauth_required(request, exception, is_ajax):
    """Handle re-authorization required errors."""
    message = "Email-Account Autorisierung abgelaufen. Bitte verbinden Sie Ihr Konto erneut."
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'reauth_required',
            'message': message,
            'redirect_url': '/mail/'
        }, status=401)
    else:
        from django.contrib import messages
        messages.error(request, message)
        from django.shortcuts import redirect
        return redirect('mail_app:dashboard')


def handle_token_error(request, exception, is_ajax):
    """Handle token refresh errors."""
    message = "Token-Fehler. Bitte versuchen Sie es erneut oder verbinden Sie Ihr Konto neu."
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'token_error',
            'message': message
        }, status=500)
    else:
        from django.contrib import messages
        messages.error(request, message)
        from django.shortcuts import redirect
        return redirect('mail_app:dashboard')


def handle_rate_limit(request, exception, is_ajax):
    """Handle rate limit exceeded errors."""
    message = "Zu viele Anfragen. Bitte warten Sie einen Moment und versuchen Sie es erneut."
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'rate_limit',
            'message': message,
            'retry_after': 60
        }, status=429)
    else:
        from django.contrib import messages
        messages.warning(request, message)
        return render(request, 'mail_app/error.html', {
            'error_type': 'Rate Limit',
            'error_message': message,
            'retry_after': 60
        }, status=429)


def handle_auth_error(request, exception, is_ajax):
    """Handle authentication errors."""
    message = "Authentifizierungsfehler. Bitte melden Sie sich erneut an."
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'auth_error',
            'message': message
        }, status=403)
    else:
        from django.contrib import messages
        messages.error(request, message)
        from django.shortcuts import redirect
        return redirect('accounts:login')


def handle_sync_error(request, exception, is_ajax):
    """Handle email synchronization errors."""
    message = f"Email-Synchronisation fehlgeschlagen: {exception}"
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'sync_error',
            'message': str(exception)
        }, status=500)
    else:
        from django.contrib import messages
        messages.error(request, message)
        return render(request, 'mail_app/error.html', {
            'error_type': 'Synchronisation Fehler',
            'error_message': str(exception)
        }, status=500)


def handle_api_error(request, exception, is_ajax):
    """Handle Zoho API errors."""
    message = f"API-Fehler: {exception}"
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'api_error',
            'message': str(exception),
            'status_code': getattr(exception, 'status_code', None)
        }, status=500)
    else:
        from django.contrib import messages
        messages.error(request, message)
        return render(request, 'mail_app/error.html', {
            'error_type': 'API Fehler',
            'error_message': str(exception),
            'status_code': getattr(exception, 'status_code', None)
        }, status=500)


def handle_permission_denied(request, exception, is_ajax):
    """Handle permission denied errors."""
    message = "Sie haben keine Berechtigung für diese Aktion."
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'permission_denied',
            'message': message
        }, status=403)
    else:
        from django.contrib import messages
        messages.error(request, message)
        return render(request, 'mail_app/error.html', {
            'error_type': 'Berechtigung verweigert',
            'error_message': message
        }, status=403)


def handle_generic_error(request, exception, is_ajax):
    """Handle generic errors."""
    message = "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut."
    
    if is_ajax:
        return JsonResponse({
            'success': False,
            'error': 'generic_error',
            'message': message
        }, status=500)
    else:
        from django.contrib import messages
        messages.error(request, message)
        return render(request, 'mail_app/error.html', {
            'error_type': 'Unerwarteter Fehler',
            'error_message': str(exception)
        }, status=500)


class MailAppExceptionMiddleware:
    """
    Middleware to catch and handle mail app exceptions.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """Process exceptions for mail app views."""
        # Only handle exceptions for mail app URLs
        if not request.path.startswith('/mail/'):
            return None
        
        # Handle known mail app exceptions
        if isinstance(exception, (
            TokenRefreshError,
            ReAuthorizationRequiredError,
            EmailSyncError,
            ZohoAPIError,
            RateLimitExceededError,
            AuthenticationError
        )):
            return handle_mail_app_exception(request, exception)
        
        # Let other exceptions be handled normally
        return None


def mail_app_error_context(request):
    """Context processor for mail app error handling."""
    return {
        'mail_app_error_handler': handle_mail_app_exception
    }