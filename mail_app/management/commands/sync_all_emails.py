"""
Django Management Command to sync all emails (no date filter)
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService, ReAuthorizationRequiredError

User = get_user_model()


class Command(BaseCommand):
    help = 'Sync all emails without date filtering'

    def handle(self, *args, **options):
        try:
            # Get user and account
            user = User.objects.get(username='taras')
            account = EmailAccount.objects.filter(user=user, is_active=True).first()
            
            if not account:
                self.stdout.write(self.style.ERROR('No active email account found'))
                return
            
            self.stdout.write(f'Syncing all emails for {account.email_address}')
            
            # Create sync service
            sync_service = EmailSyncService(account)
            
            # Sync folders first
            self.stdout.write('Syncing folders...')
            folders_synced = sync_service.sync_folders()
            self.stdout.write(f'✅ Synced {folders_synced} folders')
            
            # Sync emails for each folder (no date filter)
            from mail_app.models import Folder
            folders = Folder.objects.filter(account=account)
            
            total_emails = 0
            
            for folder in folders:
                self.stdout.write(f'\\nSyncing folder: {folder.name}')
                
                try:
                    # Sync emails without date filter
                    sync_stats = sync_service.sync_emails(
                        folder=folder,
                        limit=200
                    )
                    
                    if sync_stats:
                        fetched = sync_stats.get('fetched', 0)
                        created = sync_stats.get('created', 0)
                        updated = sync_stats.get('updated', 0)
                        
                        self.stdout.write(f'  Fetched: {fetched}, Created: {created}, Updated: {updated}')
                        total_emails += created
                    else:
                        self.stdout.write('  No sync stats returned')
                        
                except ReAuthorizationRequiredError as e:
                    self.stdout.write(
                        self.style.ERROR(f'🔑 Re-authorization required: {str(e)}')
                    )
                    self.stdout.write(
                        self.style.WARNING('Please visit /mail/ to reconnect your email account')
                    )
                    return
                except Exception as e:
                    self.stdout.write(f'  ❌ Error syncing folder {folder.name}: {str(e)}')
                    continue
            
            self.stdout.write(f'\\n🎉 Sync completed! Total new emails: {total_emails}')
            
        except ReAuthorizationRequiredError as e:
            self.stdout.write(
                self.style.ERROR(f'🔑 Email authorization expired: {str(e)}')
            )
            self.stdout.write(
                self.style.WARNING('Please visit http://127.0.0.1:8000/mail/ to reconnect your email account')
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))