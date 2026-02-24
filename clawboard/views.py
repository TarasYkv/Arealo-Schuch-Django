import json
import os
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import (
    ClawdbotConnection, Project, ProjectMemory,
    Conversation, ScheduledTask, MemoryFile, Integration, Skill,
    ClawboardChat
)
from .forms import ClawdbotConnectionForm, ProjectForm
from .services import get_available_models_for_user, call_ai_chat


def _get_api_services(user):
    """Konfigurierte API-Services und Verknuepfungen aus User-Profil sammeln."""
    services = []
    api_checks = [
        ('openai_api_key', 'OpenAI', 'bi-stars'),
        ('anthropic_api_key', 'Anthropic', 'bi-robot'),
        ('deepseek_api_key', 'DeepSeek', 'bi-braces'),
        ('gemini_api_key', 'Google Gemini', 'bi-google'),
        ('google_api_key', 'Google API', 'bi-google'),
        ('youtube_api_key', 'YouTube', 'bi-youtube'),
        ('brave_api_key', 'Brave Search', 'bi-search'),
        ('bing_api_key', 'Bing Search', 'bi-search'),
        ('ideogram_api_key', 'Ideogram', 'bi-image'),
        ('supadata_api_key', 'Supadata (TikTok)', 'bi-tiktok'),
        ('upload_post_api_key', 'Upload-Post', 'bi-upload'),
    ]
    for field, name, icon in api_checks:
        if getattr(user, field, None):
            services.append({'name': name, 'icon': icon, 'status': 'active'})

    try:
        from allauth.socialaccount.models import SocialAccount
        if SocialAccount.objects.filter(user=user, provider='telegram').exists():
            services.append({'name': 'Telegram', 'icon': 'bi-telegram', 'status': 'active'})
    except Exception:
        pass

    try:
        from mail_app.models import EmailAccount
        if EmailAccount.objects.filter(user=user, is_active=True).exists():
            services.append({'name': 'Zoho Mail', 'icon': 'bi-envelope', 'status': 'active'})
    except Exception:
        pass

    return services


@login_required
def dashboard(request):
    """Hauptdashboard mit Übersicht"""
    connections = ClawdbotConnection.objects.filter(user=request.user, is_active=True)
    active_connection = connections.first()

    context = {
        'connections': connections,
        'active_connection': active_connection,
        'projects': Project.objects.filter(connection__user=request.user)[:5],
        'recent_conversations': Conversation.objects.filter(connection__user=request.user)[:5],
        'scheduled_tasks': ScheduledTask.objects.filter(connection__user=request.user, is_enabled=True)[:5],
        'integrations': Integration.objects.filter(connection__user=request.user) if active_connection else [],
        'skills': Skill.objects.filter(connection__user=request.user) if active_connection else [],
        'api_services': _get_api_services(request.user),
        'recent_chats': ClawboardChat.objects.filter(user=request.user)[:5],
        'ai_models': get_available_models_for_user(request.user),
    }

    # System-Status falls aktive Connection
    if active_connection:
        context['system_status'] = {
            'cpu': active_connection.cpu_percent,
            'ram_used': active_connection.ram_used_mb,
            'ram_total': active_connection.ram_total_mb,
            'disk_used': active_connection.disk_used_gb,
            'disk_total': active_connection.disk_total_gb,
            'status': active_connection.status,
            'last_seen': active_connection.last_seen,
        }

    context['cb_active'] = 'dashboard'
    return render(request, 'clawboard/dashboard.html', context)


# === Connection Views ===

@login_required
def connection_list(request):
    """Liste aller Clawdbot-Verbindungen"""
    connections = ClawdbotConnection.objects.filter(user=request.user)
    return render(request, 'clawboard/connections/list.html', {'connections': connections, 'cb_active': 'connector'})


@login_required
def connection_add(request):
    """Neue Verbindung hinzufügen"""
    if request.method == 'POST':
        form = ClawdbotConnectionForm(request.POST)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.user = request.user
            connection.save()
            messages.success(request, f'Verbindung "{connection.name}" wurde erstellt.')
            return redirect('clawboard:connection_detail', pk=connection.pk)
    else:
        form = ClawdbotConnectionForm()

    return render(request, 'clawboard/connections/form.html', {'form': form, 'title': 'Neue Verbindung', 'cb_active': 'connector'})


@login_required
def connection_detail(request, pk):
    """Verbindungsdetails anzeigen"""
    connection = get_object_or_404(ClawdbotConnection, pk=pk, user=request.user)
    return render(request, 'clawboard/connections/detail.html', {'connection': connection, 'cb_active': 'connector'})


@login_required
def connection_edit(request, pk):
    """Verbindung bearbeiten"""
    connection = get_object_or_404(ClawdbotConnection, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ClawdbotConnectionForm(request.POST, instance=connection)
        if form.is_valid():
            form.save()
            messages.success(request, 'Verbindung wurde aktualisiert.')
            return redirect('clawboard:connection_detail', pk=pk)
    else:
        form = ClawdbotConnectionForm(instance=connection)

    return render(request, 'clawboard/connections/form.html', {
        'form': form,
        'connection': connection,
        'title': f'Verbindung bearbeiten: {connection.name}',
        'cb_active': 'connector',
    })


@login_required
def connection_delete(request, pk):
    """Verbindung löschen"""
    connection = get_object_or_404(ClawdbotConnection, pk=pk, user=request.user)

    if request.method == 'POST':
        name = connection.name
        connection.delete()
        messages.success(request, f'Verbindung "{name}" wurde gelöscht.')
        return redirect('clawboard:connection_list')

    return render(request, 'clawboard/connections/delete.html', {'connection': connection, 'cb_active': 'connector'})


@login_required
def connection_test(request, pk):
    """Verbindung testen (AJAX)"""
    connection = get_object_or_404(ClawdbotConnection, pk=pk, user=request.user)

    # TODO: Tatsächliche Verbindung zum Gateway testen
    # Hier würde WebSocket oder HTTP Request zum Gateway gehen

    return JsonResponse({
        'success': True,
        'status': 'online',
        'message': 'Verbindung erfolgreich getestet',
    })


# === Project Views ===

@login_required
def project_list(request):
    """Liste aller Projekte"""
    projects = Project.objects.filter(connection__user=request.user)
    return render(request, 'clawboard/projects/list.html', {'projects': projects, 'cb_active': 'projects'})


@login_required
def project_add(request):
    """Neues Projekt erstellen"""
    connections = ClawdbotConnection.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        form.fields['connection'].queryset = connections
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Projekt "{project.name}" wurde erstellt.')
            return redirect('clawboard:project_detail', pk=project.pk)
    else:
        form = ProjectForm()
        form.fields['connection'].queryset = connections

    return render(request, 'clawboard/projects/form.html', {'form': form, 'title': 'Neues Projekt', 'cb_active': 'projects'})


@login_required
def project_detail(request, pk):
    """Projektdetails anzeigen"""
    project = get_object_or_404(Project, pk=pk, connection__user=request.user)
    memories = project.memories.all()[:20]
    conversations = project.conversations.all()[:10]

    return render(request, 'clawboard/projects/detail.html', {
        'project': project,
        'memories': memories,
        'conversations': conversations,
        'cb_active': 'projects',
    })


@login_required
def project_edit(request, pk):
    """Projekt bearbeiten"""
    project = get_object_or_404(Project, pk=pk, connection__user=request.user)
    connections = ClawdbotConnection.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        form.fields['connection'].queryset = connections
        if form.is_valid():
            form.save()
            messages.success(request, 'Projekt wurde aktualisiert.')
            return redirect('clawboard:project_detail', pk=pk)
    else:
        form = ProjectForm(instance=project)
        form.fields['connection'].queryset = connections

    return render(request, 'clawboard/projects/form.html', {
        'form': form,
        'project': project,
        'title': f'Projekt bearbeiten: {project.name}',
        'cb_active': 'projects',
    })


# === Conversation Views ===

@login_required
def conversation_list(request):
    """Liste aller Konversationen"""
    conversations = Conversation.objects.filter(connection__user=request.user)
    return render(request, 'clawboard/conversations/list.html', {'conversations': conversations, 'cb_active': 'dashboard'})


@login_required
def conversation_detail(request, pk):
    """Konversation anzeigen"""
    conversation = get_object_or_404(Conversation, pk=pk, connection__user=request.user)
    return render(request, 'clawboard/conversations/detail.html', {'conversation': conversation, 'cb_active': 'dashboard'})


# === Memory Browser ===

@login_required
def memory_browser(request):
    """Memory-Dateien durchsuchen"""
    connection_id = request.GET.get('connection')
    connection = None
    files = []

    if connection_id:
        connection = get_object_or_404(ClawdbotConnection, pk=connection_id, user=request.user)
        files = MemoryFile.objects.filter(connection=connection)
    else:
        connections = ClawdbotConnection.objects.filter(user=request.user, is_active=True)
        if connections.exists():
            connection = connections.first()
            files = MemoryFile.objects.filter(connection=connection)

    return render(request, 'clawboard/memory/browser.html', {
        'connection': connection,
        'files': files,
        'connections': ClawdbotConnection.objects.filter(user=request.user),
        'cb_active': 'memory',
    })


@login_required
def memory_file_view(request):
    """Memory-Datei Inhalt anzeigen (AJAX)"""
    file_id = request.GET.get('id')
    memory_file = get_object_or_404(MemoryFile, pk=file_id, connection__user=request.user)

    return JsonResponse({
        'success': True,
        'filename': memory_file.filename,
        'path': memory_file.path,
        'content': memory_file.content,
        'last_synced': memory_file.last_synced.isoformat() if memory_file.last_synced else None,
    })


@login_required
def memory_file_save(request):
    """Memory-Datei speichern (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})

    import json
    data = json.loads(request.body)
    file_id = data.get('id')
    content = data.get('content', '')

    memory_file = get_object_or_404(MemoryFile, pk=file_id, connection__user=request.user)
    memory_file.content = content
    memory_file.save()

    # TODO: Sync zurück zum Clawdbot Gateway

    return JsonResponse({
        'success': True,
        'message': 'Datei gespeichert',
    })


# === Scheduled Tasks ===

@login_required
def task_list(request):
    """Liste aller geplanten Aufgaben"""
    tasks = ScheduledTask.objects.filter(connection__user=request.user)
    return render(request, 'clawboard/tasks/list.html', {'tasks': tasks, 'cb_active': 'dashboard'})


@login_required
def task_detail(request, pk):
    """Aufgaben-Details"""
    task = get_object_or_404(ScheduledTask, pk=pk, connection__user=request.user)
    return render(request, 'clawboard/tasks/detail.html', {'task': task, 'cb_active': 'dashboard'})


# === Integrations ===

@login_required
def integration_list(request):
    """Liste aller Integrationen"""
    integrations = Integration.objects.filter(connection__user=request.user)
    return render(request, 'clawboard/integrations/list.html', {'integrations': integrations, 'cb_active': 'services'})


# === Connector Download ===

@login_required
def connector_setup(request):
    """Connector Setup-Seite - ein Befehl zum Kopieren"""
    from django.core import signing

    connections = ClawdbotConnection.objects.filter(user=request.user, is_active=True)
    active_connection = connections.first()

    config_url = None
    script_url = request.build_absolute_uri(
        reverse('clawboard:connector_download_script')
    )
    if active_connection:
        config_token = signing.dumps(
            {'pk': active_connection.pk},
            salt='clawboard-install'
        )
        config_url = request.build_absolute_uri(
            reverse('clawboard:connector_config_token', args=[config_token])
        )

    return render(request, 'clawboard/connector/setup.html', {
        'connections': connections,
        'active_connection': active_connection,
        'config_url': config_url,
        'script_url': script_url,
        'cb_active': 'connector',
    })


def connector_download_script(request):
    """connector.py als Download (kein Login noetig - ist nur Code)"""
    connector_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'connector', 'connector.py'
    )

    with open(connector_path, 'r', encoding='utf-8') as f:
        content = f.read()

    response = HttpResponse(content, content_type='text/x-python')
    response['Content-Disposition'] = 'attachment; filename="connector.py"'
    return response


def connector_config_token(request, token):
    """Config-JSON via signiertem Token (24h gueltig, kein Login noetig)."""
    from django.core import signing

    try:
        data = signing.loads(token, salt='clawboard-install', max_age=86400)
    except (signing.BadSignature, signing.SignatureExpired):
        return HttpResponse('{"error": "Link abgelaufen oder ungueltig"}',
                            content_type='application/json', status=403)

    try:
        connection = ClawdbotConnection.objects.get(pk=data['pk'], is_active=True)
    except ClawdbotConnection.DoesNotExist:
        return HttpResponse('{"error": "Verbindung nicht gefunden"}',
                            content_type='application/json', status=404)

    config = json.dumps({
        'push_url': 'https://www.workloom.de/clawboard/api/push/',
        'connection_token': connection.gateway_token,
        'heartbeat_interval': 30,
        'reconnect_delay': 10,
        'workspace': '~/clawd',
    }, indent=2, ensure_ascii=False)

    response = HttpResponse(config, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="config.json"'
    return response


@login_required
def connector_download_config(request, pk):
    """Config-Datei mit vorausgefuelltem Token als Download"""
    connection = get_object_or_404(ClawdbotConnection, pk=pk, user=request.user)

    config = {
        'push_url': 'https://www.workloom.de/clawboard/api/push/',
        'connection_token': connection.gateway_token,
        'heartbeat_interval': 30,
        'reconnect_delay': 10,
        'workspace': '~/clawd',
    }

    content = json.dumps(config, indent=2, ensure_ascii=False)
    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="clawboard-connector.json"'
    return response


# === API Endpoints ===

@login_required
def api_status(request):
    """System-Status abrufen (für Live-Updates)"""
    connection_id = request.GET.get('connection')

    if not connection_id:
        return JsonResponse({'success': False, 'error': 'connection required'})

    connection = get_object_or_404(ClawdbotConnection, pk=connection_id, user=request.user)

    return JsonResponse({
        'success': True,
        'status': connection.status,
        'last_seen': connection.last_seen.isoformat() if connection.last_seen else None,
        'system': {
            'cpu': connection.cpu_percent,
            'ram_used': connection.ram_used_mb,
            'ram_total': connection.ram_total_mb,
            'disk_used': connection.disk_used_gb,
            'disk_total': connection.disk_total_gb,
        }
    })


@login_required
def api_sync(request):
    """Daten mit Clawdbot synchronisieren"""
    connection_id = request.GET.get('connection')

    if not connection_id:
        return JsonResponse({'success': False, 'error': 'connection required'})

    connection = get_object_or_404(ClawdbotConnection, pk=connection_id, user=request.user)

    # TODO: Tatsächliche Synchronisation implementieren
    # - Memory-Dateien vom Gateway abrufen
    # - Konversationen synchronisieren
    # - System-Status aktualisieren

    connection.last_seen = timezone.now()
    connection.save()

    return JsonResponse({
        'success': True,
        'message': 'Synchronisation gestartet',
    })


# === Connector HTTP Push API ===

@csrf_exempt
@require_http_methods(["POST"])
def api_connector_push(request):
    """
    HTTP Push Endpoint fuer den Connector.
    Der Connector sendet System-Daten, Memory-Files etc. per HTTP POST.
    Auth: Bearer Token im Authorization Header (= gateway_token)
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return JsonResponse(
            {'error': 'Authorization header required (Bearer <token>)'},
            status=401
        )

    token = auth_header[7:]

    # Connection per Token finden
    # EncryptedCharField unterstuetzt kein filter() - deshalb in Python vergleichen
    connection = None
    for conn in ClawdbotConnection.objects.filter(is_active=True):
        if conn.gateway_token == token:
            connection = conn
            break

    if not connection:
        return JsonResponse({'error': 'Invalid token'}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # System-Info aktualisieren
    system = data.get('system', {})
    gateway = data.get('gateway', {})

    connection.status = 'online'
    connection.last_seen = timezone.now()

    if system.get('cpu_percent') is not None:
        connection.cpu_percent = system['cpu_percent']
    if system.get('ram_used_mb') is not None:
        connection.ram_used_mb = int(system['ram_used_mb'])
    if system.get('ram_total_mb') is not None:
        connection.ram_total_mb = int(system['ram_total_mb'])
    if system.get('disk_used_gb') is not None:
        connection.disk_used_gb = round(system['disk_used_gb'], 2)
    if system.get('disk_total_gb') is not None:
        connection.disk_total_gb = round(system['disk_total_gb'], 2)

    if gateway.get('hostname'):
        connection.hostname = gateway['hostname']
    if gateway.get('version'):
        connection.gateway_version = gateway['version']

    connection.save()

    # Memory-Dateien verarbeiten
    # Emojis entfernen - MySQL utf8 unterstuetzt nur BMP (kein utf8mb4)
    emoji_re = re.compile(r'[\U00010000-\U0010ffff]')
    for mf in data.get('memory_files', []):
        if not mf.get('path'):
            continue
        content = emoji_re.sub('', mf.get('content', ''))
        MemoryFile.objects.update_or_create(
            connection=connection,
            path=mf['path'],
            defaults={
                'filename': mf.get('filename', os.path.basename(mf['path'])),
                'content': content,
                'size_bytes': mf.get('size', 0),
            }
        )

    # Conversations verarbeiten
    for conv in data.get('conversations', []):
        if not conv.get('session_key'):
            continue
        Conversation.objects.update_or_create(
            connection=connection,
            session_key=conv['session_key'],
            defaults={
                'title': emoji_re.sub('', conv.get('title', '')),
                'summary': emoji_re.sub('', conv.get('summary', '')),
                'messages': conv.get('messages', []),
                'message_count': conv.get('message_count', 0),
                'total_tokens': conv.get('total_tokens', 0),
                'total_cost': conv.get('total_cost', 0),
                'channel': conv.get('channel', ''),
                'started_at': conv.get('started_at', timezone.now()),
            }
        )

    # Projekte verarbeiten
    for proj in data.get('projects', []):
        if not proj.get('name'):
            continue
        Project.objects.update_or_create(
            connection=connection,
            name=proj['name'],
            defaults={
                'description': f"Auto-erkannt: {proj.get('type', 'unknown')} Projekt",
                'icon': proj.get('icon', ''),
                'status': 'active',
                'memory_path': proj.get('path', ''),
            }
        )

    # Skills verarbeiten
    for sk in data.get('skills', []):
        if not sk.get('name'):
            continue
        Skill.objects.update_or_create(
            connection=connection,
            name=sk['name'],
            defaults={
                'category': sk.get('category', 'tool'),
                'version': emoji_re.sub('', sk.get('version', '')),
                'icon': sk.get('icon', ''),
            }
        )

    # Integrations verarbeiten
    for integ in data.get('integrations', []):
        if not integ.get('name'):
            continue
        Integration.objects.update_or_create(
            connection=connection,
            name=integ['name'],
            defaults={
                'category': integ.get('category', 'cli'),
                'status': integ.get('status', 'active'),
                'icon': integ.get('icon', ''),
                'notes': emoji_re.sub('', integ.get('version', '')),
                'last_verified': timezone.now(),
            }
        )

    # Pending Command pruefen und mitschicken
    response_data = {
        'success': True,
        'connection_id': connection.pk,
    }
    if connection.pending_command:
        response_data['command'] = connection.pending_command
        connection.pending_command = ''
        connection.save(update_fields=['pending_command'])

    return JsonResponse(response_data)


@login_required
@require_http_methods(['POST'])
def api_connector_restart(request):
    """Setzt einen Restart-Befehl fuer den Connector."""
    connection = ClawdbotConnection.objects.filter(
        user=request.user, is_active=True
    ).first()
    if not connection:
        return JsonResponse({'error': 'Keine aktive Verbindung'}, status=404)

    connection.pending_command = 'restart'
    connection.save(update_fields=['pending_command'])
    return JsonResponse({'success': True, 'message': 'Neustart wird beim nächsten Push ausgeführt'})


@login_required
def api_dashboard_refresh(request):
    """Dashboard-Daten als JSON fuer AJAX-Refresh zurueckgeben"""
    connections = ClawdbotConnection.objects.filter(user=request.user, is_active=True)
    active = connections.first()

    if not active:
        return JsonResponse({
            'success': False,
            'error': 'no_connection',
        })

    # Online-Status pruefen (letzter Push < 5 Minuten)
    is_online = False
    last_seen_display = 'Nie'
    if active.last_seen:
        age_seconds = (timezone.now() - active.last_seen).total_seconds()
        is_online = age_seconds < 300
        # Menschenlesbarer Zeitstempel
        if age_seconds < 60:
            last_seen_display = 'Gerade eben'
        elif age_seconds < 3600:
            minutes = int(age_seconds / 60)
            last_seen_display = f'vor {minutes} Min.'
        elif age_seconds < 86400:
            hours = int(age_seconds / 3600)
            last_seen_display = f'vor {hours} Std.'
        else:
            days = int(age_seconds / 86400)
            last_seen_display = f'vor {days} Tagen'

    projects = list(Project.objects.filter(
        connection__user=request.user
    ).values('pk', 'name', 'status', 'icon', 'color')[:5])

    conversations_qs = Conversation.objects.filter(
        connection__user=request.user
    ).order_by('-started_at')[:5]
    conversations = []
    for conv in conversations_qs:
        age = (timezone.now() - conv.started_at).total_seconds() if conv.started_at else 0
        if age < 3600:
            age_display = f'vor {int(age / 60)} Min.'
        elif age < 86400:
            age_display = f'vor {int(age / 3600)} Std.'
        else:
            age_display = f'vor {int(age / 86400)} Tagen'
        conversations.append({
            'pk': conv.pk,
            'title': conv.title or 'Untitled',
            'message_count': conv.message_count,
            'channel': conv.channel or 'unknown',
            'age_display': age_display,
        })

    tasks = list(ScheduledTask.objects.filter(
        connection__user=request.user, is_enabled=True
    ).values('pk', 'name', 'schedule', 'next_run')[:5])

    integrations = list(Integration.objects.filter(
        connection__user=request.user
    ).values('pk', 'name', 'status', 'category', 'icon', 'notes'))

    skills = list(Skill.objects.filter(
        connection__user=request.user
    ).values('pk', 'name', 'category', 'version', 'icon'))

    # API-Services aus User-Profil
    api_services = _get_api_services(request.user)

    memory_count = MemoryFile.objects.filter(
        connection__user=request.user
    ).count()

    return JsonResponse({
        'success': True,
        'connection': {
            'id': active.pk,
            'name': active.name,
            'status': 'online' if is_online else active.status,
            'hostname': active.hostname,
            'last_seen': active.last_seen.isoformat() if active.last_seen else None,
            'last_seen_display': last_seen_display,
            'is_online': is_online,
        },
        'system': {
            'cpu': active.cpu_percent,
            'ram_used': active.ram_used_mb,
            'ram_total': active.ram_total_mb,
            'disk_used': active.disk_used_gb,
            'disk_total': active.disk_total_gb,
        },
        'projects': projects,
        'conversations': conversations,
        'tasks': tasks,
        'integrations': integrations,
        'api_services': api_services,
        'skills': skills,
        'memory_count': memory_count,
    })


# === KI Chat ===

@login_required
def chat_view(request, pk=None):
    """KI-Chat Seite"""
    chats = ClawboardChat.objects.filter(user=request.user)[:50]
    available_models = get_available_models_for_user(request.user)

    active_chat = None
    if pk:
        active_chat = get_object_or_404(ClawboardChat, pk=pk, user=request.user)

    return render(request, 'clawboard/chat.html', {
        'chats': chats,
        'active_chat': active_chat,
        'available_models': available_models,
        'cb_active': 'chat',
    })


@login_required
@require_http_methods(['POST'])
def api_chat_create(request):
    """Neuen KI-Chat erstellen"""
    data = json.loads(request.body)
    provider = data.get('provider', 'openai')
    model_name = data.get('model', 'gpt-4o-mini')
    title = data.get('title', '')

    chat = ClawboardChat.objects.create(
        user=request.user,
        provider=provider,
        model_name=model_name,
        title=title,
    )

    return JsonResponse({
        'success': True,
        'chat': {
            'id': chat.pk,
            'title': chat.title,
            'provider': chat.provider,
            'model_name': chat.model_name,
        }
    })


@login_required
@require_http_methods(['POST'])
def api_chat_send(request):
    """Nachricht senden und KI-Antwort erhalten"""
    data = json.loads(request.body)
    chat_id = data.get('chat_id')
    message = data.get('message', '').strip()

    if not message:
        return JsonResponse({'error': 'Nachricht darf nicht leer sein'}, status=400)

    chat = get_object_or_404(ClawboardChat, pk=chat_id, user=request.user)

    # User-Nachricht hinzufuegen
    now_str = timezone.now().isoformat()
    chat.messages.append({
        'role': 'user',
        'content': message,
        'timestamp': now_str,
    })

    # Auto-Titel beim ersten Nachricht
    if not chat.title and len(chat.messages) == 1:
        chat.title = message[:80]

    # KI aufrufen
    try:
        ai_response = call_ai_chat(
            user=request.user,
            provider=chat.provider,
            model=chat.model_name,
            messages=chat.messages,
        )
    except Exception as e:
        # Fehlernachricht als System-Message
        error_msg = f"Fehler: {str(e)}"
        chat.messages.append({
            'role': 'assistant',
            'content': error_msg,
            'timestamp': timezone.now().isoformat(),
            'error': True,
        })
        chat.message_count = len([m for m in chat.messages if m['role'] in ('user', 'assistant')])
        chat.save()
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'chat_title': chat.title,
        })

    # KI-Antwort hinzufuegen
    chat.messages.append({
        'role': 'assistant',
        'content': ai_response or '',
        'timestamp': timezone.now().isoformat(),
    })
    chat.message_count = len([m for m in chat.messages if m['role'] in ('user', 'assistant')])
    chat.save()

    return JsonResponse({
        'success': True,
        'response': ai_response,
        'chat_title': chat.title,
        'message_count': chat.message_count,
    })


@login_required
def api_chat_messages(request, pk):
    """Nachrichten eines Chats laden"""
    chat = get_object_or_404(ClawboardChat, pk=pk, user=request.user)
    return JsonResponse({
        'success': True,
        'chat': {
            'id': chat.pk,
            'title': chat.title,
            'provider': chat.provider,
            'model_name': chat.model_name,
            'messages': chat.messages,
            'message_count': chat.message_count,
        }
    })


@login_required
@require_http_methods(['POST'])
def api_chat_delete(request, pk):
    """Chat loeschen"""
    chat = get_object_or_404(ClawboardChat, pk=pk, user=request.user)
    chat.delete()
    return JsonResponse({'success': True})
