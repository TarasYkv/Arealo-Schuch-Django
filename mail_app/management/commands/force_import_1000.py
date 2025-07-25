"""
Force import 1000 emails from inbox (bypasses duplicate checks)
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Folder, Email
from mail_app.services import ZohoMailAPIService, EmailSyncService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Force import 1000 emails from inbox'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Force importing 1000 emails from inbox...")
        
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
            
        self.stdout.write(f"📂 Inbox: {inbox.name}")
        
        # Clear existing emails if requested
        existing_count = Email.objects.filter(account=account, folder=inbox).count()
        self.stdout.write(f"📊 Current emails in inbox: {existing_count}")
        
        # Create services
        api_service = ZohoMailAPIService(account)
        sync_service = EmailSyncService(account)
        
        # Fetch emails in batches
        self.stdout.write("\n📥 Fetching emails from API...")
        
        all_emails = []
        batch_size = 200
        max_emails = 1000
        
        for batch_num in range(5):  # 5 batches of 200 = 1000
            start_index = batch_num * batch_size + 1
            self.stdout.write(f"  Batch {batch_num + 1}/5 (index {start_index}-{start_index + batch_size - 1})...")
            
            batch_emails = api_service.get_emails(
                inbox.zoho_folder_id,
                limit=batch_size,
                start=start_index
            )
            
            if not batch_emails:
                self.stdout.write(f"    No emails returned")
                break
                
            all_emails.extend(batch_emails)
            self.stdout.write(f"    ✅ Fetched {len(batch_emails)} emails (Total: {len(all_emails)})")
            
            if len(all_emails) >= max_emails:
                break
        
        self.stdout.write(f"\n📊 Total emails fetched: {len(all_emails)}")
        
        if not all_emails:
            self.stdout.write(self.style.ERROR("❌ No emails were fetched from API"))
            return
        
        # Process and import emails using sync service
        self.stdout.write("\n💾 Importing emails to database...")
        
        # We'll trick the sync service by feeding it the emails we fetched
        # First, temporarily replace the API service's get_emails method
        original_get_emails = api_service.get_emails
        emails_to_process = all_emails[:max_emails]
        current_batch = [0]  # Use list to make it mutable in closure
        
        def mock_get_emails(folder_id, limit=200, start=1, start_date=None, end_date=None):
            # Return emails in batches as requested
            batch_start = current_batch[0]
            batch_end = min(batch_start + limit, len(emails_to_process))
            batch = emails_to_process[batch_start:batch_end]
            current_batch[0] = batch_end
            return batch
        
        # Replace the method temporarily
        api_service.get_emails = mock_get_emails
        
        try:
            # Now use the normal sync process
            sync_stats = sync_service.sync_emails(
                folder=inbox,
                limit=max_emails
            )
            
            created_count = sync_stats.get('created', 0)
            updated_count = sync_stats.get('updated', 0)
            error_count = sync_stats.get('errors', 0)
            
        finally:
            # Restore original method
            api_service.get_emails = original_get_emails
        
        # Final statistics
        self.stdout.write("\n📊 Import Summary:")
        self.stdout.write(f"  ✅ Created: {created_count}")
        self.stdout.write(f"  🔄 Updated: {updated_count}")
        self.stdout.write(f"  ❌ Errors: {error_count}")
        
        final_count = Email.objects.filter(account=account, folder=inbox).count()
        self.stdout.write(f"\n📬 Total emails now in inbox: {final_count}")
        self.stdout.write(f"🎯 New emails added: {final_count - existing_count}")
        
        if final_count >= 1000:
            self.stdout.write(self.style.SUCCESS("\n✅ Successfully imported 1000+ emails!"))
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️  Only {final_count} emails in inbox"))