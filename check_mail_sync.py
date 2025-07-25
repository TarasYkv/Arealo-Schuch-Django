#!/usr/bin/env python
"""
Quick debug script for email sync issues
Run this on the server: python check_mail_sync.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from mail_app.models import EmailAccount, Folder
from mail_app.services import ZohoMailAPIService

def main():
    print("=" * 60)
    print("Email Sync Debug Tool")
    print("=" * 60)
    
    # Get all active accounts
    accounts = EmailAccount.objects.filter(is_active=True)
    print(f"\nFound {accounts.count()} active email account(s)")
    
    for account in accounts:
        print(f"\n📧 Account: {account.email_address}")
        print(f"   User: {account.user.email}")
        
        # Check folders
        folder_count = account.folders.count()
        print(f"   Folders in DB: {folder_count}")
        
        if folder_count == 0:
            print("   ⚠️  NO FOLDERS FOUND - This is why sync shows 0!")
            print("   → Attempting to sync folders...")
            
            try:
                service = ZohoMailAPIService(account)
                
                # Check if we have valid tokens
                zoho_settings = account.user.zoho_mail_settings
                if not zoho_settings.access_token:
                    print("   ❌ No access token - needs re-authorization!")
                    continue
                
                # Try to get account ID first
                try:
                    account_id = service.get_account_id()
                    print(f"   ✅ Zoho Account ID: {account_id}")
                except Exception as e:
                    print(f"   ❌ Cannot get account ID: {str(e)}")
                    continue
                
                # Try to fetch folders
                try:
                    from mail_app.services import EmailSyncService
                    sync_service = EmailSyncService(account)
                    folder_count = sync_service.sync_folders()
                    print(f"   ✅ Synced {folder_count} folders!")
                    
                    # List folders
                    for folder in account.folders.all()[:5]:
                        print(f"      • {folder.name} ({folder.folder_type})")
                        
                except Exception as e:
                    print(f"   ❌ Error syncing folders: {str(e)}")
                    
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
        else:
            # Show existing folders
            print("   Folders:")
            for folder in account.folders.all()[:5]:
                print(f"      • {folder.name} - {folder.total_count} emails")
        
        # Check email count
        email_count = account.emails.count()
        print(f"   Emails in DB: {email_count}")
        
    print("\n" + "=" * 60)
    print("SOLUTION: If no folders found, the user needs to:")
    print("1. Go to Mail Dashboard")
    print("2. Click 'Jetzt synchronisieren'")
    print("3. This should fetch folders first, then emails")
    print("=" * 60)

if __name__ == "__main__":
    main()