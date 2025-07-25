"""
Management command to test email sending functionality
"""
from django.core.management.base import BaseCommand, CommandError
from mail_app.models import EmailAccount
from mail_app.services import ZohoMailAPIService


class Command(BaseCommand):
    help = 'Test email sending functionality'

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
            default='Test Email from Mail App',
            help='Email subject (default: Test Email from Mail App)'
        )
        parser.add_argument(
            '--body',
            type=str,
            default='This is a test email sent from the Django Mail App using Zoho Mail API.',
            help='Email body text'
        )
        parser.add_argument(
            '--account-id',
            type=int,
            help='Specific email account ID to use for sending'
        )

    def handle(self, *args, **options):
        self.stdout.write("📧 Testing Email Send Functionality...")
        
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
        self.stdout.write(f"📝 Subject: {options['subject']}")
        
        try:
            # Initialize API service
            api_service = ZohoMailAPIService(account)
            
            # Test connection first
            self.stdout.write("🔗 Testing API connection...")
            if not api_service.test_connection():
                self.stdout.write(
                    self.style.WARNING("⚠️ API connection test failed, but continuing...")
                )
            else:
                self.stdout.write(self.style.SUCCESS("✅ API connection successful"))
            
            # Send the email
            self.stdout.write("📬 Sending email...")
            success = api_service.send_email(
                to_emails=[options['to']],
                subject=options['subject'],
                body_text=options['body']
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS("🎉 Email sent successfully!")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Failed to send email")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error during email send test: {str(e)}")
            )
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("📋 Test complete!")
        self.stdout.write("\n💡 Tips:")
        self.stdout.write("- Check Django logs for detailed API responses")
        self.stdout.write("- Verify Zoho OAuth scopes include 'ZohoMail.messages.CREATE'")
        self.stdout.write("- Ensure recipient email is valid")
        self.stdout.write("- Check spam folder if email not received")