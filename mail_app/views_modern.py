"""
Modern Mail Interface Views
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string

from .models import EmailAccount, Email, Folder, Ticket

logger = logging.getLogger(__name__)


@login_required
def mail_modern(request):
    """
    Modern three-column mail interface.
    """
    # Check app permission
    from accounts.models import AppPermission
    if not AppPermission.user_has_access('mail', request.user):
        messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
        return redirect('accounts:dashboard')
    
    # Get active account (for now, just the first one)
    account = request.user.email_accounts.filter(is_active=True).first()
    if not account:
        messages.info(request, 'Bitte verbinden Sie zuerst einen Email-Account.')
        return redirect('mail_app:dashboard')
    
    # Get all folders for sidebar
    folders = account.folders.all().order_by('name')
    
    # Add icons to folders based on type
    folder_icons = {
        'inbox': '📥',
        'sent': '📤',
        'drafts': '📝',
        'trash': '🗑️',
        'spam': '🚫',
        'custom': '📁'
    }
    
    for folder in folders:
        folder.icon = folder_icons.get(folder.folder_type, '📁')
    
    # Get current folder from request
    folder_id = request.GET.get('folder')
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, account=account)
    else:
        # Default to inbox
        current_folder = folders.filter(folder_type='inbox').first()
        if not current_folder:
            current_folder = folders.first()
    
    # Get emails from current folder
    emails = Email.objects.filter(
        account=account,
        folder=current_folder
    ).order_by('-sent_at')
    
    # Pagination
    paginator = Paginator(emails, 50)  # 50 emails per page
    page_number = request.GET.get('page', 1)
    email_page = paginator.get_page(page_number)
    
    # Get current email if specified
    email_id = request.GET.get('email')
    current_email = None
    if email_id:
        current_email = get_object_or_404(Email, id=email_id, account=account)
        # Mark as read
        if not current_email.is_read:
            current_email.mark_as_read()
    
    context = {
        'account': account,
        'folders': folders,
        'current_folder': current_folder,
        'emails': email_page,
        'current_email': current_email,
    }
    
    return render(request, 'mail_app/mail_modern.html', context)


@login_required
def mail_simple(request):
    """
    Simple three-column mail interface that definitely works.
    """
    # Check app permission
    from accounts.models import AppPermission
    if not AppPermission.user_has_access('mail', request.user):
        messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
        return redirect('accounts:dashboard')
    
    # Get active account (for now, just the first one)
    account = request.user.email_accounts.filter(is_active=True).first()
    if not account:
        messages.info(request, 'Bitte verbinden Sie zuerst einen Email-Account.')
        return redirect('mail_app:dashboard')
    
    # Get all folders for sidebar
    folders = account.folders.all().order_by('name')
    
    # Add icons to folders based on type
    folder_icons = {
        'inbox': '📥',
        'sent': '📤',
        'drafts': '📝',
        'trash': '🗑️',
        'spam': '🚫',
        'custom': '📁'
    }
    
    for folder in folders:
        folder.icon = folder_icons.get(folder.folder_type, '📁')
    
    # Get current folder from request
    folder_id = request.GET.get('folder')
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, account=account)
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
        account=account,
        folder=current_folder,
        sent_at__gte=ninety_days_ago
    ).order_by('-sent_at')[:1000]  # Show up to 1000 recent emails
    
    # Get current email if specified
    email_id = request.GET.get('email')
    current_email = None
    if email_id:
        current_email = get_object_or_404(Email, id=email_id, account=account)
        # Mark as read
        if not current_email.is_read:
            current_email.mark_as_read()
    
    context = {
        'account': account,
        'folders': folders,
        'current_folder': current_folder,
        'emails': emails,
        'current_email': current_email,
    }
    
    return render(request, 'mail_app/mail_simple.html', context)


@login_required
def mail_standalone(request):
    """
    Standalone mail interface with custom header and design.
    """
    # Check app permission
    from accounts.models import AppPermission
    if not AppPermission.user_has_access('mail', request.user):
        messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
        return redirect('accounts:dashboard')
    
    # Get active account (for now, just the first one)
    account = request.user.email_accounts.filter(is_active=True).first()
    if not account:
        messages.info(request, 'Bitte verbinden Sie zuerst einen Email-Account.')
        return redirect('mail_app:dashboard')
    
    # Get all folders for sidebar
    folders = account.folders.all().order_by('name')
    
    # Add icons to folders based on type
    folder_icons = {
        'inbox': '📥',
        'sent': '📤',
        'drafts': '📝',
        'trash': '🗑️',
        'spam': '🚫',
        'custom': '📁'
    }
    
    for folder in folders:
        folder.icon = folder_icons.get(folder.folder_type, '📁')
    
    # Get current folder from request
    folder_id = request.GET.get('folder')
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, account=account)
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
        account=account,
        folder=current_folder,
        sent_at__gte=ninety_days_ago
    ).order_by('-sent_at')[:1000]  # Show up to 1000 recent emails
    
    # Get current email if specified
    email_id = request.GET.get('email')
    current_email = None
    if email_id:
        current_email = get_object_or_404(Email, id=email_id, account=account)
        # Mark as read
        if not current_email.is_read:
            current_email.mark_as_read()
    
    context = {
        'account': account,
        'folders': folders,
        'current_folder': current_folder,
        'emails': emails,
        'current_email': current_email,
    }
    
    return render(request, 'mail_app/mail_standalone.html', context)


@login_required
def mail_tickets(request):
    """
    Ticket-System für offene Email-Anfragen.
    """
    # Check app permission
    from accounts.models import AppPermission
    if not AppPermission.user_has_access('mail', request.user):
        messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
        return redirect('accounts:dashboard')
    
    # Get active account (for now, just the first one)
    account = request.user.email_accounts.filter(is_active=True).first()
    if not account:
        messages.info(request, 'Bitte verbinden Sie zuerst einen Email-Account.')
        return redirect('mail_app:dashboard')
    
    # Get all open tickets for this account
    tickets = Ticket.objects.filter(
        account=account,
        status='open'
    ).order_by('-last_email_at')
    
    # Add email count to each ticket
    for ticket in tickets:
        ticket.email_count = ticket.emails.filter(is_open=True).count()
    
    # Get current ticket from request
    ticket_id = request.GET.get('ticket')
    current_ticket = None
    current_email = None
    
    if ticket_id:
        current_ticket = get_object_or_404(Ticket, id=ticket_id, account=account)
        
        # Get current email if specified, otherwise select the most recent one
        email_id = request.GET.get('email')
        if email_id:
            current_email = get_object_or_404(
                Email, 
                id=email_id, 
                account=account, 
                ticket=current_ticket
            )
        else:
            # Auto-select the most recent email in the thread
            current_email = current_ticket.emails.filter(
                is_open=True
            ).order_by('-sent_at').first()
    
    context = {
        'account': account,
        'view_mode': 'tickets',
        'tickets': tickets,
        'current_ticket': current_ticket,
        'current_email': current_email,
    }
    
    return render(request, 'mail_app/mail_tickets.html', context)


@login_required
@require_http_methods(["POST"])
def delete_email(request, email_id):
    """
    Delete an email (move to trash or permanently delete).
    """
    email = get_object_or_404(Email, id=email_id, account__user=request.user)
    
    # For now, just delete it
    # TODO: In Phase 2, move to trash instead
    email.delete()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def toggle_email_open(request, email_id):
    """
    Toggle the open status of an email and manage tickets with grouping options.
    """
    try:
        email = get_object_or_404(Email, id=email_id, account__user=request.user)
        
        # Get grouping mode from request (default to 'email')
        grouping_mode = request.POST.get('grouping_mode', 'email')
        if grouping_mode not in ['email', 'email_subject']:
            grouping_mode = 'email'
        
        logger.info(f"Before toggle: Email {email_id} is_open={email.is_open}, grouping_mode={grouping_mode}")
        
        # Toggle the open status
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
                logger.info(f"Email {email_id} marked as open, ticket: {ticket.id}, auto-grouped: {auto_grouped_count} emails")
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
        logger.error(f"Error toggling email {email_id} status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def close_ticket(request, ticket_id):
    """
    Close a ticket and mark all associated emails as not open.
    """
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id, account__user=request.user)
        
        # Close the ticket (this also updates all associated emails)
        ticket.close_ticket()
        
        logger.info(f"Ticket {ticket_id} closed by user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': 'Ticket erfolgreich geschlossen'
        })
        
    except Exception as e:
        logger.error(f"Error closing ticket {ticket_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_email_html(request, email_id):
    """
    API endpoint to get email content as HTML for AJAX loading.
    """
    try:
        email = get_object_or_404(Email, id=email_id, account__user=request.user)
        
        # Mark as read
        email.mark_as_read()
        
        # Render email content to HTML
        html_content = render_to_string('mail_app/partials/email_viewer.html', {
            'current_email': email,
            'user': request.user,
        })
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'email_id': email.id,
        })
        
    except Exception as e:
        logger.error(f"Error loading email HTML {email_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_ticket_emails(request, ticket_id):
    """
    API endpoint to get emails for a specific ticket.
    """
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id, account__user=request.user)
        
        # Get emails in the ticket ordered by sent_at
        emails = ticket.emails.all().order_by('sent_at')
        
        # Get current email from URL parameter if present
        current_email_id = request.GET.get('email')
        current_email = None
        if current_email_id:
            try:
                current_email = emails.get(id=current_email_id)
            except Email.DoesNotExist:
                pass
        
        # Render email list to HTML
        html_content = render_to_string('mail_app/partials/ticket_email_list.html', {
            'current_ticket': ticket,
            'current_email': current_email,
            'account': ticket.account,
        })
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'ticket_id': ticket.id,
            'email_count': emails.count(),
        })
        
    except Exception as e:
        logger.error(f"Error loading ticket emails {ticket_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)