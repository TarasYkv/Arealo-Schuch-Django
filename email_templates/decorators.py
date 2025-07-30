"""
Decorators for easy integration with the email trigger system
"""

from functools import wraps
from typing import Dict, Any, Callable
import logging
from .trigger_manager import trigger_manager

logger = logging.getLogger(__name__)


def trigger_email(trigger_key: str, extract_context: Callable = None, 
                 extract_recipient: Callable = None):
    """
    Decorator to automatically trigger emails based on function execution
    
    Args:
        trigger_key: The email trigger to fire
        extract_context: Function to extract context data from function args/kwargs
        extract_recipient: Function to extract recipient info from function args/kwargs
    
    Usage:
    @trigger_email('user_registration', 
                   extract_context=lambda user, **kw: {'user_name': user.username, 'email': user.email},
                   extract_recipient=lambda user, **kw: (user.email, user.get_full_name()))
    def create_user(user):
        # Function logic here
        pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the original function
            result = func(*args, **kwargs)
            
            try:
                # Extract context data if extractor provided
                context_data = {}
                if extract_context:
                    context_data = extract_context(*args, **kwargs) or {}
                
                # Extract recipient info if extractor provided
                recipient_email = None
                recipient_name = None
                if extract_recipient:
                    recipient_info = extract_recipient(*args, **kwargs)
                    if isinstance(recipient_info, tuple):
                        recipient_email, recipient_name = recipient_info
                    else:
                        recipient_email = recipient_info
                
                # Fire the trigger if we have recipient info
                if recipient_email:
                    trigger_manager.fire_trigger(
                        trigger_key=trigger_key,
                        context_data=context_data,
                        recipient_email=recipient_email,
                        recipient_name=recipient_name
                    )
                    logger.info(f"Triggered email '{trigger_key}' for {recipient_email}")
                else:
                    logger.warning(f"Could not extract recipient for trigger '{trigger_key}'")
                    
            except Exception as e:
                logger.error(f"Error triggering email '{trigger_key}': {str(e)}")
            
            return result
        return wrapper
    return decorator


def signal_email_trigger(trigger_key: str, sender_field: str = None, 
                        created_only: bool = False):
    """
    Decorator for Django signal handlers to automatically trigger emails
    
    Args:
        trigger_key: The email trigger to fire
        sender_field: Field name to extract sender info from instance
        created_only: Only trigger for created instances (for post_save signals)
    
    Usage:
    @receiver(post_save, sender=User)
    @signal_email_trigger('user_registration', created_only=True)
    def handle_user_created(sender, instance, created, **kwargs):
        return {
            'user_name': instance.get_full_name(),
            'username': instance.username,
            'email': instance.email,
            'registration_date': instance.date_joined.strftime('%d.%m.%Y')
        }, instance.email, instance.get_full_name()
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(sender, instance, created=None, **kwargs):
            # Check if we should process this signal
            if created_only and not created:
                return
            
            try:
                # Call the original handler to get context data and recipient info
                handler_result = func(sender, instance, created, **kwargs)
                
                if handler_result:
                    if isinstance(handler_result, tuple) and len(handler_result) == 3:
                        context_data, recipient_email, recipient_name = handler_result
                    elif isinstance(handler_result, tuple) and len(handler_result) == 2:
                        context_data, recipient_email = handler_result
                        recipient_name = None
                    elif isinstance(handler_result, dict):
                        context_data = handler_result
                        # Try to extract recipient from instance
                        recipient_email = getattr(instance, 'email', None)
                        recipient_name = getattr(instance, 'get_full_name', lambda: None)()
                    else:
                        logger.warning(f"Invalid return format from signal handler for trigger '{trigger_key}'")
                        return
                    
                    # Fire the trigger
                    if recipient_email:
                        trigger_manager.fire_trigger(
                            trigger_key=trigger_key,
                            context_data=context_data,
                            recipient_email=recipient_email,
                            recipient_name=recipient_name
                        )
                        logger.info(f"Signal triggered email '{trigger_key}' for {recipient_email}")
                    else:
                        logger.warning(f"Could not extract recipient email for trigger '{trigger_key}'")
                        
            except Exception as e:
                logger.error(f"Error in signal email trigger '{trigger_key}': {str(e)}")
        
        return wrapper
    return decorator


def batch_email_trigger(trigger_key: str, extract_recipients: Callable):
    """
    Decorator for functions that need to send emails to multiple recipients
    
    Args:
        trigger_key: The email trigger to fire
        extract_recipients: Function that returns list of (context, email, name) tuples
    
    Usage:
    @batch_email_trigger('maintenance_notification',
                        extract_recipients=lambda: [(
                            {'user_name': u.name, 'maintenance_date': date},
                            u.email, u.name
                        ) for u in User.objects.filter(is_active=True)])
    def send_maintenance_notification():
        pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the original function
            result = func(*args, **kwargs)
            
            try:
                # Extract recipients
                recipients = extract_recipients(*args, **kwargs)
                
                if not recipients:
                    logger.info(f"No recipients found for batch trigger '{trigger_key}'")
                    return result
                
                success_count = 0
                for recipient_data in recipients:
                    try:
                        if isinstance(recipient_data, tuple) and len(recipient_data) == 3:
                            context_data, recipient_email, recipient_name = recipient_data
                        elif isinstance(recipient_data, tuple) and len(recipient_data) == 2:
                            context_data, recipient_email = recipient_data
                            recipient_name = None
                        else:
                            logger.warning(f"Invalid recipient data format in batch trigger '{trigger_key}'")
                            continue
                        
                        # Fire trigger for each recipient
                        results = trigger_manager.fire_trigger(
                            trigger_key=trigger_key,
                            context_data=context_data,
                            recipient_email=recipient_email,
                            recipient_name=recipient_name
                        )
                        
                        if results and any(r['success'] for r in results):
                            success_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error sending to {recipient_data}: {str(e)}")
                        continue
                
                logger.info(f"Batch trigger '{trigger_key}' sent to {success_count}/{len(recipients)} recipients")
                
            except Exception as e:
                logger.error(f"Error in batch email trigger '{trigger_key}': {str(e)}")
            
            return result
        return wrapper
    return decorator


def conditional_email_trigger(trigger_key: str, condition: Callable, 
                            extract_context: Callable, extract_recipient: Callable):
    """
    Decorator that only triggers emails when a condition is met
    
    Args:
        trigger_key: The email trigger to fire
        condition: Function that returns True if email should be sent
        extract_context: Function to extract context data
        extract_recipient: Function to extract recipient info
    
    Usage:
    @conditional_email_trigger('payment_failed',
                              condition=lambda payment: payment.attempt_count >= 3,
                              extract_context=lambda payment: {'amount': payment.amount},
                              extract_recipient=lambda payment: payment.user.email)
    def process_payment_failure(payment):
        pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the original function
            result = func(*args, **kwargs)
            
            try:
                # Check condition
                if not condition(*args, **kwargs):
                    logger.debug(f"Condition not met for trigger '{trigger_key}', skipping email")
                    return result
                
                # Extract context and recipient
                context_data = extract_context(*args, **kwargs) or {}
                recipient_info = extract_recipient(*args, **kwargs)
                
                recipient_email = None
                recipient_name = None
                if isinstance(recipient_info, tuple):
                    recipient_email, recipient_name = recipient_info
                else:
                    recipient_email = recipient_info
                
                # Fire trigger
                if recipient_email:
                    trigger_manager.fire_trigger(
                        trigger_key=trigger_key,
                        context_data=context_data,
                        recipient_email=recipient_email,
                        recipient_name=recipient_name
                    )
                    logger.info(f"Conditional trigger '{trigger_key}' fired for {recipient_email}")
                    
            except Exception as e:
                logger.error(f"Error in conditional email trigger '{trigger_key}': {str(e)}")
            
            return result
        return wrapper
    return decorator