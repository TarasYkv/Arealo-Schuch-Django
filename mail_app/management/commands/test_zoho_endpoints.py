"""
Django Management Command to test Zoho Mail API endpoints
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mail_app.services import ZohoMailAPIService
from mail_app.models import EmailAccount
import requests
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Test different Zoho Mail API endpoints to find working ones'

    def handle(self, *args, **options):
        try:
            # Get user and account
            user = User.objects.get(username='taras')
            account = EmailAccount.objects.filter(user=user, is_active=True).first()
            
            if not account:
                self.stdout.write(self.style.ERROR('No active email account found'))
                return
                
            service = ZohoMailAPIService(account)
            headers = service._get_headers()
            base_url = service.base_url
            
            self.stdout.write(f'Base URL: {base_url}')
            self.stdout.write(f'Email: {account.email_address}')
            
            # Test different endpoint formats
            endpoints_to_test = [
                # Account endpoints
                'accounts',
                'me',
                'user',
                
                # Folder endpoints
                'folders',
                'me/folders',
                f'accounts/{account.email_address}/folders',
                'user/folders',
                
                # Message endpoints  
                'messages',
                'me/messages',
                f'accounts/{account.email_address}/messages',
                'user/messages',
                'messages/view',
                'me/messages/view',
            ]
            
            for endpoint in endpoints_to_test:
                try:
                    url = f"{base_url}{endpoint}"
                    self.stdout.write(f'\\nTesting: {url}')
                    
                    response = requests.get(url, headers=headers, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ SUCCESS: {endpoint}')
                        )
                        self.stdout.write(f'Response keys: {list(data.keys()) if isinstance(data, dict) else "not dict"}')
                        
                        # Show first few items for debugging
                        if isinstance(data, dict) and 'data' in data:
                            data_content = data['data']
                            if isinstance(data_content, list) and len(data_content) > 0:
                                self.stdout.write(f'First item keys: {list(data_content[0].keys()) if isinstance(data_content[0], dict) else "not dict"}')
                                
                    elif response.status_code == 404:
                        error_data = response.json() if response.content else {}
                        if error_data.get('data', {}).get('errorCode') == 'URL_RULE_NOT_CONFIGURED':
                            self.stdout.write(f'❌ NOT_CONFIGURED: {endpoint}')
                        else:
                            self.stdout.write(f'❌ 404: {endpoint}')
                            
                    elif response.status_code == 401:
                        self.stdout.write(f'🔒 UNAUTHORIZED: {endpoint}')
                        
                    elif response.status_code == 403:
                        self.stdout.write(f'🚫 FORBIDDEN: {endpoint}')
                        
                    elif response.status_code == 429:
                        self.stdout.write(f'⏱️ RATE_LIMITED: {endpoint}')
                        
                    else:
                        self.stdout.write(f'⚠️ {response.status_code}: {endpoint}')
                        
                except requests.exceptions.RequestException as e:
                    self.stdout.write(f'🌐 NETWORK_ERROR: {endpoint} - {str(e)}')
                except Exception as e:
                    self.stdout.write(f'❗ ERROR: {endpoint} - {str(e)}')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))