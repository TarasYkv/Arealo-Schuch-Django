from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
import json

from .models import ShopifyStore, ShopifyCollection, CollectionSEOOptimization
from .ai_seo_service import generate_seo_with_ai
from .shopify_api import ShopifyAPIClient, ShopifyCollectionSync
from .collection_forms import CollectionFilterForm, CollectionSEOOptimizationForm


class ShopifyCollectionListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Kategorien"""
    model = ShopifyCollection
    template_name = 'shopify_manager/collection_list.html'
    context_object_name = 'collections'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = ShopifyCollection.objects.filter(store__user=self.request.user)
        
        # Filter anwenden
        form = CollectionFilterForm(self.request.GET)
        if form.is_valid():
            search = form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(handle__icontains=search)
                )
            
            published = form.cleaned_data.get('published')
            if published == 'true':
                queryset = queryset.filter(published=True)
            elif published == 'false':
                queryset = queryset.filter(published=False)
            
            sync_status = form.cleaned_data.get('sync_status')
            if sync_status == 'needs_sync':
                queryset = queryset.filter(needs_sync=True)
            elif sync_status == 'sync_error':
                queryset = queryset.exclude(sync_error='')
            elif sync_status == 'synced':
                queryset = queryset.filter(needs_sync=False, sync_error='')
            
            seo_issues_only = form.cleaned_data.get('seo_issues_only')
            if seo_issues_only:
                queryset = queryset.filter(
                    Q(seo_title='') | Q(seo_description='')
                )
            
            # SEO-Score Filterung
            seo_score = form.cleaned_data.get('seo_score')
            if seo_score:
                collection_ids = []
                for collection in queryset:
                    if collection.get_combined_seo_status() == seo_score:
                        collection_ids.append(collection.id)
                queryset = queryset.filter(id__in=collection_ids)
            
            sort = form.cleaned_data.get('sort', '-updated_at')
            if sort:
                queryset = queryset.order_by(sort)
        
        # Sortierung nach SEO-Score (schlechteste zuerst)
        queryset = queryset.select_related('store')
        
        collections_with_scores = []
        for collection in queryset:
            collections_with_scores.append((collection.get_seo_score(), collection.id))
        
        collections_with_scores.sort(key=lambda x: x[0])
        sorted_ids = [item[1] for item in collections_with_scores]
        
        from django.db.models import Case, When
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_ids)])
        
        return queryset.filter(id__in=sorted_ids).order_by(preserved)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = CollectionFilterForm(self.request.GET)
        
        # Statistiken
        user_collections = ShopifyCollection.objects.filter(store__user=self.request.user)
        context['stats'] = {
            'total_collections': user_collections.count(),
            'published_collections': user_collections.filter(published=True).count(),
            'needs_sync': user_collections.filter(needs_sync=True).count(),
            'sync_errors': user_collections.exclude(sync_error='').count(),
            'seo_issues': user_collections.filter(
                Q(seo_title='') | Q(seo_description='')
            ).count(),
        }
        
        # Stores für Import-Dropdown
        context['user_stores'] = ShopifyStore.objects.filter(user=self.request.user, is_active=True)
        
        # GET-Parameter für Pagination
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']
        context['get_params'] = get_params.urlencode()
        
        return context


class ShopifyCollectionDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer Shopify Kategorie"""
    model = ShopifyCollection
    template_name = 'shopify_manager/collection_detail.html'
    context_object_name = 'collection'
    
    def get_queryset(self):
        return ShopifyCollection.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # SEO-Details
        context['seo_details'] = self.object.get_seo_details()
        context['alt_text_details'] = self.object.get_alt_text_details()
        
        # Letzte SEO-Optimierung
        context['last_optimization'] = self.object.seo_optimizations.first()
        
        return context


class ShopifyCollectionUpdateView(LoginRequiredMixin, UpdateView):
    """Shopify Kategorie bearbeiten"""
    model = ShopifyCollection
    fields = ['title', 'description', 'seo_title', 'seo_description', 'image_alt']
    template_name = 'shopify_manager/collection_edit.html'
    
    def get_queryset(self):
        return ShopifyCollection.objects.filter(store__user=self.request.user)
    
    def form_valid(self, form):
        # Markiere für Synchronisation
        form.instance.mark_for_sync()
        
        messages.success(self.request, f'Kategorie "{form.instance.title}" erfolgreich aktualisiert.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('shopify_manager:collection_detail', kwargs={'pk': self.object.pk})


@login_required
def collection_seo_optimization_view(request, collection_id):
    """SEO-Optimierung für Kategorien mit KI-Unterstützung"""
    collection = get_object_or_404(ShopifyCollection, id=collection_id, store__user=request.user)
    
    if request.method == 'POST':
        form = CollectionSEOOptimizationForm(request.POST)
        if form.is_valid():
            keywords = form.cleaned_data['keywords']
            ai_model = form.cleaned_data['ai_model']
            
            try:
                # Erstelle SEO-Optimierung
                optimization = CollectionSEOOptimization.objects.create(
                    collection=collection,
                    keywords=keywords,
                    ai_model=ai_model,
                    original_title=collection.title,
                    original_description=collection.description,
                    original_seo_title=collection.seo_title,
                    original_seo_description=collection.seo_description,
                )
                
                # Generiere SEO-Daten mit KI
                success, result = generate_seo_with_ai(
                    content_title=collection.title,
                    content_description=collection.description,
                    keywords=keywords,
                    ai_model=ai_model,
                    content_type='collection'
                )
                
                if success:
                    optimization.generated_seo_title = result.get('seo_title', '')
                    optimization.generated_seo_description = result.get('seo_description', '')
                    optimization.ai_prompt_used = result.get('prompt_used', '')
                    optimization.ai_response_raw = result.get('raw_response', '')
                    optimization.save()
                    
                    messages.success(request, 'SEO-Optimierung erfolgreich generiert!')
                    return redirect('shopify_manager:collection_detail', pk=collection.pk)
                else:
                    messages.error(request, f'Fehler bei der SEO-Generierung: {result}')
                    optimization.delete()
                    
            except Exception as e:
                messages.error(request, f'Fehler bei der SEO-Optimierung: {str(e)}')
        
    else:
        form = CollectionSEOOptimizationForm()
    
    context = {
        'collection': collection,
        'form': form,
        'seo_details': collection.get_seo_details(),
    }
    return render(request, 'shopify_manager/collection_seo_optimization.html', context)


@login_required
@require_http_methods(["POST"])
def apply_collection_seo_optimization_view(request, optimization_id):
    """Wendet eine SEO-Optimierung auf eine Kategorie an"""
    optimization = get_object_or_404(CollectionSEOOptimization, id=optimization_id, collection__store__user=request.user)
    
    try:
        optimization.apply_to_collection()
        messages.success(request, f'SEO-Optimierung erfolgreich auf Kategorie "{optimization.collection.title}" angewendet.')
        return redirect('shopify_manager:collection_detail', pk=optimization.collection.pk)
    except Exception as e:
        messages.error(request, f'Fehler beim Anwenden der SEO-Optimierung: {str(e)}')
        return redirect('shopify_manager:collection_detail', pk=optimization.collection.pk)


@login_required
def collection_import_view(request):
    """Importiert Kategorien von Shopify"""
    if request.method == 'POST':
        store_id = request.POST.get('store_id')
        if not store_id:
            messages.error(request, 'Bitte wählen Sie einen Store aus.')
            return redirect('shopify_manager:collection_list')
        
        store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
        
        try:
            collection_sync = ShopifyCollectionSync(store)
            
            # Importiere alle Kategorien
            sync_log = collection_sync.import_collections(
                import_mode='all',  # Alle Collections importieren
                overwrite_existing=True  # Überschreibt existierende
            )
            
            if sync_log.status == 'success':
                messages.success(request, f'Erfolgreich {sync_log.products_success} Kategorien importiert.')
            else:
                messages.error(request, f'Fehler beim Import: {sync_log.error_message}')
                
        except Exception as e:
            messages.error(request, f'Fehler beim Import: {str(e)}')
    
    return redirect('shopify_manager:collection_list')


@login_required
def collection_alt_text_manager_view(request, collection_id):
    """Alt-Text-Manager für Kategorien"""
    collection = get_object_or_404(ShopifyCollection, id=collection_id, store__user=request.user)
    
    context = {
        'collection': collection,
    }
    return render(request, 'shopify_manager/collection_alt_text_manager.html', context)


@login_required
@require_http_methods(["POST"])
def update_collection_alt_text_view(request, collection_id):
    """Aktualisiert den Alt-Text einer Kategorie und synchronisiert mit Shopify"""
    collection = get_object_or_404(ShopifyCollection, id=collection_id, store__user=request.user)
    
    try:
        data = json.loads(request.body)
        new_alt_text = data.get('alt_text', '').strip()
        
        # Aktualisiere lokalen Alt-Text
        collection.image_alt = new_alt_text
        collection.save()
        
        # Direkte Shopify-Synchronisation
        sync_success = False
        sync_message = ""
        
        try:
            from .shopify_api import ShopifyAPIClient
            shopify_api = ShopifyAPIClient(collection.store)
            
            # Alt-Text direkt im Collection-Image über GraphQL aktualisieren
            success, message = shopify_api.update_collection_image_alt_text(
                collection.shopify_id,
                new_alt_text
            )
            
            if success:
                sync_success = True
                sync_message = "Alt-Text erfolgreich zu Shopify synchronisiert"
                # Markiere als synchronisiert (needs_sync = False)
                collection.needs_sync = False
                collection.sync_error = ""
                collection.save()
            else:
                sync_message = f"Shopify-Sync fehlgeschlagen: {message}"
                
        except Exception as sync_error:
            sync_message = f"Shopify-Sync Fehler: {str(sync_error)}"
        
        return JsonResponse({
            'success': True,
            'message': sync_message if sync_success else 'Alt-Text lokal gespeichert, aber Shopify-Sync fehlgeschlagen',
            'shopify_synced': sync_success,
            'local_saved': True
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren des Alt-Textes: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def generate_collection_alt_text_view(request, collection_id):
    """Generiert Alt-Text-Vorschläge für Kategorien mit KI"""
    collection = get_object_or_404(ShopifyCollection, id=collection_id, store__user=request.user)
    
    try:
        data = json.loads(request.body)
        image_url = data.get('image_url', '')
        collection_title = data.get('collection_title', '')
        collection_description = data.get('collection_description', '')
        
        if not image_url:
            return JsonResponse({
                'success': False,
                'error': 'Keine Bild-URL angegeben'
            })
        
        # KI-basierte Alt-Text-Generierung mit naturmacher.ai_service
        try:
            from naturmacher.services.ai_service import generate_alt_text_with_ai
            
            # Verwende AI-Service für Alt-Text-Generierung
            success, alt_text, message = generate_alt_text_with_ai(
                image_url=image_url,
                context_title=collection_title,
                context_description=collection_description,
                user=request.user,
                content_type='collection'
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'alt_text': alt_text,
                    'message': 'KI-Alt-Text erfolgreich generiert'
                })
            else:
                # Fallback bei AI-Fehler
                suggested_alt_text = f"Kategorie-Bild für {collection_title}"
                if collection_description:
                    # Nimm die ersten Worte der Beschreibung
                    desc_words = collection_description.split()[:5]
                    suggested_alt_text = f"{collection_title} - {' '.join(desc_words)}"
                
                # Kürze auf maximal 125 Zeichen
                if len(suggested_alt_text) > 125:
                    suggested_alt_text = suggested_alt_text[:122] + "..."
                
                return JsonResponse({
                    'success': True,
                    'alt_text': suggested_alt_text,
                    'message': f'Fallback-Alt-Text verwendet (KI-Fehler: {message})'
                })
        
        except ImportError:
            # Fallback wenn AI-Service nicht verfügbar
            suggested_alt_text = f"Kategorie-Bild für {collection_title}"
            if collection_description:
                # Nimm die ersten Worte der Beschreibung
                desc_words = collection_description.split()[:5]
                suggested_alt_text = f"{collection_title} - {' '.join(desc_words)}"
            
            # Kürze auf maximal 125 Zeichen
            if len(suggested_alt_text) > 125:
                suggested_alt_text = suggested_alt_text[:122] + "..."
            
            return JsonResponse({
                'success': True,
                'alt_text': suggested_alt_text,
                'message': 'Fallback-Alt-Text verwendet (AI-Service nicht verfügbar)'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der Alt-Text-Generierung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def collection_seo_ajax_view(request, collection_id):
    """AJAX-Endpunkt für Collection SEO-Optimierung"""
    collection = get_object_or_404(ShopifyCollection, id=collection_id, store__user=request.user)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        
        print(f"DEBUG: SEO AJAX Request - Action: {action}, Data: {data}")
        
        if action == 'save':
            # SEO-Daten speichern
            seo_title = data.get('seo_title', '').strip()
            seo_description = data.get('seo_description', '').strip()
            
            collection.seo_title = seo_title
            collection.seo_description = seo_description
            collection.mark_for_sync()
            collection.save()
            
            # Synchronisierung mit Shopify
            try:
                print(f"DEBUG: Starting Shopify sync for collection {collection.id}")
                print(f"DEBUG: Collection store: {collection.store}")
                print(f"DEBUG: Collection shopify_id: {collection.shopify_id}")
                print(f"DEBUG: Collection title: {collection.title}")
                
                # Prüfung ob Collection eine gültige Shopify-ID hat
                if not collection.shopify_id:
                    sync_message = 'SEO-Daten lokal gespeichert, aber Shopify-Sync fehlgeschlagen: Keine Shopify-ID vorhanden'
                    return JsonResponse({
                        'success': True,
                        'message': sync_message,
                        'seo_score': collection.get_seo_score(),
                        'shopify_synced': False
                    })
                
                from .shopify_api import ShopifyCollectionSync
                collection_sync = ShopifyCollectionSync(collection.store)
                
                # Sync Collection zu Shopify
                sync_success, sync_message_detail = collection_sync.sync_collection_to_shopify(collection)
                
                print(f"DEBUG: Sync result - success: {sync_success}, message: {sync_message_detail}")
                
                if sync_success:
                    sync_message = 'SEO-Daten erfolgreich gespeichert und zu Shopify übertragen'
                else:
                    sync_message = f'SEO-Daten lokal gespeichert, aber Shopify-Synchronisation fehlgeschlagen: {sync_message_detail}'
                
                return JsonResponse({
                    'success': True,
                    'message': sync_message,
                    'seo_score': collection.get_seo_score(),
                    'shopify_synced': sync_success,
                    'redirect_url': reverse('shopify_manager:collection_alt_text_manager', kwargs={'collection_id': collection.id})
                })
                
            except Exception as e:
                print(f"DEBUG: Shopify sync exception: {str(e)}")
                import traceback
                traceback.print_exc()
                return JsonResponse({
                    'success': True,
                    'message': f'SEO-Daten lokal gespeichert, aber Shopify-Sync fehlgeschlagen: {str(e)}',
                    'seo_score': collection.get_seo_score(),
                    'shopify_synced': False,
                    'redirect_url': reverse('shopify_manager:collection_alt_text_manager', kwargs={'collection_id': collection.id})
                })
            
        elif action == 'generate':
            # KI-basierte SEO-Optimierung
            keywords = data.get('keywords', '')
            ai_model = data.get('ai_model', 'gpt-4o')
            
            print(f"DEBUG: Generate SEO - Keywords: '{keywords}', AI Model: '{ai_model}'")
            
            if not keywords:
                return JsonResponse({
                    'success': False,
                    'error': 'Keywords sind erforderlich'
                })
            
            # KI-Integration für Collection SEO
            try:
                # Verwende die existierende AI-Service-Funktion
                success, result, message, raw_response = generate_seo_with_ai(
                    content_title=collection.title,
                    content_description=collection.description or "",
                    keywords=keywords.split(',') if keywords else [],
                    ai_model=ai_model,
                    user=request.user,
                    content_type='collection'
                )
                
                print(f"DEBUG: AI Service Response - Success: {success}, Message: {message}")
                
                if success:
                    suggested_title = result.get('seo_title', '')
                    suggested_description = result.get('seo_description', '')
                    
                    print(f"DEBUG: AI Generated SEO - Title: '{suggested_title}', Description: '{suggested_description}'")
                    
                    response_data = {
                        'success': True,
                        'seo_title': suggested_title,
                        'seo_description': suggested_description,
                        'message': 'KI-SEO-Optimierung erfolgreich generiert'
                    }
                else:
                    # Fallback bei AI-Fehler
                    suggested_title = f"{collection.title} - {keywords.split(',')[0].strip()}"
                    if len(suggested_title) > 70:
                        suggested_title = suggested_title[:67] + "..."
                    
                    suggested_description = f"Entdecken Sie {collection.title.lower()} mit {keywords}. Hochwertige Produkte für Ihre Bedürfnisse."
                    if len(suggested_description) > 160:
                        suggested_description = suggested_description[:157] + "..."
                    
                    response_data = {
                        'success': True,
                        'seo_title': suggested_title,
                        'seo_description': suggested_description,
                        'message': f'Fallback-SEO verwendet (KI-Fehler: {message})'
                    }
            except Exception as e:
                print(f"DEBUG: AI-Service Exception: {str(e)}")
                # Fallback bei Fehlern
                suggested_title = f"{collection.title} - {keywords.split(',')[0].strip()}"
                if len(suggested_title) > 70:
                    suggested_title = suggested_title[:67] + "..."
                
                suggested_description = f"Entdecken Sie {collection.title.lower()} mit {keywords}. Hochwertige Produkte für Ihre Bedürfnisse."
                if len(suggested_description) > 160:
                    suggested_description = suggested_description[:157] + "..."
                
                response_data = {
                    'success': True,
                    'seo_title': suggested_title,
                    'seo_description': suggested_description,
                    'message': f'Fallback-SEO verwendet (Exception: {str(e)})'
                }
            
            print(f"DEBUG: Response data: {response_data}")
            
            return JsonResponse(response_data)
        
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Aktion'
        })
        
    except Exception as e:
        print(f"DEBUG: Exception in collection_seo_ajax_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der SEO-Optimierung: {str(e)}'
        })