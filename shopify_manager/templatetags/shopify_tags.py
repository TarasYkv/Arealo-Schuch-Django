from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Template-Filter um auf Dictionary-Werte mit einer Variable als Key zuzugreifen.
    Verwendung: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
