"""
Mail App Error Handlers - Standardized error response system
"""
import logging
from typing import Dict, Any, Optional
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Enumeration of standard error types"""
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND_ERROR = "not_found_error"
    DATABASE_ERROR = "database_error"
    EXTERNAL_API_ERROR = "external_api_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_SERVER_ERROR = "internal_server_error"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MailAppError(Exception):
    """Base exception class for mail app specific errors"""
    
    def __init__(
        self, 
        message: str,
        error_type: ErrorType = ErrorType.INTERNAL_SERVER_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[str] = None,
        user_message: Optional[str] = None,
        recovery_suggestions: Optional[list] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.details = details
        self.user_message = user_message or self._get_default_user_message()
        self.recovery_suggestions = recovery_suggestions or []
    
    def _get_default_user_message(self) -> str:
        """Get default user-friendly message based on error type"""
        messages = {
            ErrorType.AUTHENTICATION_ERROR: "Authentifizierung erforderlich. Bitte melden Sie sich erneut an.",
            ErrorType.AUTHORIZATION_ERROR: "Sie haben keine Berechtigung für diese Aktion.",
            ErrorType.VALIDATION_ERROR: "Die eingegebenen Daten sind ungültig.",
            ErrorType.NOT_FOUND_ERROR: "Die angeforderte Ressource wurde nicht gefunden.",
            ErrorType.DATABASE_ERROR: "Ein Datenbankfehler ist aufgetreten.",
            ErrorType.EXTERNAL_API_ERROR: "Fehler beim Zugriff auf externe Dienste.",
            ErrorType.RATE_LIMIT_ERROR: "Zu viele Anfragen. Bitte versuchen Sie es später erneut.",
            ErrorType.CONFIGURATION_ERROR: "Konfigurationsfehler. Bitte kontaktieren Sie den Administrator.",
            ErrorType.INTERNAL_SERVER_ERROR: "Ein unerwarteter Serverfehler ist aufgetreten."
        }
        return messages.get(self.error_type, "Ein unbekannter Fehler ist aufgetreten.")


class ErrorResponseBuilder:
    """Builder class for creating standardized error responses"""
    
    @staticmethod
    def build_response(
        error: MailAppError,
        request,
        include_debug_info: bool = None
    ):
        """Build appropriate error response based on request type"""
        
        if include_debug_info is None:
            include_debug_info = settings.DEBUG
            
        # Determine if this is an API request
        is_api_request = ErrorResponseBuilder._is_api_request(request)
        
        if is_api_request:
            return ErrorResponseBuilder._build_json_response(error, include_debug_info)
        else:
            return ErrorResponseBuilder._build_html_response(error, request, include_debug_info)
    
    @staticmethod
    def _is_api_request(request) -> bool:
        """Determine if request expects JSON response"""
        return (
            request.path.startswith('/mail/api/') or
            'application/json' in request.headers.get('Accept', '') or
            'application/json' in request.headers.get('Content-Type', '')
        )
    
    @staticmethod
    def _build_json_response(error: MailAppError, include_debug_info: bool) -> JsonResponse:
        """Build JSON error response for API requests"""
        response_data = {
            'success': False,
            'error': {
                'type': error.error_type.value,
                'message': error.user_message,
                'severity': error.severity.value,
                'recovery_suggestions': error.recovery_suggestions
            }
        }
        
        if include_debug_info:
            response_data['error']['debug'] = {
                'details': error.details,
                'technical_message': error.message
            }
        
        # Determine HTTP status code
        status_code = ErrorResponseBuilder._get_http_status_code(error.error_type)
        
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def _build_html_response(error: MailAppError, request, include_debug_info: bool):
        """Build HTML error response for web requests"""
        context = {
            'error_title': ErrorResponseBuilder._get_error_title(error.error_type),
            'error_message': error.user_message,
            'show_details': include_debug_info,
            'error_details': error.details if include_debug_info else None,
            'recovery_suggestions': error.recovery_suggestions,
            'error_type': error.error_type.value,
            'severity': error.severity.value
        }
        
        # Add auto-refresh for temporary errors
        if error.error_type in [ErrorType.EXTERNAL_API_ERROR, ErrorType.DATABASE_ERROR]:
            context['auto_refresh_seconds'] = 30
        
        status_code = ErrorResponseBuilder._get_http_status_code(error.error_type)
        
        return render(request, 'mail_app/error.html', context, status=status_code)
    
    @staticmethod
    def _get_http_status_code(error_type: ErrorType) -> int:
        """Get appropriate HTTP status code for error type"""
        status_codes = {
            ErrorType.AUTHENTICATION_ERROR: 401,
            ErrorType.AUTHORIZATION_ERROR: 403,
            ErrorType.VALIDATION_ERROR: 400,
            ErrorType.NOT_FOUND_ERROR: 404,
            ErrorType.DATABASE_ERROR: 500,
            ErrorType.EXTERNAL_API_ERROR: 502,
            ErrorType.RATE_LIMIT_ERROR: 429,
            ErrorType.CONFIGURATION_ERROR: 500,
            ErrorType.INTERNAL_SERVER_ERROR: 500
        }
        return status_codes.get(error_type, 500)
    
    @staticmethod
    def _get_error_title(error_type: ErrorType) -> str:
        """Get user-friendly error title"""
        titles = {
            ErrorType.AUTHENTICATION_ERROR: "Authentifizierung erforderlich",
            ErrorType.AUTHORIZATION_ERROR: "Zugriff verweigert",
            ErrorType.VALIDATION_ERROR: "Ungültige Eingabe",
            ErrorType.NOT_FOUND_ERROR: "Nicht gefunden",
            ErrorType.DATABASE_ERROR: "Datenbankfehler",
            ErrorType.EXTERNAL_API_ERROR: "Externer Dienst nicht verfügbar",
            ErrorType.RATE_LIMIT_ERROR: "Zu viele Anfragen",
            ErrorType.CONFIGURATION_ERROR: "Konfigurationsfehler",
            ErrorType.INTERNAL_SERVER_ERROR: "Serverfehler"
        }
        return titles.get(error_type, "Unbekannter Fehler")


class ErrorLogger:
    """Centralized error logging with context"""
    
    @staticmethod
    def log_error(
        error: MailAppError,
        request=None,
        additional_context: Dict[str, Any] = None
    ):
        """Log error with appropriate level and context"""
        
        # Determine log level based on severity
        log_levels = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        
        log_level = log_levels.get(error.severity, logging.ERROR)
        
        # Build log context
        context = {
            'error_type': error.error_type.value,
            'severity': error.severity.value,
            'user_message': error.user_message,
        }
        
        if request:
            context.update({
                'path': request.path,
                'method': request.method,
                'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
                'ip': request.META.get('REMOTE_ADDR', 'Unknown'),
                'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown')
            })
        
        if additional_context:
            context.update(additional_context)
        
        # Log the error
        logger.log(
            log_level,
            f"Mail App Error: {error.message}",
            extra={'context': context},
            exc_info=error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
        )


# Convenience functions for common error types
def authentication_required(message: str = None, details: str = None) -> MailAppError:
    """Create authentication error"""
    return MailAppError(
        message=message or "Authentication required",
        error_type=ErrorType.AUTHENTICATION_ERROR,
        severity=ErrorSeverity.MEDIUM,
        details=details,
        recovery_suggestions=[
            "Melden Sie sich erneut an",
            "Überprüfen Sie Ihre Email-Kontokonfiguration",
            "Kontaktieren Sie den Administrator bei anhaltenden Problemen"
        ]
    )

def permission_denied(message: str = None, details: str = None) -> MailAppError:
    """Create permission denied error"""
    return MailAppError(
        message=message or "Permission denied",
        error_type=ErrorType.AUTHORIZATION_ERROR,
        severity=ErrorSeverity.MEDIUM,
        details=details,
        recovery_suggestions=[
            "Überprüfen Sie Ihre Berechtigungen",
            "Kontaktieren Sie einen Administrator",
            "Stellen Sie sicher, dass Sie angemeldet sind"
        ]
    )

def validation_error(message: str, field: str = None, details: str = None) -> MailAppError:
    """Create validation error"""
    user_message = f"Ungültige Eingabe" + (f" im Feld '{field}'" if field else "") + f": {message}"
    return MailAppError(
        message=message,
        error_type=ErrorType.VALIDATION_ERROR,
        severity=ErrorSeverity.LOW,
        details=details,
        user_message=user_message,
        recovery_suggestions=[
            "Überprüfen Sie die eingegebenen Daten",
            "Stellen Sie sicher, dass alle Pflichtfelder ausgefüllt sind",
            "Beachten Sie die Formatanforderungen"
        ]
    )

def external_api_error(service: str, message: str = None, details: str = None) -> MailAppError:
    """Create external API error"""
    return MailAppError(
        message=message or f"External API error for {service}",
        error_type=ErrorType.EXTERNAL_API_ERROR,
        severity=ErrorSeverity.HIGH,
        details=details,
        user_message=f"Der externe Dienst '{service}' ist momentan nicht verfügbar.",
        recovery_suggestions=[
            "Versuchen Sie es in wenigen Minuten erneut",
            "Überprüfen Sie Ihre Internetverbindung",
            "Kontaktieren Sie den Support bei anhaltenden Problemen"
        ]
    )

def database_error(message: str = None, details: str = None) -> MailAppError:
    """Create database error"""
    return MailAppError(
        message=message or "Database operation failed",
        error_type=ErrorType.DATABASE_ERROR,
        severity=ErrorSeverity.HIGH,
        details=details,
        recovery_suggestions=[
            "Versuchen Sie es erneut",
            "Warten Sie einen Moment und versuchen Sie es dann erneut",
            "Kontaktieren Sie den Administrator bei anhaltenden Problemen"
        ]
    )