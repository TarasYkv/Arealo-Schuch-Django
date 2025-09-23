from django.core.management.base import BaseCommand
from accounts.models import AppPermission


class Command(BaseCommand):
    help = 'Erstellt Standard-Berechtigung für Beleuchtungsrechner (DIN 13201-1)'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle Berechtigung für Beleuchtungsrechner...')

        # Erstelle oder aktualisiere die App-Berechtigung
        permission, created = AppPermission.objects.get_or_create(
            app_name='din_13201',
            defaults={
                'access_level': 'authenticated',  # Für alle angemeldeten Nutzer
                'hide_in_frontend': False,
                'superuser_bypass': True,
                'is_active': True
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Berechtigung für "{permission.get_app_name_display()}" erfolgreich erstellt!'
                )
            )
            self.stdout.write(f'Zugriffsebene: {permission.get_access_level_display()}')
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Berechtigung für "{permission.get_app_name_display()}" existiert bereits.'
                )
            )
            self.stdout.write(f'Aktuelle Zugriffsebene: {permission.get_access_level_display()}')

        self.stdout.write('\nHinweis: Berechtigungen können unter /admin/accounts/apppermission/ verwaltet werden.')