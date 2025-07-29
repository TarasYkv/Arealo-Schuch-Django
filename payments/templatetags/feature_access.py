from django import template
from django.utils.safestring import mark_safe
from accounts.models import FeatureAccess
from payments.feature_access import FeatureAccessService

register = template.Library()


@register.simple_tag(takes_context=True)
def user_has_feature_access(context, app_name):
    """
    Template tag to check if current user has access to a feature/app
    Usage: {% user_has_feature_access 'shopify_manager' as has_access %}
    """
    user = context.get('user')
    if not user:
        return False
    
    return FeatureAccess.user_can_access_app(app_name, user)


@register.simple_tag(takes_context=True)
def user_has_founder_access(context):
    """
    Template tag to check if current user has Founder's Early Access
    Usage: {% user_has_founder_access as has_founder %}
    """
    user = context.get('user')
    if not user:
        return False
    
    return FeatureAccessService.has_founder_access(user)


@register.simple_tag(takes_context=True)
def user_has_premium_access(context):
    """
    Template tag to check if current user has any premium subscription
    Usage: {% user_has_premium_access as has_premium %}
    """
    user = context.get('user')
    if not user:
        return False
    
    return FeatureAccessService.has_premium_access(user)


@register.inclusion_tag('payments/feature_access_check.html', takes_context=True)
def if_has_feature_access(context, app_name):
    """
    Inclusion tag that renders content conditionally based on feature access
    Usage: {% if_has_feature_access 'shopify_manager' %}
    """
    user = context.get('user')
    has_access = False
    
    if user:
        has_access = FeatureAccess.user_can_access_app(app_name, user)
    
    return {
        'has_access': has_access,
        'app_name': app_name,
        'user': user
    }


@register.inclusion_tag('payments/upgrade_prompt.html', takes_context=True)
def feature_upgrade_prompt(context, app_name, custom_message=None):
    """
    Shows an upgrade prompt for a specific feature
    Usage: {% feature_upgrade_prompt 'shopify_manager' %}
    """
    user = context.get('user')
    
    if not user or not user.is_authenticated:
        return {
            'show_prompt': False
        }
    
    # Check if user already has access
    has_access = FeatureAccess.user_can_access_app(app_name, user)
    if has_access:
        return {
            'show_prompt': False
        }
    
    # Get feature information
    try:
        feature = FeatureAccess.objects.get(app_name=app_name, is_active=True)
        upgrade_message = custom_message or feature.get_upgrade_message()
        subscription_required = feature.get_subscription_required_display()
    except FeatureAccess.DoesNotExist:
        upgrade_message = custom_message or f'Diese Funktion erfordert ein Abonnement.'
        subscription_required = 'Abonnement'
    
    return {
        'show_prompt': True,
        'app_name': app_name,
        'upgrade_message': upgrade_message,
        'subscription_required': subscription_required,
        'upgrade_url': '/payments/plans/',
        'user': user
    }


@register.inclusion_tag('payments/subscription_badge.html', takes_context=True)  
def subscription_required_badge(context, app_name):
    """
    Shows a badge indicating subscription requirement
    Usage: {% subscription_required_badge 'shopify_manager' %}
    """
    user = context.get('user')
    
    try:
        feature = FeatureAccess.objects.get(app_name=app_name, is_active=True)
        
        # Don't show badge for free features
        if feature.subscription_required == 'free':
            return {
                'show_badge': False
            }
        
        # Check if user has access
        has_access = False
        if user:
            has_access = feature.user_has_access(user)
        
        badge_text = ""
        badge_class = ""
        
        if feature.subscription_required == 'founder_access':
            badge_text = "Early Access"
            badge_class = "badge-founder" if has_access else "badge-locked"
        elif feature.subscription_required == 'any_paid':
            badge_text = "Premium"
            badge_class = "badge-premium" if has_access else "badge-locked"
        elif feature.subscription_required == 'storage_plan':
            badge_text = "Storage Plan"
            badge_class = "badge-storage" if has_access else "badge-locked"
        elif feature.subscription_required == 'blocked':
            badge_text = "Gesperrt"
            badge_class = "badge-blocked"
        
        return {
            'show_badge': True,
            'badge_text': badge_text,
            'badge_class': badge_class,
            'has_access': has_access,
            'app_name': app_name
        }
        
    except FeatureAccess.DoesNotExist:
        return {
            'show_badge': False
        }


@register.simple_tag(takes_context=True)
def get_user_accessible_apps(context):
    """
    Returns list of apps the current user can access
    Usage: {% get_user_accessible_apps as accessible_apps %}
    """
    user = context.get('user')
    if not user:
        return []
    
    return FeatureAccess.get_user_accessible_apps(user)


@register.simple_tag(takes_context=True)
def get_subscription_info(context):
    """
    Returns detailed subscription information for the current user
    Usage: {% get_subscription_info as sub_info %}
    """
    user = context.get('user')
    if not user:
        return {}
    
    return FeatureAccessService.get_subscription_info(user)


@register.filter
def feature_accessible(app_name, user):
    """
    Filter to check feature access
    Usage: {{ 'shopify_manager'|feature_accessible:user }}
    """
    if not user:
        return False
    
    return FeatureAccess.user_can_access_app(app_name, user)