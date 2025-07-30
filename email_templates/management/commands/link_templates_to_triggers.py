from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplate, EmailTrigger


class Command(BaseCommand):
    help = 'Link existing email templates to appropriate triggers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be linked without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("=== DRY RUN - No changes will be made ===\n")
        
        # Define mapping of template_type to trigger_key
        template_trigger_mapping = {
            'account_activation': 'account_activation',
            'welcome': 'welcome_email',
            'password_reset': 'password_reset',
            'order_confirmation': 'order_confirmation',
            'order_shipped': 'order_shipped',
            'order_delivered': 'order_delivered',  # This trigger would need to be created
            'order_cancelled': 'order_cancelled',   # This trigger would need to be created
            'invoice': 'invoice_created',          # This trigger would need to be created
            'reminder': 'event_reminder',
            'newsletter': None,  # Newsletter doesn't map to automatic triggers
        }
        
        linked_count = 0
        skipped_count = 0
        
        # Get all templates without triggers
        templates_without_triggers = EmailTemplate.objects.filter(trigger=None)
        
        self.stdout.write(f"Found {templates_without_triggers.count()} templates without triggers\n")
        
        for template in templates_without_triggers:
            trigger_key = template_trigger_mapping.get(template.template_type)
            
            if trigger_key:
                try:
                    trigger = EmailTrigger.objects.get(trigger_key=trigger_key)
                    
                    if not dry_run:
                        template.trigger = trigger
                        template.save()
                    
                    self.stdout.write(
                        f"{'[DRY RUN] Would link' if dry_run else 'Linked'} template '{template.name}' "
                        f"({template.template_type}) to trigger '{trigger.name}' ({trigger.trigger_key})"
                    )
                    linked_count += 1
                    
                except EmailTrigger.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Trigger '{trigger_key}' not found for template '{template.name}' "
                            f"({template.template_type})"
                        )
                    )
                    skipped_count += 1
            else:
                self.stdout.write(
                    f"No trigger mapping for template '{template.name}' ({template.template_type})"
                )
                skipped_count += 1
        
        # Create missing triggers for e-commerce
        missing_triggers = [
            {
                'key': 'order_delivered',
                'name': 'Lieferbestätigung',
                'description': 'Bestellung wurde erfolgreich geliefert',
                'category': 'ecommerce',
                'variables': {
                    'customer_name': 'Kundenname',
                    'order_number': 'Bestellnummer',
                    'delivery_date': 'Lieferdatum',
                    'delivery_address': 'Lieferadresse',
                    'feedback_url': 'Bewertungs-Link'
                }
            },
            {
                'key': 'order_cancelled',
                'name': 'Stornierungsbestätigung',
                'description': 'Bestellung wurde storniert',
                'category': 'ecommerce',
                'variables': {
                    'customer_name': 'Kundenname',
                    'order_number': 'Bestellnummer',
                    'cancellation_reason': 'Stornierungsgrund',
                    'refund_info': 'Erstattungsinformationen',
                    'refund_amount': 'Erstattungsbetrag'
                }
            },
            {
                'key': 'invoice_created',
                'name': 'Rechnung erstellt',
                'description': 'Neue Rechnung wurde erstellt',
                'category': 'ecommerce',
                'variables': {
                    'customer_name': 'Kundenname',
                    'invoice_number': 'Rechnungsnummer',
                    'invoice_date': 'Rechnungsdatum',
                    'total_amount': 'Gesamtbetrag',
                    'due_date': 'Fälligkeitsdatum',
                    'download_url': 'Download-Link'
                }
            },
            {
                'key': 'newsletter',
                'name': 'Newsletter-Versand',
                'description': 'Regulärer Newsletter-Versand',
                'category': 'system',
                'variables': {
                    'subscriber_name': 'Abonnenten-Name',
                    'newsletter_title': 'Newsletter-Titel',
                    'unsubscribe_url': 'Abmelde-Link',
                    'company_name': 'Firmenname'
                }
            }
        ]
        
        created_triggers = 0
        for trigger_data in missing_triggers:
            trigger, created = EmailTrigger.objects.get_or_create(
                trigger_key=trigger_data['key'],
                defaults={
                    'name': trigger_data['name'],
                    'description': trigger_data['description'],
                    'category': trigger_data['category'],
                    'available_variables': trigger_data['variables'],
                    'is_system_trigger': True
                }
            )
            
            if created and not dry_run:
                self.stdout.write(f"Created missing trigger: {trigger.name}")
                created_triggers += 1
            elif created and dry_run:
                self.stdout.write(f"[DRY RUN] Would create trigger: {trigger_data['name']}")
                created_triggers += 1
        
        # Try linking again with new triggers
        if created_triggers > 0:
            self.stdout.write(f"\nRetrying template linking with {created_triggers} new triggers...")
            
            for template in templates_without_triggers.filter(trigger=None):
                trigger_key = template_trigger_mapping.get(template.template_type)
                
                if trigger_key:
                    try:
                        trigger = EmailTrigger.objects.get(trigger_key=trigger_key)
                        
                        if not dry_run:
                            template.trigger = trigger
                            template.save()
                        
                        self.stdout.write(
                            f"{'[DRY RUN] Would link' if dry_run else 'Linked'} template '{template.name}' "
                            f"to new trigger '{trigger.name}'"
                        )
                        linked_count += 1
                        
                    except EmailTrigger.DoesNotExist:
                        continue
        
        self.stdout.write(f"\n=== Summary ===")
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Successfully linked {linked_count} templates to triggers"))
            self.stdout.write(self.style.SUCCESS(f"Created {created_triggers} new triggers"))
        else:
            self.stdout.write(f"Would link {linked_count} templates to triggers")
            self.stdout.write(f"Would create {created_triggers} new triggers")
        self.stdout.write(f"Skipped {skipped_count} templates")
        
        if dry_run:
            self.stdout.write(f"\nRun without --dry-run to apply changes.")