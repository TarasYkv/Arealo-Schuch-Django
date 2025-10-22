from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import IntegrityError
from django.db.models import Count, Q
from .models import SavedKeyword, KeywordList, UserPreference
from .services.keyword_ai import KeywordAIService
import logging
import csv

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """
    KeyEngine Dashboard - Hauptseite mit Keyword-Generator
    """
    # Prüfe ob User einen OpenAI API-Key hat
    ai_service = KeywordAIService(request.user)
    has_api_key = ai_service.has_api_key()

    # Hole alle Listen des Users für Dropdown
    user_lists = KeywordList.objects.filter(
        user=request.user,
        is_archived=False
    ).order_by('position', 'name')

    # Hole oder erstelle User-Präferenzen
    user_prefs, created = UserPreference.objects.get_or_create(user=request.user)

    context = {
        'has_api_key': has_api_key,
        'user_lists': user_lists,
        'default_list': user_prefs.last_used_list,
        'page_title': 'KeyEngine - Keyword Research Tool'
    }

    return render(request, 'keyengine/dashboard.html', context)


@login_required
@require_POST
def generate_keywords(request):
    """
    AJAX Endpoint: Generiert Keywords basierend auf Seed-Keyword
    """
    seed_keyword = request.POST.get('seed_keyword', '').strip()

    if not seed_keyword:
        return JsonResponse({
            'success': False,
            'error': 'Bitte gib ein Seed-Keyword ein'
        })

    # Keyword-Count aus Request (default: 25)
    try:
        count = int(request.POST.get('count', 25))
        count = min(max(count, 5), 50)  # Limit: 5-50
    except ValueError:
        count = 25

    # KI-Service initialisieren
    ai_service = KeywordAIService(request.user)

    # Keywords generieren
    result = ai_service.generate_keywords(
        seed_keyword=seed_keyword,
        count=count
    )

    return JsonResponse(result)


@login_required
def lists_overview(request):
    """
    Listen-Übersicht - Kachel-Dashboard mit allen Listen
    """
    # Hole alle Listen des Users (nicht archiviert)
    lists = KeywordList.objects.filter(
        user=request.user,
        is_archived=False
    ).annotate(
        total_keywords=Count('keywords'),
        open_keywords=Count('keywords', filter=Q(keywords__is_done=False)),
        done_keywords=Count('keywords', filter=Q(keywords__is_done=True))
    ).order_by('position', '-created_at')

    # Archivierte Listen
    archived_lists = KeywordList.objects.filter(
        user=request.user,
        is_archived=True
    ).annotate(
        total_keywords=Count('keywords')
    ).order_by('-created_at')

    context = {
        'lists': lists,
        'archived_lists': archived_lists,
        'total_lists': lists.count(),
        'page_title': 'KeyEngine - Meine Listen'
    }

    return render(request, 'keyengine/lists_overview.html', context)


@login_required
def list_detail(request, list_id):
    """
    Listen-Detail - Keywords einer spezifischen Liste
    """
    # Hole Liste (nur eigene Listen)
    keyword_list = get_object_or_404(KeywordList, id=list_id, user=request.user)

    # Filter-Parameter
    status_filter = request.GET.get('status', 'all')  # all, open, done
    sort_by = request.GET.get('sort', 'newest')  # newest, priority, alpha

    # Base Query
    keywords = SavedKeyword.objects.filter(keyword_list=keyword_list)

    # Filter anwenden
    if status_filter == 'open':
        keywords = keywords.filter(is_done=False)
    elif status_filter == 'done':
        keywords = keywords.filter(is_done=True)

    # Sortierung
    if sort_by == 'priority':
        # Custom Order: high, medium, low
        keywords = keywords.order_by('-is_done', 'priority', '-created_at')
    elif sort_by == 'alpha':
        keywords = keywords.order_by('-is_done', 'keyword')
    else:  # newest (default)
        keywords = keywords.order_by('-is_done', '-created_at')

    # Stats
    total_count = keyword_list.keyword_count()
    done_count = keyword_list.done_count()
    open_count = keyword_list.open_count()

    # Alle Listen für Verschieben-Dropdown
    all_lists = KeywordList.objects.filter(
        user=request.user,
        is_archived=False
    ).exclude(id=list_id).order_by('name')

    context = {
        'keyword_list': keyword_list,
        'keywords': keywords,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'total_count': total_count,
        'done_count': done_count,
        'open_count': open_count,
        'all_lists': all_lists,
        'page_title': f'KeyEngine - {keyword_list.name}'
    }

    return render(request, 'keyengine/list_detail.html', context)


@login_required
def watchlist(request):
    """
    Legacy Watchlist - Leitet zur Standard-Liste oder Listen-Übersicht um
    """
    # Hole oder erstelle Standard-Liste
    default_list, created = KeywordList.objects.get_or_create(
        user=request.user,
        name='Meine Keywords',
        defaults={
            'color': '#10b981',
            'description': 'Standard-Liste',
            'position': 0
        }
    )

    # Leite zur Listen-Übersicht um
    return redirect('keyengine:lists_overview')


@login_required
@require_POST
def add_to_watchlist(request):
    """
    AJAX Endpoint: Fügt Keyword zu einer Liste hinzu
    """
    keyword = request.POST.get('keyword', '').strip()
    intent_type = request.POST.get('intent', '').strip()
    description = request.POST.get('description', '').strip()
    list_id = request.POST.get('list_id')

    if not keyword:
        return JsonResponse({
            'success': False,
            'error': 'Keyword darf nicht leer sein'
        })

    # Liste auswählen oder Standard-Liste verwenden
    if list_id:
        keyword_list = get_object_or_404(KeywordList, id=list_id, user=request.user)
    else:
        # Hole oder erstelle Standard-Liste
        keyword_list, created = KeywordList.objects.get_or_create(
            user=request.user,
            name='Meine Keywords',
            defaults={
                'color': '#10b981',
                'description': 'Standard-Liste',
                'position': 0
            }
        )

    try:
        # Versuche zu erstellen (unique_together constraint: keyword_list + keyword)
        saved_keyword = SavedKeyword.objects.create(
            user=request.user,
            keyword_list=keyword_list,
            keyword=keyword,
            intent_type=intent_type,
            description=description,
            priority='medium',  # Default
            is_done=False
        )

        # Speichere letzte verwendete Liste
        user_prefs, created = UserPreference.objects.get_or_create(user=request.user)
        user_prefs.last_used_list = keyword_list
        user_prefs.save()

        return JsonResponse({
            'success': True,
            'message': f'"{keyword}" wurde zur Liste "{keyword_list.name}" hinzugefügt',
            'keyword_id': saved_keyword.id,
            'list_name': keyword_list.name
        })

    except IntegrityError:
        # Keyword existiert bereits in dieser Liste
        existing = SavedKeyword.objects.get(keyword_list=keyword_list, keyword=keyword)
        status_text = 'erledigt' if existing.is_done else 'offen'

        return JsonResponse({
            'success': False,
            'error': f'Keyword "{keyword}" bereits in Liste "{keyword_list.name}" (Status: {status_text})',
            'duplicate': True,
            'existing_status': 'done' if existing.is_done else 'open'
        })

    except Exception as e:
        logger.error(f"Error adding keyword to watchlist: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Hinzufügen: {str(e)}'
        })


@login_required
@require_POST
def update_keyword(request, keyword_id):
    """
    AJAX Endpoint: Aktualisiert Keyword (Priority, Done-Status)
    """
    keyword = get_object_or_404(SavedKeyword, id=keyword_id, user=request.user)

    # Welches Feld soll aktualisiert werden?
    field = request.POST.get('field')
    value = request.POST.get('value')

    try:
        if field == 'priority':
            if value in ['high', 'medium', 'low']:
                keyword.priority = value
                keyword.save()
            else:
                return JsonResponse({'success': False, 'error': 'Ungültige Priorität'})

        elif field == 'is_done':
            keyword.is_done = value.lower() == 'true'
            keyword.save()

        elif field == 'notes':
            keyword.notes = value
            keyword.save()

        else:
            return JsonResponse({'success': False, 'error': 'Unbekanntes Feld'})

        return JsonResponse({
            'success': True,
            'message': 'Keyword aktualisiert'
        })

    except Exception as e:
        logger.error(f"Error updating keyword: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren: {str(e)}'
        })


@login_required
@require_POST
def delete_keyword(request, keyword_id):
    """
    AJAX Endpoint: Löscht Keyword von Merkliste
    """
    keyword = get_object_or_404(SavedKeyword, id=keyword_id, user=request.user)

    try:
        keyword_text = keyword.keyword
        keyword.delete()

        return JsonResponse({
            'success': True,
            'message': f'"{keyword_text}" wurde gelöscht'
        })

    except Exception as e:
        logger.error(f"Error deleting keyword: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen: {str(e)}'
        })


# ==================== Listen-Management ====================

@login_required
@require_POST
def create_list(request):
    """
    AJAX Endpoint: Erstellt neue Keyword-Liste
    """
    name = request.POST.get('name', '').strip()
    color = request.POST.get('color', '#10b981').strip()
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({
            'success': False,
            'error': 'Name darf nicht leer sein'
        })

    try:
        # Prüfe ob Name bereits existiert
        if KeywordList.objects.filter(user=request.user, name=name).exists():
            return JsonResponse({
                'success': False,
                'error': f'Liste "{name}" existiert bereits'
            })

        # Erstelle neue Liste
        keyword_list = KeywordList.objects.create(
            user=request.user,
            name=name,
            color=color,
            description=description,
            position=KeywordList.objects.filter(user=request.user).count()
        )

        return JsonResponse({
            'success': True,
            'message': f'Liste "{name}" wurde erstellt',
            'list_id': keyword_list.id,
            'list_url': f'/keyengine/list/{keyword_list.id}/'
        })

    except Exception as e:
        logger.error(f"Error creating list: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Erstellen: {str(e)}'
        })


@login_required
@require_POST
def update_list(request, list_id):
    """
    AJAX Endpoint: Aktualisiert Listen-Daten
    """
    keyword_list = get_object_or_404(KeywordList, id=list_id, user=request.user)

    name = request.POST.get('name', '').strip()
    color = request.POST.get('color', '').strip()
    description = request.POST.get('description', '').strip()

    try:
        if name and name != keyword_list.name:
            # Prüfe ob neuer Name bereits existiert
            if KeywordList.objects.filter(user=request.user, name=name).exclude(id=list_id).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Liste "{name}" existiert bereits'
                })
            keyword_list.name = name

        if color:
            keyword_list.color = color

        if description is not None:  # Auch leeren String erlauben
            keyword_list.description = description

        keyword_list.save()

        return JsonResponse({
            'success': True,
            'message': 'Liste wurde aktualisiert'
        })

    except Exception as e:
        logger.error(f"Error updating list: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren: {str(e)}'
        })


@login_required
@require_POST
def delete_list(request, list_id):
    """
    AJAX Endpoint: Löscht Keyword-Liste (inkl. aller Keywords)
    """
    keyword_list = get_object_or_404(KeywordList, id=list_id, user=request.user)

    try:
        list_name = keyword_list.name
        keyword_count = keyword_list.keyword_count()
        keyword_list.delete()

        return JsonResponse({
            'success': True,
            'message': f'Liste "{list_name}" und {keyword_count} Keywords wurden gelöscht'
        })

    except Exception as e:
        logger.error(f"Error deleting list: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen: {str(e)}'
        })


@login_required
@require_POST
def toggle_archive_list(request, list_id):
    """
    AJAX Endpoint: Archiviert/De-archiviert Liste
    """
    keyword_list = get_object_or_404(KeywordList, id=list_id, user=request.user)

    try:
        keyword_list.is_archived = not keyword_list.is_archived
        keyword_list.save()

        status = 'archiviert' if keyword_list.is_archived else 'wiederhergestellt'

        return JsonResponse({
            'success': True,
            'message': f'Liste "{keyword_list.name}" wurde {status}',
            'is_archived': keyword_list.is_archived
        })

    except Exception as e:
        logger.error(f"Error toggling archive: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Archivieren: {str(e)}'
        })


@login_required
@require_POST
def duplicate_list(request, list_id):
    """
    AJAX Endpoint: Dupliziert Liste inkl. aller Keywords
    """
    source_list = get_object_or_404(KeywordList, id=list_id, user=request.user)

    try:
        # Erstelle neue Liste mit "(Kopie)" im Namen
        new_name = f"{source_list.name} (Kopie)"
        counter = 1

        # Falls Name bereits existiert, nummeriere durch
        while KeywordList.objects.filter(user=request.user, name=new_name).exists():
            new_name = f"{source_list.name} (Kopie {counter})"
            counter += 1

        # Dupliziere Liste
        new_list = KeywordList.objects.create(
            user=request.user,
            name=new_name,
            color=source_list.color,
            description=source_list.description,
            position=KeywordList.objects.filter(user=request.user).count()
        )

        # Kopiere alle Keywords
        keywords = SavedKeyword.objects.filter(keyword_list=source_list)
        for keyword in keywords:
            SavedKeyword.objects.create(
                user=request.user,
                keyword_list=new_list,
                keyword=keyword.keyword,
                intent_type=keyword.intent_type,
                description=keyword.description,
                priority=keyword.priority,
                is_done=keyword.is_done,
                notes=keyword.notes
            )

        return JsonResponse({
            'success': True,
            'message': f'Liste "{new_name}" wurde erstellt ({keywords.count()} Keywords kopiert)',
            'list_id': new_list.id,
            'list_url': f'/keyengine/list/{new_list.id}/'
        })

    except Exception as e:
        logger.error(f"Error duplicating list: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Duplizieren: {str(e)}'
        })


@login_required
def export_list(request, list_id):
    """
    Exportiert Liste als CSV
    """
    keyword_list = get_object_or_404(KeywordList, id=list_id, user=request.user)

    # CSV Response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="keyengine_{keyword_list.name}_{keyword_list.id}.csv"'

    # BOM für UTF-8 (Excel-Kompatibilität)
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')

    # Header
    writer.writerow([
        'Keyword',
        'Intent',
        'Beschreibung',
        'Priorität',
        'Status',
        'Notizen',
        'Erstellt am'
    ])

    # Keywords
    keywords = SavedKeyword.objects.filter(keyword_list=keyword_list).order_by('-created_at')
    for kw in keywords:
        writer.writerow([
            kw.keyword,
            kw.intent_type,
            kw.description,
            kw.get_priority_display(),
            'Erledigt' if kw.is_done else 'Offen',
            kw.notes,
            kw.created_at.strftime('%d.%m.%Y %H:%M')
        ])

    return response


@login_required
@require_POST
def move_keyword(request, keyword_id):
    """
    AJAX Endpoint: Verschiebt Keyword in andere Liste
    """
    keyword = get_object_or_404(SavedKeyword, id=keyword_id, user=request.user)
    target_list_id = request.POST.get('target_list_id')

    if not target_list_id:
        return JsonResponse({
            'success': False,
            'error': 'Ziel-Liste fehlt'
        })

    target_list = get_object_or_404(KeywordList, id=target_list_id, user=request.user)

    try:
        # Prüfe ob Keyword bereits in Ziel-Liste existiert
        if SavedKeyword.objects.filter(keyword_list=target_list, keyword=keyword.keyword).exists():
            return JsonResponse({
                'success': False,
                'error': f'Keyword "{keyword.keyword}" existiert bereits in Liste "{target_list.name}"'
            })

        old_list_name = keyword.keyword_list.name
        keyword.keyword_list = target_list
        keyword.save()

        return JsonResponse({
            'success': True,
            'message': f'Keyword wurde von "{old_list_name}" nach "{target_list.name}" verschoben'
        })

    except Exception as e:
        logger.error(f"Error moving keyword: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Verschieben: {str(e)}'
        })
