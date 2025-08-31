from django import template
from core.views import _get_available_apps

register = template.Library()

@register.simple_tag
def get_public_apps():
    """Gibt die verfügbaren Apps für nicht angemeldete Benutzer zurück"""
    return _get_available_apps()

@register.filter
def get_item(dictionary, key):
    """Hilfsfunktion um auf Dictionary-Elemente in Templates zuzugreifen"""
    return dictionary.get(key)