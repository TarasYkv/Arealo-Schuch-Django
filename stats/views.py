from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta, datetime
from django.http import JsonResponse, HttpResponse
import csv
from django.template.loader import render_to_string
import json
from accounts.models import CustomUser, UserLoginHistory
from .models import (
    PageVisit, UserSession, AdClick, DailyStats, PopularPage,
    RealTimeVisitor, ConversionFunnel, ConversionEvent, PerformanceMetric, ErrorLog, SearchQuery
)


def superuser_required(user):
    return user.is_superuser


@user_passes_test(superuser_required)
def dashboard(request):
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    # Heute's Stats
    today_visits = PageVisit.objects.filter(visit_time__date=today).count()
    today_unique_visitors = PageVisit.objects.filter(
        visit_time__date=today
    ).values('ip_address').distinct().count()
    today_ad_clicks = AdClick.objects.filter(click_time__date=today).count()

    # 7 Tage Stats
    week_visits = PageVisit.objects.filter(visit_time__date__gte=last_7_days).count()
    week_unique_visitors = PageVisit.objects.filter(
        visit_time__date__gte=last_7_days
    ).values('ip_address').distinct().count()
    week_ad_clicks = AdClick.objects.filter(click_time__date__gte=last_7_days).count()

    # 30 Tage Stats
    month_visits = PageVisit.objects.filter(visit_time__date__gte=last_30_days).count()
    month_unique_visitors = PageVisit.objects.filter(
        visit_time__date__gte=last_30_days
    ).values('ip_address').distinct().count()
    month_ad_clicks = AdClick.objects.filter(click_time__date__gte=last_30_days).count()

    # Beliebteste Seiten
    popular_pages = PopularPage.objects.all()[:10]

    # Letzte Besuche
    recent_visits = PageVisit.objects.select_related('user').all()[:20]

    # Durchschnittliche Session-Dauer (letzte 7 Tage)
    active_sessions = UserSession.objects.filter(
        start_time__date__gte=last_7_days
    )
    avg_duration = None
    if active_sessions.exists():
        total_duration = sum(
            [(session.last_activity - session.start_time).total_seconds()
             for session in active_sessions],
            0
        )
        avg_duration = total_duration / active_sessions.count() / 60  # in Minuten

    # Traffic-Quellen-Analyse
    traffic_sources = analyze_traffic_sources(last_7_days)

    # Device & Browser Analytics
    device_stats = analyze_device_stats(last_7_days)

    # Real-time visitors
    online_visitors = RealTimeVisitor.objects.filter(
        last_seen__gte=timezone.now() - timedelta(minutes=5)
    ).count()

    # Performance Metrics
    latest_performance = PerformanceMetric.objects.first()

    # Search Analytics
    search_stats = analyze_search_stats(last_7_days)

    # Error Analytics
    error_stats = analyze_error_stats(last_7_days)

    # User Journey Analytics
    journey_stats = analyze_user_journey(last_7_days)

    # Time-based Activity Analysis
    activity_heatmap = analyze_activity_heatmap(last_7_days)

    # Geographic Analytics
    geographic_stats = analyze_geographic_stats(last_7_days)

    # Bounce Rate Analysis
    bounce_rate_stats = analyze_bounce_rate(last_7_days)

    # SEO Metrics
    seo_metrics = analyze_seo_metrics(last_7_days)

    # User registrations & logins timeline
    try:
        selected_period = int(request.GET.get('user_period', 30))
    except (TypeError, ValueError):
        selected_period = 30
    selected_period = max(7, min(selected_period, 180))

    period_start = today - timedelta(days=selected_period - 1)

    registration_qs = CustomUser.objects.filter(
        date_joined__date__gte=period_start,
        date_joined__date__lte=today
    ).annotate(reg_date=TruncDate('date_joined'))

    registration_counts = registration_qs.values('reg_date').annotate(total=Count('id'))
    registration_map = {entry['reg_date']: entry['total'] for entry in registration_counts}

    login_qs = UserLoginHistory.objects.filter(
        login_time__date__gte=period_start,
        login_time__date__lte=today
    ).annotate(login_date=TruncDate('login_time'))

    login_counts = login_qs.values('login_date').annotate(total=Count('id'))
    login_map = {entry['login_date']: entry['total'] for entry in login_counts}

    timeline_labels = []
    registrations_per_day = []
    logins_per_day = []

    current_date = period_start
    while current_date <= today:
        label = current_date.strftime('%d.%m.%Y')
        timeline_labels.append(label)
        registrations_per_day.append(registration_map.get(current_date, 0))
        logins_per_day.append(login_map.get(current_date, 0))
        current_date += timedelta(days=1)

    context = {
        'today_visits': today_visits,
        'today_unique_visitors': today_unique_visitors,
        'today_ad_clicks': today_ad_clicks,
        'week_visits': week_visits,
        'week_unique_visitors': week_unique_visitors,
        'week_ad_clicks': week_ad_clicks,
        'month_visits': month_visits,
        'month_unique_visitors': month_unique_visitors,
        'month_ad_clicks': month_ad_clicks,
        'popular_pages': popular_pages,
        'recent_visits': recent_visits,
        'avg_duration': avg_duration,
        'traffic_sources': traffic_sources,
        'device_stats': device_stats,
        'online_visitors': online_visitors,
        'latest_performance': latest_performance,
        'search_stats': search_stats,
        'error_stats': error_stats,
        'journey_stats': journey_stats,
        'activity_heatmap': activity_heatmap,
        'geographic_stats': geographic_stats,
        'bounce_rate_stats': bounce_rate_stats,
        'seo_metrics': seo_metrics,
        'user_activity_labels': json.dumps(timeline_labels),
        'user_registration_counts': json.dumps(registrations_per_day),
        'user_login_counts': json.dumps(logins_per_day),
        'user_activity_period_options': [7, 14, 30, 60, 90, 120, 180],
        'user_activity_selected_period': selected_period,
    }

    return render(request, 'stats/dashboard.html', context)


@user_passes_test(superuser_required)
def dashboard_standalone(request):
    """Standalone Dashboard ohne base.html Template"""
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    # Heute's Stats
    today_visits = PageVisit.objects.filter(visit_time__date=today).count()
    today_unique_visitors = PageVisit.objects.filter(
        visit_time__date=today
    ).values('ip_address').distinct().count()
    today_ad_clicks = AdClick.objects.filter(click_time__date=today).count()

    # 7 Tage Stats
    week_visits = PageVisit.objects.filter(visit_time__date__gte=last_7_days).count()
    week_unique_visitors = PageVisit.objects.filter(
        visit_time__date__gte=last_7_days
    ).values('ip_address').distinct().count()
    week_ad_clicks = AdClick.objects.filter(click_time__date__gte=last_7_days).count()

    # 30 Tage Stats
    month_visits = PageVisit.objects.filter(visit_time__date__gte=last_30_days).count()
    month_unique_visitors = PageVisit.objects.filter(
        visit_time__date__gte=last_30_days
    ).values('ip_address').distinct().count()
    month_ad_clicks = AdClick.objects.filter(click_time__date__gte=last_30_days).count()

    # Beliebteste Seiten
    popular_pages = PopularPage.objects.all()[:10]

    # Letzte Besuche
    recent_visits = PageVisit.objects.select_related('user').all()[:20]

    # Durchschnittliche Session-Dauer (letzte 7 Tage)
    active_sessions = UserSession.objects.filter(
        start_time__date__gte=last_7_days
    )
    avg_duration = None
    if active_sessions.exists():
        total_duration = sum(
            [(session.last_activity - session.start_time).total_seconds()
             for session in active_sessions],
            0
        )
        avg_duration = total_duration / active_sessions.count() / 60  # in Minuten

    # Traffic-Quellen-Analyse
    traffic_sources = analyze_traffic_sources(last_7_days)

    # Activity Heatmap für standalone
    activity_heatmap = analyze_activity_heatmap(last_7_days)

    # Geographic Analytics für standalone
    geographic_stats = analyze_geographic_stats(last_7_days)

    # Bounce Rate Analysis für standalone
    bounce_rate_stats = analyze_bounce_rate(last_7_days)

    context = {
        'today_visits': today_visits,
        'today_unique_visitors': today_unique_visitors,
        'today_ad_clicks': today_ad_clicks,
        'week_visits': week_visits,
        'week_unique_visitors': week_unique_visitors,
        'week_ad_clicks': week_ad_clicks,
        'month_visits': month_visits,
        'month_unique_visitors': month_unique_visitors,
        'month_ad_clicks': month_ad_clicks,
        'popular_pages': popular_pages,
        'recent_visits': recent_visits,
        'avg_duration': avg_duration,
        'traffic_sources': traffic_sources,
        'activity_heatmap': activity_heatmap,
        'geographic_stats': geographic_stats,
        'bounce_rate_stats': bounce_rate_stats,
        'seo_metrics': seo_metrics,
    }

    return render(request, 'stats/dashboard_standalone.html', context)


@user_passes_test(superuser_required)
def visits_detail(request):
    visits = PageVisit.objects.select_related('user').all()[:100]

    # Erweitere die Besuche mit zusätzlichen Informationen
    enriched_visits = []
    for visit in visits:
        # App-Name aus URL ableiten
        app_name = extract_app_name_from_url(visit.url)

        # Session-Dauer berechnen
        session_duration = None
        if visit.session_key:
            try:
                user_session = UserSession.objects.get(session_key=visit.session_key)
                # Berechne die Zeit seit dem letzten Besuch in dieser Session
                next_visit = PageVisit.objects.filter(
                    session_key=visit.session_key,
                    visit_time__gt=visit.visit_time
                ).first()

                if next_visit:
                    duration = (next_visit.visit_time - visit.visit_time).total_seconds()
                    session_duration = int(duration) if duration < 300 else None  # Max 5 Minuten
                elif user_session.last_activity != user_session.start_time:
                    duration = (user_session.last_activity - visit.visit_time).total_seconds()
                    session_duration = int(duration) if duration < 300 else None
            except UserSession.DoesNotExist:
                pass

        # Referrer-Analyse
        referer_source = None
        referer_icon = None
        if visit.referer:
            from urllib.parse import urlparse
            try:
                parsed_url = urlparse(visit.referer)
                domain = parsed_url.netloc.lower()
                referer_source = get_source_name(domain)
                referer_icon = get_source_icon(domain)
            except:
                pass

        # Füge die zusätzlichen Attribute hinzu
        visit.app_name = app_name
        visit.session_duration = session_duration
        visit.referer_source = referer_source
        visit.referer_icon = referer_icon
        enriched_visits.append(visit)

    return render(request, 'stats/visits_detail.html', {'visits': enriched_visits})


def extract_app_name_from_url(url):
    """Extrahiert den App-Namen aus der URL"""
    import re
    from urllib.parse import urlparse

    try:
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')

        # App-Mappings basierend auf der URL-Struktur
        app_mappings = {
            'accounts': 'Accounts',
            'rechner': 'Amortisation',
            'sportplatz': 'Sportplatz',
            'pdf-tool': 'PDF Sucher',
            'schulungen': 'Schulungen',
            'todos': 'ToDos',
            'chat': 'Chat',
            'shopify': 'Shopify',
            'images': 'Bildbearbeitung',
            'organization': 'Organisation',
            'videos': 'Videos',
            'promptpro': 'PromptPro',
            'payments': 'Zahlungen',
            'mail': 'Mail',
            'email-templates': 'Email Vorlagen',
            'somi-plan': 'Somi Plan',
            'makeads': 'MakeAds',
            'streamrec': 'StreamRec',
            'superconfig': 'SuperConfig',
            'loomads': 'LoomAds',
            'loomline': 'LoomLine',
            'fileshare': 'FileShare',
            'stats': 'Statistiken',
            'beleuchtungsrechner': 'Beleuchtung',
            'din-en-13201': 'DIN EN 13201',
            'licht': 'Lichttechnik',
        }

        # Erste Pfadkomponente extrahieren
        if path:
            first_segment = path.split('/')[0]
            return app_mappings.get(first_segment, first_segment.title())
        else:
            return 'Startseite'

    except Exception:
        return None


def analyze_traffic_sources(since_date):
    """Analysiert Traffic-Quellen basierend auf Referer-URLs"""
    from urllib.parse import urlparse
    from django.db.models import Count

    # Hole alle Besuche mit Referer seit dem angegebenen Datum
    visits_with_referer = PageVisit.objects.filter(
        visit_time__date__gte=since_date,
        referer__isnull=False
    ).exclude(referer='')

    # Gruppiere nach Referer-Domain
    referer_stats = {}

    for visit in visits_with_referer:
        try:
            parsed_url = urlparse(visit.referer)
            domain = parsed_url.netloc.lower()

            # Ignoriere lokale/interne Referrer
            if domain in ['127.0.0.1:8000', 'localhost:8000', 'workloom.de', 'www.workloom.de']:
                continue

            if domain not in referer_stats:
                referer_stats[domain] = {
                    'count': 0,
                    'full_url': visit.referer,
                    'name': get_source_name(domain),
                    'icon': get_source_icon(domain),
                    'icon_class': get_source_icon_class(domain)
                }
            referer_stats[domain]['count'] += 1

        except Exception:
            continue

    # Direkter Traffic (ohne Referer)
    direct_count = PageVisit.objects.filter(
        visit_time__date__gte=since_date,
        referer__isnull=True
    ).count() + PageVisit.objects.filter(
        visit_time__date__gte=since_date,
        referer=''
    ).count()

    if direct_count > 0:
        referer_stats['direct'] = {
            'count': direct_count,
            'full_url': '',
            'name': 'Direkter Zugriff',
            'icon': '🏠',
            'icon_class': 'default'
        }

    # Sortiere nach Anzahl und gib Top 10 zurück
    return sorted(referer_stats.values(), key=lambda x: x['count'], reverse=True)[:10]


def get_source_name(domain):
    """Gibt einen benutzerfreundlichen Namen für die Traffic-Quelle zurück"""
    source_names = {
        'google.com': 'Google',
        'google.de': 'Google Deutschland',
        'bing.com': 'Bing',
        'yahoo.com': 'Yahoo',
        'duckduckgo.com': 'DuckDuckGo',
        'facebook.com': 'Facebook',
        'instagram.com': 'Instagram',
        'twitter.com': 'Twitter / X',
        'x.com': 'X (Twitter)',
        'linkedin.com': 'LinkedIn',
        'youtube.com': 'YouTube',
        'wikipedia.org': 'Wikipedia',
        'github.com': 'GitHub',
        'stackoverflow.com': 'Stack Overflow',
        't.me': 'Telegram',
        'whatsapp.com': 'WhatsApp',
    }

    # Prüfe auf Subdomains
    for known_domain, name in source_names.items():
        if domain.endswith(known_domain):
            return name

    return domain.replace('www.', '').title()


def get_source_icon(domain):
    """Gibt ein passendes Icon für die Traffic-Quelle zurück"""
    source_icons = {
        'google.com': '🔍',
        'google.de': '🔍',
        'bing.com': '🔎',
        'yahoo.com': '📧',
        'duckduckgo.com': '🦆',
        'facebook.com': '📘',
        'instagram.com': '📷',
        'twitter.com': '🐦',
        'x.com': '❌',
        'linkedin.com': '💼',
        'youtube.com': '📺',
        'wikipedia.org': '📚',
        'github.com': '🐙',
        'stackoverflow.com': '💻',
        't.me': '✈️',
        'whatsapp.com': '💬',
    }

    for known_domain, icon in source_icons.items():
        if domain.endswith(known_domain):
            return icon

    return '🌐'


def get_source_icon_class(domain):
    """Gibt eine CSS-Klasse für das Icon zurück"""
    if 'google' in domain:
        return 'accounts'
    elif 'facebook' in domain or 'instagram' in domain:
        return 'chat'
    elif 'linkedin' in domain or 'github' in domain:
        return 'stats'
    elif 'youtube' in domain:
        return 'loomads'
    else:
        return 'default'


def analyze_device_stats(since_date):
    """Analysiert Device & Browser Statistics"""
    from django.db.models import Count

    visits = PageVisit.objects.filter(visit_time__date__gte=since_date)

    # Device Type Statistics
    device_stats = visits.values('device_type').annotate(
        count=Count('id')
    ).order_by('-count')

    # Browser Statistics
    browser_stats = visits.values('browser').annotate(
        count=Count('id')
    ).order_by('-count')

    # OS Statistics
    os_stats = visits.values('os').annotate(
        count=Count('id')
    ).order_by('-count')

    # Add icons and names
    device_icons = {
        'mobile': '📱',
        'desktop': '💻',
        'tablet': '📟',
        '': '❓'
    }

    browser_icons = {
        'Chrome': '🌐',
        'Firefox': '🦊',
        'Safari': '🧭',
        'Edge': '🔷',
        'Opera': '🎭',
        'Unknown': '❓',
        '': '❓'
    }

    os_icons = {
        'Windows': '🪟',
        'macOS': '🍎',
        'Android': '🤖',
        'iOS': '📱',
        'Linux': '🐧',
        'Unknown': '❓',
        '': '❓'
    }

    # Enrich with icons
    for stat in device_stats:
        stat['icon'] = device_icons.get(stat['device_type'], '❓')
        stat['name'] = stat['device_type'].title() if stat['device_type'] else 'Unbekannt'

    for stat in browser_stats:
        stat['icon'] = browser_icons.get(stat['browser'], '❓')
        stat['name'] = stat['browser'] if stat['browser'] else 'Unbekannt'

    for stat in os_stats:
        stat['icon'] = os_icons.get(stat['os'], '❓')
        stat['name'] = stat['os'] if stat['os'] else 'Unbekannt'

    return {
        'devices': list(device_stats)[:5],
        'browsers': list(browser_stats)[:5],
        'operating_systems': list(os_stats)[:5]
    }


def analyze_search_stats(since_date):
    """Analysiert Suchstatistiken"""
    from django.db.models import Count, Q

    # Top Suchbegriffe
    top_searches = SearchQuery.objects.filter(
        timestamp__date__gte=since_date
    ).values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Suchbegriffe ohne Ergebnisse
    no_results = SearchQuery.objects.filter(
        timestamp__date__gte=since_date,
        results_count=0
    ).values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # Gesamt-Statistiken
    total_searches = SearchQuery.objects.filter(timestamp__date__gte=since_date).count()
    avg_results = SearchQuery.objects.filter(
        timestamp__date__gte=since_date
    ).aggregate(avg_results=Avg('results_count'))['avg_results'] or 0

    return {
        'top_searches': list(top_searches),
        'no_results': list(no_results),
        'total_searches': total_searches,
        'avg_results': round(avg_results, 1)
    }


def analyze_error_stats(since_date):
    """Analysiert Error-Statistiken mit erweiterten Details"""
    from django.db.models import Count, Avg

    # Error Types mit Severity
    error_types = ErrorLog.objects.filter(
        timestamp__date__gte=since_date
    ).values('error_type', 'severity').annotate(
        count=Count('id')
    ).order_by('-count')

    # Gruppiere nach error_type
    grouped_errors = {}
    for error in error_types:
        error_type = error['error_type']
        if error_type not in grouped_errors:
            grouped_errors[error_type] = {
                'error_type': error_type,
                'count': 0,
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0
            }
        grouped_errors[error_type]['count'] += error['count']
        grouped_errors[error_type][error['severity']] += error['count']

    # Top Error-Locations (File + Line)
    error_locations = ErrorLog.objects.filter(
        timestamp__date__gte=since_date,
        file_path__isnull=False
    ).exclude(file_path='').values('file_path', 'line_number', 'view_name').annotate(
        count=Count('id'),
        avg_duration=Avg('request_duration')
    ).order_by('-count')[:8]

    # Most Affected Users
    affected_users = ErrorLog.objects.filter(
        timestamp__date__gte=since_date,
        user__isnull=False
    ).values('user__username', 'user__is_staff', 'user__is_superuser').annotate(
        error_count=Count('id')
    ).order_by('-error_count')[:5]

    # Performance Impact
    slow_errors = ErrorLog.objects.filter(
        timestamp__date__gte=since_date,
        request_duration__isnull=False,
        request_duration__gt=2.0  # Slower than 2 seconds
    ).values('view_name', 'app_name').annotate(
        count=Count('id'),
        avg_duration=Avg('request_duration')
    ).order_by('-avg_duration')[:5]

    # Error Timeline (last 24 hours by hour)
    from collections import defaultdict
    error_timeline = defaultdict(int)
    recent_errors = ErrorLog.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    )

    for error in recent_errors:
        hour = error.timestamp.strftime('%H')
        error_timeline[hour] += 1

    timeline_data = []
    for hour in range(24):
        hour_str = f"{hour:02d}"
        timeline_data.append({
            'hour': hour_str,
            'count': error_timeline[hour_str]
        })

    # Error Icons
    error_icons = {
        '404': '🔍',
        '500': '⚠️',
        '403': '🔒',
        '400': '❌',
        'js': '🐛',
        'timeout': '⏱️',
        'memory': '💾',
        'database': '🗄️',
        'permission': '🚫',
        'validation': '✋'
    }

    # Add icons and names
    for error_type, data in grouped_errors.items():
        data['icon'] = error_icons.get(error_type, '❓')
        data['name'] = dict(ErrorLog.ERROR_TYPES).get(error_type, error_type)

    # Severity Summary
    severity_counts = ErrorLog.objects.filter(
        timestamp__date__gte=since_date
    ).values('severity').annotate(count=Count('id'))

    severity_summary = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for item in severity_counts:
        severity_summary[item['severity']] = item['count']

    # Unresolved Critical Errors
    critical_unresolved = ErrorLog.objects.filter(
        severity='critical',
        is_resolved=False
    ).count()

    total_errors = ErrorLog.objects.filter(timestamp__date__gte=since_date).count()

    # Get URLs where errors occurred for debugging
    enhanced_locations = []
    for location in error_locations:
        enhanced_location = dict(location)

        # Get the actual error URLs for this location
        error_urls = ErrorLog.objects.filter(
            file_path=location['file_path'],
            line_number=location['line_number']
        ).values_list('url', flat=True).distinct()[:3]  # Get up to 3 example URLs

        enhanced_location['error_urls'] = list(error_urls)
        enhanced_locations.append(enhanced_location)

    return {
        'error_types': list(grouped_errors.values())[:8],
        'error_locations': enhanced_locations,
        'affected_users': list(affected_users),
        'slow_errors': list(slow_errors),
        'timeline_data': timeline_data,
        'severity_summary': severity_summary,
        'critical_unresolved': critical_unresolved,
        'total_errors': total_errors
    }


def analyze_user_journey(since_date):
    """Analysiert User Journey und Session-Pfade"""
    from django.db.models import Count, F
    from collections import defaultdict

    # Entry Pages (Einstiegsseiten)
    entry_pages = PageVisit.objects.filter(
        visit_time__date__gte=since_date
    ).values('url').annotate(
        count=Count('session_key', distinct=True)
    ).order_by('-count')[:8]

    # Exit Pages (Ausstiegsseiten) - letzte Seite in Session
    exit_pages = []
    sessions = UserSession.objects.filter(
        start_time__date__gte=since_date
    ).values_list('session_key', flat=True)[:100]

    for session_key in sessions:
        last_visit = PageVisit.objects.filter(
            session_key=session_key
        ).order_by('-visit_time').first()
        if last_visit:
            exit_pages.append(last_visit.url)

    exit_page_counts = defaultdict(int)
    for page in exit_pages:
        exit_page_counts[page] += 1

    top_exit_pages = sorted(exit_page_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Session Flow Analysis
    session_flows = []
    for session_key in list(sessions)[:10]:
        visits = PageVisit.objects.filter(
            session_key=session_key
        ).order_by('visit_time').values('url', 'page_title')[:5]

        if visits.count() > 1:
            flow = []
            for visit in visits:
                app_name = extract_app_name_from_url(visit['url'])
                page_name = app_name or visit['page_title'] or 'Unbekannt'
                flow.append({
                    'page': page_name,
                    'url': visit['url'],
                    'icon': get_app_icon(app_name)
                })
            session_flows.append(flow)

    # Drop-off Analysis
    page_sequences = defaultdict(int)
    for session_key in list(sessions)[:50]:
        visits = list(PageVisit.objects.filter(
            session_key=session_key
        ).order_by('visit_time').values('url')[:3])

        for i in range(len(visits) - 1):
            current_app = extract_app_name_from_url(visits[i]['url'])
            next_app = extract_app_name_from_url(visits[i + 1]['url'])
            if current_app and next_app:
                page_sequences[f"{current_app} → {next_app}"] += 1

    top_sequences = sorted(page_sequences.items(), key=lambda x: x[1], reverse=True)[:5]

    # Add icons to entry pages
    for page in entry_pages:
        app_name = extract_app_name_from_url(page['url'])
        page['app_name'] = app_name
        page['icon'] = get_app_icon(app_name)

    return {
        'entry_pages': list(entry_pages),
        'exit_pages': [{'url': url, 'count': count, 'app_name': extract_app_name_from_url(url), 'icon': get_app_icon(extract_app_name_from_url(url))} for url, count in top_exit_pages],
        'session_flows': session_flows[:5],
        'top_sequences': top_sequences,
        'total_sessions': len(sessions)
    }


def get_app_icon(app_name):
    """Gibt Icons für verschiedene Apps zurück"""
    app_icons = {
        'Accounts': '👤',
        'Amortisation': '💰',
        'Sportplatz': '⚽',
        'PDF Sucher': '📄',
        'Schulungen': '📚',
        'ToDos': '✅',
        'Chat': '💬',
        'Shopify': '🛒',
        'Bildbearbeitung': '🖼️',
        'Organisation': '🏢',
        'Videos': '🎥',
        'PromptPro': '🤖',
        'Zahlungen': '💳',
        'Mail': '📧',
        'Email Vorlagen': '📨',
        'Somi Plan': '📋',
        'MakeAds': '📢',
        'StreamRec': '📹',
        'SuperConfig': '⚙️',
        'LoomAds': '📱',
        'LoomLine': '📞',
        'FileShare': '📁',
        'Statistiken': '📊',
        'Beleuchtung': '💡',
        'DIN EN 13201': '📐',
        'Lichttechnik': '🔦',
        'Startseite': '🏠',
    }
    return app_icons.get(app_name, '📄')


def analyze_activity_heatmap(since_date):
    """Analysiert zeitbasierte Aktivitäten für Heatmap"""
    from django.db.models import Count
    from collections import defaultdict

    # Hole alle Visits seit dem Datum
    visits = PageVisit.objects.filter(visit_time__date__gte=since_date)

    # Erstelle 24h x 7 Tage Heatmap
    heatmap_data = defaultdict(lambda: defaultdict(int))

    # Wochentage auf Deutsch
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

    for visit in visits:
        # Wochentag (0=Montag, 6=Sonntag)
        weekday = visit.visit_time.weekday()
        weekday_name = weekdays[weekday]

        # Stunde (0-23)
        hour = visit.visit_time.hour

        heatmap_data[weekday_name][hour] += 1

    # Finde den höchsten Wert für Normalisierung
    max_value = 0
    for day_data in heatmap_data.values():
        for hour_count in day_data.values():
            if hour_count > max_value:
                max_value = hour_count

    # Konvertiere zu Template-freundlichem Format
    heatmap = []
    for day in weekdays:
        day_data = []
        for hour in range(24):
            count = heatmap_data[day][hour]
            intensity = (count / max_value * 100) if max_value > 0 else 0

            # Bestimme Farb-Intensität
            if intensity == 0:
                color_class = 'activity-none'
            elif intensity < 25:
                color_class = 'activity-low'
            elif intensity < 50:
                color_class = 'activity-medium'
            elif intensity < 75:
                color_class = 'activity-high'
            else:
                color_class = 'activity-very-high'

            day_data.append({
                'hour': hour,
                'count': count,
                'intensity': intensity,
                'color_class': color_class
            })

        heatmap.append({
            'day': day,
            'hours': day_data
        })

    # Peak-Zeit Analysis
    peak_hours = defaultdict(int)
    for visit in visits:
        peak_hours[visit.visit_time.hour] += 1

    top_peak_hour = max(peak_hours.items(), key=lambda x: x[1]) if peak_hours else (12, 0)

    return {
        'heatmap': heatmap,
        'max_value': max_value,
        'peak_hour': top_peak_hour[0],
        'peak_count': top_peak_hour[1],
        'total_visits': visits.count()
    }


def analyze_geographic_stats(since_date):
    """Analysiert geografische Besucherverteilung"""
    from django.db.models import Count

    # Länder-Statistiken
    country_stats = PageVisit.objects.filter(
        visit_time__date__gte=since_date
    ).values('country').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # City-Statistiken
    city_stats = PageVisit.objects.filter(
        visit_time__date__gte=since_date,
        city__isnull=False
    ).exclude(city='').values('city', 'country').annotate(
        count=Count('id')
    ).order_by('-count')[:8]

    # Länder-Icons
    country_flags = {
        'Deutschland': '🇩🇪',
        'Österreich': '🇦🇹',
        'Schweiz': '🇨🇭',
        'Niederlande': '🇳🇱',
        'Frankreich': '🇫🇷',
        'Italien': '🇮🇹',
        'Spanien': '🇪🇸',
        'Polen': '🇵🇱',
        'USA': '🇺🇸',
        'Kanada': '🇨🇦',
        'Vereinigtes Königreich': '🇬🇧'
    }

    # Füge Flaggen hinzu
    for country in country_stats:
        country['flag'] = country_flags.get(country['country'], '🌍')

    for city in city_stats:
        city['flag'] = country_flags.get(city['country'], '🌍')

    # Top Country
    top_country = country_stats[0] if country_stats else {'country': 'Unbekannt', 'count': 0}

    return {
        'countries': list(country_stats),
        'cities': list(city_stats),
        'top_country': top_country,
        'total_countries': len(country_stats)
    }


def analyze_seo_metrics(since_date=None):
    """Analysiert SEO-relevante Metriken"""
    from .models import CoreWebVitals, CrawlError, BrokenLink, SitemapStatus, RobotsTxtStatus
    from django.db.models import Avg, Count
    import requests
    from urllib.parse import urlparse

    # Core Web Vitals
    core_web_vitals = CoreWebVitals.objects.all().order_by('-timestamp')[:10]

    # Durchschnittswerte berechnen
    avg_vitals = CoreWebVitals.objects.aggregate(
        avg_lcp=Avg('lcp'),
        avg_fid=Avg('fid'),
        avg_cls=Avg('cls')
    )

    # Crawl Errors
    crawl_errors = CrawlError.objects.filter(
        is_resolved=False
    ).order_by('-last_checked')[:10]

    # Broken Links
    broken_links = BrokenLink.objects.filter(
        is_fixed=False
    ).order_by('-last_checked')[:10]

    # Sitemap Status
    domain = '127.0.0.1:8000'  # Oder aus settings holen
    sitemap_url = f'http://{domain}/sitemap.xml'

    sitemap_status, created = SitemapStatus.objects.get_or_create(
        sitemap_url=sitemap_url
    )

    # Robots.txt Status
    robots_status, created = RobotsTxtStatus.objects.get_or_create(
        domain=domain
    )

    # Check robots.txt
    try:
        response = requests.get(f'http://{domain}/robots.txt', timeout=5)
        robots_status.is_accessible = response.status_code == 200
        if response.status_code == 200:
            robots_status.content = response.text
            # Parse robots.txt content
            lines = response.text.split('\n')
            for line in lines:
                if line.lower().startswith('sitemap:'):
                    sitemap_ref = line.split(':', 1)[1].strip()
                    if sitemap_ref not in robots_status.sitemap_references:
                        robots_status.sitemap_references.append(sitemap_ref)
                elif line.lower().startswith('crawl-delay:'):
                    robots_status.crawl_delay = int(line.split(':')[1].strip())
        robots_status.save()
    except:
        robots_status.is_accessible = False
        robots_status.save()

    # SEO Score berechnen
    seo_score = 100
    seo_issues = []

    # Core Web Vitals Score
    if avg_vitals['avg_lcp'] and avg_vitals['avg_lcp'] > 2.5:
        seo_score -= 10
        seo_issues.append('Slow Loading (LCP > 2.5s)')
    if avg_vitals['avg_fid'] and avg_vitals['avg_fid'] > 100:
        seo_score -= 10
        seo_issues.append('Poor Interactivity (FID > 100ms)')
    if avg_vitals['avg_cls'] and avg_vitals['avg_cls'] > 0.1:
        seo_score -= 10
        seo_issues.append('Layout Shift Issues (CLS > 0.1)')

    # Crawl Errors
    if crawl_errors.count() > 0:
        seo_score -= min(crawl_errors.count() * 5, 20)
        seo_issues.append(f'{crawl_errors.count()} Crawl Errors')

    # Broken Links
    if broken_links.count() > 0:
        seo_score -= min(broken_links.count() * 3, 15)
        seo_issues.append(f'{broken_links.count()} Broken Links')

    # Robots.txt
    if not robots_status.is_accessible:
        seo_score -= 10
        seo_issues.append('robots.txt not accessible')

    return {
        'core_web_vitals': list(core_web_vitals.values()),
        'avg_vitals': avg_vitals,
        'crawl_errors': list(crawl_errors.values()),
        'broken_links': list(broken_links.values()),
        'sitemap_status': {
            'url': sitemap_status.sitemap_url,
            'is_accessible': sitemap_status.is_accessible,
            'total_urls': sitemap_status.total_urls,
            'last_checked': sitemap_status.last_checked
        },
        'robots_status': {
            'domain': robots_status.domain,
            'is_accessible': robots_status.is_accessible,
            'crawl_delay': robots_status.crawl_delay,
            'sitemap_references': robots_status.sitemap_references
        },
        'seo_score': max(0, seo_score),
        'seo_issues': seo_issues
    }


def analyze_bounce_rate(since_date):
    """Analysiert Bounce Rate und Session-Qualität"""
    from django.db.models import Count
    from collections import defaultdict

    # Hole alle Sessions
    sessions = UserSession.objects.filter(start_time__date__gte=since_date)

    bounce_count = 0
    total_sessions = sessions.count()

    if total_sessions == 0:
        return {
            'bounce_rate': 0,
            'bounced_sessions': 0,
            'total_sessions': 0,
            'avg_pages_per_session': 0,
            'quality_score': 'N/A'
        }

    for session in sessions:
        if session.page_count <= 1:
            bounce_count += 1

    bounce_rate = (bounce_count / total_sessions) * 100

    # Durchschnittliche Seiten pro Session
    avg_pages = sessions.aggregate(avg_pages=Avg('page_count'))['avg_pages'] or 0

    # Session-Qualitäts-Score
    if bounce_rate < 25:
        quality_score = 'Exzellent 🌟'
        quality_class = 'success'
    elif bounce_rate < 40:
        quality_score = 'Gut ✅'
        quality_class = 'info'
    elif bounce_rate < 60:
        quality_score = 'OK ⚠️'
        quality_class = 'warning'
    else:
        quality_score = 'Verbesserung nötig 🔴'
        quality_class = 'danger'

    # Entry Page Bounce Analysis
    entry_page_bounces = defaultdict(lambda: {'bounces': 0, 'total': 0})

    for session in sessions:
        first_visit = PageVisit.objects.filter(
            session_key=session.session_key
        ).order_by('visit_time').first()

        if first_visit:
            app_name = extract_app_name_from_url(first_visit.url)
            entry_page_bounces[app_name]['total'] += 1
            if session.page_count <= 1:
                entry_page_bounces[app_name]['bounces'] += 1

    # Berechne Bounce Rate pro Entry Page
    page_bounce_rates = []
    for page, data in entry_page_bounces.items():
        if data['total'] > 0:
            page_bounce_rate = (data['bounces'] / data['total']) * 100
            page_bounce_rates.append({
                'page': page or 'Unbekannt',
                'bounce_rate': round(page_bounce_rate, 1),
                'bounces': data['bounces'],
                'total': data['total'],
                'icon': get_app_icon(page)
            })

    # Sortiere nach Bounce Rate
    page_bounce_rates.sort(key=lambda x: x['bounce_rate'], reverse=True)

    return {
        'bounce_rate': round(bounce_rate, 1),
        'bounced_sessions': bounce_count,
        'total_sessions': total_sessions,
        'avg_pages_per_session': round(avg_pages, 1),
        'quality_score': quality_score,
        'quality_class': quality_class,
        'page_bounce_rates': page_bounce_rates[:8]
    }


@user_passes_test(superuser_required)
def ad_clicks_detail(request):
    ad_clicks = AdClick.objects.select_related('user').all()[:100]
    return render(request, 'stats/ad_clicks_detail.html', {'ad_clicks': ad_clicks})


@user_passes_test(superuser_required)
def chart_data(request):
    chart_type = request.GET.get('type', 'visits')
    days = int(request.GET.get('days', 7))

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days-1)

    data = []
    labels = []

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        labels.append(current_date.strftime('%d.%m'))

        if chart_type == 'visits':
            count = PageVisit.objects.filter(visit_time__date=current_date).count()
        elif chart_type == 'unique_visitors':
            count = PageVisit.objects.filter(
                visit_time__date=current_date
            ).values('ip_address').distinct().count()
        elif chart_type == 'ad_clicks':
            count = AdClick.objects.filter(click_time__date=current_date).count()
        else:
            count = 0

        data.append(count)

    return JsonResponse({
        'labels': labels,
        'data': data
    })


@user_passes_test(superuser_required)
def export_csv(request):
    """Exportiert Statistiken als CSV"""
    export_type = request.GET.get('type', 'visits')
    days = int(request.GET.get('days', 30))

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="stats_{export_type}_{start_date}_to_{end_date}.csv"'

    writer = csv.writer(response)

    if export_type == 'visits':
        # Page Visits Export
        writer.writerow(['URL', 'Seitentitel', 'Benutzer', 'IP-Adresse', 'Besuchszeit', 'Gerät', 'Browser', 'OS', 'Land'])

        visits = PageVisit.objects.filter(
            visit_time__date__range=[start_date, end_date]
        ).select_related('user').order_by('-visit_time')[:1000]

        for visit in visits:
            writer.writerow([
                visit.url,
                visit.page_title or '',
                visit.user.username if visit.user else 'Anonym',
                visit.ip_address,
                visit.visit_time.strftime('%Y-%m-%d %H:%M:%S'),
                visit.device_type or '',
                visit.browser or '',
                visit.os or '',
                visit.country or ''
            ])

    elif export_type == 'popular_pages':
        # Popular Pages Export
        writer.writerow(['URL', 'Seitentitel', 'Anzahl Aufrufe', 'Letzte Aktualisierung'])

        pages = PopularPage.objects.all().order_by('-view_count')[:100]

        for page in pages:
            writer.writerow([
                page.url,
                page.page_title or '',
                page.view_count,
                page.last_updated.strftime('%Y-%m-%d %H:%M:%S')
            ])

    elif export_type == 'traffic_sources':
        # Traffic Sources Export
        traffic_sources = analyze_traffic_sources(start_date)
        writer.writerow(['Quelle', 'Name', 'Anzahl Besucher', 'URL'])

        for source in traffic_sources:
            writer.writerow([
                source.get('name', ''),
                source.get('name', ''),
                source.get('count', 0),
                source.get('full_url', '')
            ])

    return response


@user_passes_test(superuser_required)
def export_report(request):
    """Generiert einen umfassenden HTML-Report"""
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    # Sammle alle Daten
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'today_visits': PageVisit.objects.filter(visit_time__date=end_date).count(),
        'period_visits': PageVisit.objects.filter(visit_time__date__range=[start_date, end_date]).count(),
        'unique_visitors': PageVisit.objects.filter(
            visit_time__date__range=[start_date, end_date]
        ).values('ip_address').distinct().count(),
        'popular_pages': PopularPage.objects.all()[:10],
        'traffic_sources': analyze_traffic_sources(start_date),
        'device_stats': analyze_device_stats(start_date),
        'search_stats': analyze_search_stats(start_date),
        'error_stats': analyze_error_stats(start_date),
        'journey_stats': analyze_user_journey(start_date),
    }

    html_content = render_to_string('stats/report_template.html', context)

    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="stats_report_{start_date}_to_{end_date}.html"'

    return response
