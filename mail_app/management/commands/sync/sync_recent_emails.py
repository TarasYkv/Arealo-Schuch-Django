"""
Django Management Command to sync emails from last 90 days
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService, ReAuthorizationRequiredError
import pytz

User = get_user_model()


class Command(BaseCommand):
    help = 'Sync emails from the last 90 days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to sync (default: 90)'
        )

    def handle(self, *args, **options):
        days = options['days']
        
        try:
            # Get user and account
            user = User.objects.get(username='taras')
            account = EmailAccount.objects.filter(user=user, is_active=True).first()
            
            if not account:
                self.stdout.write(self.style.ERROR('No active email account found'))
                return
            
            self.stdout.write(f'Syncing emails for {account.email_address} from last {days} days')
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            self.stdout.write(f'Date range: {start_date.date()} to {end_date.date()}')
            
            # Create sync service
            sync_service = EmailSyncService(account)
            
            # Sync folders first
            self.stdout.write('Syncing folders...')
            folders_synced = sync_service.sync_folders()
            self.stdout.write(f'✅ Synced {folders_synced} folders')
            
            # Sync emails for each folder
            from mail_app.models import Folder
            folders = Folder.objects.filter(account=account)
            
            total_emails = 0
            
            for folder in folders:
                self.stdout.write(f'\\nSyncing folder: {folder.name}')
                
                try:
                    # Sync emails with date filter
                    sync_stats = sync_service.sync_emails(
                        folder=folder,
                        limit=1000,  # Limit per folder
                        start_date=start_date,
                        end_date=end_date
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
            
            # Update last sync time
            account.last_sync = timezone.now()
            account.save(update_fields=['last_sync'])
            
        except ReAuthorizationRequiredError as e:
            self.stdout.write(
                self.style.ERROR(f'🔑 Email authorization expired: {str(e)}')
            )
            self.stdout.write(
                self.style.WARNING('Please visit http://127.0.0.1:8000/mail/ to reconnect your email account')
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Command failed: {str(e)}'))