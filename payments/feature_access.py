from django.contrib.auth import get_user_model
from .models import Customer, Subscription as StripeSubscription
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class FeatureAccessService:
    """Service to control access to premium features based on subscriptions"""
    
    @staticmethod
    def get_user_active_subscription(user):
        """Get user's active Stripe subscription"""
        try:
            customer = Customer.objects.get(user=user)
            return StripeSubscription.objects.filter(
                customer=customer,
                status__in=['active', 'trialing']
            ).first()
        except Customer.DoesNotExist:
            return None
    
    @staticmethod
    def has_founder_access(user):
        """Check if user has Founder's Early Access subscription"""
        subscription = FeatureAccessService.get_user_active_subscription(user)
        if not subscription:
            return False
        return subscription.plan.plan_type == 'founder_access'
    
    @staticmethod
    def has_premium_access(user):
        """Check if user has any premium subscription (including Founder's Access)"""
        subscription = FeatureAccessService.get_user_active_subscription(user)
        if not subscription:
            return False
        return subscription.plan.price > 0
    
    @staticmethod
    def has_app_access(user, app_name):
        """Check if user has access to a specific app"""
        # Superusers always have access
        if user.is_superuser:
            return True
        
        # Check if user has Founder's Early Access (all apps unlocked)
        if FeatureAccessService.has_founder_access(user):
            return True
        
        subscription = FeatureAccessService.get_user_active_subscription(user)
        if not subscription:
            return False
        
        # Check if app is in the subscription features
        features = subscription.plan.features or {}
        if features.get('all_apps_access', False):
            return True
        
        # Check specific app list
        allowed_apps = features.get('apps', [])
        return app_name in allowed_apps
    
    @staticmethod
    def get_user_features(user):
        """Get all features available to the user"""
        subscription = FeatureAccessService.get_user_active_subscription(user)
        
        # Default features for free users
        default_features = {
            'unlimited_storage': False,
            'all_apps_access': False,
            'priority_support': False,
            'trial_days': 0,
            'apps': ['videos']  # Free users get basic video functionality
        }
        
        if not subscription:
            return default_features
        
        # Get features from subscription plan
        plan_features = subscription.plan.features or {}
        
        # Merge with defaults, plan features override defaults
        features = {**default_features, **plan_features}
        
        return features
    
    @staticmethod
    def get_subscription_info(user):
        """Get detailed subscription information for the user"""
        subscription = FeatureAccessService.get_user_active_subscription(user)
        
        if not subscription:
            return {
                'has_subscription': False,
                'plan_name': 'Kostenlos',
                'plan_type': 'free',
                'price': 0.00,
                'currency': 'EUR',
                'interval': 'month',
                'status': 'active',
                'is_founder_access': False,
                'is_premium': False,
                'features': FeatureAccessService.get_user_features(user)
            }
        
        return {
            'has_subscription': True,
            'plan_name': subscription.plan.name,
            'plan_type': subscription.plan.plan_type,
            'price': float(subscription.plan.price),
            'currency': subscription.plan.currency,
            'interval': subscription.plan.interval,
            'status': subscription.status,
            'current_period_end': subscription.current_period_end,
            'trial_end': subscription.trial_end,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'is_founder_access': subscription.plan.plan_type == 'founder_access',
            'is_premium': subscription.plan.price > 0,
            'features': FeatureAccessService.get_user_features(user)
        }


def require_founder_access(view_func):
    """Decorator to require Founder's Early Access subscription"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        if not FeatureAccessService.has_founder_access(request.user):
            from django.shortcuts import render
            return render(request, 'payments/access_denied.html', {
                'required_plan': 'WorkLoom - Founder\'s Early Access',
                'upgrade_url': '/payments/plans/'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_premium_access(view_func):
    """Decorator to require any premium subscription"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        if not FeatureAccessService.has_premium_access(request.user):
            from django.shortcuts import render
            return render(request, 'payments/access_denied.html', {
                'required_plan': 'Premium Subscription',
                'upgrade_url': '/payments/plans/'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_app_access(app_name):
    """Decorator to require access to a specific app"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            if not FeatureAccessService.has_app_access(request.user, app_name):
                from django.shortcuts import render
                return render(request, 'payments/access_denied.html', {
                    'required_app': app_name,
                    'upgrade_url': '/payments/plans/'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_subscription_access(app_name):
    """Decorator to require subscription-based access to an app using FeatureAccess model"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            # Import hier um zirkuläre Imports zu vermeiden
            from accounts.models import FeatureAccess
            
            if not FeatureAccess.user_can_access_app(app_name, request.user):
                from django.shortcuts import render
                
                # Hole FeatureAccess Objekt für detailliertere Informationen
                try:
                    feature = FeatureAccess.objects.get(app_name=app_name, is_active=True)
                    upgrade_message = feature.get_upgrade_message()
                    subscription_required = feature.get_subscription_required_display()
                except FeatureAccess.DoesNotExist:
                    upgrade_message = f'Zugriff auf {app_name} erfordert ein Abonnement.'
                    subscription_required = 'Abonnement'
                
                return render(request, 'payments/feature_access_denied.html', {
                    'app_name': app_name,
                    'required_subscription': subscription_required,
                    'upgrade_message': upgrade_message,
                    'upgrade_url': '/payments/plans/',
                    'show_upgrade_prompt': True
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_feature_access(feature_name):
    """Decorator to require access to a specific feature (granular control)"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            from accounts.models import FeatureAccess
            
            if not FeatureAccess.user_can_access_app(feature_name, request.user):
                from django.shortcuts import render
                
                try:
                    feature = FeatureAccess.objects.get(app_name=feature_name, is_active=True)
                    upgrade_message = feature.get_upgrade_message()
                    subscription_required = feature.get_subscription_required_display()
                except FeatureAccess.DoesNotExist:
                    upgrade_message = f'Diese Funktion erfordert ein Abonnement.'
                    subscription_required = 'Abonnement'
                
                return render(request, 'payments/feature_access_denied.html', {
                    'feature_name': feature_name,
                    'required_subscription': subscription_required,
                    'upgrade_message': upgrade_message,
                    'upgrade_url': '/payments/plans/',
                    'show_upgrade_prompt': True
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator