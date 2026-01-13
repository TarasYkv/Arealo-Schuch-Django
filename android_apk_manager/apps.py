"""
Android APK Manager App Config
"""

from django.apps import AppConfig


class AndroidApkManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'android_apk_manager'
    verbose_name = 'Android APK Manager'

    def ready(self):
        """Import signals when app is ready"""
        import android_apk_manager.signals  # noqa
