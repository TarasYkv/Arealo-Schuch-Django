"""
Django Management Command to test disconnect functionality
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from accounts.views import zoho_disconnect_api
from mail_app.models import EmailAccount, Email, Folder
import json

User = get_user_model()

class Command(BaseCommand):
    help = 'Test the disconnect functionality'

    def handle(self, *args, **options):
        try:
            # Get user
            user = User.objects.get(username='taras') 
            
            # Count data before disconnect
            account = EmailAccount.objects.filter(user=user, is_active=True).first()
            if account:
                emails_before = account.emails.count()
                folders_before = account.folders.count()
                threads_before = account.threads.count()
                drafts_before = account.drafts.count()
                attachments_before = sum(email.attachments.count() for email in account.emails.all())
                
                self.stdout.write(f'Before disconnect:')
                self.stdout.write(f'  - {emails_before} emails')
                self.stdout.write(f'  - {folders_before} folders')
                self.stdout.write(f'  - {threads_before} threads')
                self.stdout.write(f'  - {drafts_before} drafts')
                self.stdout.write(f'  - {attachments_before} attachments')
                self.stdout.write(f'  - Account active: {account.is_active}')
            else:
                self.stdout.write('No active account found')
                return

            # Create fake request
            factory = RequestFactory()
            request = factory.post('/accounts/api/zoho-disconnect/')
            request.user = user
            
            self.stdout.write('\\nExecuting disconnect...')

            # Test the disconnect function
            response = zoho_disconnect_api(request)
            
            # Parse response
            response_data = json.loads(response.content.decode())
            self.stdout.write(f'Response: {response_data}')
            
            # Check counts after disconnect
            emails_after = Email.objects.filter(account=account).count()
            folders_after = Folder.objects.filter(account=account).count()
            threads_after = account.threads.count()
            drafts_after = account.drafts.count()
            attachments_after = sum(email.attachments.count() for email in account.emails.all())
            
            # Check account status
            account.refresh_from_db()
            
            self.stdout.write(f'\\nAfter disconnect:')
            self.stdout.write(f'  - {emails_after} emails (was {emails_before})')
            self.stdout.write(f'  - {folders_after} folders (was {folders_before})')
            self.stdout.write(f'  - {threads_after} threads (was {threads_before})')
            self.stdout.write(f'  - {drafts_after} drafts (was {drafts_before})')
            self.stdout.write(f'  - {attachments_after} attachments (was {attachments_before})')
            self.stdout.write(f'  - Account active: {account.is_active}')
            
            if response_data.get('success'):
                self.stdout.write(self.style.SUCCESS('✅ Disconnect test successful!'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Disconnect failed: {response_data.get("error")}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))
            import traceback
            traceback.print_exc()