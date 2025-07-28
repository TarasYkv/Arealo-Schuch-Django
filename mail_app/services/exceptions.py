"""
Custom exceptions for Mail App services
"""


class TokenRefreshError(Exception):
    """Custom exception for token refresh failures."""
    pass


class ReAuthorizationRequiredError(Exception):
    """Custom exception when re-authorization is required."""
    pass


class EmailSyncError(Exception):
    """Custom exception for email synchronization errors."""
    pass


class ZohoAPIError(Exception):
    """Custom exception for Zoho API errors."""
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class EmailNotFoundError(Exception):
    """Exception raised when an email is not found."""
    pass


class FolderNotFoundError(Exception):
    """Exception raised when a folder is not found."""
    pass


class InvalidConfigurationError(Exception):
    """Exception raised when configuration is invalid."""
    pass


class RateLimitExceededError(ZohoAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass


class AuthenticationError(ZohoAPIError):
    """Exception raised when authentication fails."""
    pass