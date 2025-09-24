"""
LoomLine App Configuration
Django app configuration for LoomLine SEO Task Timeline
"""

from django.apps import AppConfig


class LoomlineConfig(AppConfig):
    """Configuration for LoomLine app"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loomline'
    verbose_name = 'LoomLine - SEO Task Timeline'

    def ready(self):
        """App initialization code"""
        # Import signals here to ensure they are connected
        try:
            from . import signals
        except ImportError:
            pass

        # Register app in core system
        self.register_app_info()

    def register_app_info(self):
        """Register app information in the core system"""
        try:
            from accounts.models import AppInfo

            app_info, created = AppInfo.objects.get_or_create(
                app_name='loomline',
                defaults={
                    'display_name': 'LoomLine',
                    'description': 'SEO Task Timeline Management - Collaborative SEO project tracking with timeline, metrics, and team coordination.',
                    'icon': 'fas fa-chart-line',
                    'url_name': 'loomline:dashboard',
                    'category': 'SEO & Marketing',
                    'is_active': True,
                    'requires_permission': True,
                    'permission_name': 'loomline',
                    'version': '1.0.0',
                    'author': 'Arealo-Schuch Development Team',
                    'features': [
                        'Project-based SEO task organization',
                        'Collaborative team management',
                        'Timeline tracking and activity history',
                        'SEO metrics recording and analysis',
                        'Task assignment and status tracking',
                        'Comment system for team communication',
                        'Real-time updates and notifications',
                        'Export and reporting capabilities'
                    ],
                    'tech_stack': [
                        'Django 5.2+',
                        'Django REST Framework',
                        'Bootstrap 5',
                        'Font Awesome Icons',
                        'JavaScript ES6+',
                        'JSON Field Storage'
                    ]
                }
            )

            if created:
                print(f"✅ LoomLine app registered in core system")
            else:
                print(f"📱 LoomLine app already registered")

        except Exception as e:
            print(f"⚠️ Could not register LoomLine app in core system: {e}")
