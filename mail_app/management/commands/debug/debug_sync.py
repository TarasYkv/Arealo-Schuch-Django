"""
Debug email sync issues
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Folder
from mail_app.services import ZohoMailAPIService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Debug email sync issues'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email address of the account to debug')

    def handle(self, *args, **options):
        email_address = options.get('email')
        
        # Get all active email accounts
        if email_address:
            accounts = EmailAccount.objects.filter(email_address=email_address, is_active=True)
        else:
            accounts = EmailAccount.objects.filter(is_active=True)
        
        if not accounts.exists():
            self.stdout.write(self.style.ERROR('No active email accounts found'))
            return
        
        for account in accounts:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Debugging account: {account.email_address}")
            self.stdout.write(f"{'='*60}")
            
            # Check basic info
            self.stdout.write(f"✓ Account ID: {account.id}")
            self.stdout.write(f"✓ User: {account.user.email}")
            self.stdout.write(f"✓ Is Active: {account.is_active}")
            self.stdout.write(f"✓ Last Sync: {account.last_sync}")
            
            # Check OAuth tokens
            try:
                api_service = ZohoMailAPIService(account)
                zoho_settings = account.user.zoho_mail_settings
                self.stdout.write(f"\n📋 OAuth Settings:")
                self.stdout.write(f"   - Has Client ID: {'Yes' if zoho_settings.client_id else 'No'}")
                self.stdout.write(f"   - Has Client Secret: {'Yes' if zoho_settings.client_secret else 'No'}")
                self.stdout.write(f"   - Has Access Token: {'Yes' if zoho_settings.access_token else 'No'}")
                self.stdout.write(f"   - Has Refresh Token: {'Yes' if zoho_settings.refresh_token else 'No'}")
                self.stdout.write(f"   - Token Expires At: {zoho_settings.token_expires_at}")
                
                # Check account ID
                self.stdout.write(f"\n🔍 Checking Zoho Account ID...")
                try:
                    zoho_account_id = api_service.get_account_id()
                    self.stdout.write(f"   ✅ Zoho Account ID: {zoho_account_id}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Error getting account ID: {str(e)}"))
                    continue
                
                # Check folders
                self.stdout.write(f"\n📁 Checking folders...")
                folders = account.folders.all()
                self.stdout.write(f"   - Total folders in DB: {folders.count()}")
                
                if folders.count() == 0:
                    self.stdout.write(self.style.WARNING("   ⚠️  No folders found! Fetching from API..."))
                    try:
                        folder_data = api_service.fetch_folders()
                        self.stdout.write(f"   - Folders from API: {len(folder_data)}")
                        for folder in folder_data[:5]:  # Show first 5
                            self.stdout.write(f"     • {folder['folderName']} (ID: {folder['folderId']})")
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Error fetching folders: {str(e)}"))
                else:
                    for folder in folders[:5]:  # Show first 5
                        self.stdout.write(f"   • {folder.name} - {folder.total_count} emails")
                
                # Try to sync a small batch
                self.stdout.write(f"\n🔄 Testing sync with limit=10...")
                try:
                    # First sync folders
                    folder_stats = api_service.sync_folders()
                    self.stdout.write(f"   ✅ Folders synced: {folder_stats}")
                    
                    # Then sync emails
                    sync_stats = api_service.sync_emails(limit=10)
                    self.stdout.write(f"   ✅ Sync stats: {sync_stats}")
                    
                    # Check if any emails were created
                    email_count = account.emails.count()
                    self.stdout.write(f"   📧 Total emails in DB: {email_count}")
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Sync error: {str(e)}"))
                    import traceback
                    self.stdout.write(self.style.ERROR(f"   Traceback: {traceback.format_exc()}"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error initializing API service: {str(e)}"))
                
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("Debug complete!")