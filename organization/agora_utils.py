"""
Agora Video/Audio Call Utilities
"""
import time
import os
from agora_token_builder import RtcTokenBuilder
from django.conf import settings


def generate_agora_token(channel_name, uid, role=1, expiration_time_in_seconds=3600):
    """
    Generate Agora RTC Token for video/audio calls
    
    Args:
        channel_name (str): The channel name for the call
        uid (int): User ID (can be 0 for string-based user IDs)
        role (int): User role (1 = Publisher, 2 = Subscriber)
        expiration_time_in_seconds (int): Token expiration time
    
    Returns:
        str: Generated Agora token
    """
    app_id = settings.AGORA_APP_ID
    app_certificate = settings.AGORA_APP_CERTIFICATE
    
    if not app_id or not app_certificate or app_id == 'your_agora_app_id_here':
        raise ValueError("Agora credentials not configured. Please set AGORA_APP_ID and AGORA_APP_CERTIFICATE in environment variables.")
    
    # Calculate expiration timestamp
    current_timestamp = int(time.time())
    privilege_expired_ts = current_timestamp + expiration_time_in_seconds
    
    # Generate token
    token = RtcTokenBuilder.buildTokenWithUid(
        app_id, app_certificate, channel_name, uid, role, privilege_expired_ts
    )
    
    return token


def get_agora_config():
    """
    Get Agora configuration for frontend
    
    Returns:
        dict: Agora configuration
    """
    return {
        'app_id': settings.AGORA_APP_ID,
        'server_url': None,  # Optional: If using Agora Cloud Recording
    }


class CallRoles:
    """Constants for Agora call roles"""
    PUBLISHER = 1    # Can publish and subscribe (video/audio)
    SUBSCRIBER = 2   # Can only subscribe (listen/watch only)