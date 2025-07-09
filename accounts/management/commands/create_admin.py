from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Erstellt einen Admin-User für Production-Deployments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username für den Admin (Standard: admin)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@example.com',
            help='E-Mail für den Admin'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Passwort für den Admin (falls nicht angegeben, wird nach ENV-Variable gesucht)'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        # Prüfe ob User bereits existiert
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" existiert bereits!')
            )
            
            # Bestehenden User zu Superuser machen
            user = User.objects.get(username=username)
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'User "{username}" wurde zu Superuser gemacht!')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'User "{username}" ist bereits Superuser!')
                )
            return

        # Passwort aus Environment Variable falls nicht angegeben
        if not password:
            password = os.environ.get('DJANGO_ADMIN_PASSWORD')
            
        if not password:
            self.stdout.write(
                self.style.ERROR(
                    'Kein Passwort angegeben! '
                    'Verwende --password oder setze DJANGO_ADMIN_PASSWORD Environment Variable.'
                )
            )
            return

        # Erstelle neuen Superuser
        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Superuser "{username}" erfolgreich erstellt!'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Fehler beim Erstellen des Superusers: {e}')
            )