"""
Test Zoho Mail API sync directly
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount, Folder
from mail_app.services import ZohoMailAPIService, EmailSyncService
import json
from datetime import datetime, timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Test Zoho Mail API sync directly'

    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        if not account:
            self.stdout.write(self.style.ERROR('No active email account found'))
            return
            
        self.stdout.write(f"\n📧 Testing sync for: {account.email_address}")
        
        # Test 1: Check API connection
        self.stdout.write("\n1️⃣ Testing API Connection...")
        try:
            api_service = ZohoMailAPIService(account)
            account_id = api_service.get_account_id()
            self.stdout.write(f"   ✅ Account ID: {account_id}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ API Error: {str(e)}"))
            return
            
        # Test 2: Check folders
        self.stdout.write("\n2️⃣ Checking Folders...")
        inbox = account.folders.filter(folder_type='inbox').first()
        if not inbox:
            self.stdout.write(self.style.ERROR("   ❌ No inbox folder found!"))
            return
        self.stdout.write(f"   ✅ Inbox found: {inbox.name} (ID: {inbox.zoho_folder_id})")
        
        # Test 3: Direct API call to get emails
        self.stdout.write("\n3️⃣ Testing Direct API Call...")
        try:
            # Build URL for messages
            url = f"{api_service.base_url}accounts/{account_id}/folders/{inbox.zoho_folder_id}/messages"
            params = {
                'limit': 10,
                'sortorder': 'desc'
            }
            
            self.stdout.write(f"   URL: {url}")
            self.stdout.write(f"   Params: {params}")
            
            response = api_service._make_request('GET', url, params=params)
            
            if response and 'data' in response:
                messages = response['data']
                self.stdout.write(f"   ✅ Found {len(messages)} messages!")
                
                # Show first 3 messages
                for i, msg in enumerate(messages[:3]):
                    self.stdout.write(f"\n   Message {i+1}:")
                    self.stdout.write(f"     - ID: {msg.get('messageId')}")
                    self.stdout.write(f"     - From: {msg.get('fromAddress')}")
                    self.stdout.write(f"     - Subject: {msg.get('subject', '(no subject)')[:50]}")
                    self.stdout.write(f"     - Date: {msg.get('receivedTime')}")
            else:
                self.stdout.write(f"   ⚠️  Response: {response}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Direct API Error: {str(e)}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            
        # Test 4: Test sync service
        self.stdout.write("\n4️⃣ Testing Sync Service...")
        try:
            sync_service = EmailSyncService(account)
            
            # Try syncing just inbox with small limit
            stats = sync_service.sync_emails(folder=inbox, limit=5)
            self.stdout.write(f"   Sync stats: {stats}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Sync Error: {str(e)}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            
        # Test 5: Check database
        self.stdout.write("\n5️⃣ Database Status:")
        email_count = account.emails.count()
        self.stdout.write(f"   Total emails in DB: {email_count}")
        if email_count > 0:
            latest = account.emails.order_by('-sent_at').first()
            self.stdout.write(f"   Latest email: {latest.subject[:50]} ({latest.sent_at})")