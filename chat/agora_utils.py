"""
Agora Token Generation Utilities
"""
import time
import hmac
import hashlib
import base64
import struct
from django.conf import settings


def generate_agora_token(channel_name, uid, role=1, expire_time=3600):
    """
    Generate Agora Token for Video/Audio calls
    
    Args:
        channel_name: Channel name for the call
        uid: User ID (can be 0 for auto-assignment)
        role: User role (1 = Publisher, 2 = Subscriber)
        expire_time: Token expiration time in seconds (default 1 hour)
    
    Returns:
        dict: {success: bool, token: str, uid: int, error: str}
    """
    try:
        app_id = settings.AGORA_APP_ID
        app_certificate = settings.AGORA_APP_CERTIFICATE
        
        if not app_id or not app_certificate:
            return {
                'success': False,
                'error': 'Agora credentials not configured'
            }
        
        # Generate timestamp
        current_timestamp = int(time.time())
        expire_timestamp = current_timestamp + expire_time
        
        # If uid is 0, generate a random uid
        if uid == 0:
            uid = current_timestamp % 1000000
        
        # Build the token (simplified version)
        # For production, use official Agora token generator
        message = f"{app_id}{channel_name}{uid}{expire_timestamp}"
        signature = hmac.new(
            app_certificate.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Create a simple token format
        token_data = {
            'app_id': app_id,
            'channel': channel_name,
            'uid': uid,
            'expire': expire_timestamp,
            'signature': signature[:32]  # Truncate for simplicity
        }
        
        # Encode token (simplified - in production use official Agora format)
        token_string = base64.b64encode(str(token_data).encode()).decode()
        
        return {
            'success': True,
            'token': token_string,
            'uid': uid,
            'expire_time': expire_timestamp
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def validate_agora_token(token, channel_name, uid):
    """
    Validate Agora token (simplified validation)
    
    Args:
        token: Token to validate
        channel_name: Channel name
        uid: User ID
    
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Decode token
        decoded = base64.b64decode(token.encode()).decode()
        # Simple validation - in production use proper validation
        return channel_name in decoded and str(uid) in decoded
    except:
        return False


# Alternative: Use official Agora token if available
try:
    from agora_token_builder import RtcTokenBuilder
    
    def generate_rtc_token(channel_name, uid, role=1, expire_time=3600):
        """
        Generate official Agora RTC Token using agora-token-builder
        """
        try:
            app_id = settings.AGORA_APP_ID
            app_certificate = settings.AGORA_APP_CERTIFICATE
            
            current_timestamp = int(time.time())
            privilege_expired_ts = current_timestamp + expire_time
            
            if uid == 0:
                uid = current_timestamp % 1000000
            
            token = RtcTokenBuilder.buildTokenWithUid(
                app_id, app_certificate, channel_name, uid, role, privilege_expired_ts
            )
            
            return {
                'success': True,
                'token': token,
                'uid': uid,
                'expire_time': privilege_expired_ts
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    # Use official token generator if available
    generate_agora_token = generate_rtc_token
    
except ImportError:
    # Fall back to simplified token generation
    print("Agora token builder not installed. Using simplified token generation.")
    print("For production, install: pip install agora-token-builder")