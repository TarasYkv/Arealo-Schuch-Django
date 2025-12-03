import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages

from .models import PinProject, PinSettings
from .forms import (
    Step1KeywordsForm, Step2TextForm, Step3ImageForm,
    Step4LinkForm, Step5SEOForm, PinSettingsForm
)

logger = logging.getLogger(__name__)


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

    context = {
        'form': form,
        'project': project,
        'step': 3,
        'total_steps': 6,
        'has_ideogram_key': bool(request.user.ideogram_api_key),
        'has_openai_key': bool(request.user.openai_api_key),
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

    context = {
        'project': project,
        'step': 6,
        'total_steps': 6,
    }
    return render(request, 'ideopin/wizard/result.html', context)


# ==================== API VIEWS ====================

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
def api_generate_image(request, project_id):
    """API: Generiert Bild via Ideogram.ai"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not request.user.ideogram_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein Ideogram API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        from .ideogram_service import IdeogramService
        service = IdeogramService(request.user.ideogram_api_key)

        # Get user's preferred model and style from settings
        selected_model = None
        selected_style = None
        try:
            pin_settings = PinSettings.objects.get(user=request.user)
            selected_model = pin_settings.ideogram_model
            selected_style = pin_settings.ideogram_style
        except PinSettings.DoesNotExist:
            pass  # Will use defaults

        # Get dimensions from format
        width, height = project.get_format_dimensions()

        # Check if product image is provided
        has_product_image = bool(project.product_image)

        # Baue den Prompt basierend auf dem text_integration_mode
        if project.text_integration_mode == 'ideogram' and project.overlay_text:
            # Text soll von Ideogram direkt ins Bild integriert werden
            prompt = IdeogramService.build_prompt_with_text(
                background_description=project.background_description,
                overlay_text=project.overlay_text,
                text_position=project.text_position,
                text_style='modern',
                keywords=project.keywords,
                has_product_image=has_product_image
            )
            logger.info(f"Generating image WITH integrated text: {project.overlay_text}")
        else:
            # Nur Hintergrund generieren (für PIL-Overlay oder ohne Text)
            prompt = IdeogramService.build_prompt_without_text(
                background_description=project.background_description,
                keywords=project.keywords,
                has_product_image=has_product_image
            )
            logger.info("Generating image WITHOUT text (for PIL overlay or no text)")

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

            image_data = result['image_data']
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)

            filename = f"generated_{project.id}.png"
            project.generated_image.save(filename, ContentFile(image_data), save=True)

            # Bei Ideogram-Modus ist das generierte Bild auch das finale Bild
            if project.text_integration_mode == 'ideogram' and project.overlay_text:
                project.final_image.save(f"final_{project.id}.png", ContentFile(image_data), save=True)

            return JsonResponse({
                'success': True,
                'image_url': project.generated_image.url,
                'is_final': project.text_integration_mode == 'ideogram'
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
def api_generate_seo_description(request, project_id):
    """API: Generiert SEO-optimierte Pin-Beschreibung via GPT"""
    project = get_object_or_404(PinProject, id=project_id, user=request.user)

    if not request.user.openai_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Kein OpenAI API-Key konfiguriert. Bitte in Ihrem Profil hinterlegen.'
        }, status=400)

    try:
        from .ai_service import PinAIService
        ai_service = PinAIService(request.user)
        result = ai_service.generate_seo_description(
            keywords=project.keywords,
            image_description=project.background_description
        )

        if result.get('success'):
            project.seo_description = result['description']
            project.seo_description_ai_generated = True
            project.save()
            return JsonResponse({
                'success': True,
                'description': result['description']
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
    projects = PinProject.objects.filter(user=request.user).order_by('-updated_at')

    context = {
        'projects': projects,
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
            messages.success(request, 'Einstellungen wurden gespeichert.')
            return redirect('ideopin:settings')
    else:
        form = PinSettingsForm(instance=pin_settings)

    context = {
        'form': form,
        'has_ideogram_key': bool(request.user.ideogram_api_key),
        'has_openai_key': bool(request.user.openai_api_key),
    }
    return render(request, 'ideopin/settings.html', context)
