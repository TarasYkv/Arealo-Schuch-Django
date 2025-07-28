"""
Django Management Command to fix email addresses stored as array strings
"""
from django.core.management.base import BaseCommand
from mail_app.models import EmailAccount
import re
import json


class Command(BaseCommand):
    help = 'Fix email addresses that are stored as array strings'

    def handle(self, *args, **options):
        self.stdout.write('Fixing email addresses...')
        
        # Find accounts with array-like email addresses
        accounts = EmailAccount.objects.filter(email_address__contains='[{')
        
        for account in accounts:
            self.stdout.write(f'Found bad email address for account {account.id}: {account.email_address[:100]}...')
            
            try:
                # Try to extract the primary email from the array string
                array_str = account.email_address
                
                # Use regex to find mailId values
                mail_id_pattern = r"'mailId':\s*'([^']+)'"
                matches = re.findall(mail_id_pattern, array_str)
                
                if matches:
                    # Find primary email (first match as fallback)
                    primary_email = matches[0]
                    
                    # Look for the one marked as primary
                    primary_pattern = r"'isPrimary':\s*True.*?'mailId':\s*'([^']+)'"
                    primary_matches = re.findall(primary_pattern, array_str)
                    
                    if primary_matches:
                        primary_email = primary_matches[0]
                    
                    self.stdout.write(f'Extracted email: {primary_email}')
                    
                    # Update the account
                    account.email_address = primary_email
                    account.display_name = primary_email
                    account.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Fixed account {account.id}: {primary_email}')
                    )
                    
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Could not extract email from account {account.id}')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing account {account.id}: {str(e)}')
                )
        
        self.stdout.write(self.style.SUCCESS('Done fixing email addresses'))