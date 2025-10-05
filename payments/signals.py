from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Subscription, SubscriptionPlan, Customer
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Subscription)
def sync_storage_on_subscription_update(sender, instance, created, **kwargs):
    """Sync video storage when subscription is created or updated"""
    try:
        from videos.subscription_sync import StorageSubscriptionSync
        StorageSubscriptionSync.sync_user_storage(instance.customer.user)
        logger.info(f"Synced storage for user {instance.customer.user.id} after subscription update")
    except Exception as e:
        logger.error(f"Error syncing storage after subscription update: {str(e)}")


@receiver(post_delete, sender=Subscription)
def sync_storage_on_subscription_delete(sender, instance, **kwargs):
    """Sync video storage when subscription is deleted"""
    try:
        from videos.subscription_sync import StorageSubscriptionSync
        StorageSubscriptionSync.sync_user_storage(instance.customer.user)
        logger.info(f"Synced storage for user {instance.customer.user.id} after subscription deletion")
    except Exception as e:
        logger.error(f"Error syncing storage after subscription deletion: {str(e)}")


@receiver(post_save, sender=User)
def activate_founder_access_on_signup(sender, instance, created, **kwargs):
    """
    Automatically activate WorkLoom Founder's Access for new users
    during Early Access Phase - NO payment required!
    """
    if created:
        try:
            # Get or create Customer
            customer, customer_created = Customer.objects.get_or_create(
                user=instance,
                defaults={
                    'stripe_customer_id': None,  # No Stripe needed for free plan
                }
            )

            if customer_created:
                logger.info(f"✅ Created Customer for new user: {instance.username}")

            # Get the free WorkLoom Founder Access plan (monthly)
            founder_plan = SubscriptionPlan.objects.filter(
                plan_type='founder_access',
                price=0,
                interval='month',
                is_active=True
            ).first()

            if founder_plan:
                # Check if subscription already exists
                existing_sub = Subscription.objects.filter(
                    customer=customer,
                    plan=founder_plan
                ).exists()

                if not existing_sub:
                    # Create free subscription (no Stripe subscription needed)
                    subscription = Subscription.objects.create(
                        customer=customer,
                        plan=founder_plan,
                        stripe_subscription_id=None,  # No Stripe needed for free
                        status='active',
                        current_period_end=None,  # No end date for free tier
                        cancel_at_period_end=False,
                    )

                    logger.info(
                        f"🎉 Activated FREE WorkLoom Founder Access for {instance.username} - "
                        f"No payment required!"
                    )
                else:
                    logger.info(
                        f"WorkLoom Founder Access already exists for {instance.username}"
                    )
            else:
                logger.warning(
                    f"⚠️  No free WorkLoom Founder Access plan found! "
                    f"Run: python manage.py setup_workloom_plans"
                )

        except Exception as e:
            logger.error(
                f"❌ Failed to activate Founder Access for {instance.username}: {str(e)}"
            )