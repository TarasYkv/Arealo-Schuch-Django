"""
Fix folder counts that are out of sync
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount


class Command(BaseCommand):
    help = 'Fix folder counts that are out of sync with actual email counts'
    
    def handle(self, *args, **options):
        accounts = EmailAccount.objects.filter(is_active=True)
        
        if not accounts:
            self.stdout.write(self.style.ERROR("No active email accounts found"))
            return
        
        for account in accounts:
            self.stdout.write(f"\n--- Fixing folder counts for {account.email_address} ---")
            
            folders = account.folders.all()
            if not folders:
                self.stdout.write("No folders found")
                continue
            
            for folder in folders:
                # Get actual counts
                actual_total = folder.emails.count()
                actual_unread = folder.emails.filter(is_read=False).count()
                
                # Compare with stored counts
                stored_total = folder.total_count
                stored_unread = folder.unread_count
                
                if stored_total != actual_total or stored_unread != actual_unread:
                    self.stdout.write(f"{folder.name}: Fixing counts")
                    self.stdout.write(f"  Total: {stored_total} -> {actual_total}")
                    self.stdout.write(f"  Unread: {stored_unread} -> {actual_unread}")
                    
                    # Update the counts
                    folder.update_counts()
                    self.stdout.write(self.style.SUCCESS(f"  ✅ {folder.name} updated"))
                else:
                    self.stdout.write(f"{folder.name}: Counts are correct ({actual_total} total, {actual_unread} unread)")
        
        self.stdout.write(self.style.SUCCESS("\n✅ All folder counts have been fixed!"))