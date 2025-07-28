"""
Management command to manually sync emails from Zoho Mail
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from mail_app.models import EmailAccount
from mail_app.services import EmailSyncService

User = get_user_model()


class Command(BaseCommand):
    help = 'Manually sync emails from Zoho Mail'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Specific email account ID to sync'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum emails per folder to sync (default: 50)'
        )
        parser.add_argument(
            '--folder-id',
            type=int,
            help='Specific folder ID to sync'
        )

    def handle(self, *args, **options):
        self.stdout.write("🔄 Starting Email Synchronization...")
        
        # Get email accounts to sync
        accounts = EmailAccount.objects.filter(is_active=True, sync_enabled=True)
        
        if options['account_id']:
            accounts = accounts.filter(id=options['account_id'])
            if not accounts.exists():
                raise CommandError(f"No active email account found with ID {options['account_id']}")
        
        if not accounts.exists():
            self.stdout.write(self.style.WARNING("⚠️ No active email accounts found to sync"))
            return
        
        total_stats = {'fetched': 0, 'created': 0, 'updated': 0, 'errors': 0}
        
        for account in accounts:
            self.stdout.write(f"\n📧 Syncing account: {account.email_address}")
            
            try:
                sync_service = EmailSyncService(account)
                
                # Sync folders first
                self.stdout.write("📁 Syncing folders...")
                folders_synced = sync_service.sync_folders()
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Synced {folders_synced} folders")
                )
                
                # Sync emails
                self.stdout.write("📨 Syncing emails...")
                
                folder_filter = None
                if options['folder_id']:
                    try:
                        folder_filter = account.folders.get(id=options['folder_id'])
                        self.stdout.write(f"📂 Syncing only folder: {folder_filter.name}")
                    except account.folders.model.DoesNotExist:
                        raise CommandError(f"Folder ID {options['folder_id']} not found")
                
                sync_stats = sync_service.sync_emails(
                    folder=folder_filter,
                    limit=options['limit']
                )
                
                # Update totals
                for key in total_stats:
                    total_stats[key] += sync_stats[key]
                
                # Display account stats
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Account sync complete: "
                        f"Fetched: {sync_stats['fetched']}, "
                        f"Created: {sync_stats['created']}, "
                        f"Errors: {sync_stats['errors']}"
                    )
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error syncing {account.email_address}: {str(e)}")
                )
                total_stats['errors'] += 1
        
        # Display final summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("🎉 Email Sync Complete!"))
        self.stdout.write(f"📊 Total Statistics:")
        self.stdout.write(f"  • Emails fetched: {total_stats['fetched']}")
        self.stdout.write(f"  • Emails created: {total_stats['created']}")
        self.stdout.write(f"  • Emails updated: {total_stats['updated']}")
        self.stdout.write(f"  • Errors: {total_stats['errors']}")
        
        if total_stats['errors'] > 0:
            self.stdout.write(
                self.style.WARNING("\n⚠️ Some errors occurred. Check logs for details.")
            )