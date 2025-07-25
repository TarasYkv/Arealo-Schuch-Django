"""
Django Management Command to check email accounts
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mail_app.models import EmailAccount

User = get_user_model()

class Command(BaseCommand):
    help = 'Check email accounts for debugging'

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username='taras')
            accounts = EmailAccount.objects.filter(user=user)
            
            self.stdout.write(f'Total accounts: {accounts.count()}')
            for acc in accounts:
                self.stdout.write(f'  - {acc.email_address}, active: {acc.is_active}, id: {acc.id}')
                
            # Check for any accounts with the problematic email
            problem_email = 'kontakt@naturmacher.de'
            problem_accounts = EmailAccount.objects.filter(email_address=problem_email)
            self.stdout.write(f'\\nAccounts with {problem_email}: {problem_accounts.count()}')
            for acc in problem_accounts:
                self.stdout.write(f'  - User: {acc.user.username}, active: {acc.is_active}, id: {acc.id}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))