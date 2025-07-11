from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserLoginHistory


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