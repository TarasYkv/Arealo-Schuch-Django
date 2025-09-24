"""
LoomLine Views - Einfache SEO-Projekt Timeline
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.db import models
from django.db.models import Prefetch
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse, Http404
from datetime import timedelta, datetime
from .models import Project, TaskEntry, ScheduledNotification
from .forms import ProjectForm, TaskEntryForm, QuickTaskEntryForm, AddMemberForm

User = get_user_model()


class ProjectListView(LoginRequiredMixin, ListView):
    """Liste aller Projekte des Benutzers"""
    model = Project
    template_name = 'loomline/project_list.html'
    context_object_name = 'projects'

    def get_queryset(self):
        # Zeige Projekte die der User besitzt oder bei denen er Mitglied ist
        user = self.request.user
        return Project.objects.filter(
            models.Q(owner=user) | models.Q(members=user),
            is_active=True
        ).distinct()


class ProjectDetailView(LoginRequiredMixin, DetailView):
    """Projekt-Timeline mit allen erledigten Aufgaben"""
    model = Project
    template_name = 'loomline/project_detail.html'
    context_object_name = 'project'

    def get_object(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        if not project.can_access(self.request.user):
            messages.error(self.request, 'Sie haben keinen Zugriff auf dieses Projekt.')
            return redirect('loomline:project-list')
        return project

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tasks'] = self.object.tasks.all()
        context['task_form'] = TaskEntryForm()
        context['can_edit'] = self.object.can_edit(self.request.user)
        context['add_member_form'] = AddMemberForm()
        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    """Neues Projekt erstellen"""
    model = Project
    form_class = ProjectForm
    template_name = 'loomline/project_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, 'Projekt erfolgreich erstellt!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('loomline:project-detail', kwargs={'pk': self.object.pk})


@login_required
def add_task(request, project_id):
    """Neue erledigte Aufgabe hinzufügen"""
    project = get_object_or_404(Project, pk=project_id, owner=request.user)

    if request.method == 'POST':
        form = TaskEntryForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.completed_by = request.user
            # Wenn completed_at leer ist, aktuellen Zeitstempel setzen
            if not task.completed_at:
                task.completed_at = timezone.now()
            task.save()
            messages.success(request, 'Aufgabe erfolgreich hinzugefügt!')
        else:
            messages.error(request, 'Fehler beim Hinzufügen der Aufgabe.')

    return redirect('loomline:project-detail', pk=project_id)


@login_required
def dashboard(request):
    """Einfaches Dashboard mit Projektübersicht"""
    # Zeige Projekte die der User besitzt oder bei denen er Mitglied ist
    user = request.user
    projects = Project.objects.filter(
        models.Q(owner=user) | models.Q(members=user),
        is_active=True
    ).distinct()[:5]

    # Zeige Tasks aus allen Projekten zu denen der User Zugang hat
    recent_tasks = TaskEntry.objects.filter(
        models.Q(project__owner=user) | models.Q(project__members=user)
    ).select_related('project').distinct()[:10]

    # Total counts für alle zugänglichen Projekte
    total_projects = Project.objects.filter(
        models.Q(owner=user) | models.Q(members=user),
        is_active=True
    ).distinct().count()

    total_tasks = TaskEntry.objects.filter(
        models.Q(project__owner=user) | models.Q(project__members=user)
    ).distinct().count()

    context = {
        'projects': projects,
        'recent_tasks': recent_tasks,
        'total_projects': total_projects,
        'total_tasks': total_tasks,
    }

    return render(request, 'loomline/dashboard.html', context)


@login_required
def quick_add_task(request):
    """Schnell eine neue Aufgabe hinzufügen"""
    user_projects = Project.objects.filter(owner=request.user, is_active=True)

    if request.method == 'POST':
        form = QuickTaskEntryForm(user=request.user, data=request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.completed_by = request.user
            # Wenn completed_at leer ist, aktuellen Zeitstempel setzen
            if not task.completed_at:
                task.completed_at = timezone.now()
            task.save()
            messages.success(request, f'Aufgabe "{task.title}" erfolgreich eingetragen!')
            # Wenn Request von Modal kommt, zur Übersicht zurück
            if request.headers.get('HX-Request') or 'modal' in request.POST:
                return redirect('loomline:tasks-tiles')
            return redirect('loomline:project-detail', pk=task.project.pk)
        else:
            messages.error(request, 'Fehler beim Eintragen der Aufgabe.')
    else:
        form = QuickTaskEntryForm(user=request.user)

    context = {
        'form': form,
        'user_projects': user_projects,
    }

    return render(request, 'loomline/quick_add_task.html', context)


@login_required
def add_member_to_project(request, project_id):
    """Mitglied zu Projekt hinzufügen"""
    project = get_object_or_404(Project, pk=project_id)

    # Nur Owner kann Mitglieder hinzufügen
    if not project.can_edit(request.user):
        messages.error(request, 'Sie haben keine Berechtigung, Mitglieder zu diesem Projekt hinzuzufügen.')
        return redirect('loomline:project-detail', pk=project_id)

    if request.method == 'POST':
        form = AddMemberForm(request.POST)
        if form.is_valid():
            new_member = form.get_user()

            # Prüfen ob User bereits Mitglied ist
            if new_member == project.owner:
                messages.warning(request, 'Der Projektbesitzer ist automatisch berechtigt.')
            elif new_member in project.members.all():
                messages.warning(request, f'{new_member.username} ist bereits Mitglied dieses Projekts.')
            else:
                project.members.add(new_member)
                messages.success(request, f'{new_member.username} wurde als Mitglied hinzugefügt!')
        else:
            messages.error(request, 'Fehler beim Hinzufügen des Mitglieds.')

    return redirect('loomline:project-detail', pk=project_id)


@login_required
def remove_member_from_project(request, project_id, user_id):
    """Mitglied aus Projekt entfernen"""
    project = get_object_or_404(Project, pk=project_id)

    # Nur Owner kann Mitglieder entfernen
    if not project.can_edit(request.user):
        messages.error(request, 'Sie haben keine Berechtigung, Mitglieder aus diesem Projekt zu entfernen.')
        return redirect('loomline:project-detail', pk=project_id)

    user_to_remove = get_object_or_404(User, pk=user_id)

    if user_to_remove in project.members.all():
        project.members.remove(user_to_remove)
        messages.success(request, f'{user_to_remove.username} wurde aus dem Projekt entfernt.')
    else:
        messages.warning(request, f'{user_to_remove.username} ist kein Mitglied dieses Projekts.')

    return redirect('loomline:project-detail', pk=project_id)


@login_required
def tasks_tiles_view(request):
    """Moderne Kachelansicht für alle Aufgaben"""
    # Grundlegende Aufgaben-Query - nur Projekte wo User Zugriff hat und nur Hauptaufgaben
    user = request.user
    base_tasks = TaskEntry.objects.filter(
        models.Q(project__owner=user) | models.Q(project__members=user),
        parent_task__isnull=True  # Nur Hauptaufgaben, keine Sub-Aufgaben
    ).select_related('project', 'completed_by').prefetch_related(
        Prefetch('subtasks', queryset=TaskEntry.objects.order_by('-completed_at').prefetch_related('notifications')),
        'notifications'  # Lade auch Benachrichtigungen für Hauptaufgaben
    ).order_by('-completed_at')

    # Filter anwenden
    tasks = base_tasks
    project_filter = request.GET.get('project')
    timeframe_filter = request.GET.get('timeframe')
    user_filter = request.GET.get('user')

    if project_filter:
        tasks = tasks.filter(project_id=project_filter)

    if timeframe_filter:
        now = timezone.now()
        if timeframe_filter == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            tasks = tasks.filter(completed_at__gte=start_date)
        elif timeframe_filter == 'week':
            start_date = now - timedelta(days=7)
            tasks = tasks.filter(completed_at__gte=start_date)
        elif timeframe_filter == 'month':
            start_date = now - timedelta(days=30)
            tasks = tasks.filter(completed_at__gte=start_date)

    if user_filter:
        tasks = tasks.filter(completed_by_id=user_filter)

    # Pagination
    paginator = Paginator(tasks, 24)  # 24 Kacheln pro Seite
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiken berechnen
    total_tasks = base_tasks.count()

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tasks_today = base_tasks.filter(completed_at__gte=today_start).count()

    week_start = timezone.now() - timedelta(days=7)
    tasks_this_week = base_tasks.filter(completed_at__gte=week_start).count()

    active_projects = Project.objects.filter(
        models.Q(owner=user) | models.Q(members=user),
        is_active=True
    ).count()

    # Verfügbare Projekte und Benutzer für Filter
    user_projects = Project.objects.filter(
        models.Q(owner=user) | models.Q(members=user),
        is_active=True
    ).order_by('name')

    # Alle Benutzer die in zugänglichen Projekten Aufgaben haben
    all_users = User.objects.filter(
        taskentry__project__in=user_projects
    ).distinct().order_by('username')

    context = {
        'tasks': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total_tasks': total_tasks,
        'tasks_today': tasks_today,
        'tasks_this_week': tasks_this_week,
        'active_projects': active_projects,
        'user_projects': user_projects,
        'all_users': all_users,
    }

    return render(request, 'loomline/tasks_tiles.html', context)


class TaskDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer einzelnen Aufgabe"""
    model = TaskEntry
    template_name = 'loomline/task_detail.html'
    context_object_name = 'task'

    def get_object(self):
        task = get_object_or_404(TaskEntry, pk=self.kwargs['pk'])
        if not task.project.can_access(self.request.user):
            messages.error(self.request, 'Sie haben keinen Zugriff auf diese Aufgabe.')
            return redirect('loomline:tasks-tiles')
        return task


@login_required
def add_subtask(request):
    """Sub-Aufgabe zu einer Hauptaufgabe hinzufügen"""
    if request.method == 'POST':
        parent_task_id = request.POST.get('parent_task_id')

        # Überprüfe ob Parent-Task existiert und User Zugriff hat
        try:
            parent_task = get_object_or_404(TaskEntry, pk=parent_task_id)
            if not parent_task.project.can_access(request.user):
                messages.error(request, 'Sie haben keinen Zugriff auf diese Aufgabe.')
                return redirect('loomline:tasks-tiles')
        except (ValueError, TaskEntry.DoesNotExist):
            messages.error(request, 'Ungültige übergeordnete Aufgabe.')
            return redirect('loomline:tasks-tiles')

        # Erstelle Sub-Aufgabe
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        completed_at_str = request.POST.get('completed_at')
        notification_datetime_str = request.POST.get('notification_datetime')

        # Debug logging
        print(f"[DEBUG] Creating subtask - notification_datetime received: {notification_datetime_str}")

        if title:
            try:
                # Datums-String in ein für Django gültiges, zeitzoneninformiertes Datum umwandeln
                if completed_at_str:
                    try:
                        completed_at_dt = datetime.fromisoformat(completed_at_str)
                        final_completed_at = timezone.make_aware(completed_at_dt)
                    except (ValueError, TypeError):
                        final_completed_at = timezone.now() # Fallback
                else:
                    final_completed_at = timezone.now()

                subtask = TaskEntry.objects.create(
                    project=parent_task.project,
                    title=title,
                    description=description,
                    completed_by=request.user,
                    parent_task=parent_task,
                    completed_at=final_completed_at
                )

                # Create notification if datetime is provided
                if notification_datetime_str:
                    print(f"[DEBUG] Creating notification for subtask {subtask.id}")
                    try:
                        send_at_dt = datetime.fromisoformat(notification_datetime_str)
                        # Make timezone aware
                        send_at_aware = timezone.make_aware(send_at_dt)
                        print(f"[DEBUG] Notification time parsed: {send_at_aware}")

                        notification = ScheduledNotification.objects.create(
                            user_to_notify=request.user,
                            task_entry=subtask,
                            message=f'Erinnerung für deine Sub-Aufgabe: "{subtask.title}"',
                            send_at=send_at_aware
                        )
                        print(f"[DEBUG] Notification created with ID: {notification.id}")
                        messages.success(request, f'Sub-Aufgabe "{subtask.title}" mit Erinnerung erstellt!')
                    except (ValueError, TypeError) as e:
                        print(f"[DEBUG] Error creating notification: {e}")
                        messages.warning(request, "Ungültiges Datumsformat für die Erinnerung.")
                else:
                     messages.success(request, f'Sub-Aufgabe "{subtask.title}" erfolgreich hinzugefügt!')
            except Exception as e:
                messages.error(request, f"Ein unerwarteter Fehler ist aufgetreten: {str(e)}")
        else:
            messages.error(request, 'Titel ist erforderlich.')

    return redirect('loomline:tasks-tiles')


@login_required
def delete_task(request, task_id):
    """Hauptaufgabe löschen"""
    if request.method == 'POST':
        task = get_object_or_404(TaskEntry, pk=task_id, parent_task__isnull=True)

        # Prüfen ob User Berechtigung hat (Owner oder Mitglied des Projekts)
        if not task.project.can_access(request.user):
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'message': 'Sie haben keine Berechtigung, diese Aufgabe zu löschen.'
                })
            messages.error(request, 'Sie haben keine Berechtigung, diese Aufgabe zu löschen.')
            return redirect('loomline:tasks-tiles')

        task_title = task.title
        task.delete()

        # JSON-Anfrage für AJAX
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': f'Aufgabe "{task_title}" wurde gelöscht.'
            })

        messages.success(request, f'Aufgabe "{task_title}" wurde gelöscht.')

    return redirect('loomline:tasks-tiles')


@login_required
def delete_subtask(request, subtask_id):
    """Sub-Aufgabe löschen"""
    if request.method == 'POST':
        subtask = get_object_or_404(TaskEntry, pk=subtask_id, parent_task__isnull=False)

        # Prüfen ob User Berechtigung hat (Owner oder Mitglied des Projekts)
        if not subtask.project.can_access(request.user):
            messages.error(request, 'Sie haben keine Berechtigung, diese Sub-Aufgabe zu löschen.')
            return redirect('loomline:tasks-tiles')

        subtask_title = subtask.title
        subtask.delete()
        messages.success(request, f'Sub-Aufgabe "{subtask_title}" wurde gelöscht.')

    return redirect('loomline:tasks-tiles')


@login_required
def edit_task(request, task_id):
    """Aufgabe bearbeiten (Haupt- oder Subtask)"""
    task = get_object_or_404(TaskEntry, pk=task_id)

    # Prüfen ob User Berechtigung hat (Owner oder Mitglied des Projekts)
    if not task.project.can_access(request.user):
        messages.error(request, 'Sie haben keine Berechtigung, diese Aufgabe zu bearbeiten.')
        return redirect('loomline:tasks-tiles')

    if request.method == 'POST':
        # JSON-Anfrage für AJAX
        if request.headers.get('Content-Type') == 'application/json':
            import json
            data = json.loads(request.body)

            task.title = data.get('title', task.title)
            task.description = data.get('description', task.description)

            # Optional: completed_at aktualisieren
            if 'completed_at' in data:
                from datetime import datetime
                try:
                    task.completed_at = datetime.fromisoformat(data['completed_at'])
                except (ValueError, TypeError):
                    pass

            task.save()

            return JsonResponse({
                'success': True,
                'message': f'Aufgabe "{task.title}" wurde aktualisiert.'
            })

        # Normale POST-Anfrage (Formular)
        else:
            form = TaskEntryForm(request.POST, instance=task)
            if form.is_valid():
                form.save()
                messages.success(request, f'Aufgabe "{task.title}" wurde aktualisiert.')
                return redirect('loomline:tasks-tiles')
    else:
        form = TaskEntryForm(instance=task)

    context = {
        'form': form,
        'task': task,
    }
    return render(request, 'loomline/edit_task.html', context)


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """Projekt bearbeiten"""
    model = Project
    form_class = ProjectForm
    template_name = 'loomline/project_form.html'

    def get_object(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        if not project.can_access(self.request.user):
            messages.error(self.request, 'Sie haben keine Berechtigung, dieses Projekt zu bearbeiten.')
            raise Http404
        return project

    def form_valid(self, form):
        messages.success(self.request, f'Projekt "{form.instance.name}" wurde erfolgreich aktualisiert!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('loomline:project-detail', kwargs={'pk': self.object.pk})


@login_required
def project_delete(request, pk):
    """Projekt löschen"""
    project = get_object_or_404(Project, pk=pk)

    # Prüfen ob User Berechtigung hat (nur Owner kann löschen)
    if project.owner != request.user:
        messages.error(request, 'Nur der Projektbesitzer kann das Projekt löschen.')
        return redirect('loomline:project-list')

    if request.method == 'POST':
        project_name = project.name
        project.delete()
        messages.success(request, f'Projekt "{project_name}" wurde erfolgreich gelöscht.')
        return redirect('loomline:project-list')

    # GET request - sollte nicht passieren, aber für Sicherheit
    return redirect('loomline:project-list')