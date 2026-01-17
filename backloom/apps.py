from django.apps import AppConfig


class BackloomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backloom'
    verbose_name = 'BackLoom - Backlink Discovery'

    def ready(self):
        """Import signals wenn App bereit ist"""
        pass
