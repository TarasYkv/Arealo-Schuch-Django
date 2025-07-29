from django import template
from accounts.models import AppPermission, UserAppPermission

register = template.Library()


@register.filter
def has_app_permission(user, app_name):
    """
    Template Filter um zu prüfen ob ein User Zugriff auf eine App hat.
    Berücksichtigt individuelle Berechtigungen mit höchster Priorität.
    
    Usage:
        {% if user|has_app_permission:"schulungen" %}
            <a href="{% url 'schulungen:index' %}">Schulungen</a>
        {% endif %}
    
    Args:
        user: User object
        app_name: str - Name der App aus AppPermission.APP_CHOICES
    
    Returns:
        bool - True wenn Zugriff erlaubt, sonst False
    """
    # Nutze die neue Methode die individuelle Berechtigungen prüft
    return UserAppPermission.get_user_app_access(app_name, user)


@register.filter
def can_see_app_in_frontend(user, app_name):
    """
    Template Filter um zu prüfen ob eine App im Frontend angezeigt werden soll.
    Berücksichtigt individuelle Berechtigungen mit höchster Priorität.
    
    Usage:
        {% if user|can_see_app_in_frontend:"schulungen" %}
            <a href="{% url 'schulungen:index' %}">Schulungen</a>
        {% endif %}
    
    Args:
        user: User object
        app_name: str - Name der App aus AppPermission.APP_CHOICES
    
    Returns:
        bool - True wenn App im Frontend sichtbar sein soll, sonst False
    """
    # Nutze die neue Methode die individuelle Berechtigungen prüft
    return UserAppPermission.user_can_see_app_in_frontend(app_name, user)


@register.simple_tag
def check_app_access(app_name, user=None):
    """
    Template Tag um App-Zugriff zu prüfen.
    Berücksichtigt individuelle Berechtigungen mit höchster Priorität.
    
    Usage:
        {% check_app_access "schulungen" user as can_access_schulungen %}
        {% if can_access_schulungen %}
            <!-- Inhalt anzeigen -->
        {% endif %}
    
    Args:
        app_name: str - Name der App
        user: User object (optional)
    
    Returns:
        bool - True wenn Zugriff erlaubt, sonst False
    """
    return UserAppPermission.get_user_app_access(app_name, user)


@register.inclusion_tag('accounts/fragments/app_nav_link.html')
def app_nav_link(app_name, url_name, icon_class, title, user=None, check_frontend_visibility=True):
    """
    Inclusion Tag um Navigation Links mit App-Berechtigung zu erstellen.
    
    Usage:
        {% app_nav_link "schulungen" "schulungen:index" "bi-mortarboard" "Schulungen" user %}
    
    Args:
        app_name: str - Name der App
        url_name: str - URL Name für den Link
        icon_class: str - CSS Klasse für das Icon
        title: str - Anzuzeigender Titel
        user: User object
        check_frontend_visibility: bool - Ob Frontend-Sichtbarkeit geprüft werden soll
    
    Returns:
        Dict mit Context für das Template
    """
    if check_frontend_visibility:
        has_access = UserAppPermission.user_can_see_app_in_frontend(app_name, user)
    else:
        has_access = UserAppPermission.get_user_app_access(app_name, user)
    
    return {
        'has_access': has_access,
        'url_name': url_name,
        'icon_class': icon_class,
        'title': title,
        'app_name': app_name
    }


@register.simple_tag
def get_app_permissions_for_user(user):
    """
    Template Tag um alle App-Berechtigungen für einen User zu holen.
    
    Usage:
        {% get_app_permissions_for_user user as user_permissions %}
        {% for perm in user_permissions %}
            {{ perm.get_app_name_display }}: {{ perm.get_access_level_display }}
        {% endfor %}
    
    Args:
        user: User object
    
    Returns:
        QuerySet von AppPermission objekten die der User nutzen kann
    """
    if not user or not user.is_authenticated:
        return AppPermission.objects.filter(access_level='anonymous', is_active=True)
    
    # Hole alle Berechtigungen die der User nutzen kann
    accessible_permissions = []
    
    for permission in AppPermission.objects.filter(is_active=True):
        if permission.has_access(user):
            accessible_permissions.append(permission)
    
    return accessible_permissions