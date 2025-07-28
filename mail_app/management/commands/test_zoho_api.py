"""
Test Zoho API endpoints directly
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
from mail_app.services import ZohoMailAPIService
import requests


class Command(BaseCommand):
    help = 'Test Zoho API endpoints directly'
    
    def handle(self, *args, **options):
        account = EmailAccount.objects.filter(is_active=True).first()
        
        if not account:
            self.stdout.write(self.style.ERROR("No active email account found"))
            return
            
        self.stdout.write(f"Testing API for account: {account.email_address}")
        
        api_service = ZohoMailAPIService(account)
        
        # Test 1: Get account info
        try:
            self.stdout.write("\n1. Testing account info...")
            account_info = api_service.get_account_info()
            self.stdout.write(self.style.SUCCESS(f"✓ Account info retrieved"))
            self.stdout.write(f"Account ID: {account_info.get('accountId')}")
            self.stdout.write(f"Account Name: {account_info.get('accountName')}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Account info failed: {e}"))
        
        # Test 2: Get folders
        try:
            self.stdout.write("\n2. Testing folders...")
            account_id = api_service.get_account_id()
            folders = api_service.get_folders(account_id)
            self.stdout.write(self.style.SUCCESS(f"✓ Found {len(folders)} folders"))
            
            for folder in folders[:3]:  # Show first 3 folders
                self.stdout.write(f"  - {folder.get('folderName')}: {folder.get('folderId')}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Folders failed: {e}"))
        
        # Test 3: Try different email endpoints
        try:
            self.stdout.write("\n3. Testing email endpoints...")
            account_id = api_service.get_account_id()
            
            # Get inbox folder
            folders = api_service.get_folders(account_id)
            inbox_folder = None
            for folder in folders:
                if folder.get('folderName', '').lower() in ['inbox', 'posteingang']:
                    inbox_folder = folder
                    break
            
            if not inbox_folder:
                inbox_folder = folders[0] if folders else None
                
            if inbox_folder:
                folder_id = inbox_folder.get('folderId')
                self.stdout.write(f"Testing with folder: {inbox_folder.get('folderName')} ({folder_id})")
                
                # Test different endpoint variations
                base_url = "https://mail.zoho.com/api"
                headers = {'Authorization': f'Zoho-oauthtoken {account.access_token}'}
                
                endpoints_to_test = [
                    f"accounts/{account_id}/folders/{folder_id}/messages",
                    f"accounts/{account_id}/messages?folderId={folder_id}",
                    f"accounts/{account_id}/folders/{folder_id}/emails",
                    f"folders/{folder_id}/messages",
                    f"messages?accountId={account_id}&folderId={folder_id}"
                ]
                
                for endpoint in endpoints_to_test:
                    try:
                        url = f"{base_url}/{endpoint}"
                        self.stdout.write(f"\nTesting: {endpoint}")
                        
                        response = requests.get(
                            url,
                            headers=headers,
                            params={'limit': 1}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            self.stdout.write(self.style.SUCCESS(f"✓ Success! Response type: {type(data)}"))
                            if isinstance(data, dict):
                                self.stdout.write(f"  Keys: {list(data.keys())}")
                            elif isinstance(data, list):
                                self.stdout.write(f"  List length: {len(data)}")
                        else:
                            self.stdout.write(self.style.WARNING(f"✗ Status {response.status_code}: {response.text[:100]}"))
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"✗ Exception: {e}"))
            else:
                self.stdout.write(self.style.ERROR("No folders found to test"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Email endpoint test failed: {e}"))