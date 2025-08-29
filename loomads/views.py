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
    AdImpression, AdClick, AdSchedule, AdTargeting
)

# Import frontend management views
from .views_frontend import (
    campaign_create, campaign_edit, campaign_delete,
    ad_create, ad_edit, ad_delete, ad_list, ad_detail,
    zone_create, zone_edit, zone_delete,
    settings
)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def dashboard(request):
    """LoomAds Dashboard - nur für Superuser"""
    
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
    
    context = {
        'zones': zones,
        'zone_type_filter': zone_type_filter,
        'active_filter': active_filter,
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
    }
    
    return render(request, 'loomads/analytics.html', context)


# API Endpoints für Anzeigen-Serving
def get_ad_for_zone(request, zone_code):
    """API: Anzeige für eine bestimmte Zone abrufen"""
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
    except AdZone.DoesNotExist:
        return JsonResponse({'error': 'Zone not found'}, status=404)
    
    # Aktive Anzeigen für diese Zone finden
    now = timezone.now()
    active_ads = Advertisement.objects.filter(
        is_active=True,
        zones=zone,
        campaign__status='active',
        campaign__start_date__lte=now,
        campaign__end_date__gte=now
    )
    
    # Device-Targeting prüfen
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(x in user_agent for x in ['mobile', 'android', 'iphone'])
    is_tablet = 'ipad' in user_agent or 'tablet' in user_agent
    
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
    
    # User-Targeting prüfen
    if request.user.is_authenticated:
        active_ads = active_ads.filter(
            Q(targeting__target_logged_in=True) | Q(targeting__isnull=True)
        )
    else:
        active_ads = active_ads.filter(
            Q(targeting__target_anonymous=True) | Q(targeting__isnull=True)
        )
    
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
    
    if not active_ads.exists():
        return JsonResponse({'error': 'No ads available'}, status=404)
    
    # Gewichtete Auswahl
    ads_with_weights = list(active_ads.values_list('id', 'weight'))
    if ads_with_weights:
        ad_ids, weights = zip(*ads_with_weights)
        selected_ad_id = random.choices(ad_ids, weights=weights, k=1)[0]
        selected_ad = Advertisement.objects.get(id=selected_ad_id)
    else:
        return JsonResponse({'error': 'No ads available'}, status=404)
    
    # Impression tracken mit Duplikatsprüfung
    if request.user.is_authenticated or request.GET.get('track') != 'false':
        # Session-basierte Duplikatsprüfung
        session_key = f'ad_impression_{selected_ad.id}_{zone.id}'
        impression_time = request.session.get(session_key)
        current_time = timezone.now().timestamp()
        
        # Nur tracken, wenn noch nicht in den letzten 30 Sekunden getrackt wurde
        if not impression_time or (current_time - impression_time) > 30:
            AdImpression.objects.create(
                advertisement=selected_ad,
                zone=zone,
                user=request.user if request.user.is_authenticated else None,
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
    elif selected_ad.ad_type == 'html':
        response_data['html_content'] = selected_ad.html_content
    elif selected_ad.ad_type == 'video':
        response_data['video_url'] = selected_ad.video_url
    
    return JsonResponse(response_data)


@require_POST
def track_click(request, ad_id):
    """API: Klick auf Anzeige tracken"""
    try:
        ad = Advertisement.objects.get(id=ad_id)
    except Advertisement.DoesNotExist:
        return JsonResponse({'error': 'Ad not found'}, status=404)
    
    # Klick tracken
    zone_code = request.POST.get('zone_code')
    zone = None
    if zone_code:
        try:
            zone = AdZone.objects.get(code=zone_code)
        except AdZone.DoesNotExist:
            pass
    
    AdClick.objects.create(
        advertisement=ad,
        zone=zone,
        user=request.user if request.user.is_authenticated else None,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        referrer_url=request.META.get('HTTP_REFERER', '')
    )
    
    ad.clicks_count = F('clicks_count') + 1
    ad.save(update_fields=['clicks_count'])
    
    return JsonResponse({'status': 'success'})


def get_client_ip(request):
    """Client-IP aus Request extrahieren"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
