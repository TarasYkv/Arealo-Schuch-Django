"""
BlogPrep Celery Tasks

Asynchrone Verarbeitung für:
- Content-Generierung (Research, Outline, Text)
- Bild-Generierung
"""

import logging
import json
from celery import shared_task

logger = logging.getLogger(__name__)


def get_user_settings(user):
    from .models import BlogPrepSettings
    settings, _ = BlogPrepSettings.objects.get_or_create(user=user)
    return settings


def get_company_info(settings):
    return {
        'name': settings.company_name,
        'description': settings.company_description,
        'expertise': settings.company_expertise,
        'products': settings.product_info,
        'product_links': settings.scraped_product_data or []
    }


def log_generation(project, step, provider, model, prompt, response, success=True, error='', duration=0, tokens_in=0, tokens_out=0):
    from .models import BlogPrepGenerationLog
    BlogPrepGenerationLog.objects.create(
        project=project,
        step=step,
        provider=provider,
        model=model,
        prompt=prompt[:5000],
        response=response[:10000] if response else '',
        success=success,
        error_message=error,
        duration_seconds=duration,
        tokens_input=tokens_in,
        tokens_output=tokens_out
    )


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_research_task(self, project_id: str, user_id: int):
    """Führt Research für ein BlogPrep-Projekt durch"""
    from django.contrib.auth import get_user_model
    from .models import BlogPrepProject, BlogPrepSettings
    from .ai_services import ContentService
    from .ai_services.research_service import WebResearchService
    
    User = get_user_model()

    try:
        project = BlogPrepProject.objects.get(id=project_id)
        user = User.objects.get(id=user_id)
        settings = get_user_settings(user)
        
        # Web-Recherche durchführen
        research_service = WebResearchService()
        web_results = research_service.search_and_analyze(project.main_keyword, num_results=5)
        
        if not web_results.get('success'):
            search_results = []
        else:
            search_results = web_results.get('search_results', [])
        
        # KI-Analyse
        content_service = ContentService(user, settings)
        result = content_service.analyze_research(project.main_keyword, search_results)
        
        if result.get('success'):
            result['data']['sources'] = [
                {'title': r.get('title', ''), 'url': r.get('url', ''), 'position': r.get('position', 0)}
                for r in search_results
            ]
            project.research_data = result['data']
            project.save()
            
            log_generation(
                project, 'research', settings.ai_provider, settings.ai_model,
                f'Research for: {project.main_keyword}',
                json.dumps(result['data']),
                duration=result.get('duration', 0),
                tokens_in=result.get('tokens_input', 0),
                tokens_out=result.get('tokens_output', 0)
            )
        
        logger.info(f"Research completed for project {project_id}")
        return {'success': True, 'project_id': project_id}
        
    except Exception as e:
        logger.error(f"Research failed for project {project_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_content_task(self, project_id: str, user_id: int, section: str = 'all'):
    """Generiert Content für ein BlogPrep-Projekt"""
    from django.contrib.auth import get_user_model
    from .models import BlogPrepProject
    from .ai_services import ContentService

    User = get_user_model()

    try:
        project = BlogPrepProject.objects.get(id=project_id)
        user = User.objects.get(id=user_id)
        settings = get_user_settings(user)
        
        content_service = ContentService(user, settings)
        company_info = get_company_info(settings)
        
        if section in ['intro', 'all']:
            result = content_service.generate_intro(
                project.main_keyword,
                project.outline or {},
                project.research_data or {},
                company_info
            )
            if result.get('success'):
                project.content_intro = result['data']
            
        if section in ['main', 'all']:
            result = content_service.generate_main_content(
                project.main_keyword,
                project.outline or {},
                project.research_data or {},
                company_info
            )
            if result.get('success'):
                project.content_main = result['data']
            
        if section in ['tips', 'all']:
            result = content_service.generate_tips(
                project.main_keyword,
                project.outline or {},
                company_info
            )
            if result.get('success'):
                project.content_tips = result['data']
        
        project.save()
        logger.info(f"Content generated for project {project_id}")
        return {'success': True, 'project_id': project_id}
        
    except Exception as e:
        logger.error(f"Content generation failed for project {project_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_images_task(self, project_id: str, user_id: int):
    """Generiert Bilder für ein BlogPrep-Projekt"""
    from django.contrib.auth import get_user_model
    from .models import BlogPrepProject
    from .ai_services import ImageService

    User = get_user_model()

    try:
        project = BlogPrepProject.objects.get(id=project_id)
        user = User.objects.get(id=user_id)
        settings = get_user_settings(user)
        
        image_service = ImageService(user, settings)
        
        # Titelbild
        if project.title_image_prompt and not project.title_image:
            result = image_service.generate_image(project.title_image_prompt)
            if result.get('success'):
                project.title_image = result['data']
        
        # Section-Bilder
        if project.section_images:
            updated = []
            for section in project.section_images:
                if section.get('prompt') and not section.get('image'):
                    result = image_service.generate_image(section['prompt'])
                    if result.get('success'):
                        section['image'] = result['data']
                updated.append(section)
            project.section_images = updated
        
        project.save()
        logger.info(f"Images generated for project {project_id}")
        return {'success': True, 'project_id': project_id}
        
    except Exception as e:
        logger.error(f"Image generation failed for project {project_id}: {e}")
        raise self.retry(exc=e)


@shared_task
def get_project_status(project_id: str):
    """Holt den aktuellen Status eines Projekts"""
    from .models import BlogPrepProject
    
    try:
        project = BlogPrepProject.objects.get(id=project_id)
        return {
            'project_id': project_id,
            'status': project.status,
            'title': project.title,
            'has_research': bool(project.research_data),
            'has_content': bool(project.content_main),
            'has_images': bool(project.title_image),
        }
    except:
        return {'error': 'Project not found'}
