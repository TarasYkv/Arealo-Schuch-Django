from django.contrib.auth import get_user_model
from .models import UserStorage
from payments.models import Customer, Subscription as StripeSubscription, SubscriptionPlan
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class StorageSubscriptionSync:
    """Service to sync video storage with Stripe subscriptions"""
    
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
    def get_storage_limit_from_subscription(subscription):
        """Get storage limit in bytes from Stripe subscription"""
        if not subscription:
            return 100 * 1024 * 1024  # 100MB default for free users
        
        # Get storage from the subscription plan
        if subscription.plan.storage_mb:
            return subscription.plan.storage_mb * 1024 * 1024
        
        # Fallback: determine by plan type and price
        if subscription.plan.plan_type == 'storage':
            price = float(subscription.plan.price)
            if price == 0:
                return 100 * 1024 * 1024  # 100MB
            elif price <= 2:
                return 1024 * 1024 * 1024  # 1GB
            elif price <= 3:
                return 2 * 1024 * 1024 * 1024  # 2GB
            elif price <= 7:
                return 5 * 1024 * 1024 * 1024  # 5GB
            else:
                return 10 * 1024 * 1024 * 1024  # 10GB
        
        return 50 * 1024 * 1024  # Default fallback
    
    @staticmethod
    def sync_user_storage(user):
        """Sync user's storage limits with their Stripe subscription"""
        try:
            user_storage, created = UserStorage.objects.get_or_create(
                user=user,
                defaults={
                    'used_storage': 0,
                    'max_storage': 104857600,  # 100MB default (free plan)
                    'is_premium': False,
                }
            )
            
            # Get active Stripe subscription
            subscription = StorageSubscriptionSync.get_user_active_subscription(user)
            
            # Calculate new storage limit
            new_storage_limit = StorageSubscriptionSync.get_storage_limit_from_subscription(subscription)
            is_premium_plan = subscription is not None and subscription.plan.price > 0
            
            # Track if we're downgrading from paid to free
            was_premium = user_storage.is_premium
            is_downgrading_to_free = was_premium and not is_premium_plan
            
            # Update storage if changed
            if user_storage.max_storage != new_storage_limit or user_storage.is_premium != is_premium_plan:
                old_limit = user_storage.max_storage
                user_storage.max_storage = new_storage_limit
                user_storage.is_premium = is_premium_plan
                
                # Handle downgrade to free plan
                if is_downgrading_to_free:
                    StorageSubscriptionSync._handle_downgrade_to_free(user_storage)
                
                # Handle upgrade (restore archived videos)
                elif not was_premium and is_premium_plan:
                    StorageSubscriptionSync._handle_upgrade_to_paid(user_storage)
                
                user_storage.save()
                
                logger.info(f"Updated storage for user {user.username}: {old_limit/1024/1024:.1f}MB -> {new_storage_limit/1024/1024:.1f}MB (Premium: {is_premium_plan})")
            
            return user_storage
            
        except Exception as e:
            logger.error(f"Error syncing storage for user {user.username}: {str(e)}")
            # Return default storage on error
            user_storage, created = UserStorage.objects.get_or_create(
                user=user,
                defaults={
                    'used_storage': 0,
                    'max_storage': 104857600,  # 100MB default
                    'is_premium': False,
                }
            )
            return user_storage
    
    @staticmethod
    def _handle_downgrade_to_free(user_storage):
        """Handle user downgrading from paid to free plan"""
        from .storage_management import StorageOverageService
        
        logger.info(f"Handling downgrade to free plan for user: {user_storage.user.username}")
        
        # Clear any existing overage status to start fresh
        user_storage.clear_overage_status()
        
        # Check if storage is now exceeded and start grace period if needed
        if user_storage.is_storage_exceeded():
            user_storage.start_grace_period()
            StorageOverageService.send_overage_notification(
                user_storage.user, 
                'grace_period_start'
            )
            logger.info(f"Started grace period for downgraded user: {user_storage.user.username}")
    
    @staticmethod 
    def _handle_upgrade_to_paid(user_storage):
        """Handle user upgrading from free to paid plan"""
        from .storage_management import VideoArchivingService
        
        logger.info(f"Handling upgrade to paid plan for user: {user_storage.user.username}")
        
        # Clear any overage restrictions
        user_storage.clear_overage_status()
        
        # Restore any archived videos
        restored_count, restored_bytes = VideoArchivingService.restore_user_videos(user_storage.user)
        
        if restored_count > 0:
            logger.info(f"Restored {restored_count} videos ({restored_bytes/1024/1024:.1f}MB) for upgraded user: {user_storage.user.username}")
    
    @staticmethod
    def is_free_plan(user):
        """Check if user is on the free plan"""
        try:
            subscription = StorageSubscriptionSync.get_user_active_subscription(user)
            return subscription is None or subscription.plan.price == 0
        except:
            return True  # Default to free if error
    
    @staticmethod
    def get_user_plan_info(user):
        """Get comprehensive plan information for a user"""
        subscription = StorageSubscriptionSync.get_user_active_subscription(user)
        user_storage = StorageSubscriptionSync.sync_user_storage(user)
        
        if subscription:
            plan_info = {
                'has_subscription': True,
                'plan_name': subscription.plan.name,
                'price': float(subscription.plan.price),
                'currency': subscription.plan.currency,
                'interval': subscription.plan.interval,
                'storage_mb': subscription.plan.storage_mb,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'is_premium': subscription.plan.price > 0
            }
        else:
            # Free plan - always active, no Stripe involved
            plan_info = {
                'has_subscription': False,
                'plan_name': 'Starter (Kostenlos)',
                'price': 0.00,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 100,
                'status': 'active',
                'current_period_end': None,
                'cancel_at_period_end': False,
                'is_premium': False,
                'is_free_plan': True,
                'requires_payment': False
            }
        
        plan_info.update({
            'used_storage_mb': user_storage.get_used_storage_mb(),
            'max_storage_mb': user_storage.get_max_storage_mb(),
            'used_percentage': (user_storage.used_storage / user_storage.max_storage * 100) if user_storage.max_storage > 0 else 0,
            'available_mb': (user_storage.max_storage - user_storage.used_storage) / 1024 / 1024
        })
        
        return plan_info
    
    @staticmethod
    def get_available_plans():
        """Get all available subscription plans"""
        return SubscriptionPlan.objects.filter(
            is_active=True,
            plan_type='storage'
        ).order_by('price')
    
    @staticmethod
    def sync_all_users():
        """Sync storage for all users - useful for management commands"""
        users = User.objects.all()
        updated_count = 0
        
        for user in users:
            try:
                StorageSubscriptionSync.sync_user_storage(user)
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to sync user {user.id}: {str(e)}")
        
        logger.info(f"Synced storage for {updated_count} users")
        return updated_count