"""
Force exactly 500 emails into inbox by clearing all and re-syncing
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService


class Command(BaseCommand):
    help = 'Force exactly 500 emails into inbox by clearing all and re-syncing'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"🎯 Forcing 500 emails into inbox for: {account.email_address}")
        
        # Step 1: Delete ALL emails
        self.stdout.write("🗑️ Step 1: Clearing all existing emails...")
        total_before = account.emails.count()
        deleted, _ = account.emails.all().delete()
        self.stdout.write(f"   Deleted {deleted} emails")
        
        # Step 2: Update folder counts
        self.stdout.write("📊 Step 2: Resetting folder counts...")
        for folder in account.folders.all():
            folder.update_counts()
        
        # Step 3: Sync ONLY inbox with high limit
        self.stdout.write("📧 Step 3: Syncing ONLY inbox with limit 1000...")
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        sync_service = EmailSyncService(account)
        
        try:
            # Sync ONLY inbox with high limit to get more than 500
            stats = sync_service.sync_emails(folder=inbox, limit=1000)
            
            self.stdout.write(f"\n📊 Sync results:")
            self.stdout.write(f"  • Fetched from API: {stats['fetched']}")
            self.stdout.write(f"  • Created in DB: {stats['created']}")
            self.stdout.write(f"  • Updated: {stats['updated']}")
            self.stdout.write(f"  • Errors: {stats['errors']}")
            
            # Check final inbox count
            final_inbox_count = inbox.emails.count()
            self.stdout.write(f"\n📬 Final emails in inbox: {final_inbox_count}")
            
            if final_inbox_count >= 500:
                self.stdout.write(self.style.SUCCESS(f"🎉 SUCCESS! Got {final_inbox_count} emails in inbox (target: 500)"))
            elif final_inbox_count >= 400:
                self.stdout.write(self.style.SUCCESS(f"✅ GOOD! Got {final_inbox_count} emails in inbox (close to 500)"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ Only got {final_inbox_count} emails in inbox"))
                
                # If we didn't get enough, try syncing more folders
                if final_inbox_count < 300:
                    self.stdout.write("\n🔄 Trying to get more emails from other folders...")
                    
                    # Get sent folder
                    sent = account.folders.filter(folder_type='sent').first()
                    if sent:
                        sent_stats = sync_service.sync_emails(folder=sent, limit=200)
                        self.stdout.write(f"   Sent folder: +{sent_stats['created']} emails")
                    
                    final_total = account.emails.count()
                    self.stdout.write(f"\n📬 Total emails after additional sync: {final_total}")
            
            # Show folder distribution
            self.stdout.write(f"\n📁 Final folder distribution:")
            for folder in account.folders.all():
                count = folder.emails.count()
                if count > 0:
                    self.stdout.write(f"  {folder.name}: {count} emails")
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Sync failed: {e}"))