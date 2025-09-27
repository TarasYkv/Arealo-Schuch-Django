from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, F
from django.conf import settings
import json
import os
import zipfile
import mimetypes
import hashlib
from datetime import timedelta
from .models import Transfer, TransferFile, TransferRecipient, DownloadLog
from .forms import TransferForm
from .utils import send_transfer_email, humanize_bytes, generate_qr_code

def index(request):
    """Main page for file sharing"""
    context = {
        'max_file_size': 2 * 1024 * 1024 * 1024,  # 2GB in bytes
        'user_transfers': None
    }

    if request.user.is_authenticated:
        context['user_transfers'] = Transfer.objects.filter(
            sender=request.user
        ).order_by('-created_at')[:10]

    return render(request, 'fileshare/index.html', context)

@csrf_exempt
def create_transfer(request):
    """Create a new transfer"""
    if request.method == 'POST':
        transfer = Transfer.objects.create(
            sender=request.user if request.user.is_authenticated else None,
            sender_email=request.POST.get('sender_email', ''),
            title=request.POST.get('title', ''),
            message=request.POST.get('message', ''),
            transfer_type=request.POST.get('transfer_type', 'link'),
            expires_at=timezone.now() + timedelta(days=int(request.POST.get('expiry_days', 7))),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Handle password protection
        password = request.POST.get('password')
        if password:
            transfer.password_hash = hashlib.sha256(password.encode()).hexdigest()
            transfer.save()

        return JsonResponse({
            'success': True,
            'transfer_id': str(transfer.id),
            'upload_url': reverse('fileshare:upload_file', kwargs={'transfer_id': str(transfer.id)})
        })

    return JsonResponse({'success': False, 'error': 'Invalid request'})

@csrf_exempt
@require_http_methods(['POST'])
def upload_file(request, transfer_id):
    """Handle file upload for a transfer"""
    try:
        transfer = Transfer.objects.get(id=transfer_id)

        # Check if transfer is still active
        if not transfer.is_active or transfer.is_expired:
            return JsonResponse({'success': False, 'error': 'Transfer is no longer active'})

        # Get the uploaded file
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'success': False, 'error': 'No file provided'})

        # Check file size (2GB limit for free users)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if request.user.is_authenticated and hasattr(request.user, 'is_premium') and request.user.is_premium:
            max_size = 200 * 1024 * 1024 * 1024  # 200GB for premium

        if file.size > max_size:
            return JsonResponse({'success': False, 'error': f'File too large. Maximum size: {humanize_bytes(max_size)}'})

        # Create TransferFile object
        transfer_file = TransferFile.objects.create(
            transfer=transfer,
            original_filename=file.name,
            file=file,
            file_size=file.size,
            file_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        )

        # Update transfer total size
        transfer.total_size = transfer.files.aggregate(Sum('file_size'))['file_size__sum'] or 0
        transfer.save()

        return JsonResponse({
            'success': True,
            'file_id': str(transfer_file.id),
            'filename': transfer_file.original_filename,
            'size': transfer_file.file_size
        })

    except Transfer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transfer nicht gefunden'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def complete_transfer(request, transfer_id):
    """Complete the transfer and send emails if needed"""
    try:
        transfer = Transfer.objects.get(id=transfer_id)

        # Generate download link
        download_url = request.build_absolute_uri(
            reverse('fileshare:download', kwargs={'transfer_id': str(transfer.id)})
        )

        # Send emails if it's an email transfer
        if transfer.transfer_type == 'email':
            recipients = request.POST.get('recipients', '').split(',')
            for email in recipients:
                email = email.strip()
                if email:
                    recipient, created = TransferRecipient.objects.get_or_create(
                        transfer=transfer,
                        email=email
                    )
                    # Send email notification
                    send_transfer_email(transfer, recipient, download_url)
                    recipient.notified_at = timezone.now()
                    recipient.save()

        # Generate QR code for the download link
        qr_code = generate_qr_code(download_url)

        return JsonResponse({
            'success': True,
            'download_url': download_url,
            'qr_code': qr_code,
            'expires_at': transfer.expires_at.isoformat()
        })

    except Transfer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transfer nicht gefunden'})

def download_page(request, transfer_id):
    """Download page for a transfer"""
    try:
        transfer = get_object_or_404(Transfer, id=transfer_id)

        # Prüfe ob Transfer heruntergeladen werden kann
        if not transfer.can_download:
            if transfer.is_expired:
                messages.error(request, 'This transfer has expired.')
            elif transfer.is_download_limit_reached:
                messages.error(request, 'Download limit has been reached.')
            else:
                messages.error(request, 'This transfer is no longer available.')
            return render(request, 'fileshare/error.html')

        # Check password if required
        if transfer.password_hash:
            if request.method == 'POST':
                password = request.POST.get('password', '')
                if hashlib.sha256(password.encode()).hexdigest() == transfer.password_hash:
                    request.session[f'transfer_{transfer_id}_auth'] = True
                    return redirect('fileshare:download', transfer_id=transfer_id)
                else:
                    messages.error(request, 'Invalid password')

            if not request.session.get(f'transfer_{transfer_id}_auth'):
                return render(request, 'fileshare/password.html', {'transfer': transfer})

        context = {
            'transfer': transfer,
            'files': transfer.files.all(),
            'total_size': humanize_bytes(transfer.total_size),
            'expires_in': (transfer.expires_at - timezone.now()).days
        }

        return render(request, 'fileshare/download.html', context)

    except Transfer.DoesNotExist:
        raise Http404("Transfer not found")

def download_file(request, transfer_id, file_id=None):
    """Download files from a transfer"""
    try:
        transfer = get_object_or_404(Transfer, id=transfer_id)

        # Prüfe ob Transfer heruntergeladen werden kann
        if not transfer.can_download:
            raise Http404("Transfer not available")

        # Check password authorization
        if transfer.password_hash and not request.session.get(f'transfer_{transfer_id}_auth'):
            return redirect('fileshare:download', transfer_id=transfer_id)

        # Log the download
        download_log = DownloadLog.objects.create(
            transfer=transfer,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Single file download
        if file_id:
            file_obj = get_object_or_404(TransferFile, id=file_id, transfer=transfer)
            download_log.file = file_obj
            download_log.save()

            response = FileResponse(
                file_obj.file.open('rb'),
                content_type=file_obj.file_type,
                as_attachment=True,
                filename=file_obj.original_filename
            )

            # Aktualisiere Download-Zähler
            transfer.total_downloads += 1
            transfer.save()

            download_log.download_completed = True
            download_log.bytes_downloaded = file_obj.file_size
            download_log.save()

            return response

        # Multiple files - create ZIP
        else:
            files = transfer.files.all()
            if not files:
                raise Http404("No files in transfer")

            # Create ZIP file in memory
            import io
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_obj in files:
                    zip_file.writestr(file_obj.original_filename, file_obj.file.read())

            zip_buffer.seek(0)

            response = HttpResponse(zip_buffer.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="transfer_{transfer_id}.zip"'

            # Aktualisiere Download-Zähler
            transfer.total_downloads += 1
            transfer.save()

            download_log.download_completed = True
            download_log.bytes_downloaded = len(zip_buffer.getvalue())
            download_log.save()

            return response

    except Transfer.DoesNotExist:
        raise Http404("Transfer not found")

@login_required
def my_transfers(request):
    """View user's transfers"""
    transfers = Transfer.objects.filter(sender=request.user).order_by('-created_at')

    # Calculate statistics
    stats = {
        'total_transfers': transfers.count(),
        'active_transfers': transfers.filter(is_active=True, expires_at__gt=timezone.now()).count(),
        'total_downloads': transfers.aggregate(Sum('total_downloads'))['total_downloads__sum'] or 0,
        'total_size': transfers.aggregate(Sum('total_size'))['total_size__sum'] or 0
    }

    context = {
        'transfers': transfers,
        'stats': stats
    }

    return render(request, 'fileshare/my_transfers.html', context)

@login_required
def delete_transfer(request, transfer_id):
    """Delete a transfer"""
    transfer = get_object_or_404(Transfer, id=transfer_id, sender=request.user)

    if request.method == 'POST':
        # Delete all files
        for file_obj in transfer.files.all():
            file_obj.delete()

        transfer.delete()
        messages.success(request, 'Transfer deleted successfully')
        return redirect('fileshare:my_transfers')

    return render(request, 'fileshare/confirm_delete.html', {'transfer': transfer})

def transfer_stats(request, transfer_id):
    """Get transfer statistics"""
    transfer = get_object_or_404(Transfer, id=transfer_id)

    # Check if user has permission to view stats
    if transfer.sender != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    downloads = transfer.download_logs.all().order_by('-downloaded_at')[:20]

    stats = {
        'total_downloads': transfer.total_downloads,
        'unique_downloads': downloads.values('ip_address').distinct().count(),
        'recent_downloads': [
            {
                'date': dl.downloaded_at.isoformat(),
                'ip': dl.ip_address,
                'completed': dl.download_completed
            } for dl in downloads
        ]
    }

    return JsonResponse(stats)