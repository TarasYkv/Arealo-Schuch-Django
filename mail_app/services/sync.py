"""
Email Synchronization Service
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from .api import ZohoMailAPIService
from .exceptions import EmailSyncError, ZohoAPIError, ReAuthorizationRequiredError
from ..models import EmailAccount, Email, Folder, EmailAttachment, EmailThread, SyncLog
from ..constants import DEFAULT_EMAIL_LIMIT, MAX_EMAILS_PER_SYNC, FOLDER_TYPES

logger = logging.getLogger(__name__)


class EmailSyncService:
    """
    Service for synchronizing emails between Zoho Mail and local database.
    """
    
    def __init__(self, email_account: EmailAccount):
        self.account = email_account
        self.api_service = ZohoMailAPIService(email_account)
    
    def sync_folders(self) -> int:
        """
        Synchronize folders from Zoho Mail.
        
        Returns:
            Number of folders synced
        """
        try:
            folders_data = self.api_service.get_folders()
            synced_count = 0
            
            for folder_data in folders_data:
                folder_id = folder_data.get('folderId')
                folder_name = folder_data.get('folderName', '')
                
                # Map Zoho folder types to our folder types
                folder_type = self._map_folder_type(folder_name.lower())
                
                folder, created = Folder.objects.get_or_create(
                    account=self.account,
                    zoho_folder_id=folder_id,
                    defaults={
                        'name': folder_name,
                        'folder_type': folder_type,
                        'total_count': folder_data.get('totalCount', 0),
                        'unread_count': folder_data.get('unreadCount', 0)
                    }
                )
                
                if not created:
                    # Update existing folder
                    folder.name = folder_name
                    folder.folder_type = folder_type
                    folder.total_count = folder_data.get('totalCount', 0)
                    folder.unread_count = folder_data.get('unreadCount', 0)
                    folder.save(update_fields=['name', 'folder_type', 'total_count', 'unread_count'])
                
                synced_count += 1
                logger.info(f"{'Created' if created else 'Updated'} folder: {folder_name}")
            
            logger.info(f"Synced {synced_count} folders for {self.account.email_address}")
            return synced_count
            
        except ReAuthorizationRequiredError:
            # Re-raise re-authorization errors without wrapping
            raise
        except Exception as e:
            logger.error(f"Error syncing folders for {self.account.email_address}: {e}")
            raise EmailSyncError(f"Folder sync failed: {e}")
    
    def sync_emails(self, folder: Optional[Folder] = None, limit: int = DEFAULT_EMAIL_LIMIT, 
                   start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, int]:
        """
        Synchronize emails from Zoho Mail.
        
        Args:
            folder: Specific folder to sync (if None, sync all folders)
            limit: Maximum emails per folder
            start_date: Start date for email sync
            end_date: End date for email sync
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'fetched': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        try:
            # Get account ID
            account_id = self.api_service.get_account_id()
            
            # Determine which folders to sync
            if folder:
                folders_to_sync = [folder]
            else:
                folders_to_sync = self.account.folders.all()
            
            if not folders_to_sync:
                logger.warning(f"No folders to sync for {self.account.email_address}")
                return stats
            
            for folder_obj in folders_to_sync:
                try:
                    folder_stats = self._sync_folder_emails(
                        account_id, folder_obj, limit, start_date, end_date
                    )
                    
                    # Add to total stats
                    for key in stats:
                        stats[key] += folder_stats.get(key, 0)
                        
                except Exception as e:
                    logger.error(f"Error syncing folder {folder_obj.name}: {e}")
                    stats['errors'] += 1
            
            # Update account last sync time
            self.account.last_sync = timezone.now()
            self.account.save(update_fields=['last_sync'])
            
            logger.info(f"Email sync completed for {self.account.email_address}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Email sync failed for {self.account.email_address}: {e}")
            stats['errors'] += 1
            raise EmailSyncError(f"Email sync failed: {e}")
    
    def _sync_folder_emails(self, account_id: str, folder: Folder, limit: int,
                           start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, int]:
        """
        Sync emails for a specific folder.
        
        Args:
            account_id: Zoho account ID
            folder: Folder to sync
            limit: Email limit
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Statistics dictionary
        """
        stats = {'fetched': 0, 'created': 0, 'updated': 0, 'errors': 0}
        
        try:
            logger.info(f"Syncing emails for folder: {folder.name} (limit: {limit})")
            
            # Fetch emails from API with pagination
            emails_data = []
            remaining_limit = min(limit, MAX_EMAILS_PER_SYNC)
            start_index = 0
            batch_size = 200  # Zoho API seems to limit to 200 per request
            
            while remaining_limit > 0 and start_index < limit:
                current_batch_size = min(batch_size, remaining_limit)
                
                logger.info(f"Fetching batch: start={start_index}, limit={current_batch_size}")
                
                batch_emails = self.api_service.get_emails(
                    account_id=account_id,
                    folder_id=folder.zoho_folder_id,
                    limit=current_batch_size,
                    start=start_index
                )
                
                if not batch_emails:
                    # No more emails available
                    logger.info(f"No more emails available after {start_index} emails")
                    break
                
                emails_data.extend(batch_emails)
                
                # If we got less than requested, we've reached the end
                if len(batch_emails) < current_batch_size:
                    logger.info(f"Got {len(batch_emails)} emails, less than requested {current_batch_size}. End reached.")
                    break
                
                start_index += len(batch_emails)
                remaining_limit -= len(batch_emails)
                
                logger.info(f"Fetched {len(batch_emails)} emails, total so far: {len(emails_data)}")
            
            logger.info(f"Total emails fetched from API: {len(emails_data)}")
            
            stats['fetched'] = len(emails_data)
            
            if not emails_data:
                logger.info(f"No emails found in folder {folder.name}")
                return stats
            
            # Process each email
            with transaction.atomic():
                for email_data in emails_data:
                    try:
                        created = self._process_email(email_data, folder, start_date, end_date)
                        if created is True:
                            stats['created'] += 1
                        elif created is False:
                            stats['updated'] += 1
                        # None means skipped (filtered out)
                        
                    except Exception as e:
                        logger.error(f"Error processing email {email_data.get('messageId', 'unknown')}: {e}")
                        stats['errors'] += 1
            
            # Update folder counts
            folder.update_counts()
            
            logger.info(f"Folder {folder.name} sync complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing folder {folder.name}: {e}")
            stats['errors'] += 1
            return stats
    
    def _process_email(self, email_data: Dict, folder: Folder, 
                      start_date: Optional[datetime], end_date: Optional[datetime]) -> Optional[bool]:
        """
        Process a single email from API data.
        
        Args:
            email_data: Email data from API
            folder: Target folder
            start_date: Date filter
            end_date: Date filter
            
        Returns:
            True if created, False if updated, None if skipped
        """
        try:
            message_id = email_data.get('messageId')
            if not message_id:
                logger.warning("Email missing messageId, skipping")
                return None
            
            # Parse email date
            sent_at = self._parse_email_date(email_data.get('sentDateInGMT') or email_data.get('receivedTime'))
            
            # Apply date filters
            if start_date and sent_at < start_date:
                return None
            if end_date and sent_at > end_date:
                return None
            
            # Check if email already exists
            try:
                existing_email = Email.objects.get(zoho_message_id=message_id)
                # Update existing email
                self._update_email(existing_email, email_data, folder)
                return False
            except Email.DoesNotExist:
                # Create new email
                self._create_email(email_data, folder, sent_at)
                return True
                
        except Exception as e:
            logger.error(f"Error processing email {email_data.get('messageId', 'unknown')}: {e}")
            raise
    
    def _create_email(self, email_data: Dict, folder: Folder, sent_at: datetime) -> Email:
        """Create a new email from API data."""
        try:
            # Extract email fields
            subject = email_data.get('subject', '')
            from_email = self._extract_email_address(email_data.get('fromAddress', ''))
            from_name = self._extract_display_name(email_data.get('fromAddress', ''))
            
            # Parse recipients
            to_emails = self._parse_email_addresses(email_data.get('toAddress', ''))
            cc_emails = self._parse_email_addresses(email_data.get('ccAddress', ''))
            bcc_emails = self._parse_email_addresses(email_data.get('bccAddress', ''))
            
            # Create email object
            email = Email.objects.create(
                account=self.account,
                folder=folder,
                zoho_message_id=email_data.get('messageId'),
                message_id=email_data.get('messageId'),  # RFC message ID if available
                zoho_thread_id=email_data.get('threadId', ''),
                subject=subject,
                from_email=from_email,
                from_name=from_name,
                to_emails=to_emails,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                body_text=email_data.get('content', ''),
                body_html=email_data.get('htmlContent', ''),
                is_read=email_data.get('readFlag', False),
                is_starred=email_data.get('flagged', False),
                is_important=email_data.get('important', False),
                sent_at=sent_at,
                received_at=self._parse_email_date(email_data.get('receivedTime')) or sent_at
            )
            
            # Process attachments if any
            if email_data.get('hasAttachment', False):
                self._process_attachments(email, email_data)
            
            # Handle email threading
            self._handle_email_threading(email, email_data)
            
            logger.debug(f"Created email: {subject[:50]}...")
            return email
            
        except Exception as e:
            logger.error(f"Error creating email: {e}")
            raise
    
    def _update_email(self, email: Email, email_data: Dict, folder: Folder):
        """Update an existing email with new data."""
        try:
            # Update fields that might change
            email.is_read = email_data.get('readFlag', False)
            email.is_starred = email_data.get('flagged', False)
            email.is_important = email_data.get('important', False)
            
            # Update folder if moved
            if email.folder != folder:
                email.folder = folder
            
            email.save(update_fields=['is_read', 'is_starred', 'is_important', 'folder', 'updated_at'])
            logger.debug(f"Updated email: {email.subject[:50]}...")
            
        except Exception as e:
            logger.error(f"Error updating email {email.zoho_message_id}: {e}")
            raise
    
    def _process_attachments(self, email: Email, email_data: Dict):
        """Process email attachments."""
        try:
            attachments_data = email_data.get('attachments', [])
            if not attachments_data:
                return
            
            for attachment_data in attachments_data:
                attachment_id = attachment_data.get('attachmentId')
                if not attachment_id:
                    continue
                
                # Check if attachment already exists
                if EmailAttachment.objects.filter(
                    email=email, 
                    zoho_attachment_id=attachment_id
                ).exists():
                    continue
                
                # Create attachment record
                EmailAttachment.objects.create(
                    email=email,
                    filename=attachment_data.get('attachmentName', 'unknown'),
                    content_type=attachment_data.get('contentType', 'application/octet-stream'),
                    file_size=attachment_data.get('size', 0),
                    zoho_attachment_id=attachment_id
                )
                
        except Exception as e:
            logger.error(f"Error processing attachments for email {email.zoho_message_id}: {e}")
    
    def _handle_email_threading(self, email: Email, email_data: Dict):
        """Handle email threading logic."""
        try:
            thread_id = email_data.get('threadId')
            if not thread_id:
                return
            
            # Find or create thread
            thread, created = EmailThread.objects.get_or_create(
                account=self.account,
                thread_id=thread_id,
                defaults={
                    'subject': email.subject,
                    'first_message_at': email.sent_at,
                    'last_message_at': email.sent_at
                }
            )
            
            # Associate email with thread
            email.thread = thread
            email.save(update_fields=['thread'])
            
            # Update thread statistics
            if not created:
                thread.update_thread_stats()
                
        except Exception as e:
            logger.error(f"Error handling threading for email {email.zoho_message_id}: {e}")
    
    def _map_folder_type(self, folder_name: str) -> str:
        """Map Zoho folder name to our folder type."""
        folder_mapping = {
            'inbox': 'inbox',
            'sent': 'sent',
            'drafts': 'drafts',
            'trash': 'trash',
            'spam': 'spam',
            'junk': 'spam',
            'deleted': 'trash'
        }
        
        return folder_mapping.get(folder_name.lower(), 'custom')
    
    def _parse_email_date(self, date_str: Optional[str]) -> datetime:
        """Parse email date string to datetime object."""
        if not date_str:
            return timezone.now()
        
        try:
            # Handle timestamp in milliseconds
            if str(date_str).isdigit():
                from datetime import timezone as dt_timezone
                timestamp = int(date_str) / 1000
                return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
            
            # Handle ISO format
            return datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse date: {date_str} - {e}")
            return timezone.now()
    
    def _extract_email_address(self, address_str: str) -> str:
        """Extract email address from address string."""
        if not address_str:
            return ""
        
        # Handle format: "Name <email@domain.com>"
        if '<' in address_str and '>' in address_str:
            start = address_str.find('<')
            end = address_str.find('>')
            if start != -1 and end != -1:
                return address_str[start+1:end].strip()
        
        # Return as-is if already clean email
        return address_str.strip()
    
    def _extract_display_name(self, address_str: str) -> str:
        """Extract display name from address string."""
        if not address_str:
            return ""
        
        # Handle format: "Name <email@domain.com>"
        if '<' in address_str:
            return address_str.split('<')[0].strip(' "\'')
        
        return ""
    
    def _parse_email_addresses(self, addresses_str: str) -> List[str]:
        """Parse comma-separated email addresses."""
        if not addresses_str:
            return []
        
        addresses = []
        for addr in addresses_str.split(','):
            email = self._extract_email_address(addr.strip())
            if email:
                addresses.append(email)
        
        return addresses
    
    def create_sync_log(self, sync_type: str = 'manual') -> SyncLog:
        """Create a new sync log entry."""
        return SyncLog.objects.create(
            account=self.account,
            sync_type=sync_type,
            status='running'
        )
    
    def update_sync_log(self, sync_log: SyncLog, stats: Dict[str, int], success: bool = True):
        """Update sync log with results."""
        sync_log.emails_fetched = stats.get('fetched', 0)
        sync_log.emails_created = stats.get('created', 0)
        sync_log.emails_updated = stats.get('updated', 0)
        sync_log.error_count = stats.get('errors', 0)
        sync_log.mark_completed(success=success and stats.get('errors', 0) == 0)
        
        if stats.get('errors', 0) > 0:
            sync_log.add_error(f"{stats['errors']} errors occurred during sync")
    
    def full_sync(self, limit: int = MAX_EMAILS_PER_SYNC) -> Dict[str, int]:
        """
        Perform a full synchronization of folders and emails.
        
        Args:
            limit: Maximum emails per folder
            
        Returns:
            Sync statistics
        """
        sync_log = self.create_sync_log('full')
        
        try:
            # Step 1: Sync folders
            folders_synced = self.sync_folders()
            sync_log.folders_synced = folders_synced
            
            # Step 2: Sync emails
            stats = self.sync_emails(limit=limit)
            
            # Update sync log
            self.update_sync_log(sync_log, stats, success=True)
            
            logger.info(f"Full sync completed for {self.account.email_address}")
            return stats
            
        except Exception as e:
            sync_log.add_error(f"Full sync failed: {e}")
            sync_log.mark_completed(success=False)
            logger.error(f"Full sync failed for {self.account.email_address}: {e}")
            raise EmailSyncError(f"Full sync failed: {e}")