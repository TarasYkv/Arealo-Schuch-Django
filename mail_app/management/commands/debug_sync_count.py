"""
Debug email sync count issues
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mail_app.models import EmailAccount, Email
from mail_app.services import ZohoMailAPIService, EmailSyncService


class Command(BaseCommand):
    help = 'Debug email sync count issues'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='Number of emails to request'
        )
    
    def handle(self, *args, **options):
        limit = options.get('limit')
        
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"Testing sync count for account: {account.email_address}")
        self.stdout.write(f"Requested limit: {limit}")
        
        # Check current emails in database
        current_count = account.emails.count()
        self.stdout.write(f"Current emails in database: {current_count}")
        
        # Get inbox folder
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            inbox = account.folders.first()
            
        if not inbox:
            self.stdout.write(self.style.ERROR("No folders found"))
            return
            
        self.stdout.write(f"Testing with folder: {inbox.name}")
        
        try:
            api_service = ZohoMailAPIService(account)
            account_id = api_service.get_account_id()
            
            # Test 1: Check how many emails API returns with different limits
            test_limits = [10, 50, 100, 200, 500, 1000]
            
            for test_limit in test_limits:
                try:
                    self.stdout.write(f"\n--- Testing API with limit {test_limit} ---")
                    emails_data = api_service.get_emails(
                        account_id=account_id,
                        folder_id=inbox.zoho_folder_id,
                        limit=test_limit
                    )
                    self.stdout.write(f"API returned: {len(emails_data)} emails")
                    
                    if emails_data:
                        # Check date range of returned emails
                        dates = []
                        for email in emails_data[:5]:  # Check first 5
                            date_str = email.get('sentDateInGMT', 'Unknown')
                            dates.append(date_str)
                        
                        self.stdout.write(f"Sample dates: {dates[:3]}")
                        
                    if test_limit >= 100:  # Only test sync for higher limits
                        break
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"API test failed for limit {test_limit}: {e}"))
            
            # Test 2: Run actual sync and see what happens
            self.stdout.write(f"\n--- Testing actual sync with limit {limit} ---")
            
            # Delete existing emails to get clean count
            if self.stdout.isatty():  # Only if running interactively
                confirm = input("Delete existing emails to test clean sync? (y/N): ")
                if confirm.lower() == 'y':
                    deleted_count = account.emails.count()
                    account.emails.all().delete()
                    self.stdout.write(f"Deleted {deleted_count} existing emails")
            
            sync_service = EmailSyncService(account)
            
            # Sync with date range (last 90 days)
            end_date = timezone.now()
            start_date = end_date - timedelta(days=90)
            
            self.stdout.write(f"Sync date range: {start_date} to {end_date}")
            
            # First get emails from API to see how many are available
            emails_data = api_service.get_emails(
                account_id=account_id,
                folder_id=inbox.zoho_folder_id,
                limit=limit
            )
            
            self.stdout.write(f"API returned {len(emails_data)} emails before sync")
            
            # Check how many fall within date range
            emails_in_range = 0
            for email_data in emails_data:
                try:
                    date_str = email_data.get('sentDateInGMT')
                    if date_str and str(date_str).isdigit():
                        from datetime import datetime, timezone as dt_timezone
                        timestamp = int(date_str) / 1000
                        email_date = datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
                        
                        if start_date <= email_date <= end_date:
                            emails_in_range += 1
                except:
                    pass
            
            self.stdout.write(f"Emails within date range: {emails_in_range}")
            
            # Now run the sync
            sync_stats = sync_service.sync_emails(
                folder=inbox,
                limit=limit,
                start_date=start_date,
                end_date=end_date
            )
            
            self.stdout.write(f"\nSync results:")
            self.stdout.write(f"  Fetched: {sync_stats['fetched']}")
            self.stdout.write(f"  Created: {sync_stats['created']}")
            self.stdout.write(f"  Updated: {sync_stats['updated']}")
            self.stdout.write(f"  Errors: {sync_stats['errors']}")
            
            # Check final count in database
            final_count = account.emails.count()
            self.stdout.write(f"\nFinal emails in database: {final_count}")
            
            # Show recent emails
            recent_emails = account.emails.order_by('-sent_at')[:5]
            self.stdout.write(f"\nRecent emails in database:")
            for email in recent_emails:
                self.stdout.write(f"  - {email.subject[:50]} ({email.sent_at})")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during debug: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())