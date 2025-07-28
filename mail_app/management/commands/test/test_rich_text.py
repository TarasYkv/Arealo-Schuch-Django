"""
Management command to test rich text email sending
"""
from django.core.management.base import BaseCommand, CommandError
from mail_app.models import EmailAccount
from mail_app.services import ZohoMailAPIService


class Command(BaseCommand):
    help = 'Test rich text HTML email sending functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            required=True,
            help='Recipient email address'
        )
        parser.add_argument(
            '--account-id',
            type=int,
            help='Specific email account ID to use for sending'
        )

    def handle(self, *args, **options):
        self.stdout.write("📝 Testing Rich Text Email Functionality...")
        
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
        
        # Create rich HTML content
        html_content = """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #667eea; text-align: center;">🎉 Rich Text Email Test</h1>
            
            <p>Hallo! Dies ist ein Test der <strong>Rich-Text-Email-Funktionalität</strong> der Django Mail App.</p>
            
            <h2 style="color: #764ba2;">✨ Features die getestet werden:</h2>
            
            <ul style="line-height: 1.6;">
                <li><strong>Fettgedruckter Text</strong></li>
                <li><em>Kursiver Text</em></li>
                <li><u>Unterstrichener Text</u></li>
                <li><span style="color: #e74c3c;">Farbiger Text</span></li>
                <li><span style="background-color: #f1c40f; padding: 2px;">Hintergrundfarbe</span></li>
            </ul>
            
            <h3 style="color: #27ae60;">📋 Listentests:</h3>
            
            <ol>
                <li>Erste nummerierte Liste</li>
                <li>Zweite nummerierte Liste</li>
                <li>Dritte nummerierte Liste</li>
            </ol>
            
            <blockquote style="border-left: 4px solid #667eea; margin: 20px 0; padding-left: 20px; font-style: italic;">
                "Dies ist ein Zitat-Block um die Formatierung zu testen."
            </blockquote>
            
            <div style="background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="margin-top: 0; color: #2c3e50;">💡 Code-Block Simulation:</h4>
                <code style="background-color: #34495e; color: #ecf0f1; padding: 2px 4px; border-radius: 3px;">
                    python manage.py test_rich_text --to email@example.com
                </code>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #667eea; color: white;">
                    <th style="padding: 10px; border: 1px solid #ddd;">Feature</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Status</th>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">HTML Formatierung</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">✅ Funktioniert</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #ddd;">CSS Styling</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">✅ Funktioniert</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">Email-Versand</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">🔄 Wird getestet</td>
                </tr>
            </table>
            
            <div style="text-align: center; margin: 30px 0;">
                <p style="color: #7f8c8d;">Gesendet von der <strong>Django Mail App</strong> mit Zoho Mail API</p>
                <p style="font-size: 12px; color: #95a5a6;">📧 Rich Text Editor powered by Quill.js</p>
            </div>
        </div>
        """
        
        plain_text = """
        Rich Text Email Test
        ====================
        
        Hallo! Dies ist ein Test der Rich-Text-Email-Funktionalität der Django Mail App.
        
        Features die getestet werden:
        - Fettgedruckter Text
        - Kursiver Text  
        - Unterstrichener Text
        - Farbiger Text
        - Hintergrundfarbe
        
        Listentests:
        1. Erste nummerierte Liste
        2. Zweite nummerierte Liste
        3. Dritte nummerierte Liste
        
        "Dies ist ein Zitat-Block um die Formatierung zu testen."
        
        Code-Block Simulation:
        python manage.py test_rich_text --to email@example.com
        
        Feature Status:
        HTML Formatierung: ✅ Funktioniert
        CSS Styling: ✅ Funktioniert  
        Email-Versand: 🔄 Wird getestet
        
        Gesendet von der Django Mail App mit Zoho Mail API
        Rich Text Editor powered by Quill.js
        """
        
        try:
            # Send rich text email
            api_service = ZohoMailAPIService(account)
            success = api_service.send_email(
                to_emails=[options['to']],
                subject="🎨 Django Mail App - Rich Text Test",
                body_text=plain_text,
                body_html=html_content
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS("🎉 Rich Text Email sent successfully!")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Failed to send rich text email")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error during rich text email test: {str(e)}")
            )
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📋 Rich Text Email Test Complete!")
        self.stdout.write("\n💡 What was tested:")
        self.stdout.write("- 🎨 HTML formatting (headings, paragraphs, lists)")
        self.stdout.write("- 🌈 CSS styling (colors, backgrounds, layouts)")
        self.stdout.write("- 📊 Table formatting")
        self.stdout.write("- 💬 Blockquotes and code blocks")
        self.stdout.write("- 📤 HTML + Plain text dual format sending")
        self.stdout.write("\n🔍 Check recipient's email for:")
        self.stdout.write("- 📧 Properly formatted rich text content")
        self.stdout.write("- 🎨 Colors, styling, and layout preservation")
        self.stdout.write("- 📱 Mobile-friendly responsive design")