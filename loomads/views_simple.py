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


@login_required
@user_passes_test(is_superuser)
def simple_ad_duplicate(request, ad_id):
    """Simple Ad duplizieren"""
    original_ad = get_object_or_404(SimpleAd, id=ad_id)

    # Neuen Titel erstellen
    new_title = f"{original_ad.title} (Kopie)"

    # Alle Felder kopieren außer id, impressions, clicks, created_at, updated_at
    new_ad = SimpleAd(
        title=new_title,
        description=original_ad.description,
        image=original_ad.image,
        icon=original_ad.icon,
        video_url=original_ad.video_url,
        button_text=original_ad.button_text,
        target_url=original_ad.target_url,
        open_in_new_tab=original_ad.open_in_new_tab,
        template_style=original_ad.template_style,
        color_scheme=original_ad.color_scheme,
        custom_color=original_ad.custom_color,
        animation=original_ad.animation,
        badge=original_ad.badge,
        badge_custom_text=original_ad.badge_custom_text,
        start_date=original_ad.start_date,
        end_date=original_ad.end_date,
        countdown_enabled=original_ad.countdown_enabled,
        countdown_text=original_ad.countdown_text,
        target_audience=original_ad.target_audience,
        app_filter=original_ad.app_filter,
        exclude_apps=original_ad.exclude_apps,
        variant_name=original_ad.variant_name,
        ab_test_group=original_ad.ab_test_group,
        is_active=False,  # Kopie standardmäßig inaktiv
        weight=original_ad.weight,
    )
    new_ad.save()

    # M2M-Felder kopieren (falls vorhanden)
    if hasattr(original_ad, 'exclude_zones') and original_ad.exclude_zones.exists():
        new_ad.exclude_zones.set(original_ad.exclude_zones.all())

    messages.success(request, f'Anzeige "{original_ad.title}" wurde dupliziert! Die Kopie ist standardmäßig deaktiviert.')
    return redirect('loomads:simple_ad_edit', ad_id=new_ad.id)
