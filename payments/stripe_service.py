import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Customer, Subscription, SubscriptionPlan, Invoice, PaymentMethod, WebhookEvent
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    
    @staticmethod
    def get_or_create_customer(user):
        """Get or create Stripe customer for user"""
        try:
            customer, created = Customer.objects.get_or_create(
                user=user,
                defaults={
                    'stripe_customer_id': ''
                }
            )
            
            if created or not customer.stripe_customer_id:
                stripe_customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}".strip() or user.username,
                    metadata={'user_id': user.id}
                )
                customer.stripe_customer_id = stripe_customer.id
                customer.save()
                logger.info(f"Created Stripe customer {stripe_customer.id} for user {user.id}")
            
            return customer
        except Exception as e:
            logger.error(f"Error creating Stripe customer for user {user.id}: {str(e)}")
            raise
    
    @staticmethod
    def create_checkout_session(user, plan_id, success_url, cancel_url):
        """Create Stripe checkout session for subscription"""
        try:
            customer = StripeService.get_or_create_customer(user)
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            
            # Check if plan has trial days configured
            subscription_data = {}
            if plan.plan_type == 'founder_access' and plan.features.get('trial_days'):
                subscription_data['trial_period_days'] = plan.features['trial_days']
            
            session = stripe.checkout.Session.create(
                customer=customer.stripe_customer_id,
                payment_method_types=['card', 'sepa_debit'],
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data=subscription_data if subscription_data else None,
                metadata={
                    'user_id': user.id,
                    'plan_id': plan.id
                }
            )
            
            logger.info(f"Created checkout session {session.id} for user {user.id} and plan {plan.id}")
            return session
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise
    
    @staticmethod
    def create_customer_portal_session(user, return_url):
        """Create Stripe customer portal session"""
        try:
            customer = Customer.objects.get(user=user)
            
            session = stripe.billing_portal.Session.create(
                customer=customer.stripe_customer_id,
                return_url=return_url,
            )
            
            return session
        except Customer.DoesNotExist:
            logger.error(f"Customer not found for user {user.id}")
            raise
        except Exception as e:
            logger.error(f"Error creating portal session: {str(e)}")
            raise
    
    @staticmethod
    def sync_subscription_from_stripe(stripe_subscription_id):
        """Sync subscription data from Stripe"""
        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
            customer = Customer.objects.get(stripe_customer_id=stripe_sub.customer)
            
            # Get the plan based on the price ID
            price_id = stripe_sub['items']['data'][0]['price']['id']
            plan = SubscriptionPlan.objects.get(stripe_price_id=price_id)
            
            # Handle different subscription states
            defaults = {
                'customer': customer,
                'plan': plan,
                'status': stripe_sub.status,
                'cancel_at_period_end': stripe_sub.cancel_at_period_end,
                'canceled_at': timezone.datetime.fromtimestamp(
                    stripe_sub.canceled_at
                ) if stripe_sub.canceled_at else None,
            }
            
            # Handle trial subscriptions differently
            if stripe_sub.status == 'trialing' and stripe_sub.trial_start and stripe_sub.trial_end:
                defaults.update({
                    'current_period_start': timezone.datetime.fromtimestamp(stripe_sub.trial_start),
                    'current_period_end': timezone.datetime.fromtimestamp(stripe_sub.trial_end),
                    'trial_start': timezone.datetime.fromtimestamp(stripe_sub.trial_start),
                    'trial_end': timezone.datetime.fromtimestamp(stripe_sub.trial_end),
                })
            elif hasattr(stripe_sub, 'current_period_start') and hasattr(stripe_sub, 'current_period_end'):
                defaults.update({
                    'current_period_start': timezone.datetime.fromtimestamp(stripe_sub.current_period_start),
                    'current_period_end': timezone.datetime.fromtimestamp(stripe_sub.current_period_end),
                    'trial_start': timezone.datetime.fromtimestamp(
                        stripe_sub.trial_start
                    ) if stripe_sub.trial_start else None,
                    'trial_end': timezone.datetime.fromtimestamp(
                        stripe_sub.trial_end
                    ) if stripe_sub.trial_end else None,
                })
            else:
                # Fallback for incomplete data
                defaults.update({
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timezone.timedelta(days=30),
                    'trial_start': None,
                    'trial_end': None,
                })
            
            subscription, created = Subscription.objects.update_or_create(
                stripe_subscription_id=stripe_subscription_id,
                defaults=defaults
            )
            
            logger.info(f"Synced subscription {stripe_subscription_id} for customer {customer.id}")
            return subscription
        except Exception as e:
            logger.error(f"Error syncing subscription {stripe_subscription_id}: {str(e)}")
            raise
    
    @staticmethod
    def sync_invoice_from_stripe(stripe_invoice_id):
        """Sync invoice data from Stripe"""
        try:
            stripe_invoice = stripe.Invoice.retrieve(stripe_invoice_id)
            customer = Customer.objects.get(stripe_customer_id=stripe_invoice.customer)
            
            subscription = None
            if stripe_invoice.subscription:
                try:
                    subscription = Subscription.objects.get(
                        stripe_subscription_id=stripe_invoice.subscription
                    )
                except Subscription.DoesNotExist:
                    pass
            
            invoice, created = Invoice.objects.update_or_create(
                stripe_invoice_id=stripe_invoice_id,
                defaults={
                    'customer': customer,
                    'subscription': subscription,
                    'status': stripe_invoice.status,
                    'amount_due': stripe_invoice.amount_due / 100,  # Convert from cents
                    'amount_paid': stripe_invoice.amount_paid / 100,
                    'currency': stripe_invoice.currency.upper(),
                    'invoice_url': stripe_invoice.hosted_invoice_url or '',
                    'invoice_pdf': stripe_invoice.invoice_pdf or '',
                    'due_date': timezone.datetime.fromtimestamp(
                        stripe_invoice.due_date, tz=timezone.utc
                    ) if stripe_invoice.due_date else None,
                    'paid_at': timezone.datetime.fromtimestamp(
                        stripe_invoice.status_transitions.paid_at, tz=timezone.utc
                    ) if stripe_invoice.status_transitions.paid_at else None,
                }
            )
            
            logger.info(f"Synced invoice {stripe_invoice_id} for customer {customer.id}")
            return invoice
        except Exception as e:
            logger.error(f"Error syncing invoice {stripe_invoice_id}: {str(e)}")
            raise
    
    @staticmethod
    def cancel_subscription(subscription_id, at_period_end=True):
        """Cancel a subscription"""
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            
            if at_period_end:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                subscription.cancel_at_period_end = True
                subscription.save()
            else:
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                subscription.status = 'canceled'
                subscription.canceled_at = timezone.now()
                subscription.save()
            
            logger.info(f"Canceled subscription {subscription_id}")
            return subscription
        except Exception as e:
            logger.error(f"Error canceling subscription {subscription_id}: {str(e)}")
            raise