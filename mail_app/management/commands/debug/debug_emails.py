"""
Django Management Command to debug email storage
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email, EmailAccount, Folder

class Command(BaseCommand):
    help = 'Debug email storage issues'

    def handle(self, *args, **options):
        # Get account
        account = EmailAccount.objects.filter(is_active=True).first()
        self.stdout.write(f'Account: {account.email_address}')
        self.stdout.write(f'Total emails in DB: {Email.objects.filter(account=account).count()}')

        # Check folders
        folders = Folder.objects.filter(account=account)
        self.stdout.write(f'\nFolders ({folders.count()}):')
        for folder in folders:
            email_count = Email.objects.filter(account=account, folder=folder).count()
            self.stdout.write(f'  {folder.name}: {email_count} emails')

        # Check recent emails
        self.stdout.write('\nRecent emails:')
        recent_emails = Email.objects.filter(account=account).order_by('-created_at')[:5]
        if recent_emails:
            for email in recent_emails:
                self.stdout.write(f'  {email.subject[:50]} - {email.created_at}')
        else:
            self.stdout.write('  No emails found')