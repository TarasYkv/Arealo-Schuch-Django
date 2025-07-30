from django.core.management.base import BaseCommand
from email_templates.trigger_manager import trigger_manager


class Command(BaseCommand):
    help = 'Synchronize email triggers from registry to database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update of existing triggers',
        )

    def handle(self, *args, **options):
        self.stdout.write("Synchronizing email triggers...")
        
        synced_count = trigger_manager.sync_triggers_to_database()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully synchronized {synced_count} email triggers'
            )
        )
        
        # Show summary of all triggers
        from email_templates.models import EmailTrigger
        
        self.stdout.write("\n=== Email Triggers Summary ===")
        for category in EmailTrigger.CATEGORY_CHOICES:
            category_key, category_name = category
            triggers = EmailTrigger.objects.filter(category=category_key)
            if triggers.exists():
                self.stdout.write(f"\n{category_name}:")
                for trigger in triggers:
                    status = "✓ Active" if trigger.is_active else "✗ Inactive"
                    self.stdout.write(f"  - {trigger.name} ({trigger.trigger_key}) - {status}")
        
        # Show templates without triggers
        from email_templates.models import EmailTemplate
        templates_without_triggers = EmailTemplate.objects.filter(trigger=None, is_active=True)
        if templates_without_triggers.exists():
            self.stdout.write(f"\n⚠️  Templates ohne Trigger ({templates_without_triggers.count()}):")
            for template in templates_without_triggers:
                self.stdout.write(f"  - {template.name} ({template.template_type})")