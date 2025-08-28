import json
import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from .models import ZohoMailServerConnection, EmailTemplate, EmailSendLog

logger = logging.getLogger(__name__)


class ZohoMailService:
    """Service for handling Zoho Mail API operations"""
    
    REGION_ENDPOINTS = {
        'US': 'https://mail.zoho.com',
        'EU': 'https://mail.zoho.eu', 
        'IN': 'https://mail.zoho.in',
        'AU': 'https://mail.zoho.com.au',
        'CN': 'https://mail.zoho.com.cn',
        'JP': 'https://mail.zoho.jp'
    }
    
    def __init__(self, connection: ZohoMailServerConnection):
        self.connection = connection
        base_url = self.REGION_ENDPOINTS.get(connection.region, self.REGION_ENDPOINTS['EU'])
        # Add /api/ if not already present (same as mail_app)
        self.base_url = f"{base_url}/api/" if not base_url.endswith('/api/') else base_url
        
    def get_auth_url(self) -> str:
        """Generate OAuth2 authorization URL"""
        auth_url = f"https://accounts.zoho.{self.connection.region.lower()}/oauth/v2/auth"
        params = {
            'scope': 'ZohoMail.messages.ALL,ZohoMail.folders.ALL,ZohoMail.accounts.READ',
            'client_id': self.connection.client_id,
            'response_type': 'code',
            'redirect_uri': self.connection.redirect_uri,
            'access_type': 'offline',
            'state': f'email_templates_{self.connection.id}'  # Add state to identify source
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{auth_url}?{query_string}"
    
    def exchange_code_for_tokens(self, auth_code: str) -> dict:
        """Exchange authorization code for access and refresh tokens"""
        token_url = f"https://accounts.zoho.{self.connection.region.lower()}/oauth/v2/token"
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.connection.client_id,
            'client_secret': self.connection.client_secret,
            'redirect_uri': self.connection.redirect_uri,
            'code': auth_code
        }
        
        try:
            response = requests.post(token_url, data=data)
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed with status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")
            
            token_data = response.json()
            logger.info(f"Token exchange successful, received keys: {list(token_data.keys())}")
            
            if 'error' in token_data:
                logger.error(f"OAuth error in response: {token_data}")
                raise Exception(f"OAuth error: {token_data.get('error')} - {token_data.get('error_description', '')}")
            
            # Save tokens to connection (use .get() like mail_app does)
            self.connection.access_token = token_data.get('access_token')
            self.connection.refresh_token = token_data.get('refresh_token')
            self.connection.token_expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            self.connection.is_configured = True
            self.connection.last_test_success = timezone.now()
            self.connection.last_error = ''
            self.connection.save()
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in', 3600),
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during token exchange: {str(e)}"
            self.connection.last_error = error_msg
            self.connection.save()
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error exchanging code for tokens: {str(e)}"
            self.connection.last_error = error_msg
            self.connection.save()
            logger.error(error_msg)
            raise
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.connection.refresh_token:
            logger.error("No refresh token available")
            return False
            
        token_url = f"https://accounts.zoho.{self.connection.region.lower()}/oauth/v2/token"
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.connection.client_id,
            'client_secret': self.connection.client_secret,
            'refresh_token': self.connection.refresh_token
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        try:
            logger.info(f"Refreshing access token for connection {self.connection.name}")
            
            response = requests.post(token_url, data=data, headers=headers, timeout=30)
            
            logger.info(f"Token refresh response status: {response.status_code}")
            
            if response.status_code == 400:
                logger.error("Token refresh failed - Bad Request (400)")
                error_content = response.text[:500]
                if "invalid_grant" in error_content or "expired" in error_content.lower():
                    logger.error("Refresh token is invalid or expired - re-authorization required")
                    # Mark connection as needing reauth
                    self.connection.is_configured = False
                    self.connection.last_error = "Refresh token invalid or expired - re-authorization required"
                    self.connection.save()
                    return False
                else:
                    logger.error(f"Bad request content: {error_content}")
                    raise Exception(f"Token refresh bad request: {error_content}")
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed with status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")
            
            token_data = response.json()
            logger.info(f"Token refresh successful, received keys: {list(token_data.keys())}")
            
            if 'error' in token_data:
                logger.error(f"OAuth error in refresh response: {token_data}")
                raise Exception(f"OAuth error: {token_data.get('error')} - {token_data.get('error_description', '')}")
            
            # Update access token
            self.connection.access_token = token_data.get('access_token')
            self.connection.token_expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            
            # Update refresh token if provided (some providers send new refresh tokens)
            if 'refresh_token' in token_data and token_data['refresh_token']:
                self.connection.refresh_token = token_data['refresh_token']
                self.connection.save(update_fields=['access_token', 'token_expires_at', 'refresh_token'])
            else:
                self.connection.save(update_fields=['access_token', 'token_expires_at'])
            
            self.connection.last_test_success = timezone.now()
            self.connection.last_error = ''
            self.connection.save(update_fields=['last_test_success', 'last_error'])
            
            return True
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during token refresh: {str(e)}"
            self.connection.last_error = error_msg
            self.connection.save()
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Token refresh failed: {str(e)}"
            self.connection.last_error = error_msg
            self.connection.save()
            logger.error(error_msg)
            return False
    
    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        # If no access token exists, we can't refresh it
        if not self.connection.access_token:
            return False
            
        # If token needs refresh, try to refresh it
        if self.connection.needs_reauth:
            logger.info(f"Token expired for connection {self.connection.name}, attempting refresh...")
            success = self.refresh_access_token()
            if success:
                logger.info(f"Token successfully refreshed for connection {self.connection.name}")
            else:
                logger.error(f"Token refresh failed for connection {self.connection.name}")
            return success
        return True
    
    def get_account_id(self) -> str:
        """Get the account ID for API calls"""
        # First check if we have cached account ID in the database
        if hasattr(self.connection, 'zoho_account_id') and self.connection.zoho_account_id:
            logger.info(f"Using cached account ID: {self.connection.zoho_account_id}")
            return self.connection.zoho_account_id
        
        try:
            # Try to get account ID from accounts endpoint
            url = f"{self.base_url}accounts"
            headers = self.get_headers()
            
            response = requests.get(url, headers=headers, timeout=10)
            logger.info(f"Accounts response: {response.status_code}")
            logger.info(f"Accounts response content: {response.text[:500]}")
            
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
                            # Try different possible account ID fields
                            account_id = (first_account.get('accountId') or 
                                        first_account.get('id') or 
                                        first_account.get('account_id') or
                                        first_account.get('accountName'))
                            if account_id:
                                logger.info(f"Found account ID: {account_id}")
                                # Cache the account ID
                                self.connection.zoho_account_id = str(account_id)
                                self.connection.save(update_fields=['zoho_account_id'])
                                return str(account_id)
                        
                # Try alternative formats
                if isinstance(data, list) and len(data) > 0:
                    first_item = data[0]
                    account_id = (first_item.get('accountId') or 
                                first_item.get('id') or 
                                first_item.get('account_id') or
                                first_item.get('accountName'))
                    if account_id:
                        logger.info(f"Found account ID (alternative format): {account_id}")
                        self.connection.zoho_account_id = str(account_id)
                        self.connection.save(update_fields=['zoho_account_id'])
                        return str(account_id)
                
                # If we have data but can't find account ID, log the structure
                logger.warning(f"Could not extract account ID from data structure: {data}")
            
            elif response.status_code == 401:
                logger.error("Authentication failed when getting account ID")
                # Try to refresh token once
                if self.refresh_access_token():
                    # Retry with new token
                    headers = self.get_headers()
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, dict) and 'data' in data:
                            accounts = data['data']
                            if isinstance(accounts, list) and len(accounts) > 0:
                                first_account = accounts[0]
                                if isinstance(first_account, dict):
                                    account_id = (first_account.get('accountId') or 
                                                first_account.get('id') or 
                                                first_account.get('account_id') or
                                                first_account.get('accountName'))
                                    if account_id:
                                        self.connection.zoho_account_id = str(account_id)
                                        self.connection.save(update_fields=['zoho_account_id'])
                                        return str(account_id)
            else:
                logger.error(f"Failed to get accounts: {response.status_code} - {response.text[:200]}")
            
            # Fallback: try using email address without domain as account ID
            email_parts = self.connection.email_address.split('@')
            if len(email_parts) > 0:
                fallback_id = email_parts[0]  # Use username part of email
                logger.warning(f"Could not get account ID, using email username as fallback: {fallback_id}")
                return fallback_id
            
            # Final fallback to using full email address
            logger.warning("Could not get account ID, using full email address as fallback")
            return self.connection.email_address
            
        except Exception as e:
            logger.error(f"Error getting account ID: {str(e)}")
            # Fallback to using email address
            return self.connection.email_address
    
    def get_headers(self) -> dict:
        """Get headers for API requests"""
        # Check if we have an access token at all
        if not self.connection.access_token:
            raise Exception("OAuth authentication required. Please complete the authorization process first.")
            
        if not self.ensure_valid_token():
            raise Exception("No valid access token available. Please re-authorize the connection.")
            
        return {
            'Authorization': f'Zoho-oauthtoken {self.connection.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_connection(self) -> dict:
        """Test the connection by trying different API endpoints"""
        try:
            # Check if we have a valid token first
            if not self.connection.access_token:
                return {
                    'success': False,
                    'message': 'OAuth-Autorisierung erforderlich. Bitte autorisieren Sie die Verbindung zuerst.'
                }
                
            # Try to get headers (this will attempt token refresh if needed)
            try:
                headers = self.get_headers()
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Token-Fehler: {str(e)}'
                }
            
            # Try different endpoints to find working one (same as mail_app)
            test_endpoints = [
                "accounts/self",
                "accounts", 
                "folders",
                "me/folders"
            ]
            
            for endpoint in test_endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    logger.info(f"Testing connection with endpoint: {url}")
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    logger.info(f"Response status for {endpoint}: {response.status_code}")
                    logger.info(f"Response content: {response.text[:200]}")
                    
                    if response.status_code == 200:
                        logger.info(f"Connection successful with endpoint: {endpoint}")
                        # Update connection status
                        self.connection.last_test_success = timezone.now()
                        self.connection.last_error = ''
                        self.connection.save()
                        
                        return {
                            'success': True,
                            'message': f'Verbindung erfolgreich getestet (Endpoint: {endpoint})',
                            'data': response.json() if response.content else {}
                        }
                    elif response.status_code == 401:
                        logger.error(f"Authentication failed - invalid token")
                        # Try token refresh once
                        if self.refresh_access_token():
                            logger.info("Token refreshed, retrying connection test...")
                            headers = self.get_headers()
                            response = requests.get(url, headers=headers, timeout=10)
                            if response.status_code == 200:
                                self.connection.last_test_success = timezone.now()
                                self.connection.last_error = ''
                                self.connection.save()
                                return {
                                    'success': True,
                                    'message': f'Verbindung erfolgreich getestet (nach Token-Refresh, Endpoint: {endpoint})',
                                    'data': response.json() if response.content else {}
                                }
                        
                        return {
                            'success': False,
                            'message': 'Authentifizierung fehlgeschlagen - bitte Verbindung neu autorisieren'
                        }
                    else:
                        logger.warning(f"Endpoint {endpoint} failed with status {response.status_code}: {response.text[:200]}")
                        continue
                    
                except Exception as endpoint_error:
                    logger.warning(f"Endpoint {endpoint} failed: {str(endpoint_error)}")
                    continue
            
            # If all endpoints failed
            error_msg = "All test endpoints failed"
            self.connection.last_error = error_msg
            self.connection.save()
            
            return {
                'success': False,
                'message': error_msg
            }
            
        except Exception as e:
            error_msg = f"Connection test failed: {str(e)}"
            self.connection.last_error = error_msg
            self.connection.save()
            logger.error(error_msg)
            
            return {
                'success': False,
                'message': error_msg
            }
    
    def send_email(self, to_email: str, to_name: str, subject: str, 
                   html_content: str, text_content: str = None) -> dict:
        """Send an email through Zoho Mail API"""
        try:
            # Get headers (this will attempt token refresh if needed)
            try:
                headers = self.get_headers()
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Token-Fehler: {str(e)}'
                }
            
            account_id = self.get_account_id()
            
            # Prepare email data according to Zoho API format (like mail_app)
            email_data = {
                'fromAddress': self.connection.email_address,
                'toAddress': f"{to_name} <{to_email}>" if to_name else to_email,
                'subject': subject,
                'content': html_content or text_content or '',
                'mailFormat': 'html' if html_content else 'plaintext'
            }
            
            # Send email using account ID
            url = f"{self.base_url}accounts/{account_id}/messages"
            
            logger.info(f"Sending email to: {to_email}")
            logger.info(f"From: {self.connection.email_address}")
            logger.info(f"Subject: {subject}")
            logger.info(f"URL: {url}")
            
            response = requests.post(url, headers=headers, json=email_data, timeout=30)
            
            logger.info(f"Email send response status: {response.status_code}")
            logger.info(f"Email send response content: {response.text[:500]}")
            
            if response.status_code in [200, 201]:
                logger.info(f"Email sent successfully from {self.connection.email_address}")
                return {
                    'success': True,
                    'message': 'E-Mail erfolgreich gesendet',
                    'data': response.json() if response.content else {}
                }
            elif response.status_code == 401:
                logger.error("Authentication failed - token may be expired")
                # Try to refresh token and retry once
                if self.refresh_access_token():
                    logger.info("Token refreshed, retrying email send...")
                    headers = self.get_headers()
                    response = requests.post(url, headers=headers, json=email_data, timeout=30)
                    if response.status_code in [200, 201]:
                        return {
                            'success': True,
                            'message': 'E-Mail erfolgreich gesendet (nach Token-Refresh)',
                            'data': response.json() if response.content else {}
                        }
                
                return {
                    'success': False,
                    'message': 'Authentifizierung fehlgeschlagen - bitte Verbindung neu autorisieren'
                }
            elif response.status_code == 500:
                error_content = response.text[:500]
                logger.error(f"Server error (500): {error_content}")
                return {
                    'success': False,
                    'message': f'Server-Fehler (500): {error_content}'
                }
            else:
                error_content = response.text[:500]
                logger.error(f"Email send failed: {response.status_code} - {error_content}")
                return {
                    'success': False,
                    'message': f'E-Mail-Versand fehlgeschlagen: {response.status_code} - {error_content}'
                }
            
        except requests.exceptions.Timeout:
            error_msg = "Email sending timeout - Zoho server not responding"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during email sending: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"Email sending failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }


class EmailTemplateService:
    """Service for email template operations"""
    
    @staticmethod
    def render_template(template: EmailTemplate, context_data: dict = None) -> dict:
        """Render an email template with given context data"""
        if context_data is None:
            context_data = {}
        
        try:
            # Create Django template objects
            subject_template = Template(template.subject)
            html_template = Template(template.html_content)
            
            # Create context
            context = Context(context_data)
            
            # Render templates
            rendered_subject = subject_template.render(context)
            rendered_html = html_template.render(context)
            
            rendered_text = None
            if template.text_content:
                text_template = Template(template.text_content)
                rendered_text = text_template.render(context)
            
            return {
                'success': True,
                'subject': rendered_subject,
                'html_content': rendered_html,
                'text_content': rendered_text
            }
            
        except Exception as e:
            logger.error(f"Template rendering failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def send_template_email(template: EmailTemplate, connection: ZohoMailServerConnection,
                           recipient_email: str, recipient_name: str = None,
                           context_data: dict = None, sent_by=None) -> dict:
        """Send an email using a template"""
        
        # WICHTIG: connection parameter wird ignoriert - wir verwenden immer SuperConfig!
        # Create send log entry (ohne connection, da wir SuperConfig verwenden)
        send_log = EmailSendLog.objects.create(
            template=template,
            connection=None,  # Keine direkte Verbindung - verwendet SuperConfig
            recipient_email=recipient_email,
            recipient_name=recipient_name or '',
            subject='',  # Will be updated after rendering
            context_data=context_data or {},
            sent_by=sent_by
        )
        
        try:
            # Render template
            render_result = EmailTemplateService.render_template(template, context_data)
            
            if not render_result['success']:
                send_log.error_message = f"Template rendering failed: {render_result['error']}"
                send_log.save()
                return {
                    'success': False,
                    'message': 'Template-Rendering fehlgeschlagen',
                    'error': render_result['error']
                }
            
            # Update subject in log
            send_log.subject = render_result['subject']
            send_log.save()
            
            # Send email via SuperConfig Email Backend (alle Apps außer mail_app verwenden SuperConfig)
            try:
                from django.core.mail import EmailMultiAlternatives
                from django.conf import settings
                
                # Create email message with SuperConfig AutoFallbackEmailBackend
                msg = EmailMultiAlternatives(
                    subject=render_result['subject'],
                    body=render_result['text_content'],
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient_email]
                )
                
                # Add HTML version if available
                if render_result['html_content']:
                    msg.attach_alternative(render_result['html_content'], "text/html")
                
                # Send via SuperConfig Email Backend (automatisch mit Zoho smtp.zoho.eu)
                msg.send()
                
                send_result = {
                    'success': True,
                    'message': 'Email sent successfully via SuperConfig'
                }
                
                logger.info(f"✅ Email-Templates: Email sent via SuperConfig to {recipient_email} (Template: {template.name})")
                
            except Exception as e:
                send_result = {
                    'success': False,
                    'message': f'SuperConfig email error: {str(e)}'
                }
                logger.error(f"❌ Email-Templates: SuperConfig backend failed: {str(e)}")
            
            if send_result['success']:
                # Update send log
                send_log.is_sent = True
                send_log.sent_at = timezone.now()
                send_log.save()
                
                # Update template usage stats
                template.increment_usage()
                
                return {
                    'success': True,
                    'message': 'E-Mail erfolgreich gesendet',
                    'send_log_id': send_log.id
                }
            else:
                # Update send log with error
                send_log.error_message = send_result['message']
                send_log.save()
                
                return {
                    'success': False,
                    'message': send_result['message'],
                    'send_log_id': send_log.id
                }
                
        except Exception as e:
            error_msg = f"Email sending failed: {str(e)}"
            send_log.error_message = error_msg
            send_log.save()
            logger.error(error_msg)
            
            return {
                'success': False,
                'message': error_msg,
                'send_log_id': send_log.id
            }
    
    @staticmethod
    def get_default_template(template_type: str) -> EmailTemplate:
        """Get the default template for a given type"""
        return EmailTemplate.objects.filter(
            template_type=template_type,
            is_default=True,
            is_active=True
        ).first()
    
    @staticmethod
    def create_template_version(template: EmailTemplate, user, change_description: str = ''):
        """Create a version snapshot of a template"""
        from .models import EmailTemplateVersion
        
        # Get next version number
        last_version = template.versions.order_by('-version_number').first()
        version_number = (last_version.version_number + 1) if last_version else 1
        
        # Create version
        EmailTemplateVersion.objects.create(
            template=template,
            version_number=version_number,
            subject=template.subject,
            html_content=template.html_content,
            text_content=template.text_content,
            custom_css=template.custom_css,
            change_description=change_description,
            created_by=user
        )
    
    @staticmethod
    def validate_template_variables(template_content: str, available_variables: list) -> dict:
        """Validate that template variables are properly defined"""
        import re
        
        # Find all template variables in content
        variable_pattern = r'\{\{\s*(\w+)\s*\}\}'
        found_variables = set(re.findall(variable_pattern, template_content))
        
        # Check for undefined variables
        undefined_variables = found_variables - set(available_variables)
        
        return {
            'valid': len(undefined_variables) == 0,
            'found_variables': list(found_variables),
            'undefined_variables': list(undefined_variables)
        }


class EmailNotificationService:
    """Service for sending automated email notifications"""
    
    @staticmethod
    def send_order_confirmation(order_data: dict, recipient_email: str, recipient_name: str = None):
        """Send order confirmation email"""
        template = EmailTemplateService.get_default_template('order_confirmation')
        if not template:
            logger.warning("No default order confirmation template found")
            return False
        
        # Get default connection
        connection = ZohoMailServerConnection.objects.filter(
            is_active=True, 
            is_configured=True
        ).first()
        
        if not connection:
            logger.warning("No active Zoho connection found")
            return False
        
        result = EmailTemplateService.send_template_email(
            template=template,
            connection=connection,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            context_data=order_data
        )
        
        return result['success']
    
    @staticmethod
    def send_welcome_email(user_data: dict, recipient_email: str, recipient_name: str = None):
        """Send welcome email"""
        template = EmailTemplateService.get_default_template('welcome')
        if not template:
            logger.warning("No default welcome template found")
            return False
        
        # Get default connection
        connection = ZohoMailServerConnection.objects.filter(
            is_active=True, 
            is_configured=True
        ).first()
        
        if not connection:
            logger.warning("No active Zoho connection found")
            return False
        
        result = EmailTemplateService.send_template_email(
            template=template,
            connection=connection,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            context_data=user_data
        )
        
        return result['success']