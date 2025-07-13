from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from .models import Note, Event, EventParticipant, IdeaBoard, BoardElement, EventReminder, VideoCall, CallParticipant
from .agora_utils import generate_agora_token, get_agora_config, CallRoles
import json
import re

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
        
        element = BoardElement.objects.create(
            board=board,
            element_type=data.get('element_type'),
            data=data.get('data', {}),
            position_x=data.get('position_x', 0),
            position_y=data.get('position_y', 0),
            width=data.get('width', 100),
            height=data.get('height', 100),
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
    if request.method == 'DELETE':
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
    
    return JsonResponse({'error': 'Nur DELETE erlaubt'}, status=405)


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
@csrf_exempt
def call_start(request):
    """Starte einen neuen Video/Audio-Anruf."""
    if request.method == 'POST':
        data = json.loads(request.body)
        call_type = data.get('call_type', 'video')
        participant_ids = data.get('participants', [])
        
        # Erstelle neuen Anruf
        call = VideoCall.objects.create(
            caller=request.user,
            call_type=call_type
        )
        call.generate_channel_name()
        
        # Füge Teilnehmer hinzu
        for user_id in participant_ids:
            try:
                user = User.objects.get(id=user_id)
                CallParticipant.objects.create(
                    call=call,
                    user=user,
                    agora_uid=user_id  # Verwende User-ID als Agora UID
                )
            except User.DoesNotExist:
                continue
        
        # Füge Anrufer als Teilnehmer hinzu
        CallParticipant.objects.create(
            call=call,
            user=request.user,
            status='joined',
            joined_at=timezone.now(),
            agora_uid=request.user.id
        )
        
        try:
            # Generiere Agora Token
            token = generate_agora_token(
                channel_name=call.channel_name,
                uid=request.user.id,
                role=CallRoles.PUBLISHER
            )
            call.agora_token = token
            call.token_expires_at = timezone.now() + timezone.timedelta(hours=1)
            call.status = 'active'
            call.started_at = timezone.now()
            call.save()
            
            return JsonResponse({
                'success': True,
                'call_id': str(call.id),
                'channel_name': call.channel_name,
                'token': token,
                'agora_config': get_agora_config()
            })
            
        except ValueError as e:
            call.delete()
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


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
    if request.method == 'POST':
        call = get_object_or_404(VideoCall, id=call_id)
        
        # Nur Anrufer kann Anruf beenden
        if call.caller != request.user:
            return JsonResponse({'error': 'Nur der Anrufer kann den Anruf beenden'}, status=403)
        
        call.status = 'ended'
        call.ended_at = timezone.now()
        call.save()
        
        # Update alle Teilnehmer die noch aktiv sind
        active_participants = CallParticipant.objects.filter(
            call=call,
            status='joined',
            left_at__isnull=True
        )
        
        for participant in active_participants:
            participant.status = 'left'
            participant.left_at = timezone.now()
            participant.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
@csrf_exempt  
def call_leave(request, call_id):
    """Verlasse einen Anruf."""
    if request.method == 'POST':
        call = get_object_or_404(VideoCall, id=call_id)
        
        try:
            participant = CallParticipant.objects.get(call=call, user=request.user)
            participant.status = 'left'
            participant.left_at = timezone.now()
            participant.save()
            
            return JsonResponse({'success': True})
            
        except CallParticipant.DoesNotExist:
            return JsonResponse({'error': 'Sie sind kein Teilnehmer dieses Anrufs'}, status=400)
    
    return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)


@login_required
def call_status(request, call_id):
    """Rufe den Status eines Anrufs ab."""
    call = get_object_or_404(VideoCall, id=call_id)
    
    # Prüfe Berechtigung
    is_participant = CallParticipant.objects.filter(call=call, user=request.user).exists()
    if not (call.caller == request.user or is_participant):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
    
    participants = []
    for participant in call.participants.through.objects.filter(call=call):
        participants.append({
            'user_id': participant.user.id,
            'username': participant.user.username,
            'status': participant.status,
            'joined_at': participant.joined_at.isoformat() if participant.joined_at else None,
            'left_at': participant.left_at.isoformat() if participant.left_at else None
        })
    
    return JsonResponse({
        'call_id': str(call.id),
        'status': call.status,
        'call_type': call.call_type,
        'caller': call.caller.username,
        'participants': participants,
        'started_at': call.started_at.isoformat() if call.started_at else None,
        'ended_at': call.ended_at.isoformat() if call.ended_at else None
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
