"""
Desktop App Manager App Config
"""

from django.apps import AppConfig


class DesktopAppManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'desktop_app_manager'
    verbose_name = 'Desktop App Manager'
