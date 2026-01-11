"""
Template-Tags für Thumbnail-Generierung

Verwendung in Templates:
{% load thumbnail_tags %}

<!-- Thumbnail URL -->
<img src="{% thumbnail image_field 'medium' %}">

<!-- Mit Fallback -->
<img src="{% thumbnail image_field 'medium' as thumb_url %}{{ thumb_url|default:image_field.url }}">
"""

from django import template
from django.utils.safestring import mark_safe
from core.thumbnails import get_or_create_thumbnail

register = template.Library()


@register.simple_tag
def thumbnail(image_field, size='medium'):
    """
    Gibt die URL eines Thumbnails zurück.

    Verwendung:
        {% thumbnail obj.image 'medium' %}
        {% thumbnail obj.image 'small' %}
        {% thumbnail obj.image 'large' %}

    Args:
        image_field: Django ImageField
        size: 'small' (200px), 'medium' (400px), 'large' (800px)

    Returns:
        URL zum Thumbnail oder Original bei Fehler
    """
    if not image_field:
        return ''

    return get_or_create_thumbnail(image_field, size)


@register.simple_tag
def thumbnail_img(image_field, size='medium', alt='', css_class='', style=''):
    """
    Generiert ein komplettes img-Tag mit Thumbnail und lazy loading.

    Verwendung:
        {% thumbnail_img obj.image 'medium' alt='Beschreibung' css_class='img-fluid' %}

    Args:
        image_field: Django ImageField
        size: Thumbnail-Größe
        alt: Alt-Text
        css_class: CSS-Klassen
        style: Inline-Styles

    Returns:
        Komplettes img-Tag als SafeString
    """
    if not image_field:
        return ''

    url = get_or_create_thumbnail(image_field, size)

    attrs = [f'src="{url}"', 'loading="lazy"']

    if alt:
        attrs.append(f'alt="{alt}"')
    if css_class:
        attrs.append(f'class="{css_class}"')
    if style:
        attrs.append(f'style="{style}"')

    return mark_safe(f'<img {" ".join(attrs)}>')
