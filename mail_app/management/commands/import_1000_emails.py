"""
Management command to import exactly 1000 emails from inbox
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mail_app.models import EmailAccount, Folder
from mail_app.services import EmailSyncService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import 1000 emails from inbox'

    def handle(self, *args, **options):
        self.stdout.write("📧 Starting import of 1000 emails from inbox...")
        
        # Get active account
        try:
            account = EmailAccount.objects.filter(is_active=True).first()
            if not account:
                self.stdout.write(self.style.ERROR("❌ No active email account found"))
                return
                
            self.stdout.write(f"✅ Using account: {account.email_address}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error getting account: {str(e)}"))
            return
        
        # Get inbox folder
        inbox_folder = Folder.objects.filter(
            account=account,
            folder_type='inbox'
        ).first()
        
        if not inbox_folder:
            self.stdout.write(self.style.ERROR("❌ No inbox folder found"))
            return
        
        self.stdout.write(f"📂 Found inbox folder: {inbox_folder.name} (ID: {inbox_folder.zoho_folder_id})")
        
        # Create sync service
        sync_service = EmailSyncService(account)
        
        # First, sync folders to ensure we have latest folder info
        self.stdout.write("🔄 Syncing folders...")
        folders_synced = sync_service.sync_folders()
        self.stdout.write(f"✅ Synced {folders_synced} folders")
        
        # Calculate date range - go back far enough to get 1000 emails
        # Start with 365 days to ensure we get enough emails
        end_date = timezone.now()
        start_date = end_date - timedelta(days=365)
        
        self.stdout.write(f"📅 Date range: {start_date.date()} to {end_date.date()}")
        
        # Sync emails from inbox with limit of 1000
        self.stdout.write(f"📨 Starting email sync for inbox (target: 1000 emails)...")
        
        try:
            sync_stats = sync_service.sync_emails(
                folder=inbox_folder,
                limit=1000,  # Exactly 1000 emails
                start_date=start_date,
                end_date=end_date
            )
            
            self.stdout.write("📊 Sync results:")
            self.stdout.write(f"  • Fetched: {sync_stats['fetched']}")
            self.stdout.write(f"  • Created: {sync_stats['created']}")
            self.stdout.write(f"  • Updated: {sync_stats['updated']}")
            self.stdout.write(f"  • Errors: {sync_stats['errors']}")
            
            # Check total emails in inbox
            from mail_app.models import Email
            total_inbox_emails = Email.objects.filter(
                account=account,
                folder=inbox_folder
            ).count()
            
            self.stdout.write(f"\n📬 Total emails now in inbox: {total_inbox_emails}")
            
            if sync_stats['fetched'] < 1000:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  Only {sync_stats['fetched']} emails were fetched. "
                        "This might be all available emails in the specified date range."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("✅ Successfully imported 1000 emails!")
                )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error during sync: {str(e)}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))