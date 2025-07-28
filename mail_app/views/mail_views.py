"""
Class-based views for Mail App
"""
import logging
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ..base_views import BaseMailView, prepare_folders_with_icons
from ..models import Email, Folder, Ticket
from ..constants import DEFAULT_EMAIL_LIMIT
from ..error_handlers import (
    MailAppError, ErrorResponseBuilder, ErrorLogger, 
    validation_error, permission_denied, external_api_error
)
from ..logging_config import get_mail_logger, get_performance_logger, get_audit_logger

logger = get_mail_logger('mail_app.views')
audit_logger = get_audit_logger()


class MailModernView(BaseMailView):
    """
    Modern three-column mail interface.
    """
    template_name = 'mail_app/mail_modern.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all folders for sidebar
        folders = self.account.folders.all().order_by('name')
        folders = prepare_folders_with_icons(folders)
        
        # Get current folder from request
        folder_id = self.request.GET.get('folder')
        if folder_id:
            current_folder = get_object_or_404(Folder, id=folder_id, account=self.account)
        else:
            # Default to inbox
            current_folder = folders.filter(folder_type='inbox').first()
            if not current_folder:
                current_folder = folders.first()
        
        # Get emails from current folder
        emails = Email.objects.filter(
            account=self.account,
            folder=current_folder
        ).order_by('-sent_at')
        
        # Pagination
        paginator = Paginator(emails, 50)
        page_number = self.request.GET.get('page', 1)
        email_page = paginator.get_page(page_number)
        
        # Get current email if specified
        email_id = self.request.GET.get('email')
        current_email = None
        if email_id:
            current_email = get_object_or_404(Email, id=email_id, account=self.account)
            # Mark as read
            if not current_email.is_read:
                current_email.mark_as_read()
        
        context.update({
            'folders': folders,
            'current_folder': current_folder,
            'emails': email_page,
            'current_email': current_email,
        })
        
        return context


class MailSimpleView(BaseMailView):
    """
    Simple three-column mail interface.
    """
    template_name = 'mail_app/mail_simple.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all folders for sidebar
        folders = self.account.folders.all().order_by('name')
        folders = prepare_folders_with_icons(folders)
        
        # Get current folder from request
        folder_id = self.request.GET.get('folder')
        if folder_id:
            current_folder = get_object_or_404(Folder, id=folder_id, account=self.account)
        else:
            # Default to inbox
            current_folder = folders.filter(folder_type='inbox').first()
            if not current_folder:
                current_folder = folders.first()
        
        # Get emails from current folder
        emails = Email.objects.filter(
            account=self.account,
            folder=current_folder
        ).order_by('-sent_at')
        
        # Pagination
        paginator = Paginator(emails, DEFAULT_EMAIL_LIMIT)
        page_number = self.request.GET.get('page', 1)
        email_page = paginator.get_page(page_number)
        
        # Get current email if specified
        email_id = self.request.GET.get('email')
        current_email = None
        if email_id:
            current_email = get_object_or_404(Email, id=email_id, account=self.account)
            # Mark as read
            if not current_email.is_read:
                current_email.mark_as_read()
        
        context.update({
            'folders': folders,
            'current_folder': current_folder,
            'emails': email_page,
            'current_email': current_email,
        })
        
        return context


class MailStandaloneView(BaseMailView):
    """
    Standalone mail interface with custom header and design.
    """
    template_name = 'mail_app/mail_standalone.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all folders for sidebar
        folders = self.account.folders.all().order_by('name')
        folders = prepare_folders_with_icons(folders)
        
        # Get current folder from request
        folder_id = self.request.GET.get('folder')
        if folder_id:
            current_folder = get_object_or_404(Folder, id=folder_id, account=self.account)
        else:
            # Default to inbox
            current_folder = folders.filter(folder_type='inbox').first()
            if not current_folder:
                current_folder = folders.first()
        
        # Get emails from current folder (last 90 days)
        from datetime import timedelta
        from django.utils import timezone
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        emails = Email.objects.filter(
            account=self.account,
            folder=current_folder,
            sent_at__gte=ninety_days_ago
        ).order_by('-sent_at')[:1000]  # Show up to 1000 recent emails
        
        # Get current email if specified
        email_id = self.request.GET.get('email')
        current_email = None
        if email_id:
            current_email = get_object_or_404(Email, id=email_id, account=self.account)
            # Mark as read
            if not current_email.is_read:
                current_email.mark_as_read()
        
        context.update({
            'folders': folders,
            'current_folder': current_folder,
            'emails': emails,
            'current_email': current_email,
        })
        
        return context


class MailTicketsView(BaseMailView):
    """
    Ticket-System für offene Email-Anfragen.
    """
    template_name = 'mail_app/mail_tickets.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all open tickets for this account
        tickets = Ticket.objects.filter(
            account=self.account,
            status='open'
        ).order_by('-last_email_at')
        
        # Add email count to each ticket
        for ticket in tickets:
            ticket.email_count = ticket.emails.filter(is_open=True).count()
        
        # Get current ticket from request
        ticket_id = self.request.GET.get('ticket')
        current_ticket = None
        current_email = None
        
        if ticket_id:
            current_ticket = get_object_or_404(Ticket, id=ticket_id, account=self.account)
            
            # Get current email if specified, otherwise select the most recent one
            email_id = self.request.GET.get('email')
            if email_id:
                current_email = get_object_or_404(
                    Email, 
                    id=email_id, 
                    account=self.account, 
                    ticket=current_ticket
                )
            else:
                # Get the most recent email in the ticket
                current_email = current_ticket.emails.filter(is_open=True).order_by('-sent_at').first()
            
            # Mark current email as read
            if current_email and not current_email.is_read:
                current_email.mark_as_read()
        
        context.update({
            'tickets': tickets,
            'current_ticket': current_ticket,
            'current_email': current_email,
        })
        
        return context


@method_decorator(require_http_methods(["POST"]), name='dispatch')
class ToggleEmailStatusView(BaseMailView):
    """
    Toggle email open status via AJAX.
    """
    
    def post(self, request, email_id):
        """Handle POST request to toggle email status."""
        try:
            email = get_object_or_404(Email, id=email_id, account=self.account)
            
            # Get grouping mode from request (default to 'subject')
            grouping_mode = request.POST.get('grouping_mode', 'subject')
            
            # Check if this is a mark-as-open-only request
            mark_as_open_only = request.POST.get('mark_as_open_only', 'false').lower() == 'true'
            
            logger.info(f"Before toggle: Email {email_id} is_open={email.is_open}, "
                       f"grouping_mode={grouping_mode}, mark_as_open_only={mark_as_open_only}")
            
            # Handle the open status change
            if mark_as_open_only and email.is_open:
                # Email is already open and we only allow marking as open - no change
                logger.info(f"Email {email_id} already open, no change allowed")
                return JsonResponse({
                    'success': True,
                    'is_open': email.is_open,
                    'auto_grouped_count': 0,
                    'message': 'Email is already marked as open'
                })
            elif mark_as_open_only:
                # Mark as open only
                email.is_open = True
                email.save(update_fields=['is_open'])
            else:
                # Normal toggle behavior (for tickets page)
                email.is_open = not email.is_open
                email.save(update_fields=['is_open'])
            
            logger.info(f"After toggle: Email {email_id} is_open={email.is_open}")
            
            auto_grouped_count = 0
            
            if email.is_open:
                # Email marked as open - create or update ticket with auto-grouping
                logger.info(f"Creating ticket for email {email_id} from {email.from_email}")
                ticket = Ticket.create_or_update_for_email(
                    email, 
                    grouping_mode=grouping_mode, 
                    auto_group_related=True
                )
                
                if ticket:
                    # Count related emails that were auto-grouped
                    auto_grouped_count = ticket.emails.filter(is_open=True).count() - 1  # Minus the trigger email
                    logger.info(f"Email {email_id} marked as open, ticket: {ticket.id}, "
                               f"auto-grouped: {auto_grouped_count} emails")
            else:
                # Email marked as closed - remove from ticket
                if email.ticket:
                    ticket = email.ticket
                    email.ticket = None
                    email.save(update_fields=['ticket'])
                    
                    # Update ticket stats (may close ticket if no open emails left)
                    ticket.update_ticket_stats()
                    logger.info(f"Email {email_id} marked as closed, removed from ticket {ticket.id}")
            
            return JsonResponse({
                'success': True,
                'is_open': email.is_open,
                'auto_grouped_count': auto_grouped_count,
                'grouping_mode': grouping_mode,
                'ticket_id': email.ticket.id if email.ticket else None
            })
            
        except Exception as e:
            logger.error(f"Error toggling email {email_id} status: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(require_http_methods(["POST"]), name='dispatch')
class CloseTicketView(BaseMailView):
    """
    Close a ticket and mark all associated emails as not open.
    """
    
    def post(self, request, ticket_id):
        """Handle POST request to close ticket."""
        try:
            ticket = get_object_or_404(Ticket, id=ticket_id, account=self.account)
            
            # Close the ticket (this also updates all associated emails)
            ticket.close_ticket()
            
            logger.info(f"Ticket {ticket_id} closed by user {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'message': 'Ticket erfolgreich geschlossen'
            })
            
        except Exception as e:
            logger.error(f"Error closing ticket {ticket_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class EmailContentAPIView(BaseMailView):
    """
    API endpoint to get email content as HTML for AJAX loading.
    """
    
    def get(self, request, email_id):
        """Handle GET request for email content."""
        with get_performance_logger(f"get_email_content_{email_id}"):
            try:
                # Validate email_id
                if not email_id or not str(email_id).isdigit():
                    raise validation_error("Invalid email ID", "email_id")
                
                email = get_object_or_404(Email, id=email_id, account=self.account)
                
                # Log email access for audit
                audit_logger.log_email_access(request.user, email_id, 'view')
                
                # Mark email as read
                if not email.is_read:
                    email.mark_as_read()
                
                # Get sync options from request
                use_background = request.GET.get('background', 'false').lower() == 'true'
                folder_id = request.GET.get('folder_id')
                limit = int(request.GET.get('limit', 1000))
                
                # If sync is requested, trigger sync
                if use_background and folder_id:
                    try:
                        from ..tasks import sync_single_account
                        task = sync_single_account.delay(self.account.id, folder_id, limit)
                        return JsonResponse({
                            'task_id': task.id,
                            'status': 'started',
                            'message': 'Background sync started'
                        })
                    except Exception as e:
                        logger.warning(f"Celery not available, falling back to synchronous sync: {e}")
                        # Fall back to synchronous operation
                        use_background = False
                
                # Render email content
                html_content = render_to_string('mail_app/partials/email_viewer_standalone.html', {
                    'current_email': email,
                    'account': self.account
                }, request=request)
                
                return JsonResponse({
                    'success': True,
                    'html': html_content,
                    'email_id': email.id,
                    'subject': email.subject,
                    'is_read': email.is_read
                })
                
            except MailAppError as e:
                # Handle our custom errors
                ErrorLogger.log_error(e, request)
                return ErrorResponseBuilder.build_response(e, request)
                
            except Exception as e:
                # Handle unexpected errors
                mail_error = MailAppError(
                    f"Error getting email content for {email_id}: {str(e)}",
                    details=str(e),
                    user_message="Fehler beim Laden der Email. Bitte versuchen Sie es erneut."
                )
                ErrorLogger.log_error(mail_error, request)
                return ErrorResponseBuilder.build_response(mail_error, request)