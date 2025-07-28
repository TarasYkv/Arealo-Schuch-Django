from django.core.management.base import BaseCommand
from accounts.models import AppPermission


class Command(BaseCommand):
    help = 'Erstellt die SoMi-Plan App-Berechtigung'

    def handle(self, *args, **options):
        """Erstellt SoMi-Plan Berechtigung falls sie nicht existiert"""
        
        permission, created = AppPermission.objects.get_or_create(
            app_name='somi_plan',
            defaults={
                'access_level': 'authenticated',  # Alle angemeldeten User haben Zugriff
                'is_active': True,
                'hide_in_frontend': False,  # Im Frontend anzeigen
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('✅ SoMi-Plan Berechtigung wurde erstellt')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠️ SoMi-Plan Berechtigung existiert bereits')
            )
            
        # Zeige aktuelle Einstellungen
        self.stdout.write(f'📋 Aktuelle Einstellungen:')
        self.stdout.write(f'   - App: {permission.get_app_name_display()}')
        self.stdout.write(f'   - Zugriffsebene: {permission.get_access_level_display()}')
        self.stdout.write(f'   - Aktiv: {permission.is_active}')
        self.stdout.write(f'   - Im Frontend ausblenden: {permission.hide_in_frontend}')