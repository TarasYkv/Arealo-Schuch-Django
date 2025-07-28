"""
Sync all emails from the last 90 days from all folders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync all emails from the last 90 days'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Specific email account to sync')
        parser.add_argument('--days', type=int, default=90, help='Number of days to sync (default: 90)')
        parser.add_argument('--limit', type=int, default=1000, help='Maximum emails per folder (default: 1000)')

    def handle(self, *args, **options):
        email_address = options.get('email')
        days = options['days']
        limit = options['limit']
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        self.stdout.write(f"Synchronizing emails from {start_date.date()} to {end_date.date()}")
        self.stdout.write(f"Maximum {limit} emails per folder\n")
        
        # Get accounts to sync
        if email_address:
            accounts = EmailAccount.objects.filter(email_address=email_address, is_active=True)
        else:
            accounts = EmailAccount.objects.filter(is_active=True)
        
        if not accounts.exists():
            self.stdout.write(self.style.ERROR('No active email accounts found'))
            return
        
        total_stats = {'fetched': 0, 'created': 0, 'updated': 0, 'errors': 0}
        
        for account in accounts:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Account: {account.email_address}")
            self.stdout.write(f"{'='*60}")
            
            try:
                sync_service = EmailSyncService(account)
                
                # First sync folders
                self.stdout.write("Syncing folders...")
                folders_synced = sync_service.sync_folders()
                self.stdout.write(f"✓ {folders_synced} folders synced")
                
                # Get all folders
                folders = account.folders.all()
                self.stdout.write(f"\nProcessing {folders.count()} folders:")
                
                # Sync each folder individually for better control
                for folder in folders:
                    self.stdout.write(f"\n📁 {folder.name}:")
                    
                    try:
                        # Sync with higher limit to ensure we get all emails from last 90 days
                        stats = sync_service.sync_emails(
                            folder=folder,
                            limit=limit,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        self.stdout.write(f"   Fetched: {stats['fetched']}, Created: {stats['created']}")
                        
                        # Add to total stats
                        for key in total_stats:
                            total_stats[key] += stats.get(key, 0)
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   Error: {str(e)}"))
                        total_stats['errors'] += 1
                
                # Show emails in date range
                emails_in_range = account.emails.filter(
                    sent_at__gte=start_date,
                    sent_at__lte=end_date
                ).count()
                
                self.stdout.write(f"\n📊 Summary for {account.email_address}:")
                self.stdout.write(f"   Total emails in last {days} days: {emails_in_range}")
                self.stdout.write(f"   Total emails in database: {account.emails.count()}")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error syncing account: {str(e)}"))
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("FINAL TOTALS:")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Fetched: {total_stats['fetched']}")
        self.stdout.write(f"Created: {total_stats['created']}")
        self.stdout.write(f"Updated: {total_stats['updated']}")
        self.stdout.write(f"Errors: {total_stats['errors']}")
        
        # Show global email count for date range
        total_emails_in_range = 0
        for account in EmailAccount.objects.filter(is_active=True):
            total_emails_in_range += account.emails.filter(
                sent_at__gte=start_date,
                sent_at__lte=end_date
            ).count()
        
        self.stdout.write(f"\nTotal emails in last {days} days: {total_emails_in_range}")
        self.stdout.write(self.style.SUCCESS("\n✅ Sync complete!"))