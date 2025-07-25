#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from mail_app.models import Email, EmailAccount, Folder

# Get account
account = EmailAccount.objects.filter(is_active=True).first()
print(f'Account: {account.email_address}')
print(f'Total emails in DB: {Email.objects.filter(account=account).count()}')

# Check folders
folders = Folder.objects.filter(account=account)
print(f'\nFolders ({folders.count()}):')
for folder in folders:
    email_count = Email.objects.filter(account=account, folder=folder).count()
    print(f'  {folder.name}: {email_count} emails')

# Check recent emails
print('\nRecent emails:')
recent_emails = Email.objects.filter(account=account).order_by('-created_at')[:5]
for email in recent_emails:
    print(f'  {email.subject[:50]} - {email.created_at}')