"""
Django Management Command to manually set Zoho Account ID
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mail_app.models import EmailAccount

User = get_user_model()


class Command(BaseCommand):
    help = 'Manually set Zoho Account ID for email accounts'

    def handle(self, *args, **options):
        try:
            # Get user and account
            user = User.objects.get(username='taras')
            account = EmailAccount.objects.filter(user=user, is_active=True).first()
            
            if not account:
                self.stdout.write(self.style.ERROR('No active email account found'))
                return
            
            # Set the known account ID    
            account.zoho_account_id = '3521813000000002002'
            account.save(update_fields=['zoho_account_id'])
            
            self.stdout.write(
                self.style.SUCCESS(f'Set account ID {account.zoho_account_id} for {account.email_address}')
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))