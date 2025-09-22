from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import AppPermission, UserAppPermission


def require_app_permission(app_name, redirect_to='accounts:dashboard'):
    """
    Decorator der prüft ob ein User Zugriff auf eine bestimmte App hat.
    Unterstützt auch anonymen Zugriff basierend auf AppPermission.access_level.

    Args:
        app_name: str - Name der App aus AppPermission.APP_CHOICES
        redirect_to: str - URL-Name wohin umgeleitet werden soll wenn kein Zugriff
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user if hasattr(request, 'user') else None

            # Prüfe App-Berechtigung (unterstützt anonymous, authenticated, selected, etc.)
            has_access = UserAppPermission.get_user_app_access(app_name, user)

            if not has_access:
                # Prüfe ob User sich anmelden sollte für bessere Fehlermeldung
                try:
                    app_permission = AppPermission.objects.get(app_name=app_name, is_active=True)
                    if app_permission.access_level in ['authenticated', 'selected'] and (not user or not user.is_authenticated):
                        # App erfordert Anmeldung, aber User ist nicht eingeloggt
                        messages.info(request, 'Bitte melden Sie sich an, um auf diese Funktion zuzugreifen.')
                        return redirect('accounts:login')
                except AppPermission.DoesNotExist:
                    pass

                # Kein Zugriff erlaubt
                messages.error(request, f'Sie haben keinen Zugriff auf diese Funktion. Kontaktieren Sie einen Administrator.')
                return redirect(redirect_to)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_app_permission(app_name, user=None, check_frontend_visibility=False):
    """
    Hilfsfunktion um in Templates und Views zu prüfen ob ein User Zugriff hat.
    
    Args:
        app_name: str - Name der App aus AppPermission.APP_CHOICES
        user: User - Der zu prüfende User (optional)
        check_frontend_visibility: bool - Ob Frontend-Sichtbarkeit geprüft werden soll
    
    Returns:
        bool - True wenn Zugriff erlaubt, sonst False
    """
    if check_frontend_visibility:
        return AppPermission.user_can_see_in_frontend(app_name, user)
    return UserAppPermission.get_user_app_access(app_name, user)


class AppPermissionMixin:
    """
    Mixin für Class-Based Views um App-Berechtigungen zu prüfen.
    
    Usage:
        class MyView(AppPermissionMixin, ListView):
            app_name = 'schulungen'
            model = MyModel
    """
    app_name = None
    redirect_to = 'accounts:dashboard'
    
    def dispatch(self, request, *args, **kwargs):
        if not self.app_name:
            raise ValueError("app_name muss in der View definiert werden")
        
        user = request.user if hasattr(request, 'user') else None
        
        # Erst prüfen ob User eingeloggt ist
        if not user or not user.is_authenticated:
            messages.info(request, 'Bitte melden Sie sich an, um auf diese Funktion zuzugreifen.')
            return redirect('accounts:login')
        
        # Prüfe App-Berechtigung mit Priorität auf individuelle Berechtigungen
        has_access = UserAppPermission.get_user_app_access(self.app_name, user)
        
        if not has_access:
            messages.error(request, f'Sie haben keinen Zugriff auf diese Funktion. Kontaktieren Sie einen Administrator.')
            return redirect(self.redirect_to)
        
        return super().dispatch(request, *args, **kwargs)