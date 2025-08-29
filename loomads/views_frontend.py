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
from .models import Campaign, AdZone, Advertisement, AdTargeting, LoomAdsSettings
from .forms import CampaignForm, AdvertisementForm, AdZoneForm
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
        
        settings_obj.save()
        messages.success(request, 'Einstellungen wurden gespeichert!')
        return redirect('loomads:settings')
    
    context = {
        'settings': settings_obj,
        'total_campaigns': Campaign.objects.count(),
        'total_ads': Advertisement.objects.count(),
        'total_zones': AdZone.objects.count(),
        'active_campaigns': Campaign.objects.filter(status='active').count(),
        'active_ads': Advertisement.objects.filter(is_active=True).count(),
        'active_zones': AdZone.objects.filter(is_active=True).count(),
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