"""
Test command to verify read status import from Zoho API.
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
from mail_app.services import ZohoMailAPIService


class Command(BaseCommand):
    help = 'Test read status import from Zoho API'

    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR('No active email account found'))
            return

        self.stdout.write(f"Testing with account: {account.email_address}")
        
        try:
            api_service = ZohoMailAPIService(account)
            
            # Get inbox folder
            inbox_folder = account.folders.filter(folder_type='inbox').first()
            if not inbox_folder:
                self.stdout.write(self.style.ERROR('No inbox folder found'))
                return
                
            self.stdout.write(f"Using inbox folder: {inbox_folder.name} (ID: {inbox_folder.zoho_folder_id})")
            
            # Get recent emails from API
            response = api_service.get_emails(inbox_folder.zoho_folder_id, limit=10)
            
            if response and 'data' in response:
                self.stdout.write(f"\n📧 Testing read status from Zoho API:")
                self.stdout.write("=" * 80)
                
                for i, email_data in enumerate(response['data'][:10]):
                    zoho_is_unread = email_data.get('isUnread', 'MISSING')
                    our_is_read = not email_data.get('isUnread', False)  # Our conversion logic
                    
                    subject = email_data.get('subject', 'No subject')[:50]
                    sent_time = email_data.get('sentTime', 'No time')
                    
                    status_icon = "📩" if zoho_is_unread else "✅"
                    
                    self.stdout.write(
                        f"{i+1:2d}. {status_icon} API_isUnread={zoho_is_unread} → OUR_is_read={our_is_read}"
                    )
                    self.stdout.write(f"     Subject: {subject}")
                    self.stdout.write(f"     Time: {sent_time}")
                    self.stdout.write("")
                    
                # Summary
                total_emails = len(response['data'])
                unread_from_api = sum(1 for email in response['data'] if email.get('isUnread', False))
                read_from_api = total_emails - unread_from_api
                
                self.stdout.write("=" * 80)
                self.stdout.write(f"📊 Summary from Zoho API:")
                self.stdout.write(f"   Total emails: {total_emails}")
                self.stdout.write(f"   Read emails: {read_from_api} ({read_from_api/total_emails*100:.1f}%)")
                self.stdout.write(f"   Unread emails: {unread_from_api} ({unread_from_api/total_emails*100:.1f}%)")
                
            else:
                self.stdout.write(self.style.ERROR('No email data received from API'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))