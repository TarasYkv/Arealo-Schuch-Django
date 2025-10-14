from django.apps import AppConfig


class LoomconnectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loomconnect'
    verbose_name = 'LoomConnect'

    def ready(self):
        """Import signals when app is ready"""
        import loomconnect.signals  # noqa
