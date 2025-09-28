from django.db import models
from django.conf import settings
from django.utils import timezone


class PageVisit(models.Model):
    url = models.URLField(max_length=500)
    page_title = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='stats_page_visits')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    referer = models.URLField(max_length=500, blank=True)
    visit_time = models.DateTimeField(default=timezone.now)
    session_key = models.CharField(max_length=40, blank=True)

    # Device & Browser Analytics
    device_type = models.CharField(max_length=20, blank=True)  # mobile, desktop, tablet
    browser = models.CharField(max_length=50, blank=True)     # Chrome, Firefox, Safari, etc.
    os = models.CharField(max_length=50, blank=True)          # Windows, macOS, Android, iOS
    screen_resolution = models.CharField(max_length=20, blank=True)  # 1920x1080, etc.

    # Geographic Data
    country = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)

    # Performance Metrics
    page_load_time = models.FloatField(null=True, blank=True)  # in seconds
    connection_type = models.CharField(max_length=20, blank=True)  # 4g, wifi, etc.

    class Meta:
        ordering = ['-visit_time']
        indexes = [
            models.Index(fields=['visit_time']),
            models.Index(fields=['url']),
            models.Index(fields=['user']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"{self.url} - {self.visit_time}"


class UserSession(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='stats_user_sessions')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    start_time = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now)
    page_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-start_time']

    @property
    def duration(self):
        return self.last_activity - self.start_time

    def __str__(self):
        return f"Session {self.session_key} - {self.start_time}"


class AdClick(models.Model):
    ad_id = models.CharField(max_length=100)
    ad_name = models.CharField(max_length=200, blank=True)
    campaign_name = models.CharField(max_length=200, blank=True)
    zone_name = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='stats_ad_clicks')
    ip_address = models.GenericIPAddressField()
    page_url = models.URLField(max_length=500)
    click_time = models.DateTimeField(default=timezone.now)
    session_key = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['-click_time']
        indexes = [
            models.Index(fields=['click_time']),
            models.Index(fields=['ad_id']),
            models.Index(fields=['campaign_name']),
        ]

    def __str__(self):
        return f"Ad Click: {self.ad_name} - {self.click_time}"


class DailyStats(models.Model):
    date = models.DateField(unique=True)
    unique_visitors = models.PositiveIntegerField(default=0)
    total_page_views = models.PositiveIntegerField(default=0)
    total_ad_clicks = models.PositiveIntegerField(default=0)
    avg_session_duration = models.DurationField(null=True, blank=True)
    bounce_rate = models.FloatField(default=0.0)  # Percentage

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Stats for {self.date}"


class PopularPage(models.Model):
    url = models.URLField(max_length=500, unique=True)
    page_title = models.CharField(max_length=200, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-view_count']

    def __str__(self):
        return f"{self.page_title or self.url} ({self.view_count} views)"


class RealTimeVisitor(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    current_page = models.URLField(max_length=500)
    last_seen = models.DateTimeField(auto_now=True)
    device_type = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f"Visitor {self.session_key} on {self.current_page}"

    @property
    def is_online(self):
        from datetime import timedelta
        return timezone.now() - self.last_seen < timedelta(minutes=5)


class ConversionFunnel(models.Model):
    name = models.CharField(max_length=100)
    step_order = models.PositiveIntegerField()
    page_url = models.URLField(max_length=500)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['name', 'step_order']
        unique_together = ['name', 'step_order']

    def __str__(self):
        return f"{self.name} - Step {self.step_order}"


class ConversionEvent(models.Model):
    funnel = models.ForeignKey(ConversionFunnel, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.funnel.name} - {self.session_key}"


class PerformanceMetric(models.Model):
    date = models.DateField(unique=True)
    avg_page_load_time = models.FloatField(default=0.0)
    server_response_time = models.FloatField(default=0.0)
    bounce_rate = models.FloatField(default=0.0)
    pages_per_session = models.FloatField(default=0.0)
    avg_session_duration = models.FloatField(default=0.0)
    conversion_rate = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Performance {self.date}"


class ErrorLog(models.Model):
    ERROR_TYPES = [
        ('404', '404 - Page Not Found'),
        ('500', '500 - Server Error'),
        ('403', '403 - Forbidden'),
        ('400', '400 - Bad Request'),
        ('js', 'JavaScript Error'),
        ('timeout', 'Request Timeout'),
        ('memory', 'Memory Error'),
        ('database', 'Database Error'),
        ('permission', 'Permission Error'),
        ('validation', 'Validation Error'),
    ]

    error_type = models.CharField(max_length=15, choices=ERROR_TYPES)
    url = models.URLField(max_length=500)
    error_message = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # Erweiterte Error-Details
    stack_trace = models.TextField(blank=True, help_text="Full stack trace")
    request_method = models.CharField(max_length=10, blank=True)  # GET, POST, etc.
    request_data = models.JSONField(default=dict, blank=True)  # POST data, query params
    referer_url = models.URLField(max_length=500, blank=True)
    session_key = models.CharField(max_length=40, blank=True)

    # System-Info
    server_name = models.CharField(max_length=100, blank=True)
    python_version = models.CharField(max_length=20, blank=True)
    django_version = models.CharField(max_length=20, blank=True)

    # Request-Context
    view_name = models.CharField(max_length=100, blank=True)  # Welche View
    app_name = models.CharField(max_length=50, blank=True)    # Welche App
    line_number = models.IntegerField(null=True, blank=True)  # Zeile im Code
    file_path = models.CharField(max_length=500, blank=True)  # Datei-Pfad

    # Performance-Context
    request_duration = models.FloatField(null=True, blank=True)  # Zeit bis Error
    memory_usage = models.FloatField(null=True, blank=True)      # Memory bei Error
    cpu_usage = models.FloatField(null=True, blank=True)        # CPU bei Error

    # User-Context
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    screen_resolution = models.CharField(max_length=20, blank=True)

    # Business-Context
    is_authenticated = models.BooleanField(default=False)
    user_role = models.CharField(max_length=50, blank=True)
    session_duration = models.IntegerField(null=True, blank=True)  # Sekunden
    pages_visited = models.IntegerField(default=0)

    # Error-Gruppierung
    error_hash = models.CharField(max_length=64, blank=True)  # MD5 für Gruppierung
    first_occurrence = models.DateTimeField(null=True, blank=True)
    occurrence_count = models.IntegerField(default=1)

    # Severity
    SEVERITY_CHOICES = [
        ('low', 'Low - Minor Issue'),
        ('medium', 'Medium - Needs Attention'),
        ('high', 'High - Important'),
        ('critical', 'Critical - Immediate Action Required'),
    ]
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')

    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_errors')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.error_type} - {self.url}"


class SearchQuery(models.Model):
    query = models.CharField(max_length=200)
    results_count = models.PositiveIntegerField(default=0)
    session_key = models.CharField(max_length=40, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Search: {self.query}"
