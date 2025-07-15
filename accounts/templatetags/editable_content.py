from django import template
from django.utils.safestring import mark_safe
from accounts.models import EditableContent

register = template.Library()

@register.simple_tag(takes_context=True)
def editable_content(context, page, content_key, content_type='text', default_content='', css_class=''):
    """
    Template-Tag für bearbeitbare Inhalte
    
    Usage:
    {% load editable_content %}
    {% editable_content 'startseite' 'hero_title' 'hero_title' 'Willkommen bei Workloom' 'display-5' %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return default_content
    
    try:
        content = EditableContent.objects.get(
            user=request.user,
            page=page,
            content_key=content_key
        )
        
        if content_type == 'image' and content.image_content:
            alt_text = content.image_alt_text or content_key
            css_class_attr = f' class="{css_class}"' if css_class else ''
            
            if content.link_url:
                return mark_safe(
                    f'<a href="{content.link_url}"><img src="{content.image_content.url}" alt="{alt_text}"{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}"></a>'
                )
            else:
                return mark_safe(
                    f'<img src="{content.image_content.url}" alt="{alt_text}"{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}">'
                )
        elif content_type in ['html_block', 'ai_generated'] and content.html_content:
            # Render HTML content with optional CSS
            css_styles = ''
            if content.css_content:
                css_styles = f'<style>{content.css_content}</style>'
            
            html_with_data = content.html_content
            # Add data attributes to the outermost element for editing
            if html_with_data.strip().startswith('<'):
                # Find the first opening tag and add data attributes
                import re
                match = re.match(r'(<[^>]+)', html_with_data)
                if match:
                    first_tag = match.group(1)
                    # Add data attributes before the closing >
                    if first_tag.endswith(' '):
                        first_tag = first_tag.rstrip() + f' data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}"'
                    else:
                        first_tag = first_tag + f' data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}"'
                    html_with_data = html_with_data.replace(match.group(1), first_tag, 1)
            
            return mark_safe(css_styles + html_with_data)
        else:
            display_content = content.text_content or default_content
            
            # Handle CSS styling for text content
            css_styles = ''
            inline_style = ''
            css_class_list = []
            
            if css_class:
                css_class_list.append(css_class)
            
            if content.css_content:
                # Create a unique CSS class for this content
                unique_class = f'content-{content.id}'
                css_class_list.append(unique_class)
                css_styles = f'<style>.{unique_class} {{ {content.css_content} }}</style>'
            
            css_class_attr = f' class="{" ".join(css_class_list)}"' if css_class_list else ''
            
            if content.link_url:
                return mark_safe(
                    f'{css_styles}<a href="{content.link_url}"{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}">{display_content}</a>'
                )
            else:
                return mark_safe(
                    f'{css_styles}<span{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}">{display_content}</span>'
                )
                
    except EditableContent.DoesNotExist:
        # Erstelle automatisch einen neuen Inhalt mit Standard-Wert
        if request.user.is_authenticated:
            content = EditableContent.objects.create(
                user=request.user,
                page=page,
                content_key=content_key,
                content_type=content_type,
                text_content=default_content if content_type != 'image' else ''
            )
            
            css_class_attr = f' class="{css_class}"' if css_class else ''
            return mark_safe(
                f'<span{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="{content_type}">{default_content}</span>'
            )
        
        return default_content


@register.simple_tag(takes_context=True)
def editable_image(context, page, content_key, default_src='', alt_text='', css_class=''):
    """
    Spezielle Template-Tag für bearbeitbare Bilder
    
    Usage:
    {% editable_image 'startseite' 'hero_image' '/static/images/default.jpg' 'Hero Bild' 'img-fluid' %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        if default_src:
            css_class_attr = f' class="{css_class}"' if css_class else ''
            return mark_safe(f'<img src="{default_src}" alt="{alt_text}"{css_class_attr}>')
        return ''
    
    try:
        content = EditableContent.objects.get(
            user=request.user,
            page=page,
            content_key=content_key
        )
        
        if content.image_content:
            image_src = content.image_content.url
            image_alt = content.image_alt_text or alt_text
        else:
            image_src = default_src
            image_alt = alt_text
            
        css_class_attr = f' class="{css_class}"' if css_class else ''
        
        if content.link_url:
            return mark_safe(
                f'<a href="{content.link_url}"><img src="{image_src}" alt="{image_alt}"{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="image"></a>'
            )
        else:
            return mark_safe(
                f'<img src="{image_src}" alt="{image_alt}"{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="image">'
            )
            
    except EditableContent.DoesNotExist:
        # Erstelle automatisch einen neuen Bild-Inhalt
        if request.user.is_authenticated:
            content = EditableContent.objects.create(
                user=request.user,
                page=page,
                content_key=content_key,
                content_type='image',
                image_alt_text=alt_text
            )
            
            css_class_attr = f' class="{css_class}"' if css_class else ''
            return mark_safe(
                f'<img src="{default_src}" alt="{alt_text}"{css_class_attr} data-editable-id="{content.id}" data-editable-key="{content_key}" data-editable-type="image">'
            )
        
        if default_src:
            css_class_attr = f' class="{css_class}"' if css_class else ''
            return mark_safe(f'<img src="{default_src}" alt="{alt_text}"{css_class_attr}>')
        return ''


@register.inclusion_tag('accounts/editable_content_toolbar.html', takes_context=True)
def editable_content_toolbar(context):
    """
    Zeigt eine Toolbar für den Content Editor an (nur für angemeldete User)
    """
    request = context.get('request')
    show_toolbar = request and request.user.is_authenticated
    
    return {
        'show_toolbar': show_toolbar,
        'current_page': context.get('current_page', 'startseite')
    }