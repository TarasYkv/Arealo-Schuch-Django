"""
Debug email counts and duplicates
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from mail_app.models import EmailAccount, Email


class Command(BaseCommand):
    help = 'Debug email counts and find duplicates'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"Debugging email counts for: {account.email_address}")
        
        # Total emails in database
        total_emails = account.emails.count()
        self.stdout.write(f"\n📊 Total emails in database: {total_emails}")
        
        # Emails per folder
        self.stdout.write(f"\n📁 Emails per folder:")
        folders = account.folders.all()
        folder_total = 0
        for folder in folders:
            email_count = folder.emails.count()
            folder_total += email_count
            self.stdout.write(f"  {folder.name}: {email_count} emails")
        
        self.stdout.write(f"  Total across folders: {folder_total}")
        
        if total_emails != folder_total:
            self.stdout.write(self.style.WARNING(f"⚠️ Mismatch: {total_emails} total vs {folder_total} in folders"))
        
        # Check for duplicates by zoho_message_id
        self.stdout.write(f"\n🔍 Checking for duplicates by zoho_message_id:")
        duplicates = Email.objects.filter(account=account).values('zoho_message_id').annotate(
            count=Count('zoho_message_id')
        ).filter(count__gt=1)
        
        if duplicates:
            self.stdout.write(f"Found {len(duplicates)} duplicate zoho_message_ids:")
            for dup in duplicates[:10]:  # Show first 10
                message_id = dup['zoho_message_id']
                count = dup['count']
                emails = Email.objects.filter(account=account, zoho_message_id=message_id)
                self.stdout.write(f"  {message_id}: {count} copies")
                for email in emails:
                    self.stdout.write(f"    - ID: {email.id}, Folder: {email.folder.name}, Subject: {email.subject[:50]}")
        else:
            self.stdout.write("✅ No duplicates found by zoho_message_id")
        
        # Check for duplicates by subject + from_email + sent_at
        self.stdout.write(f"\n🔍 Checking for duplicates by subject/sender/date:")
        content_duplicates = Email.objects.filter(account=account).values(
            'subject', 'from_email', 'sent_at'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        if content_duplicates:
            self.stdout.write(f"Found {len(content_duplicates)} potential content duplicates:")
            for dup in content_duplicates[:5]:  # Show first 5
                subject = dup['subject'][:50]
                from_email = dup['from_email']
                count = dup['count']
                self.stdout.write(f"  '{subject}' from {from_email}: {count} copies")
        else:
            self.stdout.write("✅ No content duplicates found")
        
        # Check email creation dates
        self.stdout.write(f"\n📅 Email creation dates:")
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        today = now.date()
        yesterday = (now - timedelta(days=1)).date()
        
        today_count = account.emails.filter(created_at__date=today).count()
        yesterday_count = account.emails.filter(created_at__date=yesterday).count()
        older_count = account.emails.filter(created_at__date__lt=yesterday).count()
        
        self.stdout.write(f"  Today: {today_count}")
        self.stdout.write(f"  Yesterday: {yesterday_count}")
        self.stdout.write(f"  Older: {older_count}")
        
        # Check if there are emails without proper zoho_message_id
        empty_message_ids = account.emails.filter(zoho_message_id__isnull=True).count()
        blank_message_ids = account.emails.filter(zoho_message_id='').count()
        
        self.stdout.write(f"\n🆔 Message ID issues:")
        self.stdout.write(f"  NULL zoho_message_id: {empty_message_ids}")
        self.stdout.write(f"  Empty zoho_message_id: {blank_message_ids}")
        
        if empty_message_ids > 0 or blank_message_ids > 0:
            self.stdout.write(self.style.WARNING("⚠️ Some emails have missing zoho_message_id - this could cause sync issues"))
        
        # Show recent emails
        self.stdout.write(f"\n📧 Most recent 5 emails:")
        recent_emails = account.emails.order_by('-created_at')[:5]
        for email in recent_emails:
            self.stdout.write(f"  {email.created_at} - {email.folder.name} - {email.subject[:50]}")