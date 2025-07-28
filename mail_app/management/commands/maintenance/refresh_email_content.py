"""
Management command to refresh email content for emails with incomplete content.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mail_app.models import Email, EmailAccount
from mail_app.services import ZohoMailAPIService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Refresh incomplete email content by fetching detailed content from API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of emails to process (default: 50)'
        )
        parser.add_argument(
            '--min-content-length',
            type=int,
            default=100,
            help='Minimum content length to consider complete (default: 100)'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Only process emails from last N days (default: 30)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        min_content_length = options['min_content_length']
        days_back = options['days_back']
        
        self.stdout.write("🔄 Refreshing email content...")
        self.stdout.write(f"   Limit: {limit} emails")
        self.stdout.write(f"   Min content length: {min_content_length} chars")
        self.stdout.write(f"   Days back: {days_back}")
        
        # Calculate date threshold
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Find emails with incomplete content
        incomplete_emails = Email.objects.filter(
            received_at__gte=cutoff_date
        ).exclude(
            zoho_message_id__isnull=True
        ).exclude(
            zoho_message_id=''
        )[:limit * 2]  # Get more candidates to filter from
        
        # Filter emails that need content refresh
        emails_to_refresh = []
        for email in incomplete_emails:
            content_length = len(email.body_text or '') + len(email.body_html or '')
            text_content = (email.body_text or '').lower()
            html_content = (email.body_html or '').lower()
            
            needs_refresh = (
                content_length < min_content_length or
                'summary' in text_content or
                'summary' in html_content or
                text_content.endswith('...') or
                html_content.endswith('...') or
                'mehr anzeigen' in text_content or
                'show more' in text_content or
                len(text_content) < 50
            )
            
            if needs_refresh:
                emails_to_refresh.append(email)
                if len(emails_to_refresh) >= limit:
                    break
        
        if not emails_to_refresh:
            self.stdout.write(self.style.SUCCESS("✅ No emails need content refresh"))
            return
        
        self.stdout.write(f"📧 Found {len(emails_to_refresh)} emails that need content refresh")
        
        # Get active email account for API calls
        try:
            account = EmailAccount.objects.filter(is_active=True).first()
            if not account:
                self.stdout.write(self.style.ERROR("❌ No active email account found"))
                return
            
            api_service = ZohoMailAPIService(account)
            self.stdout.write(f"🔗 Using account: {account.email_address}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error setting up API service: {str(e)}"))
            return
        
        # Process emails
        refreshed_count = 0
        error_count = 0
        
        for email in emails_to_refresh:
            try:
                old_length = len(email.body_text or '') + len(email.body_html or '')
                
                # Fetch detailed content
                email_details = api_service.get_email_details(email.zoho_message_id)
                if not email_details:
                    self.stdout.write(f"  ⚠️  Email {email.id}: No details found")
                    error_count += 1
                    continue
                
                # Get the full content
                full_text = email_details.get('content', email_details.get('textContent', email_details.get('bodyText', '')))
                full_html = email_details.get('htmlContent', email_details.get('bodyHtml', email_details.get('content', '')))
                
                # Update if we got more complete content
                if len(full_text) > len(email.body_text or '') or len(full_html) > len(email.body_html or ''):
                    email.body_text = full_text or email.body_text
                    email.body_html = full_html or email.body_html
                    email.save(update_fields=['body_text', 'body_html'])
                    
                    new_length = len(email.body_text or '') + len(email.body_html or '')
                    self.stdout.write(f"  ✅ Email {email.id}: {old_length} → {new_length} chars")
                    refreshed_count += 1
                else:
                    self.stdout.write(f"  ➡️  Email {email.id}: No improvement ({old_length} chars)")
                
            except Exception as e:
                self.stdout.write(f"  ❌ Email {email.id}: Error - {str(e)}")
                error_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Content refresh completed: {refreshed_count} refreshed, {error_count} errors"
            )
        )