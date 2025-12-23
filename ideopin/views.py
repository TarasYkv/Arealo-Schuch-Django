import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from PIL import Image

from .models import PinProject, PinSettings, Pin
from .forms import (
    Step1KeywordsForm, Step2TextForm, Step3ImageForm,
    Step4LinkForm, Step5SEOForm, PinSettingsForm
)

logger = logging.getLogger(__name__)


def resize_and_crop_to_format(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Skaliert ein Bild auf das Zielformat OHNE Text abzuschneiden.

    Strategie:
    1. Bild so skalieren, dass es komplett ins Zielformat passt (letterbox)
    2. Leere Bereiche mit passender Hintergrundfarbe füllen
    """
    orig_width, orig_height = img.size
    target_ratio = target_width / target_height
    orig_ratio = orig_width / orig_height

    if orig_ratio > target_ratio:
        # Bild ist breiter als Ziel - auf Breite skalieren, oben/unten Padding
        new_width = target_width
        new_height = int(orig_height * (target_width / orig_width))
    else:
        # Bild ist höher als Ziel - auf Höhe skalieren, links/rechts Padding
        new_height = target_height
        new_width = int(orig_width * (target_height / orig_height))

    # Skalieren mit hoher Qualität
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Hintergrundfarbe aus den Bildrändern ermitteln (Durchschnitt der Ecken)
    bg_color = get_dominant_edge_color(img)

    # Neues Bild mit Hintergrundfarbe erstellen
    result = Image.new('RGB', (target_width, target_height), bg_color)

    # Skaliertes Bild mittig platzieren
    paste_x = (target_width - new_width) // 2
    paste_y = (target_height - new_height) // 2
    result.paste(img, (paste_x, paste_y))

    return result


def get_dominant_edge_color(img: Image.Image) -> tuple:
    """
    Ermittelt die dominante Farbe an den Bildrändern.
    Verwendet die Durchschnittsfarbe der äußeren Pixel.
    """
    width, height = img.size
    pixels = []

    # Obere und untere Kante samplen
    for x in range(0, width, max(1, width // 20)):
        pixels.append(img.getpixel((x, 0)))
        pixels.append(img.getpixel((x, height - 1)))

    # Linke und rechte Kante samplen
    for y in range(0, height, max(1, height // 20)):
        pixels.append(img.getpixel((0, y)))
        pixels.append(img.getpixel((width - 1, y)))

    # Durchschnitt berechnen
    if not pixels:
        return (0, 0, 0)

    # Handle both RGB and RGBA
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)

    return (r, g, b)


# ==================== WIZARD VIEWS ====================

@login_required
def wizard_step1(request, project_id=None):
    """Schritt 1: Keywords eingeben"""
    project = None
    if project_id:
        project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if request.method == 'POST':
        form = Step1KeywordsForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.status = 'step1'
            project.save()
            return redirect('ideopin:wizard_step2', project_id=project.id)
    else:
        form = Step1KeywordsForm(instance=project)

    context = {
        'form': form,
        'project': project,
        'step': 1,
        'total_steps': 6,
    }
    return render(request, 'ideopin/wizard/step1_keywords.html', context)


@login_required
def wizard_step2(request, project_id):
    """Schritt 2: Text-Overlay generieren und bearbeiten"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if request.method == 'POST':
        form = Step2TextForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save(commit=False)
            project.status = 'step2'
            project.save()
            return redirect('ideopin:wizard_step3', project_id=project.id)
    else:
        # Load user defaults if no overlay_text yet
        if not project.overlay_text:
            try:
                settings = PinSettings.objects.get(user=request.user)
                project.text_font = settings.default_font
                project.text_size = settings.default_text_size
                project.text_color = settings.default_text_color
                project.text_position = settings.default_text_position
                project.text_background_color = settings.default_text_background_color
                project.text_background_opacity = settings.default_text_background_opacity
            except PinSettings.DoesNotExist:
                pass
        form = Step2TextForm(instance=project)

    context = {
        'form': form,
        'project': project,
        'step': 2,
        'total_steps': 6,
    }
    return render(request, 'ideopin/wizard/step2_text.html', context)


@login_required
def wizard_step3(request, project_id):
    """Schritt 3: Bild erstellen mit Ideogram"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if request.method == 'POST':
        form = Step3ImageForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            project = form.save(commit=False)

            # Eigenes Bild hochgeladen? -> Als generated_image speichern
            custom_image = form.cleaned_data.get('custom_image')
            if custom_image:
                project.generated_image = custom_image

            # Pin-Anzahl verarbeiten
            pin_count = int(request.POST.get('pin_count', 1))
            project.pin_count = pin_count

            project.status = 'step3'
            project.save()

            # Bei Single-Pin: Sicherstellen dass mindestens ein Pin existiert
            if project.pins.count() == 0:
                Pin.objects.create(
                    project=project,
                    position=1,
                    overlay_text=project.overlay_text,
                    background_description=project.background_description,
                    generated_image=project.generated_image,
                    final_image=project.final_image
                )

            return redirect('ideopin:wizard_step4', project_id=project.id)
    else:
        # Load default format from user settings
        if not project.pin_format or project.pin_format == '1000x1500':
            try:
                settings = PinSettings.objects.get(user=request.user)
                project.pin_format = settings.default_pin_format
            except PinSettings.DoesNotExist:
                pass
        form = Step3ImageForm(instance=project)

    # Determine which AI provider is selected
    ai_provider = 'gemini'  # Default
    try:
        pin_settings = PinSettings.objects.get(user=request.user)
        ai_provider = pin_settings.ai_provider
    except PinSettings.DoesNotExist:
        pass

    # Check if the required API key is available
    has_required_key = (
        (ai_provider == 'gemini' and bool(request.user.gemini_api_key)) or
        (ai_provider == 'ideogram' and bool(request.user.ideogram_api_key))
    )

    context = {
        'form': form,
        'project': project,
        'step': 3,
        'total_steps': 6,
        'has_ideogram_key': bool(request.user.ideogram_api_key),
        'has_gemini_key': bool(request.user.gemini_api_key),
        'has_openai_key': bool(request.user.openai_api_key),
        'has_required_key': has_required_key,
        'ai_provider': ai_provider,
    }
    return render(request, 'ideopin/wizard/step3_image.html', context)


@login_required
def wizard_step4(request, project_id):
    """Schritt 4: Pin-Link eingeben"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if request.method == 'POST':
        form = Step4LinkForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save(commit=False)
            project.status = 'step4'
            project.save()
            return redirect('ideopin:wizard_step5', project_id=project.id)
    else:
        form = Step4LinkForm(instance=project)

    context = {
        'form': form,
        'project': project,
        'step': 4,
        'total_steps': 6,
    }
    return render(request, 'ideopin/wizard/step4_link.html', context)


@login_required
def wizard_step5(request, project_id):
    """Schritt 5: SEO Pin-Beschreibung"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if request.method == 'POST':
        # Multi-Pin SEO-Daten verarbeiten
        if project.pins.count() > 1:
            for pin in project.pins.all():
                title_key = f'pin_title_{pin.position}'
                desc_key = f'seo_description_{pin.position}'

                if title_key in request.POST:
                    pin.pin_title = request.POST.get(title_key, '')
                    pin.pin_title_ai_generated = False
                if desc_key in request.POST:
                    pin.seo_description = request.POST.get(desc_key, '')
                    pin.seo_description_ai_generated = False
                pin.save()

            project.status = 'step5'
            project.save()
            return redirect('ideopin:wizard_result', project_id=project.id)
        else:
            # Single-Pin (Original)
            form = Step5SEOForm(request.POST, instance=project)
            if form.is_valid():
                project = form.save(commit=False)
                project.status = 'step5'
                project.save()

                # Auch den ersten Pin aktualisieren
                first_pin = project.pins.first()
                if first_pin:
                    first_pin.pin_title = project.pin_title
                    first_pin.seo_description = project.seo_description
                    first_pin.save()

                return redirect('ideopin:wizard_result', project_id=project.id)
    else:
        form = Step5SEOForm(instance=project)

    context = {
        'form': form,
        'project': project,
        'step': 5,
        'total_steps': 6,
    }
    return render(request, 'ideopin/wizard/step5_seo.html', context)


@login_required
def wizard_result(request, project_id):
    """Schritt 6: Ergebnis anzeigen"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    project.status = 'completed'
    project.save()

    # Pinterest-Verbindungsstatus prüfen
    pinterest_connected = False
    try:
        from accounts.models import PinterestAPISettings
        pinterest_settings = PinterestAPISettings.objects.get(user=request.user)
        pinterest_connected = pinterest_settings.is_connected
    except:
        pass

    # Upload-Post API-Key prüfen
    upload_post_configured = bool(request.user.upload_post_api_key)

    context = {
        'project': project,
        'step': 6,
        'total_steps': 6,
        'pinterest_connected': pinterest_connected,
        'upload_post_configured': upload_post_configured,
    }
    return render(request, 'ideopin/wizard/result.html', context)


# ==================== API VIEWS ====================

@login_required
@require_POST
def api_generate_keywords(request):
    """API: Generiert verwandte Keywords mit hohem Suchvolumen"""
    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        data = json.loads(request.body) if request.body else {}
        seed_keyword = data.get('keyword', '').strip()

        if not seed_keyword:
            return JsonResponse({
                'success': False,
                'error': 'Bitte ein Keyword eingeben.'
            }, status=400)

        from .ai_service import PinAIService
        ai_service = PinAIService(request.user)
        result = ai_service.generate_related_keywords(seed_keyword)

        if result.get('success'):
            return JsonResponse({
                'success': True,
                'keywords': result['keywords']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except Exception as e:
        logger.error(f"Error generating keywords: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_get_product_image_history(request):
    """API: Gibt einzigartige Produktbilder des Benutzers paginiert zurück"""
    try:
        # Pagination Parameter
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 12))

        # Alle Projekte mit Produktbildern sammeln
        projects = PinProject.objects.filter(
            user=request.user,
            product_image__isnull=False
        ).exclude(product_image='').values('id', 'product_image', 'keywords', 'created_at').order_by('-created_at')

        # Deduplizieren basierend auf dem Bildpfad
        seen_images = set()
        unique_images = []

        for project in projects:
            image_path = project['product_image']
            if image_path and image_path not in seen_images:
                seen_images.add(image_path)
                unique_images.append({
                    'id': project['id'],
                    'url': f'/media/{image_path}',
                    'keywords': project['keywords'][:50] + '...' if len(project['keywords'] or '') > 50 else project['keywords'],
                    'date': project['created_at'].strftime('%d.%m.%Y') if project['created_at'] else ''
                })

        # Pagination berechnen
        total_count = len(unique_images)
        total_pages = (total_count + per_page - 1) // per_page  # Aufrunden
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_images = unique_images[start_idx:end_idx]

        return JsonResponse({
            'success': True,
            'images': paginated_images,
            'count': len(paginated_images),
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        })

    except Exception as e:
        logger.error(f"Error getting product image history: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_set_product_image_from_history(request, project_id):
    """API: Setzt das Produktbild aus einem früheren Projekt"""
    try:
        project = get_object_or_404(PinProject, id=project_id, user=request.user)
        data = json.loads(request.body) if request.body else {}
        source_project_id = data.get('source_project_id')

        if not source_project_id:
            return JsonResponse({
                'success': False,
                'error': 'Kein Quell-Projekt angegeben'
            }, status=400)

        source_project = get_object_or_404(PinProject, id=source_project_id, user=request.user)

        if not source_project.product_image:
            return JsonResponse({
                'success': False,
                'error': 'Das Quell-Projekt hat kein Produktbild'
            }, status=400)

        # Kopiere das Produktbild (Referenz, nicht die Datei selbst)
        project.product_image = source_project.product_image
        project.save()

        return JsonResponse({
            'success': True,
            'image_url': project.product_image.url
        })

    except Exception as e:
        logger.error(f"Error setting product image from history: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_get_keyword_history(request):
    """API: Gibt alle einzigartigen Keywords des Benutzers zurück"""
    try:
        # Alle Keywords aus den Projekten des Benutzers sammeln
        projects = PinProject.objects.filter(user=request.user).exclude(keywords='').values_list('keywords', flat=True)

        # Keywords extrahieren und deduplizieren
        all_keywords = set()
        for keywords_str in projects:
            if keywords_str:
                # Komma-getrennte Keywords aufsplitten
                for keyword in keywords_str.split(','):
                    keyword = keyword.strip()
                    if keyword:
                        all_keywords.add(keyword)

        # Alphabetisch sortieren
        sorted_keywords = sorted(all_keywords, key=str.lower)

        return JsonResponse({
            'success': True,
            'keywords': sorted_keywords,
            'count': len(sorted_keywords)
        })

    except Exception as e:
        logger.error(f"Error getting keyword history: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_get_link_history(request):
    """API: Gibt alle einzigartigen Links des Benutzers zurück"""
    try:
        # Alle Links aus den Projekten des Benutzers sammeln
        projects = PinProject.objects.filter(user=request.user).exclude(pin_url='').values_list('pin_url', flat=True)

        # Links deduplizieren (Case-insensitive)
        seen_links = set()
        unique_links = []
        for link in projects:
            if link:
                link_lower = link.lower().strip()
                if link_lower not in seen_links:
                    seen_links.add(link_lower)
                    unique_links.append(link.strip())

        # Alphabetisch sortieren
        sorted_links = sorted(unique_links, key=str.lower)

        return JsonResponse({
            'success': True,
            'links': sorted_links,
            'count': len(sorted_links)
        })

    except Exception as e:
        logger.error(f"Error getting link history: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_overlay_text(request, project_id):
    """API: Generiert catchy Pin-Text aus Keywords via GPT"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        from .ai_service import PinAIService
        ai_service = PinAIService(request.user)
        result = ai_service.generate_overlay_text(project.keywords)

        if result.get('success'):
            project.overlay_text = result['text']
            project.overlay_text_ai_generated = True
            project.save()
            return JsonResponse({
                'success': True,
                'text': result['text']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except Exception as e:
        logger.error(f"Error generating overlay text: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_styling(request, project_id):
    """API: Generiert optimales Text-Styling via KI"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    # Text aus Request-Body lesen (falls vom Frontend gesendet)
    try:
        data = json.loads(request.body) if request.body else {}
        current_text = data.get('overlay_text', '').strip()
    except json.JSONDecodeError:
        current_text = ''

    # Fallback auf gespeicherten Text
    overlay_text = current_text or project.overlay_text

    if not overlay_text:
        return JsonResponse({
            'success': False,
            'error': 'Bitte zuerst einen Overlay-Text eingeben.'
        }, status=400)

    # Text speichern falls neu
    if current_text and current_text != project.overlay_text:
        project.overlay_text = current_text
        project.save(update_fields=['overlay_text'])

    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        from .ai_service import PinAIService
        ai_service = PinAIService(request.user)
        result = ai_service.generate_text_styling(
            keywords=project.keywords,
            overlay_text=overlay_text,
            pin_format=project.pin_format or '1000x1500'
        )

        if result.get('success'):
            styling = result['styling']

            # Styling auf Projekt anwenden
            project.style_preset = styling.get('style_preset', 'modern_bold')
            project.text_font = styling.get('text_font', 'Arial')
            project.text_size = styling.get('text_size', 48)
            project.text_color = styling.get('text_color', '#FFFFFF')
            project.text_secondary_color = styling.get('text_secondary_color', '#000000')
            project.text_background_color = styling.get('text_background_color', '')
            project.text_background_opacity = styling.get('text_background_opacity', 0.7)
            project.text_effect = styling.get('text_effect', 'shadow')
            project.text_position = styling.get('text_position', 'center')
            project.text_padding = styling.get('text_padding', 20)
            project.styling_ai_generated = True
            project.save()

            return JsonResponse({
                'success': True,
                'styling': styling,
                'reasoning': result.get('reasoning', ''),
                'is_fallback': result.get('is_fallback', False)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except Exception as e:
        logger.error(f"Error generating text styling: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_image(request, project_id):
    """API: Generiert Bild via Gemini oder Ideogram"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    # Get user's preferred AI provider and settings
    ai_provider = 'gemini'  # Default to Gemini
    selected_model = None
    selected_style = None
    try:
        pin_settings = PinSettings.objects.get(user=request.user)
        ai_provider = pin_settings.ai_provider
        if ai_provider == 'ideogram':
            selected_model = pin_settings.ideogram_model
            selected_style = pin_settings.ideogram_style
        else:
            selected_model = pin_settings.gemini_model
        logger.info(f"[IdeoPin] Loaded settings: ai_provider={ai_provider}, model={selected_model}, style={selected_style}")
    except PinSettings.DoesNotExist:
        logger.warning("[IdeoPin] No PinSettings found for user, using defaults")
        pass  # Will use defaults

    # Check API key based on provider
    if ai_provider == 'gemini':
        if not request.user.gemini_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Kein Gemini API-Key konfiguriert. Bitte in den API-Einstellungen hinterlegen.'
            }, status=400)
    else:
        if not request.user.ideogram_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Kein Ideogram API-Key konfiguriert. Bitte in den API-Einstellungen hinterlegen.'
            }, status=400)

    try:
        # Get dimensions from format
        width, height = project.get_format_dimensions()

        # Check if product image is provided
        has_product_image = bool(project.product_image)

        # Select the appropriate service
        if ai_provider == 'gemini':
            from .gemini_service import GeminiImageService
            service = GeminiImageService(request.user.gemini_api_key)

            # Baue den Prompt basierend auf dem text_integration_mode
            if project.text_integration_mode == 'ideogram' and project.overlay_text:
                # Text soll direkt ins Bild integriert werden
                prompt = GeminiImageService.build_prompt_with_text(
                    background_description=project.background_description,
                    overlay_text=project.overlay_text,
                    text_position=project.text_position,
                    text_style='modern',
                    keywords=project.keywords,
                    has_product_image=has_product_image,
                    text_color=project.text_color or '#FFFFFF',
                    text_effect=project.text_effect or 'shadow',
                    text_secondary_color=project.text_secondary_color or '#000000',
                    style_preset=project.style_preset or 'modern_bold',
                    text_background_enabled=project.text_background_enabled,
                    text_background_creative=project.text_background_creative
                )
                logger.info(f"[Gemini] Generating image WITH integrated text: {project.overlay_text}")
                logger.info(f"[Gemini] Styling from DB: preset={project.style_preset}, effect={project.text_effect}, color={project.text_color}, secondary={project.text_secondary_color}")
                logger.info(f"[Gemini] Full prompt: {prompt[:500]}...")
            else:
                # Nur Hintergrund generieren (für PIL-Overlay oder ohne Text)
                prompt = GeminiImageService.build_prompt_without_text(
                    background_description=project.background_description,
                    keywords=project.keywords,
                    has_product_image=has_product_image
                )
                logger.info("[Gemini] Generating image WITHOUT text (for PIL overlay or no text)")

            result = service.generate_image(
                prompt=prompt,
                reference_image=project.product_image if project.product_image else None,
                width=width,
                height=height,
                model=selected_model
            )
        else:
            from .ideogram_service import IdeogramService
            service = IdeogramService(request.user.ideogram_api_key)

            # Baue den Prompt basierend auf dem text_integration_mode
            if project.text_integration_mode == 'ideogram' and project.overlay_text:
                # Text soll von Ideogram direkt ins Bild integriert werden
                prompt = IdeogramService.build_prompt_with_text(
                    background_description=project.background_description,
                    overlay_text=project.overlay_text,
                    text_position=project.text_position,
                    text_style='modern',
                    keywords=project.keywords,
                    has_product_image=has_product_image,
                    text_color=project.text_color or '#FFFFFF',
                    text_effect=project.text_effect or 'shadow',
                    text_secondary_color=project.text_secondary_color or '#000000',
                    style_preset=project.style_preset or 'modern_bold',
                    text_background_enabled=project.text_background_enabled,
                    text_background_creative=project.text_background_creative
                )
                logger.info(f"[Ideogram] Generating image WITH integrated text: {project.overlay_text}")
                logger.info(f"[Ideogram] Styling: preset={project.style_preset}, effect={project.text_effect}, color={project.text_color}")
            else:
                # Nur Hintergrund generieren (für PIL-Overlay oder ohne Text)
                prompt = IdeogramService.build_prompt_without_text(
                    background_description=project.background_description,
                    keywords=project.keywords,
                    has_product_image=has_product_image
                )
                logger.info("[Ideogram] Generating image WITHOUT text (for PIL overlay or no text)")

            result = service.generate_image(
                prompt=prompt,
                reference_image=project.product_image if project.product_image else None,
                width=width,
                height=height,
                model=selected_model,
                style=selected_style
            )

        if result.get('success'):
            # Save the generated image
            from django.core.files.base import ContentFile
            import base64
            import io

            image_data = result['image_data']
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)

            # Bild auf gewähltes Format skalieren/croppen
            img = Image.open(io.BytesIO(image_data))
            img = resize_and_crop_to_format(img, width, height)
            logger.info(f"Image resized to {width}x{height}")

            # Bild als PNG speichern
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', quality=95)
            buffer.seek(0)
            image_data = buffer.read()

            filename = f"generated_{project.id}.png"
            project.generated_image.save(filename, ContentFile(image_data), save=True)

            # Bei Ideogram-Modus ist das generierte Bild auch das finale Bild
            if project.text_integration_mode == 'ideogram' and project.overlay_text:
                project.final_image.save(f"final_{project.id}.png", ContentFile(image_data), save=True)

            # Model-Name für Anzeige formatieren
            model_display = selected_model or ('gemini-2.5-flash-image' if ai_provider == 'gemini' else 'V_2A_TURBO')
            if ai_provider == 'gemini':
                model_names = {
                    'gemini-3-pro-image-preview': 'Gemini 3 Pro',
                    'gemini-2.5-flash-image': 'Gemini 2.5 Flash',
                    'imagen-4.0-ultra-generate-001': 'Imagen 4 Ultra',
                    'imagen-4.0-generate-001': 'Imagen 4',
                    'imagen-4.0-fast-generate-001': 'Imagen 4 Fast',
                }
                model_display = model_names.get(model_display, model_display)
            else:
                model_names = {
                    'V_2A_TURBO': 'Ideogram 2a Turbo',
                    'V_2A': 'Ideogram 2a',
                    'V_2': 'Ideogram 2.0',
                    'V_2_TURBO': 'Ideogram 2.0 Turbo',
                }
                model_display = model_names.get(model_display, model_display)

            return JsonResponse({
                'success': True,
                'image_url': project.generated_image.url,
                'is_final': project.text_integration_mode == 'ideogram',
                'ai_provider': ai_provider,
                'model': model_display,
                'text_mode': project.text_integration_mode
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Fehler bei der Bildgenerierung')
            }, status=500)

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_image_variants(request, project_id):
    """API: Generiert mehrere Bild-Varianten zur Auswahl"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body) if request.body else {}
        variant_count = min(data.get('count', 3), 4)  # Max 4 Varianten
    except:
        variant_count = 3

    # Format und Dimensionen
    format_dimensions = {
        '1000x1500': (1000, 1500),
        '1000x1000': (1000, 1000),
        '1080x1920': (1080, 1920),
        '600x900': (600, 900),
    }
    width, height = format_dimensions.get(project.pin_format, (1000, 1500))

    # API Provider
    ai_provider = getattr(request.user, 'ai_provider', 'ideogram') or 'ideogram'
    has_product_image = bool(project.product_image)

    # Service initialisieren
    if ai_provider == 'gemini':
        from .gemini_service import GeminiImageService
        service = GeminiImageService(request.user.gemini_api_key)

        if project.text_integration_mode == 'ideogram' and project.overlay_text:
            prompt = GeminiImageService.build_prompt_with_text(
                background_description=project.background_description,
                overlay_text=project.overlay_text,
                text_position=project.text_position,
                text_style='modern',
                keywords=project.keywords,
                has_product_image=has_product_image,
                text_color=project.text_color or '#FFFFFF',
                text_effect=project.text_effect or 'shadow',
                text_secondary_color=project.text_secondary_color or '#000000',
                style_preset=project.style_preset or 'modern_bold',
                text_background_enabled=project.text_background_enabled,
                text_background_creative=project.text_background_creative
            )
        else:
            prompt = GeminiImageService.build_prompt_without_text(
                background_description=project.background_description,
                keywords=project.keywords,
                has_product_image=has_product_image
            )
    else:
        from .ideogram_service import IdeogramService
        service = IdeogramService(request.user.ideogram_api_key)

        if project.text_integration_mode == 'ideogram' and project.overlay_text:
            prompt = IdeogramService.build_prompt_with_text(
                background_description=project.background_description,
                overlay_text=project.overlay_text,
                text_position=project.text_position,
                text_style='modern',
                keywords=project.keywords,
                has_product_image=has_product_image,
                text_color=project.text_color or '#FFFFFF',
                text_effect=project.text_effect or 'shadow',
                text_secondary_color=project.text_secondary_color or '#000000',
                style_preset=project.style_preset or 'modern_bold',
                text_background_enabled=project.text_background_enabled,
                text_background_creative=project.text_background_creative
            )
        else:
            prompt = IdeogramService.build_prompt_without_text(
                background_description=project.background_description,
                keywords=project.keywords,
                has_product_image=has_product_image
            )

    logger.info(f"Generating {variant_count} image variants for project {project_id}")

    # Varianten generieren
    variants = []
    import base64
    import io

    for i in range(variant_count):
        try:
            result = service.generate_image(
                prompt=prompt,
                reference_image=project.product_image if project.product_image else None,
                width=width,
                height=height
            )

            if result.get('success'):
                image_data = result['image_data']
                if isinstance(image_data, str):
                    # Bereits base64-encoded
                    variants.append({
                        'index': i,
                        'image_data': f"data:image/png;base64,{image_data}"
                    })
                else:
                    variants.append({
                        'index': i,
                        'image_data': f"data:image/png;base64,{base64.b64encode(image_data).decode('utf-8')}"
                    })
            else:
                logger.warning(f"Variant {i} failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error generating variant {i}: {e}")

    if variants:
        return JsonResponse({
            'success': True,
            'variants': variants,
            'count': len(variants)
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Keine Varianten konnten generiert werden'
        }, status=500)


@login_required
@require_POST
def api_select_variant(request, project_id):
    """API: Wählt eine Variante aus und speichert sie"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        image_data_url = data.get('image_data')

        if not image_data_url:
            return JsonResponse({'success': False, 'error': 'Keine Bilddaten'}, status=400)

        # Base64 extrahieren
        import base64
        from django.core.files.base import ContentFile

        # Format: data:image/png;base64,XXXXX
        if ',' in image_data_url:
            image_data = base64.b64decode(image_data_url.split(',')[1])
        else:
            image_data = base64.b64decode(image_data_url)

        # Bild auf Format skalieren
        import io
        img = Image.open(io.BytesIO(image_data))

        format_dimensions = {
            '1000x1500': (1000, 1500),
            '1000x1000': (1000, 1000),
            '1080x1920': (1080, 1920),
            '600x900': (600, 900),
        }
        width, height = format_dimensions.get(project.pin_format, (1000, 1500))
        img = resize_and_crop_to_format(img, width, height)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG', quality=95)
        buffer.seek(0)
        image_data = buffer.read()

        # Speichern
        filename = f"generated_{project.id}.png"
        project.generated_image.save(filename, ContentFile(image_data), save=True)

        # Bei Ideogram-Modus auch als final speichern
        if project.text_integration_mode == 'ideogram' and project.overlay_text:
            project.final_image.save(f"final_{project.id}.png", ContentFile(image_data), save=True)

        return JsonResponse({
            'success': True,
            'image_url': project.generated_image.url
        })

    except Exception as e:
        logger.error(f"Error selecting variant: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_save_step3(request, project_id):
    """API: Speichert Step 3 Formular-Daten ohne Weiterleitung"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        form = Step3ImageForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            project = form.save(commit=False)
            # Nicht den Status ändern - wir wollen nicht weiterleiten
            project.save()
            return JsonResponse({
                'success': True,
                'message': 'Einstellungen gespeichert'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Formular ungültig: ' + str(form.errors)
            }, status=400)

    except Exception as e:
        logger.error(f"Error saving step3: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_upload_custom_image(request, project_id):
    """API: Lädt ein eigenes Bild hoch und speichert es als generated_image"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        custom_image = request.FILES.get('custom_image')
        if not custom_image:
            return JsonResponse({
                'success': False,
                'error': 'Kein Bild hochgeladen'
            }, status=400)

        # Bild speichern
        project.generated_image = custom_image
        project.save()

        return JsonResponse({
            'success': True,
            'image_url': project.generated_image.url,
            'message': 'Bild erfolgreich hochgeladen'
        })

    except Exception as e:
        logger.error(f"Error uploading custom image: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_add_ai_text_overlay(request, project_id):
    """
    API: Fügt Text-Overlay zu einem bestehenden Bild mittels KI hinzu.

    Das Bild (generated_image) wird an Gemini gesendet mit der Anweisung,
    den Text darauf zu platzieren, ohne den Hintergrund zu verändern.
    """
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    # Prüfen ob Bild vorhanden
    if not project.generated_image:
        return JsonResponse({
            'success': False,
            'error': 'Kein Bild vorhanden. Bitte zuerst ein Bild hochladen oder auswählen.'
        }, status=400)

    # Prüfen ob Text vorhanden
    if not project.overlay_text:
        return JsonResponse({
            'success': False,
            'error': 'Kein Text zum Hinzufügen. Bitte zuerst Text in Schritt 2 eingeben.'
        }, status=400)

    # Prüfen ob Gemini API-Key vorhanden
    if not request.user.gemini_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein Gemini API-Key konfiguriert. Bitte in den API-Einstellungen hinterlegen.'
        }, status=400)

    try:
        from .gemini_service import GeminiImageService
        from django.core.files.base import ContentFile
        import base64
        import io

        # Gemini Service initialisieren
        service = GeminiImageService(request.user.gemini_api_key)

        # Prompt für Text-Overlay erstellen
        prompt = GeminiImageService.build_prompt_for_text_overlay(
            overlay_text=project.overlay_text,
            text_position=project.text_position or 'center',
            text_color=project.text_color or '#FFFFFF',
            text_background_enabled=project.text_background_enabled,
            text_background_creative=project.text_background_creative
        )

        # Bildgröße ermitteln
        width, height = project.get_format_dimensions()

        # Model aus Einstellungen holen
        selected_model = None
        try:
            pin_settings = PinSettings.objects.get(user=request.user)
            selected_model = pin_settings.gemini_model
        except PinSettings.DoesNotExist:
            pass

        logger.info(f"[IdeoPin] Adding AI text overlay to image {project.id}")
        logger.info(f"[IdeoPin] Text: {project.overlay_text}")

        # Bild an Gemini senden mit dem Referenzbild
        result = service.generate_image(
            prompt=prompt,
            reference_image=project.generated_image,
            width=width,
            height=height,
            model=selected_model
        )

        if result.get('success'):
            image_data = result['image_data']
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)

            # Bild auf gewähltes Format skalieren/croppen
            img = Image.open(io.BytesIO(image_data))
            img = resize_and_crop_to_format(img, width, height)

            # Bild als PNG speichern
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', quality=95)
            buffer.seek(0)
            image_data = buffer.read()

            # Als final_image speichern (da Text jetzt drauf ist)
            filename = f"final_{project.id}.png"
            project.final_image.save(filename, ContentFile(image_data), save=True)

            # Model-Name für Anzeige
            model_display = selected_model or 'gemini-2.5-flash-image'
            model_names = {
                'gemini-3-pro-image-preview': 'Gemini 3 Pro',
                'gemini-2.5-flash-image': 'Gemini 2.5 Flash',
            }
            model_display = model_names.get(model_display, model_display)

            logger.info(f"[IdeoPin] AI text overlay successfully added to image {project.id}")

            return JsonResponse({
                'success': True,
                'image_url': project.final_image.url,
                'message': 'Text erfolgreich mit KI hinzugefügt',
                'ai_provider': 'gemini',
                'model': model_display
            })
        else:
            error_msg = result.get('error', 'Unbekannter Fehler bei der KI-Textgenerierung')
            logger.error(f"[IdeoPin] AI text overlay failed: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)

    except Exception as e:
        logger.error(f"Error adding AI text overlay: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_apply_text_overlay(request, project_id):
    """API: Wendet Text-Overlay auf das Bild an"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not project.generated_image:
        return JsonResponse({
            'success': False,
            'error': 'Kein generiertes Bild vorhanden. Bitte zuerst ein Bild generieren.'
        }, status=400)

    try:
        from .image_processor import PinImageProcessor

        processor = PinImageProcessor(project.generated_image.path)
        result_image = processor.add_text_overlay(
            text=project.overlay_text,
            font=project.text_font,
            size=project.text_size,
            color=project.text_color,
            position=project.text_position,
            background_color=project.text_background_color or None,
            background_opacity=project.text_background_opacity
        )

        # Save final image
        from django.core.files.base import ContentFile
        import io

        buffer = io.BytesIO()
        result_image.save(buffer, format='PNG', quality=95)
        buffer.seek(0)

        filename = f"final_{project.id}.png"
        project.final_image.save(filename, ContentFile(buffer.read()), save=True)

        return JsonResponse({
            'success': True,
            'image_url': project.final_image.url
        })

    except Exception as e:
        logger.error(f"Error applying text overlay: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_background_description(request, project_id):
    """API: Generiert eine fotorealistische Hintergrund-Beschreibung aus Stichwörtern"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in den API-Einstellungen hinterlegen.'
        }, status=400)

    try:
        import json
        data = json.loads(request.body)
        user_keywords = data.get('keywords', '')
        project_keywords = data.get('project_keywords', project.keywords)

        if not user_keywords:
            return JsonResponse({
                'success': False,
                'error': 'Bitte gib Stichwörter ein.'
            }, status=400)

        from .ai_service import PinAIService
        ai_service = PinAIService(request.user)

        result = ai_service.generate_realistic_background_description(
            user_input=user_keywords,
            project_keywords=project_keywords
        )

        if result.get('success'):
            logger.info(f"[Background] Generated realistic description: {result['description'][:100]}...")
            return JsonResponse({
                'success': True,
                'description': result['description']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Anfrage'
        }, status=400)
    except Exception as e:
        logger.error(f"Error generating background description: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_pin_title(request, project_id):
    """API: Generiert einen optimalen Pinterest Pin-Titel via GPT"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        from .ai_service import PinAIService

        ai_service = PinAIService(request.user)

        result = ai_service.generate_pin_title(
            keywords=project.keywords,
            overlay_text=project.overlay_text
        )

        if result.get('success'):
            project.pin_title = result['title']
            project.pin_title_ai_generated = True
            project.save()
            logger.info(f"[Title] Generated title: {result['title'][:50]}...")
            return JsonResponse({
                'success': True,
                'title': result['title'],
                'main_keyword': result.get('main_keyword')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except Exception as e:
        logger.error(f"Error generating pin title: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_seo_description(request, project_id):
    """API: Generiert die PERFEKTE Pinterest Pin-Beschreibung via GPT + Vision"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        from .ai_service import PinAIService
        import base64

        ai_service = PinAIService(request.user)

        # Bild als Base64 laden für Vision-Analyse
        image_base64 = None
        image_to_analyze = project.final_image or project.generated_image
        if image_to_analyze:
            try:
                with image_to_analyze.open('rb') as f:
                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
                logger.info(f"[SEO] Image loaded for analysis: {len(image_base64)} chars")
            except Exception as e:
                logger.warning(f"[SEO] Could not load image for analysis: {e}")

        result = ai_service.generate_seo_description(
            keywords=project.keywords,
            image_description=project.background_description,
            image_base64=image_base64,
            overlay_text=project.overlay_text
        )

        if result.get('success'):
            project.seo_description = result['description']
            project.seo_description_ai_generated = True
            project.save()
            logger.info(f"[SEO] Generated description with main keyword: {result.get('main_keyword')}")
            return JsonResponse({
                'success': True,
                'description': result['description'],
                'main_keyword': result.get('main_keyword')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unbekannter Fehler')
            }, status=500)

    except Exception as e:
        logger.error(f"Error generating SEO description: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== MANAGEMENT VIEWS ====================

@login_required
def project_list(request):
    """Liste aller Pin-Projekte"""
    # Filter-Parameter auslesen
    filter_by = request.GET.get('filter', 'all')

    # Basis-Queryset
    all_projects = PinProject.objects.filter(user=request.user)

    # Statistiken berechnen (immer auf alle Projekte)
    total_count = all_projects.count()
    posted_count = all_projects.filter(pinterest_posted=True).count()
    completed_count = all_projects.filter(status='completed').count()
    to_post_count = completed_count - posted_count  # Fertig aber noch nicht gepostet
    drafts_count = total_count - completed_count  # Nicht fertige Pins

    # Filter anwenden
    if filter_by == 'posted':
        projects = all_projects.filter(pinterest_posted=True).order_by('-pinterest_posted_at')
    elif filter_by == 'not_posted':
        projects = all_projects.filter(pinterest_posted=False, status='completed').order_by('-updated_at')
    elif filter_by == 'drafts':
        projects = all_projects.exclude(status='completed').order_by('-updated_at')
    else:  # 'all'
        projects = all_projects.order_by('pinterest_posted', '-updated_at')

    # Pagination: 20 Pins pro Seite
    paginator = Paginator(projects, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Pinterest-Verbindungsstatus prüfen
    pinterest_connected = False
    try:
        from accounts.models import PinterestAPISettings
        pinterest_settings = PinterestAPISettings.objects.get(user=request.user)
        pinterest_connected = pinterest_settings.is_connected
    except:
        pass

    context = {
        'projects': page_obj,  # page_obj statt projects für Template-Kompatibilität
        'page_obj': page_obj,
        'pinterest_connected': pinterest_connected,
        'total_count': total_count,
        'posted_count': posted_count,
        'completed_count': completed_count,
        'to_post_count': to_post_count,
        'drafts_count': drafts_count,
        'current_filter': filter_by,
    }
    return render(request, 'ideopin/project_list.html', context)


@login_required
@require_POST
def project_delete(request, project_id):
    """Projekt löschen"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    project.delete()
    messages.success(request, 'Projekt wurde gelöscht.')
    return redirect('ideopin:project_list')


@login_required
def project_duplicate(request, project_id):
    """Projekt duplizieren"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    # Create a copy
    new_project = PinProject.objects.create(
        user=request.user,
        keywords=project.keywords,
        overlay_text=project.overlay_text,
        background_description=project.background_description,
        pin_format=project.pin_format,
        pin_url=project.pin_url,
        text_font=project.text_font,
        text_size=project.text_size,
        text_color=project.text_color,
        text_position=project.text_position,
        text_background_color=project.text_background_color,
        text_background_opacity=project.text_background_opacity,
        status='draft'
    )

    messages.success(request, 'Projekt wurde dupliziert.')
    return redirect('ideopin:wizard_step1_edit', project_id=new_project.id)


@login_required
def download_image(request, project_id):
    """Finales Bild herunterladen"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if project.final_image:
        image_file = project.final_image
    elif project.generated_image:
        image_file = project.generated_image
    else:
        messages.error(request, 'Kein Bild zum Herunterladen verfügbar.')
        return redirect('ideopin:wizard_result', project_id=project_id)

    response = FileResponse(image_file.open('rb'), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="pinterest_pin_{project.id}.png"'
    return response


@login_required
def settings_view(request):
    """User-Einstellungen für Defaults"""
    try:
        pin_settings = PinSettings.objects.get(user=request.user)
    except PinSettings.DoesNotExist:
        pin_settings = None

    if request.method == 'POST':
        form = PinSettingsForm(request.POST, instance=pin_settings)
        if form.is_valid():
            settings_obj = form.save(commit=False)
            settings_obj.user = request.user
            settings_obj.save()
            logger.info(f"[IdeoPin Settings] Saved: ai_provider={settings_obj.ai_provider}, gemini_model={settings_obj.gemini_model}, ideogram_model={settings_obj.ideogram_model}")
            messages.success(request, 'Einstellungen wurden gespeichert.')
            return redirect('ideopin:settings')
        else:
            logger.error(f"[IdeoPin Settings] Form errors: {form.errors}")
    else:
        form = PinSettingsForm(instance=pin_settings)
        if pin_settings:
            logger.info(f"[IdeoPin Settings] Loaded: ai_provider={pin_settings.ai_provider}, gemini_model={pin_settings.gemini_model}")

    context = {
        'form': form,
        'has_ideogram_key': bool(request.user.ideogram_api_key),
        'has_openai_key': bool(request.user.openai_api_key),
        'has_gemini_key': bool(request.user.gemini_api_key),
    }
    return render(request, 'ideopin/settings.html', context)


# ==================== PINTEREST API VIEWS ====================

@login_required
def api_pinterest_boards(request):
    """API: Ruft die Pinterest-Boards des Benutzers ab"""
    try:
        from accounts.models import PinterestAPISettings
        from .pinterest_service import PinterestAPIService

        pinterest_settings = PinterestAPISettings.objects.get(user=request.user)

        if not pinterest_settings.is_connected:
            return JsonResponse({
                'success': False,
                'error': 'Pinterest ist nicht verbunden'
            }, status=400)

        service = PinterestAPIService(pinterest_settings)
        result = service.get_boards()

        if result.get('success'):
            return JsonResponse({
                'success': True,
                'boards': result['boards']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Fehler beim Laden der Boards')
            }, status=500)

    except PinterestAPISettings.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Pinterest nicht konfiguriert'
        }, status=400)
    except Exception as e:
        logger.error(f"[Pinterest] Boards laden fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_mark_as_posted(request, project_id):
    """API: Markiert einen Pin manuell als auf Pinterest gepostet"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        project.pinterest_posted = True
        project.pinterest_posted_at = timezone.now()
        project.save()

        return JsonResponse({
            'success': True,
            'message': 'Pin als gepostet markiert'
        })

    except Exception as e:
        logger.error(f"Error marking pin as posted: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_unmark_as_posted(request, project_id):
    """API: Entfernt die 'gepostet' Markierung von einem Pin"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        project.pinterest_posted = False
        project.pinterest_pin_id = ''
        project.pinterest_posted_at = None
        project.save()

        return JsonResponse({
            'success': True,
            'message': 'Markierung entfernt'
        })

    except Exception as e:
        logger.error(f"Error unmarking pin as posted: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_post_to_pinterest(request, project_id):
    """API: Postet einen Pin auf Pinterest"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        from accounts.models import PinterestAPISettings
        from .pinterest_service import PinterestAPIService

        # Request-Body parsen
        data = json.loads(request.body) if request.body else {}
        board_id = data.get('board_id')

        if not board_id:
            return JsonResponse({
                'success': False,
                'error': 'Bitte wähle ein Board aus'
            }, status=400)

        # Pinterest-Settings holen
        pinterest_settings = PinterestAPISettings.objects.get(user=request.user)

        if not pinterest_settings.is_connected:
            return JsonResponse({
                'success': False,
                'error': 'Pinterest ist nicht verbunden. Bitte zuerst verbinden.'
            }, status=400)

        # Prüfen ob bereits gepostet
        if project.pinterest_posted:
            return JsonResponse({
                'success': False,
                'error': 'Dieser Pin wurde bereits auf Pinterest gepostet'
            }, status=400)

        # Prüfen ob Bild vorhanden
        if not project.get_final_image_for_upload():
            return JsonResponse({
                'success': False,
                'error': 'Kein Bild vorhanden. Bitte zuerst ein Bild generieren.'
            }, status=400)

        # Board-Name für Speicherung holen
        service = PinterestAPIService(pinterest_settings)
        boards_result = service.get_boards()
        board_name = 'Unbekannt'
        if boards_result.get('success'):
            for board in boards_result.get('boards', []):
                if str(board.get('id')) == str(board_id):
                    board_name = board.get('name', 'Unbekannt')
                    break

        # Pin posten
        result = service.post_pin_from_project(project, board_id)

        if result.get('success'):
            # Board-Name speichern
            project.pinterest_board_name = board_name
            project.save()

            logger.info(f"[Pinterest] Pin {project.id} erfolgreich auf Board '{board_name}' gepostet")

            return JsonResponse({
                'success': True,
                'pin_id': result.get('pin_id'),
                'pin_url': result.get('pin_url'),
                'message': f'Pin erfolgreich auf "{board_name}" gepostet!'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Fehler beim Posten')
            }, status=500)

    except PinterestAPISettings.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Pinterest nicht konfiguriert'
        }, status=400)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Anfrage'
        }, status=400)
    except Exception as e:
        logger.error(f"[Pinterest] Posting fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_upload_post(request, project_id):
    """API: Postet einen Pin über Upload-Post.com auf Pinterest und andere Plattformen"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    import io

    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        # Upload-Post API-Key vom User holen
        upload_post_api_key = request.user.upload_post_api_key

        if not upload_post_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post API-Key nicht konfiguriert. Bitte in den API-Einstellungen hinzufügen.'
            }, status=400)

        # API-Key bereinigen - nur ASCII-druckbare Zeichen behalten
        api_key_clean = ''.join(c for c in upload_post_api_key if c.isascii() and c.isprintable()).strip()

        # Request Body parsen
        data = json.loads(request.body)
        platforms = data.get('platforms', ['pinterest'])
        pinterest_board_id = data.get('pinterest_board_id', '')
        scheduled_date = data.get('scheduled_date', '')  # ISO-8601 Format: 2024-12-31T23:45:00Z
        platform_options = data.get('platform_options', {})  # Plattform-spezifische Optionen

        # Prüfen ob Bild vorhanden
        image_file = project.get_final_image_for_upload()
        if not image_file:
            return JsonResponse({
                'success': False,
                'error': 'Kein Bild vorhanden. Bitte zuerst ein Bild generieren.'
            }, status=400)

        # Bild lesen
        image_file.seek(0)
        image_data = image_file.read()

        # Dateiname und Typ bestimmen
        image_name = getattr(image_file, 'name', 'pin.png')
        if not image_name:
            image_name = 'pin.png'
        # Nur Dateiname ohne Pfad
        image_name = image_name.split('/')[-1]
        if '.jpg' in image_name.lower() or '.jpeg' in image_name.lower():
            content_type = 'image/jpeg'
        else:
            content_type = 'image/png'
            if not image_name.endswith('.png'):
                image_name = 'pin.png'

        # Pin-Link erstellen (Ziel-URL für den Pin)
        pin_link = project.pin_url or request.build_absolute_uri(f'/ideopin/result/{project.id}/')

        # Upload-Post API aufrufen (multipart/form-data)
        api_url = 'https://api.upload-post.com/api/upload_photos'

        headers = {
            'Authorization': f'Apikey {api_key_clean}',
        }

        # Upload-Post User-ID holen
        upload_post_user_id = request.user.upload_post_user_id
        if not upload_post_user_id:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post User-ID nicht konfiguriert. Bitte in den API-Einstellungen hinzufügen.'
            }, status=400)

        # ============================================================
        # PLATTFORM-SPEZIFISCHE INHALTE (KEIN FALLBACK!)
        # Jede Plattform bekommt exakt den gewünschten Inhalt
        # ============================================================

        pin_title = project.pin_title or ''
        seo_description = project.seo_description or ''
        post_link = pin_link

        # Plattform-spezifische Inhalte definieren
        content_pinterest_title = pin_title
        content_pinterest_description = seo_description
        content_pinterest_link = post_link

        content_instagram = f"{seo_description}\n\n-> Link in Bio!" if seo_description else "-> Link in Bio!"

        content_facebook = f"{seo_description}\n\n{post_link}" if post_link else seo_description

        # X: 280 Zeichen Limit
        if post_link:
            x_max_len = 280 - len(post_link) - 2
            x_desc = seo_description[:x_max_len] if len(seo_description) > x_max_len else seo_description
            content_x = f"{x_desc}\n{post_link}"
        else:
            content_x = seo_description[:280]

        content_linkedin = f"{seo_description}\n\n{post_link}" if post_link else seo_description

        # Threads: 500 Zeichen Limit
        if post_link:
            threads_max_len = 500 - len(post_link) - 2
            threads_desc = seo_description[:threads_max_len] if len(seo_description) > threads_max_len else seo_description
            content_threads = f"{threads_desc}\n\n{post_link}"
        else:
            content_threads = seo_description[:500]

        # Bluesky: 300 Zeichen Limit, NUR Titel + Link
        if post_link:
            content_bluesky = f"{pin_title}\n\n{post_link}"[:300]
        else:
            content_bluesky = pin_title[:300]

        # ============================================================
        # BLUESKY SEPARAT BEHANDELN (braucht anderen title!)
        # ============================================================

        # Bluesky aus Hauptliste entfernen falls vorhanden
        has_bluesky = 'bluesky' in platforms
        other_platforms = [p for p in platforms if p != 'bluesky']

        # Session mit Retry-Logik erstellen (für alle Aufrufe)
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        all_results = []
        posted_platforms = []

        # ============================================================
        # 1. ANDERE PLATTFORMEN (Instagram-kompatibel: Beschreibung)
        # ============================================================
        if other_platforms:
            form_data = [
                ('user', upload_post_user_id),
                ('title', content_instagram),  # Beschreibung + "-> Link in Bio!"
            ]

            for platform in other_platforms:
                form_data.append(('platform[]', platform))

            # Pinterest
            if 'pinterest' in other_platforms:
                if pinterest_board_id:
                    form_data.append(('pinterest_board_id', pinterest_board_id))
                form_data.append(('pinterest_title', content_pinterest_title))
                form_data.append(('pinterest_description', content_pinterest_description))
                form_data.append(('pinterest_link', content_pinterest_link))

            # Instagram
            if 'instagram' in other_platforms:
                form_data.append(('instagram_caption', content_instagram))
                # Plattform-spezifische Optionen - media_type nur bei Stories senden
                media_type = platform_options.get('media_type', '')
                if media_type == 'STORIES':
                    form_data.append(('media_type', 'STORIES'))
                # share_to_feed nur relevant bei Stories
                if media_type == 'STORIES' and platform_options.get('share_to_feed') is not None:
                    form_data.append(('share_to_feed', 'true' if platform_options['share_to_feed'] else 'false'))

            # Facebook
            if 'facebook' in other_platforms:
                form_data.append(('facebook_title', content_facebook))
                # Plattform-spezifische Optionen - media_type nur bei Stories senden
                fb_media_type = platform_options.get('facebook_media_type', '')
                if fb_media_type == 'STORIES':
                    form_data.append(('facebook_media_type', 'STORIES'))

            # X (Twitter)
            if 'x' in other_platforms:
                form_data.append(('x_title', content_x))

            # LinkedIn
            if 'linkedin' in other_platforms:
                form_data.append(('linkedin_title', content_linkedin))
                form_data.append(('linkedin_description', content_linkedin))
                # Plattform-spezifische Optionen
                if platform_options.get('visibility'):
                    form_data.append(('visibility', platform_options['visibility']))

            # Threads
            if 'threads' in other_platforms:
                form_data.append(('threads_title', content_threads))

            if scheduled_date:
                form_data.append(('scheduled_date', scheduled_date))

            files = {'photos[]': (image_name, io.BytesIO(image_data), content_type)}

            logger.info(f"[Upload-Post] Posting Pin {project.id} auf: {other_platforms}")

            try:
                response = session.post(api_url, headers=headers, data=form_data, files=files, timeout=90, verify=True)
            except requests.exceptions.SSLError as ssl_err:
                logger.warning(f"[Upload-Post] SSL-Fehler, versuche ohne Verifizierung: {ssl_err}")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                files = {'photos[]': (image_name, io.BytesIO(image_data), content_type)}
                response = session.post(api_url, headers=headers, data=form_data, files=files, timeout=90, verify=False)

            logger.info(f"[Upload-Post] Response (andere): {response.status_code}, {response.text[:300]}")

            if response.status_code in [200, 202]:
                all_results.append(response.json())
                posted_platforms.extend(other_platforms)

        # ============================================================
        # 2. BLUESKY SEPARAT (Titel + Link!)
        # ============================================================
        if has_bluesky:
            form_data_bluesky = [
                ('user', upload_post_user_id),
                ('title', content_bluesky),  # Titel + Link für Bluesky!
                ('platform[]', 'bluesky'),
            ]

            if scheduled_date:
                form_data_bluesky.append(('scheduled_date', scheduled_date))

            files_bluesky = {'photos[]': (image_name, io.BytesIO(image_data), content_type)}

            logger.info(f"[Upload-Post] Posting Pin {project.id} auf Bluesky (separat)")

            try:
                response_bluesky = session.post(api_url, headers=headers, data=form_data_bluesky, files=files_bluesky, timeout=90, verify=True)
            except requests.exceptions.SSLError as ssl_err:
                logger.warning(f"[Upload-Post] SSL-Fehler Bluesky, versuche ohne Verifizierung: {ssl_err}")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                files_bluesky = {'photos[]': (image_name, io.BytesIO(image_data), content_type)}
                response_bluesky = session.post(api_url, headers=headers, data=form_data_bluesky, files=files_bluesky, timeout=90, verify=False)

            logger.info(f"[Upload-Post] Response (Bluesky): {response_bluesky.status_code}, {response_bluesky.text[:300]}")

            if response_bluesky.status_code in [200, 202]:
                all_results.append(response_bluesky.json())
                posted_platforms.append('bluesky')

            response = response_bluesky  # Für Fehlerbehandlung unten

        # Dummy response für Erfolgslogik falls nur andere Plattformen
        if other_platforms and not has_bluesky:
            pass  # response ist bereits gesetzt

        logger.info(f"[Upload-Post] Erfolgreich gepostet auf: {posted_platforms}")

        # Erfolg wenn mindestens eine Plattform funktioniert hat
        if posted_platforms:
            from django.utils import timezone
            now = timezone.now()

            # Upload-Post Plattformen speichern
            existing_platforms = project.upload_post_platforms.split(',') if project.upload_post_platforms else []
            existing_platforms = [p.strip() for p in existing_platforms if p.strip()]
            for platform in posted_platforms:
                if platform not in existing_platforms:
                    existing_platforms.append(platform)
            project.upload_post_platforms = ','.join(existing_platforms)
            project.upload_post_posted_at = now

            # Legacy: pinterest_posted für Kompatibilität
            project.pinterest_posted = True
            project.pinterest_posted_at = now

            # Board-Name mit Planungsinfo speichern
            if scheduled_date:
                project.pinterest_board_name = f"Upload-Post ({', '.join(posted_platforms)}) - Geplant: {scheduled_date}"
            else:
                project.pinterest_board_name = f"Upload-Post ({', '.join(posted_platforms)})"
            project.save()

            # Erfolgsmeldung
            if scheduled_date:
                message = f'Pin wurde für {scheduled_date} auf {", ".join(posted_platforms)} eingeplant!'
            else:
                message = f'Pin erfolgreich auf {", ".join(posted_platforms)} gepostet!'

            logger.info(f"[Upload-Post] Pin {project.id} erfolgreich auf: {posted_platforms}")

            return JsonResponse({
                'success': True,
                'message': message,
                'scheduled': bool(scheduled_date),
                'result': all_results
            })
        else:
            error_msg = f"API Fehler: {response.status_code}"
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_data.get('message', error_msg))
            except:
                error_msg = response.text[:200]

            logger.error(f"[Upload-Post] Fehler: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=response.status_code)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Anfrage'
        }, status=400)
    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Zeitüberschreitung bei der API-Anfrage'
        }, status=504)
    except Exception as e:
        logger.error(f"[Upload-Post] Posting fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_server_images(request):
    """API: Gibt Server-Bilder zurück (ImageForge + Produktbilder)"""
    import os
    from django.conf import settings as django_settings

    try:
        images = []

        # 1. ImageForge generierte Bilder
        try:
            from imageforge.models import ImageGeneration

            imageforge_images = ImageGeneration.objects.filter(
                user=request.user,
                generated_image__isnull=False
            ).exclude(generated_image='').order_by('-created_at')[:50]

            for img in imageforge_images:
                if img.generated_image:
                    images.append({
                        'path': str(img.generated_image),
                        'url': img.generated_image.url,
                        'name': f"ImageForge {img.created_at.strftime('%d.%m.%Y')}",
                        'type': 'imageforge',
                        'date': img.created_at.strftime('%d.%m.%Y %H:%M')
                    })
        except Exception as e:
            logger.warning(f"Could not load ImageForge images: {e}")

        # 2. Produktbilder aus IdeoPin-Projekten
        product_images = PinProject.objects.filter(
            user=request.user,
            product_image__isnull=False
        ).exclude(product_image='').order_by('-created_at')[:30]

        seen_paths = set()
        for proj in product_images:
            if proj.product_image and str(proj.product_image) not in seen_paths:
                seen_paths.add(str(proj.product_image))
                images.append({
                    'path': str(proj.product_image),
                    'url': proj.product_image.url,
                    'name': (proj.keywords[:30] + '...') if len(proj.keywords or '') > 30 else proj.keywords or 'Produktbild',
                    'type': 'products',
                    'date': proj.created_at.strftime('%d.%m.%Y %H:%M') if proj.created_at else ''
                })

        # 3. Generierte Bilder aus IdeoPin-Projekten
        generated_images = PinProject.objects.filter(
            user=request.user,
            generated_image__isnull=False
        ).exclude(generated_image='').order_by('-created_at')[:30]

        for proj in generated_images:
            if proj.generated_image and str(proj.generated_image) not in seen_paths:
                seen_paths.add(str(proj.generated_image))
                images.append({
                    'path': str(proj.generated_image),
                    'url': proj.generated_image.url,
                    'name': (proj.keywords[:30] + '...') if len(proj.keywords or '') > 30 else proj.keywords or 'Pin-Bild',
                    'type': 'imageforge',  # Als ImageForge markieren da generiert
                    'date': proj.created_at.strftime('%d.%m.%Y %H:%M') if proj.created_at else ''
                })

        return JsonResponse({
            'success': True,
            'images': images,
            'count': len(images)
        })

    except Exception as e:
        logger.error(f"Error loading server images: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_use_server_image(request, project_id):
    """API: Verwendet ein Server-Bild als generated_image für das Projekt"""
    import os
    import shutil
    from django.conf import settings as django_settings
    from django.core.files.base import ContentFile

    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        image_path = data.get('image_path', '').strip()

        if not image_path:
            return JsonResponse({
                'success': False,
                'error': 'Kein Bildpfad angegeben'
            }, status=400)

        # Vollständigen Pfad erstellen
        full_path = os.path.join(django_settings.MEDIA_ROOT, image_path)

        # Sicherheitscheck: Pfad muss im MEDIA_ROOT sein
        real_path = os.path.realpath(full_path)
        real_media = os.path.realpath(django_settings.MEDIA_ROOT)
        if not real_path.startswith(real_media):
            return JsonResponse({
                'success': False,
                'error': 'Ungültiger Bildpfad'
            }, status=400)

        if not os.path.exists(full_path):
            return JsonResponse({
                'success': False,
                'error': 'Bild nicht gefunden'
            }, status=404)

        # Bild kopieren und als generated_image speichern
        with open(full_path, 'rb') as f:
            image_data = f.read()

        # Dateiname aus Pfad extrahieren
        original_filename = os.path.basename(image_path)
        ext = os.path.splitext(original_filename)[1] or '.png'
        new_filename = f"server_{project.id}{ext}"

        # Als generated_image speichern
        project.generated_image.save(new_filename, ContentFile(image_data), save=True)

        logger.info(f"[IdeoPin] Server image used: {image_path} -> {new_filename}")

        return JsonResponse({
            'success': True,
            'image_url': project.generated_image.url,
            'message': 'Bild erfolgreich übernommen'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Anfrage'
        }, status=400)
    except Exception as e:
        logger.error(f"Error using server image: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_upload_post_boards(request):
    """API: Holt Pinterest Boards von Upload-Post.com"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    try:
        # Upload-Post API-Key vom User holen
        upload_post_api_key = request.user.upload_post_api_key

        if not upload_post_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post API-Key nicht konfiguriert.'
            }, status=400)

        # API-Key bereinigen - nur ASCII-druckbare Zeichen behalten
        import re
        api_key_clean = ''.join(c for c in upload_post_api_key if c.isascii() and c.isprintable()).strip()

        if not api_key_clean:
            return JsonResponse({
                'success': False,
                'error': 'API-Key enthält ungültige Zeichen. Bitte neu eingeben.'
            }, status=400)

        logger.info(f"[Upload-Post] API-Key Länge: {len(api_key_clean)}")

        # Upload-Post API aufrufen
        api_url = 'https://api.upload-post.com/api/uploadposts/pinterest/boards'

        headers = {
            'Authorization': 'Apikey ' + api_key_clean,
        }

        # Session mit Retry-Logik erstellen
        session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        response = None
        try:
            response = session.get(api_url, headers=headers, timeout=30, verify=True)
        except requests.exceptions.SSLError as ssl_err:
            logger.warning(f"[Upload-Post] SSL-Fehler bei Boards, versuche ohne Verifizierung: {ssl_err}")
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = session.get(api_url, headers=headers, timeout=30, verify=False)

        logger.info(f"[Upload-Post] Boards Response: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            # Antwort-Format anpassen (je nach API-Response)
            boards = data if isinstance(data, list) else data.get('boards', data.get('data', []))

            return JsonResponse({
                'success': True,
                'boards': boards
            })
        else:
            error_msg = f"API Fehler: {response.status_code}"
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_data.get('message', error_msg))
            except:
                error_msg = response.text[:200]

            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=response.status_code)

    except Exception as e:
        logger.error(f"[Upload-Post] Boards abrufen fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== MULTI-PIN API ENDPOINTS ====================

@login_required
@require_POST
def api_generate_variations(request, project_id):
    """
    API: Generiert Text- und Hintergrund-Variationen für mehrere Pins.
    Erstellt auch die entsprechenden Pin-Objekte.
    """
    import openai
    from django.conf import settings as django_settings

    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        pin_count = int(data.get('pin_count', data.get('count', 1)))
        pin_count = max(1, min(7, pin_count))  # Begrenzen auf 1-7

        # Pin-Count aktualisieren
        project.pin_count = pin_count
        project.save()

        # Basis-Daten (aus Request oder aus Projekt)
        base_text = data.get('base_text') or project.overlay_text or ''
        base_background = data.get('base_background') or project.background_description or ''
        keywords = project.keywords or ''

        # Wenn nur 1 Pin, keine Variationen nötig
        if pin_count == 1:
            # Stelle sicher, dass Pin 1 existiert
            pin, created = Pin.objects.get_or_create(
                project=project,
                position=1,
                defaults={
                    'overlay_text': base_text,
                    'background_description': base_background,
                }
            )
            if not created:
                pin.overlay_text = base_text
                pin.background_description = base_background
                pin.save()

            return JsonResponse({
                'success': True,
                'pins': [{
                    'position': 1,
                    'overlay_text': base_text,
                    'background_description': base_background,
                }]
            })

        # OpenAI API für Variationen
        openai_api_key = getattr(request.user, 'openai_api_key', None)
        if not openai_api_key:
            openai_api_key = getattr(django_settings, 'OPENAI_API_KEY', None)

        if not openai_api_key:
            return JsonResponse({
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }, status=400)

        client = openai.OpenAI(api_key=openai_api_key)

        # Anzahl der Variationen (Pin 1 bleibt unverändert, nur 2-7 bekommen Variationen)
        variation_count = pin_count - 1

        # Prompt für Text-Variationen (nur für Pins 2-7)
        text_prompt = f"""Schreibe den folgenden Text {variation_count}x leicht um. Jede Version soll die gleiche Aussage haben, aber anders formuliert sein.

Original-Text: {base_text}
Keywords: {keywords}

Regeln:
- Behalte die Kernaussage bei
- Variiere Wortstellung, Synonyme, Formulierung
- Max 5-8 Wörter pro Text
- Auf Deutsch
- Jede Version soll sich vom Original unterscheiden, aber nicht komplett anders sein

Antworte NUR als JSON: {{"texts": ["Variation 1", "Variation 2", ...]}}"""

        # Prompt für Hintergrund-Variationen (nur für Pins 2-7)
        bg_prompt = f"""Schreibe die folgende Hintergrund-Beschreibung {variation_count}x leicht um. Jede Version soll die gleiche Szene beschreiben, aber mit kleinen Variationen.

Original-Beschreibung: {base_background}
Keywords: {keywords}

Jede Variation soll:
- Die gleiche Grundszene beschreiben
- Leichte Unterschiede in Details, Perspektive oder Stimmung haben
- Fotorealistisch und für Bildgenerierung optimiert sein
- 1-2 Sätze lang sein

Antworte NUR als JSON: {{"backgrounds": ["Variation 1", "Variation 2", ...]}}"""

        # Text-Variationen generieren
        text_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": text_prompt}],
            temperature=0.9,
            max_tokens=500
        )
        text_content = text_response.choices[0].message.content.strip()

        # JSON aus Text-Response extrahieren
        try:
            if '```json' in text_content:
                text_content = text_content.split('```json')[1].split('```')[0].strip()
            elif '```' in text_content:
                text_content = text_content.split('```')[1].split('```')[0].strip()
            text_data = json.loads(text_content)
            texts = text_data.get('texts', [])
        except json.JSONDecodeError:
            texts = [base_text] * variation_count

        # Hintergrund-Variationen generieren
        bg_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": bg_prompt}],
            temperature=0.9,
            max_tokens=800
        )
        bg_content = bg_response.choices[0].message.content.strip()

        # JSON aus Hintergrund-Response extrahieren
        try:
            if '```json' in bg_content:
                bg_content = bg_content.split('```json')[1].split('```')[0].strip()
            elif '```' in bg_content:
                bg_content = bg_content.split('```')[1].split('```')[0].strip()
            bg_data = json.loads(bg_content)
            backgrounds = bg_data.get('backgrounds', [])
        except json.JSONDecodeError:
            backgrounds = [base_background] * variation_count

        # Listen auf variation_count erweitern/kürzen (für Pins 2-7)
        while len(texts) < variation_count:
            texts.append(base_text or texts[0] if texts else '')
        while len(backgrounds) < variation_count:
            backgrounds.append(base_background or backgrounds[0] if backgrounds else '')

        texts = texts[:variation_count]
        backgrounds = backgrounds[:variation_count]

        # Pins erstellen/aktualisieren
        pins_data = []

        # Pin 1: Original-Texte behalten (NICHT ändern)
        pin1, created = Pin.objects.get_or_create(
            project=project,
            position=1,
            defaults={
                'overlay_text': base_text,
                'overlay_text_ai_generated': False,  # Nicht AI-generiert
                'background_description': base_background,
            }
        )
        if not created:
            pin1.overlay_text = base_text
            pin1.overlay_text_ai_generated = False
            pin1.background_description = base_background
            pin1.save()

        pins_data.append({
            'position': 1,
            'overlay_text': base_text,
            'background_description': base_background,
        })

        # Pins 2-7: Variationen verwenden
        for i in range(variation_count):
            pin, created = Pin.objects.get_or_create(
                project=project,
                position=i + 2,  # Position 2, 3, 4, ...
                defaults={
                    'overlay_text': texts[i],
                    'overlay_text_ai_generated': True,
                    'background_description': backgrounds[i],
                }
            )
            if not created:
                pin.overlay_text = texts[i]
                pin.overlay_text_ai_generated = True
                pin.background_description = backgrounds[i]
                pin.save()

            pins_data.append({
                'position': i + 2,
                'overlay_text': texts[i],
                'background_description': backgrounds[i],
            })

        # Überzählige Pins löschen
        Pin.objects.filter(project=project, position__gt=pin_count).delete()

        return JsonResponse({
            'success': True,
            'pins': pins_data
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] Variationen-Generierung fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_save_pins(request, project_id):
    """API: Speichert alle Pin-Daten eines Projekts"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        pins_data = data.get('pins', [])

        for pin_data in pins_data:
            position = pin_data.get('position')
            if not position:
                continue

            pin, created = Pin.objects.get_or_create(
                project=project,
                position=position
            )

            if 'overlay_text' in pin_data:
                pin.overlay_text = pin_data['overlay_text']
            if 'background_description' in pin_data:
                pin.background_description = pin_data['background_description']

            pin.save()

        return JsonResponse({'success': True})

    except Exception as e:
        logger.error(f"[Multi-Pin] Pins speichern fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_pin_image(request, project_id, position):
    """API: Generiert ein Bild für einen einzelnen Pin"""
    from io import BytesIO
    from django.core.files.base import ContentFile

    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    pin = get_object_or_404(Pin, project=project, position=position)

    try:
        # User-Einstellungen laden
        try:
            user_settings = request.user.pin_settings
        except PinSettings.DoesNotExist:
            user_settings = None

        # AI Provider bestimmen
        ai_provider = 'gemini'
        if user_settings:
            ai_provider = user_settings.ai_provider

        # API-Keys prüfen
        ideogram_api_key = getattr(request.user, 'ideogram_api_key', None)
        gemini_api_key = getattr(request.user, 'gemini_api_key', None)

        if ai_provider == 'ideogram' and not ideogram_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Ideogram API-Key nicht konfiguriert'
            }, status=400)
        if ai_provider == 'gemini' and not gemini_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Gemini API-Key nicht konfiguriert'
            }, status=400)

        # Format-Dimensionen
        width, height = project.get_format_dimensions()

        # Text-Integration Modus
        text_mode = project.text_integration_mode
        overlay_text = pin.overlay_text if text_mode != 'none' else ''
        has_product_image = bool(project.product_image)

        # Bild generieren
        if ai_provider == 'gemini':
            from .gemini_service import GeminiImageService

            model_name = 'gemini-2.5-flash-image'
            if user_settings:
                model_name = user_settings.gemini_model

            service = GeminiImageService(gemini_api_key)

            # Prompt bauen
            if text_mode == 'ideogram' and overlay_text:
                prompt = GeminiImageService.build_prompt_with_text(
                    background_description=pin.background_description,
                    overlay_text=overlay_text,
                    text_position=project.text_position,
                    text_style='modern',
                    keywords=project.keywords,
                    has_product_image=has_product_image,
                    text_color=project.text_color or '#FFFFFF',
                    text_effect=project.text_effect or 'shadow',
                    text_secondary_color=project.text_secondary_color or '#000000',
                    style_preset=project.style_preset or 'modern_bold',
                    text_background_enabled=project.text_background_enabled,
                    text_background_creative=project.text_background_creative
                )
            else:
                prompt = GeminiImageService.build_prompt_without_text(
                    background_description=pin.background_description,
                    keywords=project.keywords,
                    has_product_image=has_product_image
                )

            result = service.generate_image(
                prompt=prompt,
                reference_image=project.product_image if project.product_image else None,
                width=width,
                height=height,
                model=model_name
            )
        else:
            from .ideogram_service import IdeogramService

            model_name = 'V_2A_TURBO'
            style_type = 'REALISTIC'
            if user_settings:
                model_name = user_settings.ideogram_model
                style_type = user_settings.ideogram_style

            service = IdeogramService(ideogram_api_key)

            # Prompt bauen
            if text_mode == 'ideogram' and overlay_text:
                prompt = IdeogramService.build_prompt_with_text(
                    background_description=pin.background_description,
                    overlay_text=overlay_text,
                    text_position=project.text_position,
                    text_style='modern',
                    keywords=project.keywords,
                    has_product_image=has_product_image,
                    text_color=project.text_color or '#FFFFFF',
                    text_effect=project.text_effect or 'shadow',
                    text_secondary_color=project.text_secondary_color or '#000000',
                    style_preset=project.style_preset or 'modern_bold',
                    text_background_enabled=project.text_background_enabled,
                    text_background_creative=project.text_background_creative
                )
            else:
                prompt = IdeogramService.build_prompt_without_text(
                    background_description=pin.background_description,
                    keywords=project.keywords,
                    has_product_image=has_product_image
                )

            result = service.generate_image(
                prompt=prompt,
                reference_image=project.product_image if project.product_image else None,
                width=width,
                height=height,
                model=model_name,
                style_type=style_type
            )

        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Bildgenerierung fehlgeschlagen')
            }, status=500)

        # Bild verarbeiten
        import base64
        image_data = base64.b64decode(result['image_base64'])
        img = Image.open(BytesIO(image_data))

        # Auf Format skalieren
        img = resize_and_crop_to_format(img, width, height)

        # Als PNG speichern
        buffer = BytesIO()
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buffer, format='PNG', quality=95)
        buffer.seek(0)

        # Speichern
        filename = f"pin_{project_id}_{position}.png"
        pin.generated_image.save(filename, ContentFile(buffer.read()), save=False)

        # Bei Text-Integration ist generated = final
        if text_mode == 'ideogram':
            buffer.seek(0)
            pin.final_image.save(f"pin_{project_id}_{position}_final.png", ContentFile(buffer.read()), save=False)

        pin.save()

        return JsonResponse({
            'success': True,
            'position': position,
            'image_url': pin.generated_image.url if pin.generated_image else None,
            'final_image_url': pin.final_image.url if pin.final_image else None,
            'ai_provider': ai_provider,
            'model': result.get('model', model_name),
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] Pin-Bild Generierung fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_all_seo(request, project_id):
    """API: Generiert SEO-Titel und Beschreibung für alle Pins"""
    import openai
    from django.conf import settings as django_settings

    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    pins = project.pins.all().order_by('position')

    if not pins.exists():
        return JsonResponse({
            'success': False,
            'error': 'Keine Pins vorhanden'
        }, status=400)

    try:
        openai_api_key = getattr(request.user, 'openai_api_key', None)
        if not openai_api_key:
            openai_api_key = getattr(django_settings, 'OPENAI_API_KEY', None)

        if not openai_api_key:
            return JsonResponse({
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }, status=400)

        client = openai.OpenAI(api_key=openai_api_key)
        results = []

        for pin in pins:
            # Titel generieren
            title_prompt = f"""Erstelle einen Pinterest Pin-Titel (max 100 Zeichen).

Keywords: {project.keywords}
Pin-Text: {pin.overlay_text}

Regeln:
- Haupt-Keyword am Anfang
- Neugierig machen
- Max 100 Zeichen
- Auf Deutsch

Antworte NUR mit dem Titel, ohne Anführungszeichen."""

            title_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": title_prompt}],
                temperature=0.7,
                max_tokens=100
            )
            title = title_response.choices[0].message.content.strip()[:100]

            # Beschreibung generieren
            desc_prompt = f"""Erstelle eine Pinterest Pin-Beschreibung (ideal: 470-490 Zeichen).

Keywords: {project.keywords}
Pin-Text: {pin.overlay_text}
Titel: {title}

Regeln:
- Haupt-Keywords in den ersten 100 Zeichen
- Call-to-Action einbauen
- 3-5 Hashtags am Ende
- Ideal 470-490 Zeichen (max 500)
- Auf Deutsch

Antworte NUR mit der Beschreibung."""

            desc_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": desc_prompt}],
                temperature=0.7,
                max_tokens=600
            )
            description = desc_response.choices[0].message.content.strip()[:500]

            # Pin aktualisieren
            pin.pin_title = title
            pin.pin_title_ai_generated = True
            pin.seo_description = description
            pin.seo_description_ai_generated = True
            pin.save()

            results.append({
                'position': pin.position,
                'pin_title': title,
                'seo_description': description,
            })

        return JsonResponse({
            'success': True,
            'pins': results
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] SEO-Generierung fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_generate_pin_seo(request, project_id, position):
    """API: Generiert SEO-Titel und Beschreibung für einen einzelnen Pin"""
    import openai
    from django.conf import settings as django_settings

    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    pin = get_object_or_404(Pin, project=project, position=position)

    try:
        openai_api_key = getattr(request.user, 'openai_api_key', None)
        if not openai_api_key:
            openai_api_key = getattr(django_settings, 'OPENAI_API_KEY', None)

        if not openai_api_key:
            return JsonResponse({
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }, status=400)

        client = openai.OpenAI(api_key=openai_api_key)

        # Titel generieren
        title_prompt = f"""Erstelle einen Pinterest Pin-Titel (max 100 Zeichen).

Keywords: {project.keywords}
Pin-Text: {pin.overlay_text}

Regeln: Haupt-Keyword am Anfang, neugierig machen, max 100 Zeichen, auf Deutsch.

Antworte NUR mit dem Titel."""

        title_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": title_prompt}],
            temperature=0.7,
            max_tokens=100
        )
        title = title_response.choices[0].message.content.strip()[:100]

        # Beschreibung generieren
        desc_prompt = f"""Erstelle eine Pinterest Pin-Beschreibung (470-490 Zeichen).

Keywords: {project.keywords}
Pin-Text: {pin.overlay_text}
Titel: {title}

Regeln: Keywords am Anfang, Call-to-Action, 3-5 Hashtags, max 500 Zeichen, auf Deutsch.

Antworte NUR mit der Beschreibung."""

        desc_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": desc_prompt}],
            temperature=0.7,
            max_tokens=600
        )
        description = desc_response.choices[0].message.content.strip()[:500]

        # Pin aktualisieren
        pin.pin_title = title
        pin.pin_title_ai_generated = True
        pin.seo_description = description
        pin.seo_description_ai_generated = True
        pin.save()

        return JsonResponse({
            'success': True,
            'position': position,
            'pin_title': title,
            'seo_description': description,
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] Pin-SEO Generierung fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_schedule_pin(request, project_id, position):
    """API: Plant einen einzelnen Pin für späteres Posten"""
    from datetime import datetime

    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    pin = get_object_or_404(Pin, project=project, position=position)

    try:
        data = json.loads(request.body)
        scheduled_at = data.get('scheduled_at')
        board_id = data.get('board_id', '')

        if scheduled_at:
            # ISO-Format parsen
            pin.scheduled_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        else:
            pin.scheduled_at = None

        if board_id:
            pin.pinterest_board_id = board_id

        pin.save()

        return JsonResponse({
            'success': True,
            'position': position,
            'scheduled_at': str(pin.scheduled_at) if pin.scheduled_at else None,
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] Pin-Scheduling fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_apply_distribution(request, project_id):
    """API: Wendet automatische Zeitverteilung auf alle Pins an"""
    from datetime import datetime, timedelta

    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        start_date_str = data.get('start_date')
        interval_days = int(data.get('interval_days', 2))
        board_id = data.get('board_id', '')
        start_time = data.get('start_time', '12:00')

        if not start_date_str:
            return JsonResponse({
                'success': False,
                'error': 'Startdatum erforderlich'
            }, status=400)

        # Startdatum parsen
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        hour, minute = map(int, start_time.split(':'))

        # Verteilung anwenden
        pins = project.pins.filter(pinterest_posted=False).order_by('position')
        scheduled_pins = []

        for i, pin in enumerate(pins):
            scheduled_datetime = datetime.combine(
                start_date + timedelta(days=i * interval_days),
                datetime.min.time().replace(hour=hour, minute=minute)
            )
            pin.scheduled_at = timezone.make_aware(scheduled_datetime)
            if board_id:
                pin.pinterest_board_id = board_id
            pin.save()

            scheduled_pins.append({
                'position': pin.position,
                'scheduled_at': str(pin.scheduled_at),
            })

        # Projekt-Einstellungen speichern
        project.distribution_mode = 'auto'
        project.distribution_interval_days = interval_days
        project.save()

        return JsonResponse({
            'success': True,
            'scheduled_count': len(scheduled_pins),
            'pins': scheduled_pins,
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] Verteilung anwenden fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_post_single_pin(request, project_id, position):
    """API: Veröffentlicht einen einzelnen Pin auf Pinterest"""
    import base64
    import requests

    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    pin = get_object_or_404(Pin, project=project, position=position)

    try:
        data = json.loads(request.body)
        board_id = data.get('board_id')
        platforms = data.get('platforms', ['pinterest'])
        scheduled_date = data.get('scheduled_date')

        if not board_id:
            return JsonResponse({
                'success': False,
                'error': 'Board-ID erforderlich'
            }, status=400)

        # Bild für Upload vorbereiten
        image_file = pin.get_final_image_for_upload()
        if not image_file:
            return JsonResponse({
                'success': False,
                'error': 'Kein Bild vorhanden'
            }, status=400)

        # Upload-Post API-Key
        upload_post_api_key = getattr(request.user, 'upload_post_api_key', None)
        if not upload_post_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post API-Key nicht konfiguriert'
            }, status=400)

        # Bild als Base64
        with open(image_file.path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # API-Request vorbereiten
        api_url = 'https://api.upload-post.com/api/upload_photos'
        headers = {
            'Authorization': 'Apikey ' + upload_post_api_key.strip(),
            'Content-Type': 'application/json',
        }

        post_data = {
            'image': f"data:image/png;base64,{image_base64}",
            'platforms': platforms,
            'title': pin.pin_title or project.keywords[:100],
            'description': pin.seo_description or '',
            'link': project.pin_url or '',
            'pinterest_board_id': board_id,
        }

        if scheduled_date:
            post_data['scheduled_date'] = scheduled_date

        response = requests.post(api_url, headers=headers, json=post_data, timeout=60)

        if response.status_code == 200:
            result = response.json()

            # Pin als gepostet markieren
            pin.pinterest_posted = True
            pin.pinterest_board_id = board_id
            pin.pinterest_posted_at = timezone.now()
            pin.upload_post_platforms = ','.join(platforms)
            pin.save()

            return JsonResponse({
                'success': True,
                'message': 'Pin erfolgreich veröffentlicht!' if not scheduled_date else 'Pin erfolgreich geplant!',
                'position': position,
            })
        else:
            error_msg = response.text[:200]
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                pass

            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=response.status_code)

    except Exception as e:
        logger.error(f"[Multi-Pin] Pin-Posting fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_publish_batch(request, project_id):
    """API: Veröffentlicht mehrere Pins auf einmal"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        pin_positions = data.get('pin_positions', [])
        board_id = data.get('board_id')

        if not pin_positions:
            return JsonResponse({
                'success': False,
                'error': 'Keine Pins ausgewählt'
            }, status=400)

        results = []
        for position in pin_positions:
            # Für jeden Pin den einzelnen Post-Endpoint aufrufen
            pin = project.pins.filter(position=position).first()
            if pin and not pin.pinterest_posted:
                # Hier würden wir normalerweise den Post-Vorgang durchführen
                # Für jetzt markieren wir nur als "in Bearbeitung"
                results.append({
                    'position': position,
                    'status': 'pending',
                })

        return JsonResponse({
            'success': True,
            'message': f'{len(results)} Pins werden verarbeitet...',
            'results': results,
        })

    except Exception as e:
        logger.error(f"[Multi-Pin] Batch-Posting fehlgeschlagen: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def download_pin_image(request, project_id, position):
    """Download eines einzelnen Pin-Bildes"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)
    pin = get_object_or_404(Pin, project=project, position=position)

    image_file = pin.get_final_image_for_upload()
    if not image_file:
        return HttpResponse('Kein Bild vorhanden', status=404)

    response = FileResponse(
        open(image_file.path, 'rb'),
        content_type='image/png'
    )
    response['Content-Disposition'] = f'attachment; filename="pin_{project_id}_{position}.png"'
    return response
