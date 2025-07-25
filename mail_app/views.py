"""
Mail App Views - OAuth2 Authentication and API Endpoints
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import json

from .models import EmailAccount, Email, Folder, EmailDraft, EmailThread
from .services import ZohoOAuthService, ZohoMailAPIService, EmailSyncService, ReAuthorizationRequiredError

logger = logging.getLogger(__name__)


@login_required
def mail_dashboard(request):
    """
    Main mail dashboard view.
    """
    # Check app permission
    from accounts.models import AppPermission
    if not AppPermission.user_has_access('mail', request.user):
        from django.contrib import messages
        messages.error(request, 'Sie haben keine Berechtigung für die Email-App.')
        return redirect('accounts:dashboard')
    
    user_accounts = request.user.email_accounts.filter(is_active=True)
    needs_reauth_accounts = []
    
    # Check account status and update email addresses if needed
    if user_accounts.exists():
        for account in user_accounts:
            try:
                # Only try to update if email_address still looks like array data
                if '[{' in str(account.email_address):
                    try:
                        # Get fresh account info from Zoho API
                        api_service = ZohoMailAPIService(account)
                        account_info = api_service.get_account_info()
                        
                        if account_info and 'data' in account_info:
                            accounts_data = account_info['data']
                            
                            if isinstance(accounts_data, list) and len(accounts_data) > 0:
                                # Find primary email from the list
                                primary_account = None
                                for acc in accounts_data:
                                    if isinstance(acc, dict) and acc.get('isPrimary', False):
                                        primary_account = acc
                                        break
                                
                                # If no primary found, use first one
                                if not primary_account and accounts_data:
                                    primary_account = accounts_data[0]
                                
                                if primary_account:
                                    new_email = primary_account.get('mailId')  # Zoho uses 'mailId' not 'emailAddress'
                                    
                                    if new_email:
                                        account.email_address = new_email
                                        account.display_name = new_email
                                        account.save(update_fields=['email_address', 'display_name'])
                                        logger.info(f"Updated email account to: {new_email}")
                                        
                            elif isinstance(accounts_data, dict):
                                new_email = accounts_data.get('mailId')
                                if not new_email:
                                    new_email = accounts_data.get('emailAddress')
                                
                                if new_email:
                                    account.email_address = new_email
                                    account.display_name = new_email
                                    account.save(update_fields=['email_address', 'display_name'])
                                    logger.info(f"Updated email account to: {new_email}")
                                    
                    except ReAuthorizationRequiredError:
                        logger.warning(f"Re-authorization required for account {account.email_address}")
                        needs_reauth_accounts.append(account)
                    except Exception as e:
                        logger.warning(f"Failed to update email address automatically: {str(e)}")
                        pass  # Continue without updating
                        
            except Exception as e:
                logger.warning(f"Could not update email address for account {account.id}: {str(e)}")
                continue
    
    # Get ticket statistics
    total_open_tickets = 0
    if user_accounts.exists():
        from .models import Ticket
        for account in user_accounts:
            total_open_tickets += Ticket.objects.filter(
                account=account,
                status='open'
            ).count()
    
    context = {
        'accounts': user_accounts,
        'has_accounts': user_accounts.exists(),
        'zoho_auth_url': None,
        'needs_reauth': bool(needs_reauth_accounts),
        'total_open_tickets': total_open_tickets,
    }
    
    # If no accounts or re-authorization needed, provide OAuth URL
    if not user_accounts.exists() or needs_reauth_accounts:
        try:
            oauth_service = ZohoOAuthService(user=request.user)
            context['zoho_auth_url'] = oauth_service.get_authorization_url(
                state=f"user_{request.user.id}"
            )
            
            # Add message for re-authorization
            if needs_reauth_accounts:
                messages.warning(
                    request, 
                    'Ihre Email-Berechtigung ist abgelaufen. Bitte verbinden Sie Ihr Email-Konto erneut.'
                )
        except Exception as e:
            logger.error(f"Error generating OAuth URL: {str(e)}")
            messages.error(request, 'Fehler beim Generieren der Autorisierungs-URL.')
    
    return render(request, 'mail_app/dashboard.html', context)


@login_required
def oauth_authorize(request):
    """
    Initiate OAuth2 authorization with Zoho.
    """
    try:
        oauth_service = ZohoOAuthService(user=request.user)
        authorization_url = oauth_service.get_authorization_url(
            state=f"user_{request.user.id}"
        )
        return redirect(authorization_url)
        
    except Exception as e:
        logger.error(f"OAuth authorization error for user {request.user.id}: {str(e)}")
        messages.error(request, "Error initiating email authorization. Please try again.")
        return redirect('mail_app:dashboard')


@login_required
def oauth_callback(request):
    """
    Handle OAuth2 callback from Zoho.
    """
    try:
        # Get authorization code from callback
        authorization_code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            logger.error(f"OAuth callback error: {error}")
            messages.error(request, f"Authorization failed: {error}")
            return redirect('mail_app:dashboard')
        
        if not authorization_code:
            messages.error(request, "No authorization code received.")
            return redirect('mail_app:dashboard')
        
        # Verify state parameter
        expected_state = f"user_{request.user.id}"
        if state != expected_state:
            logger.warning(f"State mismatch: expected {expected_state}, got {state}")
            messages.error(request, "Invalid authorization state.")
            return redirect('mail_app:dashboard')
        
        # Exchange code for tokens
        oauth_service = ZohoOAuthService(user=request.user)
        token_data = oauth_service.exchange_code_for_tokens(authorization_code)
        
        # Update user's ZohoAPISettings with OAuth tokens
        try:
            from accounts.models import ZohoAPISettings
            zoho_settings, created = ZohoAPISettings.objects.get_or_create(user=request.user)
            zoho_settings.access_token = token_data['access_token']
            zoho_settings.refresh_token = token_data['refresh_token']
            zoho_settings.token_expires_at = token_data['expires_at']
            zoho_settings.is_active = True
            zoho_settings.save()
            logger.info(f"Updated ZohoAPISettings for user {request.user.username}")
        except Exception as e:
            logger.error(f"Failed to update ZohoAPISettings: {str(e)}")
        
        # Test the API connection to get user info
        temp_account = EmailAccount(
            user=request.user,
            access_token=token_data['access_token'],
            token_expires_at=token_data['expires_at']
        )
        
        # Get account info to determine the actual email address
        api_service = ZohoMailAPIService(temp_account)
        account_info = api_service.get_account_info()
        
        # Extract email address from account info
        email_address = 'kontakt@workloom.de'  # Default fallback
        display_name = 'Zoho Mail Account'  # Default display name
        
        if account_info and 'data' in account_info:
            # Try to get the primary email address from the account data
            accounts_data = account_info['data']
            if isinstance(accounts_data, list) and len(accounts_data) > 0:
                # Find primary email from the list
                primary_account = None
                for acc in accounts_data:
                    if isinstance(acc, dict) and acc.get('isPrimary', False):
                        primary_account = acc
                        break
                
                # If no primary found, use first one
                if not primary_account:
                    primary_account = accounts_data[0]
                
                if primary_account:
                    email_address = primary_account.get('mailId', email_address)  # Zoho uses 'mailId'
                    display_name = email_address  # Use email as display name
                    logger.info(f"Using Zoho account email: {email_address}")
                    
            elif isinstance(accounts_data, dict):
                email_address = accounts_data.get('mailId', email_address)  # Try mailId first
                if not email_address or email_address == 'kontakt@workloom.de':
                    email_address = accounts_data.get('emailAddress', email_address)  # Fallback
                display_name = email_address
                logger.info(f"Using Zoho account email: {email_address}")
        else:
            logger.warning("Could not retrieve account info, using default email address")
            # Test connection with the fallback
            connection_ok = api_service.test_connection()
            if not connection_ok:
                logger.warning("API connection test failed with fallback settings")
        
        # Look for existing email account for this user, or create new one
        try:
            # First, try to find an account with the same email address for this user
            existing_account = EmailAccount.objects.filter(
                user=request.user, 
                email_address=email_address
            ).first()
            
            if existing_account:
                # Update the existing account with the same email (reactivate if it was disconnected)
                existing_account.display_name = display_name
                existing_account.access_token = token_data['access_token']
                existing_account.refresh_token = token_data['refresh_token']
                existing_account.token_expires_at = token_data['expires_at']
                existing_account.is_active = True
                existing_account.is_default = True
                existing_account.sync_enabled = True
                existing_account.save()
                email_account = existing_account
                created = False
                logger.info(f"Reactivated existing email account for {email_address}")
            else:
                # Check if there's any other account for this user - deactivate it first
                other_accounts = EmailAccount.objects.filter(user=request.user)
                if other_accounts.exists():
                    # Deactivate all other accounts for this user
                    other_accounts.update(is_active=False, is_default=False)
                    logger.info(f"Deactivated {other_accounts.count()} other accounts for user")
                
                # Now try to create/update an account with this email address
                email_account, created = EmailAccount.objects.update_or_create(
                    email_address=email_address,
                    defaults={
                        'user': request.user,
                        'display_name': display_name,
                        'access_token': token_data['access_token'],
                        'refresh_token': token_data['refresh_token'],
                        'token_expires_at': token_data['expires_at'],
                        'is_default': True,
                        'sync_enabled': True,
                        'is_active': True
                    }
                )
                
                if created:
                    logger.info(f"Created new email account for {email_address}")
                else:
                    logger.info(f"Updated existing email account for {email_address}")
                
        except Exception as e:
            logger.error(f"Error creating/updating email account: {str(e)}")
            raise
        
        # Initialize folders (try to sync, but don't fail if it doesn't work)
        sync_service = EmailSyncService(email_account)
        try:
            folders_synced = sync_service.sync_folders()
            if folders_synced > 0:
                messages.success(
                    request, 
                    f"Email account connected successfully! Synced {folders_synced} folders."
                )
            else:
                messages.success(
                    request, 
                    "Email account connected successfully! API setup complete."
                )
        except Exception as e:
            logger.warning(f"Folder sync failed: {str(e)}")
            messages.success(
                request, 
                "Email account connected successfully! (Folder sync will happen in background)"
            )
        
        logger.info(f"OAuth setup completed for user {request.user.id}")
        return redirect('mail_app:dashboard')
        
    except Exception as e:
        logger.error(f"OAuth callback error for user {request.user.id}: {str(e)}")
        messages.error(request, "Error setting up email account. Please try again.")
        return redirect('mail_app:dashboard')


@login_required
def oauth_disconnect(request):
    """
    Disconnect and delete all email data for the user.
    """
    try:
        # Get user's email accounts
        user_accounts = request.user.email_accounts.filter(is_active=True)
        
        if not user_accounts.exists():
            messages.warning(request, "Keine aktive Email-Verbindung gefunden.")
            return redirect('mail_app:dashboard')
        
        total_deleted_data = {}
        
        for account in user_accounts:
            # Count data before deletion for user feedback
            emails_count = account.emails.count()
            folders_count = account.folders.count() 
            threads_count = account.threads.count()
            drafts_count = account.drafts.count()
            attachments_count = sum(email.attachments.count() for email in account.emails.all())
            sync_logs_count = account.sync_logs.count()
            
            logger.info(f"Disconnecting account {account.email_address} - deleting {emails_count} emails, {folders_count} folders, {threads_count} threads, {drafts_count} drafts, {attachments_count} attachments, {sync_logs_count} sync logs")
            
            # Delete all related data (CASCADE will handle most of this automatically)
            # But let's be explicit for clarity and logging
            
            # Delete emails (this will also delete attachments due to CASCADE)
            account.emails.all().delete()
            
            # Delete folders
            account.folders.all().delete()
            
            # Delete threads
            account.threads.all().delete()
            
            # Delete drafts
            account.drafts.all().delete()
            
            # Delete sync logs
            account.sync_logs.all().delete()
            
            # Update totals for user feedback
            total_deleted_data['emails'] = total_deleted_data.get('emails', 0) + emails_count
            total_deleted_data['folders'] = total_deleted_data.get('folders', 0) + folders_count
            total_deleted_data['threads'] = total_deleted_data.get('threads', 0) + threads_count
            total_deleted_data['drafts'] = total_deleted_data.get('drafts', 0) + drafts_count
            total_deleted_data['attachments'] = total_deleted_data.get('attachments', 0) + attachments_count
            total_deleted_data['sync_logs'] = total_deleted_data.get('sync_logs', 0) + sync_logs_count
            
            # Deactivate the account
            account.is_active = False
            account.access_token = ''
            account.refresh_token = ''
            account.token_expires_at = None
            account.last_sync = None
            account.save()
            
            logger.info(f"Successfully disconnected account {account.email_address}")
        
        # Also clear ZohoAPISettings
        try:
            from accounts.models import ZohoAPISettings
            zoho_settings = ZohoAPISettings.objects.filter(user=request.user).first()
            if zoho_settings:
                zoho_settings.access_token = ''
                zoho_settings.refresh_token = ''
                zoho_settings.token_expires_at = None
                zoho_settings.is_active = False
                zoho_settings.save()
                logger.info(f"Cleared ZohoAPISettings for user {request.user.username}")
        except Exception as e:
            logger.warning(f"Could not clear ZohoAPISettings: {str(e)}")
        
        # Create user-friendly message
        deleted_summary = []
        if total_deleted_data.get('emails', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['emails']} Emails")
        if total_deleted_data.get('folders', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['folders']} Ordner")
        if total_deleted_data.get('threads', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['threads']} Unterhaltungen")
        if total_deleted_data.get('drafts', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['drafts']} Entwürfe")
        if total_deleted_data.get('attachments', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['attachments']} Anhänge")
        
        summary_text = ", ".join(deleted_summary) if deleted_summary else "keine Daten"
        
        messages.success(
            request, 
            f"Email-Verbindung erfolgreich getrennt. Gelöscht: {summary_text}."
        )
        
        logger.info(f"Successfully disconnected email for user {request.user.username}: {summary_text}")
        
    except Exception as e:
        logger.error(f"Error disconnecting email for user {request.user.id}: {str(e)}")
        messages.error(request, "Fehler beim Trennen der Email-Verbindung. Bitte versuchen Sie es erneut.")
    
    return redirect('mail_app:dashboard')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_accounts(request):
    """
    API endpoint to get user's email accounts.
    """
    accounts = request.user.email_accounts.filter(is_active=True)
    data = []
    
    for account in accounts:
        data.append({
            'id': account.id,
            'email_address': account.email_address,
            'display_name': account.display_name,
            'is_default': account.is_default,
            'last_sync': account.last_sync.isoformat() if account.last_sync else None,
            'sync_enabled': account.sync_enabled,
        })
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_folders(request, account_id):
    """
    API endpoint to get folders for a specific email account.
    """
    try:
        account = get_object_or_404(
            EmailAccount, 
            id=account_id, 
            user=request.user, 
            is_active=True
        )
        
        folders = account.folders.all()
        data = []
        
        for folder in folders:
            data.append({
                'id': folder.id,
                'name': folder.name,
                'folder_type': folder.folder_type,
                'unread_count': folder.unread_count,
                'total_count': folder.total_count,
            })
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Error fetching folders for account {account_id}: {str(e)}")
        return Response(
            {'error': 'Failed to fetch folders'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_emails(request, account_id, folder_id):
    """
    API endpoint to get emails for a specific folder.
    """
    try:
        account = get_object_or_404(
            EmailAccount, 
            id=account_id, 
            user=request.user, 
            is_active=True
        )
        
        folder = get_object_or_404(Folder, id=folder_id, account=account)
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get emails
        emails = folder.emails.select_related('account').prefetch_related('attachments')[offset:offset + page_size]
        
        data = []
        for email in emails:
            data.append({
                'id': email.id,
                'subject': email.subject,
                'from_email': email.from_email,
                'from_name': email.from_name,
                'to_emails': email.to_emails,
                'sent_at': email.sent_at.isoformat(),
                'is_read': email.is_read,
                'is_starred': email.is_starred,
                'is_important': email.is_important,
                'has_attachments': email.has_attachments,
                'body_preview': email.body_text[:200] if email.body_text else '',
            })
        
        return Response({
            'emails': data,
            'page': page,
            'page_size': page_size,
            'has_next': len(emails) == page_size,
        })
        
    except Exception as e:
        logger.error(f"Error fetching emails for folder {folder_id}: {str(e)}")
        return Response(
            {'error': 'Failed to fetch emails'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_sync_emails(request, account_id):
    """
    API endpoint to manually sync emails for an account.
    """
    try:
        account = get_object_or_404(
            EmailAccount, 
            id=account_id, 
            user=request.user, 
            is_active=True
        )
        
        # Get optional parameters
        folder_id = request.data.get('folder_id')
        limit = min(int(request.data.get('limit', 100)), 500)  # Max 500 for 90-day sync
        use_background = request.data.get('background', False)
        
        if use_background:
            # Use Celery task for background sync
            from .tasks import sync_single_account
            task = sync_single_account.delay(account_id, folder_id, limit)
            
            return Response({
                'success': True,
                'message': 'Email sync started in background',
                'task_id': task.id,
                'background': True
            })
        else:
            # Synchronous sync
            sync_service = EmailSyncService(account)
            
            # Sync folders first
            folders_synced = sync_service.sync_folders()
            
            # Sync emails for specific folder or all folders
            folder_filter = None
            if folder_id:
                folder_filter = get_object_or_404(
                    account.folders, 
                    id=folder_id
                )
            
            # Set date range for last 90 days
            from datetime import timedelta
            end_date = timezone.now()
            start_date = end_date - timedelta(days=90)
            
            sync_stats = sync_service.sync_emails(
                folder=folder_filter, 
                limit=limit,
                start_date=start_date,
                end_date=end_date
            )
            
            return Response({
                'success': True,
                'folders_synced': folders_synced,
                'sync_stats': sync_stats,
                'last_sync': timezone.now().isoformat(),
                'background': False
            })
            
    except ReAuthorizationRequiredError as e:
        logger.warning(f"Re-authorization required for account {account_id}: {str(e)}")
        return Response(
            {
                'error': 'Re-authorization required',
                'reauth_required': True,
                'message': 'Your email authorization has expired. Please reconnect your email account.'
            }, 
            status=status.HTTP_401_UNAUTHORIZED
        )
        
    except Exception as e:
        logger.error(f"Error syncing emails for account {account_id}: {str(e)}")
        return Response(
            {'error': 'Failed to sync emails'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_email_detail(request, email_id):
    """
    API endpoint to get detailed information for a specific email.
    """
    try:
        email = get_object_or_404(
            Email, 
            id=email_id, 
            account__user=request.user
        )
        
        # Mark as read
        email.mark_as_read()
        
        # Get attachments
        attachments = []
        for attachment in email.attachments.all():
            attachments.append({
                'id': attachment.id,
                'filename': attachment.filename,
                'content_type': attachment.content_type,
                'file_size': attachment.file_size,
                'file_size_human': attachment.file_size_human,
            })
        
        data = {
            'id': email.id,
            'subject': email.subject,
            'from_email': email.from_email,
            'from_name': email.from_name,
            'to_emails': email.to_emails,
            'cc_emails': email.cc_emails,
            'bcc_emails': email.bcc_emails,
            'reply_to': email.reply_to,
            'body_text': email.body_text,
            'body_html': email.body_html,
            'sent_at': email.sent_at.isoformat(),
            'received_at': email.received_at.isoformat() if email.received_at else None,
            'is_read': email.is_read,
            'is_starred': email.is_starred,
            'is_important': email.is_important,
            'message_type': email.message_type,
            'priority': email.priority,
            'attachments': attachments,
        }
        
        return JsonResponse({
            'success': True,
            'email': data
        })
        
    except Exception as e:
        logger.error(f"Error fetching email detail {email_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch email details'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_send_email(request):
    """
    API endpoint to send an email.
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['account_id', 'to_emails', 'subject']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, status=400)
        
        # Get account
        account = get_object_or_404(
            EmailAccount, 
            id=data['account_id'], 
            user=request.user, 
            is_active=True
        )
        
        # Send email
        api_service = ZohoMailAPIService(account)
        success = api_service.send_email(
            to_emails=data['to_emails'],
            subject=data['subject'],
            body_text=data.get('body_text', ''),
            body_html=data.get('body_html', ''),
            cc_emails=data.get('cc_emails', []),
            bcc_emails=data.get('bcc_emails', []),
            attachments=data.get('attachments', []),
        )
        
        if success:
            return JsonResponse({'success': True, 'message': 'Email sent successfully'})
        else:
            return JsonResponse({'success': False, 'error': 'Failed to send email'}, status=500)
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Failed to send email'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mark_email(request, email_id):
    """
    API endpoint to mark email as read/unread/starred.
    """
    try:
        email = get_object_or_404(
            Email, 
            id=email_id, 
            account__user=request.user
        )
        
        action = request.data.get('action')
        
        if action == 'read':
            email.mark_as_read()
        elif action == 'unread':
            email.mark_as_unread()
        elif action == 'star':
            email.is_starred = True
            email.save(update_fields=['is_starred'])
        elif action == 'unstar':
            email.is_starred = False
            email.save(update_fields=['is_starred'])
        else:
            return Response(
                {'error': 'Invalid action'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({'success': True})
        
    except Exception as e:
        logger.error(f"Error marking email {email_id}: {str(e)}")
        return Response(
            {'error': 'Failed to mark email'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_sync_status(request, account_id):
    """
    API endpoint to get sync status for an account.
    """
    try:
        account = get_object_or_404(
            EmailAccount, 
            id=account_id, 
            user=request.user, 
            is_active=True
        )
        
        # Get recent sync logs
        recent_syncs = account.sync_logs.order_by('-started_at')[:5]
        
        sync_history = []
        for sync_log in recent_syncs:
            sync_history.append({
                'id': sync_log.id,
                'sync_type': sync_log.sync_type,
                'status': sync_log.status,
                'started_at': sync_log.started_at.isoformat(),
                'completed_at': sync_log.completed_at.isoformat() if sync_log.completed_at else None,
                'emails_fetched': sync_log.emails_fetched,
                'emails_created': sync_log.emails_created,
                'folders_synced': sync_log.folders_synced,
                'error_count': sync_log.error_count,
                'error_message': sync_log.error_message,
            })
        
        return Response({
            'account_id': account.id,
            'email_address': account.email_address,
            'last_sync': account.last_sync.isoformat() if account.last_sync else None,
            'sync_enabled': account.sync_enabled,
            'sync_history': sync_history
        })
        
    except Exception as e:
        logger.error(f"Error fetching sync status for account {account_id}: {str(e)}")
        return Response(
            {'error': 'Failed to fetch sync status'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_upload_attachment(request):
    """
    API endpoint to upload an attachment.
    """
    try:
        # Get account
        account_id = request.data.get('account_id')
        if not account_id:
            return Response(
                {'error': 'Account ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        account = get_object_or_404(
            EmailAccount, 
            id=account_id, 
            user=request.user, 
            is_active=True
        )
        
        # Check if file was uploaded
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file uploaded'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        
        # Check file size (max 25MB as per settings)
        max_size = settings.MAIL_APP_SETTINGS.get('MAX_ATTACHMENT_SIZE', 25) * 1024 * 1024
        if uploaded_file.size > max_size:
            return Response(
                {'error': f'File too large. Max size: {max_size // (1024*1024)}MB'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Upload to Zoho Mail API
        api_service = ZohoMailAPIService(account)
        attachment_info = api_service.upload_attachment(
            file_content=uploaded_file.read(),
            filename=uploaded_file.name,
            content_type=uploaded_file.content_type
        )
        
        if attachment_info:
            return Response({
                'success': True,
                'attachment': attachment_info
            })
        else:
            return Response(
                {'error': 'Failed to upload attachment'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Exception as e:
        logger.error(f"Error uploading attachment: {str(e)}")
        return Response(
            {'error': 'Failed to upload attachment'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_download_attachment(request, attachment_id):
    """
    API endpoint to download an attachment.
    """
    try:
        # Get attachment from database
        attachment = get_object_or_404(
            Attachment, 
            id=attachment_id, 
            email__account__user=request.user
        )
        
        # Check if we have cached content
        if attachment.is_cached and attachment.file_data:
            logger.info(f"Serving cached attachment: {attachment.filename}")
            from django.http import HttpResponse
            response = HttpResponse(
                attachment.file_data, 
                content_type=attachment.content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
            response['Content-Length'] = len(attachment.file_data)
            return response
        
        # Download from Zoho Mail API
        api_service = ZohoMailAPIService(attachment.email.account)
        file_content = api_service.download_attachment(
            attachment.email.zoho_message_id, 
            attachment.zoho_attachment_id
        )
        
        if file_content:
            # Cache the content for future requests
            attachment.file_data = file_content
            attachment.is_cached = True
            attachment.save(update_fields=['file_data', 'is_cached'])
            
            logger.info(f"Downloaded and cached attachment: {attachment.filename}")
            
            from django.http import HttpResponse
            response = HttpResponse(file_content, content_type=attachment.content_type)
            response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
            response['Content-Length'] = len(file_content)
            return response
        else:
            return Response(
                {'error': 'Failed to download attachment'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Exception as e:
        logger.error(f"Error downloading attachment {attachment_id}: {str(e)}")
        return Response(
            {'error': 'Failed to download attachment'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_threads(request, account_id):
    """
    API endpoint to get email threads for an account.
    """
    try:
        account = get_object_or_404(
            EmailAccount, 
            id=account_id, 
            user=request.user, 
            is_active=True
        )
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get threads
        threads = account.threads.all()[offset:offset + page_size]
        
        data = []
        for thread in threads:
            # Get latest email for preview
            latest_email = thread.emails.order_by('-sent_at').first()
            
            data.append({
                'id': thread.id,
                'thread_id': thread.thread_id,
                'subject': thread.subject,
                'participants': thread.participants,
                'message_count': thread.message_count,
                'unread_count': thread.unread_count,
                'first_message_at': thread.first_message_at.isoformat(),
                'last_message_at': thread.last_message_at.isoformat(),
                'latest_preview': {
                    'from_email': latest_email.from_email if latest_email else '',
                    'from_name': latest_email.from_name if latest_email else '',
                    'body_preview': latest_email.body_text[:200] if latest_email and latest_email.body_text else '',
                } if latest_email else None
            })
        
        return Response({
            'threads': data,
            'page': page,
            'page_size': page_size,
            'has_next': len(threads) == page_size,
        })
        
    except Exception as e:
        logger.error(f"Error fetching threads for account {account_id}: {str(e)}")
        return Response(
            {'error': 'Failed to fetch threads'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_thread_emails(request, thread_id):
    """
    API endpoint to get all emails in a thread.
    """
    try:
        thread = get_object_or_404(
            EmailThread, 
            id=thread_id, 
            account__user=request.user
        )
        
        # Get all emails in thread, ordered by date
        emails = thread.emails.select_related('folder').prefetch_related('attachments').order_by('sent_at')
        
        data = []
        for email in emails:
            data.append({
                'id': email.id,
                'subject': email.subject,
                'from_email': email.from_email,
                'from_name': email.from_name,
                'to_emails': email.to_emails,
                'cc_emails': email.cc_emails,
                'body_text': email.body_text,
                'body_html': email.body_html,
                'sent_at': email.sent_at.isoformat(),
                'is_read': email.is_read,
                'is_starred': email.is_starred,
                'is_important': email.is_important,
                'has_attachments': email.has_attachments,
                'folder_name': email.folder.name,
                'attachments': [{
                    'id': att.id,
                    'filename': att.filename,
                    'content_type': att.content_type,
                    'file_size': att.file_size,
                    'file_size_human': att.file_size_human,
                } for att in email.attachments.all()]
            })
        
        return Response({
            'thread': {
                'id': thread.id,
                'subject': thread.subject,
                'participants': thread.participants,
                'message_count': thread.message_count,
                'unread_count': thread.unread_count,
            },
            'emails': data
        })
        
    except Exception as e:
        logger.error(f"Error fetching thread emails {thread_id}: {str(e)}")
        return Response(
            {'error': 'Failed to fetch thread emails'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )