from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Note, Event, EventParticipant, IdeaBoard, BoardElement, EventReminder, VideoCall, CallParticipant, BoardAudioSession, BoardAudioParticipant
from .agora_utils import generate_agora_token, get_agora_config, CallRoles
from PIL import Image, UnidentifiedImageError
import json
import os
import re
import uuid

User = get_user_model()


@login_required
def organization_dashboard(request):
    """Dashboard für die Organisations-App."""
    # Aktuelle Notizen des Benutzers
    user_notes = Note.objects.filter(
        Q(author=request.user) | Q(mentioned_users=request.user)
    ).distinct()[:5]
    
    # Nächste Termine
    upcoming_events = Event.objects.filter(
        Q(organizer=request.user) | Q(participants=request.user),
        start_time__gte=timezone.now()
    ).distinct().order_by('start_time')[:5]
    
    # Benutzer-Ideenboards
    user_boards = IdeaBoard.objects.filter(
        Q(creator=request.user) | Q(collaborators=request.user)
    ).distinct()[:5]
    
    # Ausstehende Terminanfragen
    pending_invitations = EventParticipant.objects.filter(
        user=request.user,
        response='pending'
    )[:5]
    
    context = {
        'user_notes': user_notes,
        'upcoming_events': upcoming_events,
        'user_boards': user_boards,
        'pending_invitations': pending_invitations,
    }
    return render(request, 'organization/dashboard.html', context)


@login_required
def note_list(request):
    """Liste aller Notizen des Benutzers."""
    notes = Note.objects.filter(
        Q(author=request.user) | Q(mentioned_users=request.user)
    ).distinct().order_by('-updated_at')
    
    paginator = Paginator(notes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'organization/note_list.html', {'page_obj': page_obj})


@login_required
def note_detail(request, pk):
    """Detailansicht einer Notiz."""
    note = get_object_or_404(Note, pk=pk)
    
    # Zugriffsberechtigung prüfen
    if not (note.author == request.user or request.user in note.mentioned_users.all() or note.is_public):
        messages.error(request, "Sie haben keine Berechtigung, diese Notiz zu sehen.")
        return redirect('organization:note_list')
    
    return render(request, 'organization/note_detail.html', {'note': note})


@login_required
def note_create(request):
    """Erstelle eine neue Notiz."""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        is_public = request.POST.get('is_public') == 'on'
        image = request.FILES.get('image')
        
        if title:
            note = Note.objects.create(
                title=title,
                content=content,
                author=request.user,
                is_public=is_public,
                image=image
            )
            messages.success(request, "Notiz erfolgreich erstellt!")
            return redirect('organization:note_detail', pk=note.pk)
        else:
            messages.error(request, "Titel ist erforderlich.")
    
    return render(request, 'organization/note_form.html')


@login_required
def note_edit(request, pk):
    """Bearbeite eine existierende Notiz."""
    note = get_object_or_404(Note, pk=pk)
    
    if note.author != request.user:
        messages.error(request, "Sie können nur eigene Notizen bearbeiten.")
        return redirect('organization:note_detail', pk=pk)
    
    if request.method == 'POST':
        note.title = request.POST.get('title', note.title)
        note.content = request.POST.get('content', note.content)
        note.is_public = request.POST.get('is_public') == 'on'
        
        if request.FILES.get('image'):
            note.image = request.FILES.get('image')
        
        note.save()
        messages.success(request, "Notiz erfolgreich aktualisiert!")
        return redirect('organization:note_detail', pk=pk)
    
    return render(request, 'organization/note_form.html', {'note': note})


@login_required
def calendar_view(request):
    """Kalenderansicht mit verschiedenen Ansichtsmodi."""
    from datetime import datetime, timedelta, date
    from calendar import monthrange, month_name
    import calendar
    
    # Ansichtsmodus aus GET-Parameter
    view_mode = request.GET.get('view', 'month')
    
    # Datum aus GET-Parameter oder heute
    date_str = request.GET.get('date')
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            current_date = date.today()
    else:
        current_date = date.today()
    
    # Basis-Query für Events
    base_events = Event.objects.filter(
        Q(organizer=request.user) | Q(participants=request.user)
    ).distinct()
    
    # Je nach Ansichtsmodus filtern
    if view_mode == 'day':
        # Tagesansicht
        start_date = datetime.combine(current_date, datetime.min.time())
        end_date = datetime.combine(current_date, datetime.max.time())
        events = base_events.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        ).order_by('start_time')
        
        # Navigation
        prev_date = current_date - timedelta(days=1)
        next_date = current_date + timedelta(days=1)
        title = current_date.strftime('%A, %d. %B %Y')
        
    elif view_mode == 'week':
        # Wochenansicht
        start_week = current_date - timedelta(days=current_date.weekday())
        end_week = start_week + timedelta(days=6)
        
        start_date = datetime.combine(start_week, datetime.min.time())
        end_date = datetime.combine(end_week, datetime.max.time())
        
        events = base_events.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        ).order_by('start_time')
        
        # Wochentage für die Ansicht
        week_days = []
        for i in range(7):
            day = start_week + timedelta(days=i)
            week_days.append({
                'date': day,
                'day_name': day.strftime('%a'),
                'day_number': day.day,
                'is_today': day == date.today(),
                'events': []
            })
        
        # Events den Tagen zuordnen
        for event in events:
            day_index = (event.start_time.date() - start_week).days
            if 0 <= day_index < 7:
                week_days[day_index]['events'].append(event)
        
        # Navigation
        prev_date = start_week - timedelta(days=7)
        next_date = start_week + timedelta(days=7)
        title = f"Woche {start_week.strftime('%d.%m.')} - {end_week.strftime('%d.%m.%Y')}"
        
    elif view_mode == 'year':
        # Jahresansicht
        year = current_date.year
        events = base_events.filter(
            start_time__year=year
        ).order_by('start_time')
        
        # Monate für die Ansicht
        months_data = []
        for month in range(1, 13):
            month_events = events.filter(start_time__month=month)
            months_data.append({
                'month': month,
                'name': month_name[month],
                'event_count': month_events.count(),
                'has_events': month_events.exists()
            })
        
        # Navigation
        prev_date = date(year - 1, 1, 1)
        next_date = date(year + 1, 1, 1)
        title = str(year)
        
    else:  # month (Standard)
        # Monatsansicht
        year = current_date.year
        month = current_date.month
        
        # Erster und letzter Tag des Monats
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
        
        # Kalenderwochen berechnen
        cal = calendar.monthcalendar(year, month)
        
        # Events für den Monat
        start_date = datetime.combine(first_day, datetime.min.time())
        end_date = datetime.combine(last_day, datetime.max.time())
        
        events = base_events.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        ).order_by('start_time')
        
        # Kalender-Daten aufbereiten
        calendar_weeks = []
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'day': None, 'events': [], 'is_today': False})
                else:
                    day_date = date(year, month, day)
                    day_events = events.filter(
                        start_time__date=day_date
                    )
                    week_data.append({
                        'day': day,
                        'date': day_date,
                        'events': list(day_events),
                        'is_today': day_date == date.today(),
                        'event_count': day_events.count()
                    })
            calendar_weeks.append(week_data)
        
        # Navigation
        if month == 1:
            prev_date = date(year - 1, 12, 1)
        else:
            prev_date = date(year, month - 1, 1)
            
        if month == 12:
            next_date = date(year + 1, 1, 1)
        else:
            next_date = date(year, month + 1, 1)
            
        title = f"{month_name[month]} {year}"
    
    context = {
        'events': events,
        'view_mode': view_mode,
        'current_date': current_date,
        'title': title,
        'prev_date': prev_date,
        'next_date': next_date,
    }
    
    # Zusätzliche Kontext-Daten je nach Ansicht
    if view_mode == 'week':
        context['week_days'] = week_days
    elif view_mode == 'month':
        context['calendar_weeks'] = calendar_weeks
        context['weekday_names'] = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    elif view_mode == 'year':
        context['months_data'] = months_data
    
    return render(request, 'organization/calendar.html', context)


@login_required
def event_create(request):
    """Erstelle einen neuen Termin."""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        location = request.POST.get('location', '')
        priority = request.POST.get('priority', 'medium')
        reminder_minutes = int(request.POST.get('reminder_minutes', 15))
        is_all_day = request.POST.get('is_all_day') == 'on'
        
        if title and start_time and end_time:
            event = Event.objects.create(
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=location,
                organizer=request.user,
                priority=priority,
                reminder_minutes=reminder_minutes,
                is_all_day=is_all_day
            )
            
            # Teilnehmer hinzufügen
            participant_usernames = request.POST.getlist('participants')
            for username in participant_usernames:
                try:
                    user = User.objects.get(username=username)
                    EventParticipant.objects.create(
                        event=event,
                        user=user,
                        response='pending'
                    )
                except User.DoesNotExist:
                    continue
            
            messages.success(request, "Termin erfolgreich erstellt!")
            return redirect('organization:event_detail', pk=event.pk)
        else:
            messages.error(request, "Titel, Start- und Endzeit sind erforderlich.")
    
    return render(request, 'organization/event_form.html')


@login_required
def event_detail(request, pk):
    """Detailansicht eines Termins."""
    event = get_object_or_404(Event, pk=pk)
    
    # Zugriffsberechtigung prüfen
    if not (event.organizer == request.user or request.user in event.participants.all()):
        messages.error(request, "Sie haben keine Berechtigung, diesen Termin zu sehen.")
        return redirect('organization:calendar_view')
    
    participant_info = EventParticipant.objects.filter(event=event)
    user_participation = None
    
    if request.user in event.participants.all():
        user_participation = EventParticipant.objects.get(event=event, user=request.user)
    
    # Statistiken für die Antworten berechnen
    accepted_count = participant_info.filter(response='accepted').count()
    declined_count = participant_info.filter(response='declined').count()
    maybe_count = participant_info.filter(response='maybe').count()
    pending_count = participant_info.filter(response='pending').count()
    
    return render(request, 'organization/event_detail.html', {
        'event': event,
        'participant_info': participant_info,
        'user_participation': user_participation,
        'accepted_count': accepted_count,
        'declined_count': declined_count,
        'maybe_count': maybe_count,
        'pending_count': pending_count,
    })


@login_required
def event_respond(request, pk):
    """Auf Termineinladung antworten."""
    event = get_object_or_404(Event, pk=pk)
    
    try:
        participant = EventParticipant.objects.get(event=event, user=request.user)
        
        if request.method == 'POST':
            response = request.POST.get('response')
            if response in ['accepted', 'declined', 'maybe']:
                participant.response = response
                participant.response_time = timezone.now()
                participant.notes = request.POST.get('notes', '')
                participant.save()
                
                messages.success(request, f"Ihre Antwort '{participant.get_response_display()}' wurde gespeichert!")
                return redirect('organization:event_detail', pk=pk)
    
    except EventParticipant.DoesNotExist:
        messages.error(request, "Sie sind nicht zu diesem Termin eingeladen.")
        return redirect('organization:calendar_view')
    
    return render(request, 'organization/event_respond.html', {'event': event})


@login_required
def board_list(request):
    """Liste aller Ideenboards des Benutzers."""
    # Boards wo User Creator ist
    created_boards = IdeaBoard.objects.filter(creator=request.user)
    
    # Boards wo User Collaborator ist
    collaborated_boards = IdeaBoard.objects.filter(collaborators=request.user)
    
    # Alle Boards zusammen
    boards = IdeaBoard.objects.filter(
        Q(creator=request.user) | Q(collaborators=request.user)
    ).distinct().order_by('-updated_at')
    
    # Debug-Information
    print(f"User: {request.user.username}")
    print(f"Created boards: {created_boards.count()}")
    print(f"Collaborated boards: {collaborated_boards.count()}")
    print(f"Total boards: {boards.count()}")
    
    return render(request, 'organization/board_list.html', {
        'boards': boards,
        'created_boards': created_boards,
        'collaborated_boards': collaborated_boards,
    })


@login_required
def board_detail(request, pk):
    """Detailansicht eines Ideenboards."""
    board = get_object_or_404(IdeaBoard, pk=pk)
    
    # Zugriffsberechtigung prüfen
    if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
        messages.error(request, "Sie haben keine Berechtigung, dieses Board zu sehen.")
        return redirect('organization:board_list')
    
    elements = board.elements.all().order_by('layer_index', 'created_at')
    
    return render(request, 'organization/board_detail.html', {
        'board': board,
        'elements': elements
    })


@login_required
def board_create(request):
    """Erstelle ein neues Ideenboard."""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        width = int(request.POST.get('width', 1200))
        height = int(request.POST.get('height', 800))
        background_color = request.POST.get('background_color', '#ffffff')
        is_public = request.POST.get('is_public') == 'on'
        
        if title:
            board = IdeaBoard.objects.create(
                title=title,
                description=description,
                creator=request.user,
                width=width,
                height=height,
                background_color=background_color,
                is_public=is_public
            )
            
            # Mitarbeiter hinzufügen
            collaborator_usernames = request.POST.getlist('collaborators')
            for username in collaborator_usernames:
                try:
                    user = User.objects.get(username=username)
                    board.collaborators.add(user)
                except User.DoesNotExist:
                    continue
            
            messages.success(request, "Ideenboard erfolgreich erstellt!")
            return redirect('organization:board_detail', pk=board.pk)
        else:
            messages.error(request, "Titel ist erforderlich.")
    
    return render(request, 'organization/board_form.html')


@login_required
@csrf_exempt
def board_save_element(request, pk):
    """Speichere ein Element auf dem Ideenboard."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)
        
        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all()):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
        
        data = json.loads(request.body)
        
        width = data.get('width', 100)
        height = data.get('height', 100)

        element = BoardElement.objects.create(
            board=board,
            element_type=data.get('element_type'),
            data=data.get('data', {}),
            position_x=data.get('position_x', 0),
            position_y=data.get('position_y', 0),
            width=int(width) if width is not None else 100,
            height=int(height) if height is not None else 100,
            color=data.get('color', '#000000'),
            stroke_width=data.get('stroke_width', 2),
            opacity=data.get('opacity', 1.0),
            layer_index=data.get('layer_index', 0),
            created_by=request.user
        )
        
        # Update board's updated_at timestamp for polling
        board.updated_at = timezone.now()
        board.save()
        
        return JsonResponse({'id': element.id, 'success': True})
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
def board_get_elements(request, pk):
    """Lade alle Elemente eines Ideenboards."""
    board = get_object_or_404(IdeaBoard, pk=pk)
    
    # Zugriffsberechtigung prüfen
    if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
    
    # Check if client provided a timestamp for polling
    since_timestamp = request.GET.get('since')
    if since_timestamp:
        try:
            since_time = timezone.datetime.fromtimestamp(int(since_timestamp) / 1000, tz=timezone.get_current_timezone())
            if board.updated_at <= since_time:
                return JsonResponse({'updated': False})
        except (ValueError, TypeError):
            pass
    
    elements = board.elements.all().order_by('layer_index', 'created_at')
    
    elements_data = []
    for element in elements:
        elements_data.append({
            'id': element.id,
            'element_type': element.element_type,
            'data': element.data,
            'position_x': element.position_x,
            'position_y': element.position_y,
            'width': element.width,
            'height': element.height,
            'color': element.color,
            'stroke_width': element.stroke_width,
            'opacity': element.opacity,
            'rotation': element.rotation if element.rotation is not None else 0,
            'layer_index': element.layer_index,
            'created_by': element.created_by.username,
            'created_by_id': element.created_by.id,
        })
    
    return JsonResponse({'elements': elements_data, 'updated': True})


@login_required
@csrf_exempt
def board_invite_collaborators(request, pk):
    """Lade neue Mitarbeiter zu einem Board ein."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)
        
        # Nur der Ersteller kann Mitarbeiter einladen
        if board.creator != request.user:
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
        
        data = json.loads(request.body)
        collaborator_ids = data.get('collaborator_ids', [])
        
        success_count = 0
        for user_id in collaborator_ids:
            try:
                user = User.objects.get(id=user_id)
                # Prüfen ob bereits Mitarbeiter
                if not board.collaborators.filter(id=user_id).exists():
                    board.collaborators.add(user)
                    success_count += 1
            except User.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'{success_count} Mitarbeiter erfolgreich eingeladen'
        })
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
@csrf_exempt
def board_update_element(request, pk):
    """Aktualisiere ein Element auf dem Ideenboard."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)
        
        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all()):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
        
        data = json.loads(request.body)
        element_id = data.get('element_id')
        
        try:
            element = BoardElement.objects.get(id=element_id, board=board)
            element.data = data.get('data', element.data)
            element.position_x = data.get('position_x', element.position_x)
            element.position_y = data.get('position_y', element.position_y)
            element.rotation = data.get('rotation', element.rotation)
            if 'width' in data and data.get('width') is not None:
                element.width = int(data.get('width'))
            if 'height' in data and data.get('height') is not None:
                element.height = int(data.get('height'))

            # Update style properties if provided
            if 'color' in data:
                element.color = data.get('color')
            if 'stroke_width' in data:
                element.stroke_width = data.get('stroke_width')
            if 'opacity' in data:
                element.opacity = data.get('opacity')

            element.save()
            
            # Update board's updated_at timestamp for polling
            board.updated_at = timezone.now()
            board.save()

            return JsonResponse({'success': True})
            
        except BoardElement.DoesNotExist:
            return JsonResponse({'error': 'Element nicht gefunden'}, status=404)

    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
@csrf_exempt
def board_upload_image(request, pk):
    """Lade ein Bild für ein Ideenboard hoch und gib die URL zurück."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)

    board = get_object_or_404(IdeaBoard, pk=pk)

    if not (board.creator == request.user or request.user in board.collaborators.all()):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    upload = request.FILES.get('image')
    if not upload:
        return JsonResponse({'error': 'Kein Bild übermittelt'}, status=400)

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']:
        return JsonResponse({'error': 'Nicht unterstütztes Bildformat'}, status=400)

    temp_data = upload.read()
    try:
        with Image.open(ContentFile(temp_data)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError):
        return JsonResponse({'error': 'Ungültige Bilddatei'}, status=400)

    filename = f"board_images/{uuid.uuid4().hex}{ext}"
    saved_path = default_storage.save(filename, ContentFile(temp_data))
    image_url = default_storage.url(saved_path)

    board.updated_at = timezone.now()
    board.save(update_fields=['updated_at'])

    return JsonResponse({
        'success': True,
        'url': image_url,
        'width': width,
        'height': height
    })



@login_required
@csrf_exempt
def board_clear_elements(request, pk):
    """Lösche alle Elemente vom Board."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)
        
        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all()):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
        
        # Delete all elements
        board.elements.all().delete()
        
        # Update board's updated_at timestamp for polling
        board.updated_at = timezone.now()
        board.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
@csrf_exempt
def board_delete_element(request, pk, element_id):
    """Lösche ein Element vom Ideenboard."""
    if request.method in ['DELETE', 'POST']:
        board = get_object_or_404(IdeaBoard, pk=pk)
        
        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all()):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
        
        try:
            element = BoardElement.objects.get(id=element_id, board=board)
            element.delete()
            
            # Update board's updated_at timestamp for polling
            board.updated_at = timezone.now()
            board.save()
            
            return JsonResponse({'success': True})
            
        except BoardElement.DoesNotExist:
            return JsonResponse({'error': 'Element nicht gefunden'}, status=404)

    return JsonResponse({'error': 'Nur DELETE oder POST erlaubt'}, status=405)


@login_required
@csrf_exempt
def board_remove_collaborator(request, pk):
    """Entferne einen Mitarbeiter von einem Board."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)
        
        # Nur der Ersteller kann Mitarbeiter entfernen
        if board.creator != request.user:
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
        
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            board.collaborators.remove(user)
            return JsonResponse({'success': True})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Benutzer nicht gefunden'}, status=404)
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
def call_start_page(request):
    """Zeige die Seite zum Starten eines Anrufs."""
    return render(request, 'organization/call_start.html')


@login_required
@login_required
def call_start(request):
    """Starte einen neuen Video/Audio-Anruf."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        data = json.loads(request.body)
        call_type = data.get('call_type', 'video')
        participant_ids = data.get('participants', [])
        
        # Clean up stale calls (older than 10 minutes)
        stale_calls = VideoCall.objects.filter(
            status__in=['initiated', 'ringing'],
            started_at__lt=timezone.now() - timezone.timedelta(minutes=10)
        )
        stale_calls.update(status='missed')
        
        # Also clean up calls that are still "connected" but older than 30 minutes
        old_connected_calls = VideoCall.objects.filter(
            status='connected',
            started_at__lt=timezone.now() - timezone.timedelta(minutes=30)
        )
        old_connected_calls.update(status='ended', ended_at=timezone.now())
        
        # Create new call
        call = VideoCall.objects.create(
            caller=request.user,
            call_type=call_type,
            status='initiated'
        )
        
        # Add participants
        for user_id in participant_ids:
            try:
                user = User.objects.get(id=user_id)
                CallParticipant.objects.create(
                    call=call,
                    user=user,
                    status='invited'
                )
            except User.DoesNotExist:
                continue
        
        # Add caller as participant with joined status
        CallParticipant.objects.create(
            call=call,
            user=request.user,
            status='joined',
            joined_at=timezone.now()
        )
        
        # Send notifications to all participants (except caller)
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        for participant_id in participant_ids:
            try:
                participant = User.objects.get(id=participant_id)
                async_to_sync(channel_layer.group_send)(
                    f'user_{participant.id}',
                    {
                        'type': 'global_call_notification',
                        'call_id': str(call.id),
                        'caller': request.user.username,
                        'caller_full_name': request.user.get_full_name() or request.user.username,
                        'call_type': call_type,
                        'organization_call': True,
                        'timestamp': timezone.now().isoformat()
                    }
                )
            except User.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'call_id': str(call.id),
            'call_type': call_type,
            'message': 'Anruf gestartet'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required 
def call_join(request, call_id):
    """Tritt einem bestehenden Anruf bei oder zeige Call Interface."""
    call = get_object_or_404(VideoCall, id=call_id)
    
    # Prüfe ob Benutzer Teilnehmer ist
    try:
        participant = CallParticipant.objects.get(call=call, user=request.user)
    except CallParticipant.DoesNotExist:
        messages.error(request, 'Sie sind nicht zu diesem Anruf eingeladen.')
        return redirect('organization:dashboard')
    
    if call.status != 'active':
        messages.error(request, 'Anruf ist nicht mehr aktiv.')
        return redirect('organization:dashboard')
    
    try:
        # Generiere Token für Teilnehmer
        token = generate_agora_token(
            channel_name=call.channel_name,
            uid=request.user.id,
            role=CallRoles.PUBLISHER
        )
        
        # Update Teilnehmer-Status
        participant.status = 'joined'
        participant.joined_at = timezone.now()
        participant.save()
        
        # Zeige Call Interface
        context = {
            'call': call,
            'channel_name': call.channel_name,
            'token': token,
            'agora_config': get_agora_config()
        }
        return render(request, 'organization/call_interface.html', context)
        
    except ValueError as e:
        messages.error(request, f'Fehler beim Beitreten: {str(e)}')
        return redirect('organization:dashboard')


@login_required
@csrf_exempt
def call_end(request, call_id):
    """Beende einen Anruf."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        call = get_object_or_404(VideoCall, id=call_id)
        
        # Nur Anrufer kann Anruf beenden
        if call.caller != request.user:
            return JsonResponse({'success': False, 'error': 'Nur der Anrufer kann den Anruf beenden'}, status=403)
        
        # Calculate duration if call was connected
        if call.connected_at:
            call.duration = timezone.now() - call.connected_at
        
        call.status = 'ended'
        call.ended_at = timezone.now()
        call.save()
        
        # Update all participants who are still joined
        CallParticipant.objects.filter(call=call, status='joined').update(
            status='left',
            left_at=timezone.now()
        )
        
        return JsonResponse({'success': True, 'message': 'Anruf beendet'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt  
def call_leave(request, call_id):
    """Verlasse einen Anruf."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        call = get_object_or_404(VideoCall, id=call_id)
        
        participant = CallParticipant.objects.get(call=call, user=request.user)
        participant.status = 'left'
        participant.left_at = timezone.now()
        participant.save()
        
        return JsonResponse({'success': True, 'message': 'Anruf verlassen'})
        
    except CallParticipant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sie sind nicht Teil dieses Anrufs'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def call_status(request, call_id):
    """Rufe den Status eines Anrufs ab."""
    call = get_object_or_404(VideoCall, id=call_id)
    
    # Prüfe ob Benutzer Teilnehmer ist
    try:
        participant = CallParticipant.objects.get(call=call, user=request.user)
    except CallParticipant.DoesNotExist:
        return JsonResponse({'error': 'Zugriff verweigert'}, status=403)
    
    participants = []
    for p in call.call_participants.all():
        participants.append({
            'id': p.user.id,
            'username': p.user.username,
            'status': p.status,
            'joined_at': p.joined_at.isoformat() if p.joined_at else None
        })
    
    return JsonResponse({
        'call_id': str(call.id),
        'status': call.status,
        'call_type': call.call_type,
        'caller': call.caller.username,
        'participants': participants,
        'started_at': call.started_at.isoformat() if call.started_at else None,
        'connected_at': call.connected_at.isoformat() if call.connected_at else None,
        'duration': call.get_duration_display() if call.duration else None
    })


@login_required
def check_incoming_calls(request):
    """
    Check for incoming calls for the current user in organization
    """
    try:
        # Check for incoming calls where user is a participant
        active_calls = VideoCall.objects.filter(
            call_participants__user=request.user,
            status__in=['initiated', 'ringing']
        ).exclude(caller=request.user).order_by('-started_at')
        
        if active_calls.exists():
            latest_call = active_calls.first()
            
            return JsonResponse({
                'has_incoming_call': True,
                'call_id': str(latest_call.id),
                'caller': latest_call.caller.username,
                'caller_full_name': latest_call.caller.get_full_name() or latest_call.caller.username,
                'call_type': latest_call.call_type,
                'organization_call': True,
                'timestamp': latest_call.started_at.isoformat()
            })
        
        return JsonResponse({'has_incoming_call': False})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_agora_token(request):
    """
    Generate Agora token for video/audio calls
    """
    try:
        data = json.loads(request.body)
        call_id = data.get('call_id')
        
        if not call_id:
            return JsonResponse({
                'success': False,
                'error': 'Call ID required'
            })
        
        call = get_object_or_404(VideoCall, id=call_id)
        
        # Check if user is participant
        if not CallParticipant.objects.filter(call=call, user=request.user).exists():
            return JsonResponse({
                'success': False,
                'error': 'Access denied'
            })
        
        # For now, return a simple success response
        # This would integrate with Agora in production
        return JsonResponse({
            'success': True,
            'token': f'mock_token_{call_id}_{request.user.id}',
            'channel': f'call_{call_id}',
            'uid': request.user.id,
            'app_id': 'mock_app_id'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def user_search(request):
    """Suche nach Benutzern für Erwähnungen und Einladungen."""
    query = request.GET.get('q', '')
    
    if len(query) >= 2:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id)[:10]
        
        results = []
        for user in users:
            results.append({
                'id': user.id,
                'username': user.username,
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username
            })
        
        return JsonResponse({'results': results})

    return JsonResponse({'results': []})


# ========================================
# Board Audio Views
# ========================================

@login_required
@csrf_exempt
def board_audio_join(request, pk):
    """Audio-Session für Board beitreten."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)

        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

        # Aktive Session finden oder erstellen
        try:
            # Versuche aktive Session zu finden
            audio_session = BoardAudioSession.objects.get(board=board, is_active=True)
        except BoardAudioSession.DoesNotExist:
            # Keine aktive Session, prüfe ob inaktive existiert
            try:
                audio_session = BoardAudioSession.objects.get(board=board)
                # Reaktiviere die Session
                audio_session.is_active = True
                audio_session.ended_at = None
                audio_session.save()
            except BoardAudioSession.DoesNotExist:
                # Erstelle neue Session
                audio_session = BoardAudioSession.objects.create(
                    board=board,
                    channel_name=f'board_audio_{board.id}',
                    is_active=True
                )

        # Benutzer zur Session hinzufügen
        participant, created = BoardAudioParticipant.objects.get_or_create(
            session=audio_session,
            user=request.user,
            defaults={'left_at': None, 'is_muted': False}  # Explicitly set is_muted to False for new participants
        )

        # Falls Benutzer bereits teilgenommen hatte, reaktivieren
        if not created and participant.left_at:
            participant.left_at = None
            participant.joined_at = timezone.now()
            participant.is_muted = False  # Reset mute status when rejoining
            participant.save()
        elif not created:
            # Even if the user was already active, reset mute status to ensure clean state
            participant.is_muted = False
            participant.save()

        return JsonResponse({
            'success': True,
            'channel_name': audio_session.channel_name,
            'session_id': audio_session.id
        })

    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
@csrf_exempt
def board_audio_leave(request, pk):
    """Audio-Session für Board verlassen."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)

        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

        try:
            audio_session = BoardAudioSession.objects.get(board=board, is_active=True)
            participant = BoardAudioParticipant.objects.get(session=audio_session, user=request.user)

            # Teilnehmer als verlassen markieren
            participant.left_at = timezone.now()
            participant.save()

            # Prüfen ob noch andere aktive Teilnehmer da sind
            active_participants = BoardAudioParticipant.objects.filter(
                session=audio_session,
                left_at__isnull=True
            ).count()

            # Wenn keine aktiven Teilnehmer mehr da sind, Session beenden
            if active_participants == 0:
                audio_session.is_active = False
                audio_session.ended_at = timezone.now()
                audio_session.save()

            return JsonResponse({'success': True})

        except (BoardAudioSession.DoesNotExist, BoardAudioParticipant.DoesNotExist):
            return JsonResponse({'error': 'Keine aktive Audio-Session gefunden'}, status=404)

    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
@csrf_exempt
def board_audio_token(request, pk):
    """Agora Token für Board Audio-Session generieren."""
    if request.method == 'POST':
        board = get_object_or_404(IdeaBoard, pk=pk)

        # Zugriffsberechtigung prüfen
        if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

        try:
            audio_session = BoardAudioSession.objects.get(board=board, is_active=True)

            # Prüfen ob Benutzer aktiver Teilnehmer ist
            participant = BoardAudioParticipant.objects.get(
                session=audio_session,
                user=request.user,
                left_at__isnull=True
            )

            # Agora Token generieren
            channel_name = audio_session.channel_name
            uid = request.user.id
            role = CallRoles.PUBLISHER  # Alle können sprechen und hören

            token = generate_agora_token(channel_name, uid, role)
            agora_config = get_agora_config()

            return JsonResponse({
                'success': True,
                'token': token,
                'channel_name': channel_name,
                'uid': uid,
                'app_id': agora_config['app_id']
            })

        except BoardAudioSession.DoesNotExist:
            return JsonResponse({'error': 'Keine aktive Audio-Session gefunden'}, status=404)
        except BoardAudioParticipant.DoesNotExist:
            return JsonResponse({'error': 'Sie sind kein aktiver Teilnehmer'}, status=403)
        except Exception as e:
            return JsonResponse({'error': f'Token-Generierung fehlgeschlagen: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
def board_audio_status(request, pk):
    """Status der Board Audio-Session abrufen."""
    board = get_object_or_404(IdeaBoard, pk=pk)

    # Zugriffsberechtigung prüfen
    if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    try:
        audio_session = BoardAudioSession.objects.get(board=board, is_active=True)

        # Aktive Teilnehmer abrufen
        active_participants = BoardAudioParticipant.objects.filter(
            session=audio_session,
            left_at__isnull=True
        ).select_related('user')

        participants_data = []
        for participant in active_participants:
            # Generate Agora UID based on user ID (similar to frontend)
            agora_uid = int(f"1{participant.user.id:06d}")

            participants_data.append({
                'user_id': participant.user.id,
                'username': participant.user.username,
                'is_muted': participant.is_muted,
                'joined_at': participant.joined_at.isoformat(),
                'agora_uid': agora_uid
            })

        user_is_participant = active_participants.filter(user=request.user).exists()

        return JsonResponse({
            'has_active_session': True,
            'session_id': audio_session.id,
            'channel_name': audio_session.channel_name,
            'participants': participants_data,
            'participant_count': len(participants_data),
            'user_is_participant': user_is_participant
        })

    except BoardAudioSession.DoesNotExist:
        return JsonResponse({
            'has_active_session': False,
            'participants': [],
            'participant_count': 0,
            'user_is_participant': False
        })


@login_required
@csrf_exempt
def board_audio_mute(request, pk):
    """Mute-Status eines Teilnehmers aktualisieren."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)

    board = get_object_or_404(IdeaBoard, pk=pk)

    # Zugriffsberechtigung prüfen
    if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    try:
        import json
        data = json.loads(request.body)
        is_muted = data.get('is_muted', False)

        # Audio Session suchen
        audio_session = BoardAudioSession.objects.get(board=board, is_active=True)

        # Teilnehmer suchen und Mute-Status aktualisieren
        participant = BoardAudioParticipant.objects.get(
            session=audio_session,
            user=request.user,
            left_at__isnull=True
        )

        participant.is_muted = is_muted
        participant.save()

        return JsonResponse({'success': True, 'is_muted': is_muted})

    except BoardAudioSession.DoesNotExist:
        return JsonResponse({'error': 'Keine aktive Audio-Session'}, status=404)
    except BoardAudioParticipant.DoesNotExist:
        return JsonResponse({'error': 'Benutzer ist kein Teilnehmer'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Ungültige JSON-Daten'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_username(request, user_id):
    """Get username for a specific user ID."""
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({'username': user.username})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@login_required
@csrf_exempt
def board_update_notes(request, pk):
    """Notizen für ein Board aktualisieren."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST-Requests erlaubt'}, status=405)

    board = get_object_or_404(IdeaBoard, pk=pk)

    # Zugriffsberechtigung prüfen
    if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    try:
        data = json.loads(request.body)
        notes = data.get('notes', '')

        board.notes = notes
        board.save(update_fields=['notes', 'updated_at'])

        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Ungültige JSON-Daten'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def board_get_notes(request, pk):
    """Notizen für ein Board abrufen."""
    board = get_object_or_404(IdeaBoard, pk=pk)

    # Zugriffsberechtigung prüfen
    if not (board.creator == request.user or request.user in board.collaborators.all() or board.is_public):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    return JsonResponse({
        'success': True,
        'notes': board.notes or ''
    })
