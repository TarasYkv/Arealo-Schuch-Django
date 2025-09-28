from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
import json

from .models import TodoList, Todo, TodoAssignment, TodoComment, TodoActivity
from payments.feature_access import require_subscription_access

User = get_user_model()


@login_required
@require_subscription_access('todos')
def todo_home(request):
    """Übersichtsseite mit allen Listen des Benutzers"""
    # Listen die der Benutzer erstellt hat oder zu denen er Zugriff hat
    my_lists = TodoList.objects.filter(
        Q(created_by=request.user) | Q(shared_with=request.user)
    ).distinct().annotate(
        todo_count=Count('todos'),
        completed_count=Count('todos', filter=Q(todos__status='completed'))
    )
    
    # Meine zugeordneten ToDos
    my_todos = Todo.objects.filter(
        assignments__user=request.user
    ).exclude(status='completed').select_related('todo_list').order_by('-priority', 'due_date')[:10]
    
    # Überfällige ToDos
    overdue_todos = Todo.objects.filter(
        assignments__user=request.user,
        due_date__lt=timezone.now(),
        status__in=['pending', 'in_progress']
    ).select_related('todo_list').count()
    
    context = {
        'my_lists': my_lists,
        'my_todos': my_todos,
        'overdue_todos': overdue_todos,
    }
    return render(request, 'todos/home.html', context)


@login_required
def list_detail(request, pk):
    """Detailansicht einer ToDo-Liste"""
    todo_list = get_object_or_404(TodoList, pk=pk)
    
    # Zugriffsprüfung
    if not todo_list.can_user_access(request.user):
        messages.error(request, 'Sie haben keinen Zugriff auf diese Liste.')
        return redirect('todos:home')
    
    # Filter-Parameter
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    assigned_filter = request.GET.get('assigned', 'all')
    
    # ToDos filtern
    todos = todo_list.todos.all()
    
    if status_filter != 'all':
        todos = todos.filter(status=status_filter)
    
    if priority_filter != 'all':
        todos = todos.filter(priority=priority_filter)
    
    if assigned_filter != 'all':
        if assigned_filter == 'me':
            todos = todos.filter(assignments__user=request.user)
        elif assigned_filter == 'unassigned':
            todos = todos.filter(assignments__isnull=True)
    
    # Sortierung
    sort_by = request.GET.get('sort', 'priority')
    if sort_by == 'due_date':
        todos = todos.order_by('due_date', '-priority')
    elif sort_by == 'created':
        todos = todos.order_by('-created_at')
    elif sort_by == 'status':
        todos = todos.order_by('status', '-priority')
    else:  # priority
        todos = todos.order_by('-priority', 'due_date')
    
    # Pagination
    paginator = Paginator(todos, 20)
    page_number = request.GET.get('page')
    todos_page = paginator.get_page(page_number)
    
    # Benutzer die Zugriff auf die Liste haben
    available_users = todo_list.get_all_users()
    
    context = {
        'todo_list': todo_list,
        'todos': todos_page,
        'available_users': available_users,
        'can_edit': todo_list.can_user_edit(request.user),
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assigned_filter': assigned_filter,
        'sort_by': sort_by,
    }
    return render(request, 'todos/list_detail.html', context)


@login_required
def create_list(request):
    """Neue ToDo-Liste erstellen"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        shared_users = request.POST.getlist('shared_with')

        if not title:
            messages.error(request, 'Bitte geben Sie einen Titel ein.')
            return redirect('todos:home')

        # Liste erstellen
        todo_list = TodoList.objects.create(
            title=title,
            description=description,
            created_by=request.user,
            is_public=False
        )

        # Benutzer hinzufügen
        if shared_users:
            users = User.objects.filter(id__in=shared_users)
            todo_list.shared_with.set(users)

        messages.success(request, f'Liste "{title}" wurde erfolgreich erstellt.')
        return redirect('todos:list_detail', pk=todo_list.pk)

    # Keine Benutzer mehr vorladen - wird per AJAX geladen
    context = {}
    return render(request, 'todos/create_list.html', context)


@login_required
def create_todo(request, list_pk):
    """Neues ToDo erstellen"""
    todo_list = get_object_or_404(TodoList, pk=list_pk)
    
    # Bearbeitungsrechte prüfen
    if not todo_list.can_user_edit(request.user):
        messages.error(request, 'Sie haben keine Berechtigung, ToDos zu dieser Liste hinzuzufügen.')
        return redirect('todos:list_detail', pk=list_pk)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'medium')
        due_date = request.POST.get('due_date')
        assigned_users = request.POST.getlist('assigned_to')
        
        if not title:
            messages.error(request, 'Bitte geben Sie einen Titel ein.')
            return redirect('todos:list_detail', pk=list_pk)
        
        # ToDo erstellen
        todo = Todo.objects.create(
            todo_list=todo_list,
            title=title,
            description=description,
            priority=priority,
            created_by=request.user,
            due_date=due_date if due_date else None
        )
        
        # Benutzer zuordnen
        if assigned_users:
            for user_id in assigned_users:
                try:
                    user = User.objects.get(id=user_id)
                    TodoAssignment.objects.create(
                        todo=todo,
                        user=user,
                        assigned_by=request.user
                    )
                except User.DoesNotExist:
                    continue
        
        # Aktivität protokollieren
        TodoActivity.objects.create(
            todo=todo,
            user=request.user,
            activity_type='created',
            description=f'ToDo "{title}" wurde erstellt'
        )
        
        messages.success(request, f'ToDo "{title}" wurde erfolgreich erstellt.')
        return redirect('todos:list_detail', pk=list_pk)
    
    # Verfügbare Benutzer
    available_users = todo_list.get_all_users()
    
    context = {
        'todo_list': todo_list,
        'available_users': available_users,
    }
    return render(request, 'todos/create_todo.html', context)


@login_required
@require_http_methods(["POST"])
def update_todo_status(request, pk):
    """ToDo-Status per AJAX aktualisieren"""
    todo = get_object_or_404(Todo, pk=pk)
    
    # Prüfe ob Benutzer berechtigt ist
    if not todo.todo_list.can_user_edit(request.user):
        return JsonResponse({'success': False, 'error': 'Keine Berechtigung'})
    
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status not in ['pending', 'in_progress', 'completed']:
            return JsonResponse({'success': False, 'error': 'Ungültiger Status'})
        
        old_status = todo.status
        todo.status = new_status
        todo.save()
        
        # Aktivität protokollieren
        TodoActivity.objects.create(
            todo=todo,
            user=request.user,
            activity_type='status_changed',
            description=f'Status von "{todo.get_status_display()}" zu "{todo.get_status_display()}" geändert',
            metadata={'old_status': old_status, 'new_status': new_status}
        )
        
        return JsonResponse({
            'success': True,
            'status': new_status,
            'status_display': todo.get_status_display(),
            'completed_at': todo.completed_at.isoformat() if todo.completed_at else None
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def assign_todo(request, pk):
    """ToDo einem Benutzer zuordnen per AJAX"""
    todo = get_object_or_404(Todo, pk=pk)
    
    # Prüfe ob Benutzer berechtigt ist
    if not todo.todo_list.can_user_edit(request.user):
        return JsonResponse({'success': False, 'error': 'Keine Berechtigung'})
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        action = data.get('action', 'assign')  # assign oder unassign
        
        if action == 'assign':
            user = get_object_or_404(User, pk=user_id)
            
            # Prüfe ob Benutzer Zugriff auf die Liste hat
            if user not in todo.todo_list.get_all_users():
                return JsonResponse({'success': False, 'error': 'Benutzer hat keinen Zugriff auf diese Liste'})
            
            assignment, created = TodoAssignment.objects.get_or_create(
                todo=todo,
                user=user,
                defaults={'assigned_by': request.user}
            )
            
            if created:
                # Aktivität protokollieren
                TodoActivity.objects.create(
                    todo=todo,
                    user=request.user,
                    activity_type='assigned',
                    description=f'ToDo wurde {user.get_full_name() or user.username} zugeordnet'
                )
                
                return JsonResponse({
                    'success': True,
                    'action': 'assigned',
                    'user_name': user.get_full_name() or user.username,
                    'assigned_users': todo.get_assigned_users_display()
                })
            else:
                return JsonResponse({'success': False, 'error': 'Benutzer ist bereits zugeordnet'})
        
        elif action == 'unassign':
            user = get_object_or_404(User, pk=user_id)
            assignment = TodoAssignment.objects.filter(todo=todo, user=user).first()
            
            if assignment:
                assignment.delete()
                
                # Aktivität protokollieren
                TodoActivity.objects.create(
                    todo=todo,
                    user=request.user,
                    activity_type='unassigned',
                    description=f'Zuordnung zu {user.get_full_name() or user.username} wurde entfernt'
                )
                
                return JsonResponse({
                    'success': True,
                    'action': 'unassigned',
                    'user_name': user.get_full_name() or user.username,
                    'assigned_users': todo.get_assigned_users_display()
                })
            else:
                return JsonResponse({'success': False, 'error': 'Benutzer ist nicht zugeordnet'})
        
        else:
            return JsonResponse({'success': False, 'error': 'Ungültige Aktion'})
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def todo_detail(request, pk):
    """Detailansicht eines ToDos"""
    todo = get_object_or_404(Todo, pk=pk)
    
    # Zugriffsprüfung
    if not todo.todo_list.can_user_access(request.user):
        messages.error(request, 'Sie haben keinen Zugriff auf dieses ToDo.')
        return redirect('todos:home')
    
    # Kommentare laden
    comments = todo.comments.select_related('user').order_by('created_at')
    
    # Aktivitäten laden
    activities = todo.activities.select_related('user').order_by('-created_at')[:20]
    
    context = {
        'todo': todo,
        'comments': comments,
        'activities': activities,
        'can_edit': todo.todo_list.can_user_edit(request.user),
        'available_users': todo.todo_list.get_all_users(),
    }
    return render(request, 'todos/todo_detail.html', context)


@login_required
@require_http_methods(["POST"])
def add_comment(request, pk):
    """Kommentar zu einem ToDo hinzufügen"""
    todo = get_object_or_404(Todo, pk=pk)
    
    # Zugriffsprüfung
    if not todo.todo_list.can_user_access(request.user):
        return JsonResponse({'success': False, 'error': 'Keine Berechtigung'})
    
    content = request.POST.get('content', '').strip()
    
    if not content:
        return JsonResponse({'success': False, 'error': 'Kommentar darf nicht leer sein'})
    
    comment = TodoComment.objects.create(
        todo=todo,
        user=request.user,
        content=content
    )
    
    # Aktivität protokollieren
    TodoActivity.objects.create(
        todo=todo,
        user=request.user,
        activity_type='commented',
        description=f'Kommentar hinzugefügt'
    )
    
    return JsonResponse({
        'success': True,
        'comment_id': comment.id,
        'user_name': request.user.get_full_name() or request.user.username,
        'content': comment.content,
        'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
    })


@login_required
def my_todos(request):
    """Alle dem Benutzer zugeordneten ToDos"""
    # Filter-Parameter
    status_filter = request.GET.get('status', 'active')  # active, completed, all

    # Basis-Query
    todos = Todo.objects.filter(assignments__user=request.user).select_related('todo_list')

    if status_filter == 'active':
        todos = todos.exclude(status='completed')
    elif status_filter == 'completed':
        todos = todos.filter(status='completed')
    # 'all' zeigt alle an

    # Sortierung
    todos = todos.order_by('-priority', 'due_date', '-created_at')

    # Pagination
    paginator = Paginator(todos, 20)
    page_number = request.GET.get('page')
    todos_page = paginator.get_page(page_number)

    context = {
        'todos': todos_page,
        'status_filter': status_filter,
    }
    return render(request, 'todos/my_todos.html', context)


@login_required
def search_users(request):
    """AJAX-Endpunkt für die Benutzersuche"""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Nur GET-Requests erlaubt'})

    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'success': True, 'users': []})

    # Benutzer suchen (außer dem aktuellen Benutzer)
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).exclude(id=request.user.id).order_by('first_name', 'last_name', 'username')[:10]

    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'username': user.username,
            'full_name': user.get_full_name(),
            'display_name': user.get_full_name() or user.username,
            'email': user.email
        })

    return JsonResponse({'success': True, 'users': user_list})