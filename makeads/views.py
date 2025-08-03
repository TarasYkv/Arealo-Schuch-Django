from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
import json

from .models import Campaign, ReferenceImage, Creative, GenerationJob
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
    campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')
    
    # Statistiken
    total_campaigns = campaigns.count()
    total_creatives = Creative.objects.filter(campaign__user=request.user).count()
    active_jobs = GenerationJob.objects.filter(
        campaign__user=request.user,
        status__in=['queued', 'processing']
    ).count()
    
    # Neueste Kampagnen für Dashboard mit Favoriten-Zählung
    recent_campaigns = campaigns[:5]
    for campaign in recent_campaigns:
        campaign.favorite_count = campaign.creatives.filter(is_favorite=True).count()
    
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
    campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')
    
    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        campaigns = campaigns.filter(
            Q(name__icontains=search_query) |
            Q(basic_idea__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Favoriten-Anzahl für jede Kampagne berechnen (vor Paginierung)
    for campaign in campaigns:
        campaign.favorite_count = campaign.creatives.filter(is_favorite=True).count()
    
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
    Schritt 2: Referenzmaterial hinzufügen
    """
    campaign_id = request.session.get('campaign_id')
    if not campaign_id:
        messages.error(request, 'Bitte starten Sie mit Schritt 1.')
        return redirect('makeads:campaign_create_step1')
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    if request.method == 'POST':
        form = CampaignStep2Form(request.POST, instance=campaign)
        
        if form.is_valid():
            form.save()
            
            # Referenzbilder verarbeiten
            uploaded_files = request.FILES.getlist('reference_images')
            for uploaded_file in uploaded_files:
                ReferenceImage.objects.create(
                    campaign=campaign,
                    image=uploaded_file,
                    description=f"Referenzbild für {campaign.name}"
                )
            
            messages.success(request, 'Schritt 2 abgeschlossen! Konfigurieren Sie nun die Creative-Generierung.')
            return redirect('makeads:campaign_create_step3')
    else:
        form = CampaignStep2Form(instance=campaign)
    
    # Bereits hochgeladene Referenzbilder
    reference_images = campaign.reference_images.all()
    
    context = {
        'form': form,
        'campaign': campaign,
        'reference_images': reference_images,
        'step': 2,
        'step_title': 'Referenzmaterial',
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
    
    # Aktive Jobs
    active_jobs = campaign.generation_jobs.filter(
        status__in=['queued', 'processing']
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
    
    context = {
        'creative': creative,
        'revision_form': revision_form,
        'feedback_form': feedback_form,
        'similar_creatives': similar_creatives,
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
            
            try:
                revised_creative = ai_generator.revise_creative(
                    creative,
                    revision_text,
                    form.cleaned_data['revision_type']
                )
                
                if revised_creative:
                    messages.success(request, 'Creative wurde erfolgreich überarbeitet!')
                    return redirect('makeads:creative_detail', creative_id=revised_creative.id)
                else:
                    messages.error(request, 'Fehler bei der Überarbeitung.')
                    
            except Exception as e:
                messages.error(request, f'Fehler bei der Überarbeitung: {str(e)}')
    
    return redirect('makeads:creative_detail', creative_id=creative.id)


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
    
    return JsonResponse({
        'job_id': str(job.id),
        'status': job.status,
        'progress': job.generated_count,
        'target': job.target_count,
        'percentage': round(percentage, 1),
        'error_message': job.error_message,
        'eta_seconds': eta_seconds,
        'current_step': current_step,
        'created_at': job.created_at.isoformat(),
        'updated_at': job.updated_at.isoformat(),
        'campaign_id': str(job.campaign.id),
        'job_type': job.get_job_type_display(),
    })


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