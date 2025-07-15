from django.core.management.base import BaseCommand
from accounts.models import AppPermission


class Command(BaseCommand):
    help = 'Erstellt Standard-App-Berechtigungen'

    def handle(self, *args, **options):
        """Erstelle Standard-Berechtigungen für alle Apps"""
        
        # Standard-Einstellungen: Alle Apps für angemeldete Nutzer freigeben
        default_permissions = [
            # Hauptkategorien
            ('schulungen', 'authenticated'),
            ('shopify', 'authenticated'),
            ('bilder', 'authenticated'),
            ('todos', 'authenticated'),
            ('chat', 'authenticated'),
            ('organisation', 'authenticated'),
            
            # Schuch Tools
            ('wirtschaftlichkeitsrechner', 'authenticated'),
            ('sportplatz_konfigurator', 'authenticated'),
            ('pdf_suche', 'authenticated'),
            ('ki_zusammenfassung', 'authenticated'),
            
            # Shopify Unterkategorien
            ('shopify_produkte', 'authenticated'),
            ('shopify_blogs', 'authenticated'),
            ('shopify_seo_dashboard', 'authenticated'),
            ('shopify_verkaufszahlen', 'authenticated'),
            ('shopify_seo_optimierung', 'authenticated'),
            ('shopify_alt_text', 'authenticated'),
            
            # Organisation Unterkategorien
            ('organisation_notizen', 'authenticated'),
            ('organisation_termine', 'authenticated'),
            ('organisation_ideenboards', 'authenticated'),
            ('organisation_terminanfragen', 'authenticated'),
        ]
        
        created_count = 0
        updated_count = 0
        
        for app_name, access_level in default_permissions:
            permission, created = AppPermission.objects.get_or_create(
                app_name=app_name,
                defaults={
                    'access_level': access_level,
                    'hide_in_frontend': False,
                    'superuser_bypass': True,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Berechtigung für "{app_name}" erstellt')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'○ Berechtigung für "{app_name}" existiert bereits')
                )
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'Setup abgeschlossen: {created_count} erstellt, {updated_count} übersprungen')
        )
        self.stdout.write(
            'Alle Apps sind für angemeldete Nutzer freigegeben.'
        )
        self.stdout.write(
            'Anpassungen können über das Admin-Interface oder die App-Freigabe vorgenommen werden.'
        )