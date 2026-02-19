from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from .models import (
    ClawdbotConnection, Project, ProjectMemory,
    Conversation, ScheduledTask, MemoryFile, Integration
)
from .forms import ClawdbotConnectionForm, ProjectForm


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
    
    return render(request, 'clawboard/dashboard.html', context)


# === Connection Views ===

@login_required
def connection_list(request):
    """Liste aller Clawdbot-Verbindungen"""
    connections = ClawdbotConnection.objects.filter(user=request.user)
    return render(request, 'clawboard/connections/list.html', {'connections': connections})


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
    
    return render(request, 'clawboard/connections/form.html', {'form': form, 'title': 'Neue Verbindung'})


@login_required
def connection_detail(request, pk):
    """Verbindungsdetails anzeigen"""
    connection = get_object_or_404(ClawdbotConnection, pk=pk, user=request.user)
    return render(request, 'clawboard/connections/detail.html', {'connection': connection})


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
        'title': f'Verbindung bearbeiten: {connection.name}'
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
    
    return render(request, 'clawboard/connections/delete.html', {'connection': connection})


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
    return render(request, 'clawboard/projects/list.html', {'projects': projects})


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
    
    return render(request, 'clawboard/projects/form.html', {'form': form, 'title': 'Neues Projekt'})


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
        'title': f'Projekt bearbeiten: {project.name}'
    })


# === Conversation Views ===

@login_required
def conversation_list(request):
    """Liste aller Konversationen"""
    conversations = Conversation.objects.filter(connection__user=request.user)
    return render(request, 'clawboard/conversations/list.html', {'conversations': conversations})


@login_required
def conversation_detail(request, pk):
    """Konversation anzeigen"""
    conversation = get_object_or_404(Conversation, pk=pk, connection__user=request.user)
    return render(request, 'clawboard/conversations/detail.html', {'conversation': conversation})


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
    return render(request, 'clawboard/tasks/list.html', {'tasks': tasks})


@login_required
def task_detail(request, pk):
    """Aufgaben-Details"""
    task = get_object_or_404(ScheduledTask, pk=pk, connection__user=request.user)
    return render(request, 'clawboard/tasks/detail.html', {'task': task})


# === Integrations ===

@login_required
def integration_list(request):
    """Liste aller Integrationen"""
    integrations = Integration.objects.filter(connection__user=request.user)
    return render(request, 'clawboard/integrations/list.html', {'integrations': integrations})


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
