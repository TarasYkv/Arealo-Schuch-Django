import re
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Sum

from .models import (
    LinkLoomPage, LinkLoomIcon, LinkLoomButton, LinkLoomClick,
    PLATFORM_CHOICES, FA_ICONS, RESERVED_SLUGS
)


def anonymize_ip(ip):
    """Anonymisiert IP-Adressen für DSGVO-Konformität."""
    if not ip:
        return None
    if ':' in ip:  # IPv6
        parts = ip.split(':')
        return ':'.join(parts[:4] + ['0', '0', '0', '0'])
    else:  # IPv4
        parts = ip.split('.')
        return '.'.join(parts[:2] + ['0', '0'])


def get_client_ip(request):
    """Ermittelt die Client-IP-Adresse."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================
# Public Views (ohne Login)
# ============================================

def public_page_view(request, slug):
    """
    Zeigt die öffentliche LinkLoom-Seite für einen Slug.
    Falls der Slug nicht existiert, zeige eine "Slug verfügbar" Seite.
    """
    try:
        page = LinkLoomPage.objects.get(slug=slug, is_active=True)
    except LinkLoomPage.DoesNotExist:
        # Slug existiert nicht - zeige "Slug verfügbar" Seite
        return render(request, 'linkloom/slug_available.html', {
            'slug': slug,
        })

    icons = page.icons.filter(is_active=True).order_by('sort_order')
    buttons = page.buttons.filter(is_active=True).order_by('sort_order')

    context = {
        'page': page,
        'icons': icons,
        'buttons': buttons,
    }
    return render(request, 'linkloom/public_page.html', context)


def page_impressum(request, slug):
    """
    Zeigt das Impressum einer LinkLoom-Seite.
    """
    page = get_object_or_404(LinkLoomPage, slug=slug, is_active=True)

    if not page.custom_impressum:
        # Kein eigenes Impressum - zur Hauptseite weiterleiten
        return redirect('linkloom_public', slug=slug)

    context = {
        'page': page,
    }
    return render(request, 'linkloom/impressum.html', context)


def button_click(request, slug, button_id):
    """
    Trackt einen Button-Klick und leitet zur Ziel-URL weiter.
    """
    page = get_object_or_404(LinkLoomPage, slug=slug, is_active=True)
    button = get_object_or_404(LinkLoomButton, id=button_id, page=page, is_active=True)

    # Click tracken
    client_ip = get_client_ip(request)
    LinkLoomClick.objects.create(
        button=button,
        ip_address=anonymize_ip(client_ip),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referer=request.META.get('HTTP_REFERER', '')[:200] if request.META.get('HTTP_REFERER') else ''
    )

    # Click-Counter erhöhen
    button.click_count += 1
    button.last_clicked = timezone.now()
    button.save(update_fields=['click_count', 'last_clicked'])

    return redirect(button.url)


# ============================================
# Dashboard Views (Login erforderlich)
# ============================================

@login_required
def dashboard(request):
    """
    Dashboard zum Bearbeiten der eigenen LinkLoom-Seite.
    """
    # Seite des Users laden oder None
    try:
        page = request.user.linkloom_page
    except LinkLoomPage.DoesNotExist:
        page = None

    # Icons und Buttons laden falls Seite existiert
    icons = []
    buttons = []
    if page:
        icons = list(page.icons.order_by('sort_order').values(
            'id', 'platform', 'url', 'sort_order', 'is_active'
        ))
        buttons = list(page.buttons.order_by('sort_order').values(
            'id', 'title', 'url', 'description', 'sort_order', 'is_active', 'click_count'
        ))

    context = {
        'page': page,
        'icons_json': json.dumps(icons),
        'buttons_json': json.dumps(buttons),
        'platform_choices': PLATFORM_CHOICES,
        'fa_icons': FA_ICONS,
    }
    return render(request, 'linkloom/dashboard.html', context)


@login_required
@require_GET
def check_slug_availability(request):
    """
    Prüft ob ein Slug verfügbar ist.
    GET /linkloom/api/check-slug/?slug=xxx
    """
    slug = request.GET.get('slug', '').lower().strip()

    if not slug:
        return JsonResponse({
            'available': False,
            'reason': 'Slug darf nicht leer sein'
        })

    if len(slug) < 3:
        return JsonResponse({
            'available': False,
            'reason': 'Mindestens 3 Zeichen erforderlich'
        })

    if len(slug) > 50:
        return JsonResponse({
            'available': False,
            'reason': 'Maximal 50 Zeichen erlaubt'
        })

    if slug in RESERVED_SLUGS:
        return JsonResponse({
            'available': False,
            'reason': 'Dieser Name ist reserviert'
        })

    if not re.match(r'^[a-z0-9-]+$', slug):
        return JsonResponse({
            'available': False,
            'reason': 'Nur Kleinbuchstaben, Zahlen und Bindestriche erlaubt'
        })

    if slug.startswith('-') or slug.endswith('-'):
        return JsonResponse({
            'available': False,
            'reason': 'Darf nicht mit Bindestrich beginnen oder enden'
        })

    # Prüfen ob bereits vergeben (außer für den aktuellen User)
    exists = LinkLoomPage.objects.filter(slug=slug).exclude(user=request.user).exists()

    if exists:
        return JsonResponse({
            'available': False,
            'reason': 'Bereits vergeben'
        })

    return JsonResponse({
        'available': True,
        'slug': slug
    })


@login_required
@require_POST
def save_page(request):
    """
    Speichert die Seitenkonfiguration.
    POST /linkloom/api/save/
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})

    slug = data.get('slug', '').lower().strip()

    # Slug validieren
    if not slug or len(slug) < 3:
        return JsonResponse({'success': False, 'error': 'Slug muss mindestens 3 Zeichen haben'})

    if slug in RESERVED_SLUGS:
        return JsonResponse({'success': False, 'error': 'Dieser Name ist reserviert'})

    if not re.match(r'^[a-z0-9-]+$', slug):
        return JsonResponse({'success': False, 'error': 'Ungültiger Slug'})

    # Prüfen ob Slug bereits vergeben
    if LinkLoomPage.objects.filter(slug=slug).exclude(user=request.user).exists():
        return JsonResponse({'success': False, 'error': 'Slug bereits vergeben'})

    # Seite erstellen oder aktualisieren
    page, created = LinkLoomPage.objects.get_or_create(
        user=request.user,
        defaults={'slug': slug}
    )

    # Felder aktualisieren
    page.slug = slug
    page.profile_description = data.get('profile_description', '')[:500]
    page.background_color = data.get('background_color', '#ffffff')[:7]
    page.button_color = data.get('button_color', '#000000')[:7]
    page.button_text_color = data.get('button_text_color', '#ffffff')[:7]
    page.profile_text_color = data.get('profile_text_color', '#333333')[:7]
    page.custom_impressum = data.get('custom_impressum', '')
    page.show_affiliate_disclaimer = data.get('show_affiliate_disclaimer', False)
    page.affiliate_disclaimer_text = data.get('affiliate_disclaimer_text', '')
    page.is_active = data.get('is_active', True)

    page.save()

    return JsonResponse({
        'success': True,
        'created': created,
        'slug': page.slug,
        'url': f'/l/{page.slug}/'
    })


@login_required
@require_POST
def upload_image(request):
    """
    Lädt ein Profilbild hoch.
    POST /linkloom/api/upload-image/
    """
    if 'image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Kein Bild hochgeladen'})

    try:
        page = request.user.linkloom_page
    except LinkLoomPage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bitte erst eine Seite erstellen'})

    image = request.FILES['image']

    # Validierung
    if image.size > 5 * 1024 * 1024:  # 5MB
        return JsonResponse({'success': False, 'error': 'Bild darf maximal 5MB groß sein'})

    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if image.content_type not in allowed_types:
        return JsonResponse({'success': False, 'error': 'Nur JPEG, PNG, GIF und WebP erlaubt'})

    # Altes Bild löschen
    if page.profile_picture:
        page.profile_picture.delete(save=False)

    page.profile_picture = image
    page.save(update_fields=['profile_picture'])

    return JsonResponse({
        'success': True,
        'url': page.profile_picture.url
    })


@login_required
@require_POST
def delete_page(request):
    """
    Löscht die LinkLoom-Seite des Users komplett.
    POST /linkloom/api/delete/
    """
    try:
        page = request.user.linkloom_page
    except LinkLoomPage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Keine Seite vorhanden'})

    # Profilbild löschen falls vorhanden
    if page.profile_picture:
        page.profile_picture.delete(save=False)

    # Seite löschen (Buttons, Icons, Clicks werden durch CASCADE gelöscht)
    page.delete()

    return JsonResponse({
        'success': True,
        'message': 'Seite erfolgreich gelöscht'
    })


# ============================================
# Icon API Endpoints
# ============================================

@login_required
@require_POST
def icon_add(request):
    """
    Fügt ein neues Social Icon hinzu.
    POST /linkloom/api/icon/add/
    """
    try:
        page = request.user.linkloom_page
    except LinkLoomPage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bitte erst eine Seite erstellen'})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})

    platform = data.get('platform', '')
    url = data.get('url', '')

    # Validierung
    valid_platforms = [p[0] for p in PLATFORM_CHOICES]
    if platform not in valid_platforms:
        return JsonResponse({'success': False, 'error': 'Ungültige Plattform'})

    if not url:
        return JsonResponse({'success': False, 'error': 'URL ist erforderlich'})

    # Maximale Sortierung ermitteln
    max_order = page.icons.order_by('-sort_order').values_list('sort_order', flat=True).first() or 0

    icon = LinkLoomIcon.objects.create(
        page=page,
        platform=platform,
        url=url,
        sort_order=max_order + 1
    )

    return JsonResponse({
        'success': True,
        'icon': {
            'id': icon.id,
            'platform': icon.platform,
            'platform_display': icon.get_platform_display(),
            'url': icon.url,
            'fa_icon_class': icon.fa_icon_class,
            'sort_order': icon.sort_order,
            'is_active': icon.is_active
        }
    })


@login_required
@require_POST
def icon_delete(request, icon_id):
    """
    Löscht ein Social Icon.
    POST /linkloom/api/icon/<id>/delete/
    """
    try:
        page = request.user.linkloom_page
        icon = page.icons.get(id=icon_id)
        icon.delete()
        return JsonResponse({'success': True})
    except (LinkLoomPage.DoesNotExist, LinkLoomIcon.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Icon nicht gefunden'})


@login_required
@require_POST
def icon_toggle(request, icon_id):
    """
    Aktiviert/deaktiviert ein Social Icon.
    POST /linkloom/api/icon/<id>/toggle/
    """
    try:
        page = request.user.linkloom_page
        icon = page.icons.get(id=icon_id)
        icon.is_active = not icon.is_active
        icon.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'is_active': icon.is_active})
    except (LinkLoomPage.DoesNotExist, LinkLoomIcon.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Icon nicht gefunden'})


# ============================================
# Button API Endpoints
# ============================================

@login_required
@require_POST
def button_add(request):
    """
    Fügt einen neuen Button hinzu.
    POST /linkloom/api/button/add/
    """
    try:
        page = request.user.linkloom_page
    except LinkLoomPage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bitte erst eine Seite erstellen'})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})

    title = data.get('title', '').strip()
    url = data.get('url', '').strip()
    description = data.get('description', '').strip()

    if not title:
        return JsonResponse({'success': False, 'error': 'Titel ist erforderlich'})

    if not url:
        return JsonResponse({'success': False, 'error': 'URL ist erforderlich'})

    # Maximale Sortierung ermitteln
    max_order = page.buttons.order_by('-sort_order').values_list('sort_order', flat=True).first() or 0

    button = LinkLoomButton.objects.create(
        page=page,
        title=title[:100],
        url=url,
        description=description[:200],
        sort_order=max_order + 1
    )

    return JsonResponse({
        'success': True,
        'button': {
            'id': button.id,
            'title': button.title,
            'url': button.url,
            'description': button.description,
            'sort_order': button.sort_order,
            'is_active': button.is_active,
            'click_count': button.click_count
        }
    })


@login_required
@require_POST
def button_update(request, button_id):
    """
    Aktualisiert einen Button.
    POST /linkloom/api/button/<id>/update/
    """
    try:
        page = request.user.linkloom_page
        button = page.buttons.get(id=button_id)
    except (LinkLoomPage.DoesNotExist, LinkLoomButton.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Button nicht gefunden'})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})

    if 'title' in data:
        button.title = data['title'][:100]
    if 'url' in data:
        button.url = data['url']
    if 'description' in data:
        button.description = data['description'][:200]
    if 'sort_order' in data:
        button.sort_order = data['sort_order']

    button.save()

    return JsonResponse({
        'success': True,
        'button': {
            'id': button.id,
            'title': button.title,
            'url': button.url,
            'description': button.description,
            'sort_order': button.sort_order,
            'is_active': button.is_active,
            'click_count': button.click_count
        }
    })


@login_required
@require_POST
def button_delete(request, button_id):
    """
    Löscht einen Button.
    POST /linkloom/api/button/<id>/delete/
    """
    try:
        page = request.user.linkloom_page
        button = page.buttons.get(id=button_id)
        button.delete()
        return JsonResponse({'success': True})
    except (LinkLoomPage.DoesNotExist, LinkLoomButton.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Button nicht gefunden'})


@login_required
@require_POST
def button_toggle(request, button_id):
    """
    Aktiviert/deaktiviert einen Button.
    POST /linkloom/api/button/<id>/toggle/
    """
    try:
        page = request.user.linkloom_page
        button = page.buttons.get(id=button_id)
        button.is_active = not button.is_active
        button.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'is_active': button.is_active})
    except (LinkLoomPage.DoesNotExist, LinkLoomButton.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Button nicht gefunden'})


# ============================================
# Statistics
# ============================================

@login_required
@require_GET
def get_stats(request):
    """
    Liefert Statistiken für die Seite des Users.
    GET /linkloom/api/stats/
    """
    try:
        page = request.user.linkloom_page
    except LinkLoomPage.DoesNotExist:
        return JsonResponse({
            'success': True,
            'total_clicks': 0,
            'buttons': []
        })

    buttons_stats = list(page.buttons.values('id', 'title', 'click_count', 'last_clicked'))
    total_clicks = page.buttons.aggregate(total=Sum('click_count'))['total'] or 0

    return JsonResponse({
        'success': True,
        'total_clicks': total_clicks,
        'buttons': buttons_stats
    })
