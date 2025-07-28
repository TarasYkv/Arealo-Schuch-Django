"""
Test email opening functionality
"""
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from mail_app.models import EmailAccount, Email
from mail_app.views.mail_views import EmailContentAPIView
import json


class Command(BaseCommand):
    help = 'Test email opening functionality'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"🧪 Testing email opening for account: {account.email_address}")
        
        # Get some emails to test
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("No inbox folder found"))
            return
        
        emails = inbox.emails.all()[:3]  # Test first 3 emails
        if not emails:
            self.stdout.write(self.style.ERROR("No emails found in inbox"))
            return
        
        self.stdout.write(f"📧 Found {len(emails)} emails to test")
        
        # Create a mock request
        factory = RequestFactory()
        
        for email in emails:
            self.stdout.write(f"\n🔍 Testing email ID {email.id}: {email.subject[:50]}")
            
            try:
                # Test the API endpoint
                request = factory.get(f'/mail/api/emails/{email.id}/')
                request.user = account.user
                
                view = EmailContentAPIView()
                view.request = request
                view.account = account
                
                response = view.get(request, email.id)
                
                if response.status_code == 200:
                    data = json.loads(response.content)
                    if 'html' in data and len(data['html']) > 0:
                        self.stdout.write(self.style.SUCCESS(f"  ✅ API works - HTML length: {len(data['html'])} chars"))
                    else:
                        self.stdout.write(self.style.ERROR(f"  ❌ API returned empty HTML"))
                else:
                    self.stdout.write(self.style.ERROR(f"  ❌ API failed with status {response.status_code}"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Exception: {e}"))
        
        # Test if emails have proper content
        self.stdout.write(f"\n📋 Email content check:")
        for email in emails:
            body_text_len = len(email.body_text) if email.body_text else 0
            body_html_len = len(email.body_html) if email.body_html else 0
            self.stdout.write(f"  Email {email.id}: text={body_text_len} chars, html={body_html_len} chars")
            
            if body_text_len == 0 and body_html_len == 0:
                self.stdout.write(self.style.WARNING(f"    ⚠️ Email {email.id} has no content!"))