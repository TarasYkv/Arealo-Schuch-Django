"""
BlogPrep Async-fähige Views

Diese Views nutzen Celery für lange Operationen,
antworten aber synchron (warten auf Ergebnis).
"""

import logging
from celery.result import AsyncResult
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import time

from .models import BlogPrepProject, BlogPrepSettings
from .tasks import generate_research_task, generate_content_task, generate_images_task

logger = logging.getLogger(__name__)

TASK_TIMEOUT = 300  # 5 Minuten max


def wait_for_task(task, timeout=TASK_TIMEOUT, poll_interval=0.5):
    """Wartet auf Celery Task Ergebnis (synchron)"""
    start = time.time()
    while time.time() - start < timeout:
        if task.ready():
            if task.successful():
                return task.result
            else:
                raise Exception(str(task.result))
        time.sleep(poll_interval)
    raise TimeoutError('Task dauerte zu lange')


@login_required
@require_POST  
def api_research_celery(request, project_id):
    """Research via Celery - wartet synchron auf Ergebnis"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    
    try:
        # Task starten
        task = generate_research_task.delay(str(project.id), request.user.id)
        
        # Warten auf Ergebnis
        result = wait_for_task(task)
        
        # Projekt neu laden (wurde vom Task aktualisiert)
        project.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'data': project.research_data,
            'message': 'Research abgeschlossen'
        })
        
    except TimeoutError:
        return JsonResponse({
            'success': False,
            'error': 'Research dauert zu lange. Bitte später erneut versuchen.'
        })
    except Exception as e:
        logger.error(f'Research failed: {e}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def api_content_celery(request, project_id):
    """Content-Generierung via Celery"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    section = request.POST.get('section', 'all')
    
    try:
        task = generate_content_task.delay(str(project.id), request.user.id, section)
        result = wait_for_task(task)
        project.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'data': {
                'intro': project.content_intro,
                'main': project.content_main,
                'tips': project.content_tips
            },
            'message': 'Content generiert'
        })
        
    except Exception as e:
        logger.error(f'Content generation failed: {e}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def api_images_celery(request, project_id):
    """Bild-Generierung via Celery"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    
    try:
        task = generate_images_task.delay(str(project.id), request.user.id)
        result = wait_for_task(task, timeout=600)  # Bilder brauchen länger
        project.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'data': {
                'title_image': project.title_image.url if project.title_image else None,
                'section_images': project.section_images
            },
            'message': 'Bilder generiert'
        })
        
    except Exception as e:
        logger.error(f'Image generation failed: {e}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
