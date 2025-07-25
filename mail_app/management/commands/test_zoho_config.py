"""
Management command to test Zoho Mail configuration
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from mail_app.services import ZohoOAuthService
import requests


class Command(BaseCommand):
    help = 'Test Zoho Mail OAuth2 configuration'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Testing Zoho Mail Configuration...")
        
        # Test 1: Check settings
        self.stdout.write("\n1. Checking Django settings...")
        config = settings.ZOHO_MAIL_CONFIG
        
        required_settings = ['CLIENT_ID', 'CLIENT_SECRET', 'REDIRECT_URI']
        for setting in required_settings:
            value = config.get(setting, '')
            if not value or value == f'dein_{setting.lower()}':
                self.stdout.write(
                    self.style.ERROR(f"❌ {setting} not configured in .env file")
                )
                return
            else:
                # Hide sensitive values
                display_value = value[:10] + "..." if len(value) > 10 else value
                self.stdout.write(
                    self.style.SUCCESS(f"✅ {setting}: {display_value}")
                )
        
        # Test 2: Check OAuth service initialization
        self.stdout.write("\n2. Testing OAuth service...")
        try:
            oauth_service = ZohoOAuthService()
            self.stdout.write(self.style.SUCCESS("✅ OAuth service initialized"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ OAuth service error: {e}"))
            return
        
        # Test 3: Generate authorization URL
        self.stdout.write("\n3. Testing authorization URL generation...")
        try:
            auth_url = oauth_service.get_authorization_url(state="test_state")
            self.stdout.write(self.style.SUCCESS("✅ Authorization URL generated"))
            self.stdout.write(f"📋 URL: {auth_url[:50]}...")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Authorization URL error: {e}"))
            return
        
        # Test 4: Check Region Configuration
        self.stdout.write("\n4. Checking Region Configuration...")
        region = config.get('REGION', 'Unknown')
        if region == 'EU':
            self.stdout.write(self.style.SUCCESS(f"✅ Region: {region} (EU endpoints configured)"))
            expected_auth_url = 'https://accounts.zoho.eu/oauth/v2/auth'
            expected_token_url = 'https://accounts.zoho.eu/oauth/v2/token'
            expected_api_url = 'https://mail.zoho.eu/api/'
            
            if config['AUTH_URL'] == expected_auth_url:
                self.stdout.write(self.style.SUCCESS("✅ AUTH_URL correctly set for EU"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ AUTH_URL mismatch: {config['AUTH_URL']} (expected: {expected_auth_url})"))
                
            if config['TOKEN_URL'] == expected_token_url:
                self.stdout.write(self.style.SUCCESS("✅ TOKEN_URL correctly set for EU"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ TOKEN_URL mismatch: {config['TOKEN_URL']} (expected: {expected_token_url})"))
                
            if config['BASE_URL'] == expected_api_url:
                self.stdout.write(self.style.SUCCESS("✅ BASE_URL correctly set for EU"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ BASE_URL mismatch: {config['BASE_URL']} (expected: {expected_api_url})"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Region: {region} (not EU-specific)"))
        
        # Test 5: Test Zoho API endpoints accessibility
        self.stdout.write("\n5. Testing Zoho API accessibility...")
        try:
            # Test if Zoho auth endpoint is reachable
            response = requests.get(config['AUTH_URL'], timeout=10)
            if response.status_code in [200, 302, 400]:  # 400 is expected without params
                self.stdout.write(self.style.SUCCESS("✅ Zoho Auth API accessible"))
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️ Zoho Auth API returned {response.status_code}")
                )
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ Zoho API not accessible: {e}"))
        
        # Test 6: Check mail app settings
        self.stdout.write("\n6. Checking Mail App settings...")
        mail_settings = settings.MAIL_APP_SETTINGS
        default_email = mail_settings.get('DEFAULT_EMAIL_ACCOUNT')
        
        if default_email == 'kontakt@workloom.de':
            self.stdout.write(self.style.SUCCESS(f"✅ Default email: {default_email}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠️ Default email: {default_email} (expected: kontakt@workloom.de)")
            )
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("🎉 Configuration Test Complete!"))
        self.stdout.write("\n📋 Next Steps:")
        self.stdout.write("1. Start Django server: python manage.py runserver")
        self.stdout.write("2. Visit: http://localhost:8000/mail/")
        self.stdout.write("3. Click 'Connect Email Account' to test OAuth flow")
        self.stdout.write("4. Login with kontakt@workloom.de credentials")
        
        self.stdout.write("\n🔍 If OAuth fails, check:")
        self.stdout.write("- App is created in EU region (accounts.zoho.eu)")
        self.stdout.write("- Redirect URI matches exactly in Zoho Console")
        self.stdout.write("- Client ID and Secret are correct")
        self.stdout.write("- Required scopes are enabled: ZohoMail.messages.ALL, ZohoMail.folders.ALL, ZohoMail.accounts.READ")
        self.stdout.write("- kontakt@workloom.de has access to the OAuth app")
        self.stdout.write("- Check Django logs for detailed error messages")
        
        self.stdout.write("\n🌍 EU Region Specific:")
        self.stdout.write("- OAuth app must be created at: https://api-console.zoho.eu/")
        self.stdout.write("- Login URL will be: https://accounts.zoho.eu/...")
        self.stdout.write("- All API calls go to: https://mail.zoho.eu/api/")
        
        self.stdout.write("\n📋 Debug Commands:")
        self.stdout.write("- Check logs: python manage.py runserver --verbosity=2")
        self.stdout.write("- Test config: python manage.py test_zoho_config")  
        self.stdout.write("- Admin panel: http://localhost:8000/admin/mail_app/")