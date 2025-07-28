"""
Mail App Logging Configuration
"""
import os
import logging
from datetime import datetime
from django.conf import settings


class MailAppFormatter(logging.Formatter):
    """Custom formatter for mail app logs"""
    
    def __init__(self):
        super().__init__()
        
    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add mail app specific context
        if hasattr(record, 'context'):
            context = record.context
            record.user_info = f"User: {context.get('user', 'Unknown')}"
            record.request_info = f"{context.get('method', 'Unknown')} {context.get('path', 'Unknown')}"
            record.ip_info = f"IP: {context.get('ip', 'Unknown')}"
        else:
            record.user_info = ""
            record.request_info = ""
            record.ip_info = ""
        
        # Format the message
        if record.levelname == 'ERROR' or record.levelname == 'CRITICAL':
            template = (
                "%(timestamp)s [%(levelname)s] Mail App Error\n"
                "Message: %(message)s\n"
                "%(user_info)s\n"
                "%(request_info)s\n"
                "%(ip_info)s\n"
                "Module: %(name)s\n"
                "---"
            )
        else:
            template = "%(timestamp)s [%(levelname)s] %(name)s: %(message)s %(user_info)s %(request_info)s"
        
        formatter = logging.Formatter(template)
        return formatter.format(record)


class MailAppFilter(logging.Filter):
    """Filter for mail app specific logs"""
    
    def filter(self, record):
        # Only process logs from mail app modules
        return record.name.startswith('mail_app') or 'mail' in record.name.lower()


def setup_mail_app_logging():
    """Setup logging configuration for mail app"""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Mail app logger
    mail_logger = logging.getLogger('mail_app')
    mail_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in mail_logger.handlers[:]:
        mail_logger.removeHandler(handler)
    
    # File handler for general mail app logs
    mail_file_handler = logging.FileHandler(
        os.path.join(log_dir, 'mail_app.log'),
        encoding='utf-8'
    )
    mail_file_handler.setLevel(logging.INFO)
    mail_file_handler.setFormatter(MailAppFormatter())
    mail_file_handler.addFilter(MailAppFilter())
    
    # File handler for errors only
    error_file_handler = logging.FileHandler(
        os.path.join(log_dir, 'mail_app_errors.log'),
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(MailAppFormatter())
    error_file_handler.addFilter(MailAppFilter())
    
    # Console handler for development
    if settings.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(MailAppFilter())
        mail_logger.addHandler(console_handler)
    
    # Add handlers to logger
    mail_logger.addHandler(mail_file_handler)
    mail_logger.addHandler(error_file_handler)
    
    # Don't propagate to root logger to avoid duplication
    mail_logger.propagate = False
    
    # Setup specific loggers for different components
    setup_component_loggers(log_dir)
    
    return mail_logger


def setup_component_loggers(log_dir):
    """Setup loggers for specific mail app components"""
    
    components = {
        'mail_app.oauth': 'oauth.log',
        'mail_app.sync': 'sync.log',
        'mail_app.api': 'api.log',
        'mail_app.views': 'views.log',
        'mail_app.middleware': 'middleware.log'
    }
    
    for component_name, log_file in components.items():
        logger = logging.getLogger(component_name)
        logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler(
            os.path.join(log_dir, log_file),
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(MailAppFormatter())
        
        logger.addHandler(file_handler)
        logger.propagate = False


class PerformanceLogger:
    """Logger for performance monitoring"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.logger = logging.getLogger('mail_app.performance')
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.info(f"Starting operation: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        
        if exc_type:
            self.logger.error(
                f"Operation failed: {self.operation_name} (Duration: {duration:.2f}s)",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        else:
            log_level = logging.WARNING if duration > 5.0 else logging.INFO
            self.logger.log(
                log_level,
                f"Operation completed: {self.operation_name} (Duration: {duration:.2f}s)"
            )


class AuditLogger:
    """Logger for audit trail of important operations"""
    
    def __init__(self):
        self.logger = logging.getLogger('mail_app.audit')
        
        # Setup audit log file
        if not self.logger.handlers:
            log_dir = os.path.join(settings.BASE_DIR, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            audit_handler = logging.FileHandler(
                os.path.join(log_dir, 'mail_app_audit.log'),
                encoding='utf-8'
            )
            audit_handler.setLevel(logging.INFO)
            
            audit_formatter = logging.Formatter(
                '%(asctime)s [AUDIT] %(message)s'
            )
            audit_handler.setFormatter(audit_formatter)
            
            self.logger.addHandler(audit_handler)
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False
    
    def log_email_access(self, user, email_id, action='view'):
        """Log email access"""
        self.logger.info(f"User {user} {action} email {email_id}")
    
    def log_email_send(self, user, recipient, subject):
        """Log email sending"""
        self.logger.info(f"User {user} sent email to {recipient}: {subject[:50]}")
    
    def log_oauth_action(self, user, action, account=None):
        """Log OAuth related actions"""
        account_info = f" for account {account}" if account else ""
        self.logger.info(f"User {user} {action}{account_info}")
    
    def log_admin_action(self, user, action, target=None):
        """Log administrative actions"""
        target_info = f" on {target}" if target else ""
        self.logger.info(f"Admin {user} {action}{target_info}")


# Initialize logging when module is imported
if hasattr(settings, 'BASE_DIR'):
    try:
        setup_mail_app_logging()
    except Exception as e:
        # Fallback to basic logging if setup fails
        logging.getLogger('mail_app').error(f"Failed to setup mail app logging: {e}")


# Convenience functions
def get_mail_logger(name: str = 'mail_app'):
    """Get a mail app logger"""
    return logging.getLogger(name)

def get_performance_logger(operation_name: str):
    """Get a performance logger context manager"""
    return PerformanceLogger(operation_name)

def get_audit_logger():
    """Get the audit logger"""
    return AuditLogger()