"""
Base views and mixins for Mail App
"""
import logging
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class MailAppAccessMixin:
    """
    Mixin to check mail app access permissions
    """
    def check_mail_access(self, request):
        """Check if user has access to mail app"""
        from accounts.models import AppPermission
        if not AppPermission.user_has_access('mail', request.user):
            messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
            return False
        return True
    
    def get_user_account(self, request):
        """Get user's active email account"""
        account = request.user.email_accounts.filter(is_active=True).first()
        if not account:
            messages.info(request, 'Bitte verbinden Sie zuerst einen Email-Account.')
            return None
        return account


@method_decorator(login_required, name='dispatch')
class BaseMailView(TemplateView, MailAppAccessMixin):
    """
    Base view for all mail interface views
    """
    def dispatch(self, request, *args, **kwargs):
        # Check app permission
        if not self.check_mail_access(request):
            return redirect('accounts:dashboard')
        
        # Get user account
        account = self.get_user_account(request)
        if not account and self.requires_account:
            return redirect('mail_app:dashboard')
        
        self.account = account
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = getattr(self, 'account', None)
        return context
    
    # Override in subclasses if account is not required
    requires_account = True


def mail_access_required(view_func):
    """
    Decorator for function-based views to check mail app access
    """
    @login_required
    def wrapper(request, *args, **kwargs):
        from accounts.models import AppPermission
        if not AppPermission.user_has_access('mail', request.user):
            messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
            return redirect('accounts:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_folder_icons():
    """
    Get standard folder icons mapping
    """
    return {
        'inbox': '📥',
        'sent': '📤', 
        'drafts': '📝',
        'trash': '🗑️',
        'spam': '🚫',
        'custom': '📁'
    }


def prepare_folders_with_icons(folders):
    """
    Folders already have icons via the icon property, just return them
    """
    return folders