from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)

from .models import Campaign, ReferenceImage, Creative, GenerationJob, TextOverlay
from .forms import (
    CampaignStep1Form, CampaignStep2Form, ReferenceImageForm,
    CreativeGenerationForm, CreativeRevisionForm, CreativeFeedbackForm,
    BulkActionForm
)
from .ai_service import AICreativeGenerator
from .decorators import require_api_keys, optional_api_keys
from .api_client import CentralAPIClient


@login_required
@optional_api_keys(['openai', 'anthropic', 'google'])
def dashboard(request):
    """
    MakeAds Dashboard - Übersicht aller Kampagnen
    """
    # Basis-Queryset mit annotierter Favoriten-Anzahl (verhindert N+1)
    campaigns = Campaign.objects.filter(user=request.user).annotate(
        favorite_count=Count('creatives', filter=Q(creatives__is_favorite=True))
    ).order_by('-created_at')

    # Statistiken in einem Query
    stats = Campaign.objects.filter(user=request.user).aggregate(
        total_campaigns=Count('id'),
        total_creatives=Count('creatives'),
        active_jobs=Count(
            'generation_jobs',
            filter=Q(generation_jobs__status__in=['queued', 'processing'])
        )
    )
    total_campaigns = stats['total_campaigns']
    total_creatives = stats['total_creatives']
    active_jobs = stats['active_jobs']

    # Neueste Kampagnen für Dashboard (favorite_count bereits annotiert)
    recent_campaigns = campaigns[:5]
    
    # API-Key Status prüfen
    api_client = CentralAPIClient(request.user)
    api_key_status = api_client.validate_api_keys()
    
    context = {
        'campaigns': recent_campaigns,
        'total_campaigns': total_campaigns,
        'total_creatives': total_creatives,
        'active_jobs': active_jobs,
        'api_key_status': api_key_status,
        'api_settings_url': api_client.get_service_url(),
    }
    
    return render(request, 'makeads/dashboard.html', context)


@login_required
def campaign_list(request):
    """
    Liste aller Kampagnen des Benutzers
    """
    # Basis-Queryset mit annotierter Favoriten-Anzahl (verhindert N+1)
    campaigns = Campaign.objects.filter(user=request.user).annotate(
        favorite_count=Count('creatives', filter=Q(creatives__is_favorite=True))
    ).order_by('-created_at')

    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        campaigns = campaigns.filter(
            Q(name__icontains=search_query) |
            Q(basic_idea__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Paginierung
    paginator = Paginator(campaigns, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'makeads/campaign_list.html', context)


@login_required
def campaign_create_step1(request):
    """
    Schritt 1: Ideeneingabe
    """
    if request.method == 'POST':
        form = CampaignStep1Form(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.user = request.user
            campaign.save()
            
            # Session für Wizard
            request.session['campaign_id'] = str(campaign.id)
            messages.success(request, 'Schritt 1 abgeschlossen! Fügen Sie nun Referenzmaterial hinzu.')
            
            return redirect('makeads:campaign_create_step2')
    else:
        form = CampaignStep1Form()
    
    context = {
        'form': form,
        'step': 1,
        'step_title': 'Ideeneingabe',
    }
    
    return render(request, 'makeads/campaign_create_step1.html', context)


@login_required
def campaign_create_step2(request):
    """
    Schritt 2: Referenzmaterial hinzufügen (mit URL-zu-Bild Verarbeitung)
    """
    campaign_id = request.session.get('campaign_id')
    if not campaign_id:
        messages.error(request, 'Bitte starten Sie mit Schritt 1.')
        return redirect('makeads:campaign_create_step1')
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    # Initialize processing results for template
    url_processing_results = []
    analysis_results = []
    
    if request.method == 'POST':
        form = CampaignStep2Form(request.POST, instance=campaign)
        
        if form.is_valid():
            # Save form data first
            campaign = form.save()
            
            # Process uploaded files
            uploaded_files = request.FILES.getlist('reference_images')
            uploaded_count = 0
            
            # Get API key for image analysis
            api_client = CentralAPIClient(request.user)
            api_keys = api_client.get_api_keys()
            openai_api_key = api_keys.get('openai')
            
            # Initialize ReferenceManager
            from .image_processor import ReferenceManager
            reference_manager = ReferenceManager(openai_api_key)
            
            # Process uploaded reference images
            for uploaded_file in uploaded_files:
                try:
                    # Create ReferenceImage
                    reference_image = ReferenceImage.objects.create(
                        campaign=campaign,
                        image=uploaded_file,
                        description=f"Referenzbild für {campaign.name}"
                    )
                    
                    # Analyze uploaded image if API key available
                    if openai_api_key:
                        try:
                            analysis = reference_manager.image_analyzer.analyze_image(
                                reference_image.image, 
                                uploaded_file.name
                            )
                            
                            if analysis.get('success') and analysis.get('description'):
                                reference_image.description = f"{analysis['description']} | KI-analysiert: {analysis.get('style_elements', {}).get('overall_style', 'unbekannt')}"
                                reference_image.save()
                                
                            analysis_results.append({
                                'reference_image': reference_image,
                                'analysis': analysis,
                                'type': 'upload'
                            })
                            
                        except Exception as e:
                            logger.warning(f"Could not analyze uploaded image: {str(e)}")
                    
                    uploaded_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing uploaded file {uploaded_file.name}: {str(e)}")
                    messages.warning(request, f'Fehler beim Hochladen von "{uploaded_file.name}": {str(e)}')
            
            # Process web links for image URLs
            web_links = form.cleaned_data.get('web_links', '')
            if web_links and openai_api_key:
                try:
                    url_processing_results = reference_manager.process_web_links(web_links, campaign)
                    
                    processed_count = sum(1 for result in url_processing_results if result.get('processed'))
                    failed_count = len(url_processing_results) - processed_count
                    
                    if processed_count > 0:
                        messages.success(
                            request, 
                            f'✅ {processed_count} Bild(er) automatisch aus URLs heruntergeladen und analysiert!'
                        )
                        
                    if failed_count > 0:
                        messages.warning(
                            request,
                            f'⚠️ {failed_count} URL(s) konnten nicht als Bilder verarbeitet werden.'
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing web links: {str(e)}")
                    messages.warning(request, f'Fehler bei URL-Verarbeitung: {str(e)}')
            
            elif web_links and not openai_api_key:
                # Check if there are potential image URLs but no API key
                from .image_processor import ImageURLProcessor
                url_processor = ImageURLProcessor()
                potential_images = url_processor.extract_image_urls(web_links)
                
                if potential_images:
                    api_config_url = api_client.get_service_url()
                    messages.info(
                        request,
                        f'📷 {len(potential_images)} Bild-URL(s) erkannt! '
                        f'<a href="{api_config_url}" class="alert-link">OpenAI API-Key konfigurieren</a> '
                        'für automatisches Herunterladen und Analyse.'
                    )
            
            # Success message
            total_images = campaign.reference_images.count()
            if uploaded_count > 0 or url_processing_results:
                if total_images > 0:
                    messages.success(
                        request, 
                        f'🎨 Schritt 2 abgeschlossen! {total_images} Referenzbild(er) hochgeladen. '
                        'Konfigurieren Sie nun die Creative-Generierung.'
                    )
                else:
                    messages.success(request, 'Schritt 2 abgeschlossen! Konfigurieren Sie nun die Creative-Generierung.')
            else:
                messages.success(request, 'Schritt 2 abgeschlossen! Konfigurieren Sie nun die Creative-Generierung.')
                
            return redirect('makeads:campaign_create_step3')
    else:
        form = CampaignStep2Form(instance=campaign)
    
    # Get existing reference images
    reference_images = campaign.reference_images.all().order_by('-uploaded_at')
    
    # Check for potential image URLs in existing web_links
    existing_image_urls = []
    if campaign.web_links:
        from .image_processor import ImageURLProcessor
        url_processor = ImageURLProcessor()
        existing_image_urls = url_processor.extract_image_urls(campaign.web_links)
    
    # API key status for template
    api_client = CentralAPIClient(request.user)
    api_keys = api_client.validate_api_keys()
    
    context = {
        'form': form,
        'campaign': campaign,
        'reference_images': reference_images,
        'step': 2,
        'step_title': 'Referenzmaterial',
        'url_processing_results': url_processing_results,
        'analysis_results': analysis_results,
        'existing_image_urls': existing_image_urls,
        'api_keys': api_keys,
        'api_config_url': api_client.get_service_url(),
    }
    
    return render(request, 'makeads/campaign_create_step2.html', context)


@login_required
@require_api_keys(['openai'])  # Mindestens OpenAI wird benötigt
def campaign_create_step3(request):
    """
    Schritt 3: Creative-Generierung
    """
    campaign_id = request.session.get('campaign_id')
    if not campaign_id:
        messages.error(request, 'Bitte starten Sie mit Schritt 1.')
        return redirect('makeads:campaign_create_step1')
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    if request.method == 'POST':
        form = CreativeGenerationForm(request.POST)
        if form.is_valid():
            # Prüfe ob der gewählte Service verfügbar ist
            ai_service = form.cleaned_data['ai_service']
            api_client = CentralAPIClient(request.user)
            
            # Validiere den gewählten Service
            if not api_client.has_required_keys([ai_service]):
                messages.error(
                    request,
                    f'Der gewählte KI-Service ({ai_service.upper()}) ist nicht konfiguriert. '
                    f'<a href="{api_client.get_service_url()}" class="text-primary">API-Key konfigurieren</a>'
                )
                return render(request, 'makeads/campaign_create_step3.html', {
                    'form': form,
                    'campaign': campaign,
                    'step': 3,
                    'step_title': 'Creative-Generierung',
                })
            
            # KI-Service initialisieren
            ai_generator = AICreativeGenerator(request.user)
            
            # Generierungsparameter
            generation_params = {
                'count': int(form.cleaned_data['generation_count']),
                'ai_service': ai_service,
                'style_preference': form.cleaned_data['style_preference'],
                'color_scheme': form.cleaned_data['color_scheme'],
                'target_audience': form.cleaned_data['target_audience'],
                'custom_instructions': form.cleaned_data['custom_instructions'],
            }
            
            # Asynchrone Generierung starten
            try:
                creatives = ai_generator.generate_creatives(campaign, **generation_params)
                
                # Session aufräumen
                if 'campaign_id' in request.session:
                    del request.session['campaign_id']
                
                messages.success(
                    request, 
                    f'Ihre {len(creatives)} Creatives wurden erfolgreich generiert!'
                )
                
                return redirect('makeads:campaign_detail', campaign_id=campaign.id)
                
            except Exception as e:
                messages.error(request, f'Fehler bei der Creative-Generierung: {str(e)}')
    else:
        form = CreativeGenerationForm()
    
    # Verfügbare Services ermitteln
    api_client = CentralAPIClient(request.user)
    available_services = api_client.validate_api_keys()
    
    context = {
        'form': form,
        'campaign': campaign,
        'step': 3,
        'step_title': 'Creative-Generierung',
        'available_services': available_services,
        'api_settings_url': api_client.get_service_url(),
    }
    
    return render(request, 'makeads/campaign_create_step3.html', context)


@login_required
def campaign_detail(request, campaign_id):
    """
    Kampagnen-Detail mit Creative-Galerie
    """
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    # Creatives mit Paginierung
    creatives = campaign.creatives.order_by('-created_at')
    
    # Filter
    status_filter = request.GET.get('status', '')
    batch_filter = request.GET.get('batch', '')
    favorite_filter = request.GET.get('favorite', '')
    
    if status_filter:
        creatives = creatives.filter(generation_status=status_filter)
    if batch_filter:
        creatives = creatives.filter(generation_batch=batch_filter)
    if favorite_filter == 'true':
        creatives = creatives.filter(is_favorite=True)
    
    # Paginierung
    paginator = Paginator(creatives, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiken
    total_creatives = campaign.creatives.count()
    favorite_count = campaign.creatives.filter(is_favorite=True).count()
    batch_numbers = campaign.creatives.values_list(
        'generation_batch', flat=True
    ).distinct().order_by('generation_batch')
    
    # Stale/hängende Jobs automatisch bereinigen (z.B. Browser geschlossen, Prozess abgebrochen)
    cleanup_cutoff = timezone.now() - timedelta(minutes=30)
    campaign.generation_jobs.filter(
        status__in=['queued', 'processing'],
        created_at__lt=cleanup_cutoff
    ).update(status='failed', error_message='Automatisch als inaktiv markiert')

    # Aktive Jobs innerhalb des Zeitfensters anzeigen
    active_jobs = campaign.generation_jobs.filter(
        status__in=['queued', 'processing'],
        created_at__gte=cleanup_cutoff
    )
    
    context = {
        'campaign': campaign,
        'page_obj': page_obj,
        'total_creatives': total_creatives,
        'favorite_count': favorite_count,
        'batch_numbers': batch_numbers,
        'active_jobs': active_jobs,
        'status_filter': status_filter,
        'batch_filter': batch_filter,
        'favorite_filter': favorite_filter,
    }
    
    return render(request, 'makeads/campaign_detail.html', context)


@login_required
@require_api_keys(['openai'])  # Standard-Service ist OpenAI
def generate_more_creatives(request, campaign_id):
    """
    Weitere 5 Creatives generieren
    """
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    if request.method == 'POST':
        ai_generator = AICreativeGenerator(request.user)
        
        try:
            creatives = ai_generator.generate_more_creatives(
                campaign, 
                count=5,
                ai_service='openai',  # Standard-Service
                style_preference='modern',
                color_scheme='vibrant'
            )
            
            messages.success(
                request, 
                f'{len(creatives)} weitere Creatives wurden erfolgreich generiert!'
            )
            
        except Exception as e:
            messages.error(request, f'Fehler bei der Generierung: {str(e)}')
    
    return redirect('makeads:campaign_detail', campaign_id=campaign.id)


@login_required
def creative_detail(request, creative_id):
    """
    Creative-Detail mit Überarbeitungsmöglichkeit
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    # Überarbeitungsformular
    revision_form = CreativeRevisionForm()
    feedback_form = CreativeFeedbackForm(initial={
        'is_favorite': creative.is_favorite
    })
    
    # Ähnliche Creatives
    similar_creatives = Creative.objects.filter(
        campaign=creative.campaign,
        generation_batch=creative.generation_batch
    ).exclude(id=creative.id)[:6]
    
    # API-Key Status für Template
    api_client = CentralAPIClient(request.user)
    api_keys = api_client.validate_api_keys()
    
    # Billing-Status prüfen wenn OpenAI verfügbar ist
    billing_status = {'status': 'unknown', 'message': 'Nicht geprüft'}
    if api_keys.get('openai', False):
        try:
            ai_generator = AICreativeGenerator(request.user)
            # Kurzer Test um Billing-Status zu prüfen
            test_result = ai_generator._generate_image("test", "openai")
            billing_status = ai_generator.get_billing_status()
        except Exception as e:
            logger.warning(f"Billing check in template failed: {str(e)}")
    
    context = {
        'creative': creative,
        'revision_form': revision_form,
        'feedback_form': feedback_form,
        'similar_creatives': similar_creatives,
        'api_keys': api_keys,
        'billing_status': billing_status,
        'api_config_url': api_client.get_service_url(),
    }
    
    return render(request, 'makeads/creative_detail.html', context)


@login_required
@require_api_keys(['openai'])  # Überarbeitung benötigt API-Key
def creative_revise(request, creative_id):
    """
    Creative überarbeiten
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    if request.method == 'POST':
        form = CreativeRevisionForm(request.POST)
        if form.is_valid():
            # Prüfe API-Key Status vor der Generierung
            api_client = CentralAPIClient(request.user)
            api_keys = api_client.validate_api_keys()
            
            if not api_keys.get('openai', False):
                messages.error(
                    request, 
                    f'OpenAI API-Key ist erforderlich für Creative-Überarbeitung. '
                    f'<a href="{api_client.get_service_url()}" class="text-primary">API-Key konfigurieren</a>'
                )
                return redirect('makeads:creative_detail', creative_id=creative.id)
            
            ai_generator = AICreativeGenerator(request.user)
            
            # Revision-Anweisungen zusammenstellen
            revision_instructions = []
            
            if form.cleaned_data['text_changes']:
                revision_instructions.append(f"Text: {form.cleaned_data['text_changes']}")
            
            if form.cleaned_data['image_changes']:
                revision_instructions.append(f"Bild: {form.cleaned_data['image_changes']}")
            
            if form.cleaned_data['style_adjustments']:
                revision_instructions.append(f"Stil: {form.cleaned_data['style_adjustments']}")
            
            revision_text = " | ".join(revision_instructions)
            
            if not revision_text.strip():
                messages.error(request, 'Bitte geben Sie mindestens eine Änderungsanweisung ein.')
                return redirect('makeads:creative_detail', creative_id=creative.id)
            
            try:
                logger.info(f"Starting creative revision for {creative.id} by user {request.user.username}")
                logger.info(f"Revision instructions: {revision_text}")
                
                revised_creative = ai_generator.revise_creative(
                    creative,
                    revision_text,
                    form.cleaned_data['revision_type']
                )
                
                if revised_creative:
                    messages.success(request, 'Creative wurde erfolgreich überarbeitet!')
                    logger.info(f"Creative revision successful: {revised_creative.id}")
                    return redirect('makeads:creative_detail', creative_id=revised_creative.id)
                else:
                    messages.error(request, 'Fehler bei der Überarbeitung. Bitte versuchen Sie es erneut.')
                    logger.error(f"Creative revision failed for {creative.id}")
                    
            except Exception as e:
                logger.error(f'Creative revision error for {creative.id}: {str(e)}', exc_info=True)
                messages.error(request, f'Fehler bei der Überarbeitung: {str(e)}')
    
    return redirect('makeads:creative_detail', creative_id=creative.id)


@login_required
@require_http_methods(["POST"])
def creative_update_title(request, creative_id):
    """
    AJAX endpoint to update creative title
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    try:
        data = json.loads(request.body)
        new_title = data.get('title', '').strip()
        
        if not new_title:
            return JsonResponse({
                'success': False, 
                'error': 'Titel darf nicht leer sein.'
            }, status=400)
        
        if len(new_title) > 200:  # Assuming max length constraint
            return JsonResponse({
                'success': False, 
                'error': 'Titel ist zu lang (max. 200 Zeichen).'
            }, status=400)
        
        # Update title
        creative.title = new_title
        creative.save(update_fields=['title', 'updated_at'])
        
        return JsonResponse({
            'success': True, 
            'title': creative.title
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False, 
            'error': 'Ungültiger JSON-Request.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Fehler beim Speichern: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def add_text_overlay(request, creative_id):
    """
    Add text overlay to creative
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        text_content = data.get('text_content', '').strip()
        if not text_content:
            return JsonResponse({
                'success': False,
                'error': 'Text-Inhalt ist erforderlich.'
            }, status=400)
        
        # Create overlay with provided data
        overlay = TextOverlay.objects.create(
            creative=creative,
            text_content=text_content,
            x_position=data.get('x_position', 10.0),
            y_position=data.get('y_position', 10.0),
            font_family=data.get('font_family', 'arial'),
            font_size=data.get('font_size', 24),
            font_weight=data.get('font_weight', 'normal'),
            text_color=data.get('text_color', '#ffffff'),
            background_color=data.get('background_color'),
            background_opacity=data.get('background_opacity', 0.0),
            text_align=data.get('text_align', 'left'),
            has_shadow=data.get('has_shadow', True),
            shadow_color=data.get('shadow_color', '#000000'),
            shadow_blur=data.get('shadow_blur', 4),
            has_border=data.get('has_border', False),
            border_color=data.get('border_color', '#000000'),
            border_width=data.get('border_width', 1),
            width=data.get('width', 200),
            rotation=data.get('rotation', 0.0),
            ai_generated=data.get('ai_generated', False),
            ai_prompt_used=data.get('ai_prompt_used', ''),
            z_index=data.get('z_index', 1)
        )
        
        return JsonResponse({
            'success': True,
            'overlay_id': str(overlay.id),
            'styles': overlay.get_css_styles(),
            'style_string': overlay.get_style_string()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiger JSON-Request.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Erstellen des Overlays: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def generate_overlay_text(request, creative_id):
    """
    Generate text overlay using AI
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    try:
        data = json.loads(request.body)
        prompt = data.get('prompt', '').strip()
        
        if not prompt:
            return JsonResponse({
                'success': False,
                'error': 'Prompt ist erforderlich.'
            }, status=400)
        
        # Use AI service to generate overlay text
        ai_generator = AICreativeGenerator(request.user)
        
        # Create a context-aware prompt for overlay text
        context_prompt = f"""
        Erstelle einen kurzen, prägnanten Text-Overlay für ein Werbecreative.
        
        Creative-Kontext:
        - Titel: {creative.title}
        - Beschreibung: {creative.description}
        - Kampagne: {creative.campaign.name}
        
        Benutzer-Anfrage: {prompt}
        
        Generiere NUR den Text für das Overlay, ohne zusätzliche Formatierung oder Erklärungen.
        Der Text sollte maximal 2-3 Zeilen und sehr prägnant sein.
        """
        
        # Generate text using the existing AI service method
        try:
            text_result = ai_generator._generate_text(context_prompt, 'openai')
            logger.info(f"AI text generation result: {text_result}")
            
            # Handle different response formats
            generated_text = ''
            if isinstance(text_result, str):
                # Try to parse as JSON first
                try:
                    json_data = json.loads(text_result)
                    if 'content' in json_data:
                        generated_text = json_data['content'].strip()
                    elif 'text' in json_data:
                        generated_text = json_data['text'].strip()
                    else:
                        generated_text = text_result.strip()
                except json.JSONDecodeError:
                    generated_text = text_result.strip()
            elif isinstance(text_result, dict):
                if 'text_content' in text_result:
                    generated_text = text_result.get('text_content', '').strip()
                elif 'content' in text_result:
                    generated_text = text_result.get('content', '').strip()
                elif 'text' in text_result:
                    generated_text = text_result.get('text', '').strip()
            
            if generated_text:
                return JsonResponse({
                    'success': True,
                    'generated_text': generated_text,
                    'ai_prompt_used': context_prompt
                })
            else:
                logger.warning(f"No text generated from result: {text_result}")
                return JsonResponse({
                    'success': False,
                    'error': 'Keine Text-Generierung möglich. Versuchen Sie einen anderen Prompt.'
                }, status=500)
        except Exception as gen_error:
            logger.error(f"AI text generation error: {str(gen_error)}")
            return JsonResponse({
                'success': False,
                'error': f'Fehler bei der KI-Text-Generierung: {str(gen_error)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiger JSON-Request.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der Text-Generierung: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def generate_text_design(request, creative_id):
    """
    Generate elegant text design styling using AI
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    try:
        data = json.loads(request.body)
        design_style = data.get('design_style', 'elegant')
        
        # Define elegant design presets
        design_presets = {
            'elegant': {
                'font_family': 'georgia',
                'font_weight': 'light',
                'font_size': 28,
                'text_color': '#2C3E50',
                'background_color': '#FFFFFF',
                'background_opacity': 0.85,
                'has_shadow': True,
                'shadow_color': '#00000020',
                'letter_spacing': 1.5,
                'line_height': 1.4,
                'text_align': 'center',
                'width': 300
            },
            'modern': {
                'font_family': 'helvetica',
                'font_weight': 'normal',
                'font_size': 24,
                'text_color': '#1A1A1A',
                'background_color': None,
                'background_opacity': 0.0,
                'has_shadow': False,
                'letter_spacing': 0.5,
                'line_height': 1.3,
                'text_align': 'left',
                'width': 250
            },
            'bold': {
                'font_family': 'impact',
                'font_weight': 'black',
                'font_size': 36,
                'text_color': '#FF6B35',
                'background_color': '#000000',
                'background_opacity': 0.8,
                'has_shadow': True,
                'shadow_color': '#FFFFFF',
                'letter_spacing': 2.0,
                'line_height': 1.2,
                'text_align': 'center',
                'width': 350
            },
            'luxury': {
                'font_family': 'times',
                'font_weight': 'normal',
                'font_size': 32,
                'text_color': '#D4AF37',
                'background_color': '#000000',
                'background_opacity': 0.9,
                'has_shadow': True,
                'shadow_color': '#D4AF37',
                'letter_spacing': 3.0,
                'line_height': 1.5,
                'text_align': 'center',
                'width': 400
            },
            'playful': {
                'font_family': 'comic-sans',
                'font_weight': 'bold',
                'font_size': 26,
                'text_color': '#FF69B4',
                'background_color': '#FFFF00',
                'background_opacity': 0.7,
                'has_shadow': True,
                'shadow_color': '#FF1493',
                'letter_spacing': 0.0,
                'line_height': 1.3,
                'text_align': 'center',
                'width': 280
            },
            'corporate': {
                'font_family': 'arial',
                'font_weight': 'normal',
                'font_size': 22,
                'text_color': '#2E3B4E',
                'background_color': '#F8F9FA',
                'background_opacity': 0.95,
                'has_shadow': False,
                'letter_spacing': 0.2,
                'line_height': 1.4,
                'text_align': 'left',
                'width': 320
            }
        }
        
        design = design_presets.get(design_style, design_presets['elegant'])
        
        return JsonResponse({
            'success': True,
            'design': design,
            'style_name': design_style
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiger JSON-Request.'
        }, status=400)
    except Exception as e:
        logger.error(f"Design generation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der Design-Generierung: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_text_overlay(request, overlay_id):
    """
    Get text overlay data for form population
    """
    overlay = get_object_or_404(
        TextOverlay,
        id=overlay_id,
        creative__campaign__user=request.user
    )
    
    overlay_data = {
        'text_content': overlay.text_content,
        'font_family': overlay.font_family,
        'font_size': overlay.font_size,
        'font_weight': overlay.font_weight,
        'text_color': overlay.text_color,
        'text_align': overlay.text_align,
        'width': overlay.width,
        'line_height': overlay.line_height,
        'letter_spacing': overlay.letter_spacing,
        'background_color': overlay.background_color,
        'background_opacity': overlay.background_opacity,
        'has_shadow': overlay.has_shadow,
        'has_gradient': overlay.has_gradient,
        'gradient_start_color': overlay.gradient_start_color,
        'gradient_end_color': overlay.gradient_end_color,
        'gradient_direction': overlay.gradient_direction,
        'has_glow': overlay.has_glow,
        'glow_color': overlay.glow_color,
        'glow_intensity': overlay.glow_intensity,
        'has_outline': overlay.has_outline,
        'outline_color': overlay.outline_color,
        'outline_width': overlay.outline_width,
        'has_3d_effect': overlay.has_3d_effect,
        'effect_color': overlay.effect_color,
        'effect_depth': overlay.effect_depth,
        'x_position': overlay.x_position,
        'y_position': overlay.y_position,
        'z_index': overlay.z_index,
        'rotation': overlay.rotation
    }
    
    return JsonResponse({
        'success': True,
        'overlay': overlay_data
    })


@login_required
@require_http_methods(["POST"])
def update_text_overlay(request, overlay_id):
    """
    Update text overlay properties
    """
    overlay = get_object_or_404(
        TextOverlay,
        id=overlay_id,
        creative__campaign__user=request.user
    )
    
    try:
        data = json.loads(request.body)
        
        # Update fields if provided
        for field, value in data.items():
            if hasattr(overlay, field) and field not in ['id', 'creative', 'created_at', 'updated_at']:
                setattr(overlay, field, value)
        
        overlay.save()
        
        return JsonResponse({
            'success': True,
            'styles': overlay.get_css_styles(),
            'style_string': overlay.get_style_string()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiger JSON-Request.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren des Overlays: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def delete_text_overlay(request, overlay_id):
    """
    Delete text overlay
    """
    overlay = get_object_or_404(
        TextOverlay,
        id=overlay_id,
        creative__campaign__user=request.user
    )
    
    try:
        overlay.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Overlay wurde gelöscht.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen des Overlays: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def creative_toggle_favorite(request, creative_id):
    """
    Creative als Favorit markieren/entfernen (AJAX)
    """
    creative = get_object_or_404(
        Creative, 
        id=creative_id, 
        campaign__user=request.user
    )
    
    creative.is_favorite = not creative.is_favorite
    creative.save()
    
    return JsonResponse({
        'success': True,
        'is_favorite': creative.is_favorite,
        'message': 'Favorit aktualisiert'
    })


@login_required
def bulk_actions(request):
    """
    Bulk-Aktionen für Creatives
    """
    if request.method == 'POST':
        form = BulkActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            creative_ids = form.cleaned_data['selected_creatives'].split(',')
            
            # Nur eigene Creatives
            creatives = Creative.objects.filter(
                id__in=creative_ids,
                campaign__user=request.user
            )
            
            if action == 'favorite':
                creatives.update(is_favorite=True)
                messages.success(request, f'{creatives.count()} Creatives als Favorit markiert.')
                
            elif action == 'unfavorite':
                creatives.update(is_favorite=False)
                messages.success(request, f'{creatives.count()} Favoriten entfernt.')
                
            elif action == 'delete':
                count = creatives.count()
                creatives.delete()
                messages.success(request, f'{count} Creatives gelöscht.')
                
            elif action == 'export':
                # TODO: Export-Funktionalität implementieren
                messages.info(request, 'Export-Funktionalität wird bald verfügbar sein.')
    
    return redirect(request.META.get('HTTP_REFERER', 'makeads:dashboard'))


@login_required
def job_status(request, job_id):
    """
    AJAX-Endpoint für Job-Status mit erweiterten Informationen
    """
    job = get_object_or_404(
        GenerationJob, 
        id=job_id, 
        campaign__user=request.user
    )
    
    # Berechne Fortschritt
    percentage = (job.generated_count / job.target_count * 100) if job.target_count > 0 else 0
    
    # Geschätzte verbleibende Zeit
    eta_seconds = None
    if job.status == 'processing' and job.generated_count > 0:
        elapsed = (timezone.now() - job.created_at).total_seconds()
        avg_time_per_item = elapsed / job.generated_count
        remaining_items = job.target_count - job.generated_count
        eta_seconds = int(remaining_items * avg_time_per_item)
    
    # Aktueller Schritt
    current_step = 'Initialisierung...'
    if job.status == 'processing':
        steps = [
            'Bereite KI-Modell vor...',
            'Generiere Werbetext...',
            'Erstelle Bild mit DALL-E...',
            'Optimiere Creative...',
            'Speichere Ergebnis...'
        ]
        step_index = job.generated_count % len(steps)
        current_step = steps[step_index]
    elif job.status == 'completed':
        current_step = 'Abgeschlossen!'
    elif job.status == 'failed':
        current_step = 'Fehler aufgetreten'
    
    # Timestamps that actually exist on the model
    created_at = job.created_at.isoformat() if job.created_at else None
    started_at = job.started_at.isoformat() if job.started_at else None
    completed_at = job.completed_at.isoformat() if job.completed_at else None

    return JsonResponse({
        'job_id': str(job.id),
        'status': job.status,
        'progress': job.generated_count,
        'target': job.target_count,
        'percentage': round(percentage, 1),
        'error_message': job.error_message,
        'eta_seconds': eta_seconds,
        'current_step': current_step,
        'created_at': created_at,
        'started_at': started_at,
        'completed_at': completed_at,
        'campaign_id': str(job.campaign.id),
        'job_type': job.get_job_type_display(),
    })


@login_required
@require_http_methods(["GET"])
def check_api_keys(request):
    """
    AJAX endpoint to check API key status and billing
    """
    try:
        api_client = CentralAPIClient(request.user)
        api_keys = api_client.validate_api_keys()
        
        # Zusätzlich Billing-Status prüfen wenn OpenAI verfügbar ist
        billing_status = {'status': 'unknown', 'message': 'Nicht geprüft'}
        if api_keys.get('openai', False):
            try:
                ai_generator = AICreativeGenerator(request.user)
                # Test-Bildgenerierung um Billing-Status zu prüfen
                test_result = ai_generator._generate_image("test", "openai")
                billing_status = ai_generator.get_billing_status()
            except Exception as e:
                logger.warning(f"Billing check failed: {str(e)}")
        
        return JsonResponse({
            'openai': api_keys.get('openai', False),
            'anthropic': api_keys.get('anthropic', False),
            'google': api_keys.get('google', False),
            'config_url': api_client.get_service_url(),
            'billing_status': billing_status
        })
    except Exception as e:
        logger.error(f"Error checking API keys: {str(e)}")
        return JsonResponse({
            'openai': False,
            'anthropic': False,
            'google': False,
            'error': str(e)
        }, status=500)


@login_required
def campaign_delete(request, campaign_id):
    """
    Kampagne löschen
    """
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'Kampagne "{campaign_name}" wurde gelöscht.')
        return redirect('makeads:dashboard')
    
    context = {
        'campaign': campaign,
    }
    
    return render(request, 'makeads/campaign_delete.html', context)
