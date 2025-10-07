"""
Management command to set up WorkLoom Founder's Access plans
Run: python manage.py setup_workloom_plans
"""

from django.core.management.base import BaseCommand
from payments.models import SubscriptionPlan
from decimal import Decimal


class Command(BaseCommand):
    help = 'Set up WorkLoom Founder\'s Early Access plans (FREE during beta)'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up WorkLoom Founder\'s Access Plans...')
        )

        plans = [
            {
                'name': 'WorkLoom Founder Access (Monatlich)',
                'plan_type': 'founder_access',
                'price': Decimal('0.00'),  # KOSTENLOS während Early Access
                'currency': 'EUR',
                'interval': 'month',
                'stripe_price_id': 'price_workloom_monthly_free',  # Platzhalter
                'features': {
                    'regular_price': '24.99',  # Regulärer Preis (später)
                    'all_features': True,
                    'apps': [
                        'ChatFlow Enterprise',
                        'WorkSpace (Notizen, Kalender, Ideenboards)',
                        'ShopifyFlow Manager',
                        'ToDo Manager',
                        'VideoFlow Hosting',
                        'FileShare',
                        'StreamRec Studio',
                        'PromptPro (KI-Tools)'
                    ],
                    'note': 'Video-Speicher separat erhältlich'
                },
                'is_active': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created: {plan.name} - {plan.price}€/{plan.interval}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'🔄 Updated: {plan.name} - {plan.price}€/{plan.interval}')
                )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'📊 Summary: {created_count} created, {updated_count} updated')
        )

        # Show all active WorkLoom plans
        self.stdout.write('')
        self.stdout.write('📋 Active WorkLoom Plans:')
        for plan in SubscriptionPlan.objects.filter(plan_type='founder_access', is_active=True):
            self.stdout.write(
                f'   {plan.name}: {plan.price}€/{plan.interval}'
            )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ WorkLoom Founder\'s Access setup completed!')
        )
        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING('⚠️  WICHTIG: Diese Pläne sind KOSTENLOS während der Early Access Phase!')
        )
        self.stdout.write(
            '   Nach der Beta-Phase können Preise über das Admin-Interface angepasst werden.'
        )
