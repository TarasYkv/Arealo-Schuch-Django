from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import UserLoginHistory

User = get_user_model()


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Speichert Login-Informationen wenn sich ein User anmeldet
    """
    # Hole IP-Adresse
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Beende vorherige aktive Sessions (falls vorhanden)
    UserLoginHistory.objects.filter(
        user=user,
        is_active_session=True
    ).update(
        is_active_session=False,
        logout_time=timezone.now()
    )
    
    # Erstelle neue Login-Geschichte
    login_history = UserLoginHistory.objects.create(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        is_active_session=True
    )
    
    # Aktualisiere User Online-Status
    user.is_online = True
    user.last_activity = timezone.now()
    user.save(update_fields=['is_online', 'last_activity'])


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Speichert Logout-Informationen wenn sich ein User abmeldet
    """
    if user and user.is_authenticated:
        # Finde aktive Session
        active_sessions = UserLoginHistory.objects.filter(
            user=user,
            is_active_session=True
        )
        
        logout_time = timezone.now()
        
        for session in active_sessions:
            session.logout_time = logout_time
            session.is_active_session = False
            session.session_duration = logout_time - session.login_time
            session.save()
        
        # Aktualisiere User Online-Status
        user.is_online = False
        user.save(update_fields=['is_online'])


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Sendet eine Willkommens-E-Mail an neue Benutzer über das Trigger-System
    """
    if created and instance.email_verified:  # Nur bei neuen, verifizierten Benutzern
        try:
            # Import hier um zirkuläre Imports zu vermeiden
            from email_templates.trigger_manager import trigger_manager
            from django.urls import reverse
            from django.conf import settings
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Bereite Benutzerdaten für die E-Mail vor
            context_data = {
                'user_name': instance.get_full_name() or instance.username,
                'username': instance.username,
                'email': instance.email,
                'registration_date': instance.date_joined.strftime('%d.%m.%Y %H:%M'),
                'activation_url': f"{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}{reverse('accounts:dashboard')}",
                'site_name': 'Workloom',
                'current_year': timezone.now().year,
                'domain': 'workloom.de',
                'features': [
                    'Chat-System für direkte Kommunikation',
                    'Shopify-Integration für E-Commerce',
                    'PDF-Suche und KI-Zusammenfassungen',
                    'Video-Hosting für Ihre Projekte',
                    'Organisationstools: Notizen, Boards, Termine'
                ]
            }
            
            # Verwende das neue Trigger-System
            results = trigger_manager.fire_trigger(
                trigger_key='user_registration',
                context_data=context_data,
                recipient_email=instance.email,
                recipient_name=instance.get_full_name() or instance.username
            )
            
            # Prüfe Ergebnis
            if results and any(result['success'] for result in results):
                logger.info(f"Welcome email sent successfully via trigger system to {instance.email}")
            else:
                logger.warning(f"Welcome email trigger failed for {instance.email}")
                
        except Exception as e:
            # Fehler beim E-Mail-Versand sollen die Registrierung nicht blockieren
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending welcome email to {instance.email}: {str(e)}")


def get_client_ip(request):
    """
    Holt die echte IP-Adresse des Clients
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip