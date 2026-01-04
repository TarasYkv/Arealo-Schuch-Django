from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.core.files.base import ContentFile
import base64
import time
import logging

from .models import ImageGeneration, Character, CharacterImage, StylePreset, ProductMockup
from .services import PromptBuilder, GeminiGenerator, DalleGenerator

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD & GENERIERUNG
# =============================================================================

@login_required
def dashboard(request):
    """Hauptseite mit Generator-Formular"""
    characters = Character.objects.filter(user=request.user)
    presets = StylePreset.objects.filter(user=request.user)
    recent_generations = ImageGeneration.objects.filter(user=request.user)[:6]
    mockups = ProductMockup.objects.filter(user=request.user, mockup_image__isnull=False)[:10]

    # Bild-Verlauf für Mockup-Wizard (unique Bilder aus bisherigen Mockups)
    product_images_history = ProductMockup.objects.filter(
        user=request.user,
        product_image__isnull=False
    ).exclude(product_image='').values_list('product_image', flat=True).distinct()[:20]

    style_ref_images_history = ProductMockup.objects.filter(
        user=request.user,
        style_reference_image__isnull=False
    ).exclude(style_reference_image='').values_list('style_reference_image', flat=True).distinct()[:20]

    # URLs für Template erstellen
    from django.conf import settings
    product_images_history = [
        {'url': settings.MEDIA_URL + img} for img in product_images_history if img
    ]
    style_ref_images_history = [
        {'url': settings.MEDIA_URL + img} for img in style_ref_images_history if img
    ]

    # API-Key Verfuegbarkeit pruefen
    has_google_key = bool(getattr(request.user, 'gemini_api_key', None))
    has_openai_key = bool(getattr(request.user, 'openai_api_key', None))
    has_any_key = has_google_key or has_openai_key

    context = {
        'characters': characters,
        'presets': presets,
        'recent_generations': recent_generations,
        'mockups': mockups,
        'product_images_history': product_images_history,
        'style_ref_images_history': style_ref_images_history,
        'has_google_key': has_google_key,
        'has_openai_key': has_openai_key,
        'has_any_key': has_any_key,
    }
    return render(request, 'imageforge/dashboard.html', context)


@login_required
def generate_image(request):
    """AJAX-Endpoint für Bildgenerierung"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST-Anfragen erlaubt'}, status=405)

    start_time = time.time()

    try:
        # Formulardaten extrahieren
        mode = request.POST.get('generation_mode', 'background')
        background_prompt = request.POST.get('background_prompt', '').strip()
        aspect_ratio = request.POST.get('aspect_ratio', '1:1')
        lighting_style = request.POST.get('lighting_style', 'natural')
        perspective = request.POST.get('perspective', 'frontal')
        style_preset = request.POST.get('style_preset', 'lifestyle')
        shadow_type = request.POST.get('shadow_type', 'soft')
        color_mood = request.POST.get('color_mood', 'neutral')
        quality = request.POST.get('quality', 'standard')
        ai_model = request.POST.get('ai_model', 'gemini-2.0-flash-preview-image-generation')

        if not background_prompt:
            return JsonResponse({'error': 'Bitte Szenen-Beschreibung eingeben'}, status=400)

        # Charakter laden (falls angegeben)
        character = None
        character_id = request.POST.get('character')
        if character_id and mode in ['character', 'character_product']:
            character = get_object_or_404(Character, id=character_id, user=request.user)

        # Produktbild (falls hochgeladen)
        product_image = request.FILES.get('product_image')

        # Generator basierend auf Modell waehlen
        if ai_model.startswith('dall-e'):
            api_key = getattr(request.user, 'openai_api_key', None)
            if not api_key:
                return JsonResponse({
                    'error': 'OpenAI API-Key nicht konfiguriert. Bitte in den Einstellungen hinterlegen.'
                }, status=400)
            generator = DalleGenerator(api_key)
        else:
            api_key = getattr(request.user, 'gemini_api_key', None)
            if not api_key:
                return JsonResponse({
                    'error': 'Gemini API-Key nicht konfiguriert. Bitte in den Einstellungen hinterlegen.'
                }, status=400)
            generator = GeminiGenerator(api_key)

        # Prompt bauen
        prompt_builder = PromptBuilder()
        character_desc = character.description if character else ''
        prompt = prompt_builder.build_prompt(
            mode=mode,
            background_description=background_prompt,
            lighting=lighting_style,
            perspective=perspective,
            style=style_preset,
            shadow=shadow_type,
            color_mood=color_mood,
            character_description=character_desc,
            aspect_ratio=aspect_ratio
        )

        # Referenzbilder sammeln
        reference_images = []
        if product_image:
            reference_images.append(product_image)
        if character:
            for char_img in character.images.all()[:5]:  # Max 5 Bilder
                reference_images.append(char_img.image)

        # Dimensionen aus Aspect Ratio
        width, height = generator.get_dimensions_for_ratio(aspect_ratio)

        # Bild generieren
        logger.info(f"Generating image: mode={mode}, model={ai_model}")
        result = generator.generate(
            prompt=prompt,
            reference_images=reference_images if reference_images else None,
            width=width,
            height=height,
            model=ai_model,
            quality=quality
        )

        generation_time = time.time() - start_time

        # Generation-Objekt erstellen
        generation = ImageGeneration(
            user=request.user,
            generation_mode=mode,
            background_prompt=background_prompt,
            aspect_ratio=aspect_ratio,
            lighting_style=lighting_style,
            perspective=perspective,
            style_preset=style_preset,
            shadow_type=shadow_type,
            color_mood=color_mood,
            quality=quality,
            ai_model=ai_model,
            generation_prompt=prompt,
            generation_time=generation_time,
            character=character
        )

        # Produktbild speichern falls vorhanden
        if product_image:
            generation.product_image = product_image

        if result.get('success'):
            # Bild aus Base64 speichern
            image_data = base64.b64decode(result['image_data'])
            filename = f"imageforge_{generation.id or 'new'}_{int(time.time())}.png"
            generation.generated_image.save(filename, ContentFile(image_data), save=False)
            generation.save()

            logger.info(f"Image generated successfully: {generation.id}")

            return JsonResponse({
                'success': True,
                'generation_id': generation.id,
                'image_url': generation.generated_image.url,
                'generation_time': round(generation_time, 1)
            })
        else:
            # Fehler speichern
            generation.error_message = result.get('error', 'Unbekannter Fehler')
            generation.save()

            logger.error(f"Image generation failed: {result.get('error')}")

            return JsonResponse({
                'error': result.get('error', 'Bildgenerierung fehlgeschlagen')
            }, status=500)

    except Exception as e:
        logger.exception(f"Error in generate_image: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# HISTORY & GENERIERUNGS-DETAILS
# =============================================================================

@login_required
def history(request):
    """Verlauf aller Generierungen"""
    generations = ImageGeneration.objects.filter(user=request.user)
    return render(request, 'imageforge/history.html', {'generations': generations})


@login_required
def generation_detail(request, generation_id):
    """Detail-Ansicht einer Generierung"""
    generation = get_object_or_404(ImageGeneration, id=generation_id, user=request.user)
    return render(request, 'imageforge/generation_detail.html', {'generation': generation})


@login_required
def delete_generation(request, generation_id):
    """Generierung löschen"""
    generation = get_object_or_404(ImageGeneration, id=generation_id, user=request.user)
    if request.method == 'POST':
        generation.delete()
        messages.success(request, 'Generierung gelöscht.')
        return redirect('imageforge:history')
    return redirect('imageforge:generation_detail', generation_id=generation_id)


@login_required
def toggle_favorite(request, generation_id):
    """Favoriten-Status umschalten"""
    generation = get_object_or_404(ImageGeneration, id=generation_id, user=request.user)
    generation.is_favorite = not generation.is_favorite
    generation.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'is_favorite': generation.is_favorite})
    return redirect('imageforge:generation_detail', generation_id=generation_id)


# =============================================================================
# CHARAKTER-VERWALTUNG
# =============================================================================

@login_required
def character_list(request):
    """Liste aller Charaktere"""
    characters = Character.objects.filter(user=request.user)
    return render(request, 'imageforge/character_list.html', {'characters': characters})


@login_required
def character_create(request):
    """Neuen Charakter erstellen"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(request, 'Bitte geben Sie einen Namen ein.')
            return redirect('imageforge:character_create')

        character = Character.objects.create(
            user=request.user,
            name=name,
            description=description
        )

        # Bilder hochladen
        images = request.FILES.getlist('images')
        for i, image_file in enumerate(images):
            CharacterImage.objects.create(
                character=character,
                image=image_file,
                is_primary=(i == 0),
                upload_order=i
            )

        messages.success(request, f'Charakter "{name}" erstellt.')
        return redirect('imageforge:character_detail', character_id=character.id)

    return render(request, 'imageforge/character_create.html')


@login_required
def character_detail(request, character_id):
    """Detail-Ansicht eines Charakters"""
    character = get_object_or_404(Character, id=character_id, user=request.user)
    return render(request, 'imageforge/character_detail.html', {'character': character})


@login_required
def character_edit(request, character_id):
    """Charakter bearbeiten"""
    character = get_object_or_404(Character, id=character_id, user=request.user)

    if request.method == 'POST':
        character.name = request.POST.get('name', '').strip() or character.name
        character.description = request.POST.get('description', '').strip()
        character.save()

        # Neue Bilder hinzufügen
        new_images = request.FILES.getlist('images')
        current_order = character.images.count()
        for i, image_file in enumerate(new_images):
            CharacterImage.objects.create(
                character=character,
                image=image_file,
                upload_order=current_order + i
            )

        messages.success(request, 'Charakter aktualisiert.')
        return redirect('imageforge:character_detail', character_id=character.id)

    return render(request, 'imageforge/character_edit.html', {'character': character})


@login_required
def character_delete(request, character_id):
    """Charakter löschen"""
    character = get_object_or_404(Character, id=character_id, user=request.user)
    if request.method == 'POST':
        name = character.name
        character.delete()
        messages.success(request, f'Charakter "{name}" gelöscht.')
        return redirect('imageforge:character_list')
    return redirect('imageforge:character_detail', character_id=character_id)


# =============================================================================
# PRESET-VERWALTUNG
# =============================================================================

@login_required
def preset_list(request):
    """Liste aller Presets"""
    presets = StylePreset.objects.filter(user=request.user)
    return render(request, 'imageforge/preset_list.html', {'presets': presets})


@login_required
def save_preset(request):
    """Neues Preset speichern (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST-Anfragen erlaubt'}, status=405)

    import json

    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        settings = data.get('settings', {})

        if not name:
            return JsonResponse({'error': 'Name erforderlich'}, status=400)

        preset = StylePreset.objects.create(
            user=request.user,
            name=name,
            settings=settings
        )

        return JsonResponse({
            'success': True,
            'preset_id': preset.id,
            'name': preset.name
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Ungültiges JSON'}, status=400)


@login_required
def delete_preset(request, preset_id):
    """Preset löschen"""
    preset = get_object_or_404(StylePreset, id=preset_id, user=request.user)
    if request.method == 'POST':
        preset.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, 'Preset gelöscht.')
        return redirect('imageforge:preset_list')
    return redirect('imageforge:preset_list')


# =============================================================================
# MOCKUP-TEXT FEATURE
# =============================================================================

@login_required
def mockup_list(request):
    """Liste aller Mockups des Users"""
    mockups = ProductMockup.objects.filter(user=request.user)
    return render(request, 'imageforge/mockup_list.html', {'mockups': mockups})


@login_required
def mockup_detail(request, mockup_id):
    """Detail-Ansicht eines Mockups"""
    mockup = get_object_or_404(ProductMockup, id=mockup_id, user=request.user)
    # Zeige auch alle Szenen-Generierungen die dieses Mockup verwenden
    scene_generations = mockup.scene_generations.all()
    return render(request, 'imageforge/mockup_detail.html', {
        'mockup': mockup,
        'scene_generations': scene_generations
    })


@login_required
def mockup_delete(request, mockup_id):
    """Mockup löschen"""
    mockup = get_object_or_404(ProductMockup, id=mockup_id, user=request.user)
    if request.method == 'POST':
        mockup.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, 'Mockup gelöscht.')
        return redirect('imageforge:mockup_list')
    return redirect('imageforge:mockup_detail', mockup_id=mockup_id)


@login_required
def mockup_json(request, mockup_id):
    """JSON-Daten eines Mockups (für Dropdown-Auswahl)"""
    mockup = get_object_or_404(ProductMockup, id=mockup_id, user=request.user)
    return JsonResponse({
        'id': mockup.id,
        'name': mockup.name or f"Mockup: {mockup.text_content[:20]}...",
        'text_content': mockup.text_content,
        'text_application_type': mockup.text_application_type,
        'mockup_image_url': mockup.mockup_image.url if mockup.mockup_image else None,
    })


@login_required
def generate_mockup(request):
    """AJAX: Step 1 - Generiert Produkt-Mockup mit Text"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)

    start_time = time.time()

    try:
        # Daten extrahieren (vereinfacht - Stil wird aus Referenzbild extrahiert)
        text_content = request.POST.get('text_content', '').strip()
        product_description = request.POST.get('product_description', '')
        mockup_name = request.POST.get('mockup_name', '')

        product_image = request.FILES.get('product_image')
        style_reference_image = request.FILES.get('style_reference_image')

        if not text_content:
            return JsonResponse({'error': 'Text ist erforderlich'}, status=400)
        if not product_image:
            return JsonResponse({'error': 'Produktbild ist erforderlich'}, status=400)
        if not style_reference_image:
            return JsonResponse({'error': 'Stil-Referenzbild ist erforderlich'}, status=400)

        # Nano Banana Pro für Text-Rendering erzwingen
        ai_model = 'gemini-3-pro-image-preview'

        # API-Key prüfen (Gemini erforderlich für beste Text-Qualität)
        api_key = getattr(request.user, 'gemini_api_key', None)
        if not api_key:
            return JsonResponse({
                'error': 'Gemini API-Key erforderlich. Text-Rendering funktioniert am besten mit Gemini/Nano Banana Pro.'
            }, status=400)

        generator = GeminiGenerator(api_key)
        prompt_builder = PromptBuilder()

        # Prompt bauen (vereinfacht - Stil aus Referenzbild)
        prompt = prompt_builder.build_mockup_text_prompt(
            text_content=text_content,
            product_description=product_description
        )

        # Referenzbilder: Produktbild + Stil-Referenzbild
        reference_images = [product_image, style_reference_image]

        # Generieren
        logger.info(f"Generating mockup: text='{text_content}', model={ai_model}")
        result = generator.generate(
            prompt=prompt,
            reference_images=reference_images,
            model=ai_model
        )

        generation_time = time.time() - start_time

        # Mockup speichern (vereinfacht - Stil aus Referenzbild)
        mockup = ProductMockup(
            user=request.user,
            name=mockup_name or f"Mockup: {text_content[:30]}",
            text_content=text_content,
            ai_model=ai_model,
            generation_prompt=prompt,
            generation_time=generation_time
        )
        mockup.product_image = product_image
        mockup.style_reference_image = style_reference_image

        if result.get('success'):
            image_data = base64.b64decode(result['image_data'])
            filename = f"mockup_{int(time.time())}.png"
            mockup.mockup_image.save(filename, ContentFile(image_data), save=False)
            mockup.save()

            logger.info(f"Mockup generated successfully: {mockup.id}")

            return JsonResponse({
                'success': True,
                'mockup_id': mockup.id,
                'mockup_name': mockup.name,
                'mockup_image_url': mockup.mockup_image.url,
                'generation_time': round(generation_time, 1)
            })
        else:
            mockup.error_message = result.get('error', 'Unbekannter Fehler')
            mockup.save()

            logger.error(f"Mockup generation failed: {result.get('error')}")

            return JsonResponse({
                'error': result.get('error', 'Mockup-Generierung fehlgeschlagen'),
                'mockup_id': mockup.id
            }, status=500)

    except Exception as e:
        logger.exception(f"Error in generate_mockup: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def generate_mockup_scene(request):
    """AJAX: Step 2 - Platziert Mockup in Szene"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)

    start_time = time.time()

    try:
        mockup_id = request.POST.get('mockup_id')
        background_prompt = request.POST.get('background_prompt', '').strip()
        aspect_ratio = request.POST.get('aspect_ratio', '1:1')
        lighting_style = request.POST.get('lighting_style', 'natural')
        perspective = request.POST.get('perspective', 'frontal')
        style_preset = request.POST.get('style_preset', 'lifestyle')
        shadow_type = request.POST.get('shadow_type', 'soft')
        color_mood = request.POST.get('color_mood', 'neutral')
        quality = request.POST.get('quality', 'standard')
        ai_model = request.POST.get('ai_model', 'gemini-3-pro-image-preview')

        if not mockup_id:
            return JsonResponse({'error': 'Mockup-ID erforderlich'}, status=400)
        if not background_prompt:
            return JsonResponse({'error': 'Szenen-Beschreibung erforderlich'}, status=400)

        mockup = get_object_or_404(ProductMockup, id=mockup_id, user=request.user)

        if not mockup.mockup_image:
            return JsonResponse({'error': 'Mockup hat kein generiertes Bild'}, status=400)

        # Generator wählen basierend auf Modell
        if ai_model.startswith('dall-e'):
            api_key = getattr(request.user, 'openai_api_key', None)
            if not api_key:
                return JsonResponse({
                    'error': 'OpenAI API-Key nicht konfiguriert.'
                }, status=400)
            generator = DalleGenerator(api_key)
        else:
            api_key = getattr(request.user, 'gemini_api_key', None)
            if not api_key:
                return JsonResponse({
                    'error': 'Gemini API-Key nicht konfiguriert.'
                }, status=400)
            generator = GeminiGenerator(api_key)

        prompt_builder = PromptBuilder()
        prompt = prompt_builder.build_mockup_scene_prompt(
            scene_description=background_prompt,
            lighting=lighting_style,
            perspective=perspective,
            style=style_preset,
            shadow=shadow_type,
            color_mood=color_mood,
            aspect_ratio=aspect_ratio
        )

        # Dimensionen aus Aspect Ratio
        width, height = generator.get_dimensions_for_ratio(aspect_ratio)

        # Generieren mit Mockup als Referenz
        logger.info(f"Generating mockup scene: mockup={mockup_id}, model={ai_model}")
        result = generator.generate(
            prompt=prompt,
            reference_images=[mockup.mockup_image],
            width=width,
            height=height,
            model=ai_model,
            quality=quality
        )

        generation_time = time.time() - start_time

        # ImageGeneration speichern
        generation = ImageGeneration(
            user=request.user,
            generation_mode='mockup_text',
            background_prompt=background_prompt,
            aspect_ratio=aspect_ratio,
            lighting_style=lighting_style,
            perspective=perspective,
            style_preset=style_preset,
            shadow_type=shadow_type,
            color_mood=color_mood,
            quality=quality,
            ai_model=ai_model,
            generation_prompt=prompt,
            generation_time=generation_time,
            mockup=mockup
        )

        if result.get('success'):
            image_data = base64.b64decode(result['image_data'])
            filename = f"mockup_scene_{int(time.time())}.png"
            generation.generated_image.save(filename, ContentFile(image_data), save=False)
            generation.save()

            logger.info(f"Mockup scene generated successfully: {generation.id}")

            return JsonResponse({
                'success': True,
                'generation_id': generation.id,
                'image_url': generation.generated_image.url,
                'generation_time': round(generation_time, 1)
            })
        else:
            generation.error_message = result.get('error', 'Unbekannter Fehler')
            generation.save()

            logger.error(f"Mockup scene generation failed: {result.get('error')}")

            return JsonResponse({
                'error': result.get('error', 'Szenen-Generierung fehlgeschlagen')
            }, status=500)

    except Exception as e:
        logger.exception(f"Error in generate_mockup_scene: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def toggle_mockup_favorite(request, mockup_id):
    """Favoriten-Status eines Mockups umschalten"""
    mockup = get_object_or_404(ProductMockup, id=mockup_id, user=request.user)
    mockup.is_favorite = not mockup.is_favorite
    mockup.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'is_favorite': mockup.is_favorite})
    return redirect('imageforge:mockup_detail', mockup_id=mockup_id)


# =============================================================================
# API: Verlauf & KI-Helfer
# =============================================================================

@login_required
def api_background_prompt_history(request):
    """API: Gibt unique Hintergrund-Beschreibungen aus vergangenen Mockup-Generierungen zurück"""
    # Hole alle unique background_prompts aus mockup_text Generierungen
    prompts = ImageGeneration.objects.filter(
        user=request.user,
        mode='mockup_text',
        background_prompt__isnull=False
    ).exclude(
        background_prompt=''
    ).values_list('background_prompt', flat=True).distinct()[:30]

    # Dedupliziere und formatiere
    unique_prompts = list(dict.fromkeys(prompts))  # Reihenfolge beibehalten, Duplikate entfernen

    return JsonResponse({
        'success': True,
        'prompts': unique_prompts
    })


@login_required
def api_generate_funny_sayings(request):
    """API: Generiert 10 humorvolle Sprüche basierend auf einem Keyword"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)

    keyword = request.POST.get('keyword', '').strip()
    if not keyword:
        return JsonResponse({'error': 'Bitte ein Keyword eingeben'}, status=400)

    # KI-Provider wählen (bevorzugt Gemini, dann OpenAI)
    has_gemini = bool(getattr(request.user, 'gemini_api_key', None))
    has_openai = bool(getattr(request.user, 'openai_api_key', None))

    if not has_gemini and not has_openai:
        return JsonResponse({'error': 'Kein API-Key konfiguriert'}, status=400)

    prompt = f"""Generiere genau 10 kurze, humorvolle und witzige Sprüche zum Thema "{keyword}".

Die Sprüche sollen:
- Kurz und prägnant sein (max. 5-8 Wörter)
- Witzig/humorvoll sein
- Gut als Text auf einem Produkt-Mockup aussehen
- Auf Deutsch sein
- Keine Anführungszeichen enthalten

Antworte NUR mit einer nummerierten Liste (1. bis 10.), ohne zusätzlichen Text."""

    try:
        if has_gemini:
            import google.generativeai as genai
            genai.configure(api_key=request.user.gemini_api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)
            result_text = response.text
        else:
            from openai import OpenAI
            client = OpenAI(api_key=request.user.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            result_text = response.choices[0].message.content

        # Parse die Sprüche aus der Antwort
        import re
        lines = result_text.strip().split('\n')
        sayings = []
        for line in lines:
            # Entferne Nummerierung und bereinige
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
            cleaned = cleaned.strip('"\'')
            if cleaned and len(cleaned) > 2:
                sayings.append(cleaned)

        # Maximal 10 Sprüche
        sayings = sayings[:10]

        return JsonResponse({
            'success': True,
            'sayings': sayings,
            'keyword': keyword
        })

    except Exception as e:
        logger.exception(f"Error generating funny sayings: {e}")
        return JsonResponse({'error': str(e)}, status=500)
