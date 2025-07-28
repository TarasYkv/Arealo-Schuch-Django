"""
Debug email sync process
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mail_app.models import EmailAccount, Folder, Email
from mail_app.services import ZohoMailAPIService, EmailSyncService


class Command(BaseCommand):
    help = 'Debug email sync process'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--account',
            type=int,
            help='Account ID to debug'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of emails to check'
        )
    
    def handle(self, *args, **options):
        account_id = options.get('account')
        limit = options.get('limit')
        
        if account_id:
            accounts = EmailAccount.objects.filter(id=account_id, is_active=True)
        else:
            accounts = EmailAccount.objects.filter(is_active=True)
        
        for account in accounts:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Debugging sync for account: {account.email_address}")
            self.stdout.write(f"{'='*60}\n")
            
            # Check account status
            self.stdout.write(f"Account active: {account.is_active}")
            self.stdout.write(f"Last sync: {account.last_sync}")
            self.stdout.write(f"Total emails in DB: {account.emails.count()}")
            
            # Check folders
            folders = account.folders.all()
            self.stdout.write(f"\nFolders ({folders.count()}):")
            for folder in folders:
                email_count = folder.emails.count()
                self.stdout.write(f"  - {folder.name}: {email_count} emails (Zoho ID: {folder.zoho_folder_id})")
            
            # Try to fetch emails from API
            try:
                api_service = ZohoMailAPIService(account)
                
                # Get account ID from API
                self.stdout.write(f"\nTesting API connection...")
                api_account_id = api_service.get_account_id()
                self.stdout.write(self.style.SUCCESS(f"✓ API connection successful. Account ID: {api_account_id}"))
                
                # Get inbox folder
                inbox = folders.filter(folder_type='inbox').first()
                if not inbox:
                    inbox = folders.first()
                
                if inbox:
                    self.stdout.write(f"\nFetching emails from {inbox.name}...")
                    
                    # Get emails from API
                    emails_data = api_service.get_emails(
                        account_id=api_account_id,
                        folder_id=inbox.zoho_folder_id,
                        limit=limit
                    )
                    
                    self.stdout.write(f"Found {len(emails_data)} emails in API")
                    
                    if emails_data:
                        self.stdout.write(f"\nFirst {min(5, len(emails_data))} emails from API:")
                        for i, email_data in enumerate(emails_data[:5]):
                            subject = email_data.get('subject', 'No subject')
                            from_email = email_data.get('fromAddress', 'Unknown')
                            sent_date = email_data.get('sentDateInGMT', 'Unknown date')
                            message_id = email_data.get('messageId', 'No ID')
                            
                            self.stdout.write(f"\n  Email {i+1}:")
                            self.stdout.write(f"    Subject: {subject[:50]}...")
                            self.stdout.write(f"    From: {from_email}")
                            self.stdout.write(f"    Date: {sent_date}")
                            self.stdout.write(f"    Message ID: {message_id}")
                            
                            # Check if already in DB
                            exists = Email.objects.filter(zoho_message_id=message_id).exists()
                            if exists:
                                self.stdout.write(self.style.WARNING("    Status: Already in database"))
                            else:
                                self.stdout.write(self.style.SUCCESS("    Status: New email"))
                    
                    # Test sync service
                    self.stdout.write(f"\n\nTesting sync service...")
                    sync_service = EmailSyncService(account)
                    
                    # Sync with date range
                    end_date = timezone.now()
                    start_date = end_date - timedelta(days=90)
                    
                    self.stdout.write(f"Sync date range: {start_date} to {end_date}")
                    
                    sync_stats = sync_service.sync_emails(
                        folder=inbox,
                        limit=10,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    self.stdout.write(f"\nSync results:")
                    self.stdout.write(f"  Fetched: {sync_stats['fetched']}")
                    self.stdout.write(f"  Created: {sync_stats['created']}")
                    self.stdout.write(f"  Updated: {sync_stats['updated']}")
                    self.stdout.write(f"  Errors: {sync_stats['errors']}")
                    
                else:
                    self.stdout.write(self.style.ERROR("No folders found for this account"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error during debug: {str(e)}"))
                import traceback
                self.stdout.write(traceback.format_exc())