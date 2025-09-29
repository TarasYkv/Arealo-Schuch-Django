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


# SEO Models
class CoreWebVitals(models.Model):
    """Core Web Vitals - wichtige Performance-Metriken für SEO"""
    url = models.URLField(max_length=500)

    # Largest Contentful Paint (LCP) - Loading Performance
    lcp = models.FloatField(help_text="Largest Contentful Paint in seconds")
    lcp_rating = models.CharField(max_length=20, choices=[
        ('good', 'Good (<2.5s)'),
        ('needs_improvement', 'Needs Improvement (2.5-4s)'),
        ('poor', 'Poor (>4s)')
    ], blank=True)

    # First Input Delay (FID) - Interactivity
    fid = models.FloatField(help_text="First Input Delay in milliseconds", null=True, blank=True)
    fid_rating = models.CharField(max_length=20, choices=[
        ('good', 'Good (<100ms)'),
        ('needs_improvement', 'Needs Improvement (100-300ms)'),
        ('poor', 'Poor (>300ms)')
    ], blank=True)

    # Cumulative Layout Shift (CLS) - Visual Stability
    cls = models.FloatField(help_text="Cumulative Layout Shift score")
    cls_rating = models.CharField(max_length=20, choices=[
        ('good', 'Good (<0.1)'),
        ('needs_improvement', 'Needs Improvement (0.1-0.25)'),
        ('poor', 'Poor (>0.25)')
    ], blank=True)

    timestamp = models.DateTimeField(default=timezone.now)
    device_type = models.CharField(max_length=20, choices=[
        ('mobile', 'Mobile'),
        ('desktop', 'Desktop')
    ], default='desktop')

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['url', 'timestamp']),
        ]

    def save(self, *args, **kwargs):
        # Auto-calculate ratings
        if self.lcp:
            if self.lcp < 2.5:
                self.lcp_rating = 'good'
            elif self.lcp < 4.0:
                self.lcp_rating = 'needs_improvement'
            else:
                self.lcp_rating = 'poor'

        if self.fid:
            if self.fid < 100:
                self.fid_rating = 'good'
            elif self.fid < 300:
                self.fid_rating = 'needs_improvement'
            else:
                self.fid_rating = 'poor'

        if self.cls:
            if self.cls < 0.1:
                self.cls_rating = 'good'
            elif self.cls < 0.25:
                self.cls_rating = 'needs_improvement'
            else:
                self.cls_rating = 'poor'

        super().save(*args, **kwargs)


class CrawlError(models.Model):
    """Crawl-Fehler die von Suchmaschinen gefunden wurden"""
    ERROR_TYPES = [
        ('404', '404 Not Found'),
        ('403', '403 Forbidden'),
        ('500', '500 Server Error'),
        ('redirect_loop', 'Redirect Loop'),
        ('timeout', 'Timeout'),
        ('dns', 'DNS Error'),
        ('ssl', 'SSL Certificate Error'),
    ]

    url = models.URLField(max_length=500)
    error_type = models.CharField(max_length=20, choices=ERROR_TYPES)
    first_detected = models.DateTimeField(default=timezone.now)
    last_checked = models.DateTimeField(default=timezone.now)
    is_resolved = models.BooleanField(default=False)
    response_code = models.IntegerField(null=True, blank=True)
    crawler = models.CharField(max_length=50, blank=True)  # Googlebot, Bingbot, etc.
    source_url = models.URLField(max_length=500, blank=True, help_text="URL die auf diese Seite verlinkt")

    class Meta:
        unique_together = ['url', 'error_type']
        ordering = ['-last_checked']

    def __str__(self):
        return f"{self.error_type} - {self.url}"


class BrokenLink(models.Model):
    """Kaputte Links auf der Website"""
    source_url = models.URLField(max_length=500, help_text="Seite mit dem kaputten Link")
    target_url = models.URLField(max_length=500, help_text="Ziel-URL die nicht funktioniert")
    anchor_text = models.CharField(max_length=200, blank=True)
    status_code = models.IntegerField()
    first_detected = models.DateTimeField(default=timezone.now)
    last_checked = models.DateTimeField(default=timezone.now)
    is_fixed = models.BooleanField(default=False)
    link_type = models.CharField(max_length=20, choices=[
        ('internal', 'Internal'),
        ('external', 'External'),
        ('image', 'Image'),
        ('script', 'Script'),
        ('stylesheet', 'Stylesheet'),
    ], default='internal')

    class Meta:
        unique_together = ['source_url', 'target_url']
        ordering = ['-last_checked']

    def __str__(self):
        return f"{self.source_url} -> {self.target_url} ({self.status_code})"


class SitemapStatus(models.Model):
    """Status der XML-Sitemap"""
    sitemap_url = models.URLField(max_length=500)
    is_accessible = models.BooleanField(default=True)
    total_urls = models.IntegerField(default=0)
    indexed_urls = models.IntegerField(default=0)
    last_modified = models.DateTimeField(null=True, blank=True)
    last_checked = models.DateTimeField(default=timezone.now)
    errors = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-last_checked']

    def __str__(self):
        return f"Sitemap: {self.sitemap_url}"


class RobotsTxtStatus(models.Model):
    """Status der robots.txt Datei"""
    domain = models.CharField(max_length=200, unique=True)
    is_accessible = models.BooleanField(default=True)
    content = models.TextField(blank=True)
    last_checked = models.DateTimeField(default=timezone.now)
    violations = models.JSONField(default=list, blank=True)  # URLs die gegen robots.txt verstoßen
    disallowed_paths = models.JSONField(default=list, blank=True)
    sitemap_references = models.JSONField(default=list, blank=True)
    crawl_delay = models.IntegerField(null=True, blank=True)
    user_agents = models.JSONField(default=dict, blank=True)  # Rules per user-agent

    class Meta:
        ordering = ['-last_checked']

    def __str__(self):
        return f"robots.txt for {self.domain}"
