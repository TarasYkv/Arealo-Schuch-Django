"""
Django Management Command to debug email content from Zoho API
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mail_app.models import EmailAccount, Folder
from mail_app.services import ZohoMailAPIService

User = get_user_model()

class Command(BaseCommand):
    help = 'Debug email content from Zoho API'

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username='taras')
            account = EmailAccount.objects.filter(user=user, is_active=True).first()
            folder = account.folders.filter(total_count__gt=0).first()
            
            self.stdout.write(f'Account: {account.email_address if account else "None"}')
            self.stdout.write(f'Folder: {folder.name if folder else "None"}')
            
            if account and folder:
                api_service = ZohoMailAPIService(account)
                emails = api_service.get_emails(folder.zoho_folder_id, limit=1)
                self.stdout.write(f'Got {len(emails)} emails')
                
                if emails:
                    email = emails[0]
                    
                    self.stdout.write('\nAvailable fields:')
                    for key in sorted(email.keys()):
                        self.stdout.write(f'  {key}')
                    
                    self.stdout.write('\nContent fields:')
                    content_fields = ['content', 'body', 'bodyText', 'bodyHtml', 'htmlContent', 'summary']
                    for key in content_fields:
                        value = email.get(key, 'NOT_FOUND')
                        if value and value != 'NOT_FOUND':
                            self.stdout.write(f'{key}: {str(value)[:200]}...')
                        else:
                            self.stdout.write(f'{key}: {value}')
            else:
                self.stdout.write('No account or folder found')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))