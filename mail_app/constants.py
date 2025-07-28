"""
Constants for Mail App
"""

# OAuth and API Settings
ZOHO_BASE_URL = "https://accounts.zoho.com"
ZOHO_MAIL_API_BASE = "https://mail.zoho.com/api"
OAUTH_SCOPES = "ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ,ZohoMail.messages.CREATE"

# Pagination and Limits
DEFAULT_EMAIL_LIMIT = 50
MAX_EMAILS_PER_SYNC = 1000
MAX_EMAILS_PER_PAGE = 100
EMAIL_CONTENT_MAX_LENGTH = 1000000

# Date Ranges
DEFAULT_SYNC_DAYS = 90
MAX_SYNC_DAYS = 365

# Folder Types
FOLDER_TYPES = [
    ('inbox', 'Inbox'),
    ('sent', 'Sent'),
    ('drafts', 'Drafts'),
    ('trash', 'Trash'),
    ('spam', 'Spam'),
    ('custom', 'Custom'),
]

# Folder Icons
FOLDER_ICONS = {
    'inbox': '📥',
    'sent': '📤',
    'drafts': '📝',
    'trash': '🗑️',
    'spam': '🚫',
    'custom': '📁'
}

# Email Status
EMAIL_STATUS_CHOICES = [
    ('read', 'Read'),
    ('unread', 'Unread'),
    ('replied', 'Replied'),
    ('forwarded', 'Forwarded'),
    ('flagged', 'Flagged'),
]

# Sync Status
SYNC_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('running', 'Running'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
]

# Sync Types
SYNC_TYPE_CHOICES = [
    ('manual', 'Manual'),
    ('scheduled', 'Scheduled'),
    ('background', 'Background'),
]

# Ticket Status
TICKET_STATUS_CHOICES = [
    ('open', 'Open'),
    ('pending', 'Pending'),
    ('resolved', 'Resolved'),
    ('closed', 'Closed'),
]

# Ticket Priority
TICKET_PRIORITY_CHOICES = [
    ('low', 'Low'),
    ('normal', 'Normal'),
    ('high', 'High'),
    ('urgent', 'Urgent'),
]

# Email Grouping Modes
EMAIL_GROUPING_MODES = [
    ('subject', 'By Subject'),
    ('thread', 'By Thread'),
    ('sender', 'By Sender'),
    ('none', 'No Grouping'),
]

# Cache Keys
CACHE_KEYS = {
    'account_info': 'mail_account_info_{account_id}',
    'folder_list': 'mail_folders_{account_id}',
    'email_list': 'mail_emails_{account_id}_{folder_id}',
    'email_content': 'mail_email_content_{email_id}',
    'sync_status': 'mail_sync_status_{account_id}',
}

# Cache Timeouts (in seconds)
CACHE_TIMEOUTS = {
    'account_info': 3600,  # 1 hour
    'folder_list': 1800,   # 30 minutes
    'email_list': 300,     # 5 minutes
    'email_content': 7200, # 2 hours
    'sync_status': 60,     # 1 minute
}

# Error Messages
ERROR_MESSAGES = {
    'no_permission': 'Sie haben keine Berechtigung für die Email-App.',
    'no_account': 'Bitte verbinden Sie zuerst einen Email-Account.',
    'account_not_found': 'Email-Account nicht gefunden.',
    'folder_not_found': 'Ordner nicht gefunden.',
    'email_not_found': 'Email nicht gefunden.',
    'sync_failed': 'Email-Synchronisation fehlgeschlagen.',
    'auth_required': 'Erneute Authentifizierung erforderlich.',
    'rate_limit': 'Zu viele Anfragen. Bitte warten Sie einen Moment.',
}

# Success Messages
SUCCESS_MESSAGES = {
    'account_connected': 'Email-Account erfolgreich verbunden.',
    'account_updated': 'Email-Account erfolgreich aktualisiert.',
    'sync_started': 'Email-Synchronisation gestartet.',
    'sync_completed': 'Email-Synchronisation abgeschlossen.',
    'email_sent': 'Email erfolgreich gesendet.',
    'email_deleted': 'Email erfolgreich gelöscht.',
}

# API Rate Limits
RATE_LIMITS = {
    'api_requests_per_minute': 100,
    'sync_requests_per_hour': 10,
    'auth_requests_per_hour': 5,
}

# File Upload Settings
ATTACHMENT_MAX_SIZE = 25 * 1024 * 1024  # 25MB
ALLOWED_ATTACHMENT_TYPES = [
    'image/jpeg', 'image/png', 'image/gif',
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'text/csv'
]

# Regex Patterns
EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
THREAD_ID_PATTERN = r'^[a-zA-Z0-9_-]+$'
SUBJECT_CLEAN_PATTERN = r'^(RE:|FWD?:|AW:)\s*'

# HTML/CSS Classes
CSS_CLASSES = {
    'email_read': 'email-read',
    'email_unread': 'email-unread',
    'email_replied': 'email-replied',
    'email_forwarded': 'email-forwarded',
    'folder_active': 'folder-active',
    'folder_unread': 'folder-unread',
    'sync_running': 'sync-running',
    'sync_error': 'sync-error',
}

# Default Settings
DEFAULT_SETTINGS = {
    'auto_sync_interval': 300,  # 5 minutes
    'emails_per_page': 50,
    'show_html_emails': True,
    'auto_mark_read': True,
    'show_images': False,
    'compact_view': False,
}

# URL Patterns
URL_PATTERNS = {
    'oauth_callback': '/mail/oauth/callback/',
    'api_sync': '/mail/api/accounts/{account_id}/sync/',
    'api_emails': '/mail/api/accounts/{account_id}/folders/{folder_id}/emails/',
    'api_email_detail': '/mail/api/emails/{email_id}/',
}