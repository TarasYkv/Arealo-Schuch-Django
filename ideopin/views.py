import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.utils import timezone
from PIL import Image

from .models import PinProject, PinSettings
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

            project.status = 'step3'
            project.save()
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
        form = Step5SEOForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save(commit=False)
            project.status = 'step5'
            project.save()
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
    """API: Gibt alle einzigartigen Produktbilder des Benutzers zurück"""
    try:
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

        return JsonResponse({
            'success': True,
            'images': unique_images,
            'count': len(unique_images)
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

    # Pinterest-Verbindungsstatus prüfen
    pinterest_connected = False
    try:
        from accounts.models import PinterestAPISettings
        pinterest_settings = PinterestAPISettings.objects.get(user=request.user)
        pinterest_connected = pinterest_settings.is_connected
    except:
        pass

    context = {
        'projects': projects,
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

        # Form-Daten vorbereiten (als Liste von Tupeln für mehrere gleiche Keys)
        form_data = [
            ('user', upload_post_user_id),
            ('title', project.pin_title or 'Pinterest Pin'),
        ]

        # Plattformen hinzufügen (jede als separates Feld)
        for platform in platforms:
            form_data.append(('platform[]', platform))

        # Pinterest-spezifische Felder
        if 'pinterest' in platforms:
            if pinterest_board_id:
                form_data.append(('pinterest_board_id', pinterest_board_id))
            form_data.append(('pinterest_title', project.pin_title or ''))
            form_data.append(('pinterest_description', project.seo_description or ''))
            form_data.append(('pinterest_link', pin_link))

        # Bild als File hinzufügen
        files = {
            'photos[]': (image_name, io.BytesIO(image_data), content_type)
        }

        logger.info(f"[Upload-Post] Posting Pin {project.id} auf Plattformen: {platforms}")

        # Session mit Retry-Logik erstellen
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Versuche zuerst mit SSL-Verifizierung, dann ohne als Fallback
        response = None
        try:
            response = session.post(api_url, headers=headers, data=form_data, files=files, timeout=90, verify=True)
        except requests.exceptions.SSLError as ssl_err:
            logger.warning(f"[Upload-Post] SSL-Fehler, versuche ohne Verifizierung: {ssl_err}")
            # Fallback: Ohne SSL-Verifizierung (nur wenn nötig)
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            # BytesIO muss neu erstellt werden
            files = {'photos[]': (image_name, io.BytesIO(image_data), content_type)}
            response = session.post(api_url, headers=headers, data=form_data, files=files, timeout=90, verify=False)

        logger.info(f"[Upload-Post] Response Status: {response.status_code}, Body: {response.text[:500]}")

        if response.status_code == 200:
            result = response.json()

            # Als gepostet markieren
            from django.utils import timezone
            project.pinterest_posted = True
            project.pinterest_posted_at = timezone.now()
            project.pinterest_board_name = f"Upload-Post ({', '.join(platforms)})"
            project.save()

            logger.info(f"[Upload-Post] Pin {project.id} erfolgreich gepostet: {result}")

            return JsonResponse({
                'success': True,
                'message': f'Pin erfolgreich auf {", ".join(platforms)} gepostet!',
                'result': result
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
