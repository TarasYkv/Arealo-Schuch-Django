import qrcode
import io
import base64
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

def humanize_bytes(bytes_value):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def generate_qr_code(url):
    """Generate QR code for a URL and return as base64 string"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def send_transfer_email(transfer, recipient, download_url):
    """Send email notification for a transfer"""
    context = {
        'transfer': transfer,
        'recipient': recipient,
        'download_url': download_url,
        'expires_in_days': (transfer.expires_at - transfer.created_at).days
    }

    # Render email template
    html_message = render_to_string('fileshare/email/transfer_notification.html', context)
    plain_message = strip_tags(html_message)

    subject = f"Dateien wurden mit Ihnen geteilt: {transfer.title or 'Ohne Titel'}"

    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient.email],
        html_message=html_message,
        fail_silently=False,
    )

def clean_expired_transfers():
    """Clean up expired transfers and their files"""
    from django.utils import timezone
    from .models import Transfer

    expired_transfers = Transfer.objects.filter(
        expires_at__lt=timezone.now(),
        is_active=True
    )

    count = 0
    for transfer in expired_transfers:
        # Delete all files
        for file_obj in transfer.files.all():
            try:
                file_obj.delete()  # This will also delete the physical file
            except:
                pass

        # Mark transfer as inactive
        transfer.is_active = False
        transfer.save()
        count += 1

    return count