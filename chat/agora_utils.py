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
    # First try the newer official SDK
    from agora_python_server_sdk import rtc_token_builder
    from agora_python_server_sdk.rtc_token_builder import Role_Publisher, Role_Subscriber
    
    def generate_rtc_token_v2(channel_name, uid, role=1, expire_time=3600):
        """
        Generate official Agora RTC Token using agora-python-server-sdk (newer version)
        """
        try:
            app_id = settings.AGORA_APP_ID
            app_certificate = settings.AGORA_APP_CERTIFICATE
            
            print(f"DEBUG: Generating token with newer SDK for channel='{channel_name}', uid={uid}, role={role}")
            
            current_timestamp = int(time.time())
            privilege_expired_ts = current_timestamp + expire_time
            
            # For newer SDK, always use uid=0 for auto-assignment
            final_uid = 0
                
            print(f"DEBUG: Using newer SDK with uid={final_uid}, expire_ts={privilege_expired_ts}")
            
            # Use the newer SDK
            token = rtc_token_builder.build_token_with_uid(
                app_id, app_certificate, channel_name, final_uid, Role_Publisher, privilege_expired_ts
            )
            
            print(f"DEBUG: New SDK generated token length={len(token)}, starts with={token[:20]}...")
            
            # Validate generated token
            if len(token) == 0:
                raise Exception("Generated token is empty")
            
            return {
                'success': True,
                'token': token,
                'uid': final_uid,
                'expire_time': privilege_expired_ts
            }
            
        except Exception as e:
            print(f"ERROR: New SDK token generation failed: {e}")
            # Fall back to old method
            raise e
    
    # Use the newer SDK as primary
    generate_agora_token = generate_rtc_token_v2
    print("Using newer Agora Python Server SDK")
    
except ImportError:
    print("Newer SDK not available, trying agora-token-builder...")
    
    try:
        from agora_token_builder import RtcTokenBuilder
        
        def generate_rtc_token(channel_name, uid, role=1, expire_time=3600):
            """
            Generate official Agora RTC Token using agora-token-builder (fallback)
            """
            try:
                app_id = settings.AGORA_APP_ID
                app_certificate = settings.AGORA_APP_CERTIFICATE
                
                print(f"DEBUG: Fallback - Generating token for channel='{channel_name}', uid={uid}")
                
                current_timestamp = int(time.time())
                privilege_expired_ts = current_timestamp + expire_time
                
                # Always use uid=0 for auto-assignment in fallback
                final_uid = 0
                
                token = RtcTokenBuilder.buildTokenWithUid(
                    app_id, app_certificate, channel_name, final_uid, role, privilege_expired_ts
                )
                
                print(f"DEBUG: Fallback token generated, length={len(token)}")
                
                return {
                    'success': True,
                    'token': token,
                    'uid': final_uid,
                    'expire_time': privilege_expired_ts
                }
                
            except Exception as e:
                print(f"ERROR: Fallback token generation failed: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
        
        # Use the fallback token generator
        generate_agora_token = generate_rtc_token
        print("Using agora-token-builder (fallback)")
    
    except ImportError:
        # Fall back to simplified token generation
        print("agora-token-builder not available. Using simplified token generation.")
        print("For production, install: pip install agora-token-builder")

# Add a test function for manual token validation
def test_manual_token(channel_name, uid=0):
    """
    Test function to generate a basic Agora token manually
    This is for testing purposes only
    """
    try:
        app_id = settings.AGORA_APP_ID
        app_certificate = settings.AGORA_APP_CERTIFICATE
        
        print(f"DEBUG: Manual token test - APP_ID={app_id}")
        print(f"DEBUG: Manual token test - APP_CERT exists={bool(app_certificate)}")
        
        # Simple test without complex token generation for now
        return {
            'success': True,
            'token': f"test_token_{channel_name}_{uid}",
            'uid': uid,
            'expire_time': int(time.time() + 3600)
        }
        
    except Exception as e:
        print(f"DEBUG: Manual token test failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }