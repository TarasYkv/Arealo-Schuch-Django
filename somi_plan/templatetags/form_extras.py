"""
Template tags for enhanced form functionality
"""
from django import template
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def add_class(field, css_class):
    """Add CSS class to form field"""
    if hasattr(field, 'as_widget'):
        return field.as_widget(attrs={'class': css_class})
    return field

@register.filter
def add_attrs(field, attrs_string):
    """Add multiple attributes to form field
    Usage: {{ field|add_attrs:"class:form-control,placeholder:Enter text" }}
    """
    attrs = {}
    if attrs_string:
        for attr_pair in attrs_string.split(','):
            if ':' in attr_pair:
                key, value = attr_pair.split(':', 1)
                attrs[key.strip()] = value.strip()
    
    if hasattr(field, 'as_widget'):
        return field.as_widget(attrs=attrs)
    return field

@register.filter
def with_character_counter(field, limit):
    """Add character counter to textarea field"""
    if not hasattr(field, 'as_widget'):
        return field
    
    attrs = {
        'data-max-length': str(limit),
        'class': 'form-control'
    }
    
    widget_html = field.as_widget(attrs=attrs)
    counter_html = f'<div class="character-counter" data-field="{field.id_for_label}" data-limit="{limit}">0/{limit} Zeichen</div>'
    
    return mark_safe(widget_html + counter_html)

@register.filter
def with_validation(field):
    """Add real-time validation to form field"""
    if not hasattr(field, 'as_widget'):
        return field
    
    attrs = {'class': 'form-control'}
    if field.field.required:
        attrs['required'] = 'required'
    
    widget_html = field.as_widget(attrs=attrs)
    validation_html = '<div class="form-validation" style="display: none;"></div>'
    
    return mark_safe(widget_html + validation_html)

@register.filter
def with_tooltip(field, tooltip_text):
    """Add tooltip to form field label"""
    if not tooltip_text:
        return field
    
    tooltip_html = f'''
    <span class="tooltip-trigger ms-2" data-tooltip="{tooltip_text}">
        <i class="fas fa-question-circle text-muted"></i>
        <div class="tooltip-content">{tooltip_text}</div>
    </span>
    '''
    
    return mark_safe(tooltip_html)

@register.inclusion_tag('somi_plan/includes/enhanced_form_field.html')
def enhanced_field(field, **kwargs):
    """Render enhanced form field with all UX improvements"""
    return {
        'field': field,
        'icon': kwargs.get('icon', ''),
        'help_text': kwargs.get('help_text', ''),
        'character_limit': kwargs.get('character_limit', None),
        'tooltip': kwargs.get('tooltip', ''),
        'required': field.field.required if hasattr(field, 'field') else False
    }

@register.simple_tag
def form_errors_summary(form):
    """Display form errors summary"""
    if not form.errors:
        return ''
    
    errors_html = '<div class="alert alert-danger"><h6>Bitte korrigiere folgende Fehler:</h6><ul class="mb-0">'
    
    for field_name, errors in form.errors.items():
        field_label = form[field_name].label if field_name in form.fields else field_name
        for error in errors:
            errors_html += f'<li><strong>{field_label}:</strong> {error}</li>'
    
    errors_html += '</ul></div>'
    
    return mark_safe(errors_html)

@register.filter
def platform_character_limit(platform):
    """Get character limit for platform"""
    limits = {
        'twitter': 280,
        'instagram': 2200,
        'linkedin': 3000,
        'facebook': 63206,
        'tiktok': 150,
        'youtube': 5000
    }
    
    platform_name = platform.name.lower() if hasattr(platform, 'name') else str(platform).lower()
    return limits.get(platform_name, 1000)

@register.filter
def progress_percentage(current, total):
    """Calculate progress percentage"""
    if not total or total == 0:
        return 0
    return int((current / total) * 100)

@register.simple_tag
def success_message(message, **kwargs):
    """Display enhanced success message"""
    success_type = kwargs.get('type', 'general')
    next_steps = kwargs.get('next_steps', [])
    actions = kwargs.get('actions', [])
    
    html = f'''
    <div class="success-card">
        <h4><span class="success-icon">✅</span> {message}</h4>
    '''
    
    if next_steps:
        html += '<div class="mt-3"><strong>Nächste Schritte:</strong><ul class="mt-2">'
        for step in next_steps:
            html += f'<li>{step}</li>'
        html += '</ul></div>'
    
    if actions:
        html += '<div class="mt-3 d-flex gap-2 flex-wrap">'
        for action in actions:
            btn_class = f"btn-{action.get('type', 'primary')}"
            html += f'<a href="{action["url"]}" class="btn {btn_class} btn-sm">{action["text"]}</a>'
        html += '</div>'
    
    html += '</div>'
    
    return mark_safe(html)

@register.simple_tag
def error_message(message, **kwargs):
    """Display enhanced error message"""
    error_type = kwargs.get('type', 'general')
    fallback_options = kwargs.get('fallback_options', [])
    suggestions = kwargs.get('suggestions', [])
    retry_possible = kwargs.get('retry_possible', False)
    
    html = f'''
    <div class="error-card">
        <h4>⚠️ {message}</h4>
    '''
    
    if suggestions:
        html += '<div class="mt-3"><strong>Vorschläge:</strong><ul class="mt-2">'
        for suggestion in suggestions:
            html += f'<li>{suggestion}</li>'
        html += '</ul></div>'
    
    if fallback_options or retry_possible:
        html += '<div class="error-actions mt-3">'
        if retry_possible:
            html += '<button class="btn btn-primary" onclick="retryLastAction()">Nochmal versuchen</button>'
        for option in fallback_options:
            html += f'<button class="btn btn-outline-primary">{option}</button>'
        html += '</div>'
    
    html += '</div>'
    
    return mark_safe(html)