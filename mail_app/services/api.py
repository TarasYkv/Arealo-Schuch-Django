"""
Zoho Mail API Service
"""
import logging
import requests
from typing import Dict, List, Optional
from django.conf import settings
from django.utils import timezone
from .exceptions import (
    TokenRefreshError, 
    ReAuthorizationRequiredError, 
    ZohoAPIError,
    EmailNotFoundError,
    FolderNotFoundError,
    RateLimitExceededError,
    AuthenticationError
)
from .oauth import ZohoOAuthService
from ..constants import ZOHO_MAIL_API_BASE
from ..error_handlers import external_api_error, authentication_required, MailAppError, ErrorType, ErrorSeverity
from ..recovery import retry_on_api_error, circuit_breaker, create_resilient_api_call
from ..logging_config import get_mail_logger, get_performance_logger

logger = get_mail_logger('mail_app.api')


class ZohoMailAPIService:
    """
    Service for making API calls to Zoho Mail.
    """
    
    def __init__(self, email_account):
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
        except Exception:
            # Fallback to .env configuration
            try:
                self.config = settings.ZOHO_MAIL_CONFIG
                self.base_url = self.config['BASE_URL']
                logger.info(f"Using .env Zoho base_url: {self.base_url}")
            except (AttributeError, KeyError):
                logger.error("No Zoho base URL configuration found")
                self.base_url = ZOHO_MAIL_API_BASE  # Default fallback
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
            logger.error(f"Error getting headers for {self.account.email_address}: {e}")
            raise ZohoAPIError(f"Failed to get API headers: {e}")
    
    def _refresh_token(self):
        """Refresh the access token if needed."""
        try:
            if not self.account.refresh_token:
                logger.warning(f"No refresh token available for {self.account.email_address}")
                raise ReAuthorizationRequiredError("No refresh token available - re-authorization required")
            
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
            logger.error(f"❌ Token refresh failed for {self.account.email_address}: {e}")
            
            # Mark tokens as invalid to prevent repeated failed attempts
            self.account.access_token = ""
            self.account.token_expires_at = None
            self.account.save(update_fields=['access_token', 'token_expires_at'])
            
            raise TokenRefreshError(f"Token refresh failed for {self.account.email_address}: {e}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make a request to Zoho API with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            Response object
            
        Raises:
            ZohoAPIError: For API errors
            AuthenticationError: For authentication errors
            RateLimitExceededError: For rate limit errors
        """
        try:
            url = f"{self.base_url}{endpoint}"
            headers = self._get_headers()
            headers.update(kwargs.pop('headers', {}))
            
            logger.debug(f"Making {method} request to: {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=30,
                **kwargs
            )
            
            # Handle different response codes
            if response.status_code == 200:
                return response
            elif response.status_code == 401:
                logger.error(f"Authentication failed for {endpoint}")
                raise AuthenticationError("Authentication failed", response.status_code, response.json() if response.content else None)
            elif response.status_code == 429:
                logger.error(f"Rate limit exceeded for {endpoint}")
                raise RateLimitExceededError("Rate limit exceeded", response.status_code, response.json() if response.content else None)
            elif response.status_code == 404:
                logger.error(f"Resource not found: {endpoint}")
                raise ZohoAPIError(f"Resource not found: {endpoint}", response.status_code)
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text[:500]}")
                raise ZohoAPIError(f"API request failed: {response.status_code}", response.status_code, response.json() if response.content else None)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error for {endpoint}: {e}")
            raise ZohoAPIError(f"Network error: {e}")
        except (AuthenticationError, RateLimitExceededError):
            # Re-raise specific exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {e}")
            raise ZohoAPIError(f"Unexpected error: {e}")
    
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
            
            for endpoint in test_endpoints:
                try:
                    logger.info(f"Testing connection with endpoint: {endpoint}")
                    response = self._make_request('GET', endpoint)
                    
                    if response.status_code == 200:
                        logger.info(f"Connection successful with endpoint: {endpoint}")
                        return True
                        
                except (AuthenticationError, ReAuthorizationRequiredError):
                    logger.error("Authentication failed - invalid token")
                    return False
                except Exception as e:
                    logger.warning(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            logger.error("All test endpoints failed")
            return False
            
        except Exception as e:
            logger.error(f"Connection test failed for {self.account.email_address}: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """
        Get account information.
        
        Returns:
            Account information dictionary
        """
        try:
            response = self._make_request('GET', 'accounts')
            data = response.json()
            logger.info(f"Account info retrieved successfully")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return {}

    def get_account_id(self) -> str:
        """
        Get the account ID for API calls.
        
        Returns:
            Account ID string
        """
        # First check if we have cached account ID in the database
        if hasattr(self.account, 'zoho_account_id') and self.account.zoho_account_id:
            logger.debug(f"Using cached account ID: {self.account.zoho_account_id}")
            return self.account.zoho_account_id
        
        try:
            response = self._make_request('GET', 'accounts')
            data = response.json()
            
            # Extract account ID from response
            account_id = self._extract_account_id(data)
            if account_id:
                logger.info(f"Found account ID: {account_id}")
                self._cache_account_id(account_id)
                return account_id
            else:
                logger.error(f"Could not extract account ID from response: {data}")
                raise ZohoAPIError("Account ID not found in API response")
                
        except Exception as e:
            logger.error(f"Error getting account ID: {e}")
            raise ZohoAPIError(f"Failed to get account ID: {e}")
    
    def _extract_account_id(self, data: Dict) -> Optional[str]:
        """Extract account ID from API response."""
        if isinstance(data, dict) and 'data' in data:
            accounts = data['data']
            if isinstance(accounts, list) and len(accounts) > 0:
                first_account = accounts[0]
                if isinstance(first_account, dict):
                    return first_account.get('accountId') or first_account.get('id')
                        
        # Try alternative formats
        if isinstance(data, list) and len(data) > 0:
            return data[0].get('accountId') or data[0].get('id')
        
        return None
    
    def _cache_account_id(self, account_id: str):
        """Cache account ID in database."""
        try:
            if hasattr(self.account, 'zoho_account_id'):
                self.account.zoho_account_id = account_id
                self.account.save(update_fields=['zoho_account_id'])
                logger.info(f"Cached account ID in database: {account_id}")
        except Exception as e:
            logger.warning(f"Could not cache account ID: {e}")
    
    @retry_on_api_error(max_attempts=3)
    @circuit_breaker(name="zoho_get_folders", failure_threshold=5, recovery_timeout=60)
    def get_folders(self, account_id: str = None) -> List[Dict]:
        """
        Get folders for the account.
        
        Args:
            account_id: Optional account ID, will be fetched if not provided
            
        Returns:
            List of folder dictionaries
        """
        with get_performance_logger(f"get_folders_account_{account_id or 'auto'}"):
            try:
                if not account_id:
                    account_id = self.get_account_id()
                
                endpoint = f"accounts/{account_id}/folders"
                response = self._make_request('GET', endpoint)
                data = response.json()
                
                # Extract folders from response
                if isinstance(data, dict) and 'data' in data:
                    folders = data['data']
                elif isinstance(data, list):
                    folders = data
                else:
                    logger.warning(f"Unexpected folders response format: {type(data)}")
                    folders = []
                
                logger.info(f"Retrieved {len(folders)} folders")
                return folders
                
            except Exception as e:
                logger.error(f"Error fetching folders: {e}")
                raise ZohoAPIError(f"Failed to get folders: {e}")
    
    def get_emails(self, account_id: str, folder_id: str, limit: int = 50, start: int = 0) -> List[Dict]:
        """
        Get emails from a specific folder.
        
        Args:
            account_id: Account ID
            folder_id: Folder ID  
            limit: Maximum number of emails to fetch
            start: Starting index for pagination
            
        Returns:
            List of email dictionaries
        """
        try:
            endpoint = f"accounts/{account_id}/messages/view"
            params = {
                'folderId': folder_id,
                'limit': limit
            }
            
            response = self._make_request('GET', endpoint, params=params)
            data = response.json()
            
            # Extract emails from response
            if isinstance(data, dict) and 'data' in data:
                emails = data['data']
            elif isinstance(data, list):
                emails = data
            else:
                logger.warning(f"Unexpected emails response format: {type(data)}")
                emails = []
            
            logger.info(f"Retrieved {len(emails)} emails from folder {folder_id}")
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            raise ZohoAPIError(f"Failed to get emails: {e}")
    
    def get_email_content(self, account_id: str, message_id: str) -> Dict:
        """
        Get full email content including body and attachments.
        
        Args:
            account_id: Account ID
            message_id: Message ID
            
        Returns:
            Email content dictionary
        """
        try:
            endpoint = f"accounts/{account_id}/messages/{message_id}"
            response = self._make_request('GET', endpoint)
            data = response.json()
            
            if isinstance(data, dict) and 'data' in data:
                email_data = data['data']
            else:
                email_data = data
            
            logger.info(f"Retrieved email content for message {message_id}")
            return email_data
            
        except Exception as e:
            logger.error(f"Error fetching email content for {message_id}: {e}")
            raise EmailNotFoundError(f"Failed to get email content: {e}")
    
    def send_email(self, account_id: str, email_data: Dict) -> Dict:
        """
        Send an email.
        
        Args:
            account_id: Account ID
            email_data: Email data dictionary
            
        Returns:
            Send response dictionary
        """
        try:
            endpoint = f"accounts/{account_id}/messages"
            response = self._make_request('POST', endpoint, json=email_data)
            data = response.json()
            
            logger.info(f"Email sent successfully")
            return data
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise ZohoAPIError(f"Failed to send email: {e}")
    
    def get_attachment(self, account_id: str, message_id: str, attachment_id: str) -> bytes:
        """
        Download email attachment.
        
        Args:
            account_id: Account ID
            message_id: Message ID
            attachment_id: Attachment ID
            
        Returns:
            Attachment binary data
        """
        try:
            endpoint = f"accounts/{account_id}/messages/{message_id}/attachments/{attachment_id}"
            headers = self._get_headers()
            # Remove content-type for binary downloads
            headers.pop('Content-Type', None)
            
            response = self._make_request('GET', endpoint, headers=headers)
            
            logger.info(f"Downloaded attachment {attachment_id}")
            return response.content
            
        except Exception as e:
            logger.error(f"Error downloading attachment {attachment_id}: {e}")
            raise ZohoAPIError(f"Failed to download attachment: {e}")