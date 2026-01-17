import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Count, Q
from django.utils import timezone
from django.core.paginator import Paginator

from .models import (
    BacklinkSource,
    BacklinkSearch,
    SearchQuery,
    BacklinkCategory,
    SourceType,
    BacklinkSearchStatus,
)
from .services import run_backlink_search, initialize_default_queries, cleanup_old_sources

logger = logging.getLogger(__name__)


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin das Superuser-Rechte erfordert"""

    def test_func(self):
        return self.request.user.is_superuser


class BackloomDashboardView(LoginRequiredMixin, ListView):
    """
    BackLoom Dashboard - Übersicht und Statistiken
    """
    model = BacklinkSource
    template_name = 'backloom/dashboard.html'
    context_object_name = 'recent_sources'
    paginate_by = 10

    def get_queryset(self):
        return BacklinkSource.objects.order_by('-last_found')[:10]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiken
        total_sources = BacklinkSource.objects.count()
        new_sources = BacklinkSource.objects.filter(is_processed=False).count()
        processed_sources = BacklinkSource.objects.filter(is_processed=True).count()
        successful_sources = BacklinkSource.objects.filter(is_successful=True).count()

        # Kategorien-Verteilung
        category_stats = BacklinkSource.objects.values('category').annotate(
            count=Count('id')
        ).order_by('-count')

        # Letzte Suche
        last_search = BacklinkSearch.objects.first()

        # Laufende Suche
        running_search = BacklinkSearch.objects.filter(
            status=BacklinkSearchStatus.RUNNING
        ).first()

        context.update({
            'total_sources': total_sources,
            'new_sources': new_sources,
            'processed_sources': processed_sources,
            'successful_sources': successful_sources,
            'category_stats': category_stats,
            'last_search': last_search,
            'running_search': running_search,
            'categories': BacklinkCategory.choices,
            'is_superuser': self.request.user.is_superuser,
        })

        return context


class BackloomFeedView(LoginRequiredMixin, ListView):
    """
    BackLoom Feed - Liste aller Backlink-Quellen mit Filtern
    """
    model = BacklinkSource
    template_name = 'backloom/feed.html'
    context_object_name = 'sources'
    paginate_by = 25

    def get_queryset(self):
        queryset = BacklinkSource.objects.all()

        # Filter: Kategorie
        category = self.request.GET.get('category')
        if category and category in dict(BacklinkCategory.choices):
            queryset = queryset.filter(category=category)

        # Filter: Status
        status = self.request.GET.get('status')
        if status == 'new':
            queryset = queryset.filter(is_processed=False)
        elif status == 'processed':
            queryset = queryset.filter(is_processed=True, is_successful=False, is_rejected=False)
        elif status == 'successful':
            queryset = queryset.filter(is_successful=True)
        elif status == 'rejected':
            queryset = queryset.filter(is_rejected=True)

        # Filter: Qualität
        quality = self.request.GET.get('quality')
        if quality == 'high':
            queryset = queryset.filter(quality_score__gte=70)
        elif quality == 'medium':
            queryset = queryset.filter(quality_score__gte=40, quality_score__lt=70)
        elif quality == 'low':
            queryset = queryset.filter(quality_score__lt=40)

        # Filter: Quelle
        source = self.request.GET.get('source')
        if source and source in dict(SourceType.choices):
            queryset = queryset.filter(source_type=source)

        # Suche
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(domain__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )

        # Sortierung
        sort = self.request.GET.get('sort', '-last_found')
        valid_sorts = ['-last_found', 'last_found', '-quality_score', 'quality_score', 'domain', '-domain']
        if sort in valid_sorts:
            queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filter-Optionen
        context.update({
            'categories': BacklinkCategory.choices,
            'source_types': SourceType.choices,
            'current_category': self.request.GET.get('category', ''),
            'current_status': self.request.GET.get('status', ''),
            'current_quality': self.request.GET.get('quality', ''),
            'current_source': self.request.GET.get('source', ''),
            'current_sort': self.request.GET.get('sort', '-last_found'),
            'search_query': self.request.GET.get('q', ''),
        })

        return context


class BackloomSourceDetailView(LoginRequiredMixin, DetailView):
    """
    Detail-Ansicht einer Backlink-Quelle
    """
    model = BacklinkSource
    template_name = 'backloom/source_detail.html'
    context_object_name = 'source'


class BackloomSearchHistoryView(LoginRequiredMixin, ListView):
    """
    Historie aller Backlink-Suchen
    """
    model = BacklinkSearch
    template_name = 'backloom/search_history.html'
    context_object_name = 'searches'
    paginate_by = 20


# ==================
# API ENDPOINTS
# ==================

@login_required
@require_POST
def api_start_search(request):
    """
    API: Startet eine neue Backlink-Suche (nur Superuser)
    """
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Nur Superuser können Suchen starten'
        }, status=403)

    # Prüfen ob bereits eine Suche läuft
    running = BacklinkSearch.objects.filter(status=BacklinkSearchStatus.RUNNING).exists()
    if running:
        return JsonResponse({
            'success': False,
            'error': 'Es läuft bereits eine Suche'
        }, status=400)

    try:
        # Suche im Hintergrund starten (oder synchron für kleinere Suchen)
        search = run_backlink_search(request.user)

        return JsonResponse({
            'success': True,
            'message': f'Suche gestartet. {search.new_sources} neue Quellen gefunden.',
            'search_id': str(search.id),
            'new_sources': search.new_sources,
            'updated_sources': search.updated_sources
        })

    except Exception as e:
        logger.exception("Error starting backlink search")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_update_source_status(request, pk):
    """
    API: Aktualisiert den Status einer Backlink-Quelle
    """
    source = get_object_or_404(BacklinkSource, pk=pk)

    action = request.POST.get('action')

    if action == 'processed':
        source.is_processed = True
        source.is_rejected = False
        message = 'Als bearbeitet markiert'
    elif action == 'successful':
        source.is_processed = True
        source.is_successful = True
        source.is_rejected = False
        message = 'Als erfolgreich markiert'
    elif action == 'rejected':
        source.is_processed = True
        source.is_rejected = True
        source.is_successful = False
        message = 'Als abgelehnt markiert'
    elif action == 'reset':
        source.is_processed = False
        source.is_successful = False
        source.is_rejected = False
        message = 'Status zurückgesetzt'
    else:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Aktion'
        }, status=400)

    source.save()

    return JsonResponse({
        'success': True,
        'message': message,
        'is_processed': source.is_processed,
        'is_successful': source.is_successful,
        'is_rejected': source.is_rejected
    })


@login_required
@require_POST
def api_update_source_notes(request, pk):
    """
    API: Aktualisiert die Notizen einer Backlink-Quelle
    """
    source = get_object_or_404(BacklinkSource, pk=pk)

    notes = request.POST.get('notes', '')
    source.notes = notes
    source.save(update_fields=['notes', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': 'Notizen gespeichert'
    })


@login_required
@require_GET
def api_search_status(request, pk):
    """
    API: Gibt den Status einer laufenden Suche zurück
    """
    search = get_object_or_404(BacklinkSearch, pk=pk)

    return JsonResponse({
        'status': search.status,
        'status_display': search.get_status_display(),
        'sources_found': search.sources_found,
        'new_sources': search.new_sources,
        'updated_sources': search.updated_sources,
        'progress_log': search.progress_log,
        'is_running': search.status == BacklinkSearchStatus.RUNNING
    })


@login_required
@require_POST
def api_init_queries(request):
    """
    API: Initialisiert die vordefinierten Suchbegriffe (nur Superuser)
    """
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Nur Superuser können Suchbegriffe initialisieren'
        }, status=403)

    try:
        created = initialize_default_queries()
        return JsonResponse({
            'success': True,
            'message': f'{created} Suchbegriffe erstellt'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_cleanup_old(request):
    """
    API: Löscht alte Backlink-Quellen (nur Superuser)
    """
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Nur Superuser können Daten bereinigen'
        }, status=403)

    try:
        deleted = cleanup_old_sources(months=12)
        return JsonResponse({
            'success': True,
            'message': f'{deleted} alte Einträge gelöscht'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def api_stats(request):
    """
    API: Gibt aktuelle Statistiken zurück
    """
    stats = {
        'total': BacklinkSource.objects.count(),
        'new': BacklinkSource.objects.filter(is_processed=False).count(),
        'processed': BacklinkSource.objects.filter(is_processed=True).count(),
        'successful': BacklinkSource.objects.filter(is_successful=True).count(),
        'rejected': BacklinkSource.objects.filter(is_rejected=True).count(),
    }

    return JsonResponse(stats)
