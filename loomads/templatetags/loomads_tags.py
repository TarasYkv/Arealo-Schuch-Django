from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, F
from datetime import timedelta
import random
import json
import uuid

from ..models import AdZone, Advertisement, AdImpression, AdClick, AdTargeting, LoomAdsSettings

register = template.Library()


@register.inclusion_tag('loomads/tags/ad_zone.html', takes_context=True)
def show_ad_zone(context, zone_code, css_class='', style='', fallback=''):
    """
    Template Tag zum Anzeigen einer Werbezone
    
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
    
    context_data = {
        'zone': zone,
        'zone_code': zone_code,
        'api_url': request.build_absolute_uri(reverse('loomads:get_ad_for_zone', args=[zone_code])),
        'track_url': request.build_absolute_uri(reverse('loomads:track_click', args=[str(uuid.uuid4())])),
        'css_class': css_class,
        'style': style,
        'fallback': fallback,
        'width': zone.width,
        'height': zone.height,
        'zone_type': zone.zone_type,
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
    
    placeholder_html = '<div id="loomads-zone-{}" class="loomads-zone" style="width: {}px; height: {}px; background: #f8f9fa; border: 1px dashed #dee2e6; display: flex; align-items: center; justify-content: center; color: #6c757d; font-size: 12px; display: none;">Werbung wird geladen...</div>'.format(
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
        margin: 10px 0;
        text-align: center;
        position: relative;
    }
    
    .loomads-link {
        text-decoration: none;
        display: block;
    }
    
    .loomads-image {
        max-width: 100%;
        height: auto;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.2s ease;
    }
    
    .loomads-image:hover {
        transform: scale(1.02);
    }
    
    .loomads-text {
        display: block;
        padding: 15px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-decoration: none;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        transition: transform 0.2s ease;
    }
    
    .loomads-text:hover {
        transform: translateY(-2px);
        color: white;
        text-decoration: none;
    }
    
    .loomads-text h4 {
        margin: 0 0 8px 0;
        font-size: 16px;
        font-weight: 600;
    }
    
    .loomads-text p {
        margin: 0;
        font-size: 14px;
        opacity: 0.9;
    }
    
    .loomads-html {
        cursor: pointer;
    }
    
    .loomads-video {
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .loomads-zone {
            margin: 5px 0;
        }
        
        .loomads-text {
            padding: 12px;
        }
        
        .loomads-text h4 {
            font-size: 14px;
        }
        
        .loomads-text p {
            font-size: 12px;
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
        'track_url': request.build_absolute_uri(reverse('loomads:track_click', args=[str(uuid.uuid4())])),
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
        'track_url': request.build_absolute_uri(reverse('loomads:track_click', args=[str(uuid.uuid4())])),
        'css_class': css_class,
        'style': style,
        'width': zone.width,
        'height': zone.height,
        'popup_delay': zone.popup_delay,
    }