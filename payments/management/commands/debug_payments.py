"""
Debug command for payments system on PythonAnywhere
Run: python manage.py debug_payments
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from payments.models import SubscriptionPlan, Customer, Subscription
from videos.models import UserStorage
from django.db import models
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Debug payments system configuration and data'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 Payments System Debug Report')
        )
        self.stdout.write('=' * 60)
        
        # 1. Environment Check
        self.stdout.write('\n📋 1. Environment Configuration:')
        self.stdout.write('-' * 40)
        
        env_file_exists = os.path.exists('.env')
        self.stdout.write(f'   .env file exists: {env_file_exists}')
        
        stripe_secret = getattr(settings, 'STRIPE_SECRET_KEY', None)
        stripe_public = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', None)
        stripe_webhook = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        
        self.stdout.write(f'   STRIPE_SECRET_KEY configured: {bool(stripe_secret and not stripe_secret.startswith("sk_test_51234"))}')
        self.stdout.write(f'   STRIPE_PUBLISHABLE_KEY configured: {bool(stripe_public and not stripe_public.startswith("pk_test_51234"))}')
        self.stdout.write(f'   STRIPE_WEBHOOK_SECRET configured: {bool(stripe_webhook and not stripe_webhook.startswith("whsec_1234"))}')
        
        if stripe_secret:
            key_type = "Live" if stripe_secret.startswith('sk_live_') else "Test"
            self.stdout.write(f'   Stripe Key Type: {key_type}')
        
        # 2. Database Check
        self.stdout.write('\n📋 2. Database Content:')
        self.stdout.write('-' * 40)
        
        plans_count = SubscriptionPlan.objects.count()
        customers_count = Customer.objects.count()
        subscriptions_count = Subscription.objects.count()
        users_count = User.objects.count()
        storage_count = UserStorage.objects.count()
        
        self.stdout.write(f'   Subscription Plans: {plans_count}')
        self.stdout.write(f'   Stripe Customers: {customers_count}')
        self.stdout.write(f'   Stripe Subscriptions: {subscriptions_count}')
        self.stdout.write(f'   Total Users: {users_count}')
        self.stdout.write(f'   User Storage Entries: {storage_count}')
        
        # 3. Subscription Plans Detail
        if plans_count > 0:
            self.stdout.write('\n📋 3. Subscription Plans Details:')
            self.stdout.write('-' * 40)
            
            for plan in SubscriptionPlan.objects.all().order_by('plan_type', 'price'):
                status = "✅ Active" if plan.is_active else "❌ Inactive"
                self.stdout.write(f'   {plan.name} ({plan.plan_type}):')
                self.stdout.write(f'      Price: {plan.price}€/{plan.interval}')
                self.stdout.write(f'      Stripe ID: {plan.stripe_price_id}')
                self.stdout.write(f'      Status: {status}')
                if plan.storage_mb:
                    self.stdout.write(f'      Storage: {plan.storage_mb}MB')
                self.stdout.write('')
        else:
            self.stdout.write('\n❌ 3. No Subscription Plans Found!')
            self.stdout.write('   Run: python manage.py setup_subscription_plans')
        
        # 4. UserStorage Check
        self.stdout.write('\n📋 4. User Storage Analysis:')
        self.stdout.write('-' * 40)
        
        if storage_count > 0:
            free_users = UserStorage.objects.filter(is_premium=False).count()
            premium_users = UserStorage.objects.filter(is_premium=True).count()
            exceeded_users = UserStorage.objects.filter(used_storage__gt=models.F('max_storage')).count()
            
            self.stdout.write(f'   Free plan users: {free_users}')
            self.stdout.write(f'   Premium users: {premium_users}')
            self.stdout.write(f'   Users exceeding storage: {exceeded_users}')
            
            # Show some examples
            sample_storage = UserStorage.objects.select_related('user').first()
            if sample_storage:
                self.stdout.write(f'\n   Sample user ({sample_storage.user.username}):')
                self.stdout.write(f'      Storage: {sample_storage.get_used_storage_mb():.1f}MB / {sample_storage.get_max_storage_mb():.1f}MB')
                self.stdout.write(f'      Premium: {sample_storage.is_premium}')
        else:
            self.stdout.write('   ❌ No UserStorage entries found!')
            self.stdout.write('   Run: python manage.py setup_free_plans')
        
        # 5. Common Issues & Solutions
        self.stdout.write('\n📋 5. Common Issues & Solutions:')
        self.stdout.write('-' * 40)
        
        issues_found = []
        
        if plans_count == 0:
            issues_found.append("No subscription plans in database")
            self.stdout.write('   ❌ Missing subscription plans')
            self.stdout.write('      Solution: python manage.py setup_subscription_plans')
        
        if storage_count < users_count:
            issues_found.append("Some users missing UserStorage")
            self.stdout.write('   ❌ Some users missing storage entries')
            self.stdout.write('      Solution: python manage.py setup_free_plans')
        
        if not stripe_secret or stripe_secret.startswith("sk_test_51234"):
            issues_found.append("Stripe keys not configured")
            self.stdout.write('   ❌ Stripe keys not properly configured')
            self.stdout.write('      Solution: Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY in .env')
        
        if not issues_found:
            self.stdout.write('   ✅ No obvious issues found!')
        
        # 6. Quick Fix Commands
        self.stdout.write('\n📋 6. Quick Fix Commands:')
        self.stdout.write('-' * 40)
        self.stdout.write('   Create plans: python manage.py setup_subscription_plans')
        self.stdout.write('   Setup free storage: python manage.py setup_free_plans')
        self.stdout.write('   Check migrations: python manage.py migrate')
        self.stdout.write('   Test system: python manage.py shell')
        
        self.stdout.write('\n' + '=' * 60)
        if issues_found:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Found {len(issues_found)} issues to resolve')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ System appears to be configured correctly!')
            )