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


@register.filter
def split_feature_title(feature):
    """Gibt den Titel eines Features zurück (vor dem ' - ')"""
    if ' - ' in feature:
        return feature.split(' - ', 1)[0]
    return feature


@register.filter
def split_feature_desc(feature):
    """Gibt die Beschreibung eines Features zurück (nach dem ' - ')"""
    if ' - ' in feature:
        return feature.split(' - ', 1)[1]
    return ''  # Leerer String wenn kein " - " vorhanden


@register.filter
def has_feature_desc(feature):
    """Prüft ob ein Feature eine Beschreibung hat (enthält ' - ')"""
    return ' - ' in feature