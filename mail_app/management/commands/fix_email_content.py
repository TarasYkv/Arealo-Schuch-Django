"""
Management command to fix incomplete email content by re-fetching from API
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email, EmailAccount
from mail_app.services import ZohoMailAPIService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix incomplete email content by re-fetching from API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of emails to process (default: 100)'
        )
        parser.add_argument(
            '--min-length',
            type=int,
            default=300,
            help='Minimum content length to consider complete (default: 300)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        min_length = options['min_length']
        
        self.stdout.write("🔧 Fixing incomplete email content...")
        
        # Get active account
        try:
            account = EmailAccount.objects.filter(is_active=True).first()
            if not account:
                self.stdout.write(self.style.ERROR("❌ No active email account found"))
                return
                
            self.stdout.write(f"📧 Using account: {account.email_address}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error getting account: {str(e)}"))
            return
        
        # Find emails with incomplete content
        incomplete_emails = Email.objects.filter(
            account=account,
            zoho_message_id__isnull=False
        ).exclude(
            zoho_message_id=''
        )[:limit * 2]  # Get more candidates
        
        # Filter by content length
        emails_to_fix = []
        for email in incomplete_emails:
            content_length = len(email.body_text or '') + len(email.body_html or '')
            if content_length < min_length:
                emails_to_fix.append(email)
                if len(emails_to_fix) >= limit:
                    break
        
        self.stdout.write(f"📊 Found {len(emails_to_fix)} emails with incomplete content")
        
        if not emails_to_fix:
            self.stdout.write(self.style.SUCCESS("✅ All emails have sufficient content"))
            return
        
        # Create API service
        api_service = ZohoMailAPIService(account)
        
        # Process emails
        fixed_count = 0
        error_count = 0
        
        for i, email in enumerate(emails_to_fix):
            if i % 10 == 0:
                self.stdout.write(f"  Processing email {i+1}/{len(emails_to_fix)}...")
                
            try:
                old_length = len(email.body_text or '') + len(email.body_html or '')
                
                # Fetch detailed content using folder-based endpoint
                email_details = api_service.get_email_details(
                    email.zoho_message_id, 
                    email.folder.zoho_folder_id
                )
                
                if not email_details:
                    self.stdout.write(f"    ⚠️  Email {email.id}: No details returned")
                    continue
                
                # Handle nested data structure
                detail_data = email_details.get('data', email_details)
                
                # Extract content
                full_text = detail_data.get('content', detail_data.get('textContent', detail_data.get('bodyText', '')))
                full_html = detail_data.get('htmlContent', detail_data.get('bodyHtml', detail_data.get('content', '')))
                
                # Update if we got better content
                if len(full_text) > len(email.body_text or '') or len(full_html) > len(email.body_html or ''):
                    email.body_text = full_text or email.body_text
                    email.body_html = full_html or email.body_html
                    email.save(update_fields=['body_text', 'body_html'])
                    
                    new_length = len(email.body_text or '') + len(email.body_html or '')
                    self.stdout.write(f"    ✅ Email {email.id}: {old_length} → {new_length} chars")
                    fixed_count += 1
                else:
                    self.stdout.write(f"    ➡️  Email {email.id}: No improvement available ({old_length} chars)")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"    ❌ Email {email.id}: Error - {str(e)}")
                if error_count < 5:  # Only log first few errors in detail
                    import traceback
                    logger.error(f"Error fixing email {email.id}: {traceback.format_exc()}")
        
        # Summary
        self.stdout.write(f"\n📊 Content fix completed:")
        self.stdout.write(f"  ✅ Fixed: {fixed_count}")
        self.stdout.write(f"  ❌ Errors: {error_count}")
        self.stdout.write(f"  📧 Total processed: {len(emails_to_fix)}")
        
        if fixed_count > 0:
            self.stdout.write(self.style.SUCCESS(f"\n🎉 Successfully improved content for {fixed_count} emails!"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️  No emails were improved"))