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
from .models import Campaign, AdZone, Advertisement, AdTargeting, LoomAdsSettings, ZoneIntegration
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
    
    # Verwende hartcodierte Daten statt Datenbank
    zone_data = []
    for zone_code, zone_info in HARDCODED_EXAMPLES.items():
        zone_data.append({
            'zone': {
                'id': zone_info['zone_id'],
                'name': zone_info['zone_name'],
                'code': zone_code,
                'width': zone_info['width'],
                'height': zone_info['height']
            },
            'ads_count': len(zone_info['ads']),
            'size_category': zone_info['size_category']
        })
    
    # Sortiere nach Zone-Namen
    zone_data.sort(key=lambda x: x['zone']['name'])
    
    context = {
        'zone_data': zone_data,
        'total_zones': len(zone_data),
        'is_hardcoded': True  # Flag für Template
    }
    
    return render(request, 'loomads/examples/overview.html', context)


@login_required  
@user_passes_test(is_superuser)
def examples_zone_detail(request, zone_id):
    """Show example ads for specific zone using hardcoded data"""
    from .hardcoded_examples import HARDCODED_EXAMPLES
    
    # Finde Zone in hartcodierten Daten
    zone_data = None
    zone_code = None
    
    for code, data in HARDCODED_EXAMPLES.items():
        if str(data['zone_id']) == str(zone_id):
            zone_data = data
            zone_code = code
            break
    
    if not zone_data:
        from django.http import Http404
        raise Http404("Zone nicht gefunden")
    
    # Simuliere Zone-Objekt
    zone = {
        'id': zone_data['zone_id'],
        'name': zone_data['zone_name'],
        'code': zone_code,
        'width': zone_data['width'],
        'height': zone_data['height']
    }
    
    # Anzeigen aus hartcodierten Daten
    ads = []
    for i, ad_data in enumerate(zone_data['ads']):
        ads.append({
            'id': f"{zone_id}_{i}",  # Generiere eindeutige ID
            'name': ad_data['name'],
            'title': ad_data['title'], 
            'html_content': ad_data['html_content'],
            'campaign': {'name': ad_data['campaign']},
            'weight': ad_data['weight'],
            'description': ad_data.get('description', '')
        })
    
    context = {
        'zone': zone,
        'ads': ads,
        'ads_count': len(ads),
        'is_hardcoded': True
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