"""
Middleware für App-Nutzungs-Tracking
"""
import re
from django.utils import timezone
from .models import AppUsageTracking


class AppUsageTrackingMiddleware:
    """
    Middleware zum Tracking der App-Nutzung basierend auf URL-Pfaden
    """
    
    # Mapping von URL-Patterns zu App-Namen
    APP_URL_PATTERNS = {
        r'^/chat/': 'chat',
        r'^/videos/': 'videos',
        r'^/$': 'schuch',
        r'^/dashboard/': 'schuch_dashboard',
        r'^/shopify/': 'shopify_manager',
        r'^/image-editor/': 'image_editor',
        r'^/naturmacher/': 'naturmacher',
        r'^/organization/': 'organization',
        r'^/todos/': 'todos',
        r'^/pdf-sucher/': 'pdf_sucher',
        r'^/amortization-calculator/': 'amortization_calculator',
        r'^/sportplatz/': 'sportplatzApp',
        r'^/bug-report/': 'bug_report',
        r'^/payments/': 'payments',
        r'^/accounts/': 'accounts',
    }
    
    # URLs die ignoriert werden sollen (API, Statische Dateien, etc.)
    IGNORE_PATTERNS = [
        r'^/api/',
        r'^/static/',
        r'^/media/',
        r'^/admin/',
        r'^/favicon\.ico',
        r'^/robots\.txt',
        r'\.json$',
        r'\.xml$',
        r'\.css$',
        r'\.js$',
        r'\.png$',
        r'\.jpg$',
        r'\.jpeg$',
        r'\.gif$',
        r'\.svg$',
        r'^/accounts/api/',  # Account API endpoints
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Kompiliere die Regex-Patterns für bessere Performance
        self.compiled_app_patterns = [
            (re.compile(pattern), app_name)
            for pattern, app_name in self.APP_URL_PATTERNS.items()
        ]
        
        self.compiled_ignore_patterns = [
            re.compile(pattern) for pattern in self.IGNORE_PATTERNS
        ]
    
    def __call__(self, request):
        # Vor der View-Verarbeitung
        self.process_request(request)
        
        # View verarbeiten
        response = self.get_response(request)
        
        # Nach der View-Verarbeitung
        self.process_response(request, response)
        
        return response
    
    def process_request(self, request):
        """Wird vor jeder Request ausgeführt"""
        # Nur für angemeldete Benutzer tracken
        if not request.user.is_authenticated:
            return
        
        path = request.path
        
        # Ignoriere bestimmte URLs
        for ignore_pattern in self.compiled_ignore_patterns:
            if ignore_pattern.search(path):
                return
        
        # Finde die passende App basierend auf der URL
        app_name = self.get_app_name_from_path(path)
        if not app_name:
            return
        
        # Store in request for later use
        request._app_usage_tracking = {
            'app_name': app_name,
            'start_time': timezone.now(),
        }
        
        # Starte App-Session
        try:
            session = AppUsageTracking.start_session(
                user=request.user,
                app_name=app_name,
                url_path=path,
                request=request
            )
            request._app_usage_session = session
        except Exception as e:
            # Fehler beim Tracking sollten die App nicht zum Absturz bringen
            print(f"App Usage Tracking Error: {e}")
    
    def process_response(self, request, response):
        """Wird nach jeder Request ausgeführt"""
        # Beende aktive Session falls vorhanden
        if hasattr(request, '_app_usage_session'):
            try:
                session = request._app_usage_session
                session.end_session()
            except Exception as e:
                print(f"App Usage Tracking Error (response): {e}")
        
        return response
    
    def get_app_name_from_path(self, path):
        """Bestimmt den App-Namen basierend auf dem URL-Pfad"""
        for pattern, app_name in self.compiled_app_patterns:
            if pattern.match(path):
                return app_name
        return None


class AppUsageHeartbeatMiddleware:
    """
    Lightweight Middleware für Session-Heartbeat Updates
    Aktualisiert die letzte Aktivität für laufende Sessions
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Update aktive Sessions mit neuem Timestamp
        if request.user.is_authenticated and hasattr(request, '_app_usage_session'):
            try:
                session = request._app_usage_session
                if session.is_active_session:
                    session.updated_at = timezone.now()
                    session.save(update_fields=['updated_at'])
            except Exception:
                pass  # Silent fail
        
        return response