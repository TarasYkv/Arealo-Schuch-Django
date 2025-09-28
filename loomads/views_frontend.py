from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import json
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Campaign, AdZone, Advertisement, AdTargeting, LoomAdsSettings, ZoneIntegration, AutoCampaignFormat, AutoCampaign, AutoAdvertisement
from .forms import CampaignForm, AdvertisementForm, AdZoneForm, ZoneIntegrationForm
import uuid


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


# ========== CAMPAIGN MANAGEMENT ==========

@login_required
@user_passes_test(is_superuser)
def campaign_create(request):
    """Create new campaign"""
    if request.method == 'POST':
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            messages.success(request, f'Kampagne "{campaign.name}" wurde erfolgreich erstellt!')
            return redirect('loomads:campaign_detail', campaign_id=campaign.id)
    else:
        form = CampaignForm(initial={
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=30)
        })
    
    context = {
        'form': form,
        'title': 'Neue Kampagne erstellen'
    }
    return render(request, 'loomads/campaign_form.html', context)


@login_required
@user_passes_test(is_superuser)
def campaign_edit(request, campaign_id):
    """Edit existing campaign"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            messages.success(request, f'Kampagne "{campaign.name}" wurde aktualisiert!')
            return redirect('loomads:campaign_detail', campaign_id=campaign.id)
    else:
        form = CampaignForm(instance=campaign)
    
    context = {
        'form': form,
        'campaign': campaign,
        'title': f'Kampagne "{campaign.name}" bearbeiten'
    }
    return render(request, 'loomads/campaign_form.html', context)


@login_required
@user_passes_test(is_superuser)
def campaign_delete(request, campaign_id):
    """Delete campaign"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'Kampagne "{campaign_name}" wurde gelöscht!')
        return redirect('loomads:campaign_list')
    
    context = {
        'campaign': campaign
    }
    return render(request, 'loomads/campaign_confirm_delete.html', context)


# ========== ADVERTISEMENT MANAGEMENT ==========

@login_required
@user_passes_test(is_superuser)
def ad_list(request):
    """List all advertisements"""
    ads = Advertisement.objects.all().select_related('campaign').prefetch_related('zones').order_by('-created_at')
    
    context = {
        'ads': ads
    }
    return render(request, 'loomads/ad_list.html', context)


@login_required
@user_passes_test(is_superuser)
def ad_detail(request, ad_id):
    """Show advertisement details"""
    ad = get_object_or_404(Advertisement, id=ad_id)
    
    context = {
        'ad': ad,
        'targeting': ad.targeting.first() if hasattr(ad, 'targeting') else None,
    }
    return render(request, 'loomads/ad_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def ad_create(request):
    """Create new advertisement"""
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, request.FILES)
        if form.is_valid():
            ad = form.save()
            
            # Create targeting
            AdTargeting.objects.create(
                advertisement=ad,
                target_desktop=request.POST.get('target_desktop', 'on') == 'on',
                target_mobile=request.POST.get('target_mobile', 'on') == 'on',
                target_tablet=request.POST.get('target_tablet', 'on') == 'on',
                target_logged_in=request.POST.get('target_logged_in', 'on') == 'on',
                target_anonymous=request.POST.get('target_anonymous', 'on') == 'on',
                target_apps=request.POST.getlist('target_apps') or [],
                exclude_apps=request.POST.getlist('exclude_apps') or [],
                target_urls=request.POST.get('target_urls', '').strip(),
                exclude_urls=request.POST.get('exclude_urls', '').strip(),
                
                # Browser targeting
                target_browsers=request.POST.getlist('target_browsers') or [],
                exclude_browsers=request.POST.getlist('exclude_browsers') or [],
                
                # OS targeting
                target_os=request.POST.getlist('target_os') or [],
                exclude_os=request.POST.getlist('exclude_os') or [],
                
                # Referrer targeting
                target_referrers=request.POST.get('target_referrers', '').strip(),
                exclude_referrers=request.POST.get('exclude_referrers', '').strip(),
                
                # Geographic targeting
                target_cities=request.POST.getlist('target_cities') or [],
                exclude_cities=request.POST.getlist('exclude_cities') or [],
                
                # Time-based targeting
                target_weekdays=request.POST.getlist('target_weekdays') or [],
                target_hours_start=request.POST.get('target_hours_start') or None,
                target_hours_end=request.POST.get('target_hours_end') or None,
                target_date_start=request.POST.get('target_date_start') or None,
                target_date_end=request.POST.get('target_date_end') or None,
            )
            
            messages.success(request, f'Anzeige "{ad.name}" wurde erfolgreich erstellt!')
            return redirect('loomads:ad_detail', ad_id=ad.id)
    else:
        form = AdvertisementForm()
    
    context = {
        'form': form,
        'campaigns': Campaign.objects.filter(status='active'),
        'zones': AdZone.objects.filter(is_active=True),
        'title': 'Neue Anzeige erstellen'
    }
    return render(request, 'loomads/ad_form.html', context)


@login_required
@user_passes_test(is_superuser)
def ad_edit(request, ad_id):
    """Edit existing advertisement"""
    ad = get_object_or_404(Advertisement, id=ad_id)
    targeting, created = AdTargeting.objects.get_or_create(advertisement=ad)
    
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, request.FILES, instance=ad)
        if form.is_valid():
            form.save()
            
            # Update targeting
            targeting.target_desktop = request.POST.get('target_desktop', 'on') == 'on'
            targeting.target_mobile = request.POST.get('target_mobile', 'on') == 'on'
            targeting.target_tablet = request.POST.get('target_tablet', 'on') == 'on'
            targeting.target_logged_in = request.POST.get('target_logged_in', 'on') == 'on'
            targeting.target_anonymous = request.POST.get('target_anonymous', 'on') == 'on'
            
            # Update app and URL targeting
            targeting.target_apps = request.POST.getlist('target_apps') or []
            targeting.exclude_apps = request.POST.getlist('exclude_apps') or []
            targeting.target_urls = request.POST.get('target_urls', '').strip()
            targeting.exclude_urls = request.POST.get('exclude_urls', '').strip()
            
            # Update browser targeting
            targeting.target_browsers = request.POST.getlist('target_browsers') or []
            targeting.exclude_browsers = request.POST.getlist('exclude_browsers') or []
            
            # Update OS targeting
            targeting.target_os = request.POST.getlist('target_os') or []
            targeting.exclude_os = request.POST.getlist('exclude_os') or []
            
            # Update referrer targeting
            targeting.target_referrers = request.POST.get('target_referrers', '').strip()
            targeting.exclude_referrers = request.POST.get('exclude_referrers', '').strip()
            
            # Update geographic targeting
            targeting.target_cities = request.POST.getlist('target_cities') or []
            targeting.exclude_cities = request.POST.getlist('exclude_cities') or []
            
            # Update time-based targeting
            targeting.target_weekdays = request.POST.getlist('target_weekdays') or []
            targeting.target_hours_start = request.POST.get('target_hours_start') or None
            targeting.target_hours_end = request.POST.get('target_hours_end') or None
            targeting.target_date_start = request.POST.get('target_date_start') or None
            targeting.target_date_end = request.POST.get('target_date_end') or None
            
            targeting.save()
            
            messages.success(request, f'Anzeige "{ad.name}" wurde aktualisiert!')
            return redirect('loomads:ad_detail', ad_id=ad.id)
    else:
        form = AdvertisementForm(instance=ad)
    
    context = {
        'form': form,
        'ad': ad,
        'targeting': targeting,
        'campaigns': Campaign.objects.filter(status='active'),
        'zones': AdZone.objects.filter(is_active=True),
        'title': f'Anzeige "{ad.name}" bearbeiten'
    }
    return render(request, 'loomads/ad_form.html', context)


@login_required
@user_passes_test(is_superuser)
def ad_delete(request, ad_id):
    """Delete advertisement"""
    ad = get_object_or_404(Advertisement, id=ad_id)
    
    if request.method == 'POST':
        ad_name = ad.name
        ad.delete()
        messages.success(request, f'Anzeige "{ad_name}" wurde gelöscht!')
        return redirect('loomads:ad_list')
    
    context = {
        'ad': ad
    }
    return render(request, 'loomads/ad_confirm_delete.html', context)


# ========== AD ZONE MANAGEMENT ==========

@login_required
@user_passes_test(is_superuser)
def zone_create(request):
    """Create new ad zone"""
    if request.method == 'POST':
        form = AdZoneForm(request.POST)
        if form.is_valid():
            zone = form.save()
            messages.success(request, f'Werbezone "{zone.name}" wurde erfolgreich erstellt!')
            return redirect('loomads:zone_list')
    else:
        form = AdZoneForm()
    
    context = {
        'form': form,
        'title': 'Neue Werbezone erstellen'
    }
    return render(request, 'loomads/zone_form.html', context)


@login_required
@user_passes_test(is_superuser)
def zone_edit(request, zone_id):
    """Edit existing ad zone"""
    zone = get_object_or_404(AdZone, id=zone_id)
    
    if request.method == 'POST':
        form = AdZoneForm(request.POST, instance=zone)
        if form.is_valid():
            form.save()
            messages.success(request, f'Werbezone "{zone.name}" wurde aktualisiert!')
            return redirect('loomads:zone_list')
    else:
        form = AdZoneForm(instance=zone)
    
    context = {
        'form': form,
        'zone': zone,
        'title': f'Werbezone "{zone.name}" bearbeiten'
    }
    return render(request, 'loomads/zone_form.html', context)


@login_required
@user_passes_test(is_superuser)
def zone_delete(request, zone_id):
    """Delete ad zone"""
    zone = get_object_or_404(AdZone, id=zone_id)
    
    if request.method == 'POST':
        zone_name = zone.name
        zone.delete()
        messages.success(request, f'Werbezone "{zone_name}" wurde gelöscht!')
        return redirect('loomads:zone_list')
    
    context = {
        'zone': zone
    }
    return render(request, 'loomads/zone_confirm_delete.html', context)


# ========== SETTINGS ==========

@login_required
@user_passes_test(is_superuser)
def settings(request):
    """LoomAds settings page"""
    settings_obj = LoomAdsSettings.get_settings()
    
    if request.method == 'POST':
        # Handle global settings updates
        settings_obj.enable_tracking = request.POST.get('enable_tracking') == 'on'
        settings_obj.enable_targeting = request.POST.get('enable_targeting') == 'on'
        settings_obj.enable_scheduling = request.POST.get('enable_scheduling') == 'on'
        
        # Handle default values
        daily_limit = request.POST.get('default_daily_limit')
        settings_obj.default_daily_limit = int(daily_limit) if daily_limit else None
        settings_obj.default_weight = int(request.POST.get('default_weight', 5))
        
        # Handle global zone controls
        settings_obj.global_header_enabled = request.POST.get('global_header_enabled') == 'on'
        settings_obj.global_footer_enabled = request.POST.get('global_footer_enabled') == 'on'
        settings_obj.global_sidebar_enabled = request.POST.get('global_sidebar_enabled') == 'on'
        settings_obj.global_infeed_enabled = request.POST.get('global_infeed_enabled') == 'on'
        settings_obj.global_modal_enabled = request.POST.get('global_modal_enabled') == 'on'
        settings_obj.global_video_preroll_enabled = request.POST.get('global_video_preroll_enabled') == 'on'
        settings_obj.global_video_overlay_enabled = request.POST.get('global_video_overlay_enabled') == 'on'
        settings_obj.global_video_popup_enabled = request.POST.get('global_video_popup_enabled') == 'on'
        settings_obj.global_content_card_enabled = request.POST.get('global_content_card_enabled') == 'on'
        settings_obj.global_notification_enabled = request.POST.get('global_notification_enabled') == 'on'
        
        # Handle analytics data deletion
        if request.POST.get('delete_analytics'):
            delete_start_date = request.POST.get('delete_start_date')
            delete_end_date = request.POST.get('delete_end_date')
            
            if delete_start_date and delete_end_date:
                from datetime import datetime
                from django.utils import timezone
                from ..models import AdImpression, AdClick
                
                try:
                    start_date = datetime.strptime(delete_start_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(delete_end_date, '%Y-%m-%d').date()
                    
                    # Delete impressions in date range
                    deleted_impressions = AdImpression.objects.filter(
                        timestamp__date__gte=start_date,
                        timestamp__date__lte=end_date
                    ).delete()[0]
                    
                    # Delete clicks in date range
                    deleted_clicks = AdClick.objects.filter(
                        timestamp__date__gte=start_date,
                        timestamp__date__lte=end_date
                    ).delete()[0]
                    
                    # Update impression/click counters on advertisements
                    from django.db.models import F
                    Advertisement.objects.all().update(
                        impressions_count=0,
                        clicks_count=0
                    )
                    
                    # Recalculate counters
                    for ad in Advertisement.objects.all():
                        ad.impressions_count = ad.impressions.count()
                        ad.clicks_count = ad.clicks.count()
                        ad.save(update_fields=['impressions_count', 'clicks_count'])
                    
                    messages.success(request, 
                        f'Analytics-Daten gelöscht: {deleted_impressions} Impressions und {deleted_clicks} Klicks '
                        f'vom {start_date.strftime("%d.%m.%Y")} bis {end_date.strftime("%d.%m.%Y")}'
                    )
                    
                except ValueError:
                    messages.error(request, 'Ungültiges Datumsformat. Bitte verwenden Sie YYYY-MM-DD.')
                except Exception as e:
                    messages.error(request, f'Fehler beim Löschen der Analytics-Daten: {str(e)}')
            else:
                messages.error(request, 'Bitte geben Sie Start- und Enddatum für die Löschung an.')
        else:
            settings_obj.save()
            messages.success(request, 'Einstellungen wurden gespeichert!')
        
        return redirect('loomads:settings')
    
    # Get app definitions for zone status overview
    app_definitions = {
        'dashboard': {
            'name': 'Dashboard',
            'app_name': 'dashboard'
        },
        'wirtschaftlichkeitsrechner': {
            'name': 'Wirtschaftlichkeitsrechner',
            'app_name': 'wirtschaftlichkeitsrechner'
        },
        'sportplatz_konfigurator': {
            'name': 'Sportplatz-Konfigurator',
            'app_name': 'sportplatz_konfigurator'
        },
        'pdf_suche': {
            'name': 'PDF-Suche',
            'app_name': 'pdf_suche'
        },
        'ki_zusammenfassung': {
            'name': 'KI-Zusammenfassung',
            'app_name': 'ki_zusammenfassung'
        },
        'shopify': {
            'name': 'Shopify Integration',
            'app_name': 'shopify'
        },
        'bilder': {
            'name': 'Bilder-Editor',
            'app_name': 'bilder'
        },
        'videos': {
            'name': 'Video-Management',
            'app_name': 'videos'
        },
        'audio': {
            'name': 'Audio Studio',
            'app_name': 'audio'
        },
        'loomads': {
            'name': 'LoomAds',
            'app_name': 'loomads'
        },
        'superconfig': {
            'name': 'SuperConfig',
            'app_name': 'superconfig'
        }
    }
    
    # Build app zone status overview
    app_zone_status = []
    zone_types = ['header', 'footer', 'sidebar', 'infeed', 'modal', 'video_preroll', 'video_overlay', 'video_popup', 'content_card', 'notification']
    
    for app_key, app_config in app_definitions.items():
        app_name = app_config['app_name']
        app_status = {
            'name': app_config['name'],
            'app_name': app_name,
            'zones': {}
        }
        
        for zone_type in zone_types:
            app_status['zones'][zone_type] = settings_obj.is_zone_enabled(zone_type, app_name)
        
        app_zone_status.append(app_status)
    
    # Analytics-Statistiken für Settings-Übersicht
    from .models import AdImpression, AdClick
    total_impressions = AdImpression.objects.count()
    total_clicks = AdClick.objects.count()
    overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    
    context = {
        'settings': settings_obj,
        'total_campaigns': Campaign.objects.count(),
        'total_ads': Advertisement.objects.count(),
        'total_zones': AdZone.objects.count(),
        'active_campaigns': Campaign.objects.filter(status='active').count(),
        'active_ads': Advertisement.objects.filter(is_active=True).count(),
        'active_zones': AdZone.objects.filter(is_active=True).count(),
        'app_zone_status': app_zone_status,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'overall_ctr': overall_ctr,
    }
    return render(request, 'loomads/settings.html', context)


@require_POST
@login_required
@user_passes_test(is_superuser)
def ajax_update_zone_status(request):
    """AJAX endpoint to update app-specific zone status"""
    try:
        data = json.loads(request.body)
        app_name = data.get('app_name')
        zone_type = data.get('zone_type')
        enabled = data.get('enabled', True)
        
        if not app_name or not zone_type:
            return JsonResponse({
                'success': False, 
                'error': 'App name and zone type are required'
            })
        
        settings_obj = LoomAdsSettings.get_settings()
        settings_obj.set_zone_enabled(zone_type, app_name, enabled)
        
        return JsonResponse({
            'success': True,
            'message': f'{zone_type} zones for app "{app_name}" {"enabled" if enabled else "disabled"}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ========== EXAMPLES PAGES ==========

@login_required
@user_passes_test(is_superuser)
def examples_overview(request):
    """Show zone tiles overview page with hardcoded examples"""
    from .hardcoded_examples import HARDCODED_EXAMPLES

    # Get app filter from URL parameter
    app_filter = request.GET.get('app', None)

    # App-spezifische Zonen aus der Datenbank mit erstellten Beispielanzeigen
    app_zones = {}

    # App-spezifische Zonen aus der Datenbank
    app_zone_configs = {
        'loomline': {'prefix': 'loomline_', 'default_width': 300, 'default_height': 250},
        'fileshare': {'prefix': 'fileshare_', 'default_width': 400, 'default_height': 200},
        'streamrec': {'prefix': 'streamrec_', 'default_width': 350, 'default_height': 180},
        'promptpro': {'prefix': 'promptpro_', 'default_width': 320, 'default_height': 200},
        'blog': {'prefix': 'blog_', 'default_width': 728, 'default_height': 90},
        'videos': {'prefix': 'videos_', 'default_width': 400, 'default_height': 300},
        'chat': {'prefix': 'chat_', 'default_width': 300, 'default_height': 150}
    }

    # Lade Zonen für alle Apps aus der Datenbank
    for app_name, config in app_zone_configs.items():
        zones = AdZone.objects.filter(code__startswith=config['prefix'], is_active=True)
        for zone in zones:
            if zone.code not in app_zones:
                app_zones[zone.code] = {
                    'zone_name': zone.name,
                    'zone_id': zone.id,
                    'width': zone.width or config['default_width'],
                    'height': zone.height or config['default_height'],
                    'size_category': get_size_category(zone.width or config['default_width'], zone.height or config['default_height']),
                    'app': app_name,
                    'ads': get_sample_ads_for_zone(zone, app_name)
                }

    # Bestehende hartcodierte Beispiele zu anderen Apps hinzufügen
    for zone_code, zone_info in HARDCODED_EXAMPLES.items():
        if zone_code not in app_zones:
            app_zones[zone_code] = {
                **zone_info,
                'app': determine_app_from_zone_code(zone_code)
            }

    # Gruppiere nach Apps
    apps_data = {}
    for zone_code, zone_info in app_zones.items():
        app = zone_info.get('app', 'other')

        # Filter nach App wenn gewählt
        if app_filter and app != app_filter:
            continue

        if app not in apps_data:
            apps_data[app] = {
                'name': get_app_display_name(app),
                'zones': [],
                'total_zones': 0,
                'total_ads': 0
            }

        zone_data = {
            'zone': {
                'id': zone_info['zone_id'],
                'name': zone_info['zone_name'],
                'code': zone_code,
                'width': zone_info['width'],
                'height': zone_info['height']
            },
            'ads_count': len(zone_info['ads']),
            'size_category': zone_info['size_category'],
            'app': app
        }

        apps_data[app]['zones'].append(zone_data)
        apps_data[app]['total_zones'] += 1
        apps_data[app]['total_ads'] += len(zone_info['ads'])

    # Sortiere Apps und Zonen
    for app_data in apps_data.values():
        app_data['zones'].sort(key=lambda x: x['zone']['name'])

    # Apps nach Priorität sortieren
    app_priority = {
        'loomline': 1, 'fileshare': 2, 'streamrec': 3, 'promptpro': 4, 'blog': 5,
        'videos': 6, 'chat': 7, 'dashboard': 8, 'global': 9, 'other': 99
    }
    sorted_apps = sorted(apps_data.items(), key=lambda x: app_priority.get(x[0], 50))

    context = {
        'apps_data': sorted_apps,
        'total_zones': sum(app['total_zones'] for app in apps_data.values()),
        'total_ads': sum(app['total_ads'] for app in apps_data.values()),
        'is_hardcoded': True,
        'app_filter': app_filter,
        'available_apps': sorted(apps_data.keys())
    }

    return render(request, 'loomads/examples/overview_grouped.html', context)


def get_size_category(width, height):
    """Bestimme Größenkategorie basierend auf Dimensionen"""
    area = width * height
    if area < 50000:  # z.B. 300x160
        return 'small'
    elif area < 120000:  # z.B. 400x300
        return 'medium'
    else:
        return 'large'


def get_app_display_name(app_code):
    """Benutzerfreundliche App-Namen"""
    app_names = {
        'loomline': 'LoomLine',
        'fileshare': 'FileShara',
        'streamrec': 'StreamRec',
        'promptpro': 'PromptPro',
        'blog': 'Blog',
        'dashboard': 'Dashboard',
        'videos': 'Video-Management',
        'audio': 'Audio Studio',
        'bilder': 'Bilder-Editor',
        'shopify': 'Shopify Integration',
        'chat': 'Chat-System',
        'global': 'Global Bereiche',
        'other': 'Andere Apps'
    }
    return app_names.get(app_code, app_code.title())


def determine_app_from_zone_code(zone_code):
    """Bestimme App aus Zone-Code"""
    if zone_code.startswith('loomline_'):
        return 'loomline'
    elif zone_code.startswith('fileshare_'):
        return 'fileshare'
    elif zone_code.startswith('streamrec_'):
        return 'streamrec'
    elif zone_code.startswith('promptpro_'):
        return 'promptpro'
    elif zone_code.startswith('blog_'):
        return 'blog'
    elif zone_code.startswith('videos_') or 'video' in zone_code:
        return 'videos'
    elif zone_code.startswith('dashboard_') or 'dashboard' in zone_code:
        return 'dashboard'
    elif zone_code.startswith('chat_'):
        return 'chat'
    elif zone_code.startswith('header_') or zone_code.startswith('footer_') or zone_code.startswith('main_'):
        return 'global'
    elif 'shopify' in zone_code or 'produkte' in zone_code or 'kategorien' in zone_code or 'stores' in zone_code or zone_code.startswith('collection_'):
        return 'shopify'
    elif 'audio' in zone_code:
        return 'audio'
    elif 'bilder' in zone_code or 'image' in zone_code:
        return 'bilder'
    else:
        return 'other'


def get_sample_ads_for_zone(zone, app):
    """Erstelle Beispielanzeigen für eine Zone"""
    if app == 'loomline':
        return get_loomline_sample_ads(zone)
    elif app == 'fileshare':
        return get_fileshare_sample_ads(zone)
    elif app == 'streamrec':
        return get_streamrec_sample_ads(zone)
    elif app == 'promptpro':
        return get_promptpro_sample_ads(zone)
    elif app == 'blog':
        return get_blog_sample_ads(zone)
    else:
        return []


def get_loomline_sample_ads(zone):
    """LoomLine-spezifische Beispielanzeigen"""
    ads = []

    # Premium Features Ad
    ads.append({
        'name': f'LoomLine Premium - {zone.name}',
        'title': 'LoomLine Premium Features',
        'campaign': 'LoomLine Integration',
        'weight': 8,
        'description': f'Premium-Features Anzeige für {zone.name}',
        'html_content': f'''
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 12px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: {zone.width or 300}px; height: {zone.height or 200}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 32px; margin-bottom: 10px;">🚀</div>
            <h3 style="margin: 0 0 10px 0; font-size: 18px;">LoomLine Pro</h3>
            <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.9;">Erweiterte Projekt-Features & KI-Analytics</p>
            <button style="background: white; color: #667eea; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer;">Jetzt upgraden</button>
        </div>
        '''
    })

    # Task Management Ad
    ads.append({
        'name': f'Smart Tasks - {zone.name}',
        'title': 'Intelligente Aufgabenverwaltung',
        'campaign': 'LoomLine Features',
        'weight': 7,
        'description': f'Smart Tasks Anzeige für {zone.name}',
        'html_content': f'''
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 12px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: {zone.width or 300}px; height: {zone.height or 200}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 28px; margin-bottom: 10px;">📋</div>
            <h3 style="margin: 0 0 10px 0; font-size: 16px;">Smart Tasks</h3>
            <p style="margin: 0 0 15px 0; font-size: 12px; opacity: 0.9;">KI-unterstützte Aufgabenpriorisierung</p>
            <div style="background: rgba(255,255,255,0.2); padding: 8px; border-radius: 4px; font-size: 11px;">+40% Effizienz</div>
        </div>
        '''
    })

    return ads


def get_fileshare_sample_ads(zone):
    """FileShara-spezifische Beispielanzeigen"""
    ads = []

    # Storage Upgrade Ad
    ads.append({
        'name': f'FileShara Pro Storage - {zone.name}',
        'title': 'Unbegrenzter Cloud-Speicher',
        'campaign': 'FileShara Premium',
        'weight': 9,
        'description': f'Storage-Upgrade Anzeige für {zone.name}',
        'html_content': f'''
        <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: {zone.width or 400}px; height: {zone.height or 200}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 36px; margin-bottom: 10px;">💾</div>
            <h3 style="margin: 0 0 10px 0; font-size: 20px;">FileShara PRO</h3>
            <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 8px; margin: 10px 0;">
                <div style="font-size: 24px; font-weight: bold;">100GB</div>
                <div style="font-size: 12px;">Cloud-Speicher</div>
            </div>
            <button style="background: white; color: #ff6b6b; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer;">Upgrade starten</button>
        </div>
        '''
    })

    # Security Features Ad
    ads.append({
        'name': f'Sicherheits-Features - {zone.name}',
        'title': 'Erweiterte Dateisicherheit',
        'campaign': 'FileShara Security',
        'weight': 8,
        'description': f'Sicherheits-Features Anzeige für {zone.name}',
        'html_content': f'''
        <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: {zone.width or 400}px; height: {zone.height or 200}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 32px; margin-bottom: 10px;">🔒</div>
            <h3 style="margin: 0 0 10px 0; font-size: 18px;">Enterprise Security</h3>
            <ul style="list-style: none; padding: 0; margin: 10px 0; font-size: 12px; text-align: left;">
                <li style="margin: 4px 0;">✓ End-to-End Verschlüsselung</li>
                <li style="margin: 4px 0;">✓ Erweiterte Zugriffskontrollen</li>
                <li style="margin: 4px 0;">✓ Audit-Protokolle</li>
            </ul>
            <button style="background: white; color: #4facfe; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer;">Mehr erfahren</button>
        </div>
        '''
    })

    # Speed Boost Ad
    ads.append({
        'name': f'Upload Speed Boost - {zone.name}',
        'title': '10x schnellere Uploads',
        'campaign': 'FileShara Performance',
        'weight': 7,
        'description': f'Speed Boost Anzeige für {zone.name}',
        'html_content': f'''
        <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #2c3e50; padding: 20px; border-radius: 12px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: {zone.width or 400}px; height: {zone.height or 200}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 28px; margin-bottom: 10px;">⚡</div>
            <h3 style="margin: 0 0 10px 0; font-size: 16px;">Speed Boost</h3>
            <div style="background: #2c3e50; color: white; padding: 8px; border-radius: 6px; margin: 10px 0; font-weight: bold;">
                10x schneller
            </div>
            <p style="margin: 0; font-size: 11px;">Premium Upload-Geschwindigkeit</p>
        </div>
        '''
    })

    return ads


@login_required
@user_passes_test(is_superuser)
def examples_zone_detail(request, zone_id):
    """Show example ads for specific zone using both DB and hardcoded data"""
    from .hardcoded_examples import HARDCODED_EXAMPLES

    zone = None
    ads = []

    # Erst in Datenbank-Zonen suchen (LoomLine/FileShara)
    try:
        db_zone = AdZone.objects.get(id=zone_id)
        app = determine_app_from_zone_code(db_zone.code)

        zone = {
            'id': db_zone.id,
            'name': db_zone.name,
            'code': db_zone.code,
            'width': db_zone.width or 300,
            'height': db_zone.height or 200,
            'app': app
        }

        # Generiere Beispielanzeigen für diese Zone
        sample_ads = get_sample_ads_for_zone(db_zone, app)

        for i, ad_data in enumerate(sample_ads):
            try:
                ads.append({
                    'id': f"db_{zone_id}_{i}",
                    'name': ad_data.get('name', f'Anzeige {i+1}'),
                    'title': ad_data.get('title', 'Beispielanzeige'),
                    'html_content': ad_data.get('html_content', ''),
                    'campaign': {'name': ad_data.get('campaign', 'Beispielkampagne')},
                    'weight': ad_data.get('weight', 5),
                    'description': ad_data.get('description', '')
                })
            except Exception as e:
                print(f"Error processing DB ad {i}: {e}")
                # Skip this ad but continue with others
                continue

    except AdZone.DoesNotExist:
        # Fallback zu hartcodierten Daten
        zone_data = None
        zone_code = None

        for code, data in HARDCODED_EXAMPLES.items():
            try:
                if str(data.get('zone_id', '')) == str(zone_id):
                    zone_data = data
                    zone_code = code
                    break
            except Exception as e:
                print(f"Error checking hardcoded zone {code}: {e}")
                continue

        if not zone_data:
            from django.http import Http404
            raise Http404(f"Zone mit ID {zone_id} nicht gefunden")

        try:
            zone = {
                'id': zone_data.get('zone_id', zone_id),
                'name': zone_data.get('zone_name', f'Zone {zone_id}'),
                'code': zone_code or f'zone_{zone_id}',
                'width': zone_data.get('width', 300),
                'height': zone_data.get('height', 200),
                'app': determine_app_from_zone_code(zone_code or '')
            }

            # Anzeigen aus hartcodierten Daten
            hardcoded_ads = zone_data.get('ads', [])
            for i, ad_data in enumerate(hardcoded_ads):
                try:
                    ads.append({
                        'id': f"hc_{zone_id}_{i}",
                        'name': ad_data.get('name', f'Anzeige {i+1}'),
                        'title': ad_data.get('title', 'Beispielanzeige'),
                        'html_content': ad_data.get('html_content', '<div>Keine Anzeige verfügbar</div>'),
                        'campaign': {'name': ad_data.get('campaign', 'Beispielkampagne')},
                        'weight': ad_data.get('weight', 5),
                        'description': ad_data.get('description', '')
                    })
                except Exception as e:
                    print(f"Error processing hardcoded ad {i}: {e}")
                    # Skip this ad but continue with others
                    continue

        except Exception as e:
            print(f"Error processing zone data: {e}")
            from django.http import Http404
            raise Http404(f"Fehler beim Verarbeiten der Zone {zone_id}")

    # Falls immer noch keine Zone gefunden wurde
    if not zone:
        from django.http import Http404
        raise Http404(f"Zone mit ID {zone_id} konnte nicht geladen werden")

    context = {
        'zone': zone,
        'ads': ads,
        'ads_count': len(ads),
        'is_hardcoded': True,
        'app_name': get_app_display_name(zone.get('app', 'other'))
    }

    return render(request, 'loomads/examples/zone_detail.html', context)


# ========== ZONE INTEGRATION MANAGEMENT ==========

@login_required
@user_passes_test(is_superuser)
def integration_create(request):
    """Create new zone integration"""
    if request.method == 'POST':
        form = ZoneIntegrationForm(request.POST)
        if form.is_valid():
            integration = form.save()
            messages.success(request, f'Integration "{integration.zone_code}" in "{integration.template_path}" wurde erfolgreich erstellt!')
            return redirect('loomads:zone_list')
    else:
        form = ZoneIntegrationForm()
    
    context = {
        'form': form,
        'title': 'Neue Zone Integration erstellen'
    }
    return render(request, 'loomads/integration_form.html', context)


@login_required
@user_passes_test(is_superuser)
def integration_edit(request, integration_id):
    """Edit existing zone integration"""
    integration = get_object_or_404(ZoneIntegration, id=integration_id)
    
    if request.method == 'POST':
        form = ZoneIntegrationForm(request.POST, instance=integration)
        if form.is_valid():
            form.save()
            messages.success(request, f'Integration "{integration.zone_code}" wurde aktualisiert!')
            return redirect('loomads:zone_list')
    else:
        form = ZoneIntegrationForm(instance=integration)
    
    context = {
        'form': form,
        'integration': integration,
        'title': f'Integration "{integration.zone_code}" bearbeiten'
    }
    return render(request, 'loomads/integration_form.html', context)


@login_required
@user_passes_test(is_superuser)
def integration_delete(request, integration_id):
    """Delete zone integration"""
    integration = get_object_or_404(ZoneIntegration, id=integration_id)
    
    if request.method == 'POST':
        integration_info = f"{integration.zone_code} in {integration.template_path}"
        integration.delete()
        messages.success(request, f'Integration "{integration_info}" wurde gelöscht!')
        return redirect('loomads:zone_list')
    
    context = {
        'integration': integration
    }
    return render(request, 'loomads/integration_confirm_delete.html', context)


# ========== AUTO CAMPAIGN MANAGEMENT ==========

@login_required
@user_passes_test(is_superuser)
def auto_campaign_list(request):
    """List all auto campaigns"""
    auto_campaigns = AutoCampaign.objects.all().select_related('target_format', 'created_by').order_by('-created_at')
    
    context = {
        'auto_campaigns': auto_campaigns,
        'title': 'Automatische Kampagnen'
    }
    return render(request, 'loomads/auto_campaign_list.html', context)


@login_required
@user_passes_test(is_superuser)
def auto_campaign_detail(request, campaign_id):
    """Show auto campaign details"""
    campaign = get_object_or_404(AutoCampaign, id=campaign_id)
    
    # Get matching zones for this campaign's format
    matching_zones = campaign.target_format.get_matching_zones()
    
    # Get auto advertisements
    auto_ads = campaign.auto_advertisements.all().select_related('target_zone')
    
    context = {
        'campaign': campaign,
        'matching_zones': matching_zones,
        'auto_ads': auto_ads,
        'title': f'Auto-Kampagne: {campaign.name}'
    }
    return render(request, 'loomads/auto_campaign_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def auto_campaign_create(request):
    """Create new auto campaign"""
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        description = request.POST.get('description')
        target_format_id = request.POST.get('target_format')
        content_strategy = request.POST.get('content_strategy')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        status = request.POST.get('status', 'draft')
        
        # Validation
        if not all([name, target_format_id, start_date, end_date]):
            messages.error(request, 'Bitte füllen Sie alle Pflichtfelder aus!')
        else:
            try:
                target_format = AutoCampaignFormat.objects.get(id=target_format_id)
                
                # Create auto campaign
                auto_campaign = AutoCampaign.objects.create(
                    name=name,
                    description=description,
                    target_format=target_format,
                    content_strategy=content_strategy,
                    start_date=datetime.fromisoformat(start_date.replace('Z', '+00:00')),
                    end_date=datetime.fromisoformat(end_date.replace('Z', '+00:00')),
                    status=status,
                    created_by=request.user
                )
                
                messages.success(request, f'Auto-Kampagne "{auto_campaign.name}" wurde erfolgreich erstellt!')
                return redirect('loomads:auto_campaign_detail', campaign_id=auto_campaign.id)
                
            except AutoCampaignFormat.DoesNotExist:
                messages.error(request, 'Ungültiges Format ausgewählt!')
            except Exception as e:
                messages.error(request, f'Fehler beim Erstellen: {str(e)}')
    
    # Get available formats
    formats = AutoCampaignFormat.objects.filter(is_active=True).order_by('-priority')
    
    context = {
        'formats': formats,
        'title': 'Neue Auto-Kampagne erstellen',
        'content_strategies': AutoCampaign.CONTENT_STRATEGIES
    }
    return render(request, 'loomads/auto_campaign_form.html', context)


@login_required
@user_passes_test(is_superuser)
def auto_campaign_edit(request, campaign_id):
    """Edit existing auto campaign"""
    campaign = get_object_or_404(AutoCampaign, id=campaign_id)
    
    if request.method == 'POST':
        # Update campaign
        campaign.name = request.POST.get('name')
        campaign.description = request.POST.get('description')
        campaign.content_strategy = request.POST.get('content_strategy')
        campaign.status = request.POST.get('status')
        
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if start_date:
            campaign.start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            campaign.end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        campaign.save()
        messages.success(request, f'Auto-Kampagne "{campaign.name}" wurde aktualisiert!')
        return redirect('loomads:auto_campaign_detail', campaign_id=campaign.id)
    
    # Get available formats
    formats = AutoCampaignFormat.objects.filter(is_active=True).order_by('-priority')
    
    context = {
        'campaign': campaign,
        'formats': formats,
        'title': f'Auto-Kampagne "{campaign.name}" bearbeiten',
        'content_strategies': AutoCampaign.CONTENT_STRATEGIES
    }
    return render(request, 'loomads/auto_campaign_form.html', context)


@login_required
@user_passes_test(is_superuser)
def auto_campaign_delete(request, campaign_id):
    """Delete auto campaign"""
    campaign = get_object_or_404(AutoCampaign, id=campaign_id)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'Auto-Kampagne "{campaign_name}" wurde gelöscht!')
        return redirect('loomads:auto_campaign_list')
    
    context = {
        'campaign': campaign
    }
    return render(request, 'loomads/auto_campaign_confirm_delete.html', context)


# ========== AUTO CAMPAIGN FORMAT MANAGEMENT ==========

@login_required
@user_passes_test(is_superuser)
def auto_format_list(request):
    """List all auto campaign formats"""
    formats = AutoCampaignFormat.objects.all().order_by('-priority', 'name')
    
    # Add zone count for each format
    for fmt in formats:
        fmt.zone_count = fmt.get_zone_count()
    
    context = {
        'formats': formats,
        'title': 'Auto-Kampagnen-Formate'
    }
    return render(request, 'loomads/auto_format_list.html', context)


# ========== SAMPLE ADS GENERATORS FOR NEW APPS ==========

def get_streamrec_sample_ads(zone):
    """StreamRec-spezifische Beispielanzeigen"""
    ads = []

    # Recording Equipment Ad
    if zone.height and zone.height <= 120:
        # Banner style
        ads.append({
            'id': f"streamrec_banner_{zone.id}_1",
            'name': f'StreamRec Pro Equipment - {zone.name}',
            'title': 'Professionelle Aufnahme-Ausrüstung',
            'html_content': f'''
            <div style="width: {zone.width}px; height: {zone.height}px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 8px; display: flex; align-items: center;
                        padding: 10px; color: white; font-family: Arial, sans-serif;">
                <div style="flex: 1;">
                    <div style="font-weight: bold; font-size: 14px;">🎙️ StreamRec Pro</div>
                    <div style="font-size: 11px;">Professionelle Aufnahme-Tools</div>
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 5px 10px;
                           border-radius: 4px; font-size: 11px; font-weight: bold;">
                    Mehr erfahren →
                </div>
            </div>
            ''',
            'campaign': {'name': 'StreamRec Equipment'},
            'weight': 8,
            'description': 'Banner-Anzeige für Recording-Equipment'
        })
    else:
        # Card style
        ads.append({
            'id': f"streamrec_card_{zone.id}_1",
            'name': f'StreamRec Studio Setup - {zone.name}',
            'title': 'Komplettes Studio Setup',
            'html_content': f'''
            <div style="width: {zone.width}px; height: {zone.height}px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 12px; padding: 20px; color: white;
                        font-family: Arial, sans-serif; position: relative; overflow: hidden;">
                <div style="position: absolute; top: -20px; right: -20px;
                           width: 80px; height: 80px; background: rgba(255,255,255,0.1);
                           border-radius: 50%;"></div>
                <div style="font-size: 24px; margin-bottom: 5px;">🎬</div>
                <div style="font-weight: bold; font-size: 16px; margin-bottom: 8px;">
                    StreamRec Studio
                </div>
                <div style="font-size: 12px; margin-bottom: 15px; opacity: 0.9;">
                    Professionelle Aufnahme-Software mit Premium-Features
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 8px 16px;
                           border-radius: 6px; font-size: 12px; font-weight: bold;
                           text-align: center; cursor: pointer;">
                    Jetzt testen →
                </div>
            </div>
            ''',
            'campaign': {'name': 'StreamRec Studio'},
            'weight': 9,
            'description': 'Karten-Anzeige für Studio-Setup'
        })

    # Streaming Tools Ad
    ads.append({
        'id': f"streamrec_tools_{zone.id}_2",
        'name': f'StreamRec Live Tools - {zone.name}',
        'title': 'Live-Streaming Tools',
        'html_content': f'''
        <div style="width: {zone.width}px; height: {zone.height}px;
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                    border-radius: 8px; padding: 15px; color: white;
                    font-family: Arial, sans-serif; text-align: center;">
            <div style="font-size: 20px; margin-bottom: 8px;">📡</div>
            <div style="font-weight: bold; font-size: 14px; margin-bottom: 5px;">
                Live-Streaming
            </div>
            <div style="font-size: 11px; margin-bottom: 10px;">
                Professionelle Tools für Live-Übertragungen
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 6px 12px;
                       border-radius: 4px; font-size: 11px; display: inline-block;">
                Demo ansehen
            </div>
        </div>
        ''',
        'campaign': {'name': 'StreamRec Live'},
        'weight': 7,
        'description': 'Live-Streaming Tools Anzeige'
    })

    return ads


def get_promptpro_sample_ads(zone):
    """PromptPro-spezifische Beispielanzeigen"""
    ads = []

    # AI Prompts Ad
    ads.append({
        'id': f"promptpro_ai_{zone.id}_1",
        'name': f'PromptPro AI Assistant - {zone.name}',
        'title': 'KI-gestützte Prompt-Generierung',
        'html_content': f'''
        <div style="width: {zone.width}px; height: {zone.height}px;
                    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                    border-radius: 10px; padding: 16px; color: white;
                    font-family: Arial, sans-serif; position: relative;">
            <div style="position: absolute; top: 10px; right: 10px;
                       background: rgba(255,255,255,0.2); border-radius: 50%;
                       width: 30px; height: 30px; display: flex; align-items: center;
                       justify-content: center; font-size: 14px;">🤖</div>
            <div style="font-weight: bold; font-size: 16px; margin-bottom: 8px;">
                PromptPro AI
            </div>
            <div style="font-size: 12px; margin-bottom: 12px; opacity: 0.9;">
                Intelligente Prompt-Optimierung für bessere KI-Ergebnisse
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 8px 14px;
                       border-radius: 5px; font-size: 11px; display: inline-block;">
                ✨ Prompts optimieren
            </div>
        </div>
        ''',
        'campaign': {'name': 'PromptPro AI'},
        'weight': 9,
        'description': 'KI-Prompt-Optimierung Anzeige'
    })

    # Template Library Ad
    ads.append({
        'id': f"promptpro_templates_{zone.id}_2",
        'name': f'PromptPro Templates - {zone.name}',
        'title': 'Professionelle Prompt-Vorlagen',
        'html_content': f'''
        <div style="width: {zone.width}px; height: {zone.height}px;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    border-radius: 8px; padding: 14px; color: white;
                    font-family: Arial, sans-serif;">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <div style="font-size: 18px; margin-right: 8px;">📝</div>
                <div style="font-weight: bold; font-size: 14px;">Template-Bibliothek</div>
            </div>
            <div style="font-size: 11px; margin-bottom: 12px;">
                500+ vorgefertigte Prompts für alle Anwendungsfälle
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 6px 12px;
                       border-radius: 4px; font-size: 11px; text-align: center;">
                Bibliothek durchsuchen →
            </div>
        </div>
        ''',
        'campaign': {'name': 'PromptPro Templates'},
        'weight': 8,
        'description': 'Template-Bibliothek Anzeige'
    })

    return ads


def get_blog_sample_ads(zone):
    """Blog-spezifische Beispielanzeigen"""
    ads = []

    # Content Marketing Ad
    ads.append({
        'id': f"blog_content_{zone.id}_1",
        'name': f'Blog Content Marketing - {zone.name}',
        'title': 'Professionelles Content Marketing',
        'html_content': f'''
        <div style="width: {zone.width}px; height: {zone.height}px;
                    background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
                    border-radius: 6px; padding: 12px; color: white;
                    font-family: Arial, sans-serif; display: flex;
                    align-items: center; justify-content: center;">
            <div style="text-align: center;">
                <div style="font-size: 16px; margin-bottom: 5px;">✍️</div>
                <div style="font-weight: bold; font-size: 13px; margin-bottom: 4px;">
                    Content Marketing
                </div>
                <div style="font-size: 10px; margin-bottom: 8px;">
                    Professionelle Blog-Artikel & SEO-Optimierung
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 4px 8px;
                           border-radius: 3px; font-size: 10px;">
                    Mehr erfahren
                </div>
            </div>
        </div>
        ''',
        'campaign': {'name': 'Blog Content'},
        'weight': 7,
        'description': 'Content Marketing für Blog'
    })

    # SEO Tools Ad
    ads.append({
        'id': f"blog_seo_{zone.id}_2",
        'name': f'Blog SEO Tools - {zone.name}',
        'title': 'SEO-Optimierung für Blogs',
        'html_content': f'''
        <div style="width: {zone.width}px; height: {zone.height}px;
                    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                    border-radius: 8px; padding: 10px; color: white;
                    font-family: Arial, sans-serif;">
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="font-size: 14px; margin-right: 6px;">🔍</div>
                <div style="font-weight: bold; font-size: 12px;">SEO-Boost</div>
            </div>
            <div style="font-size: 10px; margin-bottom: 10px;">
                Optimiere deine Blog-Artikel für bessere Suchmaschinen-Rankings
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 5px 10px;
                       border-radius: 4px; font-size: 10px; text-align: center;">
                SEO analysieren →
            </div>
        </div>
        ''',
        'campaign': {'name': 'Blog SEO'},
        'weight': 8,
        'description': 'SEO-Tools für Blog-Optimierung'
    })

    return ads