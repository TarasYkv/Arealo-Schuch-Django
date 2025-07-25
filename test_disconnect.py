#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'workloom.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from accounts.views import zoho_disconnect_api
from mail_app.models import EmailAccount, Email, Folder

User = get_user_model()

# Get user
user = User.objects.get(username='taras')

# Count data before disconnect
account = EmailAccount.objects.filter(user=user, is_active=True).first()
if account:
    emails_before = account.emails.count() 
    folders_before = account.folders.count()
    print(f"Before disconnect: {emails_before} emails, {folders_before} folders")
else:
    print("No active account found")

# Create fake request
factory = RequestFactory()
request = factory.post('/accounts/api/zoho-disconnect/')
request.user = user

# Test the disconnect function
try:
    response = zoho_disconnect_api(request)
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.content.decode()}")
    
    # Check counts after disconnect
    if account:
        emails_after = Email.objects.filter(account=account).count()
        folders_after = Folder.objects.filter(account=account).count()  
        print(f"After disconnect: {emails_after} emails, {folders_after} folders")
        
        # Check account status
        account.refresh_from_db()
        print(f"Account is_active: {account.is_active}")
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()