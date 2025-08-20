"""
AJAX Views für MakeAds Progress-Tracking
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib import messages
import json
import logging

from .models import GenerationJob, Campaign
from .ai_service import AICreativeGenerator
from .api_client import CentralAPIClient

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def start_generation_ajax(request):
    """
    Startet die Creative-Generierung via AJAX und gibt Job-ID zurück
    """
    try:
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            # Handle form data from template
            data = request.POST
        
        campaign_id = data.get('campaign_id')
        count = int(data.get('generation_count', data.get('count', 10)))
        ai_service = data.get('ai_service', 'openai')
        style_preference = data.get('style_preference', 'modern')
        color_scheme = data.get('color_scheme', 'vibrant')
        target_audience = data.get('target_audience', '')
        custom_instructions = data.get('custom_instructions', '')
        job_type = data.get('job_type', 'initial')
        
        # Debug logging
        logger.info(f"Received campaign_id: {campaign_id} (type: {type(campaign_id)})")
        logger.info(f"Request user: {request.user.username}")
        logger.info(f"Request POST data: {dict(request.POST)}")
        logger.info(f"Request session campaign_id: {request.session.get('campaign_id')}")
        
        # Falls keine campaign_id in POST, versuche aus Session
        if not campaign_id:
            campaign_id = request.session.get('campaign_id')
            logger.info(f"Using campaign_id from session: {campaign_id}")
        
        if not campaign_id:
            return JsonResponse({
                'success': False,
                'error': 'Keine campaign_id übertragen (weder POST noch Session)'
            }, status=400)
        
        # Kampagne laden
        try:
            campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
            logger.info(f"Found campaign: {campaign.name} (ID: {campaign.id})")
        except Campaign.DoesNotExist:
            # Debug: Show available campaigns
            available_campaigns = Campaign.objects.filter(user=request.user)
            logger.error(f"Campaign with ID {campaign_id} not found for user {request.user.username}")
            logger.error(f"Available campaigns for user: {[(c.id, c.name) for c in available_campaigns]}")
            return JsonResponse({
                'success': False,
                'error': f'Kampagne nicht gefunden (ID: {campaign_id}). Verfügbar: {len(available_campaigns)} Kampagnen.'
            }, status=404)
        
        # API-Key Validierung
        api_client = CentralAPIClient(request.user)
        if not api_client.has_required_keys([ai_service]):
            return JsonResponse({
                'success': False,
                'error': f'Der gewählte KI-Service ({ai_service.upper()}) ist nicht konfiguriert.',
                'redirect_url': api_client.get_service_url()
            }, status=400)
        
        # TEMPORARY: Skip AI generation for debugging
        logger.info(f"Creating job without AI generation for debugging...")
        
        # Create job manually for testing
        job = GenerationJob.objects.create(
            campaign=campaign,
            job_type=job_type,
            target_count=count,
            generated_count=count,  # Pretend all are generated
            status='completed'
        )
        
        logger.info(f"Test job {job.id} created successfully")
        
        # AI-Generator starten - Job wird intern erstellt (DISABLED FOR DEBUGGING)
        # ai_generator = AICreativeGenerator(request.user)
        
        try:
            # TEMPORARY: Skip actual generation
            creatives = []
            
            # # Starte Generierung - Job wird automatisch erstellt und verwaltet
            # creatives = ai_generator.generate_creatives(
            #     campaign=campaign,
            #     count=count,
            #     ai_service=ai_service,
            #     style_preference=style_preference,
            #     color_scheme=color_scheme,
            #     target_audience=target_audience,
            #     custom_instructions=custom_instructions
            # )
            
            # Job already created above for debugging
            logger.info(f"Job {job.id} abgeschlossen: {len(creatives)} Creatives generiert (DEBUG MODE)")
            
        except Exception as e:
            # Fehlgeschlagenen Job finden oder erstellen
            job = GenerationJob.objects.filter(
                campaign=campaign,
                status='failed'
            ).order_by('-created_at').first()
            
            if not job:
                job = GenerationJob.objects.create(
                    campaign=campaign,
                    job_type=job_type,
                    target_count=count,
                    status='failed',
                    error_message=str(e)
                )
            
            logger.error(f"Job {job.id} fehlgeschlagen: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'job_id': str(job.id),
            'campaign_id': str(campaign.id),
            'total_creatives': count,
            'message': 'Generierung gestartet'
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Starten der AJAX-Generierung: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Starten der Generierung: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def cancel_generation_ajax(request, job_id):
    """
    Bricht eine laufende Generierung ab
    """
    try:
        job = get_object_or_404(
            GenerationJob, 
            id=job_id, 
            campaign__user=request.user
        )
        
        if job.status in ['queued', 'processing']:
            job.status = 'failed'
            job.error_message = 'Vom Benutzer abgebrochen'
            job.save()
            
            logger.info(f"Job {job.id} vom User {request.user.username} abgebrochen")
            
            return JsonResponse({
                'success': True,
                'message': 'Generierung wurde abgebrochen'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Job kann nicht abgebrochen werden (bereits abgeschlossen)'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Fehler beim Abbrechen von Job {job_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Abbrechen: {str(e)}'
        }, status=500)


@login_required
def active_jobs_ajax(request):
    """
    Gibt alle aktiven Jobs des Benutzers zurück
    """
    try:
        active_jobs = GenerationJob.objects.filter(
            campaign__user=request.user,
            status__in=['queued', 'processing']
        ).order_by('-created_at')
        
        jobs_data = []
        for job in active_jobs:
            percentage = (job.generated_count / job.target_count * 100) if job.target_count > 0 else 0
            
            jobs_data.append({
                'job_id': str(job.id),
                'campaign_id': str(job.campaign.id),
                'campaign_name': job.campaign.name,
                'status': job.status,
                'progress': job.generated_count,
                'target': job.target_count,
                'percentage': round(percentage, 1),
                'job_type': job.get_job_type_display(),
                'created_at': job.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'active_jobs': jobs_data,
            'count': len(jobs_data)
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen aktiver Jobs: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Abrufen der Jobs: {str(e)}'
        }, status=500)


@login_required  
def generation_stats_ajax(request):
    """
    Gibt Generierungs-Statistiken für den Benutzer zurück
    """
    try:
        from django.db.models import Count, Avg, Q
        from datetime import timedelta
        
        # Statistiken der letzten 30 Tage
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        stats = GenerationJob.objects.filter(
            campaign__user=request.user,
            created_at__gte=thirty_days_ago
        ).aggregate(
            total_jobs=Count('id'),
            completed_jobs=Count('id', filter=Q(status='completed')),
            failed_jobs=Count('id', filter=Q(status='failed')),
            avg_creatives=Avg('target_count')
        )
        
        # Erfolgsrate berechnen
        success_rate = 0
        if stats['total_jobs'] > 0:
            success_rate = (stats['completed_jobs'] / stats['total_jobs']) * 100
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_jobs': stats['total_jobs'] or 0,
                'completed_jobs': stats['completed_jobs'] or 0,
                'failed_jobs': stats['failed_jobs'] or 0,
                'success_rate': round(success_rate, 1),
                'avg_creatives': round(stats['avg_creatives'] or 0, 1),
                'period': '30 Tage'
            }
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Statistiken: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Abrufen der Statistiken: {str(e)}'
        }, status=500)