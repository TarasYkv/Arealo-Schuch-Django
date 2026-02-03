import re
from django import template
from django.utils.safestring import mark_safe
from ..models import AppInfo

register = template.Library()


def parse_app_description(description):
    """
    Parst die App-Beschreibung und extrahiert die Komponenten.

    Format in der Datenbank:
    "Das Problem: ... Die Workloom-Lösung: ...
    So funktioniert's:
    1️⃣ Schritt 1
    2️⃣ Schritt 2
    3️⃣ Schritt 3
    Tagline am Ende!"

    Returns:
        dict mit keys: problem, solution, steps, tagline
    """
    if not description:
        return {'raw': '', 'problem': '', 'solution': '', 'steps': [], 'tagline': ''}

    result = {
        'raw': description,
        'problem': '',
        'solution': '',
        'steps': [],
        'tagline': ''
    }

    lines = description.strip().split('\n')
    clean_lines = [line.strip() for line in lines if line.strip()]

    # Problem und Lösung extrahieren
    full_text = ' '.join(clean_lines)

    # Problem extrahieren
    problem_match = re.search(r'Das Problem:\s*(.+?)(?:Die Workloom-Lösung:|$)', full_text, re.DOTALL)
    if problem_match:
        result['problem'] = problem_match.group(1).strip()

    # Lösung extrahieren
    solution_match = re.search(r'Die Workloom-Lösung:\s*(.+?)(?:So funktioniert|1️⃣|$)', full_text, re.DOTALL)
    if solution_match:
        result['solution'] = solution_match.group(1).strip()

    # Schritte extrahieren (mit Emoji-Nummern)
    # Die Keycap-Emojis bestehen aus: Ziffer + Variation Selector (optional) + Combining Enclosing Keycap
    # Pattern: digit + \uFE0F (optional) + \u20E3 + text
    step_pattern = r'(\d)[\uFE0F]?\u20E3\s*([^\n]+)'
    step_matches = re.findall(step_pattern, description)

    for step_num, step_text in step_matches:
        step_text = step_text.strip()
        # Entferne "So funktioniert's:" falls am Anfang
        step_text = re.sub(r"^So funktioniert'?s?:?\s*", '', step_text)
        if step_text:
            result['steps'].append(step_text)

    # Tagline extrahieren (letzte Zeile nach den Schritten)
    if clean_lines:
        last_line = clean_lines[-1]
        # Prüfe ob es keine Schritt-Zeile ist
        if not re.match(r'^[123]️⃣', last_line) and not last_line.startswith('Das Problem') and not last_line.startswith('Die Workloom'):
            # Entferne Emoji-Schritte falls vorhanden
            if '3️⃣' not in last_line and '2️⃣' not in last_line:
                result['tagline'] = last_line

    return result


@register.inclusion_tag('includes/app_info_card.html', takes_context=True)
def show_app_info(context, app_name, gradient_colors=None, icon_override=None):
    """
    Template Tag zum Anzeigen einer App-Info-Karte.

    Lädt die AppInfo aus der Datenbank und zeigt sie als schöne Info-Karte an.

    Verwendung:
    {% load app_info_tags %}
    {% show_app_info 'videos' %}
    {% show_app_info 'loomtalk' gradient_colors='#f5365c, #fb6340' %}
    {% show_app_info 'chat' icon_override='bi-chat-dots' %}

    Parameter:
    - app_name: Der app_name aus AppInfo (z.B. 'videos', 'loomtalk')
    - gradient_colors: CSS Gradient-Farben (überschreibt Standard)
    - icon_override: Optionales Icon-Override (überschreibt das Icon aus der DB)
    """
    try:
        app_info = AppInfo.objects.get(app_name=app_name, is_active=True)
    except AppInfo.DoesNotExist:
        return {
            'app_info': None,
            'error': f'AppInfo für "{app_name}" nicht gefunden',
        }

    # Icon bestimmen
    icon_class = icon_override or app_info.icon_class

    # Gradient bestimmen
    if not gradient_colors:
        gradient_colors = APP_GRADIENTS.get(app_name, '#667eea, #764ba2')

    # Beschreibung parsen
    parsed = parse_app_description(app_info.detailed_description)

    return {
        'app_info': app_info,
        'gradient_colors': gradient_colors,
        'icon_class': icon_class,
        'parsed_description': parsed,
    }


@register.simple_tag
def get_app_info(app_name):
    """
    Einfacher Tag zum Laden von AppInfo in eine Variable.

    Verwendung:
    {% load app_info_tags %}
    {% get_app_info 'videos' as video_info %}
    {{ video_info.title }}
    """
    try:
        return AppInfo.objects.get(app_name=app_name, is_active=True)
    except AppInfo.DoesNotExist:
        return None


# Gradient-Presets für verschiedene Apps
APP_GRADIENTS = {
    'videos': '#f5365c, #f56036, #fb6340',  # Rot-Orange
    'streamrec': '#5e72e4, #825ee4',  # Blau-Lila
    'chat': '#2dce89, #26c6da',  # Grün-Türkis
    'todos': '#fb6340, #fbb140',  # Orange-Gelb
    'organization': '#11cdef, #1171ef',  # Cyan-Blau
    'shopify_manager': '#95bf47, #5e8e3e',  # Shopify Grün
    'image_editor': '#f3a4b5, #c471ed',  # Rosa-Lila
    'mail': '#4a90d9, #667eea',  # Blau
    'naturmacher': '#2ecc71, #27ae60',  # Grün
    'somi_plan': '#e91e63, #9c27b0',  # Pink-Lila
    'promptpro': '#ff6b6b, #ee5a24',  # Rot-Orange
    'myprompter': '#764ba2, #667eea',  # Lila-Blau
    'fileshare': '#00b894, #00cec9',  # Türkis
    'loomconnect': '#0984e3, #6c5ce7',  # Blau-Lila
    'linkloom': '#fdcb6e, #e17055',  # Gelb-Orange
    'makeads': '#d63031, #e17055',  # Rot
    'ideopin': '#e60023, #bd081c',  # Pinterest Rot
    'imageforge': '#8e44ad, #3498db',  # Lila-Blau
    'vskript': '#1abc9c, #16a085',  # Türkis
    'questionfinder': '#f39c12, #e67e22',  # Orange
    'blogprep': '#3498db, #2980b9',  # Blau
    'backloom': '#9b59b6, #8e44ad',  # Lila
    'loommarket': '#e74c3c, #c0392b',  # Rot
    'ploom': '#95bf47, #5e8e3e',  # Shopify Grün
    'keyengine': '#2c3e50, #34495e',  # Dunkelblau
    'loomline': '#3498db, #2ecc71',  # Blau-Grün
    'loomtalk': '#6366f1, #8b5cf6',  # Indigo-Violett
    'email_templates': '#4a90d9, #667eea',  # Blau
}


@register.simple_tag
def get_app_gradient(app_name):
    """
    Gibt die Gradient-Farben für eine App zurück.

    Verwendung:
    {% get_app_gradient 'videos' as gradient %}
    """
    return APP_GRADIENTS.get(app_name, '#667eea, #764ba2')
