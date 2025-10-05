from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from bs4 import BeautifulSoup
import os
from django.conf import settings
import hashlib

@login_required
def visual_editor(request):
    """Interactive Visual Page Editor"""
    page = request.GET.get('page', 'startseite')
    
    # Page choices
    page_choices = [
        ('startseite', 'Startseite'),
        ('dashboard', 'Dashboard'),  
        ('impressum', 'Impressum'),
        ('agb', 'AGB'),
        ('datenschutz', 'Datenschutzerklärung'),
    ]
    
    # Try to get custom pages
    try:
        from accounts.models import CustomPage
        custom_pages = CustomPage.objects.filter(user=request.user)
        for custom_page in custom_pages:
            page_choices.append((custom_page.page_name, custom_page.display_name))
    except:
        pass
    
    context = {
        'page': page,
        'page_name': dict(page_choices).get(page, page),
        'page_choices': page_choices,
    }
    
    return render(request, 'accounts/visual_editor.html', context)


def _normalize_selector(raw_selector):
    """Remove editor-specific artifacts and normalize whitespace."""
    if not isinstance(raw_selector, str):
        return ''
    selector = raw_selector.replace('.editable-highlight', '').replace('.element-selected', '')
    selector = selector.replace('..', '.').replace('  ', ' ')
    selector = selector.strip('. ')
    selector = ' '.join(selector.split())
    return selector


def _resolve_content_identifiers(element_id, change_data):
    """Determine stable content_key and DOM selector for an edited element."""
    change_data = change_data or {}
    raw_selector = change_data.get('selector') or element_id or ''
    dom_selector = _normalize_selector(raw_selector)

    data_key = (change_data.get('dataKey') or '').strip()
    attributes = change_data.get('attributes') or {}
    attr_id = ''
    if isinstance(attributes, dict):
        attr_id = (attributes.get('id') or '').strip()

    if data_key:
        content_key = data_key
    elif attr_id:
        content_key = attr_id
    elif dom_selector and all(ch not in dom_selector for ch in (' ', '>', ':', '[', ']')):
        content_key = dom_selector
    else:
        if not dom_selector:
            return None, ''
        hashed = hashlib.sha1(dom_selector.encode('utf-8')).hexdigest()[:12]
        content_key = f'auto_{hashed}'

    return content_key, dom_selector


@login_required
@require_http_methods(["POST"])
def save_visual_changes(request):
    """Save changes from visual editor"""
    try:
        data = json.loads(request.body)
        page = data.get('page')
        changes = data.get('changes', {})
        full_html = data.get('html', '')
        
        # Import models
        from accounts.models import EditableContent, PageSnapshot
        
        # Save individual element changes with stable selectors
        for element_id, change_data in changes.items():
            content_key, dom_selector = _resolve_content_identifiers(element_id, change_data)
            if not content_key:
                continue

            if change_data.get('action') == 'delete':
                EditableContent.objects.update_or_create(
                    user=request.user,
                    page=page,
                    content_key=content_key,
                    defaults={
                        'content_type': 'delete_action',
                        'html_content': '',
                        'text_content': f'[DELETED: {change_data.get("tagName", "Unknown")}]',
                        'dom_selector': dom_selector,
                        'is_active': False
                    }
                )
            else:
                EditableContent.objects.update_or_create(
                    user=request.user,
                    page=page,
                    content_key=content_key,
                    defaults={
                        'content_type': 'html_block',
                        'html_content': change_data.get('content', ''),
                        'text_content': change_data.get('textContent', ''),
                        'dom_selector': dom_selector,
                        'is_active': True
                    }
                )
        
        # Save page snapshot for backup
        try:
            PageSnapshot.objects.create(
                user=request.user,
                page=page,
                html_content=full_html,
                changes=json.dumps(changes)
            )
        except:
            # Model might not exist yet
            pass
        
        return JsonResponse({'success': True, 'message': 'Änderungen gespeichert'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def publish_visual_changes(request):
    """Publish changes to live site"""
    try:
        data = json.loads(request.body)
        page = data.get('page')
        changes = data.get('changes', {})
        full_html = data.get('html', '')
        
        # Import models
        from accounts.models import EditableContent, PageSnapshot
        
        # First, save all changes like save_visual_changes does
        for element_id, change_data in changes.items():
            content_key, dom_selector = _resolve_content_identifiers(element_id, change_data)
            if not content_key:
                continue

            if change_data.get('action') == 'delete':
                EditableContent.objects.update_or_create(
                    user=request.user,
                    page=page,
                    content_key=content_key,
                    defaults={
                        'content_type': 'delete_action',
                        'html_content': '',
                        'text_content': f'[DELETED: {change_data.get("tagName", "Unknown")}]',
                        'dom_selector': dom_selector,
                        'is_active': False,
                        'is_published': True
                    }
                )
            else:
                EditableContent.objects.update_or_create(
                    user=request.user,
                    page=page,
                    content_key=content_key,
                    defaults={
                        'content_type': 'html_block',
                        'html_content': change_data.get('content', ''),
                        'text_content': change_data.get('textContent', ''),
                        'dom_selector': dom_selector,
                        'is_active': True,
                        'is_published': True
                    }
                )
        
        # Also mark any existing content for this page as published
        existing_contents = EditableContent.objects.filter(
            user=request.user,
            page=page,
            is_active=True
        )
        existing_contents.update(is_published=True)
        
        # Save page snapshot for backup
        try:
            PageSnapshot.objects.create(
                user=request.user,
                page=page,
                html_content=full_html,
                changes=json.dumps(changes)
            )
        except:
            # Model might not exist yet
            pass
        
        return JsonResponse({
            'success': True,
            'message': 'Änderungen gespeichert und veröffentlicht',
            'published_count': len(changes)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_page_content(request):
    """Get saved content for a page"""
    try:
        page = request.GET.get('page', 'startseite')
        
        # Import models
        from accounts.models import EditableContent
        
        # Get all content for this page
        contents = EditableContent.objects.filter(
            user=request.user,
            page=page
        ).values('content_key', 'html_content', 'text_content', 'is_active')
        
        return JsonResponse({
            'success': True,
            'contents': list(contents)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def clone_element(request):
    """Clone an element in the visual editor"""
    try:
        data = json.loads(request.body)
        element_html = data.get('html', '')
        element_type = data.get('type', 'div')
        
        # Parse and clean HTML
        soup = BeautifulSoup(element_html, 'html.parser')
        
        # Add unique identifier to cloned element
        import uuid
        clone_id = f"clone_{uuid.uuid4().hex[:8]}"
        
        if soup.contents:
            element = soup.contents[0]
            if hasattr(element, 'attrs'):
                element.attrs['data-clone-id'] = clone_id
        
        return JsonResponse({
            'success': True,
            'html': str(soup),
            'clone_id': clone_id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_element_styles(request):
    """Get computed styles for an element"""
    try:
        element_id = request.GET.get('element_id')
        page = request.GET.get('page', 'startseite')
        
        # This would typically fetch from a style database
        # For now, return default styles
        default_styles = {
            'fontSize': '16px',
            'fontFamily': 'Arial, sans-serif',
            'color': '#333333',
            'backgroundColor': 'transparent',
            'padding': '10px',
            'margin': '0',
            'borderWidth': '0',
            'borderColor': '#cccccc',
            'borderRadius': '0'
        }
        
        return JsonResponse({
            'success': True,
            'styles': default_styles
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def save_element_style(request):
    """Save style changes for an element"""
    try:
        data = json.loads(request.body)
        element_id = data.get('element_id')
        styles = data.get('styles', {})
        page = data.get('page', 'startseite')
        
        # Import models
        from accounts.models import EditableContent
        
        # Create style string
        style_string = '; '.join([f"{k}: {v}" for k, v in styles.items() if v])
        
        # Save as editable content
        content_key = f"style_{element_id}"
        EditableContent.objects.update_or_create(
            user=request.user,
            page=page,
            content_key=content_key,
            defaults={
                'content_type': 'css',
                'text_content': style_string,
                'is_active': True
            }
        )
        
        return JsonResponse({'success': True, 'message': 'Stil gespeichert'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def preview_page(request, page_name):
    """Preview page with edits applied"""
    try:
        # Import models
        from accounts.models import EditableContent
        
        # Get all active content for this page
        contents = EditableContent.objects.filter(
            user=request.user,
            page=page_name,
            is_active=True
        )
        
        # Render the actual page template with modifications
        template_map = {
            'startseite': 'home.html',
            'dashboard': 'accounts/dashboard.html',
            'impressum': 'impressum.html',
            'agb': 'agb.html',
            'datenschutz': 'datenschutz.html',
        }
        
        template = template_map.get(page_name, 'home.html')
        
        context = {
            'editable_contents': contents,
            'preview_mode': True,
            'user': request.user
        }
        
        return render(request, template, context)
        
    except Exception as e:
        # Fallback to redirect to actual page
        if page_name == 'startseite':
            return redirect('/')
        else:
            return redirect(f'/{page_name}/')


@login_required
def export_page_changes(request):
    """Export page changes as JSON"""
    try:
        page = request.GET.get('page', 'startseite')
        
        # Import models
        from accounts.models import EditableContent
        
        # Get all content for this page
        contents = EditableContent.objects.filter(
            user=request.user,
            page=page
        )
        
        export_data = {
            'page': page,
            'timestamp': str(timezone.now()),
            'contents': []
        }
        
        for content in contents:
            export_data['contents'].append({
                'key': content.content_key,
                'type': content.content_type,
                'html': content.html_content,
                'text': content.text_content,
                'active': content.is_active,
                'sort_order': content.sort_order
            })
        
        response = JsonResponse(export_data)
        response['Content-Disposition'] = f'attachment; filename="{page}_export.json"'
        return response
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def import_page_changes(request):
    """Import page changes from JSON"""
    try:
        import_file = request.FILES.get('import_file')
        if not import_file:
            return JsonResponse({'success': False, 'error': 'Keine Datei hochgeladen'})
        
        # Read and parse JSON
        import_data = json.loads(import_file.read())
        
        # Import models
        from accounts.models import EditableContent
        
        page = import_data.get('page')
        contents = import_data.get('contents', [])
        
        imported_count = 0
        for content_data in contents:
            EditableContent.objects.update_or_create(
                user=request.user,
                page=page,
                content_key=content_data['key'],
                defaults={
                    'content_type': content_data.get('type', 'html_block'),
                    'html_content': content_data.get('html', ''),
                    'text_content': content_data.get('text', ''),
                    'is_active': content_data.get('active', True),
                    'sort_order': content_data.get('sort_order', 1)
                }
            )
            imported_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{imported_count} Inhalte importiert'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
