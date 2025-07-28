"""
Management command to test attachment functionality
"""
import tempfile
import os
from django.core.management.base import BaseCommand, CommandError
from mail_app.models import EmailAccount
from mail_app.services import ZohoMailAPIService


class Command(BaseCommand):
    help = 'Test attachment upload and email sending functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            required=True,
            help='Recipient email address'
        )
        parser.add_argument(
            '--subject',
            type=str,
            default='Test Email with Attachment',
            help='Email subject (default: Test Email with Attachment)'
        )
        parser.add_argument(
            '--body',
            type=str,
            default='This is a test email with attachment sent from the Django Mail App.',
            help='Email body text'
        )
        parser.add_argument(
            '--account-id',
            type=int,
            help='Specific email account ID to use for sending'
        )

    def handle(self, *args, **options):
        self.stdout.write("📎 Testing Attachment Functionality...")
        
        # Get email account
        try:
            if options['account_id']:
                account = EmailAccount.objects.get(id=options['account_id'], is_active=True)
            else:
                account = EmailAccount.objects.filter(is_active=True).first()
                
            if not account:
                raise CommandError("No active email account found")
                
        except EmailAccount.DoesNotExist:
            raise CommandError(f"Email account with ID {options['account_id']} not found")
        
        self.stdout.write(f"📤 Using account: {account.email_address}")
        self.stdout.write(f"📨 Sending to: {options['to']}")
        
        try:
            # Initialize API service
            api_service = ZohoMailAPIService(account)
            
            # Create a test file
            self.stdout.write("📝 Creating test attachment...")
            test_content = b"Hello, this is a test attachment from Django Mail App!\n\nThis file contains test data to verify the attachment functionality is working correctly.\n\nBest regards,\nDjango Mail App"
            test_filename = "test_attachment.txt"
            
            # Upload attachment
            self.stdout.write("⬆️ Uploading attachment to Zoho Mail...")
            attachment_info = api_service.upload_attachment(
                file_content=test_content,
                filename=test_filename,
                content_type="text/plain"
            )
            
            if not attachment_info:
                self.stdout.write(self.style.ERROR("❌ Failed to upload attachment"))
                return
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Attachment uploaded: {attachment_info['filename']}")
            )
            self.stdout.write(f"   📋 Store Name: {attachment_info.get('storeName', 'N/A')}")
            self.stdout.write(f"   📋 Attachment Path: {attachment_info.get('attachmentPath', 'N/A')}")
            self.stdout.write(f"   📋 Size: {attachment_info.get('size', 0)} bytes")
            
            # Send email with attachment
            self.stdout.write("📬 Sending email with attachment...")
            success = api_service.send_email(
                to_emails=[options['to']],
                subject=options['subject'],
                body_text=options['body'] + f"\n\nAttachment: {test_filename}",
                attachments=[attachment_info]
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS("🎉 Email with attachment sent successfully!")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Failed to send email with attachment")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error during attachment test: {str(e)}")
            )
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📋 Attachment Test Complete!")
        self.stdout.write("\n💡 What was tested:")
        self.stdout.write("- ⬆️ Attachment upload to Zoho Mail API")
        self.stdout.write("- 📤 Email sending with attachment")
        self.stdout.write("- 🔄 Integration between upload and send APIs")
        self.stdout.write("\n🔍 Check recipient's email for:")
        self.stdout.write("- 📧 Email with correct subject and body")
        self.stdout.write("- 📎 Attached test_attachment.txt file")
        self.stdout.write("- 💾 File should contain test content when downloaded")