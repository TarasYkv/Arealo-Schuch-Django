from django.apps import AppConfig


class MailAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mail_app'
    verbose_name = 'Mail Application'
    
    def ready(self):
        import mail_app.signals
