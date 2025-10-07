"""
Management command to activate WorkLoom Founder Access for all existing users
Run: python manage.py activate_founder_access
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from payments.models import SubscriptionPlan, Customer, Subscription

User = get_user_model()


class Command(BaseCommand):
    help = 'Activate FREE WorkLoom Founder Access for all existing users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - No changes will be made')
            )

        self.stdout.write(
            self.style.SUCCESS('🚀 Activating WorkLoom Founder Access for all users...')
        )
        self.stdout.write('')

        # Get the free WorkLoom Founder Access plan (monthly)
        founder_plan = SubscriptionPlan.objects.filter(
            plan_type='founder_access',
            price=0,
            interval='month',
            is_active=True
        ).first()

        if not founder_plan:
            self.stdout.write(
                self.style.ERROR('❌ No free WorkLoom Founder Access plan found!')
            )
            self.stdout.write('   Run: python manage.py setup_workloom_plans')
            self.stdout.write('')
            self.stdout.write('   Expected plan:')
            self.stdout.write('   - Name: WorkLoom Founder Access (Monatlich)')
            self.stdout.write('   - Type: founder_access')
            self.stdout.write('   - Price: 0.00€')
            self.stdout.write('   - Interval: month')
            return

        self.stdout.write(f'📋 Found plan: {founder_plan.name} (0€/month)')
        self.stdout.write('')

        total_users = User.objects.count()
        activated_count = 0
        already_active_count = 0
        error_count = 0

        for user in User.objects.all():
            try:
                # Get or create Customer
                customer, customer_created = Customer.objects.get_or_create(
                    user=user,
                    defaults={'stripe_customer_id': None}
                )

                # Check if already has subscription
                existing_sub = Subscription.objects.filter(
                    customer=customer,
                    plan=founder_plan
                ).exists()

                if existing_sub:
                    already_active_count += 1
                    self.stdout.write(
                        f'  ℹ️  {user.username}: Already has Founder Access'
                    )
                else:
                    if not dry_run:
                        # Create free subscription
                        Subscription.objects.create(
                            customer=customer,
                            plan=founder_plan,
                            stripe_subscription_id=None,
                            status='active',
                            current_period_end=None,
                            cancel_at_period_end=False,
                        )

                    activated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ {user.username}: Activated Founder Access')
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ❌ {user.username}: Error - {str(e)}')
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('━' * 60))
        self.stdout.write('📊 Summary:')
        self.stdout.write(f'   Total users: {total_users}')
        self.stdout.write(
            self.style.SUCCESS(f'   ✅ Newly activated: {activated_count}')
        )
        self.stdout.write(f'   ℹ️  Already active: {already_active_count}')
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Errors: {error_count}')
            )

        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN - Run without --dry-run to apply changes')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('🎉 WorkLoom Founder Access activation completed!')
            )
            self.stdout.write('')
            self.stdout.write('💡 New users will automatically get Founder Access upon signup!')
