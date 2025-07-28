"""
Zoho Mail API Integration Services
"""
import logging
import requests
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from requests_oauthlib import OAuth2Session
from .models import EmailAccount, Email, Folder, EmailAttachment, SyncLog, EmailThread

logger = logging.getLogger(__name__)


class TokenRefreshError(Exception):
    """Custom exception for token refresh failures."""
    pass


class ReAuthorizationRequiredError(Exception):
    """Custom exception when re-authorization is required."""
    pass


class ZohoOAuthService:
    """
    Service for handling Zoho OAuth2 authentication.
    """
    
    def __init__(self, user=None):
        self.user = user
        self.scope = 'ZohoMail.messages.ALL,ZohoMail.folders.ALL,ZohoMail.accounts.READ'
        
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
            except:
                logger.info(f"No user-specific Zoho settings found for {user.username}, falling back to .env")
        
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
        except (AttributeError, KeyError):
            logger.error("No Zoho configuration found in .env or user settings")
            raise ValueError("Zoho Mail configuration not found")
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate the OAuth2 authorization URL for Zoho.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL string
        """
        oauth = OAuth2Session(
            self.client_id,
            scope=self.scope,
            redirect_uri=self.redirect_uri,
            state=state
        )
        
        authorization_url, state = oauth.authorization_url(
            self.auth_url,
            access_type='offline',
            prompt='consent'
        )
        
        return authorization_url
    
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
            logger.info(f"Token URL: {self.token_url}")
            logger.info(f"Client ID: {self.client_id[:10]}...")
            logger.info(f"Redirect URI: {self.redirect_uri}")
            
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
            logger.info(f"Token exchange response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed with status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")
            
            token_data = response.json()
            logger.info(f"Token exchange successful, received keys: {list(token_data.keys())}")
            
            if 'error' in token_data:
                logger.error(f"OAuth error in response: {token_data}")
                raise Exception(f"OAuth error: {token_data.get('error')} - {token_data.get('error_description', '')}")
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in', 3600),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token exchange: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            raise
    
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
                logger.error(f"Token refresh failed - Bad Request (400)")
                error_content = response.text[:500]  # Limit error content
                if "invalid_grant" in error_content or "expired" in error_content.lower():
                    logger.error("Refresh token is invalid or expired - re-authorization required")
                    raise ReAuthorizationRequiredError("Refresh token invalid or expired")
                else:
                    logger.error(f"Bad request content: {error_content}")
                    raise Exception(f"Token refresh bad request: {error_content}")
                    
            elif response.status_code == 401:
                logger.error("Token refresh failed - Unauthorized (401) - re-authorization required")
                raise ReAuthorizationRequiredError("Unauthorized - re-authorization required")
                
            elif response.status_code != 200:
                logger.error(f"Token refresh failed with status {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                raise Exception(f"Token refresh failed: {response.status_code}")
            
            try:
                token_data = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from token refresh: {response.text[:200]}")
                raise Exception(f"Invalid JSON response: {str(e)}")
            
            if 'error' in token_data:
                error_type = token_data.get('error', '')
                error_desc = token_data.get('error_description', '')
                logger.error(f"OAuth error in refresh response: {error_type} - {error_desc}")
                
                if error_type in ['invalid_grant', 'invalid_token']:
                    raise ReAuthorizationRequiredError(f"OAuth error - re-authorization required: {error_type}")
                else:
                    raise Exception(f"OAuth error: {error_type} - {error_desc}")
            
            return {
                'access_token': token_data.get('access_token'),
                'expires_in': token_data.get('expires_in', 3600),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            }
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {str(e)}")
            raise


class ZohoMailAPIService:
    """
    Service for interacting with Zoho Mail API.
    """
    
    def __init__(self, email_account: EmailAccount):
        self.account = email_account
        self.oauth_service = ZohoOAuthService(user=email_account.user)
        
        # Try to get user-specific settings first, then fall back to .env
        try:
            from accounts.models import ZohoAPISettings
            zoho_settings = ZohoAPISettings.objects.get(user=email_account.user, is_configured=True)
            self.base_url = zoho_settings.base_url
            # Set config for compatibility with existing code
            self.config = {
                'BASE_URL': self.base_url,
                'REGION': zoho_settings.region
            }
            logger.info(f"Using user-specific Zoho base_url: {self.base_url}")
        except:
            # Fallback to .env configuration
            try:
                self.config = settings.ZOHO_MAIL_CONFIG
                self.base_url = self.config['BASE_URL']
                logger.info(f"Using .env Zoho base_url: {self.base_url}")
            except (AttributeError, KeyError):
                logger.error("No Zoho base URL configuration found")
                self.base_url = 'https://mail.zoho.eu/api/'  # Default fallback
                self.config = {'BASE_URL': self.base_url, 'REGION': 'EU'}
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with valid access token."""
        try:
            # Check if we have an access token
            if not self.account.access_token:
                logger.warning(f"No access token for {self.account.email_address}")
                raise ReAuthorizationRequiredError("No access token available")
            
            # Check if token needs refresh
            if (self.account.token_expires_at and 
                self.account.token_expires_at <= timezone.now()):
                logger.info(f"Access token expired for {self.account.email_address}, refreshing...")
                self._refresh_token()
            
            return {
                'Authorization': f'Bearer {self.account.access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
        except TokenRefreshError:
            # Token refresh failed, re-authorization required
            raise ReAuthorizationRequiredError("Token refresh failed - re-authorization required")
        except Exception as e:
            logger.error(f"Error getting headers for {self.account.email_address}: {str(e)}")
            raise
    
    def _refresh_token(self):
        """Refresh the access token if needed."""
        try:
            if not self.account.refresh_token:
                logger.warning(f"No refresh token available for {self.account.email_address}")
                raise ValueError("No refresh token available - re-authorization required")
            
            logger.info(f"Attempting to refresh token for {self.account.email_address}")
            
            token_data = self.oauth_service.refresh_access_token(
                self.account.refresh_token
            )
            
            # Update account with new token
            self.account.access_token = token_data['access_token']
            self.account.token_expires_at = token_data['expires_at']
            
            # Also update refresh token if provided (some OAuth providers rotate them)
            if 'refresh_token' in token_data and token_data['refresh_token']:
                self.account.refresh_token = token_data['refresh_token']
                self.account.save(update_fields=['access_token', 'token_expires_at', 'refresh_token'])
            else:
                self.account.save(update_fields=['access_token', 'token_expires_at'])
            
            logger.info(f"✅ Token successfully refreshed for account: {self.account.email_address}")
            
        except Exception as e:
            logger.error(f"❌ Token refresh failed for {self.account.email_address}: {str(e)}")
            
            # Mark tokens as invalid to prevent repeated failed attempts
            self.account.access_token = ""
            self.account.token_expires_at = None
            self.account.save(update_fields=['access_token', 'token_expires_at'])
            
            raise TokenRefreshError(f"Token refresh failed for {self.account.email_address}: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test the API connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try different endpoints to find working one
            test_endpoints = [
                "accounts/self",
                "accounts", 
                "folders",
                "me/folders"
            ]
            
            headers = self._get_headers()
            
            for endpoint in test_endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    logger.info(f"Testing connection with endpoint: {url}")
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    logger.info(f"Response status for {endpoint}: {response.status_code}")
                    
                    if response.status_code == 200:
                        logger.info(f"Connection successful with endpoint: {endpoint}")
                        return True
                    elif response.status_code == 401:
                        logger.error(f"Authentication failed - invalid token")
                        return False
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Endpoint {endpoint} failed: {str(e)}")
                    continue
            
            logger.error("All test endpoints failed")
            return False
            
        except Exception as e:
            logger.error(f"Connection test failed for {self.account.email_address}: {str(e)}")
            return False
    
    def get_account_info(self) -> Dict:
        """
        Get account information.
        
        Returns:
            Account information dictionary
        """
        try:
            url = f"{self.base_url}accounts"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=30)
            logger.info(f"Account info response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Account info data: {data}")
                return data
            else:
                logger.error(f"Account info failed: {response.status_code} - {response.text}")
                return {}
            
        except Exception as e:
            logger.error(f"Error fetching account info: {str(e)}")
            return {}

    def get_account_id(self) -> str:
        """
        Get the account ID for API calls.
        
        Returns:
            Account ID string
        """
        # First check if we have cached account ID in the database
        if hasattr(self.account, 'zoho_account_id') and self.account.zoho_account_id:
            logger.info(f"Using cached account ID: {self.account.zoho_account_id}")
            return self.account.zoho_account_id
        
        try:
            # Try to get account ID from accounts endpoint
            url = f"{self.base_url}accounts"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=10)
            logger.info(f"Accounts response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Accounts data: {data}")
                
                # Extract account ID from response
                if isinstance(data, dict) and 'data' in data:
                    accounts = data['data']
                    if isinstance(accounts, list) and len(accounts) > 0:
                        # Use the first account (there should only be one for the authenticated user)
                        first_account = accounts[0]
                        if isinstance(first_account, dict):
                            account_id = first_account.get('accountId')
                            if account_id:
                                logger.info(f"Found account ID: {account_id}")
                                self._cache_account_id(account_id)
                                return account_id
                        
                # Try alternative formats
                if isinstance(data, list) and len(data) > 0:
                    account_id = data[0].get('accountId', data[0].get('id', ''))
                    if account_id:
                        logger.info(f"Found account ID (alt format): {account_id}")
                        self._cache_account_id(account_id)
                        return account_id
            
            elif response.status_code == 429:
                logger.warning("Rate limit hit, using email address as fallback")
                return self.account.email_address
                
            else:
                logger.warning(f"Account ID request failed: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting account ID: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting account ID: {str(e)}")
            
        # Fallback: use email address as account ID
        logger.warning("Could not find account ID, using email address")
        return self.account.email_address
    
    def _cache_account_id(self, account_id: str):
        """Cache the account ID to avoid repeated API calls."""
        try:
            # Only cache if it's not an email address
            if '@' not in account_id and account_id != self.account.zoho_account_id:
                self.account.zoho_account_id = account_id
                self.account.save(update_fields=['zoho_account_id'])
                logger.info(f"Cached account ID: {account_id}")
        except Exception as e:
            logger.warning(f"Could not cache account ID: {str(e)}")

    def get_folders(self) -> List[Dict]:
        """
        Fetch all folders from Zoho Mail.
        
        Returns:
            List of folder dictionaries
        """
        try:
            # Get the correct account ID from Zoho
            account_id = self.get_account_id()
            logger.info(f"Fetching folders for account ID: {account_id}")
            
            # Try different folder endpoints - the correct one uses numeric account ID
            folder_endpoints = [
                f"accounts/{account_id}/folders",
            ]
            
            headers = self._get_headers()
            
            for endpoint in folder_endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    logger.info(f"Trying folder endpoint: {url}")
                    
                    response = requests.get(url, headers=headers, timeout=30)
                    logger.info(f"Folder response {endpoint}: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Folder data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                        
                        # Extract folders from different response formats
                        folders = []
                        if isinstance(data, dict):
                            folders = data.get('data', data.get('folders', []))
                        elif isinstance(data, list):
                            folders = data
                            
                        logger.info(f"Found {len(folders)} folders")
                        return folders
                        
                    else:
                        logger.warning(f"Folder endpoint {endpoint} failed: {response.status_code} - {response.text[:200]}")
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Folder endpoint {endpoint} error: {str(e)}")
                    continue
            
            logger.error("All folder endpoints failed")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching folders for {self.account.email_address}: {str(e)}")
            return []
    
    def get_emails(self, folder_id: str, limit: int = 1000, start: int = 1, start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """
        Fetch emails from a specific folder.
        
        Args:
            folder_id: The folder ID
            limit: Maximum number of emails to fetch
            start: Starting index (1-based)
            start_date: Start date for filtering emails (optional)
            end_date: End date for filtering emails (optional)
            
        Returns:
            List of email dictionaries
        """
        try:
            # Get the correct account ID from Zoho  
            account_id = self.get_account_id()
            logger.info(f"Fetching emails for account ID: {account_id}")
            
            # Use the correct endpoint format with numeric account ID
            email_endpoints = [
                f"accounts/{account_id}/messages/view",
            ]
            headers = self._get_headers()
            
            # Parameters for Zoho Mail API messages/view endpoint
            params = {
                'limit': min(limit, 200),  # Zoho's API limit is 200
                'start': start
            }
            
            # Add folder filter if specified
            if folder_id:
                params['folderId'] = folder_id
            
            # Note: Zoho API doesn't support fromDate/toDate parameters for messages/view
            # Date filtering will be done client-side after fetching emails
            
            # Try each endpoint until one works
            for endpoint in email_endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    logger.info(f"Trying email endpoint: {url}")
                    
                    response = requests.get(url, headers=headers, params=params, timeout=10)
                    logger.info(f"Email API response: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Success with endpoint: {endpoint}")
                        break
                    elif response.status_code == 429:
                        logger.warning(f"Rate limit hit on endpoint: {endpoint}")
                        continue
                    else:
                        logger.warning(f"Endpoint {endpoint} failed: {response.status_code} - {response.text[:200]}")
                        continue
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Network error with endpoint {endpoint}: {str(e)}")
                    continue
                    
            else:
                # All endpoints failed
                logger.error("All email endpoints failed")
                return []
            
            if response.status_code == 200:
                logger.info(f"Email API response keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                
                # Extract emails from Zoho API response
                emails = []
                if isinstance(data, dict):
                    if 'data' in data:
                        emails = data['data']
                    elif 'messages' in data:
                        emails = data['messages']
                    else:
                        # Sometimes the response is directly the data
                        emails = [data] if data else []
                elif isinstance(data, list):
                    emails = data
                
                logger.info(f"Found {len(emails)} emails in folder {folder_id}")
                
                # Apply client-side date filtering if specified
                if start_date or end_date:
                    filtered_emails = []
                    for email in emails:
                        email_date = self._parse_datetime(email.get('sentTime', email.get('sentDateInGMT', email.get('date'))))
                        
                        # Check if email is within date range
                        if start_date and email_date < start_date:
                            continue
                        if end_date and email_date > end_date:
                            continue
                        
                        filtered_emails.append(email)
                    
                    logger.info(f"After date filtering: {len(filtered_emails)} emails remain")
                    return filtered_emails
                
                return emails
                
            elif response.status_code == 400:
                error_data = response.json()
                if error_data.get('data', {}).get('errorCode') == 'INVALID_FOLDER':
                    logger.warning(f"Invalid folder ID: {folder_id}")
                    return []
                else:
                    logger.error(f"API error 400: {response.text}")
                    return []
                    
            elif response.status_code == 401:
                logger.error("Authentication failed - token may be expired")
                # Try to refresh token
                self._refresh_token()
                return []
                
            else:
                logger.error(f"Email API failed: {response.status_code} - {response.text[:500]}")
                return []
            
        except Exception as e:
            logger.error(f"Error fetching emails for {self.account.email_address}: {str(e)}")
            return []
    
    def get_email_details(self, message_id: str, folder_id: str = None) -> Optional[Dict]:
        """
        Fetch detailed information for a specific email.
        
        Args:
            message_id: The message ID
            folder_id: Optional folder ID for better API routing
            
        Returns:
            Email details dictionary or None
        """
        try:
            # Get account ID for API calls
            account_id = self.get_account_id()
            
            # Build endpoints to try (prioritize folder-based content endpoint if folder_id provided)
            endpoints_to_try = []
            
            if folder_id:
                # Folder-based endpoints tend to work better
                endpoints_to_try.extend([
                    f"accounts/{account_id}/folders/{folder_id}/messages/{message_id}/content",
                    f"accounts/{account_id}/folders/{folder_id}/messages/{message_id}/view",
                    f"accounts/{account_id}/folders/{folder_id}/messages/{message_id}",
                ])
            
            # Add general endpoints as fallback
            endpoints_to_try.extend([
                f"accounts/{account_id}/messages/{message_id}/content",
                f"accounts/{account_id}/messages/{message_id}/view",
                f"accounts/{account_id}/messages/{message_id}",
                f"accounts/{account_id}/messages/view/{message_id}",
            ])
            
            headers = self._get_headers()
            
            for endpoint in endpoints_to_try:
                url = f"{self.base_url}{endpoint}"
                logger.debug(f"Trying message details from: {url}")
                
                response = requests.get(url, headers=headers, timeout=30)
                logger.debug(f"Message detail response from {endpoint}: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract message data from Zoho API response
                    message_data = None
                    if isinstance(data, dict):
                        if 'data' in data:
                            message_data = data['data']
                        else:
                            message_data = data
                    elif isinstance(data, list) and len(data) > 0:
                        message_data = data[0]
                    else:
                        message_data = data
                        
                    if message_data:
                        logger.debug(f"Retrieved message details for {message_id} from {endpoint}")
                        return message_data
                    
                elif response.status_code == 404:
                    logger.debug(f"Message {message_id} not found at {endpoint}")
                    continue  # Try next endpoint
                    
                elif response.status_code == 401:
                    logger.error("Authentication failed - token may be expired")
                    self._refresh_token()
                    return None
                else:
                    logger.debug(f"Message detail API failed at {endpoint}: {response.status_code} - {response.text[:200]}")
                    continue  # Try next endpoint
                    
            # If we get here, none of the endpoints worked
            logger.warning(f"No working endpoint found for message {message_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching email details {message_id}: {str(e)}")
            return None
    
    def upload_attachment(self, file_content: bytes, filename: str, content_type: str = None) -> Optional[Dict]:
        """
        Upload an attachment to Zoho Mail API.
        
        Args:
            file_content: Binary file content
            filename: Name of the file
            content_type: MIME type of the file
            
        Returns:
            Attachment info dict or None if failed
        """
        try:
            # Get account ID for API calls
            account_id = self.get_account_id()
            
            # Zoho Mail API endpoint for uploading attachments
            url = f"{self.base_url}accounts/{account_id}/messages/attachments"
            headers = self._get_headers()
            
            # Remove Content-Type header to let requests handle multipart
            headers.pop('Content-Type', None)
            headers.pop('Accept', None)  # Remove Accept header too
            
            # Try multipart form upload
            files = {
                'attachment': (filename, file_content, content_type or 'application/octet-stream')
            }
            
            # Add query parameters
            params = {
                'uploadType': 'multipart',
                'isInline': 'false'
            }
            
            logger.info(f"Uploading attachment: {filename} ({len(file_content)} bytes)")
            logger.info(f"Upload URL: {url}")
            logger.info(f"Upload params: {params}")
            logger.info(f"Headers: {headers}")
            
            response = requests.post(url, headers=headers, files=files, params=params, timeout=60)
            
            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Attachment uploaded successfully: {filename}")
                
                # Extract attachment info from response
                if isinstance(data, dict) and 'data' in data:
                    attachment_info = data['data']
                elif isinstance(data, dict):
                    attachment_info = data
                else:
                    attachment_info = {}
                
                return {
                    'filename': filename,
                    'storeName': attachment_info.get('storeName', ''),
                    'attachmentName': attachment_info.get('attachmentName', filename),
                    'attachmentPath': attachment_info.get('attachmentPath', ''),
                    'size': len(file_content),
                    'content_type': content_type
                }
                
            elif response.status_code == 401:
                logger.error("Authentication failed - token may be expired")
                self._refresh_token()
                return None
                
            else:
                logger.error(f"Attachment upload failed: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error uploading attachment {filename}: {str(e)}")
            return None
    
    def download_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download an attachment from a specific email.
        
        Args:
            message_id: The message ID
            attachment_id: The attachment ID
            
        Returns:
            Binary file content or None if failed
        """
        try:
            # Get account ID for API calls
            account_id = self.get_account_id()
            
            # Zoho Mail API endpoint for downloading attachments
            # We need to find the folder ID first - try common folders
            common_folders = ['INBOX', 'SENT', 'DRAFTS']
            
            for folder_name in common_folders:
                try:
                    url = f"{self.base_url}accounts/{account_id}/folders/{folder_name}/messages/{message_id}/attachments/{attachment_id}"
                    headers = self._get_headers()
                    
                    logger.debug(f"Trying to download attachment from: {url}")
                    
                    response = requests.get(url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        logger.info(f"Attachment downloaded successfully: {attachment_id}")
                        return response.content
                    elif response.status_code == 404:
                        continue  # Try next folder
                    elif response.status_code == 401:
                        logger.error("Authentication failed - token may be expired")
                        self._refresh_token()
                        return None
                    else:
                        logger.debug(f"Folder {folder_name} failed: {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Folder {folder_name} error: {str(e)}")
                    continue
            
            logger.warning(f"Attachment {attachment_id} not found in any folder")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading attachment {attachment_id}: {str(e)}")
            return None

    def send_email(self, to_emails: List[str], subject: str, body_text: str = "", 
                   body_html: str = "", cc_emails: List[str] = None, 
                   bcc_emails: List[str] = None, attachments: List = None) -> bool:
        """
        Send an email via Zoho Mail API.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            attachments: List of attachment data
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get account ID for API calls
            account_id = self.get_account_id()
            
            # Correct Zoho Mail API endpoint for sending messages
            url = f"{self.base_url}accounts/{account_id}/messages"
            headers = self._get_headers()
            
            # Prepare email data according to Zoho API format
            email_data = {
                'fromAddress': self.account.email_address,
                'toAddress': ','.join(to_emails) if isinstance(to_emails, list) else to_emails,
                'subject': subject,
                'content': body_html or body_text or '',
                'mailFormat': 'html' if body_html else 'plaintext'
            }
            
            if cc_emails:
                email_data['ccAddress'] = ','.join(cc_emails) if isinstance(cc_emails, list) else cc_emails
            if bcc_emails:
                email_data['bccAddress'] = ','.join(bcc_emails) if isinstance(bcc_emails, list) else bcc_emails
            
            # Handle attachments if provided
            if attachments:
                attachment_list = []
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        # If attachment is already uploaded info
                        attachment_list.append({
                            'storeName': attachment.get('storeName', ''),
                            'attachmentName': attachment.get('attachmentName', ''),
                            'attachmentPath': attachment.get('attachmentPath', '')
                        })
                    else:
                        logger.warning(f"Invalid attachment format: {type(attachment)}")
                
                if attachment_list:
                    email_data['attachments'] = attachment_list
                    logger.info(f"Added {len(attachment_list)} attachments to email")
            
            logger.info(f"Sending email to: {to_emails}")
            logger.info(f"From: {self.account.email_address}")
            logger.info(f"Subject: {subject}")
            
            response = requests.post(url, headers=headers, json=email_data, timeout=30)
            
            if response.status_code in [200, 201]:
                logger.info(f"Email sent successfully from {self.account.email_address}")
                return True
            elif response.status_code == 401:
                logger.error("Authentication failed - token may be expired")
                self._refresh_token()
                return False
            else:
                logger.error(f"Email send failed: {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending email from {self.account.email_address}: {str(e)}")
            return False

    def _parse_datetime(self, timestamp_str: str) -> datetime:
        """Parse Zoho timestamp string to datetime object."""
        if not timestamp_str:
            return timezone.now()
        
        try:
            # Zoho typically returns timestamps in milliseconds
            if str(timestamp_str).isdigit():
                timestamp = int(timestamp_str) / 1000
                from datetime import timezone as dt_timezone
                return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
            
            # Try parsing as ISO format
            return datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
            
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp: {timestamp_str}")
            return timezone.now()


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
                        'unread_count': folder_data.get('unreadCount', 0),
                        'total_count': folder_data.get('totalCount', 0)
                    }
                )
                
                if not created:
                    folder.name = folder_name
                    folder.unread_count = folder_data.get('unreadCount', 0)
                    folder.total_count = folder_data.get('totalCount', 0)
                    folder.save()
                
                synced_count += 1
            
            logger.info(f"Synced {synced_count} folders for {self.account.email_address}")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing folders for {self.account.email_address}: {str(e)}")
            return 0
    
    def sync_emails(self, folder: Folder = None, limit: int = 1000, start_date: datetime = None, end_date: datetime = None) -> Dict[str, int]:
        """
        Synchronize emails for a specific folder or all folders.
        
        Args:
            folder: Specific folder to sync, None for all folders
            limit: Maximum emails per folder to sync
            start_date: Start date for filtering emails (optional)
            end_date: End date for filtering emails (optional)
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {'fetched': 0, 'created': 0, 'updated': 0, 'errors': 0}
        
        try:
            folders_to_sync = [folder] if folder else self.account.folders.all()
            
            for folder_obj in folders_to_sync:
                try:
                    # For 90-day sync, we need to paginate through multiple batches
                    batch_size = 200  # Zoho API limit
                    start_index = 1
                    emails_in_range_found = True
                    folder_emails_processed = 0
                    
                    logger.info(f"Starting sync for folder {folder_obj.name} (limit: {limit})")
                    
                    while emails_in_range_found and folder_emails_processed < limit:
                        batch_limit = min(batch_size, limit - folder_emails_processed)
                        
                        emails_data = self.api_service.get_emails(
                            folder_obj.zoho_folder_id, 
                            limit=batch_limit,
                            start=start_index,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        if not emails_data:
                            logger.info(f"No more emails found in folder {folder_obj.name}")
                            break
                            
                        # Process this batch
                        batch_count = 0
                        for email_data in emails_data:
                            try:
                                created = self._sync_single_email(email_data, folder_obj)
                                stats['fetched'] += 1
                                batch_count += 1
                                if created:
                                    stats['created'] += 1
                            except Exception as e:
                                logger.error(f"Error syncing email {email_data.get('messageId')}: {str(e)}")
                                stats['errors'] += 1
                        
                        folder_emails_processed += batch_count
                        start_index += batch_size
                        
                        # If we got fewer emails than requested, we've reached the end
                        if len(emails_data) < batch_limit:
                            logger.info(f"Reached end of folder {folder_obj.name} (got {len(emails_data)} < {batch_limit})")
                            break
                            
                        logger.info(f"Processed batch for {folder_obj.name}: {batch_count} emails (total: {folder_emails_processed})")
                    
                    logger.info(f"Completed folder {folder_obj.name}: {folder_emails_processed} emails processed")
                    
                except Exception as e:
                    logger.error(f"Error syncing folder {folder_obj.name}: {str(e)}")
                    stats['errors'] += 1
            
            # Update folder counts after sync
            self._update_folder_counts()
            
            # Update last sync time
            self.account.last_sync = timezone.now()
            self.account.save(update_fields=['last_sync'])
            
            logger.info(f"Email sync completed for {self.account.email_address}: {stats}")
            
        except Exception as e:
            logger.error(f"Error in email sync for {self.account.email_address}: {str(e)}")
            stats['errors'] += 1
        
        return stats
    
    def _sync_single_email(self, email_data: Dict, folder: Folder) -> bool:
        """
        Sync a single email to the database.
        
        Returns:
            True if a new email was created, False if it already existed
        """
        zoho_message_id = email_data.get('messageId', email_data.get('id'))
        zoho_thread_id = ''  # Initialize to avoid NameError
        
        if not zoho_message_id:
            logger.warning("No message ID found in email data")
            return False
        
        # Check if email already exists
        if Email.objects.filter(zoho_message_id=zoho_message_id).exists():
            logger.debug(f"Email {zoho_message_id} already exists, skipping")
            return False
        
        # Use basic email data first, then get details if needed
        subject = email_data.get('subject', '')
        from_email = email_data.get('fromAddress', email_data.get('from', ''))
        from_name = email_data.get('fromName', email_data.get('fromDisplayName', ''))
        zoho_thread_id = email_data.get('threadId', email_data.get('conversationId', ''))
        
        # Find or create email thread
        email_thread = None
        if zoho_thread_id:
            email_thread = self._get_or_create_thread(
                thread_id=zoho_thread_id,
                subject=subject,
                sent_at=self._parse_datetime(email_data.get('sentTime', email_data.get('date')))
            )
        
        # Create email object with available data
        email_obj = Email.objects.create(
            account=self.account,
            folder=folder,
            thread=email_thread,
            zoho_message_id=zoho_message_id,
            zoho_thread_id=zoho_thread_id,
            subject=subject,
            from_email=from_email,
            from_name=from_name,
            to_emails=self._parse_emails(email_data.get('toAddress', email_data.get('to', ''))),
            cc_emails=self._parse_emails(email_data.get('ccAddress', email_data.get('cc', ''))),
            bcc_emails=self._parse_emails(email_data.get('bccAddress', email_data.get('bcc', ''))),
            body_text=email_data.get('content', email_data.get('bodyText', email_data.get('textContent', email_data.get('body', email_data.get('summary', ''))))),
            body_html=email_data.get('htmlContent', email_data.get('bodyHtml', email_data.get('content', email_data.get('body', email_data.get('summary', ''))))),
            is_read=not email_data.get('isUnread', False),
            is_starred=email_data.get('isStarred', False),
            is_important=email_data.get('isImportant', False),
            sent_at=self._parse_datetime(email_data.get('sentTime', email_data.get('sentDateInGMT', email_data.get('date')))),
            received_at=self._parse_datetime(email_data.get('receivedTime', email_data.get('receivedDate'))),
        )
        
        logger.debug(f"Created email: {subject[:50]}... from {from_email}")
        
        # Always get detailed content if content seems incomplete or is just summary
        content_length = len(email_obj.body_text or '') + len(email_obj.body_html or '')
        text_content = (email_obj.body_text or '').lower()
        html_content = (email_obj.body_html or '').lower()
        
        # Fetch detailed content if:
        # - Content is very short (< 1000 chars) - increased from 200 to catch more truncated emails
        # - Content contains summary indicators
        # - Content seems to be truncated
        should_fetch_details = (
            content_length < 1000 or
            'summary' in text_content or
            'summary' in html_content or
            text_content.endswith('...') or
            html_content.endswith('...') or
            'mehr anzeigen' in text_content or
            'show more' in text_content or
            len(text_content) < 50 or
            # If HTML content looks like plain text (no HTML tags), fetch detailed content
            (email_obj.body_html and '<' not in email_obj.body_html and '>' not in email_obj.body_html)
        )
        
        if should_fetch_details:
            try:
                logger.info(f"Email {email_obj.id} has incomplete content ({content_length} chars), fetching details...")
                email_details = self.api_service.get_email_details(zoho_message_id, folder.zoho_folder_id)
                if email_details:
                    # Handle nested data structure from API
                    detail_data = email_details.get('data', email_details)
                    
                    # Get the full content with better field mapping
                    full_text = detail_data.get('content', detail_data.get('textContent', detail_data.get('bodyText', '')))
                    full_html = detail_data.get('htmlContent', detail_data.get('bodyHtml', detail_data.get('content', '')))
                    
                    # Only update if we got more complete content
                    if len(full_text) > len(email_obj.body_text or '') or len(full_html) > len(email_obj.body_html or ''):
                        email_obj.body_text = full_text or email_obj.body_text
                        email_obj.body_html = full_html or email_obj.body_html
                        email_obj.save(update_fields=['body_text', 'body_html'])
                        logger.info(f"Updated email {email_obj.id} with detailed content ({len(full_text)} text chars, {len(full_html)} html chars)")
            except Exception as e:
                logger.warning(f"Could not fetch detailed content for {zoho_message_id}: {str(e)}")
        
        # Handle attachments if they exist
        if email_data.get('hasAttachments', False) and email_data.get('attachments'):
            self._sync_attachments(email_obj, email_data.get('attachments', []))
        
        # Update thread statistics
        if email_thread:
            email_thread.update_thread_stats()
        
        return True
    
    def _update_folder_counts(self):
        """Update email counts for all folders."""
        try:
            folders = self.account.folders.all()
            for folder in folders:
                total_count = Email.objects.filter(account=self.account, folder=folder).count()
                unread_count = Email.objects.filter(account=self.account, folder=folder, is_read=False).count()
                
                folder.total_count = total_count
                folder.unread_count = unread_count
                folder.save(update_fields=['total_count', 'unread_count'])
                
                logger.debug(f"Updated folder {folder.name}: {total_count} total, {unread_count} unread")
                
        except Exception as e:
            logger.error(f"Error updating folder counts: {str(e)}")
    
    def _sync_attachments(self, email_obj: Email, attachments_data: List[Dict]):
        """Sync attachments for an email."""
        for attachment_data in attachments_data:
            EmailAttachment.objects.get_or_create(
                email=email_obj,
                zoho_attachment_id=attachment_data.get('attachmentId'),
                defaults={
                    'filename': attachment_data.get('attachmentName', ''),
                    'content_type': attachment_data.get('contentType', ''),
                    'file_size': attachment_data.get('size', 0),
                }
            )
    
    def _map_folder_type(self, folder_name: str) -> str:
        """Map Zoho folder names to our folder types."""
        folder_mapping = {
            'inbox': 'inbox',
            'sent': 'sent',
            'drafts': 'drafts',
            'trash': 'trash',
            'spam': 'spam',
            'junk': 'spam',
        }
        return folder_mapping.get(folder_name, 'custom')
    
    def _get_or_create_thread(self, thread_id: str, subject: str, sent_at) -> EmailThread:
        """Get or create an email thread."""
        try:
            # Try to find existing thread
            thread = EmailThread.objects.get(thread_id=thread_id, account=self.account)
            return thread
        except EmailThread.DoesNotExist:
            # Create new thread
            # Clean subject (remove Re:, Fwd:, etc.)
            clean_subject = self._clean_subject(subject)
            
            thread = EmailThread.objects.create(
                account=self.account,
                thread_id=thread_id,
                subject=clean_subject,
                first_message_at=sent_at,
                last_message_at=sent_at,
                message_count=0,
                unread_count=0
            )
            
            logger.debug(f"Created new thread: {clean_subject[:50]}...")
            return thread
    
    def _clean_subject(self, subject: str) -> str:
        """Clean email subject by removing Re:, Fwd:, etc."""
        if not subject:
            return "(No Subject)"
        
        # Remove common prefixes
        prefixes = ['re:', 'fw:', 'fwd:', 'aw:', 'wg:', 'antwort:', 'weiterleitung:']
        
        cleaned = subject.strip()
        
        # Keep removing prefixes until none are found
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if cleaned.lower().startswith(prefix):
                    cleaned = cleaned[len(prefix):].strip()
                    changed = True
                    break
        
        return cleaned if cleaned else "(No Subject)"
    
    def _parse_emails(self, email_string: str) -> List[str]:
        """Parse email string into list of email addresses."""
        if not email_string:
            return []
        
        # Handle Zoho API's "Not Provided" values
        if email_string.strip().lower() in ['not provided', 'not_provided', '', 'null', 'none']:
            return []
        
        # Split by comma and clean up each email
        emails = []
        for email in email_string.split(','):
            email = email.strip()
            if email and email.lower() not in ['not provided', 'not_provided', 'null', 'none']:
                # Extract email from "Name <email@example.com>" format
                if '<' in email and '>' in email:
                    email = email.split('<')[1].split('>')[0].strip()
                emails.append(email)
        
        return emails
    
    def _parse_datetime(self, timestamp_str: str) -> datetime:
        """Parse Zoho timestamp string to datetime object."""
        if not timestamp_str:
            return timezone.now()
        
        try:
            # Zoho typically returns timestamps in milliseconds
            if str(timestamp_str).isdigit():
                timestamp = int(timestamp_str) / 1000
                from datetime import timezone as dt_timezone
                return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
            
            # Try parsing as ISO format
            return datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
            
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp: {timestamp_str}")
            return timezone.now()