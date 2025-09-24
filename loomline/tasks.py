"""
LoomLine Celery Tasks
"""

from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_scheduled_notifications():
    """
    Celery task to send scheduled LoomLine notifications via chat
    """
    try:
        call_command('send_scheduled_notifications')
        logger.info("Successfully ran send_scheduled_notifications command")
        return "Success"
    except Exception as e:
        logger.error(f"Error running send_scheduled_notifications: {e}")
        return f"Error: {e}"