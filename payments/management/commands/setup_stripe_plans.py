from django.core.management.base import BaseCommand
from payments.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Create initial subscription plans'

    def handle(self, *args, **options):
        plans = [
            {
                'name': 'Kostenlos',
                'stripe_price_id': 'price_free_plan',  # Replace with actual Stripe price ID
                'plan_type': 'storage',
                'price': 0.00,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 50,
                'features': {
                    'video_hosting': 'Basic video hosting',
                    'support': 'Community support'
                }
            },
            {
                'name': '1GB Plan',
                'stripe_price_id': 'price_1gb_plan',  # Replace with actual Stripe price ID
                'plan_type': 'storage',
                'price': 1.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 1024,
                'features': {
                    'video_hosting': 'Enhanced video hosting',
                    'support': 'Email support',
                    'analytics': 'Basic analytics'
                }
            },
            {
                'name': '2GB Plan',
                'stripe_price_id': 'price_2gb_plan',  # Replace with actual Stripe price ID
                'plan_type': 'storage',
                'price': 2.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 2048,
                'features': {
                    'video_hosting': 'Enhanced video hosting',
                    'support': 'Email support',
                    'analytics': 'Advanced analytics',
                    'custom_branding': 'Custom branding options'
                }
            },
            {
                'name': '5GB Plan',
                'stripe_price_id': 'price_5gb_plan',  # Replace with actual Stripe price ID
                'plan_type': 'storage',
                'price': 6.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 5120,
                'features': {
                    'video_hosting': 'Premium video hosting',
                    'support': 'Priority support',
                    'analytics': 'Advanced analytics',
                    'custom_branding': 'Full custom branding',
                    'api_access': 'API access'
                }
            },
            {
                'name': '10GB Plan',
                'stripe_price_id': 'price_10gb_plan',  # Replace with actual Stripe price ID
                'plan_type': 'storage',
                'price': 9.99,
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 10240,
                'features': {
                    'video_hosting': 'Premium video hosting',
                    'support': 'Priority support',
                    'analytics': 'Advanced analytics',
                    'custom_branding': 'Full custom branding',
                    'api_access': 'Full API access',
                    'backup': 'Automated backups'
                }
            }
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created plan: {plan.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Plan already exists: {plan.name}')
                )