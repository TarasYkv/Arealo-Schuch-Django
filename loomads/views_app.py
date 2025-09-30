from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta

from .models import AppCampaign, AppAdvertisement, AdZone
from .forms import AppCampaignForm, AppAdvertisementForm


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def app_campaign_list(request):
    """Liste aller App-Kampagnen"""
    campaigns = AppCampaign.objects.all().order_by('-created_at')

    # Filter
    app_filter = request.GET.get('app')
    if app_filter:
        campaigns = campaigns.filter(app_target=app_filter)

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

    # App choices für Filter
    app_choices = AppCampaign.APP_CHOICES

    context = {
        'page_obj': page_obj,
        'app_filter': app_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'app_choices': app_choices,
    }

    return render(request, 'loomads/app_campaign_list.html', context)


@login_required
@user_passes_test(is_superuser)
def app_campaign_detail(request, campaign_id):
    """App-Kampagnen-Details anzeigen"""
    campaign = get_object_or_404(AppCampaign, id=campaign_id)
    advertisements = campaign.app_advertisements.all()

    # Statistiken für die Kampagne
    total_impressions = campaign.get_total_impressions()
    total_clicks = campaign.get_total_clicks()
    campaign_ctr = campaign.get_ctr()

    # Ziel-Zonen
    target_zones = campaign.get_target_zones()

    context = {
        'campaign': campaign,
        'advertisements': advertisements,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'campaign_ctr': campaign_ctr,
        'target_zones': target_zones,
        'target_zones_count': len(target_zones),
    }

    return render(request, 'loomads/app_campaign_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def app_campaign_create(request):
    """Neue App-Kampagne erstellen"""
    if request.method == 'POST':
        form = AppCampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()

            messages.success(request, f'App-Kampagne "{campaign.name}" wurde erfolgreich erstellt.')
            return redirect('loomads:app_campaign_detail', campaign_id=campaign.id)
    else:
        form = AppCampaignForm()

    context = {
        'form': form,
        'title': 'Neue App-Kampagne erstellen',
    }

    return render(request, 'loomads/app_campaign_form.html', context)


@login_required
@user_passes_test(is_superuser)
def app_campaign_edit(request, campaign_id):
    """App-Kampagne bearbeiten"""
    campaign = get_object_or_404(AppCampaign, id=campaign_id)

    if request.method == 'POST':
        form = AppCampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            messages.success(request, f'App-Kampagne "{campaign.name}" wurde erfolgreich aktualisiert.')
            return redirect('loomads:app_campaign_detail', campaign_id=campaign.id)
    else:
        form = AppCampaignForm(instance=campaign)

    context = {
        'form': form,
        'campaign': campaign,
        'title': f'App-Kampagne "{campaign.name}" bearbeiten',
    }

    return render(request, 'loomads/app_campaign_form.html', context)


@login_required
@user_passes_test(is_superuser)
def app_campaign_delete(request, campaign_id):
    """App-Kampagne löschen"""
    campaign = get_object_or_404(AppCampaign, id=campaign_id)

    if request.method == 'POST':
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'App-Kampagne "{campaign_name}" wurde erfolgreich gelöscht.')
        return redirect('loomads:app_campaign_list')

    context = {
        'campaign': campaign,
    }

    return render(request, 'loomads/app_campaign_confirm_delete.html', context)


@login_required
@user_passes_test(is_superuser)
def app_ad_create(request, campaign_id):
    """Neue App-Anzeige erstellen"""
    campaign = get_object_or_404(AppCampaign, id=campaign_id)

    if request.method == 'POST':
        form = AppAdvertisementForm(request.POST, request.FILES)
        if form.is_valid():
            ad = form.save(commit=False)
            ad.app_campaign = campaign
            ad.save()

            # Automatisch mit App-Zonen synchronisieren
            ad.sync_with_app_zones()

            messages.success(request, f'App-Anzeige "{ad.name}" wurde erfolgreich erstellt und mit {ad.zones.count()} Zonen synchronisiert.')
            return redirect('loomads:app_campaign_detail', campaign_id=campaign.id)
    else:
        form = AppAdvertisementForm()

    context = {
        'form': form,
        'campaign': campaign,
        'title': f'Neue Anzeige für Kampagne "{campaign.name}" erstellen',
    }

    return render(request, 'loomads/app_ad_form.html', context)


@login_required
@user_passes_test(is_superuser)
def app_ad_edit(request, ad_id):
    """App-Anzeige bearbeiten"""
    ad = get_object_or_404(AppAdvertisement, id=ad_id)

    if request.method == 'POST':
        form = AppAdvertisementForm(request.POST, request.FILES, instance=ad)
        if form.is_valid():
            form.save()

            # Zone-Synchronisation aktualisieren
            ad.sync_with_app_zones()

            messages.success(request, f'App-Anzeige "{ad.name}" wurde erfolgreich aktualisiert.')
            return redirect('loomads:app_campaign_detail', campaign_id=ad.app_campaign.id)
    else:
        form = AppAdvertisementForm(instance=ad)

    context = {
        'form': form,
        'ad': ad,
        'title': f'Anzeige "{ad.name}" bearbeiten',
    }

    return render(request, 'loomads/app_ad_form.html', context)


@login_required
@user_passes_test(is_superuser)
def app_ad_delete(request, ad_id):
    """App-Anzeige löschen"""
    ad = get_object_or_404(AppAdvertisement, id=ad_id)
    campaign_id = ad.app_campaign.id

    if request.method == 'POST':
        ad_name = ad.name
        ad.delete()
        messages.success(request, f'App-Anzeige "{ad_name}" wurde erfolgreich gelöscht.')
        return redirect('loomads:app_campaign_detail', campaign_id=campaign_id)

    context = {
        'ad': ad,
    }

    return render(request, 'loomads/app_ad_confirm_delete.html', context)