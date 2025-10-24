from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json
import random

from .models import (
    Campaign, AdZone, Advertisement, AdPlacement,
    AdImpression, AdClick, AdSchedule, AdTargeting, ZoneIntegration, LoomAdsSettings,
    AppCampaign, AppAdvertisement
)

# Import frontend management views
from .views_frontend import (
    campaign_create, campaign_edit, campaign_delete,
    ad_create, ad_edit, ad_delete, ad_list, ad_detail,
    zone_create, zone_edit, zone_delete,
    settings
)

# Import app campaign views
from .views_app import (
    app_campaign_list, app_campaign_create, app_campaign_detail,
    app_campaign_edit, app_campaign_delete,
    app_ad_create, app_ad_edit, app_ad_delete
)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


@login_required
def dashboard(request):
    """LoomAds Dashboard - für alle User (Wizard für alle, Admin-Funktionen nur für Superuser)"""
    
    # Statistiken sammeln
    total_campaigns = Campaign.objects.count()
    active_campaigns = Campaign.objects.filter(
        status='active',
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).count()
    
    total_ads = Advertisement.objects.count()
    active_ads = Advertisement.objects.filter(is_active=True).count()
    
    total_zones = AdZone.objects.count()
    active_zones = AdZone.objects.filter(is_active=True).count()
    
    # Impressions und Klicks der letzten 30 Tage
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_impressions = AdImpression.objects.filter(timestamp__gte=thirty_days_ago).count()
    recent_clicks = AdClick.objects.filter(timestamp__gte=thirty_days_ago).count()
    
    # CTR berechnen
    overall_ctr = (recent_clicks / recent_impressions * 100) if recent_impressions > 0 else 0
    
    # Top-performing Anzeigen
    top_ads = Advertisement.objects.filter(
        is_active=True,
        impressions_count__gt=0
    ).annotate(
        ctr_value=F('clicks_count') * 100.0 / F('impressions_count')
    ).order_by('-ctr_value')[:5]
    
    # Aktuelle Kampagnen
    current_campaigns = Campaign.objects.filter(
        status='active',
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).order_by('-created_at')[:5]
    
    # Chart-Daten für die letzten 7 Tage
    chart_data = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        impressions = AdImpression.objects.filter(
            timestamp__date=date
        ).count()
        clicks = AdClick.objects.filter(
            timestamp__date=date
        ).count()
        chart_data.append({
            'date': date.strftime('%d.%m'),
            'impressions': impressions,
            'clicks': clicks
        })
    chart_data.reverse()
    
    context = {
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'total_ads': total_ads,
        'active_ads': active_ads,
        'total_zones': total_zones,
        'active_zones': active_zones,
        'recent_impressions': recent_impressions,
        'recent_clicks': recent_clicks,
        'overall_ctr': overall_ctr,
        'top_ads': top_ads,
        'current_campaigns': current_campaigns,
        'chart_data': json.dumps(chart_data),
    }
    
    return render(request, 'loomads/dashboard.html', context)


@login_required
@user_passes_test(is_superuser)
def campaign_list(request):
    """Liste aller Kampagnen"""
    campaigns = Campaign.objects.all().order_by('-created_at')
    
    # Filter
    status_filter = request.GET.get('status')
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    
    search_query = request.GET.get('search')
    if search_query:
        campaigns = campaigns.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    paginator = Paginator(campaigns, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'loomads/campaign_list.html', context)


@login_required
@user_passes_test(is_superuser)
def campaign_detail(request, campaign_id):
    """Kampagnen-Details anzeigen"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    advertisements = campaign.advertisements.all()
    
    # Statistiken für die Kampagne
    total_impressions = sum(ad.impressions_count for ad in advertisements)
    total_clicks = sum(ad.clicks_count for ad in advertisements)
    campaign_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    
    context = {
        'campaign': campaign,
        'advertisements': advertisements,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'campaign_ctr': campaign_ctr,
    }
    
    return render(request, 'loomads/campaign_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def ad_list(request):
    """Liste aller Anzeigen"""
    ads = Advertisement.objects.all().select_related('campaign').prefetch_related('zones').order_by('-created_at')
    
    # Filter
    ad_type_filter = request.GET.get('type')
    if ad_type_filter:
        ads = ads.filter(ad_type=ad_type_filter)
    
    active_filter = request.GET.get('active')
    if active_filter == 'true':
        ads = ads.filter(is_active=True)
    elif active_filter == 'false':
        ads = ads.filter(is_active=False)
    
    campaign_filter = request.GET.get('campaign')
    if campaign_filter:
        ads = ads.filter(campaign_id=campaign_filter)
    
    search_query = request.GET.get('search')
    if search_query:
        ads = ads.filter(
            Q(name__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    paginator = Paginator(ads, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Kampagnen für Filter-Dropdown
    campaigns = Campaign.objects.all().order_by('name')
    
    context = {
        'ads': page_obj,  # Template erwartet 'ads'
        'page_obj': page_obj,
        'campaigns': campaigns,
        'ad_type_filter': ad_type_filter,
        'active_filter': active_filter,
        'campaign_filter': campaign_filter,
        'search_query': search_query,
    }
    
    return render(request, 'loomads/ad_list.html', context)


@login_required
@user_passes_test(is_superuser)
def ad_detail(request, ad_id):
    """Anzeigen-Details"""
    ad = get_object_or_404(Advertisement, id=ad_id)
    
    # Statistiken für die letzten 30 Tage
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_impressions = ad.impressions.filter(timestamp__gte=thirty_days_ago)
    recent_clicks = ad.clicks.filter(timestamp__gte=thirty_days_ago)
    
    # Performance nach Zone
    zone_performance = []
    for zone in ad.zones.all():
        zone_impressions = recent_impressions.filter(zone=zone).count()
        zone_clicks = recent_clicks.filter(zone=zone).count()
        zone_ctr = (zone_clicks / zone_impressions * 100) if zone_impressions > 0 else 0
        zone_performance.append({
            'zone': zone,
            'impressions': zone_impressions,
            'clicks': zone_clicks,
            'ctr': zone_ctr
        })
    
    # Chart-Daten für die letzten 7 Tage
    chart_data = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        impressions = ad.impressions.filter(timestamp__date=date).count()
        clicks = ad.clicks.filter(timestamp__date=date).count()
        chart_data.append({
            'date': date.strftime('%d.%m'),
            'impressions': impressions,
            'clicks': clicks
        })
    chart_data.reverse()
    
    context = {
        'ad': ad,
        'zone_performance': zone_performance,
        'chart_data': json.dumps(chart_data),
        'recent_impressions_count': recent_impressions.count(),
        'recent_clicks_count': recent_clicks.count(),
    }
    
    return render(request, 'loomads/ad_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def zone_list(request):
    """Liste aller Werbezonen"""
    zones = AdZone.objects.all().order_by('name')
    
    # Filter
    zone_type_filter = request.GET.get('type')
    if zone_type_filter:
        zones = zones.filter(zone_type=zone_type_filter)
    
    active_filter = request.GET.get('active')
    if active_filter == 'true':
        zones = zones.filter(is_active=True)
    elif active_filter == 'false':
        zones = zones.filter(is_active=False)
    
    # Zone integrations for the Integration section
    integrations = ZoneIntegration.objects.all().order_by('template_path', 'zone_code')
    
    context = {
        'zones': zones,
        'zone_type_filter': zone_type_filter,
        'active_filter': active_filter,
        'integrations': integrations,
    }
    
    return render(request, 'loomads/zone_list.html', context)


@login_required
@user_passes_test(is_superuser)
def analytics(request):
    """Analytics Dashboard"""
    # Zeitraum aus Request holen
    period = request.GET.get('period', '7')  # Standard: 7 Tage
    try:
        days = int(period)
    except ValueError:
        days = 7
    
    start_date = timezone.now() - timedelta(days=days)
    
    # Allgemeine Statistiken
    impressions = AdImpression.objects.filter(timestamp__gte=start_date)
    clicks = AdClick.objects.filter(timestamp__gte=start_date)
    
    total_impressions = impressions.count()
    total_clicks = clicks.count()
    overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    
    # Top Kampagnen
    top_campaigns = Campaign.objects.filter(
        advertisements__impressions__timestamp__gte=start_date
    ).annotate(
        impression_count=Count('advertisements__impressions'),
        click_count=Count('advertisements__clicks')
    ).order_by('-impression_count')[:10]
    
    # Top Anzeigen
    top_ads = Advertisement.objects.filter(
        impressions__timestamp__gte=start_date
    ).annotate(
        recent_impressions=Count('impressions'),
        recent_clicks=Count('clicks')
    ).order_by('-recent_impressions')[:10]
    
    # Performance nach Zone
    zone_stats = []
    for zone in AdZone.objects.filter(is_active=True):
        zone_impressions = impressions.filter(zone=zone).count()
        zone_clicks = clicks.filter(zone=zone).count()
        if zone_impressions > 0:
            zone_ctr = (zone_clicks / zone_impressions * 100)
            zone_stats.append({
                'zone': zone,
                'impressions': zone_impressions,
                'clicks': zone_clicks,
                'ctr': zone_ctr
            })
    zone_stats.sort(key=lambda x: x['impressions'], reverse=True)
    
    # Tägliche Performance
    daily_stats = []
    for i in range(days):
        date = timezone.now().date() - timedelta(days=i)
        day_impressions = impressions.filter(timestamp__date=date).count()
        day_clicks = clicks.filter(timestamp__date=date).count()
        daily_stats.append({
            'date': date.strftime('%d.%m.%Y'),
            'impressions': day_impressions,
            'clicks': day_clicks,
            'ctr': (day_clicks / day_impressions * 100) if day_impressions > 0 else 0
        })
    daily_stats.reverse()
    
    # Browser-Statistiken
    browser_stats = {}
    for impression in impressions:
        user_agent = impression.user_agent.lower() if impression.user_agent else 'unknown'
        browser = 'andere'
        if 'chrome' in user_agent and 'edge' not in user_agent:
            browser = 'chrome'
        elif 'firefox' in user_agent:
            browser = 'firefox'
        elif 'safari' in user_agent and 'chrome' not in user_agent:
            browser = 'safari'
        elif 'edge' in user_agent:
            browser = 'edge'
        elif 'opera' in user_agent or 'opr' in user_agent:
            browser = 'opera'
        
        if browser not in browser_stats:
            browser_stats[browser] = {'impressions': 0, 'clicks': 0}
        browser_stats[browser]['impressions'] += 1
    
    for click in clicks:
        user_agent = click.user_agent.lower() if click.user_agent else 'unknown'
        browser = 'andere'
        if 'chrome' in user_agent and 'edge' not in user_agent:
            browser = 'chrome'
        elif 'firefox' in user_agent:
            browser = 'firefox'
        elif 'safari' in user_agent and 'chrome' not in user_agent:
            browser = 'safari'
        elif 'edge' in user_agent:
            browser = 'edge'
        elif 'opera' in user_agent or 'opr' in user_agent:
            browser = 'opera'
            
        if browser in browser_stats:
            browser_stats[browser]['clicks'] += 1
    
    # CTR berechnen
    for browser in browser_stats:
        imp_count = browser_stats[browser]['impressions']
        click_count = browser_stats[browser]['clicks']
        browser_stats[browser]['ctr'] = (click_count / imp_count * 100) if imp_count > 0 else 0
    
    # Betriebssystem-Statistiken
    os_stats = {}
    for impression in impressions:
        user_agent = impression.user_agent.lower() if impression.user_agent else 'unknown'
        os_name = 'andere'
        if 'windows' in user_agent:
            os_name = 'windows'
        elif 'macintosh' in user_agent or 'mac os' in user_agent:
            os_name = 'macos'
        elif 'linux' in user_agent and 'android' not in user_agent:
            os_name = 'linux'
        elif 'iphone' in user_agent or 'ipad' in user_agent:
            os_name = 'ios'
        elif 'android' in user_agent:
            os_name = 'android'
            
        if os_name not in os_stats:
            os_stats[os_name] = {'impressions': 0, 'clicks': 0}
        os_stats[os_name]['impressions'] += 1
        
    for click in clicks:
        user_agent = click.user_agent.lower() if click.user_agent else 'unknown'
        os_name = 'andere'
        if 'windows' in user_agent:
            os_name = 'windows'
        elif 'macintosh' in user_agent or 'mac os' in user_agent:
            os_name = 'macos'
        elif 'linux' in user_agent and 'android' not in user_agent:
            os_name = 'linux'
        elif 'iphone' in user_agent or 'ipad' in user_agent:
            os_name = 'ios'
        elif 'android' in user_agent:
            os_name = 'android'
            
        if os_name in os_stats:
            os_stats[os_name]['clicks'] += 1
    
    # CTR berechnen für OS
    for os_name in os_stats:
        imp_count = os_stats[os_name]['impressions']
        click_count = os_stats[os_name]['clicks']
        os_stats[os_name]['ctr'] = (click_count / imp_count * 100) if imp_count > 0 else 0
    
    # Stundenweise Performance
    hourly_stats = {}
    for i in range(24):
        hourly_stats[i] = {'impressions': 0, 'clicks': 0}
    
    for impression in impressions:
        hour = impression.timestamp.hour
        hourly_stats[hour]['impressions'] += 1
    
    for click in clicks:
        hour = click.timestamp.hour
        hourly_stats[hour]['clicks'] += 1
    
    # CTR berechnen für Stunden
    for hour in hourly_stats:
        imp_count = hourly_stats[hour]['impressions']
        click_count = hourly_stats[hour]['clicks']
        hourly_stats[hour]['ctr'] = (click_count / imp_count * 100) if imp_count > 0 else 0
    
    # Wochentagsstatistiken
    weekday_stats = {}
    weekday_names = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    for i in range(7):
        weekday_stats[i] = {'name': weekday_names[i], 'impressions': 0, 'clicks': 0}
    
    for impression in impressions:
        weekday = impression.timestamp.weekday()
        weekday_stats[weekday]['impressions'] += 1
    
    for click in clicks:
        weekday = click.timestamp.weekday()
        weekday_stats[weekday]['clicks'] += 1
    
    # CTR berechnen für Wochentage
    for weekday in weekday_stats:
        imp_count = weekday_stats[weekday]['impressions']
        click_count = weekday_stats[weekday]['clicks']
        weekday_stats[weekday]['ctr'] = (click_count / imp_count * 100) if imp_count > 0 else 0
    
    context = {
        'period': period,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'overall_ctr': overall_ctr,
        'top_campaigns': top_campaigns,
        'top_ads': top_ads,
        'zone_stats': zone_stats[:10],  # Top 10 Zonen
        'daily_stats': daily_stats,
        'chart_data': json.dumps(daily_stats),
        'browser_stats': browser_stats,
        'os_stats': os_stats,
        'hourly_stats': hourly_stats,
        'weekday_stats': weekday_stats,
    }
    
    return render(request, 'loomads/analytics.html', context)


# API Endpoints für Anzeigen-Serving
def get_ad_for_zone(request, zone_code):
    """API: Anzeige für eine bestimmte Zone abrufen"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
        logger.debug(f'Found zone: {zone.name} ({zone.code})')
    except AdZone.DoesNotExist:
        logger.warning(f'Zone not found: {zone_code}')
        return JsonResponse({'error': f'Zone "{zone_code}" not found'}, status=404)
    
    # Aktive Anzeigen für diese Zone finden (normale Anzeigen)
    now = timezone.now()
    active_ads = Advertisement.objects.filter(
        is_active=True,
        zones=zone,
        campaign__status='active',
        campaign__start_date__lte=now
    ).filter(
        Q(campaign__end_date__gte=now) | Q(campaign__end_date__isnull=True)
    )

    # Aktive App-Anzeigen für diese Zone hinzufügen
    app_ads = AppAdvertisement.objects.filter(
        is_active=True,
        zones=zone,
        app_campaign__status='active',
        app_campaign__start_date__lte=now
    ).filter(
        Q(app_campaign__end_date__gte=now) | Q(app_campaign__end_date__isnull=True)
    )

    initial_count = active_ads.count()
    app_ads_count = app_ads.count()
    logger.debug(f'Initial ads found for {zone_code}: {initial_count} normal, {app_ads_count} app ads')

    # Wenn keine normalen Anzeigen da sind, aber App-Anzeigen, dann App-Anzeigen verwenden
    if initial_count == 0 and app_ads_count > 0:
        # App-Anzeige auswählen (weighted random)
        if app_ads_count == 1:
            selected_app_ad = app_ads.first()
        else:
            # Gewichtete Auswahl bei mehreren App-Anzeigen
            app_ads_with_weights = []
            for app_ad in app_ads:
                app_ads_with_weights.append((app_ad, app_ad.effective_weight))

            if app_ads_with_weights:
                ads, weights = zip(*app_ads_with_weights)
                selected_app_ad = random.choices(ads, weights=weights, k=1)[0]
            else:
                selected_app_ad = app_ads.first()

        # App-Anzeige zu Advertisement-kompatiblem Format konvertieren
        should_track = (
            request.GET.get('track') != 'false' and
            not (request.user.is_authenticated and request.user.is_superuser)
        )

        if should_track:
            # Impression tracken für App-Anzeigen (nur Counter, kein detailliertes Tracking)
            session_key = f'ad_impression_{selected_app_ad.id}_{zone.id}'
            impression_time = request.session.get(session_key)
            current_time = timezone.now().timestamp()

            if not impression_time or (current_time - impression_time) > 30:
                # Nur den Counter erhöhen, kein AdImpression Record
                # (da AdImpression nur normale Advertisements unterstützt)
                selected_app_ad.impressions_count = F('impressions_count') + 1
                selected_app_ad.save(update_fields=['impressions_count'])

                request.session[session_key] = current_time
                request.session.modified = True

        # Response für App-Anzeige
        response_data = {
            'id': str(selected_app_ad.id),
            'type': selected_app_ad.ad_type,
            'title': selected_app_ad.title,
            'description': selected_app_ad.description_text,
            'target_url': selected_app_ad.link_url,
            'target_type': '_blank',  # App-Anzeigen öffnen standardmäßig in neuem Tab
        }

        if selected_app_ad.ad_type == 'image' and selected_app_ad.image:
            response_data['image_url'] = request.build_absolute_uri(selected_app_ad.image.url)
        elif selected_app_ad.ad_type == 'html' and selected_app_ad.html_content:
            response_data['type'] = 'html'
            response_data['html_content'] = selected_app_ad.html_content
        elif selected_app_ad.ad_type == 'video' and selected_app_ad.video_url:
            response_data['video_url'] = selected_app_ad.video_url

        return JsonResponse(response_data)

    # Wenn keine App-Anzeigen oder normale Anzeigen vorhanden sind, mit normaler Logik fortfahren
    if initial_count == 0:
        error_msg = f'No ads available for zone {zone_code}. Normal ads: {initial_count}, App ads: {app_ads_count}'
        logger.warning(error_msg)
        return JsonResponse({'error': 'No ads available', 'debug': error_msg}, status=200)
    
    # Device-Targeting prüfen
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(x in user_agent for x in ['mobile', 'android', 'iphone'])
    is_tablet = 'ipad' in user_agent or 'tablet' in user_agent
    
    device_type = 'mobile' if is_mobile and not is_tablet else 'tablet' if is_tablet else 'desktop'
    logger.debug(f'Device type detected: {device_type}')
    
    if is_mobile and not is_tablet:
        active_ads = active_ads.filter(
            Q(targeting__target_mobile=True) | Q(targeting__isnull=True)
        )
    elif is_tablet:
        active_ads = active_ads.filter(
            Q(targeting__target_tablet=True) | Q(targeting__isnull=True)
        )
    else:
        active_ads = active_ads.filter(
            Q(targeting__target_desktop=True) | Q(targeting__isnull=True)
        )
    
    device_filtered_count = active_ads.count()
    logger.debug(f'After device filtering: {device_filtered_count} ads')
    
    # User-Targeting prüfen
    user_type = 'authenticated' if request.user.is_authenticated else 'anonymous'
    logger.debug(f'User type: {user_type}')
    
    if request.user.is_authenticated:
        active_ads = active_ads.filter(
            Q(targeting__target_logged_in=True) | Q(targeting__isnull=True)
        )
    else:
        active_ads = active_ads.filter(
            Q(targeting__target_anonymous=True) | Q(targeting__isnull=True)
        )
    
    user_filtered_count = active_ads.count()
    logger.debug(f'After user filtering: {user_filtered_count} ads')
    
    # Erweiterte Targeting-Prüfungen
    current_time = timezone.now()
    current_date = current_time.date()
    current_hour = current_time.time()
    current_weekday = current_time.weekday()
    
    # Browser-Targeting
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    browser = 'andere'
    if 'chrome' in user_agent and 'edge' not in user_agent:
        browser = 'chrome'
    elif 'firefox' in user_agent:
        browser = 'firefox'
    elif 'safari' in user_agent and 'chrome' not in user_agent:
        browser = 'safari'
    elif 'edge' in user_agent:
        browser = 'edge'
    elif 'opera' in user_agent or 'opr' in user_agent:
        browser = 'opera'
    
    logger.debug(f'Browser detected: {browser}')
    
    # Betriebssystem-Targeting
    os_name = 'andere'
    if 'windows' in user_agent:
        os_name = 'windows'
    elif 'macintosh' in user_agent or 'mac os' in user_agent:
        os_name = 'macos'
    elif 'linux' in user_agent and 'android' not in user_agent:
        os_name = 'linux'
    elif 'iphone' in user_agent or 'ipad' in user_agent:
        os_name = 'ios'
    elif 'android' in user_agent:
        os_name = 'android'
    
    logger.debug(f'OS detected: {os_name}')
    
    # Referrer-Targeting
    referrer = request.META.get('HTTP_REFERER', '').lower()
    if not referrer:
        referrer = 'direkt'
    
    logger.debug(f'Referrer: {referrer}')
    
    # Ads mit Targeting filtern
    filtered_ads = []
    for ad in active_ads:
        try:
            targeting = ad.targeting.first()
        except:
            targeting = None
            
        if not targeting:
            # Keine Targeting-Regeln -> zeige Anzeige
            filtered_ads.append(ad)
            continue
            
        # Browser-Targeting prüfen
        if targeting.target_browsers:
            if browser not in targeting.target_browsers:
                logger.debug(f'Ad {ad.name} excluded: browser {browser} not in target_browsers')
                continue
        if targeting.exclude_browsers:
            if browser in targeting.exclude_browsers:
                logger.debug(f'Ad {ad.name} excluded: browser {browser} in exclude_browsers')
                continue
        
        # OS-Targeting prüfen
        if targeting.target_os:
            if os_name not in targeting.target_os:
                logger.debug(f'Ad {ad.name} excluded: OS {os_name} not in target_os')
                continue
        if targeting.exclude_os:
            if os_name in targeting.exclude_os:
                logger.debug(f'Ad {ad.name} excluded: OS {os_name} in exclude_os')
                continue
        
        # Referrer-Targeting prüfen
        if targeting.target_referrers and targeting.target_referrers.strip():
            referrer_patterns = [pattern.strip().lower() for pattern in targeting.target_referrers.split('\n') if pattern.strip()]
            referrer_match = False
            for pattern in referrer_patterns:
                if pattern == 'direkt' and referrer == 'direkt':
                    referrer_match = True
                    break
                elif pattern in referrer:
                    referrer_match = True
                    break
            if not referrer_match:
                logger.debug(f'Ad {ad.name} excluded: referrer {referrer} not matching patterns')
                continue
        
        if targeting.exclude_referrers and targeting.exclude_referrers.strip():
            exclude_patterns = [pattern.strip().lower() for pattern in targeting.exclude_referrers.split('\n') if pattern.strip()]
            referrer_excluded = False
            for pattern in exclude_patterns:
                if pattern in referrer:
                    referrer_excluded = True
                    break
            if referrer_excluded:
                logger.debug(f'Ad {ad.name} excluded: referrer {referrer} in exclude patterns')
                continue
        
        # Zeitbasiertes Targeting prüfen
        if targeting.target_weekdays:
            weekday_strings = [str(w) for w in targeting.target_weekdays]
            if str(current_weekday) not in weekday_strings:
                logger.debug(f'Ad {ad.name} excluded: weekday {current_weekday} not in target_weekdays')
                continue
        
        if targeting.target_hours_start and targeting.target_hours_end:
            if not (targeting.target_hours_start <= current_hour <= targeting.target_hours_end):
                logger.debug(f'Ad {ad.name} excluded: hour {current_hour} not in time range')
                continue
        
        if targeting.target_date_start and current_date < targeting.target_date_start:
            logger.debug(f'Ad {ad.name} excluded: date {current_date} before start date')
            continue
        
        if targeting.target_date_end and current_date > targeting.target_date_end:
            logger.debug(f'Ad {ad.name} excluded: date {current_date} after end date')
            continue
        
        # App-Targeting prüfen (bereits implementiert)
        if targeting.target_apps:
            current_app = request.resolver_match.app_name if hasattr(request, 'resolver_match') and request.resolver_match else None
            if current_app and current_app not in targeting.target_apps:
                logger.debug(f'Ad {ad.name} excluded: app {current_app} not in target_apps')
                continue
        
        if targeting.exclude_apps:
            current_app = request.resolver_match.app_name if hasattr(request, 'resolver_match') and request.resolver_match else None
            if current_app and current_app in targeting.exclude_apps:
                logger.debug(f'Ad {ad.name} excluded: app {current_app} in exclude_apps')
                continue
        
        # URL-Targeting prüfen (bereits implementiert)
        current_url = request.get_full_path()
        if targeting.target_urls and targeting.target_urls.strip():
            url_patterns = [pattern.strip() for pattern in targeting.target_urls.split('\n') if pattern.strip()]
            url_match = False
            for pattern in url_patterns:
                import fnmatch
                if fnmatch.fnmatch(current_url, pattern):
                    url_match = True
                    break
            if not url_match:
                logger.debug(f'Ad {ad.name} excluded: URL {current_url} not matching patterns')
                continue
        
        if targeting.exclude_urls and targeting.exclude_urls.strip():
            exclude_url_patterns = [pattern.strip() for pattern in targeting.exclude_urls.split('\n') if pattern.strip()]
            url_excluded = False
            for pattern in exclude_url_patterns:
                import fnmatch
                if fnmatch.fnmatch(current_url, pattern):
                    url_excluded = True
                    break
            if url_excluded:
                logger.debug(f'Ad {ad.name} excluded: URL {current_url} in exclude patterns')
                continue
        
        # Anzeige hat alle Targeting-Tests bestanden
        filtered_ads.append(ad)
    
    # Update active_ads to filtered list
    ad_ids = [ad.id for ad in filtered_ads]
    active_ads = Advertisement.objects.filter(id__in=ad_ids)
    
    targeting_filtered_count = active_ads.count()
    logger.debug(f'After extended targeting filtering: {targeting_filtered_count} ads')
    
    # Tägliche Limits prüfen
    today = timezone.now().date()
    for ad in active_ads:
        campaign = ad.campaign
        if campaign.daily_impression_limit:
            today_impressions = ad.impressions.filter(timestamp__date=today).count()
            if today_impressions >= campaign.daily_impression_limit:
                active_ads = active_ads.exclude(id=ad.id)
        if campaign.total_impression_limit:
            if ad.impressions_count >= campaign.total_impression_limit:
                active_ads = active_ads.exclude(id=ad.id)
    
    final_count = active_ads.count()
    logger.debug(f'Final ads after all filtering: {final_count}')
    
    if not active_ads.exists():
        error_msg = f'No ads available for zone {zone_code}. Initial: {initial_count}, Device filtered: {device_filtered_count}, User filtered: {user_filtered_count}, Targeting filtered: {targeting_filtered_count}, Final: {final_count}'
        logger.warning(error_msg)
        return JsonResponse({'error': 'No ads available', 'debug': error_msg}, status=200)
    
    # Gewichtete Auswahl
    ads_with_weights = list(active_ads.values_list('id', 'weight'))
    if ads_with_weights:
        ad_ids, weights = zip(*ads_with_weights)
        selected_ad_id = random.choices(ad_ids, weights=weights, k=1)[0]
        selected_ad = Advertisement.objects.get(id=selected_ad_id)
        logger.debug(f'Selected ad: {selected_ad.name} (ID: {selected_ad_id})')
    else:
        logger.warning(f'No ads with weights available for zone {zone_code}')
        return JsonResponse({'error': 'No ads available', 'debug': 'No weighted ads found'}, status=200)
    
    # Impression tracken mit Duplikatsprüfung (Superuser ausschließen)
    should_track = (
        request.GET.get('track') != 'false' and 
        not (request.user.is_authenticated and request.user.is_superuser)
    )
    
    if should_track:
        # Session-basierte Duplikatsprüfung
        session_key = f'ad_impression_{selected_ad.id}_{zone.id}'
        impression_time = request.session.get(session_key)
        current_time = timezone.now().timestamp()
        
        # Nur tracken, wenn noch nicht in den letzten 30 Sekunden getrackt wurde
        if not impression_time or (current_time - impression_time) > 30:
            AdImpression.objects.create(
                advertisement=selected_ad,
                zone=zone,
                user=request.user if request.user.is_authenticated and not request.user.is_superuser else None,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                page_url=request.META.get('HTTP_REFERER', '')
            )
            selected_ad.impressions_count = F('impressions_count') + 1
            selected_ad.save(update_fields=['impressions_count'])
            
            # Zeit in Session speichern
            request.session[session_key] = current_time
            request.session.modified = True
    
    # Response vorbereiten
    response_data = {
        'id': str(selected_ad.id),
        'type': selected_ad.ad_type,
        'title': selected_ad.title,
        'description': selected_ad.description,
        'target_url': selected_ad.target_url,
        'target_type': selected_ad.target_type,
    }
    
    if selected_ad.ad_type == 'image' and selected_ad.image:
        response_data['image_url'] = request.build_absolute_uri(selected_ad.image.url)
    elif selected_ad.ad_type == 'html' or (selected_ad.ad_type == 'banner' and selected_ad.html_content):
        response_data['type'] = 'html'  # Override type for JavaScript compatibility
        response_data['html_content'] = selected_ad.html_content
    elif selected_ad.ad_type == 'video':
        response_data['video_url'] = selected_ad.video_url
        response_data['video_with_audio'] = selected_ad.video_with_audio
    
    return JsonResponse(response_data)


def get_multiple_ads_for_zone(request, zone_code, count=3):
    """API: Mehrfache Anzeigen für eine Zone abrufen"""
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
    except AdZone.DoesNotExist:
        return JsonResponse({'error': f'Zone "{zone_code}" not found'}, status=404)

    # Limit count to reasonable number
    count = min(max(1, count), 10)

    # Get multiple ads - with proper campaign status and date filtering
    now = timezone.now()

    # Normale Ads
    active_ads = Advertisement.objects.filter(
        zones=zone,
        is_active=True,
        campaign__status='active',  # Only active campaigns
        campaign__start_date__lte=now
    ).filter(
        Q(campaign__end_date__gte=now) | Q(campaign__end_date__isnull=True)
    ).select_related().order_by('?')[:count]

    # App-Ads hinzufügen falls keine normalen Ads vorhanden
    if not active_ads:
        app_ads = AppAdvertisement.objects.filter(
            zones=zone,
            is_active=True,
            app_campaign__status='active',
            app_campaign__start_date__lte=now
        ).filter(
            Q(app_campaign__end_date__gte=now) | Q(app_campaign__end_date__isnull=True)
        ).order_by('?')[:count]

        if not app_ads:
            return JsonResponse({
                'error': 'No active ads available for this zone'
            }, status=404)

        # Konvertiere App-Ads zu Standard-Format
        ads_data = []
        for app_ad in app_ads:
            ad_data = {
                'id': str(app_ad.id),
                'type': app_ad.ad_type,
                'title': app_ad.title,
                'description': app_ad.description_text,
                'target_url': app_ad.link_url,
                'target_type': '_blank',
            }

            if app_ad.ad_type == 'image' and app_ad.image:
                ad_data['image_url'] = request.build_absolute_uri(app_ad.image.url)
            elif app_ad.ad_type == 'html' and app_ad.html_content:
                ad_data['type'] = 'html'
                ad_data['html_content'] = app_ad.html_content
            elif app_ad.ad_type == 'video' and app_ad.video_url:
                ad_data['video_url'] = app_ad.video_url

            ads_data.append(ad_data)

        return JsonResponse({'ads': ads_data, 'count': len(ads_data)})
    
    ads_data = []
    for ad in active_ads:
        ad_data = {
            'id': str(ad.id),
            'type': ad.ad_type,
            'title': ad.title,
            'description': ad.description,
            'target_url': ad.target_url,
            'target_type': ad.target_type,
        }
        
        if ad.ad_type == 'image' and ad.image:
            ad_data['image_url'] = request.build_absolute_uri(ad.image.url)
        elif ad.ad_type == 'html' or (ad.ad_type == 'banner' and ad.html_content):
            ad_data['type'] = 'html'
            ad_data['html_content'] = ad.html_content
        elif ad.ad_type == 'video':
            ad_data['video_url'] = ad.video_url
            ad_data['video_with_audio'] = ad.video_with_audio
        
        ads_data.append(ad_data)
    
    return JsonResponse({'ads': ads_data, 'count': len(ads_data)})


@require_POST
def track_click(request, ad_id):
    """API: Klick auf Anzeige tracken"""
    # Prüfen ob es eine normale Anzeige oder App-Anzeige ist
    ad = None
    app_ad = None

    try:
        ad = Advertisement.objects.get(id=ad_id)
    except Advertisement.DoesNotExist:
        try:
            app_ad = AppAdvertisement.objects.get(id=ad_id)
        except AppAdvertisement.DoesNotExist:
            return JsonResponse({'error': 'Ad not found'}, status=404)

    # Klick tracken
    zone_code = request.POST.get('zone_code')
    zone = None
    if zone_code:
        try:
            zone = AdZone.objects.get(code=zone_code)
        except AdZone.DoesNotExist:
            pass

    # Nur tracken wenn nicht Superuser
    if not (request.user.is_authenticated and request.user.is_superuser):
        AdClick.objects.create(
            advertisement=ad if ad else None,
            zone=zone,
            user=request.user if request.user.is_authenticated else None,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer_url=request.META.get('HTTP_REFERER', '')
        )

        if ad:
            ad.clicks_count = F('clicks_count') + 1
            ad.save(update_fields=['clicks_count'])
        elif app_ad:
            app_ad.clicks_count = F('clicks_count') + 1
            app_ad.save(update_fields=['clicks_count'])

    return JsonResponse({'status': 'success'})


def get_client_ip(request):
    """Client-IP aus Request extrahieren"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
