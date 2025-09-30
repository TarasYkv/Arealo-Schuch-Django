from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.conf import settings
from .models import ErrorLog, UserSession
import traceback
import sys
import hashlib
import json
import psutil
import platform
import django
import re
import logging

logger = logging.getLogger(__name__)


class DetailedErrorLoggingMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.start_time = None
        super().__init__(get_response)

    def process_request(self, request):
        """Store request start time for duration calculation"""
        self.start_time = timezone.now()
        return None

    def process_exception(self, request, exception):
        """Log detailed error information when an exception occurs"""
        try:
            self.log_error(request, exception, error_type='500')
        except Exception as e:
            logger.error(f"Error while logging exception: {e}")
        return None

    def process_response(self, request, response):
        """Log HTTP error responses (4xx, 5xx)"""
        try:
            if response.status_code >= 400:
                error_type = str(response.status_code)
                if hasattr(response, 'content'):
                    error_message = response.content.decode('utf-8', errors='ignore')[:1000]
                else:
                    error_message = f"HTTP {response.status_code} Error"

                self.log_error(request, None, error_type=error_type, error_message=error_message)
        except Exception as e:
            logger.error(f"Error while logging response: {e}")

        return response

    def log_error(self, request, exception=None, error_type='500', error_message=''):
        """Log comprehensive error details"""
        try:
            # Basic error info
            if exception:
                error_message = str(exception)
                stack_trace = self.get_formatted_traceback()
                line_number, file_path = self.extract_error_location()
            else:
                stack_trace = ''
                line_number = None
                file_path = ''

            # Request context
            request_duration = None
            if self.start_time:
                duration = timezone.now() - self.start_time
                request_duration = duration.total_seconds()

            # User context
            device_info = self.get_device_info(request)
            user_context = self.get_user_context(request)

            # System context
            system_info = self.get_system_info()
            performance_info = self.get_performance_info()

            # Request data
            request_data = self.get_request_data(request)

            # Error hash for grouping
            error_hash = self.generate_error_hash(error_message, file_path, line_number)

            # Determine severity
            severity = self.determine_severity(error_type, exception)

            # Get or create view/app info
            view_name, app_name = self.get_view_info(request)

            # Check for existing similar error
            existing_error = ErrorLog.objects.filter(error_hash=error_hash).first()

            if existing_error:
                # Update existing error
                existing_error.occurrence_count += 1
                existing_error.timestamp = timezone.now()
                existing_error.save()
            else:
                # Create new error log
                error_log = ErrorLog.objects.create(
                    # Basic Info
                    error_type=error_type,
                    url=request.build_absolute_uri(),
                    error_message=error_message[:2000],  # Limit length
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    ip_address=self.get_client_ip(request),
                    timestamp=timezone.now(),
                    user=request.user if request.user.is_authenticated else None,

                    # Extended Details
                    stack_trace=stack_trace,
                    request_method=request.method,
                    request_data=request_data,
                    referer_url=request.META.get('HTTP_REFERER', '')[:500],
                    session_key=request.session.session_key or '',

                    # System Info
                    server_name=system_info['server_name'],
                    python_version=system_info['python_version'],
                    django_version=system_info['django_version'],

                    # Request Context
                    view_name=view_name,
                    app_name=app_name,
                    line_number=line_number,
                    file_path=file_path,

                    # Performance Context
                    request_duration=request_duration,
                    memory_usage=performance_info['memory_usage'],
                    cpu_usage=performance_info['cpu_usage'],

                    # User Context
                    device_type=device_info['device_type'],
                    browser=device_info['browser'],
                    os=device_info['os'],
                    screen_resolution=device_info.get('screen_resolution', ''),

                    # Business Context
                    is_authenticated=request.user.is_authenticated,
                    user_role=user_context['role'],
                    session_duration=user_context['session_duration'],
                    pages_visited=user_context['pages_visited'],

                    # Grouping
                    error_hash=error_hash,
                    first_occurrence=timezone.now(),
                    occurrence_count=1,

                    # Severity
                    severity=severity,
                )

                # Auto-resolve minor errors after 24h
                if severity == 'low':
                    from datetime import timedelta
                    old_errors = ErrorLog.objects.filter(
                        severity='low',
                        timestamp__lt=timezone.now() - timedelta(hours=24),
                        is_resolved=False
                    )
                    old_errors.update(is_resolved=True, resolved_at=timezone.now())

        except Exception as e:
            logger.error(f"Critical error in error logging: {e}")

    def get_formatted_traceback(self):
        """Get formatted stack trace"""
        try:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_traceback:
                return ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        except:
            pass
        return ''

    def extract_error_location(self):
        """Extract line number and file path from traceback"""
        try:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_traceback:
                # Get the last frame in the traceback
                tb = exc_traceback
                while tb.tb_next:
                    tb = tb.tb_next

                line_number = tb.tb_lineno
                file_path = tb.tb_frame.f_code.co_filename

                # Shorten file path
                if 'PycharmProjects' in file_path:
                    file_path = file_path.split('PycharmProjects/')[-1]

                return line_number, file_path
        except:
            pass
        return None, ''

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip

    def get_device_info(self, request):
        """Extract device information from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()

        device_info = {
            'device_type': 'desktop',
            'browser': 'Unknown',
            'os': 'Unknown'
        }

        # Device Type Detection
        mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'phone', 'tablet']
        if any(keyword in user_agent for keyword in mobile_keywords):
            if 'tablet' in user_agent or 'ipad' in user_agent:
                device_info['device_type'] = 'tablet'
            else:
                device_info['device_type'] = 'mobile'

        # Browser Detection
        if 'chrome' in user_agent and 'edge' not in user_agent:
            device_info['browser'] = 'Chrome'
        elif 'firefox' in user_agent:
            device_info['browser'] = 'Firefox'
        elif 'safari' in user_agent and 'chrome' not in user_agent:
            device_info['browser'] = 'Safari'
        elif 'edge' in user_agent:
            device_info['browser'] = 'Edge'
        elif 'opera' in user_agent:
            device_info['browser'] = 'Opera'

        # OS Detection
        if 'windows' in user_agent:
            device_info['os'] = 'Windows'
        elif 'mac os' in user_agent or 'macos' in user_agent:
            device_info['os'] = 'macOS'
        elif 'android' in user_agent:
            device_info['os'] = 'Android'
        elif 'iphone' in user_agent or 'ios' in user_agent:
            device_info['os'] = 'iOS'
        elif 'linux' in user_agent:
            device_info['os'] = 'Linux'

        return device_info

    def get_user_context(self, request):
        """Get user session context"""
        context = {
            'role': '',
            'session_duration': None,
            'pages_visited': 0
        }

        if request.user.is_authenticated:
            if request.user.is_superuser:
                context['role'] = 'superuser'
            elif request.user.is_staff:
                context['role'] = 'staff'
            else:
                context['role'] = 'user'

        # Get session info
        session_key = request.session.session_key
        if session_key:
            try:
                from .models import UserSession
                user_session = UserSession.objects.get(session_key=session_key)
                duration = timezone.now() - user_session.start_time
                context['session_duration'] = int(duration.total_seconds())
                context['pages_visited'] = user_session.page_count
            except:
                pass

        return context

    def get_system_info(self):
        """Get system information"""
        return {
            'server_name': platform.node(),
            'python_version': platform.python_version(),
            'django_version': django.get_version()
        }

    def get_performance_info(self):
        """Get current performance metrics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_usage = memory_info.rss / 1024 / 1024  # MB
            cpu_usage = process.cpu_percent()
        except:
            memory_usage = None
            cpu_usage = None

        return {
            'memory_usage': memory_usage,
            'cpu_usage': cpu_usage
        }

    def get_request_data(self, request):
        """Extract relevant request data"""
        data = {}

        try:
            # GET parameters
            if request.GET:
                data['GET'] = dict(request.GET)

            # POST parameters (but filter sensitive data)
            if request.POST:
                post_data = dict(request.POST)
                # Remove sensitive fields
                sensitive_fields = ['password', 'token', 'secret', 'key', 'csrf']
                for field in sensitive_fields:
                    post_data.pop(field, None)
                data['POST'] = post_data

            # Headers (filtered)
            headers = {}
            for key, value in request.META.items():
                if key.startswith('HTTP_'):
                    header_name = key[5:].replace('_', '-').title()
                    if header_name not in ['Authorization', 'Cookie']:
                        headers[header_name] = value[:200]  # Limit length
            data['headers'] = headers

        except Exception as e:
            data['error'] = f"Could not extract request data: {e}"

        return data

    def get_view_info(self, request):
        """Extract view and app information"""
        view_name = ''
        app_name = ''

        try:
            # Try to get view from resolver
            from django.urls import resolve
            resolved = resolve(request.path)
            view_name = resolved.view_name
            app_name = resolved.app_name or resolved.namespace or ''

            # If view_name contains app, extract it
            if '.' in view_name:
                parts = view_name.split('.')
                if not app_name and len(parts) > 1:
                    app_name = parts[0]
                view_name = parts[-1]

        except Exception as e:
            # Fallback: extract from URL
            path_parts = request.path.strip('/').split('/')
            if path_parts and path_parts[0]:
                app_name = path_parts[0]

        return view_name, app_name

    def generate_error_hash(self, error_message, file_path, line_number):
        """Generate hash for error grouping"""
        hash_string = f"{error_message}{file_path}{line_number}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def determine_severity(self, error_type, exception):
        """Determine error severity"""
        if error_type in ['500', 'database', 'memory']:
            return 'critical'
        elif error_type in ['404', '403']:
            return 'low'
        elif error_type in ['400', 'validation']:
            return 'medium'
        elif exception and any(word in str(exception).lower() for word in ['critical', 'fatal', 'urgent']):
            return 'critical'
        else:
            return 'medium'