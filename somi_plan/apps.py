from django.apps import AppConfig


class SomiPlanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'somi_plan'
    verbose_name = 'SoMi-Plan - AI Social Media Planner'
    
    def ready(self):
        """Import signal handlers"""
        try:
            import somi_plan.signals  # noqa
        except ImportError:
            pass
