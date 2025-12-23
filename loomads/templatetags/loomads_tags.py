from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, F
from datetime import timedelta
import random
import json
import uuid

from ..models import AdZone, Advertisement, AdImpression, AdClick, AdTargeting, LoomAdsSettings, SimpleAd

register = template.Library()


@register.inclusion_tag('loomads/tags/multi_ad_zone.html', takes_context=True)
def show_multi_ad_zone(context, zone_code, ad_count=3, css_class='', style='', fallback=''):
    """
    Template Tag für Mehrfachanzeigen in einer Zone

    Verwendung:
    {% load loomads_tags %}
    {% show_multi_ad_zone 'header_main' ad_count=3 css_class='my-ads-container' %}
    """
    request = context.get('request')
    if not request:
        return {
            'zone_code': zone_code,
            'error': 'Request context not available',
            'fallback': fallback
        }

    # === PRIORITÄT 1: SimpleAds (neu, vereinfacht) ===
    user = getattr(request, 'user', None)
    current_app = request.resolver_match.app_name if request.resolver_match else None
    simple_ad = SimpleAd.get_random_ad(zone_code=zone_code, user=user, app_name=current_app)
    if simple_ad:
        # Impression zählen
        simple_ad.record_impression()
        # HTML direkt rendern mit zone_code für format-abhängiges Rendering
        simple_ad_html = _render_simple_ad(simple_ad, css_class, zone_code)
        return {
            'zone_code': zone_code,
            'simple_ad_html': simple_ad_html,
            'css_class': css_class,
        }

    # === PRIORITÄT 2: Legacy Multi-Ad Zone System ===
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
    except AdZone.DoesNotExist:
        return {
            'zone_code': zone_code,
            'error': 'Zone "{}" not found'.format(zone_code),
            'fallback': fallback
        }
    
    # App-spezifische Zone-Kontrolle prüfen
    current_app = request.resolver_match.app_name if request.resolver_match else None
    settings = LoomAdsSettings.get_settings()
    
    # Überprüfe ob Zone für diese App aktiviert ist
    zone_type = zone.zone_type
    if not settings.is_zone_enabled(zone_type, current_app):
        return {
            'zone_code': zone_code,
            'error': 'Zone "{}" disabled for app "{}"'.format(zone_type, current_app or 'default'),
            'fallback': fallback
        }
    
    # App-Beschränkung prüfen
    if zone.app_restriction:
        if current_app != zone.app_restriction:
            return {
                'zone_code': zone_code,
                'error': 'Zone restricted to app "{}"'.format(zone.app_restriction),
                'fallback': fallback
            }
    
    # Generiere eine eindeutige ID für diese Zone-Instanz
    random_id = str(uuid.uuid4())[:8]
    
    context_data = {
        'zone': zone,
        'zone_code': zone_code,
        'ad_count': min(max(1, ad_count), 10),  # Limit zwischen 1-10
        'api_url': request.build_absolute_uri(reverse('loomads:get_multiple_ads_for_zone', args=[zone_code, ad_count])),
        'track_url': request.build_absolute_uri('/loomads/api/track/click/AD_ID_PLACEHOLDER/'),
        'css_class': css_class,
        'style': style,
        'fallback': fallback,
        'width': zone.width,
        'height': zone.height,
        'zone_type': zone.zone_type,
        'random_id': random_id,
    }
    
    return context_data


@register.inclusion_tag('loomads/tags/ad_zone.html', takes_context=True)
def show_ad_zone(context, zone_code, css_class='', style='', fallback=''):
    """
    Template Tag zum Anzeigen einer Werbezone.

    VEREINFACHT: Prüft zuerst auf SimpleAds und zeigt diese direkt an.
    Nur wenn keine SimpleAds vorhanden sind, wird das Legacy-System verwendet.

    Verwendung:
    {% load loomads_tags %}
    {% show_ad_zone 'header_main' css_class='my-ad-banner' %}
    """
    request = context.get('request')
    if not request:
        return {
            'zone_code': zone_code,
            'error': 'Request context not available',
            'fallback': fallback
        }

    # === PRIORITÄT 1: SimpleAds (neu, vereinfacht) ===
    # Prüfe zuerst, ob aktive SimpleAds vorhanden sind
    user = getattr(request, 'user', None)
    current_app = request.resolver_match.app_name if request.resolver_match else None
    simple_ad = SimpleAd.get_random_ad(zone_code=zone_code, user=user, app_name=current_app)
    if simple_ad:
        # Impression zählen
        simple_ad.record_impression()
        # HTML direkt rendern mit zone_code für format-abhängiges Rendering
        simple_ad_html = _render_simple_ad(simple_ad, css_class, zone_code)
        return {
            'zone_code': zone_code,
            'simple_ad_html': simple_ad_html,
            'css_class': css_class,
        }

    # === PRIORITÄT 2: Legacy AdZone System ===
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
    except AdZone.DoesNotExist:
        # Keine Zone und keine SimpleAds → Fallback oder leer
        if fallback:
            return {
                'zone_code': zone_code,
                'error': 'Zone "{}" not found'.format(zone_code),
                'fallback': fallback
            }
        return {
            'zone_code': zone_code,
            'error': 'Zone "{}" not found and no SimpleAds available'.format(zone_code),
            'fallback': ''
        }

    # App-spezifische Zone-Kontrolle prüfen
    current_app = request.resolver_match.app_name if request.resolver_match else None
    settings = LoomAdsSettings.get_settings()

    # Überprüfe ob Zone für diese App aktiviert ist
    zone_type = zone.zone_type
    if not settings.is_zone_enabled(zone_type, current_app):
        return {
            'zone_code': zone_code,
            'error': 'Zone "{}" disabled for app "{}"'.format(zone_type, current_app or 'default'),
            'fallback': fallback
        }

    # App-Beschränkung prüfen
    if zone.app_restriction:
        if current_app != zone.app_restriction:
            return {
                'zone_code': zone_code,
                'error': 'Zone restricted to app "{}"'.format(zone.app_restriction),
                'fallback': fallback
            }

    # Generiere eine eindeutige ID für diese Zone-Instanz
    random_id = str(uuid.uuid4())[:8]

    context_data = {
        'zone': zone,
        'zone_code': zone_code,
        'api_url': request.build_absolute_uri(reverse('loomads:get_ad_for_zone', args=[zone_code])),
        'track_url': request.build_absolute_uri('/loomads/api/track/click/AD_ID_PLACEHOLDER/'),
        'css_class': css_class,
        'style': style,
        'fallback': fallback,
        'width': zone.width,
        'height': zone.height,
        'zone_type': zone.zone_type,
        'random_id': random_id,
    }

    return context_data


@register.simple_tag
def ad_stats(period_days=30):
    """
    Statistiken für Anzeigen abrufen
    
    Verwendung:
    {% ad_stats 30 as stats %}
    {{ stats.impressions }} Impressions, {{ stats.clicks }} Clicks
    """
    start_date = timezone.now() - timedelta(days=period_days)
    
    impressions = AdImpression.objects.filter(timestamp__gte=start_date).count()
    clicks = AdClick.objects.filter(timestamp__gte=start_date).count()
    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    
    return {
        'impressions': impressions,
        'clicks': clicks,
        'ctr': round(ctr, 2),
        'period_days': period_days
    }


@register.filter
def ad_ctr(advertisement):
    """
    Click-Through-Rate für eine Anzeige berechnen
    
    Verwendung:
    {{ ad|ad_ctr }}
    """
    if not advertisement or advertisement.impressions_count == 0:
        return 0
    return round((advertisement.clicks_count / advertisement.impressions_count * 100), 2)


@register.simple_tag(takes_context=True)
def ad_zone_placeholder(context, zone_code, width=None, height=None):
    """
    Platzhalter für eine Werbezone (während des Ladens)
    
    Verwendung:
    {% ad_zone_placeholder 'header_main' width=728 height=90 %}
    """
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
        width = width or zone.width
        height = height or zone.height
    except AdZone.DoesNotExist:
        width = width or 300
        height = height or 250
    
    placeholder_html = '<div id="loomads-zone-{}" class="loomads-zone" style="width: {}px; height: {}px; background: #f8f9fa; border: 1px dashed #dee2e6; display: flex; align-items: center; justify-content: center; color: #6c757d; font-size: 12px; display: none;">Hier kann Deine Werbung stehen!</div>'.format(
        zone_code, width, height
    )
    
    return mark_safe(placeholder_html)


@register.simple_tag
def loomads_css():
    """
    Basis-CSS für LoomAds
    
    Verwendung:
    {% loomads_css %}
    """
    css = """
    <style>
    .loomads-zone {
        margin: 0;
        padding: 0;
        text-align: center !important;
        position: relative;
        display: block !important;
        width: 100% !important;
        overflow: hidden;
        clear: both;
    }
    
    .loomads-zone > * {
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    /* Kompakte Header Anzeigen */
    .loomads-header {
        margin: 0 0 1rem 0 !important;
        height: auto !important;
        min-height: auto !important;
        border-radius: 8px;
        overflow: hidden;
    }
    
    .loomads-header .loomads-html > div {
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    
    /* Sidebar Anzeigen ohne extra Margin */
    .loomads-sidebar {
        margin: 0 !important;
        width: 100% !important;
    }
    
    /* Content Cards kompakt */
    .loomads-content_card {
        margin: 0 0 1rem 0 !important;
    }
    
    /* Notification Banner schlank */
    .loomads-notification {
        margin: 0 0 0.5rem 0 !important;
        height: auto !important;
        min-height: auto !important;
    }
    
    .loomads-link {
        text-decoration: none;
        display: block;
        width: 100%;
    }
    
    .loomads-image {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 0 auto;
    }
    
    .loomads-text {
        display: block;
        padding: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-decoration: none;
        border-radius: 6px;
        transition: transform 0.2s ease;
    }
    
    .loomads-text:hover {
        transform: translateY(-1px);
        color: white;
        text-decoration: none;
    }
    
    .loomads-text h4 {
        margin: 0 0 5px 0;
        font-size: 14px;
        font-weight: 600;
    }
    
    .loomads-text p {
        margin: 0;
        font-size: 12px;
        opacity: 0.9;
    }
    
    .loomads-html {
        cursor: pointer;
        width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
        overflow: hidden;
    }
    
    .loomads-html > div {
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    .loomads-video {
        max-width: 100%;
        height: auto;
    }
    
    /* Videos App spezifisch */
    .videos-page .loomads-zone {
        margin-bottom: 1rem;
    }
    
    /* StreamRec App spezifisch */
    .streamrec-page .loomads-zone {
        margin-bottom: 0.75rem;
    }
    
    /* PromptPro App spezifisch */
    .promptpro-page .loomads-zone {
        margin-bottom: 0.5rem;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .loomads-zone {
            margin: 0 0 0.5rem 0;
        }
        
        .loomads-text {
            padding: 8px;
        }
        
        .loomads-text h4 {
            font-size: 13px;
        }
        
        .loomads-text p {
            font-size: 11px;
        }
        
        .loomads-html > div {
            padding: 6px 8px !important;
            font-size: 12px !important;
        }
        
        .loomads-header {
            margin-bottom: 0.75rem !important;
        }
    }
    
    @media (max-width: 480px) {
        .loomads-html > div {
            padding: 4px 6px !important;
            font-size: 11px !important;
        }
        
        .loomads-header {
            margin-bottom: 0.5rem !important;
        }
    }
    </style>
    """
    
    return mark_safe(css)


@register.inclusion_tag('loomads/tags/ad_modal.html', takes_context=True)
def show_ad_modal(context, zone_code, delay=5000, show_close=True):
    """
    Modal-Anzeige nach bestimmter Zeit anzeigen
    
    Verwendung:
    {% show_ad_modal 'popup_main' delay=3000 %}
    """
    request = context.get('request')
    if not request:
        return {'error': 'No request context'}
    
    # App-spezifische Modal-Kontrolle prüfen
    current_app = request.resolver_match.app_name if request.resolver_match else None
    settings = LoomAdsSettings.get_settings()
    
    # Überprüfe ob Modal-Zone für diese App aktiviert ist
    if not settings.is_zone_enabled('modal', current_app):
        return {'error': 'Modal disabled for app "{}"'.format(current_app or 'default')}
    
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True, zone_type='modal')
    except AdZone.DoesNotExist:
        return {'error': 'Modal zone "{}" not found'.format(zone_code)}
    
    return {
        'zone': zone,
        'zone_code': zone_code,
        'delay': delay,
        'show_close': show_close,
        'api_url': request.build_absolute_uri(reverse('loomads:get_ad_for_zone', args=[zone_code])),
        'track_url': request.build_absolute_uri('/loomads/api/track/click/AD_ID_PLACEHOLDER/'),
    }


@register.inclusion_tag('loomads/tags/video_popup_zone.html', takes_context=True)
def show_video_popup(context, zone_code, css_class='', style=''):
    """
    Video-Popup-Anzeige unten rechts mit zeitgesteuertem Autoplay
    
    Verwendung:
    {% load loomads_tags %}
    {% show_video_popup 'video_popup_main' %}
    """
    request = context.get('request')
    if not request:
        return {
            'zone_code': zone_code,
            'error': 'Request context not available'
        }
    
    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True, zone_type='video_popup')
    except AdZone.DoesNotExist:
        return {
            'zone_code': zone_code,
            'error': 'Video popup zone "{}" not found'.format(zone_code)
        }
    
    # App-spezifische Zone-Kontrolle prüfen
    current_app = request.resolver_match.app_name if request.resolver_match else None
    settings = LoomAdsSettings.get_settings()
    
    # App-Beschränkung prüfen
    if zone.app_restriction:
        if current_app != zone.app_restriction:
            return {
                'zone_code': zone_code,
                'error': 'Zone restricted to app "{}"'.format(zone.app_restriction)
            }
    
    return {
        'zone': zone,
        'zone_code': zone_code,
        'api_url': request.build_absolute_uri(reverse('loomads:get_ad_for_zone', args=[zone_code])),
        'track_url': request.build_absolute_uri('/loomads/api/track/click/AD_ID_PLACEHOLDER/'),
        'css_class': css_class,
        'style': style,
        'width': zone.width,
        'height': zone.height,
        'popup_delay': zone.popup_delay,
    }


@register.inclusion_tag('loomads/tags/ad_card_zone.html', takes_context=True)
def show_ad_card_zone(context, zone_code, css_class='', style='', fallback=''):
    """
    Template Tag zum Anzeigen einer Werbezone als Card

    Verwendung:
    {% load loomads_tags %}
    {% show_ad_card_zone 'loomline_tasks_card' css_class='task-ad-card' %}
    """
    request = context.get('request')
    if not request:
        return {
            'zone_code': zone_code,
            'error': 'Request context not available',
            'fallback': fallback
        }

    try:
        zone = AdZone.objects.get(code=zone_code, is_active=True)
    except AdZone.DoesNotExist:
        return {
            'zone_code': zone_code,
            'error': 'Zone "{}" not found'.format(zone_code),
            'fallback': fallback
        }

    # App-spezifische Zone-Kontrolle prüfen
    current_app = request.resolver_match.app_name if request.resolver_match else None
    settings = LoomAdsSettings.get_settings()

    # Überprüfe ob Zone für diese App aktiviert ist
    zone_type = zone.zone_type
    if not settings.is_zone_enabled(zone_type, current_app):
        return {
            'zone_code': zone_code,
            'error': 'Zone "{}" disabled for app "{}"'.format(zone_type, current_app or 'default'),
            'fallback': fallback
        }

    # App-Beschränkung prüfen
    if zone.app_restriction:
        if current_app != zone.app_restriction:
            return {
                'zone_code': zone_code,
                'error': 'Zone restricted to app "{}"'.format(zone.app_restriction),
                'fallback': fallback
            }

    # Generiere eine eindeutige ID für diese Zone-Instanz
    random_id = str(uuid.uuid4())[:8]

    context_data = {
        'zone': zone,
        'zone_code': zone_code,
        'api_url': request.build_absolute_uri(reverse('loomads:get_ad_for_zone', args=[zone_code])),
        'track_url': request.build_absolute_uri('/loomads/api/track/click/AD_ID_PLACEHOLDER/'),
        'css_class': css_class,
        'style': style,
        'fallback': fallback,
        'width': zone.width,
        'height': zone.height,
        'zone_type': zone.zone_type,
        'random_id': random_id,
    }

    return context_data


@register.simple_tag
def get_ad_apps(advertisement):
    """
    Ermittelt in welchen Apps eine Anzeige ausgespielt wird
    
    Verwendung:
    {% get_ad_apps ad as app_info %}
    """
    from django.urls import get_resolver
    from django.conf import settings
    
    # Alle verfügbaren Apps ermitteln
    resolver = get_resolver()
    all_apps = []
    
    # Standard Apps sammeln
    app_names = {
        'accounts': 'Accounts',
        'loomads': 'LoomAds', 
        'streamrec': 'StreamRec',
        'videos': 'Videos',
        'shopify': 'Shopify Manager',
        'makeads': 'MakeAds',
        'payments': 'Payments',
        'promptpro': 'PromptPro',
    }
    
    # LoomAds Einstellungen abrufen
    settings_obj = LoomAdsSettings.get_settings()
    
    # Für jede Zone der Anzeige prüfen, in welchen Apps sie aktiv ist
    active_apps = set()
    restricted_apps = set()
    
    for zone in advertisement.zones.all():
        zone_type = zone.zone_type
        
        # Prüfe globale Aktivierung der Zone
        if not settings_obj.is_zone_enabled(zone_type):
            continue
            
        # Wenn Zone app-spezifisch beschränkt ist
        if zone.app_restriction:
            if zone.app_restriction in app_names:
                restricted_apps.add(app_names[zone.app_restriction])
        else:
            # Zone ist für alle Apps verfügbar (außer explizit deaktivierte)
            for app_key, app_name in app_names.items():
                if settings_obj.is_zone_enabled(zone_type, app_key):
                    active_apps.add(app_name)
    
    # Falls app-spezifische Beschränkungen existieren, diese verwenden
    if restricted_apps:
        active_apps = restricted_apps
    
    # Falls keine Apps gefunden wurden, Standard-Apps verwenden
    if not active_apps:
        active_apps = {'Alle Apps (Standard)'}
    
    return {
        'apps': sorted(list(active_apps)),
        'count': len(active_apps),
        'is_restricted': bool(restricted_apps)
    }


@register.filter
def get_item(dictionary, key):
    """
    Dictionary-Zugriff im Template

    Verwendung:
    {{ dict|get_item:key }}

    Beispiel:
    {{ app_zone_counts|get_item:app_code }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


# =============================================================================
# SIMPLE ADS - Vereinfachte Ad-Tags
# =============================================================================

@register.simple_tag(takes_context=True)
def show_simple_ad(context, zone_code='', css_class='', fallback=''):
    """
    Einfacher Tag für SimpleAds - zeigt eine zufällige aktive Anzeige an.

    Verwendung:
    {% load loomads_tags %}
    {% show_simple_ad 'header' css_class='mb-4' %}

    oder ohne Zone (zeigt irgendeine aktive Anzeige):
    {% show_simple_ad %}
    """
    request = context.get('request')

    # Hole eine zufällige aktive SimpleAd
    ad = SimpleAd.get_random_ad(zone_code=zone_code if zone_code else None)

    if not ad:
        if fallback:
            return mark_safe(f'<div class="simple-ad-fallback {css_class}">{fallback}</div>')
        return ''

    # Impression zählen
    ad.record_impression()

    # HTML generieren
    html = _render_simple_ad(ad, css_class)

    return mark_safe(html)


def _render_simple_ad(ad, extra_css_class='', zone_code=''):
    """
    Generiert responsives HTML für eine SimpleAd.
    Alle Styles sind inline für maximale Kompatibilität.

    Zone-abhängiges Rendering:
    - header/banner: Breites horizontales Format
    - sidebar: Schmales vertikales Format
    - inline/content/default: Card-Format
    """
    color = ad.get_primary_color()
    style = ad.template_style
    target = '_blank' if ad.open_in_new_tab else '_self'

    # Zone-Typ aus zone_code ableiten
    zone_lower = zone_code.lower() if zone_code else ''
    if 'header' in zone_lower or 'banner' in zone_lower:
        zone_type = 'banner'
    elif 'sidebar' in zone_lower:
        zone_type = 'sidebar'
    else:
        zone_type = 'card'

    # Style-spezifische CSS
    styles = {
        'minimal': {
            'container': f'padding: 16px; border-left: 4px solid {color}; background: #f9fafb; border-radius: 0 8px 8px 0;',
            'text_color': '#1f2937',
            'desc_color': '#6b7280',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'card': {
            'container': f'padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e5e7eb; background: white;',
            'text_color': '#1f2937',
            'desc_color': '#6b7280',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'gradient': {
            'container': f'padding: 20px; border-radius: 12px; background: linear-gradient(135deg, {color}, {color}cc);',
            'text_color': 'white',
            'desc_color': 'rgba(255,255,255,0.9)',
            'btn_bg': 'white',
            'btn_color': color
        },
        'banner': {
            'container': f'padding: 16px 24px; border-radius: 8px; background: {color}12; border: 1px solid {color}30;',
            'text_color': '#1f2937',
            'desc_color': '#6b7280',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'highlight': {
            'container': f'padding: 20px; border-radius: 12px; background: {color}08; border: 2px solid {color};',
            'text_color': '#1f2937',
            'desc_color': '#6b7280',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'dark': {
            'container': 'padding: 20px; border-radius: 12px; background: #1f2937;',
            'text_color': 'white',
            'desc_color': 'rgba(255,255,255,0.8)',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'glass': {
            'container': f'padding: 20px; border-radius: 16px; background: rgba(255,255,255,0.25); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 8px 32px rgba(0,0,0,0.1);',
            'text_color': '#1f2937',
            'desc_color': '#4b5563',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'neon': {
            'container': f'padding: 20px; border-radius: 12px; background: #0f0f0f; border: 2px solid {color}; box-shadow: 0 0 20px {color}40, inset 0 0 20px {color}10;',
            'text_color': 'white',
            'desc_color': 'rgba(255,255,255,0.8)',
            'btn_bg': color,
            'btn_color': 'white'
        },
        'retro': {
            'container': f'padding: 20px; border-radius: 0; background: #fef3c7; border: 3px solid #92400e; box-shadow: 6px 6px 0 #92400e;',
            'text_color': '#78350f',
            'desc_color': '#92400e',
            'btn_bg': '#92400e',
            'btn_color': '#fef3c7'
        },
        'threed': {
            'container': f'padding: 20px; border-radius: 12px; background: linear-gradient(145deg, #ffffff, #e6e6e6); box-shadow: 8px 8px 16px #d1d1d1, -8px -8px 16px #ffffff;',
            'text_color': '#1f2937',
            'desc_color': '#6b7280',
            'btn_bg': color,
            'btn_color': 'white'
        }
    }

    s = styles.get(style, styles['card'])

    # Badge HTML
    badge_html = ''
    if ad.badge:
        badge_text = ad.badge_custom_text if ad.badge == 'custom' and ad.badge_custom_text else ad.badge.upper()
        badge_html = f'''
            <span style="position: absolute; top: 4px; right: 8px; background: #ef4444; color: white;
                         padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 700;
                         text-transform: uppercase; letter-spacing: 0.5px; box-shadow: 0 2px 8px rgba(239,68,68,0.4);
                         transform: rotate(12deg); z-index: 10;">
                {badge_text}
            </span>
        '''

    # Click-Tracking Script (einmalig pro Ad-ID)
    track_script = f'''
    <script>
    (function() {{
        var adLinks = document.querySelectorAll('[data-simple-ad-id="{ad.id}"]');
        adLinks.forEach(function(adLink) {{
            if (!adLink.dataset.tracked) {{
                adLink.dataset.tracked = 'true';
                adLink.addEventListener('click', function() {{
                    fetch('/loomads/api/simple-ad/track/{ad.id}/', {{
                        method: 'POST',
                        headers: {{'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''}}
                    }}).catch(function() {{}});
                }});
            }}
        }});
    }})();
    </script>
    '''

    # === BANNER FORMAT (horizontal, zentriert) ===
    if zone_type == 'banner':
        # Media für Banner
        media_html = ''
        if ad.video_url:
            media_html = f'''
                <video autoplay loop muted playsinline
                       style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px; flex-shrink: 0;">
                    <source src="{ad.video_url}" type="video/mp4">
                </video>
            '''
        elif ad.image:
            media_html = f'''
                <img src="{ad.image.url}" alt="{ad.title}"
                     style="width: 50px; height: 50px; object-fit: cover; border-radius: 8px; flex-shrink: 0;" />
            '''
        elif ad.icon:
            media_html = f'''
                <i class="bi {ad.icon}" style="font-size: 32px; color: {color}; flex-shrink: 0;"></i>
            '''

        html = f'''
        <div class="simple-ad-wrapper simple-ad-banner {extra_css_class}" style="width: 100%; display: flex; justify-content: center;">
            <div class="simple-ad-container" style="position: relative; {s['container']} font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; text-align: center;">
                {badge_html}
                <a href="{ad.target_url}" target="{target}" rel="noopener" data-simple-ad-id="{ad.id}"
                   style="display: inline-flex; align-items: center; gap: 16px; text-decoration: none;">
                    {media_html}
                    <div style="text-align: left;">
                        <h4 style="margin: 0; color: {s['text_color']}; font-size: 15px; font-weight: 600;">
                            {ad.title}
                        </h4>
                        {f'<p style="margin: 4px 0 0 0; color: {s["desc_color"]}; font-size: 13px;">{ad.description[:80]}</p>' if ad.description else ''}
                    </div>
                    <span style="flex-shrink: 0; background: {s['btn_bg']}; color: {s['btn_color']};
                                 padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 500;">
                        {ad.button_text}
                    </span>
                </a>
            </div>
        </div>
        {track_script}
        '''

    # === SIDEBAR FORMAT (vertikal, schmal) ===
    elif zone_type == 'sidebar':
        # Media für Sidebar
        media_html = ''
        if ad.video_url:
            media_html = f'''
                <video autoplay loop muted playsinline
                       style="width: 100%; height: 120px; object-fit: cover; border-radius: 8px; margin-bottom: 12px;">
                    <source src="{ad.video_url}" type="video/mp4">
                </video>
            '''
        elif ad.image:
            media_html = f'''
                <img src="{ad.image.url}" alt="{ad.title}"
                     style="width: 100%; height: 120px; object-fit: cover; border-radius: 8px; margin-bottom: 12px;" />
            '''
        elif ad.icon:
            media_html = f'''
                <div style="text-align: center; margin-bottom: 12px;">
                    <i class="bi {ad.icon}" style="font-size: 48px; color: {color};"></i>
                </div>
            '''

        html = f'''
        <div class="simple-ad-wrapper simple-ad-sidebar {extra_css_class}" style="width: 100%;">
            <div class="simple-ad-container" style="position: relative; {s['container']} font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 100%; text-align: center;">
                {badge_html}
                <a href="{ad.target_url}" target="{target}" rel="noopener" data-simple-ad-id="{ad.id}"
                   style="display: block; text-decoration: none;">
                    {media_html}
                    <h4 style="margin: 0 0 8px 0; color: {s['text_color']}; font-size: 15px; font-weight: 600; line-height: 1.3;">
                        {ad.title}
                    </h4>
                    {f'<p style="margin: 0 0 12px 0; color: {s["desc_color"]}; font-size: 13px; line-height: 1.4;">{ad.description[:100]}</p>' if ad.description else ''}
                    <span style="display: inline-block; background: {s['btn_bg']}; color: {s['btn_color']};
                                 padding: 10px 24px; border-radius: 6px; font-size: 13px; font-weight: 500;">
                        {ad.button_text}
                    </span>
                </a>
            </div>
        </div>
        {track_script}
        '''

    # === CARD FORMAT (Standard, flexibles Layout) ===
    else:
        # Media für Card
        media_html = ''
        if ad.video_url:
            media_html = f'''
                <video autoplay loop muted playsinline
                       style="width: 100%; max-width: 120px; height: auto; max-height: 80px;
                              object-fit: cover; border-radius: 8px; flex-shrink: 0;">
                    <source src="{ad.video_url}" type="video/mp4">
                </video>
            '''
        elif ad.image:
            media_html = f'''
                <img src="{ad.image.url}" alt="{ad.title}"
                     style="width: 100%; max-width: 120px; height: auto; max-height: 80px;
                            object-fit: cover; border-radius: 8px; flex-shrink: 0;" />
            '''
        elif ad.icon:
            media_html = f'''
                <div style="width: 60px; height: 60px; background: {color}15; border-radius: 12px;
                            display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <i class="bi {ad.icon}" style="font-size: 28px; color: {color};"></i>
                </div>
            '''

        # Description HTML
        desc_html = ''
        if ad.description:
            desc_html = f'''
                <p style="margin: 0 0 12px 0; color: {s['desc_color']}; font-size: 14px; line-height: 1.5;">
                    {ad.description}
                </p>
            '''

        html = f'''
        <div class="simple-ad-wrapper simple-ad-card {extra_css_class}" style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; min-height: inherit;">
            <div class="simple-ad-container" style="position: relative; {s['container']} font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; width: 100%; text-align: center;">
                {badge_html}
                <a href="{ad.target_url}" target="{target}" rel="noopener" data-simple-ad-id="{ad.id}"
                   style="display: flex; align-items: center; justify-content: center; gap: 16px; text-decoration: none; flex-wrap: wrap;">
                    {media_html}
                    <div style="flex: 1; min-width: 200px; text-align: left;">
                        <h4 style="margin: 0 0 8px 0; color: {s['text_color']}; font-size: 16px; font-weight: 600; line-height: 1.3;">
                            {ad.title}
                        </h4>
                        {desc_html}
                        <span style="display: inline-block; background: {s['btn_bg']}; color: {s['btn_color']};
                                     padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;">
                            {ad.button_text}
                        </span>
                    </div>
                </a>
            </div>
        </div>
        {track_script}
        '''

    return html