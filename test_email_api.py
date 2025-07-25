from mail_app.models import EmailAccount, Folder
from mail_app.services import ZohoMailAPIService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='taras')
account = EmailAccount.objects.filter(user=user, is_active=True).first()
folder = account.folders.first()

print(f'Account: {account.email_address if account else "None"}')
print(f'Folder: {folder.name if folder else "None"}')

if account and folder:
    api_service = ZohoMailAPIService(account)
    emails = api_service.get_emails(folder.zoho_folder_id, limit=1)
    print(f'Got {len(emails)} emails')
    
    if emails:
        email = emails[0]
        print('')
        print('Available fields:')
        for key in sorted(email.keys()):
            print(f'  {key}')
        
        print('')
        print('Content fields:')
        content_fields = ['content', 'body', 'bodyText', 'bodyHtml', 'htmlContent', 'summary']
        for key in content_fields:
            value = email.get(key, 'NOT_FOUND')
            if value and value != 'NOT_FOUND':
                print(f'{key}: {str(value)[:200]}...')
            else:
                print(f'{key}: {value}')
else:
    print('No account or folder found')