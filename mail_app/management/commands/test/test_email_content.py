"""
Test email content fetching to diagnose incomplete body issue
"""
from django.core.management.base import BaseCommand
from mail_app.models import Email, EmailAccount
from mail_app.services import ZohoMailAPIService
import json


class Command(BaseCommand):
    help = 'Test email content fetching'

    def add_arguments(self, parser):
        parser.add_argument('email_id', type=int, help='Email ID to test')

    def handle(self, *args, **options):
        email_id = options['email_id']
        
        try:
            email = Email.objects.get(id=email_id)
            self.stdout.write(f"📧 Testing Email {email.id}:")
            self.stdout.write(f"   Subject: {email.subject}")
            self.stdout.write(f"   Zoho Message ID: {email.zoho_message_id}")
            
            # Show current content
            self.stdout.write(f"\n📄 Current stored content:")
            self.stdout.write(f"   Body Text Length: {len(email.body_text or '')}")
            self.stdout.write(f"   Body HTML Length: {len(email.body_html or '')}")
            
            if email.body_text:
                self.stdout.write(f"   Text Preview: {email.body_text[:200]}...")
            if email.body_html:
                self.stdout.write(f"   HTML Preview: {email.body_html[:200]}...")
            
            # Test API
            self.stdout.write(f"\n🔍 Testing Zoho API endpoints:")
            
            account = email.account
            api_service = ZohoMailAPIService(account)
            account_id = api_service.get_account_id()
            
            endpoints = [
                (f"accounts/{account_id}/messages/{email.zoho_message_id}/content", "Content Endpoint"),
                (f"accounts/{account_id}/messages/{email.zoho_message_id}/view", "View Endpoint"),
                (f"accounts/{account_id}/messages/{email.zoho_message_id}", "Basic Endpoint"),
                (f"accounts/{account_id}/folders/{email.folder.zoho_folder_id}/messages/{email.zoho_message_id}/content", "Folder Content"),
            ]
            
            headers = api_service._get_headers()
            
            for endpoint, name in endpoints:
                url = f"{api_service.base_url}{endpoint}"
                self.stdout.write(f"\n📌 Testing {name}:")
                self.stdout.write(f"   URL: {url}")
                
                try:
                    import requests
                    response = requests.get(url, headers=headers, timeout=30)
                    self.stdout.write(f"   Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Pretty print the response structure
                        self.stdout.write("   Response structure:")
                        if isinstance(data, dict):
                            for key in data.keys():
                                value = data[key]
                                if isinstance(value, str):
                                    self.stdout.write(f"     {key}: {len(value)} chars")
                                    if key in ['content', 'htmlContent', 'body', 'bodyHtml', 'textContent']:
                                        self.stdout.write(f"       Preview: {value[:100]}...")
                                else:
                                    self.stdout.write(f"     {key}: {type(value).__name__}")
                        
                        # Check for specific content fields
                        content_fields = ['content', 'htmlContent', 'body', 'bodyHtml', 'textContent', 'data']
                        for field in content_fields:
                            if field in data:
                                if field == 'data' and isinstance(data[field], dict):
                                    # Check nested data
                                    for subfield in ['content', 'htmlContent', 'body']:
                                        if subfield in data[field]:
                                            self.stdout.write(f"     Found {field}.{subfield}: {len(str(data[field][subfield]))} chars")
                                else:
                                    self.stdout.write(f"     Found {field}: {len(str(data[field]))} chars")
                    
                except Exception as e:
                    self.stdout.write(f"   Error: {str(e)}")
            
        except Email.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Email {email_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))