from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from payments.models import Customer, Subscription
from payments.stripe_service import StripeService
import stripe
from django.conf import settings

User = get_user_model()


class Command(BaseCommand):
    help = 'Manually sync all Stripe subscriptions to local database'

    def handle(self, *args, **options):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        self.stdout.write(self.style.SUCCESS('🔄 Starting Stripe subscription sync...'))
        
        # Get all customers
        customers = Customer.objects.all()
        total_synced = 0
        
        for customer in customers:
            self.stdout.write(f'📋 Processing customer: {customer.user.username} ({customer.stripe_customer_id})')
            
            try:
                # Get subscriptions from Stripe
                subscriptions = stripe.Subscription.list(customer=customer.stripe_customer_id)
                
                for stripe_sub in subscriptions.data:
                    self.stdout.write(f'  🔄 Syncing subscription: {stripe_sub.id} ({stripe_sub.status})')
                    
                    try:
                        local_sub = StripeService.sync_subscription_from_stripe(stripe_sub.id)
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✅ Synced: {local_sub.plan.name} ({local_sub.status})')
                        )
                        total_synced += 1
                    except Exception as sync_error:
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Sync failed: {str(sync_error)}')
                        )
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error processing customer {customer.stripe_customer_id}: {str(e)}')
                )
        
        # Show summary
        active_subs = Subscription.objects.filter(status__in=['active', 'trialing']).count()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'🎉 Sync completed!'))
        self.stdout.write(f'📊 Total subscriptions synced: {total_synced}')
        self.stdout.write(f'📊 Active subscriptions in database: {active_subs}')
        
        if active_subs > 0:
            self.stdout.write('')
            self.stdout.write('📋 Active subscriptions:')
            for sub in Subscription.objects.filter(status__in=['active', 'trialing']):
                trial_info = f' (Trial ends: {sub.trial_end})' if sub.trial_end else ''
                self.stdout.write(f'  - {sub.customer.user.username}: {sub.plan.name} ({sub.status}){trial_info}')