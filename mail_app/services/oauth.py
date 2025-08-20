"""
Zoho OAuth2 Authentication Service
"""
import logging
import requests
from datetime import timedelta
from typing import Dict, Optional
from django.conf import settings
from django.utils import timezone
from requests_oauthlib import OAuth2Session
from .exceptions import TokenRefreshError, ReAuthorizationRequiredError, InvalidConfigurationError
from ..constants import ZOHO_BASE_URL, OAUTH_SCOPES

logger = logging.getLogger(__name__)


class ZohoOAuthService:
    """
    Service for handling Zoho OAuth2 authentication.
    """
    
    def __init__(self, user=None):
        self.user = user
        self.scope = OAUTH_SCOPES
        
        # Try to get user-specific settings first, then fall back to .env
        if user:
            try:
                from accounts.models import ZohoAPISettings
                self.zoho_settings = ZohoAPISettings.objects.get(user=user, is_configured=True)
                self.client_id = self.zoho_settings.client_id
                self.client_secret = self.zoho_settings.client_secret
                self.redirect_uri = self.zoho_settings.redirect_uri
                self.auth_url = self.zoho_settings.auth_url
                self.token_url = self.zoho_settings.token_url
                # Set config for compatibility with existing code
                self.config = {
                    'CLIENT_ID': self.client_id,
                    'CLIENT_SECRET': self.client_secret,
                    'REDIRECT_URI': self.redirect_uri,
                    'AUTH_URL': self.auth_url,
                    'TOKEN_URL': self.token_url,
                    'REGION': self.zoho_settings.region
                }
                logger.info(f"Using user-specific Zoho settings for {user.username}")
                return
            except Exception as e:
                logger.info(f"No user-specific Zoho settings found for {user.username}, falling back to .env: {e}")
        
        # Fallback to .env configuration
        try:
            self.config = settings.ZOHO_MAIL_CONFIG
            self.client_id = self.config['CLIENT_ID']
            self.client_secret = self.config['CLIENT_SECRET']
            self.redirect_uri = self.config['REDIRECT_URI']
            self.auth_url = self.config['AUTH_URL']
            self.token_url = self.config['TOKEN_URL']
            self.zoho_settings = None
            logger.info("Using .env Zoho configuration")
        except (AttributeError, KeyError) as e:
            logger.error(f"No Zoho configuration found in .env or user settings: {e}")
            raise InvalidConfigurationError("Zoho Mail configuration not found")
    
    def get_authorization_url(self, state: Optional[str] = None, force_refresh: bool = True) -> str:
        """
        Generate the OAuth2 authorization URL for Zoho with enhanced parameters for longer code validity.
        
        Args:
            state: Optional state parameter for CSRF protection
            force_refresh: Force refresh consent screen for longer code validity
            
        Returns:
            Authorization URL string
        """
        try:
            oauth = OAuth2Session(
                self.client_id,
                scope=self.scope,
                redirect_uri=self.redirect_uri,
                state=state
            )
            
            # Enhanced parameters for longer authorization code validity
            auth_params = {
                'access_type': 'offline',
                'approval_prompt': 'force',  # Force approval screen
                'prompt': 'consent'  # Always show consent screen
            }
            
            # Add additional parameters to potentially extend code lifetime
            if force_refresh:
                auth_params['response_mode'] = 'query'
                auth_params['include_granted_scopes'] = 'true'
            
            authorization_url, state = oauth.authorization_url(
                self.auth_url,
                **auth_params
            )
            
            logger.info(f"Generated enhanced authorization URL for client_id: {self.client_id[:10]}... with extended validity parameters")
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error generating authorization URL: {e}")
            raise InvalidConfigurationError(f"Failed to generate authorization URL: {e}")
    
    def exchange_code_for_tokens(self, authorization_code: str) -> Dict:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            authorization_code: The authorization code from Zoho
            
        Returns:
            Dictionary containing tokens and expiration info
        """
        try:
            logger.info(f"Exchanging authorization code for tokens (Region: {self.config.get('REGION', 'Unknown')})")
            logger.debug(f"Token URL: {self.token_url}")
            logger.debug(f"Client ID: {self.client_id[:10]}...")
            logger.debug(f"Redirect URI: {self.redirect_uri}")
            
            # Manual token exchange for better error handling
            data = {
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'code': authorization_code
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            response = requests.post(self.token_url, data=data, headers=headers, timeout=30)
            
            logger.info(f"Token exchange response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed with status {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                logger.error(f"Response content: {response.text[:1000]}")
                
                # Check if it's a JSON error response
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = f"{error_data.get('error')}: {error_data.get('error_description', '')}"
                        logger.error(f"Zoho OAuth error: {error_msg}")
                        
                        # Check for specific authorization code errors
                        if 'invalid_grant' in error_msg.lower() or 'authorization code' in error_msg.lower():
                            logger.error("Authorization code expired or invalid - OAuth flow must be completed quickly!")
                            raise TokenRefreshError("Token exchange failed: Authorization code expired or invalid. Please try the OAuth flow again and complete it within 1-2 minutes.")
                        else:
                            raise TokenRefreshError(f"Token exchange failed: {error_msg}")
                except ValueError:
                    # Not JSON, probably HTML error page
                    if '<title>' in response.text and 'Zoho' in response.text:
                        logger.error("Received HTML error page instead of JSON - likely expired authorization code")
                        if 'expired' in response.text.lower() or 'invalid' in response.text.lower():
                            logger.error("Authorization code has expired - OAuth must be completed faster!")
                            raise TokenRefreshError("Token exchange failed: Authorization code expired. The OAuth process must be completed within 1-2 minutes. Please try again immediately.")
                        else:
                            raise TokenRefreshError("Token exchange failed: Invalid request parameters or expired authorization code")
                    else:
                        raise TokenRefreshError(f"Token exchange failed: {response.status_code} - {response.text[:200]}")
            
            try:
                token_data = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response: {response.text[:500]}")
                raise TokenRefreshError("Token exchange failed: Invalid response format")
            logger.info(f"Token exchange successful, received keys: {list(token_data.keys())}")
            
            if 'error' in token_data:
                error_msg = f"{token_data.get('error')} - {token_data.get('error_description', '')}"
                logger.error(f"OAuth error in response: {token_data}")
                raise TokenRefreshError(f"OAuth error: {error_msg}")
            
            # Validate required fields
            if not token_data.get('access_token'):
                raise TokenRefreshError("No access token in response")
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in', 3600),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token exchange: {e}")
            raise TokenRefreshError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise TokenRefreshError(f"Token exchange failed: {e}")
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh the access token using refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dictionary containing new tokens
        """
        try:
            logger.info(f"Refreshing access token (Region: {self.config.get('REGION', 'Unknown')})")
            
            data = {
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            response = requests.post(self.token_url, data=data, headers=headers, timeout=30)
            
            logger.info(f"Token refresh response status: {response.status_code}")
            
            if response.status_code == 400:
                logger.error("Token refresh failed - Bad Request (400)")
                error_content = response.text[:500]
                if "invalid_grant" in error_content or "expired" in error_content.lower():
                    logger.error("Refresh token is invalid or expired - re-authorization required")
                    raise ReAuthorizationRequiredError("Refresh token invalid or expired")
                else:
                    logger.error(f"Bad request content: {error_content}")
                    raise TokenRefreshError(f"Token refresh bad request: {error_content}")
                    
            elif response.status_code == 401:
                logger.error("Token refresh failed - Unauthorized (401) - re-authorization required")
                raise ReAuthorizationRequiredError("Unauthorized - re-authorization required")
                
            elif response.status_code != 200:
                logger.error(f"Token refresh failed with status {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                raise TokenRefreshError(f"Token refresh failed: {response.status_code}")
            
            try:
                token_data = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from token refresh: {response.text[:200]}")
                raise TokenRefreshError(f"Invalid JSON response: {e}")
            
            if 'error' in token_data:
                error_type = token_data.get('error', '')
                error_desc = token_data.get('error_description', '')
                logger.error(f"OAuth error in refresh response: {error_type} - {error_desc}")
                
                if error_type in ['invalid_grant', 'invalid_token']:
                    raise ReAuthorizationRequiredError(f"OAuth error - re-authorization required: {error_type}")
                else:
                    raise TokenRefreshError(f"OAuth error: {error_type} - {error_desc}")
            
            # Validate response
            if not token_data.get('access_token'):
                raise TokenRefreshError("No access token in refresh response")
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token', refresh_token),  # Use old if not provided
                'expires_in': token_data.get('expires_in', 3600),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token refresh: {e}")
            raise TokenRefreshError(f"Network error: {e}")
        except (ReAuthorizationRequiredError, TokenRefreshError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise TokenRefreshError(f"Token refresh failed: {e}")
    
    def validate_token_response(self, token_data: Dict) -> bool:
        """
        Validate that token response contains required fields.
        
        Args:
            token_data: Token response dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['access_token']
        optional_fields = ['refresh_token', 'expires_in', 'token_type']
        
        # Check required fields
        for field in required_fields:
            if not token_data.get(field):
                logger.error(f"Missing required field in token response: {field}")
                return False
        
        # Log available fields
        available_fields = [field for field in required_fields + optional_fields if token_data.get(field)]
        logger.info(f"Token response contains fields: {available_fields}")
        
        return True