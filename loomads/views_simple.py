"""
Simple Ads Views - Vereinfachte Anzeigenverwaltung
Ermöglicht das Erstellen von globalen Anzeigen ohne komplexe Kampagnen-Struktur.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import F

from .models import SimpleAd
from .forms import SimpleAdForm


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def simple_ad_list(request):
    """Liste aller Simple Ads"""
    ads = SimpleAd.objects.all().order_by('-created_at')

    # Statistiken
    total_ads = ads.count()
    active_ads = ads.filter(is_active=True).count()
    total_impressions = sum(ad.impressions for ad in ads)
    total_clicks = sum(ad.clicks for ad in ads)
    overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

    context = {
        'ads': ads,
        'total_ads': total_ads,
        'active_ads': active_ads,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'overall_ctr': overall_ctr,
    }
    return render(request, 'loomads/simple_ad_list.html', context)


@login_required
@user_passes_test(is_superuser)
def simple_ad_create(request):
    """Neue Simple Ad erstellen"""
    if request.method == 'POST':
        form = SimpleAdForm(request.POST, request.FILES)
        if form.is_valid():
            ad = form.save()
            messages.success(request, f'Anzeige "{ad.title}" wurde erfolgreich erstellt!')
            return redirect('loomads:simple_ad_list')
    else:
        form = SimpleAdForm()

    context = {
        'form': form,
        'title': 'Neue Anzeige erstellen',
        'submit_text': 'Anzeige erstellen',
    }
    return render(request, 'loomads/simple_ad_form.html', context)


@login_required
@user_passes_test(is_superuser)
def simple_ad_edit(request, ad_id):
    """Simple Ad bearbeiten"""
    ad = get_object_or_404(SimpleAd, id=ad_id)

    if request.method == 'POST':
        form = SimpleAdForm(request.POST, request.FILES, instance=ad)
        if form.is_valid():
            ad = form.save()
            messages.success(request, f'Anzeige "{ad.title}" wurde erfolgreich aktualisiert!')
            return redirect('loomads:simple_ad_list')
    else:
        form = SimpleAdForm(instance=ad)

    context = {
        'form': form,
        'ad': ad,
        'title': 'Anzeige bearbeiten',
        'submit_text': 'Änderungen speichern',
    }
    return render(request, 'loomads/simple_ad_form.html', context)


@login_required
@user_passes_test(is_superuser)
def simple_ad_delete(request, ad_id):
    """Simple Ad löschen"""
    ad = get_object_or_404(SimpleAd, id=ad_id)

    if request.method == 'POST':
        title = ad.title
        ad.delete()
        messages.success(request, f'Anzeige "{title}" wurde gelöscht.')
        return redirect('loomads:simple_ad_list')

    context = {
        'ad': ad,
    }
    return render(request, 'loomads/simple_ad_confirm_delete.html', context)


@login_required
@user_passes_test(is_superuser)
def simple_ad_toggle(request, ad_id):
    """Simple Ad aktivieren/deaktivieren (AJAX)"""
    ad = get_object_or_404(SimpleAd, id=ad_id)
    ad.is_active = not ad.is_active
    ad.save(update_fields=['is_active'])

    return JsonResponse({
        'success': True,
        'is_active': ad.is_active,
        'message': f'Anzeige {"aktiviert" if ad.is_active else "deaktiviert"}.'
    })


@login_required
@user_passes_test(is_superuser)
def simple_ad_preview(request, ad_id):
    """Live-Preview einer Simple Ad"""
    ad = get_object_or_404(SimpleAd, id=ad_id)

    context = {
        'ad': ad,
    }
    return render(request, 'loomads/simple_ad_preview.html', context)
