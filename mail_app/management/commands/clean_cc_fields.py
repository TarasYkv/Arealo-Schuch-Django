"""
Management command to clean up "Not Provided" values in CC/BCC fields.
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email
import json


class Command(BaseCommand):
    help = 'Clean up "Not Provided" values in email CC/BCC fields'

    def handle(self, *args, **options):
        self.stdout.write("🧹 Cleaning up CC/BCC fields...")
        
        # Find all emails and process them
        emails_with_not_provided = Email.objects.all()
        
        cleaned_count = 0
        for email in emails_with_not_provided:
            # Skip if cc_emails or bcc_emails are None
            if email.cc_emails is None:
                email.cc_emails = []
            if email.bcc_emails is None:
                email.bcc_emails = []
                
            # Clean CC emails
            cleaned_cc = []
            for cc_email in email.cc_emails:
                if isinstance(cc_email, str) and cc_email.strip().lower() not in ['not provided', 'not_provided', '', 'null', 'none']:
                    cleaned_cc.append(cc_email)
            
            # Clean BCC emails  
            cleaned_bcc = []
            for bcc_email in email.bcc_emails:
                if isinstance(bcc_email, str) and bcc_email.strip().lower() not in ['not provided', 'not_provided', '', 'null', 'none']:
                    cleaned_bcc.append(bcc_email)
            
            # Update if changed
            if email.cc_emails != cleaned_cc or email.bcc_emails != cleaned_bcc:
                old_cc = email.cc_emails.copy()
                old_bcc = email.bcc_emails.copy()
                
                email.cc_emails = cleaned_cc
                email.bcc_emails = cleaned_bcc
                email.save(update_fields=['cc_emails', 'bcc_emails'])
                
                self.stdout.write(f"  📧 Email {email.id}: CC {old_cc} → {cleaned_cc}")
                cleaned_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Cleaned {cleaned_count} emails")
        )