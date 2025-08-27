"""
Zoho OAuth2 Integration for Email Service
"""
import requests
import base64
import json
from urllib.parse import urlencode
from django.conf import settings
from django.urls import reverse
from .models import EmailConfiguration


class ZohoOAuthHandler:
    """Handle Zoho OAuth2 authentication for email sending"""
    
    def __init__(self):
        self.base_url = "https://accounts.zoho.eu"  # or .com for US
        self.scope = "ZohoMail.send.ALL"
        
    def get_redirect_uri(self, request):
        """Generate the correct redirect URI"""
        return request.build_absolute_uri(reverse('superconfig:zoho_oauth_callback'))
    
    def get_authorization_url(self, request, client_id):
        """Get Zoho authorization URL"""
        redirect_uri = self.get_redirect_uri(request)
        
        params = {
            'scope': self.scope,
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        return f"{self.base_url}/oauth/v2/auth?" + urlencode(params)
    
    def exchange_code_for_tokens(self, code, client_id, client_secret, redirect_uri):
        """Exchange authorization code for access and refresh tokens"""
        token_url = f"{self.base_url}/oauth/v2/token"
        
        data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {'error': str(e)}
    
    def refresh_access_token(self, refresh_token, client_id, client_secret):
        """Refresh access token using refresh token"""
        token_url = f"{self.base_url}/oauth/v2/token"
        
        data = {
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token'
        }
        
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {'error': str(e)}
    
    def send_email_via_api(self, access_token, from_email, to_emails, subject, body):
        """Send email using Zoho Mail API instead of SMTP"""
        api_url = "https://mail.zoho.eu/api/accounts/me/messages"  # or .com for US
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Prepare recipients
        to_list = [{'email': email} for email in to_emails] if isinstance(to_emails, list) else [{'email': to_emails}]
        
        data = {
            'fromAddress': from_email,
            'toAddress': to_list,
            'subject': subject,
            'content': body,
            'mailFormat': 'html' if '<' in body else 'plaintext'
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=data)
            response.raise_for_status()
            return {'success': True, 'data': response.json()}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def validate_smtp_vs_api(self, email_config):
        """Determine if we should use SMTP or API based on configuration"""
        has_oauth_credentials = bool(
            email_config.zoho_client_id and 
            email_config.zoho_client_secret
        )
        
        has_smtp_credentials = bool(email_config.email_host_password)
        
        if has_oauth_credentials:
            return 'api', 'Zoho OAuth2 credentials found - using API'
        elif has_smtp_credentials:
            return 'smtp', 'SMTP password found - using SMTP'
        else:
            return 'none', 'No credentials configured - please setup OAuth2 or SMTP password'


def setup_zoho_oauth_configuration():
    """Helper function to setup Zoho OAuth2 configuration"""
    instructions = """
    🔧 Zoho OAuth2 Setup Instructions:
    
    1. Go to https://api-console.zoho.eu/
    2. Create a new "Server-based Applications" client
    3. Set Redirect URI to: {your_domain}/superconfig/zoho/callback/
    4. Add these scopes: ZohoMail.send.ALL
    5. Copy Client ID and Client Secret to SuperConfig
    
    📋 Required Information:
    - Client ID (from Zoho Console)
    - Client Secret (from Zoho Console) 
    - Redirect URI: Must match exactly in Zoho Console
    
    💡 Why OAuth2 instead of SMTP?
    - More reliable than SMTP (no DNS issues)
    - Better security (tokens vs passwords)
    - Higher sending limits
    - Real-time delivery status
    """
    return instructions