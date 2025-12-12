from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.core.files.base import ContentFile
import base64
import time
import logging

from .models import ImageGeneration, Character, CharacterImage, StylePreset
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

    # API-Key Verfuegbarkeit pruefen
    has_google_key = bool(getattr(request.user, 'gemini_api_key', None))
    has_openai_key = bool(getattr(request.user, 'openai_api_key', None))
    has_any_key = has_google_key or has_openai_key

    context = {
        'characters': characters,
        'presets': presets,
        'recent_generations': recent_generations,
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
