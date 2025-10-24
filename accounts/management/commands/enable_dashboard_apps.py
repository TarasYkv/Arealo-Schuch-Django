"""
Management Command zum Freischalten aller Dashboard-Apps für angemeldete User.

Dieses Command:
1. Erstellt fehlende AppPermission-Einträge
2. Aktualisiert gesperrte Apps auf 'authenticated'
3. Stellt sicher, dass alle Dashboard-Apps für Normaluser sichtbar sind

Usage:
    python manage.py enable_dashboard_apps
"""
from django.core.management.base import BaseCommand
from accounts.models import AppPermission


class Command(BaseCommand):
    help = 'Schaltet alle Dashboard-Apps für angemeldete User frei'

    def handle(self, *args, **options):
        # Alle Apps aus dem Dashboard (accounts/views.py app_definitions)
        dashboard_apps = [
            'chat', 'videos', 'schuch', 'schuch_dashboard', 'wirtschaftlichkeitsrechner',
            'sportplatz_konfigurator', 'pdf_suche', 'ki_zusammenfassung', 'shopify',
            'bilder', 'organisation', 'schulungen', 'todos', 'editor', 'bug_report',
            'payments', 'loomline', 'streamrec', 'fileshare', 'promptpro', 'loomads',
            'loomconnect', 'keyengine', 'lighting_tools'
        ]
        
        self.stdout.write(self.style.SUCCESS('🔓 Schalte Dashboard-Apps frei...'))
        self.stdout.write('')
        
        updated_count = 0
        created_count = 0
        
        for app_name in dashboard_apps:
            perm, created = AppPermission.objects.get_or_create(
                app_name=app_name,
                defaults={
                    'access_level': 'authenticated',
                    'is_active': True,
                    'hide_in_frontend': False
                }
            )
            
            if created:
                self.stdout.write(f'  ✅ {app_name}: NEU erstellt → Angemeldete Nutzer')
                created_count += 1
            elif perm.access_level not in ['public', 'authenticated']:
                old_status = perm.get_access_level_display()
                perm.access_level = 'authenticated'
                perm.is_active = True
                perm.hide_in_frontend = False
                perm.save()
                self.stdout.write(f'  🔄 {app_name}: {old_status} → Angemeldete Nutzer')
                updated_count += 1
            else:
                self.stdout.write(self.style.WARNING(f'  ℹ️  {app_name}: Bereits freigeschaltet'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'✅ Fertig! {created_count} neu erstellt, {updated_count} aktualisiert'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Alle {len(dashboard_apps)} Dashboard-Apps sind jetzt für angemeldete User sichtbar!'
        ))
