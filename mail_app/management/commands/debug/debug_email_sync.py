"""
Debug email sync to understand why only 50 emails are imported
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mail_app.models import EmailAccount, Folder
from mail_app.services import EmailSyncService, ZohoMailAPIService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Debug email sync process'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Debugging email sync...")
        
        # Get active account
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("❌ No active email account found"))
            return
            
        self.stdout.write(f"📧 Account: {account.email_address}")
        
        # Get inbox folder
        inbox = Folder.objects.filter(account=account, folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("❌ No inbox folder found"))
            return
            
        self.stdout.write(f"📂 Inbox: {inbox.name} (ID: {inbox.zoho_folder_id})")
        
        # Create API service
        api_service = ZohoMailAPIService(account)
        
        # Test direct API call
        self.stdout.write("\n🔄 Testing direct API call to get emails...")
        
        # Try different date ranges
        end_date = timezone.now()
        test_ranges = [
            ("Last 7 days", 7),
            ("Last 30 days", 30),
            ("Last 90 days", 90),
            ("Last 365 days", 365),
        ]
        
        for range_name, days in test_ranges:
            start_date = end_date - timedelta(days=days)
            self.stdout.write(f"\n📅 Testing {range_name} ({start_date.date()} to {end_date.date()}):")
            
            # First, try without date filter
            emails_no_filter = api_service.get_emails(
                inbox.zoho_folder_id,
                limit=10,
                start=1
            )
            self.stdout.write(f"  Without date filter: {len(emails_no_filter)} emails")
            
            # Then with date filter
            emails_with_filter = api_service.get_emails(
                inbox.zoho_folder_id,
                limit=10,
                start=1,
                start_date=start_date,
                end_date=end_date
            )
            self.stdout.write(f"  With date filter: {len(emails_with_filter)} emails")
        
        # Test pagination
        self.stdout.write("\n📄 Testing pagination (batches of 200)...")
        
        total_emails = []
        batch_size = 200
        max_batches = 5  # Test up to 5 batches (1000 emails)
        
        for batch_num in range(max_batches):
            start_index = batch_num * batch_size + 1
            self.stdout.write(f"\n  Batch {batch_num + 1} (start index: {start_index}):")
            
            batch_emails = api_service.get_emails(
                inbox.zoho_folder_id,
                limit=batch_size,
                start=start_index
            )
            
            self.stdout.write(f"    Fetched: {len(batch_emails)} emails")
            
            if not batch_emails:
                self.stdout.write("    No more emails available")
                break
                
            total_emails.extend(batch_emails)
            
            # Show sample of email dates
            if batch_emails:
                first_email = batch_emails[0]
                last_email = batch_emails[-1]
                self.stdout.write(f"    First email date: {first_email.get('sentTime', 'N/A')}")
                self.stdout.write(f"    Last email date: {last_email.get('sentTime', 'N/A')}")
        
        self.stdout.write(f"\n📊 Total emails fetched across all batches: {len(total_emails)}")
        
        # Check API response structure
        if total_emails:
            self.stdout.write("\n🔍 Sample email structure:")
            sample = total_emails[0]
            for key in ['messageId', 'subject', 'fromAddress', 'sentTime', 'receivedTime']:
                self.stdout.write(f"  {key}: {sample.get(key, 'N/A')}")