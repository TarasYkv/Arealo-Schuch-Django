from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.conf import settings
import json
import os
import time
import requests
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import io
import base64
import openai
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .models import ImageProject, ProcessingStep, ExportFormat, EngravingSettings, AIGenerationHistory
from .image_processing import ImageProcessor
from naturmacher.utils.api_helpers import get_user_api_key


@login_required
def dashboard_view(request):
    """Hauptseite der Bildbearbeitung"""
    # Benutzerstatistiken
    user_projects = ImageProject.objects.filter(user=request.user)
    user_ai_generations = AIGenerationHistory.objects.filter(user=request.user)
    
    stats = {
        'total_projects': user_projects.count(),
        'ai_generated': user_projects.filter(source_type='ai_generated').count(),
        'uploaded': user_projects.filter(source_type='upload').count(),
        'completed': user_projects.filter(status='completed').count(),
        'ai_generations': user_ai_generations.count(),
        'successful_generations': user_ai_generations.filter(success=True).count(),
    }
    
    # Letzte Projekte
    recent_projects = user_projects.order_by('-updated_at')[:6]
    
    # Letzte AI-Generierungen
    recent_ai = user_ai_generations.order_by('-created_at')[:5]
    
    context = {
        'stats': stats,
        'recent_projects': recent_projects,
        'recent_ai': recent_ai,
    }
    
    return render(request, 'image_editor/dashboard.html', context)


class ProjectListView(LoginRequiredMixin, ListView):
    """Liste aller Bildprojekte des Benutzers"""
    model = ImageProject
    template_name = 'image_editor/project_list.html'
    context_object_name = 'projects'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = ImageProject.objects.filter(user=self.request.user)
        
        # Filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(ai_prompt__icontains=search)
            )
        
        source_type = self.request.GET.get('source_type')
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Sortierung
        sort = self.request.GET.get('sort', '-updated_at')
        if sort:
            queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter-Parameter für URL
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']
        context['get_params'] = get_params.urlencode()
        
        return context


class ProjectDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht eines Bildprojekts"""
    model = ImageProject
    template_name = 'image_editor/project_detail.html'
    context_object_name = 'project'
    
    def get_queryset(self):
        return ImageProject.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['processing_steps'] = self.object.steps.all().order_by('applied_at')
        context['export_formats'] = self.object.exports.all().order_by('-created_at')
        
        # Gravur-Einstellungen falls vorhanden
        try:
            context['engraving_settings'] = self.object.engraving_settings
        except EngravingSettings.DoesNotExist:
            context['engraving_settings'] = None
        
        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    """Neues Bildprojekt erstellen"""
    model = ImageProject
    template_name = 'image_editor/project_create.html'
    fields = ['name', 'description', 'source_type', 'original_image']
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Bei Upload: Bildabmessungen ermitteln
        if form.instance.original_image:
            try:
                with Image.open(form.instance.original_image) as img:
                    form.instance.original_width = img.width
                    form.instance.original_height = img.height
                    form.instance.original_filename = form.instance.original_image.name
            except Exception as e:
                messages.error(self.request, f'Fehler beim Lesen der Bilddatei: {e}')
                return self.form_invalid(form)
        
        messages.success(self.request, f'Projekt "{form.instance.name}" wurde erstellt.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('image_editor:project_detail', kwargs={'pk': self.object.pk})


class ProjectEditView(LoginRequiredMixin, UpdateView):
    """Bildprojekt bearbeiten"""
    model = ImageProject
    template_name = 'image_editor/project_edit.html'
    fields = ['name', 'description', 'status']
    
    def get_queryset(self):
        return ImageProject.objects.filter(user=self.request.user)
    
    def get_success_url(self):
        return reverse('image_editor:project_detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    """Bildprojekt löschen"""
    model = ImageProject
    template_name = 'image_editor/project_delete.html'
    success_url = reverse_lazy('image_editor:project_list')
    
    def get_queryset(self):
        return ImageProject.objects.filter(user=self.request.user)


@login_required
def image_editor_view(request, pk):
    """Bildbearbeitungs-Interface"""
    project = get_object_or_404(ImageProject, pk=pk, user=request.user)
    
    # Shopify stores für Export-Funktionalität laden
    try:
        from shopify_manager.models import ShopifyStore
        import json
        shopify_stores = ShopifyStore.objects.filter(user=request.user)
        # Convert to JSON-serializable format
        shopify_stores_list = [
            {
                'id': store.id,
                'name': store.name,
                'shop_domain': store.shop_domain
            }
            for store in shopify_stores
        ]
        shopify_stores_json = json.dumps(shopify_stores_list)
    except ImportError:
        shopify_stores_json = '[]'
    except Exception:
        shopify_stores_json = '[]'
    
    context = {
        'project': project,
        'processing_steps': project.steps.all().order_by('applied_at'),
        'shopify_stores_json': shopify_stores_json,
    }
    
    return render(request, 'image_editor/editor.html', context)


@login_required
def ai_generation_view(request):
    """AI-Bildgenerierung Interface"""
    if request.method == 'POST':
        # Redirect zur API für eigentliche Generierung
        return redirect('image_editor:generate_ai_image')
    
    # GET: Zeige das Generierungs-Interface
    recent_generations = AIGenerationHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    context = {
        'recent_generations': recent_generations,
    }
    
    return render(request, 'image_editor/ai_generation.html', context)


@login_required
def ai_history_view(request):
    """Historie der AI-Generierungen"""
    generations = AIGenerationHistory.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(generations, 20)
    page = request.GET.get('page')
    generations = paginator.get_page(page)
    
    context = {
        'generations': generations,
    }
    
    return render(request, 'image_editor/ai_history.html', context)


# API Views

@require_http_methods(["POST"])
@login_required
def upload_image_api(request):
    """API: Bild hochladen"""
    try:
        if 'image' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'Keine Bilddatei gefunden'})
        
        image_file = request.FILES['image']
        project_name = request.POST.get('name', f'Hochgeladen am {timezone.now().strftime("%d.%m.%Y %H:%M")}')
        
        # Projekt erstellen
        project = ImageProject.objects.create(
            user=request.user,
            name=project_name,
            source_type='upload',
            original_image=image_file,
            original_filename=image_file.name
        )
        
        # Bildabmessungen ermitteln
        try:
            with Image.open(project.original_image) as img:
                project.original_width = img.width
                project.original_height = img.height
                project.save()
        except Exception:
            pass
        
        return JsonResponse({
            'success': True,
            'project_id': project.id,
            'redirect_url': reverse('image_editor:project_detail', kwargs={'pk': project.pk})
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def generate_ai_image_api(request):
    """API: AI-Bild generieren"""
    try:
        data = json.loads(request.body)
        prompt = data.get('prompt', '').strip()
        
        if not prompt:
            return JsonResponse({'success': False, 'error': 'Prompt ist erforderlich'})
        
        # AI-Generation starten
        generation_history = AIGenerationHistory.objects.create(
            user=request.user,
            prompt=prompt,
            ai_model=data.get('model', 'dall-e-3'),
            quality=data.get('quality', 'standard'),
            size=data.get('size', '1024x1024'),
        )
        
        start_time = time.time()
        
        try:
            # OpenAI API-Key holen
            api_key = get_user_api_key(request.user, 'openai')
            
            if not api_key:
                generation_history.success = False
                generation_history.error_message = "Kein OpenAI API-Key verfügbar"
                generation_history.save()
                return JsonResponse({
                    'success': False, 
                    'error': 'Kein OpenAI API-Key konfiguriert. Bitte in den Einstellungen hinzufügen.'
                })
            
            # OpenAI für alte Version (0.28.x) konfigurieren
            openai.api_key = api_key
            
            # Bild generieren mit alter API
            try:
                if generation_history.ai_model == 'dall-e-3':
                    # Versuche DALL-E 3 (falls unterstützt)
                    response = openai.Image.create(
                        prompt=prompt,
                        n=1,
                        size=generation_history.size if generation_history.size in ["1024x1024", "1792x1024", "1024x1792"] else "1024x1024",
                        model="dall-e-3"
                    )
                else:
                    # DALL-E 2
                    response = openai.Image.create(
                        prompt=prompt,
                        n=1,
                        size="1024x1024" if generation_history.size not in ["256x256", "512x512", "1024x1024"] else generation_history.size
                    )
            except Exception as dalle3_error:
                # Fallback zu DALL-E 2 wenn DALL-E 3 nicht verfügbar
                try:
                    response = openai.Image.create(
                        prompt=prompt,
                        n=1,
                        size="1024x1024"
                    )
                    generation_history.ai_model = 'dall-e-2'  # Update model in history
                except Exception as dalle2_error:
                    raise Exception(f"AI-Generierung fehlgeschlagen: {str(dalle2_error)}")
            
            # Generiertes Bild herunterladen und speichern
            image_url = response['data'][0]['url']
            
            # Bild von URL herunterladen
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            
            # Neues ImageProject erstellen
            project = ImageProject.objects.create(
                user=request.user,
                name=f"AI-Generiert: {prompt[:50]}...",
                source_type='ai_generated',
                status='completed'
            )
            
            # Bild speichern
            image_content = ContentFile(img_response.content)
            project.original_image.save(
                f"ai_generated_{project.id}.png",
                image_content,
                save=True
            )
            
            # Bildgrößen setzen
            with Image.open(project.original_image) as img:
                project.original_width = img.width
                project.original_height = img.height
                project.save()
            
            # Generation History aktualisieren
            generation_time = time.time() - start_time
            generation_history.generation_time = generation_time
            generation_history.success = True
            generation_history.generated_project = project
            generation_history.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Bild wurde erfolgreich generiert!',
                'generation_id': generation_history.id,
                'project_id': project.id,
                'redirect_url': reverse('image_editor:project_detail', args=[project.id])
            })
            
        except Exception as e:
            generation_history.success = False
            generation_history.error_message = str(e)
            generation_history.save()
            
            return JsonResponse({'success': False, 'error': f'AI-Generierung fehlgeschlagen: {str(e)}'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def process_image_api(request):
    """API: Bildbearbeitung anwenden"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        operation = data.get('operation')
        parameters = data.get('parameters', {})
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        start_time = time.time()
        
        # Bildverarbeitung mit ImageProcessor - verwende das zuletzt bearbeitete Bild
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        
        # Anwenden der Operation
        success = False
        if operation == 'invert':
            success, message = processor.invert()
        elif operation == 'grayscale':
            success, message = processor.convert_to_grayscale()
        elif operation == 'brightness':
            factor = parameters.get('factor', 1.0)
            success, message = processor.adjust_brightness(factor)
        elif operation == 'contrast':
            factor = parameters.get('factor', 1.0)
            success, message = processor.adjust_contrast(factor)
        elif operation == 'saturation':
            factor = parameters.get('factor', 1.0)
            success, message = processor.adjust_saturation(factor)
        else:
            return JsonResponse({'success': False, 'error': f'Operation "{operation}" nicht unterstützt'})
        
        if not success:
            return JsonResponse({'success': False, 'error': message})
        
        # Bearbeitetes Bild speichern
        processed_file = processor.save_to_file()
        filename = f"processed_{project.id}_{int(time.time())}.jpg"
        saved_path = default_storage.save(f'images/processed/{filename}', processed_file)
        
        # Bearbeitungsschritt speichern
        step = ProcessingStep.objects.create(
            project=project,
            operation=operation,
            parameters=parameters,
            processing_time=time.time() - start_time
        )
        
        # Projekt aktualisieren
        project.processed_image = saved_path
        project.processing_history.append({
            'operation': operation,
            'parameters': parameters,
            'timestamp': timezone.now().isoformat(),
            'step_id': step.id
        })
        project.status = 'completed'
        project.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Operation "{operation}" wurde angewendet',
            'step_id': step.id,
            'preview_base64': processor.get_current_image_base64()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def apply_image_operation(image_file, operation, parameters):
    """Bildbearbeitung durchführen"""
    try:
        with Image.open(image_file) as img:
            if operation == 'invert':
                return ImageOps.invert(img.convert('RGB'))
            elif operation == 'grayscale':
                return ImageOps.grayscale(img)
            elif operation == 'brightness':
                enhancer = ImageEnhance.Brightness(img)
                return enhancer.enhance(parameters.get('factor', 1.5))
            elif operation == 'contrast':
                enhancer = ImageEnhance.Contrast(img)
                return enhancer.enhance(parameters.get('factor', 1.5))
            elif operation == 'saturation':
                enhancer = ImageEnhance.Color(img)
                return enhancer.enhance(parameters.get('factor', 1.5))
            elif operation == 'blur':
                return img.filter(ImageFilter.GaussianBlur(parameters.get('radius', 2)))
            elif operation == 'sharpen':
                return img.filter(ImageFilter.SHARPEN)
            # Weitere Operationen können hier hinzugefügt werden
            
        return None
    except Exception:
        return None


@require_http_methods(["POST"])
@login_required
def apply_advanced_filter_api(request):
    """API: Erweiterte Filter anwenden"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        filter_type = data.get('filter_type')
        filter_params = data.get('parameters', {})
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        start_time = time.time()
        
        # Bildverarbeitung mit ImageProcessor - IMMER das Originalbild verwenden
        processor = ImageProcessor(project.original_image)
        success, message = processor.apply_advanced_filter(filter_type, **filter_params)
        
        if success:
            # Bearbeitetes Bild speichern
            processed_file = processor.save_to_file(format='PNG')
            filename = f"filtered_{filter_type}_{project.id}_{int(time.time())}.png"
            saved_path = default_storage.save(f'images/processed/{filename}', processed_file)
            
            # Bearbeitungsschritt speichern
            step = ProcessingStep.objects.create(
                project=project,
                operation=filter_type,
                parameters=filter_params,
                processing_time=time.time() - start_time
            )
            
            # Projekt aktualisieren
            project.processed_image = saved_path
            project.processing_history.append({
                'operation': filter_type,
                'parameters': filter_params,
                'timestamp': timezone.now().isoformat(),
                'step_id': step.id
            })
            project.status = 'processing'
            project.save()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'step_id': step.id,
                'preview_url': f'/media/{saved_path}',
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def batch_process_api(request):
    """API: Batch-Verarbeitung für mehrere Projekte"""
    try:
        data = json.loads(request.body)
        project_ids = data.get('project_ids', [])
        operations = data.get('operations', [])
        
        if not project_ids or not operations:
            return JsonResponse({'success': False, 'error': 'Projekt-IDs und Operationen sind erforderlich'})
        
        projects = ImageProject.objects.filter(pk__in=project_ids, user=request.user)
        
        if projects.count() != len(project_ids):
            return JsonResponse({'success': False, 'error': 'Einige Projekte wurden nicht gefunden'})
        
        results = []
        
        for project in projects:
            if not project.original_image:
                results.append({
                    'project_id': project.id,
                    'success': False,
                    'error': 'Kein Ausgangsbild vorhanden'
                })
                continue
            
            try:
                # Verwende das zuletzt bearbeitete Bild für kumulative Bearbeitung
                current_image = project.original_image
                processor = ImageProcessor(current_image)
                project_results = []
                
                for operation in operations:
                    op_type = operation.get('type')
                    op_params = operation.get('parameters', {})
                    
                    if op_type == 'remove_background':
                        success, message = processor.remove_background(**op_params)
                    elif op_type == 'prepare_engraving':
                        success, message = processor.prepare_for_engraving(**op_params)
                    elif op_type == 'enhance_lines':
                        success, message = processor.enhance_lines_for_engraving(**op_params)
                    elif op_type in ['emboss', 'edge_detect', 'oil_painting', 'pencil_sketch', 'vintage']:
                        success, message = processor.apply_advanced_filter(op_type, **op_params)
                    else:
                        success, message = False, f"Unbekannte Operation: {op_type}"
                    
                    project_results.append({
                        'operation': op_type,
                        'success': success,
                        'message': message
                    })
                    
                    if not success:
                        break
                
                # Speichere finales Ergebnis falls alle Operationen erfolgreich
                if all(r['success'] for r in project_results):
                    processed_file = processor.save_to_file(format='PNG')
                    filename = f"batch_{project.id}_{int(time.time())}.png"
                    saved_path = default_storage.save(f'images/processed/{filename}', processed_file)
                    
                    project.processed_image = saved_path
                    project.processing_history.extend([{
                        'operation': 'batch_processing',
                        'parameters': {'operations': operations},
                        'timestamp': timezone.now().isoformat(),
                    }])
                    project.status = 'completed'
                    project.save()
                
                results.append({
                    'project_id': project.id,
                    'success': all(r['success'] for r in project_results),
                    'operations': project_results
                })
                
            except Exception as e:
                results.append({
                    'project_id': project.id,
                    'success': False,
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': True,
            'message': f'Batch-Verarbeitung abgeschlossen für {len(projects)} Projekte',
            'results': results
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_live_preview_api(request, project_id):
    """API: Live-Vorschau für ein Projekt"""
    try:
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        # Verwende processed_image falls vorhanden, sonst original
        image_source = project.original_image
        
        if not image_source:
            return JsonResponse({'success': False, 'error': 'Kein Bild vorhanden'})
        
        processor = ImageProcessor(image_source)
        
        return JsonResponse({
            'success': True,
            'preview_base64': processor.get_current_image_base64(),
            'image_info': {
                'width': processor.current_image.width,
                'height': processor.current_image.height,
                'mode': processor.current_image.mode,
                'format': processor.current_image.format or 'Unknown'
            },
            'processing_history': project.processing_history
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def remove_background_api(request):
    """API: Hintergrund entfernen"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        model = data.get('model', 'u2net')
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        start_time = time.time()
        
        # Bildverarbeitung mit ImageProcessor - verwende das zuletzt bearbeitete Bild
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        success, message = processor.remove_background(model=model)
        
        if success:
            # Bearbeitetes Bild speichern
            processed_file = processor.save_to_file(format='PNG')
            filename = f"processed_{project.id}_{int(time.time())}.png"
            saved_path = default_storage.save(f'images/processed/{filename}', processed_file)
            
            # Bearbeitungsschritt speichern
            step = ProcessingStep.objects.create(
                project=project,
                operation='remove_background',
                parameters={'model': model},
                processing_time=time.time() - start_time
            )
            
            # Projekt aktualisieren
            project.processed_image = saved_path
            project.processing_history.append({
                'operation': 'remove_background',
                'parameters': {'model': model},
                'timestamp': timezone.now().isoformat(),
                'step_id': step.id
            })
            project.status = 'processing'
            project.save()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'step_id': step.id,
                'preview_url': f'/media/{saved_path}',
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def prepare_engraving_api(request):
    """API: Bild für Gravur vorbereiten"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        beam_width = float(data.get('beam_width', 0.1))
        line_thickness = float(data.get('line_thickness', 0.1))
        depth_levels = int(data.get('depth_levels', 5))
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        start_time = time.time()
        
        # Bildverarbeitung mit ImageProcessor - verwende das zuletzt bearbeitete Bild
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        success, message = processor.prepare_for_engraving(
            beam_width=beam_width,
            line_thickness=line_thickness,
            depth_levels=depth_levels
        )
        
        if success:
            # Bearbeitetes Bild speichern
            processed_file = processor.save_to_file(format='PNG')
            filename = f"engraving_{project.id}_{int(time.time())}.png"
            saved_path = default_storage.save(f'images/processed/{filename}', processed_file)
            
            # Gravur-Einstellungen speichern oder aktualisieren
            engraving_settings, created = EngravingSettings.objects.get_or_create(
                project=project,
                defaults={
                    'beam_width': beam_width,
                    'line_thickness': line_thickness,
                    'depth_levels': depth_levels,
                }
            )
            
            if not created:
                engraving_settings.beam_width = beam_width
                engraving_settings.line_thickness = line_thickness
                engraving_settings.depth_levels = depth_levels
                engraving_settings.save()
            
            # Bearbeitungsschritt speichern
            step = ProcessingStep.objects.create(
                project=project,
                operation='prepare_engraving',
                parameters={
                    'beam_width': beam_width,
                    'line_thickness': line_thickness,
                    'depth_levels': depth_levels
                },
                processing_time=time.time() - start_time
            )
            
            # Projekt aktualisieren
            project.processed_image = saved_path
            project.processing_history.append({
                'operation': 'prepare_engraving',
                'parameters': {
                    'beam_width': beam_width,
                    'line_thickness': line_thickness,
                    'depth_levels': depth_levels
                },
                'timestamp': timezone.now().isoformat(),
                'step_id': step.id
            })
            project.status = 'processing'
            project.save()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'step_id': step.id,
                'preview_url': f'/media/{saved_path}',
                'preview_base64': processor.get_current_image_base64(),
                'engraving_settings_id': engraving_settings.id
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def vectorize_image_api(request):
    """API: Bild in Vektor umwandeln"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        threshold = int(data.get('threshold', 128))
        simplify_tolerance = float(data.get('simplify_tolerance', 1.0))
        enhance_lines = data.get('enhance_lines', False)
        line_width = int(data.get('line_width', 2))
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        start_time = time.time()
        
        # Bildverarbeitung mit ImageProcessor - verwende das zuletzt bearbeitete Bild
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        
        # Optional: Linien verstärken vor Vektorisierung
        if enhance_lines:
            enhance_success, enhance_msg = processor.enhance_lines_for_engraving(line_width=line_width)
            if not enhance_success:
                return JsonResponse({'success': False, 'error': f'Linienverstärkung fehlgeschlagen: {enhance_msg}'})
        
        # Vektorisierung
        success, message, svg_content = processor.vectorize_for_engraving(
            threshold=threshold,
            simplify_tolerance=simplify_tolerance
        )
        
        if success:
            # SVG-Datei speichern
            svg_filename = f"vector_{project.id}_{int(time.time())}.svg"
            svg_path = default_storage.save(f'images/vectors/{svg_filename}', ContentFile(svg_content))
            
            # Bearbeitungsschritt speichern
            step = ProcessingStep.objects.create(
                project=project,
                operation='vectorize',
                parameters={
                    'threshold': threshold,
                    'simplify_tolerance': simplify_tolerance,
                    'enhance_lines': enhance_lines,
                    'line_width': line_width if enhance_lines else None
                },
                processing_time=time.time() - start_time
            )
            
            # Projekt aktualisieren
            project.processing_history.append({
                'operation': 'vectorize',
                'parameters': {
                    'threshold': threshold,
                    'simplify_tolerance': simplify_tolerance,
                    'enhance_lines': enhance_lines
                },
                'timestamp': timezone.now().isoformat(),
                'step_id': step.id,
                'svg_path': svg_path
            })
            project.status = 'processing'
            project.save()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'step_id': step.id,
                'svg_url': f'/media/{svg_path}',
                'svg_content': svg_content,
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def export_image_api(request):
    """API: Bild exportieren"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        format_type = data.get('format', 'PNG').upper()
        quality = data.get('quality', 'high')
        width = data.get('width')
        height = data.get('height')
        dpi = int(data.get('dpi', 300))
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        # Verwende processed_image falls vorhanden, sonst original
        image_source = project.original_image
        
        start_time = time.time()
        
        # Bildverarbeitung mit ImageProcessor
        processor = ImageProcessor(image_source)
        
        # Größe anpassen falls gewünscht
        if width and height:
            current_img = processor.current_image
            resized_img = current_img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
            processor.current_image = resized_img
        
        # Qualitätseinstellungen
        quality_settings = {
            'low': 60,
            'medium': 80, 
            'high': 95,
            'max': 100
        }
        
        jpeg_quality = quality_settings.get(quality, 95)
        
        # Export-Parameter basierend auf Format
        export_kwargs = {}
        if format_type == 'JPEG':
            export_kwargs = {'quality': jpeg_quality, 'optimize': True}
        elif format_type == 'PNG':
            export_kwargs = {'optimize': True}
        elif format_type == 'WEBP':
            export_kwargs = {'quality': jpeg_quality, 'method': 6}
        elif format_type == 'TIFF':
            export_kwargs = {'compression': 'tiff_lzw', 'dpi': (dpi, dpi)}
        elif format_type == 'PDF':
            export_kwargs = {'resolution': dpi}
        
        # Bild exportieren
        exported_file = processor.save_to_file(format=format_type, **export_kwargs)
        
        # Datei speichern
        filename = f"export_{project.id}_{int(time.time())}.{format_type.lower()}"
        saved_path = default_storage.save(f'images/exports/{filename}', exported_file)
        
        # Export-Record erstellen
        export_record = ExportFormat.objects.create(
            project=project,
            format_type=format_type,
            quality=quality,
            width=width,
            height=height,
            dpi=dpi,
            file_path=saved_path,
            file_size=exported_file.size if hasattr(exported_file, 'size') else None
        )
        
        processing_time = time.time() - start_time
        
        return JsonResponse({
            'success': True,
            'message': f'Bild erfolgreich als {format_type} exportiert',
            'export_id': export_record.id,
            'download_url': reverse('image_editor:download_image', kwargs={
                'project_id': project.id,
                'format': format_type.lower()
            }),
            'file_size': export_record.file_size,
            'processing_time': round(processing_time, 2),
            'preview_url': f'/media/{saved_path}'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def preview_filter_api(request):
    """API: Filter-Vorschau ohne Speichern"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        filter_type = data.get('filter_type')
        filter_params = data.get('parameters', {})
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        # Bildverarbeitung ohne Speichern - verwende das aktuelle Bild
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        success, message = processor.apply_advanced_filter(filter_type, **filter_params)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Vorschau erstellt',
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def preview_remove_background_api(request):
    """API: Hintergrund-Entfernung Vorschau ohne Speichern"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        model = data.get('model', 'u2net')
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        # Bildverarbeitung ohne Speichern
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        success, message = processor.remove_background(model=model)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Vorschau erstellt',
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def preview_prepare_engraving_api(request):
    """API: Gravur-Vorbereitung Vorschau ohne Speichern"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        beam_width = float(data.get('beam_width', 0.1))
        line_thickness = float(data.get('line_thickness', 0.1))
        depth_levels = int(data.get('depth_levels', 5))
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        # Bildverarbeitung ohne Speichern
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        success, message = processor.prepare_for_engraving(
            beam_width=beam_width,
            line_thickness=line_thickness,
            depth_levels=depth_levels
        )
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Vorschau erstellt',
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def preview_vectorize_api(request):
    """API: Vektorisierung Vorschau ohne Speichern"""
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        threshold = int(data.get('threshold', 128))
        simplify_tolerance = float(data.get('simplify_tolerance', 1.0))
        enhance_lines = data.get('enhance_lines', False)
        line_width = int(data.get('line_width', 2))
        
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        if not project.original_image:
            return JsonResponse({'success': False, 'error': 'Kein Ausgangsbild vorhanden'})
        
        # Bildverarbeitung ohne Speichern
        current_image = project.original_image
        processor = ImageProcessor(current_image)
        
        # Optional: Linien verstärken vor Vektorisierung
        if enhance_lines:
            enhance_success, enhance_msg = processor.enhance_lines_for_engraving(line_width=line_width)
            if not enhance_success:
                return JsonResponse({'success': False, 'error': f'Linienverstärkung fehlgeschlagen: {enhance_msg}'})
        
        # Für Vektorisierung zeigen wir nur die bearbeitete Raster-Version als Vorschau
        # Das eigentliche SVG wird erst bei der finalen Anwendung erstellt
        success, message = processor.prepare_for_engraving(
            beam_width=0.1,
            line_thickness=0.1,
            depth_levels=2  # Vereinfacht für Vorschau
        )
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Vektorisierung-Vorschau erstellt',
                'preview_base64': processor.get_current_image_base64()
            })
        else:
            return JsonResponse({'success': False, 'error': message})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def canva_import_view(request):
    """Seite zum Importieren von Canva-Designs"""
    try:
        from naturmacher.models import CanvaAPISettings
        from naturmacher.canva_service import CanvaAPIService
        
        # Prüfe Canva-Einstellungen
        canva_settings = CanvaAPISettings.objects.get(user=request.user)
        
        if not canva_settings.has_access_token():
            messages.error(request, 'Bitte verbinden Sie zuerst Ihr Canva-Konto in den API-Einstellungen.')
            return redirect('accounts:manage_api_keys')
        
        canva_service = CanvaAPIService(request.user)
        designs = []
        error_message = None
        
        try:
            # Designs von Canva laden
            designs_data = canva_service.list_designs(limit=20)
            designs = designs_data.get('items', [])
        except Exception as e:
            error_message = f"Fehler beim Laden der Designs: {str(e)}"
        
        context = {
            'designs': designs,
            'error_message': error_message,
            'canva_settings': canva_settings
        }
        
        return render(request, 'image_editor/canva_import.html', context)
        
    except CanvaAPISettings.DoesNotExist:
        messages.error(request, 'Bitte konfigurieren Sie zuerst Ihre Canva-Einstellungen.')
        return redirect('accounts:manage_api_keys')


@require_http_methods(["POST"])
@login_required
def canva_import_design_api(request):
    """API: Importiert ein spezifisches Canva-Design"""
    try:
        data = json.loads(request.body)
        design_id = data.get('design_id')
        project_name = data.get('project_name')
        
        if not design_id:
            return JsonResponse({'success': False, 'error': 'Design ID ist erforderlich'})
        
        from naturmacher.canva_service import CanvaAPIService
        
        canva_service = CanvaAPIService(request.user)
        project = canva_service.import_design_to_project(design_id, project_name)
        
        return JsonResponse({
            'success': True,
            'message': f'Design "{project.name}" erfolgreich importiert',
            'project_id': project.id,
            'redirect_url': reverse('image_editor:project_detail', kwargs={'pk': project.pk})
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def canva_designs_api(request):
    """API: Lädt weitere Canva-Designs für Pagination"""
    try:
        from naturmacher.canva_service import CanvaAPIService
        
        canva_service = CanvaAPIService(request.user)
        continuation_token = request.GET.get('continuation_token')
        limit = int(request.GET.get('limit', 20))
        
        designs_data = canva_service.list_designs(limit=limit, continuation_token=continuation_token)
        
        return JsonResponse({
            'success': True,
            'items': designs_data.get('items', []),
            'continuation_token': designs_data.get('continuation_token')
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def download_image_view(request, project_id, format):
    """Download eines bearbeiteten Bildes"""
    try:
        project = get_object_or_404(ImageProject, pk=project_id, user=request.user)
        
        # Finde den neuesten Export für das gewünschte Format
        export_record = ExportFormat.objects.filter(
            project=project,
            format_type=format.upper()
        ).order_by('-created_at').first()
        
        if not export_record or not export_record.file_path:
            # Erstelle Export falls nicht vorhanden
            processor = ImageProcessor(project.original_image)
            exported_file = processor.save_to_file(format=format.upper())
            
            filename = f"export_{project.id}_{int(time.time())}.{format.lower()}"
            saved_path = default_storage.save(f'images/exports/{filename}', exported_file)
            
            export_record = ExportFormat.objects.create(
                project=project,
                format_type=format.upper(),
                quality='high',
                file_path=saved_path,
                file_size=exported_file.size if hasattr(exported_file, 'size') else None
            )
        
        # Datei zum Download bereitstellen
        file_path = export_record.file_path
        
        if default_storage.exists(file_path):
            with default_storage.open(file_path, 'rb') as f:
                file_content = f.read()
            
            # MIME-Type basierend auf Format
            mime_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'webp': 'image/webp',
                'tiff': 'image/tiff',
                'pdf': 'application/pdf',
                'svg': 'image/svg+xml'
            }
            
            mime_type = mime_types.get(format.lower(), 'application/octet-stream')
            
            response = HttpResponse(file_content, content_type=mime_type)
            response['Content-Disposition'] = f'attachment; filename="{project.name}_{int(time.time())}.{format.lower()}"'
            response['Content-Length'] = len(file_content)
            
            return response
        else:
            raise Http404("Export-Datei nicht gefunden")
            
    except Exception as e:
        raise Http404(f"Download fehlgeschlagen: {str(e)}")


# === Shopify Integration Views ===

@login_required
def shopify_import_view(request):
    """Shopify Import Interface"""
    from shopify_manager.models import ShopifyStore
    
    # Store ID aus URL-Parameter lesen
    store_id = request.GET.get('store_id')
    store = None
    
    if store_id:
        try:
            store = ShopifyStore.objects.get(id=store_id, user=request.user)
        except ShopifyStore.DoesNotExist:
            messages.error(request, 'Shopify Store nicht gefunden.')
            return redirect('image_editor:dashboard')
    
    # Alle verfügbaren Stores des Benutzers
    stores = ShopifyStore.objects.filter(user=request.user, is_active=True)
    
    context = {
        'stores': stores,
        'selected_store': store,
        'store_id': store_id
    }
    
    return render(request, 'image_editor/shopify_import.html', context)


@login_required
@require_http_methods(["POST"])
def shopify_images_api(request):
    """API: Holt Bilder von einem Shopify Store"""
    try:
        import json
        from shopify_manager.models import ShopifyStore
        from .shopify_service import ShopifyImageService
        
        data = json.loads(request.body)
        store_id = data.get('store_id')
        limit = data.get('limit', 50)
        
        if not store_id:
            return JsonResponse({
                'success': False,
                'error': 'Store ID ist erforderlich'
            })
        
        store = ShopifyStore.objects.get(id=store_id, user=request.user)
        service = ShopifyImageService(store)
        
        success, images, message = service.get_product_images(limit=limit)
        
        return JsonResponse({
            'success': success,
            'images': images if success else [],
            'message': message,
            'count': len(images) if success else 0
        })
        
    except ShopifyStore.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Laden der Bilder: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def shopify_import_image_api(request):
    """API: Importiert ein Bild von Shopify in den Image Editor"""
    try:
        import json
        from shopify_manager.models import ShopifyStore
        from .shopify_service import ShopifyImageService
        from .models import ImageProject
        
        data = json.loads(request.body)
        store_id = data.get('store_id')
        image_url = data.get('image_url')
        image_alt = data.get('alt_text', '')
        product_title = data.get('product_title', 'Shopify Import')
        
        if not store_id or not image_url:
            return JsonResponse({
                'success': False,
                'error': 'Store ID und Bild-URL sind erforderlich'
            })
        
        store = ShopifyStore.objects.get(id=store_id, user=request.user)
        service = ShopifyImageService(store)
        
        # Bild herunterladen
        success, file_path, message = service.download_image(image_url, image_alt)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': message
            })
        
        # Neues Projekt erstellen
        project_name = f"{product_title} - {image_alt}" if image_alt else product_title
        project = ImageProject.objects.create(
            name=project_name,
            user=request.user,
            source_type='shopify_import'
        )
        
        # Bild-Pfad korrekt setzen
        project.original_image.name = file_path
        
        # Bildabmessungen ermitteln
        try:
            from PIL import Image
            full_path = project.original_image.path
            with Image.open(full_path) as img:
                project.original_width = img.width
                project.original_height = img.height
        except Exception:
            pass
        
        project.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Bild erfolgreich importiert: {project_name}',
            'project_id': project.id,
            'project_url': f'/images/projects/{project.id}/editor/'
        })
        
    except ShopifyStore.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Importieren: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def shopify_export_image_api(request):
    """API: Exportiert ein Bild zum Shopify Store"""
    try:
        import json
        from shopify_manager.models import ShopifyStore
        from .shopify_service import ShopifyImageService
        from .models import ImageProject
        
        data = json.loads(request.body)
        store_id = data.get('store_id')
        project_id = data.get('project_id')
        export_type = data.get('export_type', 'new_product')  # 'new_product', 'existing_product', 'update_image'
        product_id = data.get('product_id')
        product_title = data.get('product_title', '')
        product_description = data.get('product_description', '')
        alt_text = data.get('alt_text', '')
        
        if not store_id or not project_id:
            return JsonResponse({
                'success': False,
                'error': 'Store ID und Projekt ID sind erforderlich'
            })
        
        store = ShopifyStore.objects.get(id=store_id, user=request.user)
        project = ImageProject.objects.get(id=project_id, user=request.user)
        service = ShopifyImageService(store)
        
        # Verarbeitetes Bild verwenden, falls verfügbar
        image_path = project.original_image.path
        
        if export_type == 'new_product':
            if not product_title:
                product_title = f"Projekt: {project.name}"
            
            success, result, message = service.create_product_with_image(
                image_path, product_title, product_description, alt_text
            )
        elif export_type == 'existing_product':
            if not product_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Produkt ID ist für bestehende Produkte erforderlich'
                })
            
            success, result, message = service.upload_image_to_product(
                image_path, product_id, alt_text
            )
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ungültiger Export-Typ'
            })
        
        if success:
            return JsonResponse({
                'success': True,
                'message': message,
                'shopify_data': result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
        
    except ShopifyStore.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store nicht gefunden'
        })
    except ImageProject.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Projekt nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Export: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def shopify_products_api(request):
    """API: Holt Produkte von einem Shopify Store"""
    try:
        import json
        from shopify_manager.models import ShopifyStore
        from .shopify_service import ShopifyImageService
        
        data = json.loads(request.body)
        store_id = data.get('store_id')
        limit = data.get('limit', 50)
        search_term = data.get('search', '')
        
        if not store_id:
            return JsonResponse({
                'success': False,
                'error': 'Store ID ist erforderlich'
            })
        
        store = ShopifyStore.objects.get(id=store_id, user=request.user)
        service = ShopifyImageService(store)
        
        if search_term:
            success, products, message = service.search_products_for_export(search_term=search_term, limit=limit)
        else:
            success, products, message = service.get_products_for_export(limit=limit)
        
        return JsonResponse({
            'success': success,
            'products': products if success else [],
            'message': message,
            'count': len(products) if success else 0
        })
        
    except ShopifyStore.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Laden der Produkte: {str(e)}'
        })