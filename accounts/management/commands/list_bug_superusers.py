from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Listet alle Bug-Chat Superuser auf'

    def handle(self, *args, **options):
        # Finde alle Bug-Chat Superuser
        bug_superusers = User.objects.filter(is_bug_chat_superuser=True)
        
        if not bug_superusers.exists():
            self.stdout.write(
                self.style.WARNING('Keine Bug-Chat Superuser gefunden!')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🐛 Bug-Chat Superuser ({bug_superusers.count()}):')
        )
        self.stdout.write('=' * 60)
        
        for user in bug_superusers:
            status = []
            if user.receive_bug_reports:
                status.append('✓ Bug-Reports')
            if user.receive_anonymous_reports:
                status.append('✓ Anonyme Reports')
            
            self.stdout.write(
                f'• {user.username} ({user.email})\n'
                f'  Status: {", ".join(status) if status else "Keine aktiven Empfangseinstellungen"}'
            )
        
        self.stdout.write('=' * 60)
        
        # Zeige auch normale Bug-Report Empfänger
        bug_receivers = User.objects.filter(
            receive_bug_reports=True,
            is_bug_chat_superuser=False
        )
        
        if bug_receivers.exists():
            self.stdout.write(
                f'\n📧 Bug-Report Empfänger (ohne Superuser-Rechte): {bug_receivers.count()}'
            )
            for user in bug_receivers:
                self.stdout.write(f'• {user.username} ({user.email})')