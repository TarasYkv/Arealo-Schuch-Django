from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Erstellt oder aktualisiert einen Bug-Chat Superuser'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username des Users der Bug-Chat Superuser werden soll'
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Erstellt den User falls er nicht existiert'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='',
            help='E-Mail für neuen User (nur bei --create)'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Passwort für neuen User (nur bei --create)'
        )

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            # Versuche bestehenden User zu finden
            user = User.objects.get(username=username)
            self.stdout.write(f'User "{username}" gefunden.')
            
        except User.DoesNotExist:
            if options['create']:
                # Erstelle neuen User
                if not options['password']:
                    self.stdout.write(
                        self.style.ERROR(
                            'Passwort erforderlich für neuen User! Verwende --password'
                        )
                    )
                    return
                    
                user = User.objects.create_user(
                    username=username,
                    email=options['email'],
                    password=options['password']
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Neuer User "{username}" erstellt.')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'User "{username}" existiert nicht! '
                        'Verwende --create um ihn zu erstellen.'
                    )
                )
                return
        
        # Aktiviere Bug-Chat Superuser Rechte
        user.is_bug_chat_superuser = True
        user.receive_bug_reports = True
        user.receive_anonymous_reports = True
        user.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ User "{username}" ist jetzt Bug-Chat Superuser!\n'
                f'   - Kann Bug-Reports empfangen: ✓\n'
                f'   - Kann anonyme Reports empfangen: ✓\n'
                f'   - Kann andere Bug-Chat Superuser verwalten: ✓'
            )
        )