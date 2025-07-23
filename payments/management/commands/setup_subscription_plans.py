"""
Management command to create all subscription plans with correct Stripe IDs
Run on PythonAnywhere after deployment: python manage.py setup_subscription_plans
"""

from django.core.management.base import BaseCommand
from payments.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Create or update all subscription plans with Stripe Price IDs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing plans and recreate them',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        
        if reset:
            self.stdout.write('🗑️ Deleting existing subscription plans...')
            SubscriptionPlan.objects.all().delete()
        
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up subscription plans...')
        )
        
        # Define all plans with their Stripe IDs
        plans_data = [
            {
                'name': 'Kostenlos',
                'stripe_price_id': 'price_1Rny93GDxp57VS6VJ1vHsTYd',
                'plan_type': 'storage',
                'price': 0.00,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 50,
                'features': {
                    'video_uploads': True,
                    'cloud_storage': True,
                    'free_plan': True
                },
                'is_active': True
            },
            {
                'name': '1GB Plan', 
                'stripe_price_id': 'price_1RnvClGDxp57VS6VmmuJoLa7',
                'plan_type': 'storage',
                'price': 1.99,
                'currency': 'EUR', 
                'interval': 'month',
                'storage_mb': 1024,
                'features': {
                    'video_uploads': True,
                    'cloud_storage': True,
                    'priority_support': False
                },
                'is_active': True
            },
            {
                'name': '2GB Plan',
                'stripe_price_id': 'price_1RnvDVGDxp57VS6V9pSpxSbs',
                'plan_type': 'storage',
                'price': 2.99,
                'currency': 'EUR',
                'interval': 'month', 
                'storage_mb': 2048,
                'features': {
                    'video_uploads': True,
                    'cloud_storage': True,
                    'priority_support': False
                },
                'is_active': True
            },
            {
                'name': '5GB Plan',
                'stripe_price_id': 'price_1RnvEGGDxp57VS6V6bX1EIVV',
                'plan_type': 'storage',
                'price': 6.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 5120,
                'features': {
                    'video_uploads': True,
                    'cloud_storage': True,
                    'priority_support': True
                },
                'is_active': True
            },
            {
                'name': '10GB Plan',
                'stripe_price_id': 'price_1RnvIAGDxp57VS6Vp9epBJEN', 
                'plan_type': 'storage',
                'price': 9.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 10240,
                'features': {
                    'video_uploads': True,
                    'cloud_storage': True,
                    'priority_support': True,
                    'advanced_analytics': True
                },
                'is_active': True
            },
            {
                'name': 'WorkLoom - Founder\'s Early Access',
                'stripe_price_id': 'price_1RnvgQGDxp57VS6VN2kIFL4V',
                'plan_type': 'founder_access',
                'price': 9.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': None,  # No storage included
                'features': {
                    'unlimited_storage': False,
                    'all_apps_access': True,
                    'priority_support': True,
                    'trial_days': 3,
                    'apps': ['chat', 'videos', 'shopify_manager', 'image_editor', 'naturmacher', 'organization', 'todos', 'pdf_sucher', 'amortization_calculator', 'sportplatzApp'],
                    'regular_price': '19.99',
                    'early_access_discount': True,
                    'storage_info': 'Video-Speicherplatz separat erhältlich'
                },
                'is_active': True
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.get_or_create(
                stripe_price_id=plan_data['stripe_price_id'],
                defaults=plan_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'✅ Created: {plan.name}')
            else:
                # Update existing plan
                for key, value in plan_data.items():
                    if key != 'stripe_price_id':  # Don't update the ID
                        setattr(plan, key, value)
                plan.save()
                updated_count += 1
                self.stdout.write(f'🔄 Updated: {plan.name}')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'📊 Summary:')
        )
        self.stdout.write(f'   Plans created: {created_count}')
        self.stdout.write(f'   Plans updated: {updated_count}')
        self.stdout.write(f'   Total plans: {SubscriptionPlan.objects.count()}')
        
        # Show current plans
        self.stdout.write('')
        self.stdout.write('📋 Current Subscription Plans:')
        
        workloom_plans = SubscriptionPlan.objects.filter(plan_type='founder_access')
        storage_plans = SubscriptionPlan.objects.filter(plan_type='storage').order_by('price')
        
        self.stdout.write('')
        self.stdout.write('🚀 WorkLoom Plans:')
        for plan in workloom_plans:
            self.stdout.write(f'   - {plan.name}: {plan.price}€/{plan.interval}')
            self.stdout.write(f'     ID: {plan.stripe_price_id}')
        
        self.stdout.write('')
        self.stdout.write('💾 Storage Plans:')
        for plan in storage_plans:
            self.stdout.write(f'   - {plan.name}: {plan.price}€/{plan.interval}')
            self.stdout.write(f'     Storage: {plan.storage_mb}MB')
            self.stdout.write(f'     ID: {plan.stripe_price_id}')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ Subscription plans setup completed!')
        )
        self.stdout.write('')
        self.stdout.write('💡 Next steps:')
        self.stdout.write('   1. Test the plans page: /payments/plans/')
        self.stdout.write('   2. Verify Stripe integration works')
        self.stdout.write('   3. Test free plan assignment for new users')