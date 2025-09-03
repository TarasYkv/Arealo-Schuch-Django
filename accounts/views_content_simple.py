from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db import models
import json

@login_required
@require_http_methods(["POST"])  
def update_content_simple(request):
    """Vereinfachte Content-Update View"""
    try:
        content_id = request.POST.get('content_id')
        page = request.POST.get('page')
        content_key = request.POST.get('content_key', '')
        content_type = request.POST.get('content_type', 'text')
        title = request.POST.get('title', '')
        text_content = request.POST.get('text_content', '')
        html_content = request.POST.get('html_content', '')
        sort_order = request.POST.get('sort_order', 1)
        is_active = request.POST.get('is_active') == 'on'
        
        if not page:
            return JsonResponse({'success': False, 'error': 'Seite ist erforderlich'})
            
        if not content_key.strip():
            return JsonResponse({'success': False, 'error': 'Content-Schlüssel ist erforderlich'})
        
        # Import the model here to avoid circular imports
        from accounts.models import EditableContent
        
        if content_id:
            # Update existing content
            content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        else:
            # Create new content
            try:
                sort_order = int(sort_order)
            except (ValueError, TypeError):
                sort_order = 1
                
            content = EditableContent.objects.create(
                user=request.user,
                page=page,
                content_key=content_key,
                content_type=content_type,
                sort_order=sort_order
            )
        
        # Update fields
        content.content_key = content_key
        content.content_type = content_type
        content.title = title
        content.text_content = text_content
        content.html_content = html_content
        content.sort_order = int(sort_order) if str(sort_order).isdigit() else 1
        content.is_active = is_active
        
        content.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Inhalt erfolgreich gespeichert',
            'content_id': content.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_content_simple(request):
    """Vereinfachte Content-Delete View"""
    try:
        from accounts.models import EditableContent
        
        content_id = request.POST.get('content_id')
        if not content_id:
            return JsonResponse({'success': False, 'error': 'Content-ID ist erforderlich'})
            
        content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        content.delete()
        
        return JsonResponse({'success': True, 'message': 'Inhalt erfolgreich gelöscht'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_content_simple(request, content_id):
    """Vereinfachte Content-Get View"""
    try:
        from accounts.models import EditableContent
        
        content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        
        return JsonResponse({
            'success': True,
            'content': {
                'id': content.id,
                'page': content.page,
                'content_key': content.content_key or '',
                'content_type': content.content_type,
                'title': content.title or '',
                'text_content': content.text_content or '',
                'html_content': content.html_content or '',
                'sort_order': content.sort_order,
                'is_active': content.is_active,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def generate_ai_content_simple(request):
    """Vereinfachte AI Content Generation"""
    try:
        prompt = request.POST.get('prompt', '')
        page = request.POST.get('page', 'startseite')
        content_type = request.POST.get('content_type', 'ai_generated')
        
        if not prompt.strip():
            return JsonResponse({'success': False, 'error': 'Prompt ist erforderlich'})
        
        # Try to import AI service
        try:
            from naturmacher.services.ai_service import generate_html_content
            
            # Generate content with AI
            result = generate_html_content(prompt, page=page)
            
            if result and isinstance(result, dict):
                return JsonResponse({
                    'success': True,
                    'text_content': result.get('text_content', ''),
                    'html_content': result.get('html_content', ''),
                    'message': 'KI-Inhalt erfolgreich generiert'
                })
            else:
                return JsonResponse({'success': False, 'error': 'KI-Service lieferte kein Ergebnis'})
                
        except ImportError:
            return JsonResponse({'success': False, 'error': 'KI-Service nicht verfügbar'})
        except Exception as ai_error:
            return JsonResponse({'success': False, 'error': f'KI-Fehler: {str(ai_error)}'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})