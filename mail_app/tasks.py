"""
Celery tasks for Mail App background processing
"""
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import EmailAccount, SyncLog
from .services import EmailSyncService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_emails(self, account_id=None):
    """
    Background task to sync emails from Zoho Mail.
    
    Args:
        account_id: Optional specific account ID to sync
    """
    try:
        # Get email accounts to sync
        accounts = EmailAccount.objects.filter(is_active=True, sync_enabled=True)
        
        if account_id:
            accounts = accounts.filter(id=account_id)
            if not accounts.exists():
                logger.error(f"No active email account found with ID {account_id}")
                return
        
        if not accounts.exists():
            logger.info("No active email accounts found to sync")
            return
        
        total_synced = 0
        total_errors = 0
        
        for account in accounts:
            logger.info(f"Starting sync for account: {account.email_address}")
            
            # Create sync log entry
            sync_log = SyncLog.objects.create(
                account=account,
                sync_type='scheduled',
                started_at=timezone.now(),
                status='running'
            )
            
            try:
                sync_service = EmailSyncService(account)
                
                # Sync folders first
                folders_synced = sync_service.sync_folders()
                
                # Sync emails with configured limit
                sync_stats = sync_service.sync_emails(
                    limit=settings.MAIL_APP_SETTINGS.get('MAX_EMAILS_PER_SYNC', 100)
                )
                
                # Update sync log
                sync_log.status = 'completed'
                sync_log.completed_at = timezone.now()
                sync_log.emails_fetched = sync_stats['fetched']
                sync_log.emails_created = sync_stats['created']
                sync_log.emails_updated = sync_stats['updated']
                sync_log.folders_synced = folders_synced
                sync_log.error_count = sync_stats['errors']
                
                if sync_stats['errors'] > 0:
                    sync_log.error_message = f"{sync_stats['errors']} errors occurred during sync"
                
                sync_log.save()
                
                total_synced += sync_stats['fetched']
                total_errors += sync_stats['errors']
                
                logger.info(
                    f"Sync completed for {account.email_address}: "
                    f"Fetched: {sync_stats['fetched']}, "
                    f"Created: {sync_stats['created']}, "
                    f"Errors: {sync_stats['errors']}"
                )
                
            except Exception as e:
                # Update sync log with error
                sync_log.status = 'failed'
                sync_log.completed_at = timezone.now()
                sync_log.error_message = str(e)
                sync_log.save()
                
                total_errors += 1
                logger.error(f"Error syncing emails for {account.email_address}: {str(e)}")
                
                # Retry task if not exceeded max retries
                if self.request.retries < self.max_retries:
                    logger.info(f"Retrying sync for {account.email_address} (attempt {self.request.retries + 1})")
                    raise self.retry(countdown=60 * (self.request.retries + 1))
        
        logger.info(f"Email sync task completed. Total synced: {total_synced}, Errors: {total_errors}")
        return {
            'total_synced': total_synced,
            'total_errors': total_errors,
            'accounts_processed': len(accounts)
        }
        
    except Exception as e:
        logger.error(f"Critical error in sync_emails task: {str(e)}")
        raise


@shared_task
def sync_single_account(account_id, folder_id=None, limit=1000):
    """
    Background task to sync a single email account.
    
    Args:
        account_id: Email account ID to sync
        folder_id: Optional specific folder ID to sync
        limit: Maximum emails to sync per folder
    """
    try:
        account = EmailAccount.objects.get(id=account_id, is_active=True)
        logger.info(f"Starting single account sync: {account.email_address}")
        
        # Create sync log entry
        sync_log = SyncLog.objects.create(
            account=account,
            sync_type='manual',
            started_at=timezone.now(),
            status='running'
        )
        
        try:
            sync_service = EmailSyncService(account)
            
            # Sync folders first
            folders_synced = sync_service.sync_folders()
            
            # Sync emails for specific folder or all folders
            folder_filter = None
            if folder_id:
                folder_filter = account.folders.get(id=folder_id)
            
            # Set date range for last 90 days
            from datetime import timedelta
            end_date = timezone.now()
            start_date = end_date - timedelta(days=90)
            
            sync_stats = sync_service.sync_emails(
                folder=folder_filter, 
                limit=limit,
                start_date=start_date,
                end_date=end_date
            )
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.emails_fetched = sync_stats['fetched']
            sync_log.emails_created = sync_stats['created']
            sync_log.emails_updated = sync_stats['updated']
            sync_log.folders_synced = folders_synced
            sync_log.error_count = sync_stats['errors']
            
            if sync_stats['errors'] > 0:
                sync_log.error_message = f"{sync_stats['errors']} errors occurred during sync"
            
            sync_log.save()
            
            logger.info(f"Single account sync completed: {sync_stats}")
            return sync_stats
            
        except Exception as e:
            # Update sync log with error
            sync_log.status = 'failed'
            sync_log.completed_at = timezone.now()
            sync_log.error_message = str(e)
            sync_log.save()
            
            logger.error(f"Error in single account sync for {account.email_address}: {str(e)}")
            raise
            
    except EmailAccount.DoesNotExist:
        logger.error(f"Email account with ID {account_id} not found")
        raise
    except Exception as e:
        logger.error(f"Critical error in sync_single_account task: {str(e)}")
        raise


@shared_task
def cleanup_old_sync_logs(days=30):
    """
    Background task to cleanup old sync logs.
    
    Args:
        days: Number of days to keep sync logs (default: 30)
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        deleted_count = SyncLog.objects.filter(
            started_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old sync logs older than {days} days")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up sync logs: {str(e)}")
        raise


@shared_task
def refresh_expired_tokens():
    """
    Background task to refresh expired OAuth tokens.
    """
    try:
        # Find accounts with expired or soon-to-expire tokens
        soon_expire = timezone.now() + timezone.timedelta(minutes=30)
        accounts = EmailAccount.objects.filter(
            is_active=True,
            token_expires_at__lt=soon_expire,
            refresh_token__isnull=False
        )
        
        refreshed_count = 0
        
        for account in accounts:
            try:
                from .services import ZohoMailAPIService
                api_service = ZohoMailAPIService(account)
                api_service._refresh_token()
                refreshed_count += 1
                logger.info(f"Refreshed token for {account.email_address}")
                
            except Exception as e:
                logger.error(f"Error refreshing token for {account.email_address}: {str(e)}")
                # Mark account as inactive if refresh fails
                account.is_active = False
                account.save(update_fields=['is_active'])
        
        logger.info(f"Token refresh task completed. Refreshed: {refreshed_count}")
        return refreshed_count
        
    except Exception as e:
        logger.error(f"Critical error in refresh_expired_tokens task: {str(e)}")
        raise