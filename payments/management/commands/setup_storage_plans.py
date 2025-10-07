"""
Management Command: Setup Storage Plans
========================================
Erstellt/aktualisiert Storage-Subscription-Plans in der Datenbank

WICHTIG: Vor Ausführung müssen die Stripe Price IDs in Stripe Dashboard erstellt werden!

Usage:
    python manage.py setup_storage_plans
"""

from django.core.management.base import BaseCommand
from payments.models import SubscriptionPlan
from decimal import Decimal


class Command(BaseCommand):
    help = 'Erstellt Storage-Subscription-Plans mit monatlichen und jährlichen Intervallen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Aktualisiert existierende Pläne statt nur neue zu erstellen',
        )

    def handle(self, *args, **options):
        update_existing = options.get('update', False)

        # Storage Plans - Nur Monatlich
        # WICHTIG: Stripe Price IDs müssen im Stripe Dashboard erstellt werden!
        plans = [
            # ========== KOSTENLOS ==========
            {
                'name': 'Kostenlos (100MB)',
                'stripe_price_id': 'price_free_storage',  # Dummy ID - wird nicht verwendet
                'plan_type': 'storage',
                'price': Decimal('0.00'),
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 100,
                'features': {
                    'storage': '100MB Speicher',
                    'apps': 'Videos, Fileshare, Streamrec',
                    'support': 'Community Support'
                },
                'is_active': True,
            },

            # ========== 1GB PLAN ==========
            {
                'name': '1GB Plan (Monatlich)',
                'stripe_price_id': 'price_1gb_monthly',  # TODO: Aus Stripe Dashboard einfügen
                'plan_type': 'storage',
                'price': Decimal('2.99'),
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 1024,
                'features': {
                    'storage': '1GB Speicher',
                    'apps': 'Videos, Fileshare, Streamrec',
                    'support': 'E-Mail Support',
                    'analytics': 'Basis-Statistiken'
                },
                'is_active': True,
            },

            # ========== 3GB PLAN ==========
            {
                'name': '3GB Plan (Monatlich)',
                'stripe_price_id': 'price_3gb_monthly',  # TODO: Aus Stripe Dashboard einfügen
                'plan_type': 'storage',
                'price': Decimal('4.99'),
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 3072,
                'features': {
                    'storage': '3GB Speicher',
                    'apps': 'Videos, Fileshare, Streamrec',
                    'support': 'E-Mail Support',
                    'analytics': 'Erweiterte Statistiken',
                    'priority': 'Höhere Upload-Priorität'
                },
                'is_active': True,
            },

            # ========== 5GB PLAN ==========
            {
                'name': '5GB Plan (Monatlich)',
                'stripe_price_id': 'price_5gb_monthly',  # TODO: Aus Stripe Dashboard einfügen
                'plan_type': 'storage',
                'price': Decimal('7.99'),
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 5120,
                'features': {
                    'storage': '5GB Speicher',
                    'apps': 'Videos, Fileshare, Streamrec',
                    'support': 'Prioritäts-Support',
                    'analytics': 'Erweiterte Statistiken',
                    'priority': 'Höchste Upload-Priorität',
                    'custom_branding': 'Custom Branding (optional)'
                },
                'is_active': True,
            },

            # ========== 10GB PLAN ==========
            {
                'name': '10GB Plan (Monatlich)',
                'stripe_price_id': 'price_10gb_monthly',  # TODO: Aus Stripe Dashboard einfügen
                'plan_type': 'storage',
                'price': Decimal('9.99'),
                'currency': 'EUR',
                'interval': 'month',
                'storage_mb': 10240,
                'features': {
                    'storage': '10GB Speicher',
                    'apps': 'Videos, Fileshare, Streamrec',
                    'support': 'VIP-Support',
                    'analytics': 'Pro-Statistiken',
                    'priority': 'Höchste Upload-Priorität',
                    'custom_branding': 'Full Custom Branding',
                    'api_access': 'API Zugriff',
                    'backup': 'Automatische Backups'
                },
                'is_active': True,
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING('Setting up Storage Plans...'))
        self.stdout.write('')

        for plan_data in plans:
            try:
                plan, created = SubscriptionPlan.objects.get_or_create(
                    stripe_price_id=plan_data['stripe_price_id'],
                    defaults=plan_data
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created: {plan.name} ({plan.price}€/{plan.interval})')
                    )
                elif update_existing:
                    # Update existing plan
                    for key, value in plan_data.items():
                        setattr(plan, key, value)
                    plan.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Updated: {plan.name} ({plan.price}€/{plan.interval})')
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.NOTICE(f'- Skipped (exists): {plan.name}')
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error creating {plan_data["name"]}: {str(e)}')
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== Summary ==='))
        self.stdout.write(f'Created: {created_count}')
        self.stdout.write(f'Updated: {updated_count}')
        self.stdout.write(f'Skipped: {skipped_count}')
        self.stdout.write('')

        if created_count > 0 or updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS('✓ Storage Plans setup completed!')
            )

        # Important reminder
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('WICHTIG: Stripe Price IDs müssen im Stripe Dashboard erstellt werden!'))
        self.stdout.write('Anleitung:')
        self.stdout.write('1. Gehe zu https://dashboard.stripe.com/products')
        self.stdout.write('2. Erstelle für jede Storage-Größe ein Product (1GB, 3GB, 5GB, 10GB)')
        self.stdout.write('3. Für jedes Product erstelle 2 Prices (monatlich & jährlich)')
        self.stdout.write('4. Kopiere die Price IDs und trage sie in payments/management/commands/setup_storage_plans.py ein')
        self.stdout.write('5. Führe den Command erneut aus mit --update Flag')
