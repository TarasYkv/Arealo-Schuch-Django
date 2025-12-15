"""
BlogPrep Views

Wizard-basierte Blog-Erstellung in 7 Schritten:
1. Keywords eingeben
2. Recherche & Gliederung
3. Content generieren
4. Bilder erstellen
5. Diagramm (optional)
6. Video-Skript (optional)
7. Export zu Shopify
"""

import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from .models import BlogPrepSettings, BlogPrepProject, BlogPrepGenerationLog
from .ai_services import ContentService, ImageService, VideoService
from shopify_manager.models import ShopifyStore, ShopifyBlog
from urllib.parse import urlparse, unquote
import re

logger = logging.getLogger(__name__)


def extract_product_name_from_url(url):
    """
    Extrahiert einen lesbaren Produktnamen aus einer URL.
    z.B. https://shop.de/produkt-premium-holz-schneidebrett -> Produkt Premium Holz Schneidebrett
    """
    try:
        parsed = urlparse(url)
        # Nimm den letzten Teil des Pfads
        path = parsed.path.rstrip('/')
        if path:
            slug = path.split('/')[-1]
            # Entferne Dateiendungen
            slug = re.sub(r'\.(html?|php|aspx?)$', '', slug, flags=re.IGNORECASE)
            # URL-Dekodierung
            slug = unquote(slug)
            # Ersetze Bindestriche und Unterstriche durch Leerzeichen
            name = re.sub(r'[-_]+', ' ', slug)
            # Entferne Zahlen am Ende (oft IDs)
            name = re.sub(r'\s+\d+$', '', name)
            # Kapitalisiere Wörter
            name = name.title()
            return name if name else url
        return url
    except Exception:
        return url


# ============================================================================
# Hilfsfunktionen
# ============================================================================

def get_user_settings(user):
    """Holt oder erstellt BlogPrepSettings für den User"""
    settings, created = BlogPrepSettings.objects.get_or_create(user=user)
    return settings


def get_company_info(settings):
    """Extrahiert Unternehmensinformationen aus den Settings"""
    return {
        'name': settings.company_name,
        'description': settings.company_description,
        'expertise': settings.company_expertise,
        'products': settings.product_info,
        'product_links': settings.scraped_product_data or []
    }


def log_generation(project, step, provider, model, prompt, response, success=True, error='', duration=0, tokens_in=0, tokens_out=0):
    """Erstellt einen Log-Eintrag für eine KI-Generierung"""
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


# ============================================================================
# Dashboard & Projekt-Liste
# ============================================================================

@login_required
def project_list(request):
    """Zeigt alle BlogPrep-Projekte des Users"""
    projects = BlogPrepProject.objects.filter(user=request.user).order_by('-created_at')
    settings = get_user_settings(request.user)

    # Statistiken
    stats = {
        'total': projects.count(),
        'in_progress': projects.exclude(status__in=['completed', 'published']).count(),
        'completed': projects.filter(status='completed').count(),
        'published': projects.filter(status='published').count()
    }

    context = {
        'projects': projects,
        'settings': settings,
        'stats': stats
    }
    return render(request, 'blogprep/project_list.html', context)


@login_required
def project_delete(request, project_id):
    """Löscht ein Projekt"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)

    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Projekt wurde gelöscht.')
        return redirect('blogprep:project_list')

    return render(request, 'blogprep/project_confirm_delete.html', {'project': project})


# ============================================================================
# Settings
# ============================================================================

@login_required
def settings_view(request):
    """Einstellungen für BlogPrep"""
    settings = get_user_settings(request.user)

    if request.method == 'POST':
        # Unternehmensinformationen
        settings.company_name = request.POST.get('company_name', '')
        settings.company_description = request.POST.get('company_description', '')
        settings.company_expertise = request.POST.get('company_expertise', '')
        settings.writing_style = request.POST.get('writing_style', 'du')

        # Produkte
        settings.product_info = request.POST.get('product_info', '')

        # Produktlinks als Liste mit Namen parsen
        product_links_text = request.POST.get('product_links', '')
        product_links = []
        scraped_products = []

        for line in product_links_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Format: "Produktname | URL" oder nur "URL"
            if '|' in line:
                parts = line.split('|', 1)
                name = parts[0].strip()
                url = parts[1].strip()
            else:
                url = line
                # Extrahiere Namen aus URL
                name = extract_product_name_from_url(url)

            if url.startswith('http'):
                product_links.append(url)
                scraped_products.append({
                    'name': name,
                    'url': url
                })

        settings.product_links = product_links
        settings.scraped_product_data = scraped_products

        # KI-Einstellungen
        settings.ai_provider = request.POST.get('ai_provider', 'openai')
        settings.ai_model = request.POST.get('ai_model', 'gpt-4o')
        settings.image_provider = request.POST.get('image_provider', 'gemini')
        settings.image_model = request.POST.get('image_model', 'imagen-3.0-generate-001')

        settings.save()
        messages.success(request, 'Einstellungen wurden gespeichert.')
        return redirect('blogprep:settings')

    # Text-Modell-Choices für Template
    model_choices = {
        'openai': BlogPrepSettings.OPENAI_MODEL_CHOICES,
        'gemini': BlogPrepSettings.GEMINI_MODEL_CHOICES,
    }

    # Modell-Beschreibungen
    model_descriptions = {
        'openai': BlogPrepSettings.OPENAI_MODEL_DESCRIPTIONS,
        'gemini': BlogPrepSettings.GEMINI_MODEL_DESCRIPTIONS,
    }

    # Bild-Modell-Choices für Template
    image_model_choices = {
        'gemini': BlogPrepSettings.GEMINI_IMAGE_MODEL_CHOICES,
        'dalle': BlogPrepSettings.DALLE_IMAGE_MODEL_CHOICES,
    }

    # Bild-Modell-Beschreibungen
    image_model_descriptions = {
        'gemini': BlogPrepSettings.GEMINI_IMAGE_MODEL_DESCRIPTIONS,
        'dalle': BlogPrepSettings.DALLE_IMAGE_MODEL_DESCRIPTIONS,
    }

    context = {
        'settings': settings,
        'model_choices': model_choices,
        'model_descriptions': model_descriptions,
        'image_model_choices': image_model_choices,
        'image_model_descriptions': image_model_descriptions,
        'product_links_text': '\n'.join(
            f"{p['name']} | {p['url']}" for p in settings.scraped_product_data
        ) if settings.scraped_product_data else '\n'.join(settings.product_links) if settings.product_links else ''
    }
    return render(request, 'blogprep/settings.html', context)


@login_required
@require_POST
def api_scrape_product_links(request):
    """Scrapt Produktinformationen von den konfigurierten Links"""
    settings = get_user_settings(request.user)

    if not settings.product_links:
        return JsonResponse({'success': False, 'error': 'Keine Produktlinks konfiguriert'})

    # TODO: Implementiere Web-Scraping
    # Hier würde das Scraping der Produktlinks stattfinden

    return JsonResponse({
        'success': True,
        'message': f'{len(settings.product_links)} Links werden analysiert...'
    })


# ============================================================================
# Wizard Step 1: Keywords
# ============================================================================

@login_required
def wizard_step1(request, project_id=None):
    """Schritt 1: Keywords eingeben"""
    settings = get_user_settings(request.user)

    # Existierendes Projekt laden oder neues erstellen
    if project_id:
        project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    else:
        project = None

    if request.method == 'POST':
        main_keyword = request.POST.get('main_keyword', '').strip()
        secondary_keywords_text = request.POST.get('secondary_keywords', '')

        if not main_keyword:
            messages.error(request, 'Bitte gib ein Hauptkeyword ein.')
            return render(request, 'blogprep/wizard/step1_keywords.html', {
                'project': project,
                'settings': settings,
                'step': 1
            })

        # Parse sekundäre Keywords
        secondary_keywords = [
            kw.strip() for kw in secondary_keywords_text.replace('\n', ',').split(',')
            if kw.strip()
        ]

        # Projekt erstellen oder aktualisieren
        if not project:
            project = BlogPrepProject.objects.create(
                user=request.user,
                main_keyword=main_keyword,
                secondary_keywords=secondary_keywords,
                title=f"Blog: {main_keyword}",
                status='step1'
            )
        else:
            project.main_keyword = main_keyword
            project.secondary_keywords = secondary_keywords
            project.status = 'step1'
            project.save()

        return redirect('blogprep:wizard_step2', project_id=project.id)

    context = {
        'project': project,
        'settings': settings,
        'step': 1
    }
    return render(request, 'blogprep/wizard/step1_keywords.html', context)


@login_required
@require_POST
def api_suggest_keywords(request):
    """API: Schlägt sekundäre Keywords vor"""
    main_keyword = request.POST.get('main_keyword', '')

    if not main_keyword:
        return JsonResponse({'success': False, 'error': 'Kein Keyword angegeben'})

    settings = get_user_settings(request.user)
    content_service = ContentService(request.user, settings)

    result = content_service.suggest_keywords(main_keyword)

    return JsonResponse(result)


# ============================================================================
# Wizard Step 2: Recherche & Gliederung
# ============================================================================

@login_required
def wizard_step2(request, project_id):
    """Schritt 2: Recherche und Gliederung"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    if request.method == 'POST':
        # Speichere editierte Gliederung
        outline_json = request.POST.get('outline', '[]')
        try:
            project.outline = json.loads(outline_json)
        except json.JSONDecodeError:
            project.outline = []

        project.status = 'step2'
        project.save()

        return redirect('blogprep:wizard_step3', project_id=project.id)

    context = {
        'project': project,
        'settings': settings,
        'step': 2
    }
    return render(request, 'blogprep/wizard/step2_research.html', context)


@login_required
@require_POST
def api_run_research(request, project_id):
    """API: Führt echte Web-Recherche durch"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    # Echte Web-Recherche durchführen
    from .ai_services import WebResearchService

    research_service = WebResearchService()
    web_results = research_service.search_and_analyze(project.main_keyword, num_results=5)

    if not web_results['success']:
        logger.warning(f"Web-Recherche fehlgeschlagen: {web_results.get('error')}")
        # Fallback: Leere Suchergebnisse, KI analysiert nur Keyword
        search_results = []
    else:
        search_results = web_results.get('search_results', [])
        logger.info(f"Web-Recherche erfolgreich: {len(search_results)} Ergebnisse mit Inhalt")

    # Content Service für KI-Analyse
    content_service = ContentService(request.user, settings)

    # Analyse der echten Suchergebnisse durchführen
    result = content_service.analyze_research(project.main_keyword, search_results)

    if result['success']:
        # Speichere auch die Quellen
        result['data']['sources'] = [
            {
                'title': r.get('title', ''),
                'url': r.get('url', ''),
                'position': r.get('position', 0)
            }
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

    return JsonResponse(result)


@login_required
@require_POST
def api_generate_outline(request, project_id):
    """API: Generiert Blog-Gliederung"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    content_service = ContentService(request.user, settings)

    result = content_service.generate_outline(
        project.main_keyword,
        project.secondary_keywords,
        project.research_data or {}
    )

    if result['success']:
        project.outline = result['data'].get('outline', [])
        project.save()

        log_generation(
            project, 'outline', settings.ai_provider, settings.ai_model,
            f'Outline for: {project.main_keyword}',
            json.dumps(result['data']),
            duration=result.get('duration', 0),
            tokens_in=result.get('tokens_input', 0),
            tokens_out=result.get('tokens_output', 0)
        )

    return JsonResponse(result)


# ============================================================================
# Wizard Step 3: Content generieren
# ============================================================================

@login_required
def wizard_step3(request, project_id):
    """Schritt 3: Content generieren"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    if request.method == 'POST':
        # Speichere editierten Content
        project.content_intro = request.POST.get('content_intro', '')
        project.content_main = request.POST.get('content_main', '')
        project.content_tips = request.POST.get('content_tips', '')
        project.seo_title = request.POST.get('seo_title', '')
        project.meta_description = request.POST.get('meta_description', '')
        project.summary = request.POST.get('summary', '')

        # FAQs
        faqs_json = request.POST.get('faqs', '[]')
        try:
            project.faqs = json.loads(faqs_json)
        except json.JSONDecodeError:
            project.faqs = []

        project.status = 'step3'
        project.save()

        return redirect('blogprep:wizard_step4', project_id=project.id)

    context = {
        'project': project,
        'settings': settings,
        'step': 3
    }
    return render(request, 'blogprep/wizard/step3_content.html', context)


@login_required
@require_POST
def api_generate_content_section(request, project_id):
    """API: Generiert einen Content-Abschnitt"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    section_type = request.POST.get('section_type', 'intro')  # intro, main, tips

    content_service = ContentService(request.user, settings)
    company_info = get_company_info(settings)

    # Finde den passenden Outline-Abschnitt
    outline_section = {}
    for item in project.outline:
        if item.get('section') == section_type:
            outline_section = item
            break

    result = content_service.generate_content_section(
        section_type,
        project.main_keyword,
        outline_section,
        company_info,
        settings.writing_style
    )

    if result['success']:
        # Speichere in passendem Feld
        if section_type == 'intro':
            project.content_intro = result['content']
        elif section_type == 'main':
            project.content_main = result['content']
        elif section_type == 'tips':
            project.content_tips = result['content']

        project.save()

        log_generation(
            project, f'content_{section_type}', settings.ai_provider, settings.ai_model,
            f'{section_type} for: {project.main_keyword}',
            result['content'][:2000],
            duration=result.get('duration', 0),
            tokens_in=result.get('tokens_input', 0),
            tokens_out=result.get('tokens_output', 0)
        )

    return JsonResponse(result)


@login_required
@require_POST
def api_generate_faqs(request, project_id):
    """API: Generiert FAQs"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    content_service = ContentService(request.user, settings)

    result = content_service.generate_faqs(
        project.main_keyword,
        project.research_data or {},
        project.summary
    )

    if result['success']:
        project.faqs = result['faqs']
        project.save()

        log_generation(
            project, 'faqs', settings.ai_provider, settings.ai_model,
            f'FAQs for: {project.main_keyword}',
            json.dumps(result['faqs']),
            duration=result.get('duration', 0),
            tokens_in=result.get('tokens_input', 0),
            tokens_out=result.get('tokens_output', 0)
        )

    return JsonResponse(result)


@login_required
@require_POST
def api_generate_seo_meta(request, project_id):
    """API: Generiert SEO-Meta-Daten"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    content_service = ContentService(request.user, settings)

    # Erstelle Zusammenfassung aus Content
    content_summary = f"{project.content_intro[:500] if project.content_intro else ''}"

    result = content_service.generate_seo_meta(project.main_keyword, content_summary)

    if result['success']:
        data = result['data']
        project.seo_title = data.get('title', '')[:70]
        project.meta_description = data.get('description', '')[:160]
        project.summary = data.get('summary', '')
        project.save()

        log_generation(
            project, 'seo', settings.ai_provider, settings.ai_model,
            f'SEO for: {project.main_keyword}',
            json.dumps(data),
            duration=result.get('duration', 0),
            tokens_in=result.get('tokens_input', 0),
            tokens_out=result.get('tokens_output', 0)
        )

    return JsonResponse(result)


# ============================================================================
# Wizard Step 4: Bilder
# ============================================================================

@login_required
def wizard_step4(request, project_id):
    """Schritt 4: Bilder erstellen"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    if request.method == 'POST':
        project.status = 'step4'
        project.save()
        return redirect('blogprep:wizard_step5', project_id=project.id)

    context = {
        'project': project,
        'settings': settings,
        'step': 4,
        # Bild-Modell Auswahl
        'image_providers': BlogPrepSettings.IMAGE_PROVIDER_CHOICES,
        'gemini_image_models': BlogPrepSettings.GEMINI_IMAGE_MODEL_CHOICES,
        'dalle_image_models': BlogPrepSettings.DALLE_IMAGE_MODEL_CHOICES,
    }
    return render(request, 'blogprep/wizard/step4_images.html', context)


@login_required
@require_POST
def api_generate_title_image(request, project_id):
    """API: Generiert das Titelbild"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    # Überschreibe Modell aus Request (falls angegeben)
    custom_provider = request.POST.get('image_provider')
    custom_model = request.POST.get('image_model')

    if custom_provider:
        settings.image_provider = custom_provider
    if custom_model:
        settings.image_model = custom_model

    image_service = ImageService(request.user, settings)

    result = image_service.generate_title_image(
        project.main_keyword,
        project.summary
    )

    if result['success']:
        # Speichere Bild
        saved = image_service.save_image_to_field(
            result['image_data'],
            project.title_image,
            f"blogprep_title_{project.id}"
        )

        if saved:
            project.title_image_prompt = result.get('prompt', '')
            project.save()

            log_generation(
                project, 'image_title', settings.image_provider, settings.image_model,
                result.get('prompt', ''),
                'Image generated successfully',
                duration=result.get('duration', 0)
            )

            return JsonResponse({
                'success': True,
                'image_url': project.title_image.url if project.title_image else None
            })

    return JsonResponse(result)


@login_required
@require_POST
def api_generate_section_image(request, project_id):
    """API: Generiert ein Abschnittsbild"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    section_text = request.POST.get('section_text', '')
    section_name = request.POST.get('section_name', 'section')

    # Überschreibe Modell aus Request (falls angegeben)
    custom_provider = request.POST.get('image_provider')
    custom_model = request.POST.get('image_model')

    if custom_provider:
        settings.image_provider = custom_provider
    if custom_model:
        settings.image_model = custom_model

    if not section_text:
        return JsonResponse({'success': False, 'error': 'Kein Text ausgewählt'})

    image_service = ImageService(request.user, settings)

    result = image_service.generate_section_image(section_text, project.main_keyword)

    if result['success']:
        # Speichere Bild als Datei für Shopify-kompatible URLs
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{project.id}_{section_name}_{unique_id}"
        image_url = image_service.save_image_to_media(result['image_data'], filename)

        # Füge zu section_images hinzu (mit URL UND base64 für lokale Anzeige)
        section_images = project.section_images or []
        section_images.append({
            'section': section_name,
            'image_data': result['image_data'],
            'image_url': image_url,  # URL für Shopify Export
            'prompt': result.get('prompt', '')
        })
        project.section_images = section_images
        project.save()

        log_generation(
            project, 'image_section', settings.image_provider, settings.image_model,
            result.get('prompt', ''),
            'Section image generated',
            duration=result.get('duration', 0)
        )

        # Füge URL zur Response hinzu
        result['image_url'] = image_url

    return JsonResponse(result)


@login_required
@require_POST
def api_suggest_section_images(request, project_id):
    """API: Generiert Vorschläge für Abschnittsbilder basierend auf dem Content"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    content_service = ContentService(request.user, settings)

    # Sammle Content für jeden Abschnitt
    sections_content = {
        'intro': project.content_intro or '',
        'main': project.content_main or '',
        'tips': project.content_tips or '',
    }

    # Generiere Vorschläge mit KI
    system_prompt = """Du bist ein Experte für visuelle Content-Strategie.
Erstelle prägnante Bildbeschreibungen für Blog-Abschnitte, die sich gut für KI-Bildgenerierung eignen."""

    suggestions = {}  # Dict mit section als Key

    section_labels = {
        'intro': 'Einleitung',
        'main': 'Hauptteil',
        'tips': 'Tipps'
    }

    for section_name, content in sections_content.items():
        if not content or len(content) < 100:
            continue

        # Kürze Content für Prompt
        content_preview = content[:1000] if len(content) > 1000 else content

        user_prompt = f"""Erstelle eine Bildbeschreibung für den Abschnitt "{section_labels.get(section_name, section_name)}" eines Blogs zum Thema "{project.main_keyword}".

CONTENT DES ABSCHNITTS:
{content_preview}

ANFORDERUNGEN:
- 2-3 Sätze, max. 150 Wörter
- Beschreibe ein konkretes, visualisierbares Motiv
- Passend zum Thema und Ton des Abschnitts
- Keine Texte oder Schrift im Bild
- Professionell, modern, ansprechend

Antworte NUR mit der Bildbeschreibung (keine Erklärung, kein JSON)."""

        result = content_service._call_llm(system_prompt, user_prompt, max_tokens=200, temperature=0.7)

        if result['success']:
            suggestions[section_name] = result['content'].strip()

    return JsonResponse({
        'success': True,
        'suggestions': suggestions
    })


# ============================================================================
# Wizard Step 5: Diagramm (Optional)
# ============================================================================

@login_required
def wizard_step5(request, project_id):
    """Schritt 5: Diagramm erstellen (optional)"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    if request.method == 'POST':
        skip = request.POST.get('skip_diagram') == 'true'

        if skip:
            project.skip_diagram = True
        else:
            # Speichere Diagramm-Daten
            diagram_type = request.POST.get('diagram_type', '')
            diagram_data_json = request.POST.get('diagram_data', '{}')

            try:
                project.diagram_data = json.loads(diagram_data_json)
            except json.JSONDecodeError:
                project.diagram_data = {}

            project.diagram_type = diagram_type

        project.status = 'step5'
        project.save()

        return redirect('blogprep:wizard_step6', project_id=project.id)

    context = {
        'project': project,
        'settings': settings,
        'step': 5,
        'diagram_types': BlogPrepProject.DIAGRAM_TYPE_CHOICES,
        # Bild-Modell Auswahl
        'image_providers': BlogPrepSettings.IMAGE_PROVIDER_CHOICES,
        'gemini_image_models': BlogPrepSettings.GEMINI_IMAGE_MODEL_CHOICES,
        'dalle_image_models': BlogPrepSettings.DALLE_IMAGE_MODEL_CHOICES,
    }
    return render(request, 'blogprep/wizard/step5_diagram.html', context)


@login_required
@require_POST
def api_analyze_for_diagram(request, project_id):
    """API: Analysiert Content für Diagramm-Vorschlag"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    video_service = VideoService(request.user, settings)

    # Kombiniere Content für Analyse
    full_content = f"{project.content_intro}\n{project.content_main}\n{project.content_tips}"

    result = video_service.analyze_for_diagram(full_content, project.main_keyword)

    if result['success']:
        project.diagram_data = result['data']
        project.diagram_type = result['data'].get('diagram_type', 'bar')
        project.save()

        log_generation(
            project, 'diagram', settings.ai_provider, settings.ai_model,
            f'Diagram analysis for: {project.main_keyword}',
            json.dumps(result['data']),
            duration=result.get('duration', 0),
            tokens_in=result.get('tokens_input', 0),
            tokens_out=result.get('tokens_output', 0)
        )

    return JsonResponse(result)


@login_required
@require_POST
def api_generate_diagram_image(request, project_id):
    """API: Generiert Diagramm als Bild"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    # Überschreibe Modell aus Request (falls angegeben)
    custom_provider = request.POST.get('image_provider')
    custom_model = request.POST.get('image_model')

    if custom_provider:
        settings.image_provider = custom_provider
    if custom_model:
        settings.image_model = custom_model

    if not project.diagram_data:
        return JsonResponse({'success': False, 'error': 'Keine Diagramm-Daten vorhanden'})

    image_service = ImageService(request.user, settings)

    result = image_service.generate_diagram_image(
        project.diagram_type,
        project.diagram_data,
        project.main_keyword
    )

    if result['success']:
        saved = image_service.save_image_to_field(
            result['image_data'],
            project.diagram_image,
            f"blogprep_diagram_{project.id}"
        )

        if saved:
            project.save()
            return JsonResponse({
                'success': True,
                'image_url': project.diagram_image.url if project.diagram_image else None
            })

    return JsonResponse(result)


# ============================================================================
# Wizard Step 6: Video-Skript (Optional)
# ============================================================================

@login_required
def wizard_step6(request, project_id):
    """Schritt 6: Video-Skript erstellen (optional)"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    if request.method == 'POST':
        skip = request.POST.get('skip_video') == 'true'

        if skip:
            project.skip_video = True
        else:
            project.video_script = request.POST.get('video_script', '')
            project.video_duration = float(request.POST.get('video_duration', 5))

        project.status = 'step6'
        project.save()

        return redirect('blogprep:wizard_step7', project_id=project.id)

    context = {
        'project': project,
        'settings': settings,
        'step': 6
    }
    return render(request, 'blogprep/wizard/step6_video.html', context)


@login_required
@require_POST
def api_generate_video_script(request, project_id):
    """API: Generiert Video-Skript"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    duration = float(request.POST.get('duration', 5))  # Float für Sekunden (0.25 = 15s)

    video_service = VideoService(request.user, settings)

    # Kombiniere Content
    full_content = f"{project.content_intro}\n{project.content_main}\n{project.content_tips}"

    result = video_service.generate_video_script(
        duration,
        full_content,
        project.main_keyword,
        settings.company_name
    )

    if result['success']:
        project.video_script = result['script']
        project.video_duration = duration
        project.save()

        log_generation(
            project, 'video_script', settings.ai_provider, settings.ai_model,
            f'Video script ({duration} min) for: {project.main_keyword}',
            result['script'][:2000],
            duration=result.get('duration', 0),
            tokens_in=result.get('tokens_input', 0),
            tokens_out=result.get('tokens_output', 0)
        )

    return JsonResponse(result)


# ============================================================================
# Wizard Step 7: Export zu Shopify
# ============================================================================

@login_required
def wizard_step7(request, project_id):
    """Schritt 7: Export zu Shopify"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    # Verfügbare Stores und Blogs
    stores = ShopifyStore.objects.filter(user=request.user, is_active=True)
    blogs = ShopifyBlog.objects.filter(store__user=request.user)

    if request.method == 'POST':
        store_id = request.POST.get('store_id')
        blog_id = request.POST.get('blog_id')

        if store_id:
            project.shopify_store = ShopifyStore.objects.get(id=store_id, user=request.user)
        if blog_id:
            project.shopify_blog = ShopifyBlog.objects.get(id=blog_id)

        project.status = 'step7'
        project.save()

        # HTML generieren
        project.generate_full_html()
        project.save()

        messages.success(request, 'Projekt ist bereit zum Export!')

    context = {
        'project': project,
        'settings': settings,
        'stores': stores,
        'blogs': blogs,
        'step': 7
    }
    return render(request, 'blogprep/wizard/step7_export.html', context)


@login_required
@require_POST
def api_export_to_shopify(request, project_id):
    """API: Exportiert Blog zu Shopify als Entwurf"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)

    if not project.shopify_store or not project.shopify_blog:
        return JsonResponse({
            'success': False,
            'error': 'Bitte wähle einen Store und Blog aus'
        })

    try:
        import base64
        import requests
        from .shopify_files import ShopifyFilesService

        store = project.shopify_store
        # Base URL für Fallback (falls Shopify Upload fehlschlägt)
        base_url = request.build_absolute_uri('/').rstrip('/')

        # Schritt 1: Abschnittsbilder zu Shopify hochladen (falls vorhanden)
        if project.section_images:
            shopify_files = ShopifyFilesService(store)
            updated_section_images = []

            for idx, img in enumerate(project.section_images):
                section_name = img.get('section', f'section_{idx}')
                image_data = img.get('image_data')

                # Nur hochladen wenn Base64-Daten vorhanden und noch keine Shopify-URL
                if image_data and not img.get('shopify_cdn_url'):
                    filename = f"blogprep_{project.id}_{section_name}"
                    alt_text = f"{project.main_keyword} - {section_name}"

                    success, cdn_url, file_id = shopify_files.upload_image_from_base64(
                        image_data, filename, alt_text
                    )

                    if success:
                        img['shopify_cdn_url'] = cdn_url
                        img['shopify_file_id'] = file_id
                        # Setze image_url auf CDN URL für HTML-Generierung
                        img['image_url'] = cdn_url
                        logger.info(f"Bild '{section_name}' zu Shopify hochgeladen: {cdn_url}")
                    else:
                        logger.warning(f"Shopify Upload fehlgeschlagen für '{section_name}': {cdn_url}")
                        # Fallback: Behalte lokale URL wenn vorhanden

                updated_section_images.append(img)

            project.section_images = updated_section_images
            project.save()

        # Schritt 2: Diagrammbild zu Shopify hochladen (falls vorhanden)
        diagram_cdn_url = None
        if project.diagram_image and not project.skip_diagram:
            try:
                shopify_files = ShopifyFilesService(store)
                with project.diagram_image.open('rb') as img_file:
                    diagram_data = base64.b64encode(img_file.read()).decode('utf-8')
                    filename = f"blogprep_{project.id}_diagram"
                    alt_text = f"{project.main_keyword} - Diagramm"

                    success, cdn_url, file_id = shopify_files.upload_image_from_base64(
                        diagram_data, filename, alt_text
                    )

                    if success:
                        diagram_cdn_url = cdn_url
                        logger.info(f"Diagramm zu Shopify hochgeladen: {cdn_url}")
            except Exception as e:
                logger.warning(f"Diagramm Upload fehlgeschlagen: {e}")

        # Generiere HTML mit Shopify CDN URLs
        # Titelbild NICHT im body_html (wird als Article Image gesetzt)
        project.generate_full_html(base_url=base_url, include_title_image=False, include_section_images=True)

        # Ersetze Diagramm-URL im HTML durch Shopify CDN URL
        if diagram_cdn_url and project.diagram_image:
            local_diagram_url = project.diagram_image.url
            # Ersetze sowohl relative als auch absolute URLs
            project.full_html_content = project.full_html_content.replace(
                f'src="{local_diagram_url}"',
                f'src="{diagram_cdn_url}"'
            )
            project.full_html_content = project.full_html_content.replace(
                f'src="{base_url}{local_diagram_url}"',
                f'src="{diagram_cdn_url}"'
            )

        project.save()

        # Shopify API Call
        store = project.shopify_store
        blog = project.shopify_blog

        # Erstelle Article via Shopify Admin API
        url = f"https://{store.shop_domain}/admin/api/2024-01/blogs/{blog.shopify_id}/articles.json"

        headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json'
        }

        article_data = {
            'article': {
                'title': project.seo_title or project.title,
                'body_html': project.full_html_content,
                'summary_html': project.summary,
                'published': False,  # Als Entwurf
                'tags': ', '.join(project.secondary_keywords) if project.secondary_keywords else ''
            }
        }

        # Titelbild als Article Featured Image (nicht im body_html)
        if project.title_image:
            try:
                # Lese Bild und konvertiere zu Base64
                with project.title_image.open('rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')
                    article_data['article']['image'] = {
                        'attachment': image_data,
                        'alt': project.seo_title or project.title
                    }
            except Exception as img_error:
                logger.warning(f"Could not read title image: {img_error}")
                # Fallback: Verwende URL wenn lokales Lesen fehlschlägt
                img_url = f"{base_url}{project.title_image.url}"
                article_data['article']['image'] = {
                    'src': img_url,
                    'alt': project.seo_title or project.title
                }

        # Meta-Description als Metafield
        if project.meta_description:
            article_data['article']['metafields'] = [{
                'namespace': 'global',
                'key': 'description_tag',
                'value': project.meta_description,
                'type': 'single_line_text_field'
            }]

        response = requests.post(url, json=article_data, headers=headers, timeout=30)

        if response.status_code in [200, 201]:
            result = response.json()
            article_id = result.get('article', {}).get('id')

            project.shopify_article_id = str(article_id)
            project.exported_at = timezone.now()
            project.status = 'completed'
            project.save()

            return JsonResponse({
                'success': True,
                'article_id': article_id,
                'message': 'Blog wurde als Entwurf zu Shopify exportiert!'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Shopify API Fehler: {response.text}'
            })

    except Exception as e:
        logger.error(f"Shopify export error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def api_get_blogs_for_store(request, store_id):
    """API: Gibt Blogs für einen Store zurück"""
    blogs = ShopifyBlog.objects.filter(
        store_id=store_id,
        store__user=request.user
    ).values('id', 'title', 'shopify_id')

    return JsonResponse({'blogs': list(blogs)})


@login_required
def api_get_server_images(request, project_id):
    """API: Gibt verfügbare Server-Bilder aus imageforge zurück"""
    from imageforge.models import ImageGeneration, ProductMockup

    # Parameter für Filterung
    image_type = request.GET.get('type', 'all')  # 'all', 'generated', 'mockup'
    limit = int(request.GET.get('limit', 50))

    images = []

    # ImageGeneration Bilder
    if image_type in ['all', 'generated']:
        generations = ImageGeneration.objects.filter(
            user=request.user,
            generated_image__isnull=False
        ).exclude(
            generated_image=''
        ).order_by('-created_at')[:limit]

        for gen in generations:
            if gen.generated_image:
                images.append({
                    'id': f'gen_{gen.id}',
                    'type': 'generated',
                    'url': gen.generated_image.url,
                    'mode': gen.mode_display,
                    'prompt': gen.background_prompt[:100] if gen.background_prompt else '',
                    'created_at': gen.created_at.strftime('%d.%m.%Y %H:%M'),
                    'is_favorite': gen.is_favorite
                })

    # ProductMockup Bilder
    if image_type in ['all', 'mockup']:
        mockups = ProductMockup.objects.filter(
            user=request.user,
            mockup_image__isnull=False
        ).exclude(
            mockup_image=''
        ).order_by('-updated_at')[:limit]

        for mockup in mockups:
            if mockup.mockup_image:
                images.append({
                    'id': f'mockup_{mockup.id}',
                    'type': 'mockup',
                    'url': mockup.mockup_image.url,
                    'name': mockup.name or f'Mockup: {mockup.text_content[:30]}',
                    'text': mockup.text_content,
                    'created_at': mockup.updated_at.strftime('%d.%m.%Y %H:%M'),
                    'is_favorite': mockup.is_favorite
                })

    # Sortiere nach Erstellungsdatum (neueste zuerst), Favoriten bevorzugen
    images.sort(key=lambda x: (not x.get('is_favorite', False), x.get('created_at', '')), reverse=True)

    return JsonResponse({
        'success': True,
        'images': images[:limit],
        'total': len(images)
    })


@login_required
@require_POST
def api_use_server_image(request, project_id):
    """API: Verwendet ein Server-Bild als Abschnittsbild"""
    from imageforge.models import ImageGeneration, ProductMockup
    import base64
    import uuid

    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)

    image_id = request.POST.get('image_id', '')
    section_name = request.POST.get('section_name', 'section')

    if not image_id:
        return JsonResponse({'success': False, 'error': 'Keine Bild-ID angegeben'})

    try:
        # Bestimme Bildtyp und ID
        if image_id.startswith('gen_'):
            gen_id = int(image_id.replace('gen_', ''))
            gen = ImageGeneration.objects.get(id=gen_id, user=request.user)
            image_field = gen.generated_image
            prompt = gen.background_prompt or ''
        elif image_id.startswith('mockup_'):
            mockup_id = int(image_id.replace('mockup_', ''))
            mockup = ProductMockup.objects.get(id=mockup_id, user=request.user)
            image_field = mockup.mockup_image
            prompt = mockup.text_content or ''
        else:
            return JsonResponse({'success': False, 'error': 'Ungültiger Bildtyp'})

        if not image_field:
            return JsonResponse({'success': False, 'error': 'Bild nicht gefunden'})

        # Lese Bild und konvertiere zu Base64
        with image_field.open('rb') as img_file:
            image_data = base64.b64encode(img_file.read()).decode('utf-8')

        # Generiere eindeutige ID
        unique_id = str(uuid.uuid4())[:8]

        # Füge zu section_images hinzu
        section_images = project.section_images or []
        section_images.append({
            'section': section_name,
            'image_data': image_data,
            'image_url': image_field.url,
            'prompt': prompt,
            'source': 'server'
        })
        project.section_images = section_images
        project.save()

        log_generation(
            project, 'image_section', 'server', 'imageforge',
            f'Server image used: {image_id}',
            'Section image from server',
            duration=0
        )

        return JsonResponse({
            'success': True,
            'image_data': image_data,
            'image_url': image_field.url,
            'section': section_name
        })

    except (ImageGeneration.DoesNotExist, ProductMockup.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Bild nicht gefunden'})
    except Exception as e:
        logger.error(f"Error using server image: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# Ergebnis-Ansicht
# ============================================================================

@login_required
def project_result(request, project_id):
    """Zeigt das fertige Ergebnis eines Projekts"""
    project = get_object_or_404(BlogPrepProject, id=project_id, user=request.user)
    settings = get_user_settings(request.user)

    # Generiere HTML falls noch nicht geschehen
    if not project.full_html_content:
        project.generate_full_html()
        project.save()

    # Logs für Statistiken
    logs = project.generation_logs.all()
    total_tokens = sum(log.tokens_input + log.tokens_output for log in logs)
    total_duration = sum(log.duration_seconds for log in logs)

    context = {
        'project': project,
        'settings': settings,
        'logs': logs,
        'total_tokens': total_tokens,
        'total_duration': round(total_duration, 2),
        'word_count': project.get_word_count()
    }
    return render(request, 'blogprep/project_result.html', context)
