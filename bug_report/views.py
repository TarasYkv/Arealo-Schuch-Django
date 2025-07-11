from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.utils import timezone
from chat.models import ChatRoom, ChatMessage
from .models import BugReport, BugReportAttachment
from .forms import BugReportForm, BugReportAttachmentForm
import json
import base64
import uuid
import os

User = get_user_model()


@require_http_methods(["POST"])
def submit_bug_report(request):
    """AJAX-Endpunkt für Bug-Meldungen"""
    try:
        data = json.loads(request.body)
        
        # Erstelle Bug-Report
        bug_report = BugReport.objects.create(
            sender=request.user if request.user.is_authenticated else None,
            sender_name=data.get('sender_name', ''),
            sender_email=data.get('sender_email', ''),
            subject=data.get('subject', 'Bug-Meldung'),
            message=data.get('message', ''),
            browser_info=data.get('browser_info', ''),
            url=data.get('url', ''),
            console_log=data.get('console_log', '')
        )
        
        # Verarbeite Screenshot falls vorhanden
        if 'screenshot' in data and data['screenshot']:
            screenshot_data = data['screenshot']
            if screenshot_data.startswith('data:image'):
                # Extrahiere Base64-Daten
                format_part, imgstr = screenshot_data.split(',', 1)
                ext = format_part.split(';')[0].split('/')[1]
                
                # Konvertiere Base64 zu Datei
                screenshot_file = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'screenshot_{uuid.uuid4()}.{ext}'
                )
                
                # Erstelle Anhang
                BugReportAttachment.objects.create(
                    bug_report=bug_report,
                    file=screenshot_file,
                    filename=f'screenshot.{ext}',
                    file_size=len(base64.b64decode(imgstr)),
                    content_type=f'image/{ext}',
                    is_screenshot=True
                )
        
        # Erstelle Chat-Raum für Bug-Meldung
        chat_room = create_bug_chat_room(bug_report)
        bug_report.chat_room = chat_room
        bug_report.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Bug-Meldung erfolgreich gesendet!',
            'bug_report_id': bug_report.id,
            'chat_room_id': chat_room.id if chat_room else None,
            'chat_room_url': chat_room.get_absolute_url() if chat_room else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def create_bug_chat_room(bug_report):
    """Erstellt einen Chat-Raum für eine Bug-Meldung"""
    # Finde alle Super User die Bug-Meldungen empfangen möchten
    superusers = User.objects.filter(
        is_bug_chat_superuser=True,
        receive_bug_reports=True
    )
    
    # Wenn anonyme Meldung, filtere auf User die anonyme Meldungen empfangen
    if not bug_report.sender:
        superusers = superusers.filter(receive_anonymous_reports=True)
    
    # Erstelle Chat-Raum
    room_name = f"Bug-Meldung: {bug_report.subject}"
    chat_room = ChatRoom.objects.create(
        name=room_name,
        created_by=bug_report.sender,
        is_bug_report_room=True
    )
    
    # Füge Super User zum Chat-Raum hinzu
    for superuser in superusers:
        chat_room.participants.add(superuser)
    
    # Füge Sender hinzu falls angemeldet
    if bug_report.sender:
        chat_room.participants.add(bug_report.sender)
    
    # Erstelle initiale Chat-Nachricht
    initial_message = f"🐛 **Bug-Meldung**\n\n"
    initial_message += f"**Betreff:** {bug_report.subject}\n"
    initial_message += f"**Von:** {bug_report.get_sender_name()}\n"
    if bug_report.get_sender_email():
        initial_message += f"**E-Mail:** {bug_report.get_sender_email()}\n"
    initial_message += f"**URL:** {bug_report.url}\n\n"
    initial_message += f"**Beschreibung:**\n{bug_report.message}"
    
    # Füge Console Log hinzu falls vorhanden
    if bug_report.console_log:
        initial_message += f"\n\n**Console Log (letzte {bug_report.console_log.count(chr(10))} Zeilen):**\n```\n{bug_report.console_log}\n```"
    
    ChatMessage.objects.create(
        chat_room=chat_room,
        sender=bug_report.sender,
        sender_name=bug_report.sender_name if not bug_report.sender else None,
        content=initial_message,
        is_system_message=True
    )
    
    return chat_room


@require_http_methods(["POST"])
def upload_bug_attachment(request):
    """AJAX-Endpunkt für Datei-Uploads"""
    try:
        bug_report_id = request.POST.get('bug_report_id')
        bug_report = get_object_or_404(BugReport, id=bug_report_id)
        
        # Überprüfe Berechtigung
        if bug_report.sender != request.user and not request.user.is_bug_chat_superuser:
            return JsonResponse({'success': False, 'error': 'Keine Berechtigung'})
        
        uploaded_files = []
        
        for file in request.FILES.getlist('files'):
            # Validiere Datei
            if file.size > 10 * 1024 * 1024:  # 10MB
                continue
            
            # Erstelle Anhang
            attachment = BugReportAttachment.objects.create(
                bug_report=bug_report,
                file=file,
                filename=file.name,
                file_size=file.size,
                content_type=file.content_type
            )
            
            uploaded_files.append({
                'id': attachment.id,
                'filename': attachment.filename,
                'size': attachment.get_file_size_display()
            })
        
        return JsonResponse({
            'success': True,
            'files': uploaded_files
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def bug_report_list(request):
    """Liste aller Bug-Meldungen für Super User"""
    if not request.user.is_bug_chat_superuser:
        messages.error(request, "Keine Berechtigung für Bug-Meldungen")
        return redirect('accounts:dashboard')
    
    bug_reports = BugReport.objects.all().order_by('-created_at')
    
    return render(request, 'bug_report/bug_report_list.html', {
        'bug_reports': bug_reports
    })


@login_required
def bug_report_detail(request, bug_report_id):
    """Detail-Ansicht einer Bug-Meldung"""
    bug_report = get_object_or_404(BugReport, id=bug_report_id)
    
    # Überprüfe Berechtigung
    if not (request.user.is_bug_chat_superuser or bug_report.sender == request.user):
        messages.error(request, "Keine Berechtigung für diese Bug-Meldung")
        return redirect('accounts:dashboard')
    
    return render(request, 'bug_report/bug_report_detail.html', {
        'bug_report': bug_report
    })


@login_required
@require_http_methods(["POST"])
def update_bug_status(request, bug_report_id):
    """Aktualisiert den Status einer Bug-Meldung"""
    if not request.user.is_bug_chat_superuser:
        return JsonResponse({'success': False, 'error': 'Keine Berechtigung'})
    
    bug_report = get_object_or_404(BugReport, id=bug_report_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(BugReport.STATUS_CHOICES):
        bug_report.status = new_status
        bug_report.save()
        
        # Sende Benachrichtigung in Chat
        if bug_report.chat_room:
            status_display = dict(BugReport.STATUS_CHOICES)[new_status]
            ChatMessage.objects.create(
                chat_room=bug_report.chat_room,
                sender=request.user,
                content=f"🔄 Status geändert zu: **{status_display}**",
                is_system_message=True
            )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Ungültiger Status'})