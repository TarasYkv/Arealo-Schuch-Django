from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from typing import Dict, List, Tuple, Optional
import requests
import base64

from .models import ShopifyStore, ShopifyProduct, ShopifySyncLog, ProductSEOOptimization, SEOAnalysisResult, ShopifyBlog, ShopifyBlogPost, BlogPostSEOOptimization, ShopifyCollection, CollectionSEOOptimization
from .ai_seo_service import generate_seo_with_ai, BlogPostSEOService
from .shopify_api import ShopifyAPIClient
from .forms import (
    ShopifyStoreForm, ShopifyProductEditForm, ProductFilterForm, 
    BulkActionForm, ProductImportForm, SEOOptimizationForm, BlogPostSEOOptimizationForm, BlogPostFilterForm
)
from .shopify_api import ShopifyAPIClient, ShopifyProductSync, ShopifyBlogSync
from payments.feature_access import require_subscription_access


class ShopifyStoreListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Stores des Benutzers"""
    model = ShopifyStore
    template_name = 'shopify_manager/store_list.html'
    context_object_name = 'stores'
    
    def dispatch(self, request, *args, **kwargs):
        """Check feature access before processing request"""
        from accounts.models import FeatureAccess
        if not FeatureAccess.user_can_access_app('shopify_manager', request.user):
            from django.shortcuts import render
            try:
                feature = FeatureAccess.objects.get(app_name='shopify_manager', is_active=True)
                upgrade_message = feature.get_upgrade_message()
                subscription_required = feature.get_subscription_required_display()
            except FeatureAccess.DoesNotExist:
                upgrade_message = 'Shopify Manager erfordert ein Abonnement.'
                subscription_required = 'Abonnement'
            
            return render(request, 'payments/feature_access_denied.html', {
                'app_name': 'shopify_manager',
                'required_subscription': subscription_required,
                'upgrade_message': upgrade_message,
                'upgrade_url': '/payments/plans/',
                'show_upgrade_prompt': True
            }, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return ShopifyStore.objects.filter(user=self.request.user)


class ShopifyStoreCreateView(LoginRequiredMixin, CreateView):
    """Neuen Shopify Store hinzufügen"""
    model = ShopifyStore
    form_class = ShopifyStoreForm
    template_name = 'shopify_manager/store_form.html'
    success_url = reverse_lazy('shopify_manager:store_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Teste die Verbindung vor dem Speichern
        store_data = form.cleaned_data
        test_store = ShopifyStore(
            shop_domain=store_data['shop_domain'],
            access_token=store_data['access_token']
        )
        
        api_client = ShopifyAPIClient(test_store)
        success, message = api_client.test_connection()
        
        if not success:
            form.add_error('access_token', f'Verbindung fehlgeschlagen: {message}')
            return self.form_invalid(form)
        
        messages.success(self.request, f'Store erfolgreich hinzugefügt: {message}')
        return super().form_valid(form)


class ShopifyStoreUpdateView(LoginRequiredMixin, UpdateView):
    """Shopify Store bearbeiten"""
    model = ShopifyStore
    form_class = ShopifyStoreForm
    template_name = 'shopify_manager/store_form.html'
    success_url = reverse_lazy('shopify_manager:store_list')
    
    def get_queryset(self):
        return ShopifyStore.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        # Teste die Verbindung vor dem Speichern
        store_data = form.cleaned_data
        test_store = ShopifyStore(
            shop_domain=store_data['shop_domain'],
            access_token=store_data['access_token']
        )
        
        api_client = ShopifyAPIClient(test_store)
        success, message = api_client.test_connection()
        
        if not success:
            form.add_error('access_token', f'Verbindung fehlgeschlagen: {message}')
            return self.form_invalid(form)
        
        messages.success(self.request, f'Store erfolgreich aktualisiert: {message}')
        return super().form_valid(form)


class ShopifyProductListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Produkte"""
    model = ShopifyProduct
    template_name = 'shopify_manager/product_list.html'
    context_object_name = 'products'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = ShopifyProduct.objects.filter(store__user=self.request.user)
        
        # Filter anwenden
        form = ProductFilterForm(self.request.GET)
        if form.is_valid():
            search = form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(body_html__icontains=search) |
                    Q(tags__icontains=search) |
                    Q(vendor__icontains=search)
                )
            
            status = form.cleaned_data.get('status')
            if status:
                queryset = queryset.filter(status=status)
            elif 'status' not in self.request.GET:
                # Standard: nur aktive Produkte anzeigen, wenn kein Status-Filter gesetzt ist
                queryset = queryset.filter(status='active')
            
            sync_status = form.cleaned_data.get('sync_status')
            if sync_status == 'needs_sync':
                queryset = queryset.filter(needs_sync=True)
            elif sync_status == 'sync_error':
                queryset = queryset.exclude(sync_error='')
            elif sync_status == 'synced':
                queryset = queryset.filter(needs_sync=False, sync_error='')
            
            vendor = form.cleaned_data.get('vendor')
            if vendor:
                queryset = queryset.filter(vendor__icontains=vendor)
            
            product_type = form.cleaned_data.get('product_type')
            if product_type:
                queryset = queryset.filter(product_type__icontains=product_type)
            
            seo_issues_only = form.cleaned_data.get('seo_issues_only')
            if seo_issues_only:
                queryset = queryset.filter(
                    Q(seo_title='') | Q(seo_description='')
                )
            
            # SEO-Score Filterung basierend auf get_combined_seo_status()
            seo_score = form.cleaned_data.get('seo_score')
            if seo_score:
                # Filtere Produkte basierend auf ihrem SEO-Score
                product_ids = []
                for product in queryset:
                    if product.get_combined_seo_status() == seo_score:
                        product_ids.append(product.id)
                queryset = queryset.filter(id__in=product_ids)
            
            sort = form.cleaned_data.get('sort', '-updated_at')
            if sort:
                queryset = queryset.order_by(sort)
        
        # Fetch all products and sort by SEO score (worst first)
        queryset = queryset.select_related('store')
        
        # Create a list of tuples (seo_score, product_id) for sorting
        products_with_scores = []
        for product in queryset:
            products_with_scores.append((product.get_seo_score(), product.id))
        
        # Sort by SEO score (ascending = worst first)
        products_with_scores.sort(key=lambda x: x[0])
        
        # Extract sorted product IDs
        sorted_ids = [item[1] for item in products_with_scores]
        
        # Preserve the order using Case/When
        from django.db.models import Case, When
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_ids)])
        
        # Return queryset ordered by SEO score
        return queryset.filter(id__in=sorted_ids).order_by(preserved)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProductFilterForm(self.request.GET)
        context['bulk_form'] = BulkActionForm()
        
        # Statistiken
        user_products = ShopifyProduct.objects.filter(store__user=self.request.user)
        context['stats'] = {
            'total_products': user_products.count(),
            'needs_sync': user_products.filter(needs_sync=True).count(),
            'sync_errors': user_products.exclude(sync_error='').count(),
            'seo_issues': user_products.filter(
                Q(seo_title='') | Q(seo_description='')
            ).count(),
        }
        
        # Stores für Import-Dropdown
        context['user_stores'] = ShopifyStore.objects.filter(user=self.request.user, is_active=True)
        
        # GET-Parameter für Pagination (ohne 'page' Parameter)
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']
        context['get_params'] = get_params.urlencode()
        
        return context


class ShopifyProductDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht eines Shopify Produkts"""
    model = ShopifyProduct
    template_name = 'shopify_manager/product_detail.html'
    context_object_name = 'product'
    
    def get_queryset(self):
        return ShopifyProduct.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seo_issues'] = self.object.has_seo_issues()
        return context


class ShopifyProductEditView(LoginRequiredMixin, UpdateView):
    """Bearbeitung eines Shopify Produkts"""
    model = ShopifyProduct
    form_class = ShopifyProductEditForm
    template_name = 'shopify_manager/product_edit.html'
    
    def get_queryset(self):
        return ShopifyProduct.objects.filter(store__user=self.request.user)
    
    def get_success_url(self):
        if hasattr(self, 'object') and self.object and self.object.pk:
            return reverse('shopify_manager:product_detail', kwargs={'pk': self.object.pk})
        else:
            # Fallback zur Produktliste wenn object.pk nicht verfügbar ist
            return reverse('shopify_manager:product_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.object  # Für Template-Kompatibilität
        return context
    
    def form_valid(self, form):
        print(f"=== PRODUKT EDIT FORM VALID ===")
        print(f"POST data: {dict(self.request.POST)}")
        print(f"Form is_valid: {form.is_valid()}")
        print(f"Form errors: {form.errors}")
        print(f"Alte SEO-Titel: '{self.object.seo_title}'")
        print(f"Alte SEO-Beschreibung: '{self.object.seo_description}'")
        print(f"Form cleaned_data SEO-Titel: '{form.cleaned_data.get('seo_title', 'NOT_FOUND')}'")
        print(f"Form cleaned_data SEO-Beschreibung: '{form.cleaned_data.get('seo_description', 'NOT_FOUND')}'")
        print(f"Form instance SEO-Titel: '{form.instance.seo_title}'")
        print(f"Form instance SEO-Beschreibung: '{form.instance.seo_description}'")
        
        # Manuelle Zuweisung als Test
        if 'seo_title' in form.cleaned_data:
            form.instance.seo_title = form.cleaned_data['seo_title']
        if 'seo_description' in form.cleaned_data:
            form.instance.seo_description = form.cleaned_data['seo_description']
            
        form.instance.needs_sync = True  # Markiere als Sync erforderlich
        result = super().form_valid(form)
        
        # Objekt neu laden um sicherzustellen, dass wir die aktuellen DB-Werte haben
        self.object.refresh_from_db()
        
        print(f"Nach dem Speichern (nach refresh_from_db):")
        print(f"Gespeicherte SEO-Titel: '{self.object.seo_title}'")
        print(f"Gespeicherte SEO-Beschreibung: '{self.object.seo_description}'")
        print(f"Needs Sync: {self.object.needs_sync}")
        
        # Direkte Synchronisation zu Shopify
        try:
            from .shopify_api import ShopifyProductSync
            product_sync = ShopifyProductSync(self.object.store)
            success, message = product_sync.sync_product_to_shopify(self.object)
            
            if success:
                self.object.needs_sync = False
                self.object.sync_error = ""
                self.object.last_synced_at = timezone.now()
                self.object.save(update_fields=['needs_sync', 'sync_error', 'last_synced_at'])
                messages.success(self.request, '✅ Produkt erfolgreich gespeichert und zu Shopify synchronisiert!')
                print(f"✅ Synchronisation erfolgreich: {message}")
            else:
                self.object.sync_error = str(message)[:500]  # Begrenzte Länge für DB
                self.object.save(update_fields=['sync_error'])
                messages.warning(self.request, f'Produkt gespeichert, aber Synchronisation fehlgeschlagen: {message}')
                print(f"❌ Synchronisation fehlgeschlagen: {message}")
                
        except Exception as e:
            self.object.sync_error = f"Sync-Fehler: {str(e)[:500]}"
            self.object.save(update_fields=['sync_error'])
            messages.warning(self.request, f'Produkt gespeichert, aber Synchronisation fehlgeschlagen: {str(e)}')
            print(f"❌ Synchronisation-Exception: {str(e)}")
        
        return result


@login_required
def dashboard_view(request):
    """Dashboard mit Übersicht"""
    user_stores = ShopifyStore.objects.filter(user=request.user)
    user_products = ShopifyProduct.objects.filter(store__user=request.user)
    
    # Statistiken
    stats = {
        'stores_count': user_stores.count(),
        'products_count': user_products.count(),
        'needs_sync_count': user_products.filter(needs_sync=True).count(),
        'sync_errors_count': user_products.exclude(sync_error='').count(),
        'seo_issues_count': user_products.filter(
            Q(seo_title='') | Q(seo_description='')
        ).count(),
    }
    
    # Letzte Sync-Logs
    recent_logs = ShopifySyncLog.objects.filter(
        store__user=request.user
    ).order_by('-started_at')[:5]
    
    # Produkte mit Problemen
    problem_products = user_products.filter(
        Q(needs_sync=True) | ~Q(sync_error='')
    ).order_by('-updated_at')[:10]
    
    context = {
        'stats': stats,
        'recent_logs': recent_logs,
        'problem_products': problem_products,
        'stores': user_stores,
    }
    
    return render(request, 'shopify_manager/dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def import_products_view(request):
    """Importiert Produkte von Shopify mit Fortschrittsanzeige"""
    store_id = request.POST.get('store_id')
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    form = ProductImportForm(request.POST)
    if not form.is_valid():
        # Bessere Fehlermeldung mit Details
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                errors.append(f"{field}: {error}")
        
        return JsonResponse({
            'success': False,
            'error': f'Ungültige Eingabe: {", ".join(errors)}'
        })
    
    import_mode = form.cleaned_data['import_mode']
    import_images = form.cleaned_data['import_images']
    
    # Immer 250 Produkte pro Import
    limit = 250
    
    # Neuer Modus: "reset_and_import" bedeutet alle löschen und erste 250 importieren
    if import_mode == 'reset_and_import':
        overwrite_existing = True
        import_mode = 'new_only'  # Aber als new_only behandeln für die 250 Begrenzung
    else:
        overwrite_existing = False
    
    # Generiere Import-ID für Fortschritts-Tracking
    import_id = str(uuid.uuid4())
    
    # Initialisiere Progress-Tracking
    import time as time_module
    import_progress[import_id] = {
        'status': 'running',
        'current': 0,
        'total': 0,
        'message': 'Initialisiere Produkt-Import...',
        'success_count': 0,
        'failed_count': 0,
        'last_update': time_module.time(),
        'store_id': store.id
    }
    
    try:
        # Starte Import asynchron in separatem Thread
        import threading
        
        def run_import():
            try:
                print(f"Starting async product import - Store: {store.id}, Mode: {import_mode}, Limit: {limit}")
                sync = ShopifyProductSyncWithProgress(store, import_id)
                log = sync.import_products(
                    limit=limit,
                    import_mode=import_mode,
                    overwrite_existing=overwrite_existing,
                    import_images=import_images
                )
                print(f"Import completed - Status: {log.status}, Success: {log.products_success}, Failed: {log.products_failed}")
                
                is_successful = log.status in ['success', 'partial']
                
                if log.status == 'success':
                    message = f'{log.products_success} Produkte erfolgreich importiert'
                    if overwrite_existing:
                        message += ' (alle lokalen Produkte wurden zuerst gelöscht)'
                elif log.status == 'partial':
                    message = f'{log.products_success} Produkte importiert, {log.products_failed} Fehler aufgetreten'
                    if overwrite_existing:
                        message += ' (alle lokalen Produkte wurden zuerst gelöscht)'
                else:
                    message = f'Import fehlgeschlagen: {log.error_message or "Unbekannter Fehler"}'
                
                # Update final status
                if import_id in import_progress:
                    import_progress[import_id].update({
                        'status': 'completed',
                        'success': is_successful,
                        'message': message,
                        'products_imported': log.products_success,
                        'products_failed': log.products_failed,
                    })
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"Exception in async product import: {error_details}")
                
                if import_id in import_progress:
                    import_progress[import_id].update({
                        'status': 'error',
                        'success': False,
                        'error': f'Fehler beim Produkt-Import: {str(e)}',
                        'message': f'Import fehlgeschlagen: {str(e)}'
                    })
        
        # Starte Thread
        thread = threading.Thread(target=run_import)
        thread.daemon = True  # Thread wird beendet wenn main process endet
        thread.start()
        
        # Gib sofort die import_id zurück
        return JsonResponse({
            'success': True,
            'import_id': import_id,
            'message': 'Import gestartet - Progress wird geladen...'
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Exception in product import: {error_details}")
        
        import_progress[import_id].update({
            'status': 'error',
            'success': False,
            'error': f'Fehler beim Produkt-Import: {str(e)}',
            'message': f'Import fehlgeschlagen: {str(e)}'
        })
        
        return JsonResponse({
            'success': False,
            'import_id': import_id,
            'error': f'Fehler beim Import: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def sync_product_view(request, product_id):
    """Synchronisiert ein einzelnes Produkt zu Shopify"""
    product = get_object_or_404(
        ShopifyProduct, 
        id=product_id, 
        store__user=request.user
    )
    
    try:
        sync = ShopifyProductSync(product.store)
        success, message = sync.sync_product_to_shopify(product)
        
        if success:
            # Aktualisiere lokale Daten nach erfolgreicher Synchronisation
            product.shopify_updated_at = timezone.now()
            product.needs_sync = False
            product.sync_error = ''  # Leerer String statt None für NOT NULL Feld
            product.last_synced_at = timezone.now()
            product.save(update_fields=['shopify_updated_at', 'needs_sync', 'sync_error', 'last_synced_at'])
            
            return JsonResponse({
                'success': True,
                'message': f'Produkt "{product.title}" erfolgreich synchronisiert'
            })
        else:
            # Protokolliere Sync-Fehler
            product.sync_error = f'Sync-Fehler: {message}'
            product.save(update_fields=['sync_error'])
            
            return JsonResponse({
                'success': False,
                'error': f'Fehler beim Synchronisieren: {message}'
            })
        
    except Exception as e:
        # Protokolliere Exception-Fehler
        product.sync_error = f'Exception: {str(e)}'
        product.save(update_fields=['sync_error'])
        
        return JsonResponse({
            'success': False,
            'error': f'Sync-Fehler: {str(e)}'
        })



@login_required
@require_http_methods(["POST"])
def delete_product_local_view(request, product_id):
    """Löscht ein Produkt nur lokal aus der App (nicht aus Shopify)"""
    product = get_object_or_404(
        ShopifyProduct, 
        id=product_id, 
        store__user=request.user
    )
    
    try:
        product_title = product.title
        product_shopify_id = product.shopify_id
        
        # Lösche das Produkt nur lokal
        product.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Produkt "{product_title}" wurde lokal aus der App entfernt (bleibt in Shopify bestehen)'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim lokalen Löschen: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def bulk_action_view(request):
    """Führt Bulk-Aktionen auf Produkten aus"""
    form = BulkActionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Eingabe'
        })
    
    action = form.cleaned_data['action']
    product_ids = form.cleaned_data['selected_products']
    
    # Hole Produkte des Benutzers
    products = ShopifyProduct.objects.filter(
        id__in=product_ids,
        store__user=request.user
    )
    
    if not products.exists():
        return JsonResponse({
            'success': False,
            'error': 'Keine gültigen Produkte gefunden'
        })
    
    try:
        processed_count = 0
        success_count = 0
        
        if action == 'sync_to_shopify':
            for product in products:
                sync = ShopifyProductSync(product.store)
                success, _ = sync.sync_product_to_shopify(product)
                processed_count += 1
                if success:
                    success_count += 1
        
        elif action == 'mark_needs_sync':
            products.update(needs_sync=True, sync_error='')
            processed_count = success_count = products.count()
        
        elif action == 'clear_sync_errors':
            products.update(sync_error='')
            processed_count = success_count = products.count()
        
        elif action.startswith('update_status_'):
            status = action.replace('update_status_', '')
            products.update(status=status, needs_sync=True)
            processed_count = success_count = products.count()
        
        return JsonResponse({
            'success': True,
            'message': f'{success_count} von {processed_count} Produkten erfolgreich verarbeitet',
            'processed': processed_count,
            'successful': success_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei Bulk-Aktion: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def test_store_connection_view(request, store_id):
    """Testet die Verbindung zu einem Shopify Store"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        api_client = ShopifyAPIClient(store)
        success, message = api_client.test_connection()
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Verbindungstest fehlgeschlagen: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def test_connection_api_view(request):
    """API Endpoint zum Testen der Shopify-Verbindung ohne Store zu speichern"""
    shop_domain = request.POST.get('shop_domain')
    access_token = request.POST.get('access_token')
    
    if not shop_domain or not access_token:
        return JsonResponse({
            'success': False,
            'error': 'Shop-Domain und Access Token sind erforderlich'
        })
    
    try:
        # Erstelle temporären Store für Test
        from .models import ShopifyStore
        temp_store = ShopifyStore(
            shop_domain=shop_domain,
            access_token=access_token
        )
        
        api_client = ShopifyAPIClient(temp_store)
        success, message = api_client.test_connection()
        
        return JsonResponse({
            'success': success,
            'message': message if success else None,
            'error': message if not success else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Verbindungstest fehlgeschlagen: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def delete_store_view(request, store_id):
    """Löscht einen Shopify Store"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        store_name = store.name
        store.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Store "{store_name}" wurde erfolgreich gelöscht'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen des Stores: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def debug_product_data_view(request, product_id):
    """Debug: Zeigt rohe Shopify-Produktdaten an"""
    product = get_object_or_404(
        ShopifyProduct, 
        id=product_id, 
        store__user=request.user
    )
    
    try:
        # Hole aktuelle Daten von Shopify
        api_client = ShopifyAPIClient(product.store)
        success, fresh_data, message = api_client.get_product(product.shopify_id)
        
        # Hole auch Metafields für umfassende Analyse
        meta_success, metafields, meta_message = api_client.get_product_metafields(product.shopify_id)
        
        if success:
            # Erweiterte SEO-Analyse
            seo_analysis = {
                'stored_seo_title': product.seo_title,
                'stored_seo_description': product.seo_description,
                'shopify_keys': list(fresh_data.keys()) if fresh_data else [],
                'has_seo_object': 'seo' in fresh_data if fresh_data else False,
                'has_meta_fields': any(key.startswith('meta_') for key in fresh_data.keys()) if fresh_data else False,
                'metafields_count': len(metafields) if meta_success and metafields else 0,
                'metafields_success': meta_success,
                'metafields_message': meta_message,
            }
            
            # Analysiere alle Metafields für SEO-relevante Daten
            webrex_fields = []
            seo_fields = []
            all_namespaces = set()
            
            if meta_success and metafields:
                for mf in metafields:
                    if isinstance(mf, dict):
                        namespace = mf.get('namespace', '')
                        key = mf.get('key', '')
                        value = str(mf.get('value', ''))
                        
                        all_namespaces.add(namespace)
                        
                        # Sammle Webrex-spezifische Felder
                        if 'webrex' in namespace.lower():
                            webrex_fields.append({
                                'namespace': namespace,
                                'key': key,
                                'value': value[:100] + '...' if len(value) > 100 else value
                            })
                        
                        # Sammle alle SEO-relevanten Felder
                        if any(seo_word in (namespace + key).lower() for seo_word in ['seo', 'meta', 'title', 'description']):
                            seo_fields.append({
                                'namespace': namespace,
                                'key': key,
                                'value': value[:100] + '...' if len(value) > 100 else value
                            })
            
            seo_analysis.update({
                'webrex_fields': webrex_fields,
                'seo_fields': seo_fields,
                'all_namespaces': list(all_namespaces),
                'webrex_found': len(webrex_fields) > 0,
                'seo_fields_found': len(seo_fields) > 0,
            })
            
            return JsonResponse({
                'success': True,
                'stored_data': product.raw_shopify_data,
                'fresh_data': fresh_data,
                'metafields': metafields if meta_success else [],
                'seo_analysis': seo_analysis
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message,
                'stored_data': product.raw_shopify_data
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Debug-Fehler: {str(e)}',
            'stored_data': product.raw_shopify_data
        })


@login_required
@require_http_methods(["POST"])
def update_seo_data_view(request, product_id):
    """Aktualisiert SEO-Daten für ein Produkt über Metafields"""
    print(f"=== SEO UPDATE STARTED für Produkt {product_id} ===")
    
    try:
        product = get_object_or_404(
            ShopifyProduct, 
            id=product_id, 
            store__user=request.user
        )
        print(f"Produkt gefunden: {product.title}")
        
        sync = ShopifyProductSync(product.store)
        print(f"ShopifyProductSync erstellt für Store: {product.store.name}")
        
        sync._fetch_and_update_seo_data(product)
        print(f"SEO-Daten Update abgeschlossen")
        
        # Lade das Produkt neu um aktualisierte Daten zu bekommen
        product.refresh_from_db()
        
        print(f"=== SEO UPDATE ERFOLGREICH ===")
        return JsonResponse({
            'success': True,
            'message': 'SEO-Daten erfolgreich aktualisiert',
            'seo_title': product.seo_title,
            'seo_description': product.seo_description,
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"=== SEO UPDATE FEHLER ===")
        print(f"Fehler: {str(e)}")
        print(f"Details: {error_details}")
        
        return JsonResponse({
            'success': False,
            'error': f'SEO-Update fehlgeschlagen: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def webrex_search_view(request, product_id):
    """Spezialisierte Suche nach Webrex SEO-Daten"""
    product = get_object_or_404(
        ShopifyProduct, 
        id=product_id, 
        store__user=request.user
    )
    
    try:
        api_client = ShopifyAPIClient(product.store)
        success, search_result, message = api_client.search_webrex_seo_data(product.shopify_id)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': message,
                'search_result': search_result,
                'product_info': {
                    'title': product.title,
                    'shopify_id': product.shopify_id,
                    'current_seo_title': product.seo_title,
                    'current_seo_description': product.seo_description,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Webrex-Suche fehlgeschlagen: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def bulk_seo_analysis_view(request):
    """Analysiert SEO-Status aller Produkte eines Stores"""
    store_id = request.POST.get('store_id')
    if not store_id:
        return JsonResponse({
            'success': False,
            'error': 'Store ID erforderlich'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        # Prüfe ob eine Neu-Analyse erzwungen wird
        force_refresh = request.POST.get('force_refresh', 'false').lower() == 'true'
        
        # Prüfe ob eine aktuelle Analyse existiert (außer bei force_refresh)
        # Fallback falls Tabelle noch nicht existiert
        cached_analysis = None
        try:
            cached_analysis = SEOAnalysisResult.get_latest_for_store(store) if not force_refresh else None
        except Exception as db_error:
            print(f"Cache-Tabelle noch nicht verfügbar: {db_error}")
            cached_analysis = None
        
        if cached_analysis and not force_refresh:
            print(f"SEO-Analyse aus Cache geladen: {cached_analysis.created_at}")
            return JsonResponse({
                'success': True,
                'from_cache': True,
                'cache_date': cached_analysis.created_at.isoformat(),
                'analysis_results': {
                    'total_products': cached_analysis.total_products,
                    'products_with_good_seo': cached_analysis.products_with_good_seo,
                    'products_with_poor_seo': cached_analysis.products_with_poor_seo,
                    'products_with_alt_texts': cached_analysis.products_with_alt_texts,
                    'products_without_alt_texts': cached_analysis.products_without_alt_texts,
                    'products_with_global_seo': cached_analysis.products_with_global_seo,
                    'products_with_woo_data': cached_analysis.products_with_woo_data,
                    'products_with_webrex_data': cached_analysis.products_with_webrex_data,
                    'products_with_no_metafields': cached_analysis.products_with_no_metafields,
                    'detailed_results': cached_analysis.detailed_results
                }
            })
        
        # Keine aktuelle Analyse vorhanden - erstelle neue
        products = ShopifyProduct.objects.filter(store=store)
        blog_posts = ShopifyBlogPost.objects.filter(blog__store=store)
        api_client = ShopifyAPIClient(store)
        
        if not products.exists() and not blog_posts.exists():
            return JsonResponse({
                'success': False,
                'error': 'Keine Produkte oder Blog-Posts im Store gefunden. Bitte importieren Sie zuerst Inhalte.'
            })
        
        print(f"SEO Bulk-Analyse: {products.count()} Produkte und {blog_posts.count()} Blog-Posts werden neu analysiert")
        
        analysis_results = {
            'total_products': products.count(),
            'total_blog_posts': blog_posts.count(),
            'products_with_global_seo': 0,
            'products_with_woo_data': 0,
            'products_with_no_metafields': 0,
            'products_with_webrex_data': 0,
            'products_with_good_seo': 0,
            'products_with_poor_seo': 0,
            'products_with_alt_texts': 0,
            'products_without_alt_texts': 0,
            'blog_posts_with_good_seo': 0,
            'blog_posts_with_poor_seo': 0,
            'blog_posts_with_alt_texts': 0,
            'blog_posts_without_alt_texts': 0,
            'detailed_results': []
        }
        
        for product in products:
            try:
                product_id = product.shopify_id
                product_title = product.title
                
                # Verwende lokale SEO-Daten
                current_seo_title = product.seo_title or ""
                current_seo_description = product.seo_description or ""
                
                # Berechne SEO-Qualität (Ampelsystem)
                seo_score = 0
                seo_status = "poor"  # poor/good
                
                # SEO-Titel Bewertung
                if current_seo_title:
                    title_length = len(current_seo_title)
                    if 30 <= title_length <= 70:  # Optimale Länge
                        seo_score += 50
                    elif 20 <= title_length <= 80:  # Akzeptable Länge
                        seo_score += 30
                    else:  # Zu kurz oder zu lang
                        seo_score += 10
                
                # SEO-Beschreibung Bewertung
                if current_seo_description:
                    desc_length = len(current_seo_description)
                    if 120 <= desc_length <= 160:  # Optimale Länge
                        seo_score += 50
                    elif 100 <= desc_length <= 180:  # Akzeptable Länge
                        seo_score += 30
                    else:  # Zu kurz oder zu lang
                        seo_score += 10
                
                # SEO-Status bestimmen
                if seo_score >= 70:  # Beide Felder optimal
                    seo_status = "good"
                    analysis_results['products_with_good_seo'] += 1
                else:
                    analysis_results['products_with_poor_seo'] += 1
                
                # Alt-Text Analyse (aus raw_shopify_data)
                has_alt_texts = False
                total_images = 0
                images_with_alt = 0
                
                if hasattr(product, 'raw_shopify_data') and product.raw_shopify_data:
                    images = product.raw_shopify_data.get('images', [])
                    total_images = len(images)
                    
                    for image in images:
                        alt_text = image.get('alt', '').strip() if image.get('alt') else ''
                        if alt_text:
                            images_with_alt += 1
                    
                    # Als "gut" bewerten wenn mindestens 80% der Bilder Alt-Texte haben
                    if total_images > 0 and (images_with_alt / total_images) >= 0.8:
                        has_alt_texts = True
                        analysis_results['products_with_alt_texts'] += 1
                    else:
                        analysis_results['products_without_alt_texts'] += 1
                else:
                    analysis_results['products_without_alt_texts'] += 1
                
                # Hole erweiterte Metafields für detaillierte Analyse
                meta_success, metafields, meta_message = api_client.get_product_metafields(product_id)
                
                product_analysis = {
                    'title': product_title,
                    'shopify_id': product_id,
                    'current_seo_title': current_seo_title,
                    'current_seo_description': current_seo_description,
                    'seo_score': seo_score,
                    'seo_status': seo_status,
                    'has_alt_texts': has_alt_texts,
                    'total_images': total_images,
                    'images_with_alt': images_with_alt,
                    'metafields_count': len(metafields) if meta_success else 0,
                    'namespaces': [],
                    'has_global_seo': False,
                    'has_woo_data': False,
                    'has_webrex_data': False,
                    'seo_fields_found': []
                }
                
                if meta_success and metafields:
                    namespaces = set()
                    for mf in metafields:
                        if isinstance(mf, dict):
                            namespace = mf.get('namespace', '')
                            key = mf.get('key', '')
                            
                            namespaces.add(namespace)
                            
                            # Check for SEO-relevante Felder
                            if namespace == 'global' and key in ['title_tag', 'description_tag']:
                                product_analysis['has_global_seo'] = True
                                product_analysis['seo_fields_found'].append(f"{namespace}.{key}")
                            
                            if namespace == 'woo':
                                product_analysis['has_woo_data'] = True
                            
                            if 'webrex' in namespace.lower():
                                product_analysis['has_webrex_data'] = True
                    
                    product_analysis['namespaces'] = list(namespaces)
                
                # Update counters
                if product_analysis['has_global_seo']:
                    analysis_results['products_with_global_seo'] += 1
                if product_analysis['has_woo_data']:
                    analysis_results['products_with_woo_data'] += 1
                if product_analysis['has_webrex_data']:
                    analysis_results['products_with_webrex_data'] += 1
                if product_analysis['metafields_count'] == 0:
                    analysis_results['products_with_no_metafields'] += 1
                
                analysis_results['detailed_results'].append(product_analysis)
                
            except Exception as e:
                print(f"Fehler bei Produkt {product_id}: {e}")
                continue
        
        # Blog-Posts analysieren
        for blog_post in blog_posts:
            try:
                post_id = blog_post.shopify_id
                post_title = blog_post.title
                
                # Verwende lokale SEO-Daten
                current_seo_title = blog_post.seo_title or ""
                current_seo_description = blog_post.seo_description or ""
                
                # Berechne SEO-Qualität für Blog-Posts (gleiche Logik wie Produkte)
                seo_score = 0
                seo_status = "poor"
                
                # SEO-Titel Bewertung
                if current_seo_title:
                    title_length = len(current_seo_title)
                    if 30 <= title_length <= 70:
                        seo_score += 50
                    elif 20 <= title_length <= 80:
                        seo_score += 30
                    else:
                        seo_score += 10
                
                # SEO-Beschreibung Bewertung
                if current_seo_description:
                    desc_length = len(current_seo_description)
                    if 120 <= desc_length <= 160:
                        seo_score += 50
                    elif 100 <= desc_length <= 180:
                        seo_score += 30
                    else:
                        seo_score += 10
                
                # SEO-Status bestimmen
                if seo_score >= 70:
                    seo_status = "good"
                    analysis_results['blog_posts_with_good_seo'] += 1
                else:
                    analysis_results['blog_posts_with_poor_seo'] += 1
                
                # Alt-Text Analyse für Blog-Posts
                has_alt_texts = bool(blog_post.featured_image_url and blog_post.featured_image_alt)
                
                if has_alt_texts:
                    analysis_results['blog_posts_with_alt_texts'] += 1
                else:
                    analysis_results['blog_posts_without_alt_texts'] += 1
                
                # Detaillierte Ergebnisse für Blog-Posts
                blog_post_analysis = {
                    'type': 'blog_post',
                    'id': post_id,
                    'title': post_title,
                    'blog_title': blog_post.blog.title,
                    'current_seo_title': current_seo_title,
                    'current_seo_description': current_seo_description,
                    'seo_status': seo_status,
                    'seo_score': seo_score,
                    'has_featured_image': bool(blog_post.featured_image_url),
                    'has_alt_text': has_alt_texts,
                    'status': blog_post.status,
                    'published_at': blog_post.published_at.isoformat() if blog_post.published_at else None
                }
                
                analysis_results['detailed_results'].append(blog_post_analysis)
                
            except Exception as e:
                print(f"Fehler bei Blog-Post {post_id}: {e}")
                continue
        
        # Versuche die neue Analyse zu speichern (falls Tabelle existiert)
        try:
            # Invalidiere alte Analysen
            SEOAnalysisResult.invalidate_store_cache(store)
            
            # Speichere die neue Analyse
            SEOAnalysisResult.objects.create(
                store=store,
                total_products=analysis_results['total_products'],
                products_with_good_seo=analysis_results['products_with_good_seo'],
                products_with_poor_seo=analysis_results['products_with_poor_seo'],
                products_with_alt_texts=analysis_results['products_with_alt_texts'],
                products_without_alt_texts=analysis_results['products_without_alt_texts'],
                products_with_global_seo=analysis_results['products_with_global_seo'],
                products_with_woo_data=analysis_results['products_with_woo_data'],
                products_with_webrex_data=analysis_results['products_with_webrex_data'],
                products_with_no_metafields=analysis_results['products_with_no_metafields'],
                detailed_results=analysis_results['detailed_results']
            )
            
            print(f"SEO-Analyse gespeichert für Store {store.name}")
        except Exception as save_error:
            print(f"Konnte Analyse nicht speichern (Migration erforderlich): {save_error}")
            # Weiter ohne Cache - Analyse wird trotzdem durchgeführt
        
        return JsonResponse({
            'success': True,
            'from_cache': False,
            'analysis_results': analysis_results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Bulk-Analyse fehlgeschlagen: {str(e)}'
        })


@login_required
def seo_optimization_view(request, product_id):
    """SEO-Optimierung Seite mit KI-Unterstützung"""
    # product_id kann sowohl lokale ID als auch Shopify-ID sein
    # Versuche zuerst Shopify-ID, dann lokale ID
    product = None
    
    try:
        # Versuche zuerst mit Shopify-ID (häufigster Fall aus SEO Dashboard Links)
        product = ShopifyProduct.objects.get(
            shopify_id=str(product_id), 
            store__user=request.user
        )
        print(f"Produkt gefunden über Shopify-ID: {product_id}")
    except ShopifyProduct.DoesNotExist:
        # Fallback: Versuche mit lokaler ID (aus product_list Links)
        try:
            product = ShopifyProduct.objects.get(
                id=product_id, 
                store__user=request.user
            )
            print(f"Produkt gefunden über lokale ID: {product_id}")
        except ShopifyProduct.DoesNotExist:
            print(f"Produkt nicht gefunden - weder Shopify-ID noch lokale ID: {product_id}")
            # Debugging: Zeige verfügbare Produkte
            available_products = ShopifyProduct.objects.filter(store__user=request.user)
            print(f"Verfügbare Produkte für User: {[p.shopify_id for p in available_products[:5]]}")
            
            # Wenn beide fehlschlagen, 404 werfen
            from django.http import Http404
            raise Http404(f"Produkt mit ID {product_id} nicht gefunden")
    
    if request.method == 'POST':
        form = SEOOptimizationForm(request.POST, product=product)
        if form.is_valid():
            seo_optimization = form.save()
            return redirect('shopify_manager:seo_optimization_detail', pk=seo_optimization.pk)
    else:
        form = SEOOptimizationForm(product=product)
    
    # Hole letzte SEO-Optimierungen für dieses Produkt
    recent_optimizations = product.seo_optimizations.all()[:5]
    
    context = {
        'product': product,
        'form': form,
        'recent_optimizations': recent_optimizations,
    }
    
    return render(request, 'shopify_manager/seo_optimization.html', context)


@login_required
def seo_optimization_detail_view(request, pk):
    """Detailansicht einer SEO-Optimierung mit KI-Generierung"""
    seo_optimization = get_object_or_404(
        ProductSEOOptimization,
        pk=pk,
        product__store__user=request.user
    )
    
    context = {
        'seo_optimization': seo_optimization,
        'product': seo_optimization.product,
    }
    
    return render(request, 'shopify_manager/seo_optimization_detail.html', context)


@login_required
@require_http_methods(["POST"])
def generate_seo_ai_view(request, pk):
    """Generiert SEO-Inhalte mit KI"""
    seo_optimization = get_object_or_404(
        ProductSEOOptimization,
        pk=pk,
        product__store__user=request.user
    )
    
    try:
        from .ai_seo_service import generate_seo_with_ai
        
        keywords = seo_optimization.get_keywords_list()
        
        success, result, message, raw_response = generate_seo_with_ai(
            content_title=seo_optimization.original_title,
            content_description=seo_optimization.original_description,
            keywords=keywords,
            ai_model=seo_optimization.ai_model,
            user=request.user
        )
        
        if success:
            # Speichere generierte SEO-Daten
            seo_optimization.generated_seo_title = result.get('seo_title', '')
            seo_optimization.generated_seo_description = result.get('seo_description', '')
            seo_optimization.ai_response_raw = raw_response
            seo_optimization.save()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'seo_title': seo_optimization.generated_seo_title,
                'seo_description': seo_optimization.generated_seo_description,
                'seo_title_length': len(seo_optimization.generated_seo_title),
                'seo_description_length': len(seo_optimization.generated_seo_description)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei KI-Generierung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def apply_seo_optimization_view(request, pk):
    """Wendet die generierten SEO-Daten auf das Produkt an"""
    seo_optimization = get_object_or_404(
        ProductSEOOptimization,
        pk=pk,
        product__store__user=request.user
    )
    
    try:
        if not seo_optimization.generated_seo_title and not seo_optimization.generated_seo_description:
            return JsonResponse({
                'success': False,
                'error': 'Keine generierten SEO-Daten vorhanden. Zuerst "Mit KI generieren" klicken.'
            })
        
        seo_optimization.apply_to_product()
        
        return JsonResponse({
            'success': True,
            'message': 'SEO-Daten erfolgreich auf Produkt angewendet!',
            'redirect_url': reverse('shopify_manager:product_detail', kwargs={'pk': seo_optimization.product.pk})
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Anwenden der SEO-Daten: {str(e)}'
        })


@login_required
def seo_dashboard_view(request):
    """SEO Dashboard mit visueller Analyse und umfassenden SEO-Tipps"""
    # Hole alle Stores des Benutzers
    user_stores = ShopifyStore.objects.filter(user=request.user, is_active=True)
    
    context = {
        'user_stores': user_stores,
    }
    
    return render(request, 'shopify_manager/seo_dashboard.html', context)


@login_required
def alt_text_manager_overview_view(request):
    """Alt-Text Manager Übersicht für alle Bildtypen"""
    # Hole alle Stores des Benutzers
    user_stores = ShopifyStore.objects.filter(user=request.user, is_active=True)
    
    context = {
        'user_stores': user_stores,
    }
    
    return render(request, 'shopify_manager/alt_text_manager.html', context)


@login_required
@require_http_methods(["GET"])
def get_alt_text_data_view(request, store_id):
    """Holt Alt-Text Daten für einen Store"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    search_query = request.GET.get('search', '').strip().lower()
    
    try:
        api_client = ShopifyAPIClient(store)
        
        # Hole Produktdaten mit Bildern
        success, products, message = api_client.fetch_products(limit=250)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': f'Fehler beim Laden der Produkte: {message}'
            })
        
        print(f"Alt-Text Manager: {len(products)} Produkte von Store {store.name} geladen")
        
        # Verarbeite Produktbilder
        product_data = []
        total_images = 0
        complete_alt_texts = 0
        missing_alt_texts = 0
        
        for product in products:
            try:
                images = product.get('images', [])
                if not images:
                    continue
                    
                product_images = []
                for image in images:
                    try:
                        total_images += 1
                        # Sichere Behandlung von Alt-Text (kann None sein)
                        raw_alt = image.get('alt') or ''
                        alt_text = raw_alt.strip() if raw_alt else ''
                        
                        if alt_text:
                            complete_alt_texts += 1
                        else:
                            missing_alt_texts += 1
                        
                        product_images.append({
                            'id': str(image.get('id', '')),
                            'src': image.get('src', ''),
                            'alt_text': alt_text,
                            'position': image.get('position', 1)
                        })
                    except Exception as img_error:
                        print(f"Fehler beim Verarbeiten von Bild in Produkt {product.get('id', 'unknown')}: {img_error}")
                        continue
                
                if product_images:
                    product_title = product.get('title', '')
                    
                    # Suchfilter anwenden
                    if search_query:
                        # Suche in Produkttitel (case-insensitive)
                        if search_query not in product_title.lower():
                            continue
                    
                    product_data.append({
                        'id': str(product.get('id', '')),
                        'title': product_title,
                        'images': product_images
                    })
            except Exception as product_error:
                print(f"Fehler beim Verarbeiten von Produkt {product.get('id', 'unknown')}: {product_error}")
                continue
        
        # Statistiken berechnen
        partial_alt_texts = 0  # Produkte mit einigen aber nicht allen Alt-Texten
        for product in product_data:
            has_alt = sum(1 for img in product['images'] if img['alt_text'])
            total_imgs = len(product['images'])
            if 0 < has_alt < total_imgs:
                partial_alt_texts += total_imgs - has_alt
        
        statistics = {
            'complete': complete_alt_texts,
            'partial': partial_alt_texts,
            'missing': missing_alt_texts,
            'total': total_images
        }
        
        # Hole Blog-Daten
        blog_data = []
        try:
            # Hole lokale Blog-Posts (bereits importiert)
            blog_posts = ShopifyBlogPost.objects.filter(blog__store=store)
            
            for post in blog_posts:
                if post.featured_image_url:
                    blog_data.append({
                        'id': str(post.shopify_id),
                        'title': post.title,
                        'blog_title': post.blog.title,
                        'image_url': post.featured_image_url,
                        'alt_text': post.featured_image_alt or '',
                        'status': post.status,
                        'published_at': post.published_at.isoformat() if post.published_at else None
                    })
        except Exception as e:
            print(f"Fehler beim Laden der Blog-Daten: {e}")

        return JsonResponse({
            'success': True,
            'data': {
                'products': product_data,
                'collections': [],  # TODO: Implementiere Collections
                'blog': blog_data,
                'pages': []  # TODO: Implementiere Pages
            },
            'statistics': statistics
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Laden der Alt-Text Daten: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def update_alt_text_view(request):
    """Aktualisiert den Alt-Text eines Bildes"""
    store_id = request.POST.get('store_id')
    product_id = request.POST.get('product_id')
    image_id = request.POST.get('image_id')
    alt_text = request.POST.get('alt_text', '').strip()
    
    # Validierung der Alt-Text-Eingabe
    if alt_text.lower() in ['none', 'null', '']:
        alt_text = ''  # Leeren Alt-Text setzen statt "None"
    
    if not all([store_id, product_id, image_id]):
        return JsonResponse({
            'success': False,
            'error': 'Fehlende Parameter'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        print(f"DEBUG: Alt-Text Update Request - Store: {store.name}, Product: {product_id}, Image: {image_id}")
        print(f"DEBUG: Original Alt-Text: '{alt_text}'")
        print(f"DEBUG: Alt-Text Length: {len(alt_text)}")
        print(f"DEBUG: Alt-Text Type: {type(alt_text)}")
        
        # Shopify API Call zum Aktualisieren des Alt-Textes
        api_client = ShopifyAPIClient(store)
        
        # Aktualisiere DIREKT das einzelne Bild in Shopify (ohne lokale DB zu überschreiben)
        print(f"DEBUG: Calling update_single_product_image - Product: {product_id}, Image: {image_id}")
        success, message = api_client.update_single_product_image(product_id, image_id, alt_text)
        print(f"DEBUG: Update Single Image Result - Success: {success}, Message: {message}")
        
        if success:
            print(f"DEBUG: Shopify Update erfolgreich - KEINE lokale DB-Aktualisierung um Überschreibung zu vermeiden")
            
            return JsonResponse({
                'success': True,
                'message': 'Alt-Text erfolgreich aktualisiert',
                'redirect_url': reverse('shopify_manager:product_list')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Fehler beim Aktualisieren in Shopify: {message}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren des Alt-Textes: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
# REMOVED: Old fallback-only generate_alt_text_view function
# Now using the AI-integrated version at line ~2131


def index_view(request):
    """Startseite der Shopify Manager App"""
    if request.user.is_authenticated:
        return redirect('shopify_manager:dashboard')
    
    return render(request, 'shopify_manager/index.html')


# Blog Views
class ShopifyBlogListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Blogs"""
    model = ShopifyBlog
    template_name = 'shopify_manager/blog_list.html'
    context_object_name = 'blogs'
    paginate_by = 50
    
    def get_queryset(self):
        return ShopifyBlog.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_stores'] = ShopifyStore.objects.filter(user=self.request.user, is_active=True)
        
        # Statistiken
        user_blogs = ShopifyBlog.objects.filter(store__user=self.request.user)
        all_posts = ShopifyBlogPost.objects.filter(blog__store__user=self.request.user)
        published_posts = all_posts.filter(status='published')
        draft_posts = all_posts.filter(status='draft')
        
        context['stats'] = {
            'total_blogs': user_blogs.count(),
            'total_posts': all_posts.count(),
            'published_posts': published_posts.count(),
            'draft_posts': draft_posts.count(),
        }
        
        return context


class ShopifyBlogDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht eines Shopify Blogs"""
    model = ShopifyBlog
    template_name = 'shopify_manager/blog_detail.html'
    context_object_name = 'blog'
    
    def get_queryset(self):
        return ShopifyBlog.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Blog-Posts für diesen Blog mit Filterung
        posts = self.object.posts.all()
        
        # Filter anwenden
        filter_form = BlogPostFilterForm(self.request.GET)
        if filter_form.is_valid():
            search = filter_form.cleaned_data.get('search')
            if search:
                posts = posts.filter(
                    Q(title__icontains=search) |
                    Q(content__icontains=search) |
                    Q(tags__icontains=search) |
                    Q(author__icontains=search)
                )
            
            status = filter_form.cleaned_data.get('status')
            if status:
                posts = posts.filter(status=status)
            elif 'status' not in self.request.GET:
                # Standard: nur veröffentlichte Blog-Posts anzeigen
                posts = posts.filter(status='published')
            
            sync_status = filter_form.cleaned_data.get('sync_status')
            if sync_status == 'needs_sync':
                posts = posts.filter(needs_sync=True)
            elif sync_status == 'sync_error':
                posts = posts.exclude(sync_error='')
            elif sync_status == 'synced':
                posts = posts.filter(needs_sync=False, sync_error='')
            
            author = filter_form.cleaned_data.get('author')
            if author:
                posts = posts.filter(author__icontains=author)
            
            seo_issues_only = filter_form.cleaned_data.get('seo_issues_only')
            if seo_issues_only:
                posts = posts.filter(
                    Q(seo_title='') | Q(seo_description='')
                )
            
            # SEO-Score Filterung basierend auf get_combined_seo_status()
            seo_score = filter_form.cleaned_data.get('seo_score')
            if seo_score:
                # Filtere Blog-Posts basierend auf ihrem SEO-Score
                post_ids = []
                for post in posts:
                    if post.get_combined_seo_status() == seo_score:
                        post_ids.append(post.id)
                posts = posts.filter(id__in=post_ids)
            
            sort = filter_form.cleaned_data.get('sort', '-updated_at')
            if sort:
                posts = posts.order_by(sort)
        
        # Sort blog posts by SEO score (worst first)
        posts_list = list(posts)
        posts_list.sort(key=lambda p: p.get_seo_score())  # Lower scores (worse) first
        
        context['filter_form'] = filter_form
        
        paginator = Paginator(posts_list, 100)  # Zeige 100 Posts pro Seite für bessere Übersicht
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        
        # Statistiken für diesen Blog
        total_count = self.object.posts.count()
        published_count = self.object.posts.filter(status='published').count()
        draft_count = self.object.posts.filter(status='draft').count()
        
        # Debug-Ausgabe
        print(f"Blog {self.object.title} - Total Posts in DB: {total_count}")
        print(f"  Published: {published_count}, Draft: {draft_count}")
        print(f"  Posts nach Filterung: {len(posts_list)}")
        print(f"  Pagination: {paginator.count} Posts gesamt, {paginator.num_pages} Seiten")
        
        context['stats'] = {
            'total_posts': total_count,
            'published_posts': published_count,
            'draft_posts': draft_count,
        }
        
        return context


class ShopifyBlogPostListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Blog-Posts"""
    model = ShopifyBlogPost
    template_name = 'shopify_manager/blog_post_list.html'
    context_object_name = 'posts'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = ShopifyBlogPost.objects.filter(blog__store__user=self.request.user)
        
        # Filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(content__icontains=search) |
                Q(tags__icontains=search) |
                Q(author__icontains=search)
            )
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        elif 'status' not in self.request.GET:
            # Standard: nur veröffentlichte Blog-Posts anzeigen, wenn kein Status-Filter gesetzt ist
            queryset = queryset.filter(status='published')
        
        blog_id = self.request.GET.get('blog')
        if blog_id:
            queryset = queryset.filter(blog_id=blog_id)
        
        # Sortierung
        sort = self.request.GET.get('sort', '-published_at')
        if sort:
            queryset = queryset.order_by(sort)
        
        # Fetch all blog posts and sort by SEO score (worst first)
        queryset = queryset.select_related('blog')
        
        # Create a list of tuples (seo_score, blog_post_id) for sorting
        posts_with_scores = []
        for post in queryset:
            posts_with_scores.append((post.get_seo_score(), post.id))
        
        # Sort by SEO score (ascending = worst first)
        posts_with_scores.sort(key=lambda x: x[0])
        
        # Extract sorted blog post IDs
        sorted_ids = [item[1] for item in posts_with_scores]
        
        # Preserve the order using Case/When
        from django.db.models import Case, When
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_ids)])
        
        # Return queryset ordered by SEO score
        return queryset.filter(id__in=sorted_ids).order_by(preserved)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_blogs'] = ShopifyBlog.objects.filter(store__user=self.request.user)
        
        # Statistiken
        user_posts = ShopifyBlogPost.objects.filter(blog__store__user=self.request.user)
        context['stats'] = {
            'total_posts': user_posts.count(),
            'published_posts': user_posts.filter(status='published').count(),
            'draft_posts': user_posts.filter(status='draft').count(),
            'seo_issues': user_posts.filter(
                Q(seo_title='') | Q(seo_description='')
            ).count(),
        }
        
        # Filter-Parameter für URL
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']
        context['get_params'] = get_params.urlencode()
        
        return context


class ShopifyBlogPostDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht eines Shopify Blog-Posts"""
    model = ShopifyBlogPost
    template_name = 'shopify_manager/blog_post_detail.html'
    context_object_name = 'post'
    
    def get_queryset(self):
        return ShopifyBlogPost.objects.filter(blog__store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seo_status'] = self.object.get_seo_status()
        context['alt_text_status'] = self.object.get_alt_text_status()
        return context


@login_required
@require_http_methods(["POST"])
def import_blogs_view(request):
    """Importiert Blogs von Shopify"""
    store_id = request.POST.get('store_id')
    
    if not store_id:
        return JsonResponse({
            'success': False,
            'error': 'Store-ID fehlt'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        blog_sync = ShopifyBlogSync(store)
        log = blog_sync.import_blogs()
        
        return JsonResponse({
            'success': log.status in ['success', 'partial'],
            'message': f'{log.products_success} Blogs importiert',
            'imported': log.products_success,
            'failed': log.products_failed,
            'status': log.status
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Blog-Import: {str(e)}'
        })


import threading
import queue
import uuid

# Globaler Dict für Import-Progress tracking
import_progress = {}

@login_required
@require_http_methods(["POST"])
def import_blog_posts_view(request):
    """Startet den Import von Blog-Posts für einen bestimmten Blog"""
    blog_id = request.POST.get('blog_id')
    store_id = request.POST.get('store_id')  # Store-ID aus dem Modal
    import_mode = request.POST.get('import_mode', 'new_only')  # new_only, reset_and_import
    
    if not blog_id or not store_id:
        return JsonResponse({
            'success': False,
            'error': 'Blog-ID oder Store-ID fehlt'
        })
    
    blog = get_object_or_404(ShopifyBlog, id=blog_id, store_id=store_id, store__user=request.user)
    
    # Erstelle eine eindeutige Import-ID
    import_id = str(uuid.uuid4())

    # Initialisiere Progress-Tracking
    import time as time_module
    import_progress[import_id] = {
        'status': 'running',
        'current': 0,
        'total': 0,
        'message': 'Import wird gestartet...',
        'success': True,
        'error': None,
        'log': None,
        'last_update': time_module.time()
    }
    
    # Starte Import in separatem Thread
    import_thread = threading.Thread(
        target=_run_blog_import,
        args=(blog, import_mode, import_id)
    )
    import_thread.start()
    
    return JsonResponse({
        'success': True,
        'import_id': import_id,
        'message': 'Import gestartet'
    })

def _run_blog_import(blog, import_mode, import_id):
    """Führt den Blog-Import in einem separaten Thread aus"""
    try:
        # Erstelle Custom Blog Sync mit Progress-Callback
        blog_sync = ShopifyBlogSyncWithProgress(blog.store, import_id)
        log = blog_sync.import_blog_posts(blog, import_mode=import_mode)
        
        # Detailliertere Erfolgsprüfung
        is_successful = log.status in ['success', 'partial']
        
        if is_successful:
            message = f'{log.products_success} Blog-Posts erfolgreich importiert'
            if log.products_failed > 0:
                message += f', {log.products_failed} fehlgeschlagen'
            if import_mode == 'all':
                message += ' (alle lokalen Blog-Posts wurden überschrieben)'
        else:
            message = f'Import fehlgeschlagen: {log.error_message or "Unbekannter Fehler"}'
        
        # Update final status
        import_progress[import_id].update({
            'status': 'completed',
            'success': is_successful,
            'message': message,
            'error': message if not is_successful else None,
            'imported': log.products_success,
            'failed': log.products_failed,
            'log_status': log.status,
            'import_mode': import_mode
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Exception in blog import: {error_details}")
        
        import_progress[import_id].update({
            'status': 'error',
            'success': False,
            'error': f'Fehler beim Blog-Post-Import: {str(e)}',
            'message': f'Fehler beim Blog-Post-Import: {str(e)}'
        })

@login_required
def import_blog_posts_progress_view(request, import_id):
    """Gibt den aktuellen Import-Fortschritt zurück"""
    import time as time_module

    if import_id not in import_progress:
        return JsonResponse({
            'success': False,
            'error': 'Import-ID nicht gefunden'
        })

    progress = import_progress[import_id]

    # Timeout-Erkennung: Wenn Status "running" aber kein Update seit 10 Sekunden
    if progress['status'] == 'running':
        last_update = progress.get('last_update', 0)
        if last_update and (time_module.time() - last_update) > 10:  # 10 Sekunden
            progress['status'] = 'stalled'
            progress['message'] = f'Import scheint abgebrochen (bei {progress.get("current", 0)} Elementen). Bitte starten Sie einen neuen Import.'

    return JsonResponse({
        'success': True,
        'progress': progress
    })


@login_required
def import_products_progress_view(request, import_id):
    """Gibt den aktuellen Produkt-Import-Fortschritt zurück"""
    import time as time_module

    if import_id not in import_progress:
        return JsonResponse({
            'success': False,
            'error': 'Import-ID nicht gefunden'
        })

    progress = import_progress[import_id]

    # Timeout-Erkennung: Wenn Status "running" aber kein Update seit 10 Sekunden
    if progress['status'] == 'running':
        last_update = progress.get('last_update', 0)
        if last_update and (time_module.time() - last_update) > 10:  # 10 Sekunden
            # Import ist wahrscheinlich abgestürzt
            progress['status'] = 'stalled'
            progress['message'] = f'Import scheint abgebrochen (bei {progress.get("current", 0)} Elementen). Bitte starten Sie einen neuen Import mit "Nur neue".'

    return JsonResponse({
        'success': True,
        'progress': progress
    })

# Erweiterte ShopifyBlogSync Klasse mit Progress-Callbacks
class ShopifyBlogSyncWithProgress(ShopifyBlogSync):
    def __init__(self, store: ShopifyStore, import_id: str):
        super().__init__(store)
        self.import_id = import_id
    
    def _update_progress(self, current, total, message):
        """Aktualisiert den Import-Fortschritt"""
        import time as time_module
        if self.import_id in import_progress:
            import_progress[self.import_id].update({
                'current': current,
                'total': total,
                'message': message,
                'last_update': time_module.time()
            })
    
    def _fetch_all_blog_posts(self, blog_id: str, max_posts: int = None, start_from_id: str = None, load_older: bool = False):
        """Holt Blog-Posts über Pagination mit Progress-Updates"""
        all_articles = []
        since_id = None
        max_id = None
        
        if load_older:
            max_id = start_from_id  # Lade Posts älter als diese ID
        else:
            since_id = start_from_id  # Lade Posts neuer als diese ID
        
        total_fetched = 0
        page = 1
        consecutive_small_pages = 0  # Zähler für aufeinanderfolgende kleine Seiten

        max_pages = 1000  # Maximale Anzahl Seiten zur Sicherheit (1000 × 250 = 250.000 Posts)
        
        while page <= max_pages:
            self._update_progress(
                len(all_articles), 
                len(all_articles) + 1,  # Wir wissen noch nicht wie viele es insgesamt sind
                f'Hole Blog-Posts von Shopify (Seite {page})...'
            )
            
            # Hier wird die API-Client-Methode aufgerufen
            success, articles, message, _ = self.api.fetch_blog_posts(blog_id, limit=250, since_id=since_id, max_id=max_id)

            if not success:
                return False, [], message

            if not articles:  # Keine weiteren Artikel
                print(f"📄 Letzte Seite erreicht: Keine Artikel zurückgegeben")
                break

            all_articles.extend(articles)
            total_fetched += len(articles)
            print(f"Pagination: {len(articles)} Blog-Posts geholt, insgesamt: {total_fetched}")

            # Update progress message
            self._update_progress(
                len(all_articles), 
                len(all_articles) + 1,
                f'{total_fetched} Blog-Posts von Shopify geladen...'
            )

            # ID für nächste Seite setzen
            if load_older:
                max_id = str(articles[-1]['id'])  # ID des ältesten Artikels dieser Seite
                print(f"📄 Nächste Seite: max_id = {max_id}")
            else:
                since_id = str(articles[-1]['id'])  # ID des letzten Artikels
                print(f"📄 Nächste Seite: since_id = {since_id}")
            page += 1

            # Verbessertes Pagination-Handling
            # Nur stoppen wenn wir deutlich weniger als das Maximum bekommen
            # Da Shopify manchmal 249 statt 250 Posts zurückgibt, verwenden wir eine Toleranz
            if len(articles) < 200:  # Deutlich weniger als Maximum - wahrscheinlich Ende
                consecutive_small_pages += 1
                print(f"📄 Kleine Seite: {len(articles)} Posts (#{consecutive_small_pages})")
                
                # Stoppe nur wenn wir mehrere kleine Seiten hintereinander bekommen
                if consecutive_small_pages >= 2:
                    print(f"📄 Letzte Seite erreicht: {consecutive_small_pages} aufeinanderfolgende kleine Seiten")
                    break
            else:
                consecutive_small_pages = 0  # Reset bei normaler Seitengröße
                
            # Zusätzliche Überprüfung: Stoppe wenn weniger als 100 Posts und wir schon viele haben
            if len(articles) < 100 and total_fetched > 1000:
                print(f"📄 Letzte Seite erreicht: Nur {len(articles)} Posts bei {total_fetched} total")
                break

            # Stoppe wenn maximale Anzahl Posts erreicht
            if max_posts and total_fetched >= max_posts:
                print(f"📄 Maximale Anzahl Posts erreicht: {total_fetched}/{max_posts}")
                break

            # Sicherheitscheck: Stoppe bei sehr vielen Artikeln
            if total_fetched >= 250000:  # Erhöht für sehr große Blogs
                print(f"Sicherheitsstopp bei {total_fetched} Blog-Posts erreicht")
                break
        
        # Warnung wenn Seitenlimit erreicht wurde
        if page > max_pages:
            print(f"Warnung: Maximale Seitenanzahl ({max_pages}) erreicht. Möglicherweise wurden nicht alle Blog-Posts geladen.")

        print(f"✅ PAGINATION ABGESCHLOSSEN: {total_fetched} Blog-Posts über {page-1} Seiten abgerufen")
        return True, all_articles, f"{total_fetched} Blog-Posts über Pagination abgerufen"
    
    def _fetch_blog_posts_after_id(self, blog_id: str, max_posts: int, start_from_id: str = None):
        """Holt Blog-Posts nach einer bestimmten ID (oder neueste wenn None)"""
        self._update_progress(0, max_posts, f'Hole Blog-Posts von Shopify...')
        
        if start_from_id is None:
            # Hole die neuesten Posts (ohne since_id)
            success, articles, message, _ = self.api.fetch_blog_posts(blog_id, limit=max_posts)
        else:
            # Lade Posts mit since_id (Posts die NACH der angegebenen ID kommen)
            # Das sind Posts, die neuer sind als der neueste Post in der DB
            success, articles, message, _ = self.api.fetch_blog_posts(blog_id, limit=max_posts, since_id=start_from_id)
            print(f"📄 API-Aufruf mit since_id={start_from_id}: {len(articles)} Posts geholt")
        
        if not success:
            return False, [], message
        
        print(f"📄 {len(articles)} Blog-Posts geholt")
        return True, articles, f"{len(articles)} Blog-Posts abgerufen"
    
    def _fetch_blog_posts_with_skip(self, blog_id: str, skip_count: int, take_count: int):
        """Holt Blog-Posts mit Skip-und-Take-Pattern"""
        self._update_progress(0, take_count, f'Überspringe {skip_count} Posts und hole {take_count} weitere...')
        
        all_articles = []
        since_id = None
        total_fetched = 0
        
        # Überspringe die ersten skip_count Posts
        while total_fetched < skip_count:
            batch_size = min(250, skip_count - total_fetched)
            success, batch_articles, message, _ = self.api.fetch_blog_posts(blog_id, limit=batch_size, since_id=since_id)
            
            if not success or not batch_articles:
                print(f"📄 Fehler oder keine Posts mehr beim Überspringen: {message}")
                break
            
            total_fetched += len(batch_articles)
            since_id = str(batch_articles[-1]['id'])
            
            print(f"📄 Überspringe Posts: {total_fetched}/{skip_count}")
            
            self._update_progress(total_fetched, skip_count + take_count, f'Überspringe Posts ({total_fetched}/{skip_count})...')
        
        # Jetzt hole die nächsten take_count Posts und filtere bereits vorhandene heraus
        collected = 0
        attempts = 0
        max_attempts = 10  # Verhindere Endlosschleife
        
        while collected < take_count and attempts < max_attempts:
            batch_size = min(250, (take_count - collected) * 2)  # Hole mehr für Filterung
            success, batch_articles, message, _ = self.api.fetch_blog_posts(blog_id, limit=batch_size, since_id=since_id)
            
            if not success or not batch_articles:
                print(f"📄 Keine weiteren Posts verfügbar: {message}")
                break
            
            # Filtere Posts heraus, die bereits in der DB sind
            from .models import ShopifyBlogPost
            existing_ids = set(ShopifyBlogPost.objects.filter(
                blog__shopify_id=blog_id, 
                shopify_id__in=[str(a['id']) for a in batch_articles]
            ).values_list('shopify_id', flat=True))
            
            new_articles = [a for a in batch_articles if str(a['id']) not in existing_ids]
            
            print(f"📄 Batch: {len(batch_articles)} Posts, {len(new_articles)} neue Posts")
            
            if new_articles:
                # Nehme nur die benötigten Posts
                needed = take_count - collected
                articles_to_add = new_articles[:needed]
                all_articles.extend(articles_to_add)
                collected += len(articles_to_add)
                
                print(f"📄 Sammle Posts: {collected}/{take_count}")
            
            if len(batch_articles) > 0:
                since_id = str(batch_articles[-1]['id'])
            
            attempts += 1
            
            self._update_progress(skip_count + collected, skip_count + take_count, f'Sammle Posts ({collected}/{take_count})...')
            
            # Stoppe wenn weniger als erwartete Posts zurückgegeben wurden
            if len(batch_articles) < batch_size:
                break
        
        print(f"📄 {len(all_articles)} Blog-Posts gesammelt (nach Überspringen von {skip_count} Posts)")
        return True, all_articles, f"{len(all_articles)} Blog-Posts abgerufen"
    
    def _fetch_blog_posts_continuation(self, blog_id: str, max_posts: int, start_from_id: str = None):
        """Holt weitere Blog-Posts durch vollständige Pagination und Filterung"""
        self._update_progress(0, max_posts, f'Lade weitere Blog-Posts...')
        
        # Hole ALLE Posts von Shopify und filtere die bereits importierten heraus
        print(f"📄 Hole alle Posts von Shopify und filtere bereits importierte heraus...")
        
        # Verwende die bestehende _fetch_all_blog_posts Methode
        success, all_shopify_posts, message = self._fetch_all_blog_posts(blog_id, max_posts=None)
        
        if not success:
            return False, [], message
        
        print(f"📄 {len(all_shopify_posts)} Posts von Shopify geholt")
        
        # Hole alle bereits importierten Post-IDs
        from .models import ShopifyBlogPost
        existing_ids = set(ShopifyBlogPost.objects.filter(
            blog__shopify_id=blog_id
        ).values_list('shopify_id', flat=True))
        
        print(f"📄 {len(existing_ids)} Posts bereits in DB")
        
        # Filtere bereits importierte Posts heraus
        new_articles = [a for a in all_shopify_posts if str(a['id']) not in existing_ids]
        
        print(f"📄 {len(new_articles)} neue Posts gefunden")
        
        # Nimm nur die ersten max_posts
        articles_to_return = new_articles[:max_posts]
        
        print(f"📄 Gebe {len(articles_to_return)} Posts zurück")
        return True, articles_to_return, f"{len(articles_to_return)} Blog-Posts abgerufen"
    
    def _clear_pagination_state(self, blog):
        """Löscht den Pagination-Zustand für einen Blog"""
        # Für "all" Modus werden alle Posts gelöscht, das ist der Reset
        print(f"📄 Pagination-Status für Blog {blog.title} zurückgesetzt")
    
    def _get_pagination_state(self, blog):
        """Holt den aktuellen Pagination-Zustand für einen Blog"""
        # Das Problem: since_id gibt nur NEUERE Posts zurück
        # Lösung: Verwende gar kein since_id und filtere stattdessen
        from .models import ShopifyBlogPost
        
        post_count = ShopifyBlogPost.objects.filter(blog=blog).count()
        
        if post_count > 0:
            print(f"📄 Pagination-Status: {post_count} Posts bereits importiert")
            return post_count  # Verwende die Anzahl als Offset
        else:
            print(f"📄 Pagination-Status: Beginne von vorne")
            return 0
    
    def _save_pagination_state(self, blog, since_id):
        """Speichert den aktuellen Pagination-Zustand"""
        # Wird automatisch durch das Speichern der Posts gemacht
        print(f"📄 Pagination-Status gespeichert: {since_id}")
    
    def _fetch_next_batch(self, blog_id: str, batch_size: int = 250):
        """Holt die nächste Batch von Posts mit vollständiger Suche"""
        self._update_progress(0, batch_size, f'Hole nächste {batch_size} Blog-Posts...')
        
        # VOLLSTÄNDIGE LÖSUNG: Hole alle Posts und filtere bereits vorhandene heraus
        # Das ist notwendig, da die Shopify API Posts in chronologischer Reihenfolge zurückgibt
        # und wir die noch nicht importierten Posts finden müssen
        
        print(f"📄 Durchsuche alle verfügbaren Posts nach neuen Einträgen...")
        
        # Hole alle Posts über Pagination
        success, all_articles, message = self._fetch_all_blog_posts(blog_id, max_posts=None)
        
        if not success:
            return False, [], message
        
        print(f"📄 {len(all_articles)} Posts von Shopify erhalten")
        
        # Filtere bereits vorhandene Posts heraus
        from .models import ShopifyBlog, ShopifyBlogPost
        blog = ShopifyBlog.objects.get(shopify_id=blog_id)
        
        existing_ids = set(ShopifyBlogPost.objects.filter(
            blog=blog
        ).values_list('shopify_id', flat=True))
        
        new_articles = [a for a in all_articles if str(a['id']) not in existing_ids]
        
        print(f"📄 {len(new_articles)} neue Posts gefunden (von {len(all_articles)} geprüft)")
        
        # Nimm nur die ersten batch_size Posts für timeout-sichere Verarbeitung
        articles_to_return = new_articles[:batch_size]
        
        print(f"📄 Gebe {len(articles_to_return)} Posts für Import zurück")
        
        return True, articles_to_return, f"{len(articles_to_return)} Blog-Posts abgerufen"
    
    def import_blog_posts(self, blog: ShopifyBlog, import_mode: str = 'new_only') -> ShopifySyncLog:
        """Importiert Blog-Posts mit Progress-Updates"""
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import_blog_posts',
            status='success'
        )
        
        try:
            self._update_progress(0, 0, 'Lösche alte Blog-Posts...' if import_mode == 'all' else 'Starte Import...')
            
            # Bei "Alle Posts" - alle lokalen Blog-Posts für diesen Blog löschen
            if import_mode == 'all':
                deleted_count = self._delete_all_local_blog_posts(blog)
                print(f"🗑️ {deleted_count} lokale Blog-Posts gelöscht vor Neuimport für Blog {blog.title}")
                self._update_progress(0, 0, f'{deleted_count} alte Blog-Posts gelöscht')
            
            self._update_progress(0, 0, 'Hole Blog-Posts von Shopify...')
            
            # Bestimme Parameter basierend auf Import-Modus
            if import_mode == 'all':
                # Lösche Pagination-Status und beginne von vorne
                self._clear_pagination_state(blog)
                
                # DIREKTE API-ABFRAGE für die neuesten Posts
                print(f"📄 RESET-MODUS: Hole neueste 250 Posts direkt von Shopify")
                api_success, articles, api_message, _ = self.api.fetch_blog_posts(
                    blog.shopify_id, 
                    limit=250
                )
                
                if api_success:
                    success = True
                    message = f"{len(articles)} Posts von Shopify geholt"
                    print(f"📄 API gab {len(articles)} Posts zurück")
                    
                    # Debug: Zeige die ersten 3 Posts
                    for i, article in enumerate(articles[:3]):
                        print(f"📄 Post {i+1}: ID={article.get('id')}, Title={article.get('title', 'No title')[:50]}")
                else:
                    success = False
                    articles = []
                    message = f"API-Fehler: {api_message}"
                    print(f"❌ API-Fehler: {api_message}")
            else:  # new_only / weitere 250 laden
                # MODERNE LÖSUNG: Verwende cursor-basierte Pagination
                from .models import ShopifyBlogPost
                
                print(f"📄 🚀 NEUE LÖSUNG: Moderne cursor-basierte Pagination")
                self._update_progress(0, 0, "Hole ALLE Posts mit moderner Pagination...")
                
                # Hole bereits importierte IDs
                existing_ids = set(ShopifyBlogPost.objects.filter(blog=blog).values_list('shopify_id', flat=True))
                print(f"📊 {len(existing_ids)} Posts bereits in lokaler DB")
                
                # VOLLSTÄNDIGER IMPORT MIT MODERNER PAGINATION
                all_posts = []
                page_info = None
                page_count = 0
                max_pages = 50  # Sicherheit gegen Endlosschleife
                
                while page_count < max_pages:
                    page_count += 1
                    print(f"📄 Hole Seite {page_count} (cursor: {page_info[:20] if page_info else 'None'}...)")
                    self._update_progress(0, 0, f"Lade Seite {page_count}...")
                    
                    # NEUE API-SIGNATUR mit 4 Rückgabewerten
                    api_success, batch_posts, api_message, next_page_info = self.api.fetch_blog_posts(
                        blog.shopify_id, 
                        limit=250,
                        page_info=page_info
                    )
                    
                    if not api_success:
                        print(f"❌ API-Fehler auf Seite {page_count}: {api_message}")
                        break
                        
                    if not batch_posts:
                        print(f"📄 Keine Posts auf Seite {page_count} - Ende erreicht")
                        break
                    
                    print(f"✅ Seite {page_count}: {len(batch_posts)} Posts geladen")
                    all_posts.extend(batch_posts)
                    
                    # Prüfe ob weitere Seiten verfügbar
                    if not next_page_info:
                        print(f"📄 Letzte Seite erreicht (keine next_page_info)")
                        break
                        
                    if len(batch_posts) < 250:
                        print(f"📄 Letzte Seite erreicht (weniger als 250 Posts)")
                        break
                    
                    page_info = next_page_info
                
                print(f"🎉 PAGINATION ABGESCHLOSSEN: {len(all_posts)} Posts über {page_count} Seiten geladen")
                self._update_progress(0, 0, f"Shopify: {len(all_posts)} Posts geladen, filtere...")
                
                # Filtere neue Posts
                new_posts = []
                for post in all_posts:
                    if str(post['id']) not in existing_ids:
                        new_posts.append(post)
                
                articles = new_posts[:250]  # Limitiere auf 250 für diesen Import
                success = True
                message = f"{len(articles)} neue Posts von {len(all_posts)} geprüften gefunden"
                print(f"📊 ERGEBNIS: {len(articles)} neue Posts für Import aus {len(all_posts)} geladenen")
            print(f"=== IMPORT RESULT: {len(articles)} Blog-Posts von Shopify geholt ===")
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = timezone.now()
                log.save()
                return log
            
            log.products_processed = len(articles)
            success_count = 0
            failed_count = 0
            total = len(articles)
            
            self._update_progress(0, total, f'Importiere {total} Blog-Posts...')
            
            for i, article_data in enumerate(articles):
                try:
                    shopify_id = str(article_data.get('id'))
                    
                    # Bei "new_only" (weitere Posts laden) werden alle Posts importiert
                    # Die Filterung erfolgt bereits durch die since_id Logik
                    if import_mode == 'new_only':
                        # Prüfe ob Post bereits existiert (zur Sicherheit)
                        try:
                            from .models import ShopifyBlogPost
                            existing_post = ShopifyBlogPost.objects.get(
                                shopify_id=shopify_id,
                                blog=blog
                            )
                            # Post existiert bereits - überspringen
                            print(f"Blog-Post {shopify_id} bereits vorhanden - überspringe")
                            self._update_progress(i + 1, total, f'Überspringe existierenden Post ({i + 1}/{total})')
                            continue
                        except ShopifyBlogPost.DoesNotExist:
                            # Post existiert noch nicht - kann importiert werden
                            pass
                    
                    article_title = article_data.get('title', 'Unbekannt')
                    self._update_progress(i + 1, total, f'Importiere: {article_title[:50]}... ({i + 1}/{total})')
                    
                    post, created = self._create_or_update_blog_post(blog, article_data)
                    success_count += 1
                    if created:
                        print(f"Blog-Post {post.shopify_id} erstellt: {post.title}")
                    else:
                        print(f"Blog-Post {post.shopify_id} aktualisiert: {post.title}")
                        
                except Exception as e:
                    failed_count += 1
                    import traceback
                    error_details = traceback.format_exc()
                    article_title = article_data.get('title', 'Unknown')
                    article_id = article_data.get('id', 'Unknown')
                    
                    print(f"❌ Fehler beim Importieren von Blog-Post '{article_title}' (ID: {article_id}): {e}")
                    print(f"Vollständiger Fehler: {error_details}")
                    
                    # Sammle detaillierte Fehlerinformationen
                    error_info = {
                        'article_id': article_id,
                        'article_title': article_title,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'error_details': error_details
                    }
                    
                    # Speichere den Fehler im Log für spätere Analyse
                    if not hasattr(log, '_errors'):
                        log._errors = []
                    log._errors.append(error_info)
            
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial'
            log.completed_at = timezone.now()
            log.save()
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = timezone.now()
            log.save()
        
        return log


class ShopifyProductSyncWithProgress(ShopifyProductSync):
    """ShopifyProductSync mit Fortschrittsanzeige"""
    
    def __init__(self, store: ShopifyStore, import_id: str):
        super().__init__(store)
        self.import_id = import_id
    
    def _update_progress(self, current, total, message, success_count=0, failed_count=0):
        """Aktualisiert den Import-Fortschritt"""
        import time as time_module
        if self.import_id in import_progress:
            import_progress[self.import_id].update({
                'current': current,
                'total': total,
                'message': message,
                'success_count': success_count,
                'failed_count': failed_count,
                'last_update': time_module.time()
            })
    
    def _fetch_products_with_progress(self, limit: int = 250) -> Tuple[bool, List[Dict], str]:
        """Holt Produkte von Shopify mit Progress-Updates"""
        self._update_progress(0, 0, 'Verbinde mit Shopify API...')
        
        all_products = []
        page_info = None
        total_fetched = 0
        page_count = 0
        
        while total_fetched < limit:
            page_count += 1
            self._update_progress(0, 0, f'Lade Seite {page_count} von Shopify...')
            
            # Hole nächste Seite
            success, products, message = self.api.fetch_products(
                limit=min(250, limit - total_fetched),
                page_info=page_info if page_count > 1 else None
            )
            
            if not success:
                return False, all_products, message
                
            if not products:
                break
                
            all_products.extend(products)
            total_fetched += len(products)
            
            self._update_progress(0, 0, f'{total_fetched} Produkte von Shopify geladen...')
            
            # Checke ob es weitere Seiten gibt
            if len(products) < 250 or total_fetched >= limit:
                break
                
        return True, all_products[:limit], f"{len(all_products)} Produkte geladen"
    
    def _fetch_next_unimported_products_with_progress(self, limit: int = 250) -> Tuple[bool, List[Dict], str]:
        """Holt nicht-importierte Produkte mit Progress-Updates"""
        self._update_progress(0, 0, 'Prüfe bereits importierte Produkte...')
        
        # Erstelle Set mit bereits importierten IDs
        existing_ids = set(
            ShopifyProduct.objects.filter(store=self.store)
            .values_list('shopify_id', flat=True)
        )
        
        self._update_progress(0, 0, f'{len(existing_ids)} Produkte bereits importiert, suche neue...')
        
        collected_products = []
        page_limit = 250
        max_attempts = 10
        attempts = 0
        since_id = None
        
        while len(collected_products) < limit and attempts < max_attempts:
            attempts += 1
            self._update_progress(0, 0, f'Durchsuche Shopify-Katalog (Versuch {attempts}/{max_attempts})...')
            
            # Hole nächsten Batch
            success, products, message = self.api.fetch_products(
                limit=page_limit,
                since_id=since_id
            )
            
            if not success:
                return False, [], message
                
            if not products:
                break
                
            # Filtere neue Produkte
            new_count = 0
            for product in products:
                shopify_id = str(product.get('id'))
                if shopify_id not in existing_ids:
                    collected_products.append(product)
                    new_count += 1
                    if len(collected_products) >= limit:
                        break
                        
            self._update_progress(0, 0, f'{len(collected_products)} neue Produkte gefunden...')
            
            # Update since_id
            if products:
                since_id = products[-1].get('id')
                
        return True, collected_products[:limit], f"{len(collected_products)} neue Produkte gefunden"
    
    def import_products(self, limit: int = 250, import_mode: str = 'all', 
                       overwrite_existing: bool = True, import_images: bool = True) -> 'ShopifySyncLog':
        """Importiert Produkte mit Fortschrittsanzeige"""
        from .models import ShopifySyncLog
        
        log = ShopifySyncLog.objects.create(
            store=self.store,
            action='import',
            status='success'
        )
        
        try:
            self._update_progress(0, 0, 'Initialisiere Produkt-Import...')
            
            # Bei "reset_and_import" - alle lokalen Produkte löschen
            if overwrite_existing:
                self._update_progress(0, 0, 'Lösche bestehende Produkte...')
                
                # Zähle Produkte vor dem Löschen für Progress
                total_to_delete = ShopifyProduct.objects.filter(store=self.store).count()
                if total_to_delete > 0:
                    self._update_progress(0, total_to_delete, f'Lösche {total_to_delete} lokale Produkte...')
                    
                    # Lösche in Batches für bessere Progress-Anzeige
                    deleted_count = 0
                    batch_size = 50
                    
                    while True:
                        batch = list(ShopifyProduct.objects.filter(store=self.store)[:batch_size])
                        if not batch:
                            break
                            
                        batch_deleted = len(batch)
                        for product in batch:
                            product.delete()
                        
                        deleted_count += batch_deleted
                        self._update_progress(
                            deleted_count, total_to_delete, 
                            f'Lösche bestehende Produkte... ({deleted_count}/{total_to_delete})'
                        )
                        
                        # Kleine Pause für UI-Update
                        import time
                        time.sleep(0.01)
                    
                    self._update_progress(total_to_delete, total_to_delete, f'{deleted_count} lokale Produkte gelöscht')
                else:
                    self._update_progress(0, 0, 'Keine lokalen Produkte zum Löschen gefunden')
            
            # Hole Produkte je nach Modus
            self._update_progress(0, 0, 'Hole Produkte von Shopify...')
            if import_mode == 'new_only':
                success, products, message = self._fetch_next_unimported_products_with_progress(limit=limit)
            else:
                success, products, message = self._fetch_products_with_progress(limit=limit)
            
            if not success:
                log.status = 'error'
                log.error_message = message
                log.completed_at = timezone.now()
                log.save()
                self._update_progress(0, 0, f'Fehler: {message}')
                return log
            
            log.products_processed = len(products)
            success_count = 0
            failed_count = 0
            total = len(products)
            
            self._update_progress(0, total, f'Verarbeite {total} Produkte...')
            
            # Verarbeite Produkte mit Progress-Updates
            from django.db import transaction
            
            for i, product_data in enumerate(products):
                try:
                    shopify_id = str(product_data.get('id'))
                    product_title = product_data.get('title', 'Unbekannt')[:30]
                    
                    # Progress-Update für aktuelles Produkt
                    self._update_progress(
                        i + 1, total, 
                        f'Importiere: {product_title}... ({i + 1}/{total})',
                        success_count, failed_count
                    )
                    
                    # Prüfe ob Produkt bereits existiert (für new_only Modus)
                    if import_mode == 'new_only':
                        try:
                            ShopifyProduct.objects.get(shopify_id=shopify_id, store=self.store)
                            # Produkt existiert bereits - überspringen
                            continue
                        except ShopifyProduct.DoesNotExist:
                            # Produkt existiert noch nicht - kann importiert werden
                            pass
                    
                    # Importiere/aktualisiere das Produkt
                    with transaction.atomic():
                        product, created = self._create_or_update_product(
                            product_data, 
                            overwrite_existing=overwrite_existing,
                            import_images=import_images
                        )
                        success_count += 1
                    
                    # Alle 5 Produkte kleine Pause für UI-Update
                    if (i + 1) % 5 == 0:
                        import time
                        time.sleep(0.01)
                        
                except Exception as e:
                    failed_count += 1
                    import traceback
                    error_details = traceback.format_exc()
                    print(f"❌ Fehler beim Import von Produkt {shopify_id}: {str(e)}")
                    print(f"Details: {error_details}")
                    
                    self._update_progress(
                        i + 1, total, 
                        f'Fehler bei Produkt {i + 1}: {str(e)[:30]}...',
                        success_count, failed_count
                    )
            
            # Import abgeschlossen
            log.products_success = success_count
            log.products_failed = failed_count
            log.status = 'success' if failed_count == 0 else 'partial'
            log.completed_at = timezone.now()
            log.save()
            
            final_message = f'{success_count} Produkte importiert'
            if failed_count > 0:
                final_message += f', {failed_count} Fehler'
            
            self._update_progress(total, total, final_message, success_count, failed_count)
            
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.completed_at = timezone.now()
            log.save()
            self._update_progress(0, 0, f'Import-Fehler: {str(e)}')
        
        return log



@login_required
@require_http_methods(["POST"])
def update_blog_alt_text_view(request):
    """Aktualisiert den Alt-Text eines Blog-Post Bildes"""
    store_id = request.POST.get('store_id')
    blog_post_id = request.POST.get('blog_post_id')
    image_id = request.POST.get('image_id')
    image_url = request.POST.get('image_url')
    alt_text = request.POST.get('alt_text', '').strip()
    
    if not all([store_id, blog_post_id]):
        return JsonResponse({
            'success': False,
            'error': 'Fehlende Parameter'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    blog_post = get_object_or_404(ShopifyBlogPost, shopify_id=blog_post_id, blog__store=store)
    
    # Nur Featured Images werden unterstützt (da nur diese zu Shopify synchronisiert werden können)
    is_featured_image = image_id and image_id.startswith('featured_')
    
    try:
        if is_featured_image:
            # Featured Image Alt-Text Update
            blog_post.featured_image_alt = alt_text
            blog_post.save(update_fields=['featured_image_alt'])
            
            # Shopify API Update für Featured Image
            shopify_api = ShopifyAPIClient(store)
            
            # Erstelle die Update-Daten für Shopify (korrekte Struktur)
            # WICHTIG: Shopify API erfordert immer einen title - verwende den aktuellen Titel
            update_data = {
                'title': blog_post.title,  # Aktueller Titel MUSS enthalten sein
                'body_html': blog_post.content or '',  # Aktueller Inhalt
            }
            
            # WICHTIG: published_at beibehalten, sonst wird der Post auf draft gesetzt
            if blog_post.published_at:
                update_data['published_at'] = blog_post.published_at.isoformat()
            
            # Wenn eine Featured Image URL vorhanden ist, füge sie hinzu
            if blog_post.featured_image_url:
                update_data['featured_image'] = {
                    'url': blog_post.featured_image_url,
                    'alt': alt_text
                }
            else:
                # Nur Alt-Text ohne URL (für bestehende Bilder)
                update_data['featured_image'] = {
                    'alt': alt_text
                }
            
            # Update zu Shopify senden
            try:
                print(f"DEBUG: Updating Featured Image - Blog ID: {blog_post.blog.shopify_id}, Post ID: {blog_post.shopify_id}")
                print(f"DEBUG: Update data: {update_data}")
                
                success, response_data, message = shopify_api.update_blog_post(blog_post.blog.shopify_id, blog_post.shopify_id, update_data)
                print(f"DEBUG: Shopify response: success={success}, data={response_data}, message={message}")
                
                if success:
                    # Erfolgreiche Synchronisation
                    blog_post.needs_sync = False
                    blog_post.sync_error = ''  # Leerer String statt None für NOT NULL Feld
                    blog_post.last_synced_at = timezone.now()
                    blog_post.save(update_fields=['needs_sync', 'sync_error', 'last_synced_at'])
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Featured Image Alt-Text erfolgreich zu Shopify übertragen',
                        'redirect_url': reverse('shopify_manager:product_list')
                    })
                else:
                    # Shopify-Update fehlgeschlagen
                    blog_post.needs_sync = True
                    blog_post.sync_error = f'Shopify-Update fehlgeschlagen: {message}'
                    blog_post.save(update_fields=['needs_sync', 'sync_error'])
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Alt-Text lokal gespeichert, Shopify-Update fehlgeschlagen'
                    })
                    
            except Exception as shopify_error:
                # Shopify API Fehler
                print(f"DEBUG: Shopify API Exception: {shopify_error}")
                blog_post.needs_sync = True
                blog_post.sync_error = f'Shopify API Fehler: {str(shopify_error)}'
                blog_post.save(update_fields=['needs_sync', 'sync_error'])
                
                return JsonResponse({
                    'success': True,
                    'message': f'Alt-Text lokal gespeichert, Shopify-Fehler: {str(shopify_error)}'
                })
        
        else:
            # Nur Featured Images werden unterstützt
            return JsonResponse({
                'success': False,
                'error': 'Nur Featured Images werden unterstützt - Content-Bilder können nicht zu Shopify synchronisiert werden'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren des Blog Alt-Textes: {str(e)}'
        })


@login_required
def alt_text_manager_view(request, product_id):
    """Alt-Text Management für Produktbilder"""
    product = get_object_or_404(ShopifyProduct, id=product_id, store__user=request.user)
    
    # Lade Produktbilder aus raw_shopify_data
    images = []
    if product.raw_shopify_data and 'images' in product.raw_shopify_data:
        for img in product.raw_shopify_data['images']:
            # Bereinige Alt-Text von None-Werten
            alt_text = img.get('alt', '') or ''
            if alt_text in ['None', 'null', None]:
                alt_text = ''
            
            images.append({
                'id': img.get('id'),
                'src': img.get('src'),
                'alt': alt_text,
                'width': img.get('width'),
                'height': img.get('height'),
                'position': img.get('position', 0)
            })
    
    # Sortiere Bilder nach Position
    images.sort(key=lambda x: x['position'])
    
    context = {
        'product': product,
        'images': images
    }
    
    return render(request, 'shopify_manager/product_alt_text_manager.html', context)


@login_required
def blog_post_alt_text_manager_view(request, blog_post_id):
    """Alt-Text Management für Blog-Post-Bilder - Nur Featured Images (da nur diese zu Shopify synchronisiert werden können)"""
    blog_post = get_object_or_404(ShopifyBlogPost, id=blog_post_id, blog__store__user=request.user)
    
    # Nur Featured Images laden (da nur diese zu Shopify synchronisiert werden können)
    images = []
    
    # Featured image
    if blog_post.featured_image_url:
        # Bereinige Alt-Text von None-Werten
        alt_text = blog_post.featured_image_alt or ''
        if alt_text in ['None', 'null', None]:
            alt_text = ''
        
        images.append({
            'id': f'featured_{blog_post.id}',
            'src': blog_post.featured_image_url,
            'alt': alt_text,
            'width': None,
            'height': None,
            'is_featured': True,
            'name': 'Hauptbild'
        })
    
    # CONTENT-BILDER WERDEN NICHT ANGEZEIGT
    # Grund: Shopify API erlaubt keine direkten Alt-Text-Updates für Content-Bilder
    # Nur Featured Images können erfolgreich zu Shopify synchronisiert werden
    
    # Lade auch Bilder aus raw_shopify_data falls vorhanden
    if blog_post.raw_shopify_data and 'image' in blog_post.raw_shopify_data:
        shopify_image = blog_post.raw_shopify_data['image']
        if shopify_image and shopify_image.get('src'):
            # Prüfe ob dieses Bild nicht bereits als Featured Image hinzugefügt wurde
            existing_srcs = [img['src'] for img in images]
            if shopify_image['src'] not in existing_srcs:
                alt_text = shopify_image.get('alt', '') or ''
                if alt_text in ['None', 'null', None]:
                    alt_text = ''
                
                images.append({
                    'id': f'shopify_{blog_post.id}',
                    'src': shopify_image['src'],
                    'alt': alt_text,
                    'width': shopify_image.get('width'),
                    'height': shopify_image.get('height'),
                    'is_featured': True,
                    'name': 'Shopify-Bild'
                })
    
    context = {
        'blog_post': blog_post,
        'images': images
    }
    
    return render(request, 'shopify_manager/blog_post_alt_text_manager.html', context)


@login_required
@require_http_methods(["POST"])
def generate_alt_text_view(request):
    """Generiert Alt-Text für ein Bild mit KI"""
    image_url = request.POST.get('image_url')
    django_product_id = request.POST.get('django_product_id')
    product_id = request.POST.get('product_id')  # Shopify ID for backwards compatibility
    blog_post_title = request.POST.get('blog_post_title')
    blog_post_content = request.POST.get('blog_post_content')
    
    if not image_url:
        return JsonResponse({
            'success': False,
            'error': 'Bild-URL fehlt'
        })
    
    # Prüfe ob es sich um einen Blog-Post handelt
    if blog_post_title or blog_post_content:
        # Blog-Post Alt-Text Generierung
        try:
            blog_post = None
            if django_product_id:
                try:
                    blog_post = ShopifyBlogPost.objects.filter(
                        id=django_product_id,
                        blog__store__user=request.user
                    ).first()
                except:
                    pass
            
            # Erstelle Kontext für Alt-Text Generierung
            context = {
                'title': blog_post_title or (blog_post.title if blog_post else ''),
                'content': blog_post_content or (blog_post.content if blog_post else ''),
                'type': 'blog_post'
            }
            
            # Versuche KI-basierte Alt-Text Generierung (gleiche Funktionalität wie bei Produkten)
            if blog_post:
                try:
                    # Erstelle ein temporäres Produkt-ähnliches Objekt für die KI-Generierung
                    class BlogPostWrapper:
                        def __init__(self, blog_post):
                            self.title = blog_post.title
                            self.body_html = blog_post.content or ''
                            self.vendor = blog_post.author or ''
                            self.product_type = 'Blog-Post'
                            self.store = blog_post.blog.store
                    
                    blog_wrapper = BlogPostWrapper(blog_post)
                    alt_text = generate_alt_text_with_ai(blog_wrapper, image_url, request.user)
                    if alt_text and alt_text != 'Produktbild':
                        return JsonResponse({
                            'success': True,
                            'alt_text': alt_text,
                            'method': 'ai'
                        })
                except Exception as e:
                    print(f"AI Alt-Text generation failed: {e}")
            
            # Einfacher Fallback
            alt_text = "Blog-Beitragsbild"
            
            return JsonResponse({
                'success': True,
                'alt_text': alt_text,
                'method': 'fallback'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Fehler bei der Alt-Text Generierung: {str(e)}'
            })
    
    # Finde das Produkt basierend auf Django ID (ursprüngliche Logik)
    product = None
    if django_product_id:
        try:
            product = ShopifyProduct.objects.filter(
                id=django_product_id,
                store__user=request.user
            ).first()
        except:
            pass
    elif product_id:
        # Fallback für alte Implementierung
        try:
            product = ShopifyProduct.objects.filter(
                id=product_id,
                store__user=request.user
            ).first()
        except:
            pass
    
    if not product:
        # Fallback für fehlende Produktdaten
        print(f"DEBUG: Kein Produkt mit ID {product_id} gefunden für User {request.user}")
        return JsonResponse({
            'success': True,
            'alt_text': 'Produktbild',
            'suggested_alt': 'Produktbild'
        })
    
    try:
        # Versuche KI-Integration für Alt-Text-Generierung
        print(f"DEBUG: Starte KI-Alt-Text Generierung für Produkt: {product.title}")
        suggested_alt = generate_alt_text_with_ai(product, image_url, request.user)
        
        # Validiere und bereinige AI-Ergebnis
        if suggested_alt and suggested_alt.strip() and suggested_alt.lower() not in ['none', 'null']:
            suggested_alt = suggested_alt.strip()
            print(f"DEBUG: KI-Alt-Text generiert für Bild {image_url}: {suggested_alt}")
            return JsonResponse({
                'success': True,
                'alt_text': suggested_alt,
                'suggested_alt': suggested_alt  # Beide Formate für Kompatibilität
            })
        else:
            # Keine KI-Generierung möglich - Fehler zurückgeben statt Fallback
            print(f"DEBUG: KI-Generierung fehlgeschlagen für Bild {image_url} ('{suggested_alt}')")
            return JsonResponse({
                'success': False,
                'error': 'Alt-Text konnte nicht generiert werden. OpenAI API ist nicht verfügbar oder fehlgeschlagen.',
                'details': f'API Response: {suggested_alt}' if suggested_alt else 'Keine API-Response erhalten'
            })
            
    except Exception as e:
        print(f"Alt-Text Generierung Fehler: {e}")
        # Kein Fallback mehr - direkt Fehler zurückgeben
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der Alt-Text-Generierung: {str(e)}'
        })


def generate_alt_text_with_ai(product, image_url, user):
    """Generiert Alt-Text mit KI-Unterstützung"""
    print(f"DEBUG: Starte KI-Alt-Text für Produkt: {product.title}")
    print(f"DEBUG: Bild-URL: {image_url}")
    
    try:
        # Versuche verschiedene AI-Services
        from naturmacher.utils.api_helpers import get_user_api_key
        
        # 1. OpenAI GPT-4 Vision (falls verfügbar)
        openai_key = get_user_api_key(user, 'openai')
        print(f"DEBUG: OpenAI Key verfügbar: {bool(openai_key)}")
        if openai_key:
            try:
                print("DEBUG: Versuche OpenAI Vision...")
                alt_text = generate_alt_text_openai_vision(product, image_url, openai_key)
                if alt_text:
                    print(f"DEBUG: OpenAI Vision erfolgreich: {alt_text}")
                    return alt_text
                else:
                    print("DEBUG: OpenAI Vision lieferte keinen Text")
            except Exception as e:
                print(f"OpenAI Vision fehlgeschlagen: {e}")
        
        print("DEBUG: OpenAI nicht verfügbar oder fehlgeschlagen - keine weiteren KI-Services konfiguriert")
        return None
        
    except Exception as e:
        print(f"Fehler bei Alt-Text-Generierung: {e}")
        return None


def generate_alt_text_openai_vision(product, image_url, api_key):
    """Generiert Alt-Text mit OpenAI GPT-4 Vision oder Text-basiertem Fallback"""
    try:
        # Zuerst versuchen, das Bild zu validieren
        try:
            img_response = requests.head(image_url, timeout=5)
            if img_response.status_code != 200:
                print(f"DEBUG: Bild nicht erreichbar (Status {img_response.status_code}), verwende Text-basierte Generierung")
                return generate_alt_text_openai_text_only(product, api_key)
        except:
            print(f"DEBUG: Bild-URL nicht erreichbar, verwende Text-basierte Generierung")
            return generate_alt_text_openai_text_only(product, api_key)
        
        prompt = f"""Analysiere dieses Produktbild und erstelle einen präzisen Alt-Text für SEO und Barrierefreiheit.

Produktkontext:
- Titel: {product.title}
- Hersteller: {product.vendor or 'Unbekannt'}
- Typ: {product.product_type or 'Unbekannt'}
- Beschreibung: {(product.body_html or '')[:200]}

Erstelle einen Alt-Text der:
- Präzise das Bild beschreibt
- Für Screenreader geeignet ist
- SEO-optimiert ist
- Unter 125 Zeichen liegt
- Den Produktkontext berücksichtigt

Antworte nur mit dem Alt-Text, ohne weitere Erklärungen."""

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o',
                'messages': [
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': prompt},
                            {'type': 'image_url', 'image_url': {'url': image_url}}
                        ]
                    }
                ],
                'max_tokens': 100,
                'temperature': 0.3
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                alt_text = result['choices'][0]['message']['content'].strip()
                # Kürze wenn nötig
                if len(alt_text) > 125:
                    alt_text = alt_text[:122] + '...'
                print(f"DEBUG: OpenAI Vision erfolgreich: {alt_text}")
                return alt_text
        else:
            # Fallback zu Text-only bei API-Fehlern
            print(f"DEBUG: Vision API Fehler (Status {response.status_code}), verwende Text-basierte Generierung")
            return generate_alt_text_openai_text_only(product, api_key)
        
    except Exception as e:
        print(f"DEBUG: OpenAI Vision Fehler: {e}, verwende Text-basierte Generierung")
        return generate_alt_text_openai_text_only(product, api_key)
    
    return None


def generate_alt_text_openai_text_only(product, api_key):
    """Generiert Alt-Text nur auf Basis der Produktdaten (ohne Bilderkennung)"""
    try:
        prompt = f"""Erstelle einen präzisen Alt-Text für ein Produktbild basierend auf den folgenden Produktdaten:

Produktkontext:
- Titel: {product.title}
- Hersteller: {product.vendor or 'Unbekannt'}
- Typ: {product.product_type or 'Unbekannt'}
- Beschreibung: {(product.body_html or '')[:300]}

Erstelle einen Alt-Text der:
- Das Produkt präzise beschreibt (auch ohne das Bild zu sehen)
- Für Screenreader geeignet ist
- SEO-optimiert ist
- Unter 125 Zeichen liegt
- Natürlich klingt

Antworte nur mit dem Alt-Text, ohne weitere Erklärungen."""

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o-mini',  # Günstiger für Text-only
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 80,
                'temperature': 0.3
            },
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                alt_text = result['choices'][0]['message']['content'].strip()
                # Kürze wenn nötig
                if len(alt_text) > 125:
                    alt_text = alt_text[:122] + '...'
                return alt_text
        
    except Exception as e:
        print(f"DEBUG: OpenAI Text-only Fehler: {e}")
    
    return None


# generate_alt_text_google_vision komplett entfernt


# generate_alt_text_fallback komplett entfernt - keine automatischen Fallback-Texte


# generate_alt_text_anthropic_vision komplett entfernt


@login_required
@require_http_methods(["GET"])
def get_blogs_for_store_view(request, store_id):
    """Holt Blogs für einen Store zur Auswahl"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        blogs = ShopifyBlog.objects.filter(store=store)
        
        blog_data = []
        for blog in blogs:
            blog_data.append({
                'id': blog.id,
                'title': blog.title,
                'handle': blog.handle,
                'posts_count': blog.posts_count
            })
        
        return JsonResponse({
            'success': True,
            'blogs': blog_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Laden der Blogs: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def import_all_blog_posts_view(request):
    """Importiert alle Blog-Posts für alle Blogs eines Stores (mit Background-Thread)"""
    store_id = request.POST.get('store_id')
    import_mode = request.POST.get('import_mode', 'new_only')

    if not store_id:
        return JsonResponse({
            'success': False,
            'error': 'Store-ID fehlt'
        })

    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)

    # Prüfe ob Blogs existieren
    blogs = ShopifyBlog.objects.filter(store=store)
    if not blogs.exists():
        return JsonResponse({
            'success': False,
            'error': 'Keine Blogs gefunden. Bitte importieren Sie zuerst Blogs für diesen Store.'
        })

    # Erstelle eine eindeutige Import-ID
    import_id = str(uuid.uuid4())

    # Initialisiere Progress-Tracking
    import time as time_module
    import_progress[import_id] = {
        'status': 'running',
        'current': 0,
        'total': 0,
        'message': 'Import aller Blog-Posts wird gestartet...',
        'success': True,
        'error': None,
        'success_count': 0,
        'failed_count': 0,
        'last_update': time_module.time()
    }

    # Starte Import in separatem Thread
    import_thread = threading.Thread(
        target=_run_all_blogs_import,
        args=(store, import_mode, import_id),
        daemon=True
    )
    import_thread.start()

    return JsonResponse({
        'success': True,
        'import_id': import_id,
        'message': 'Import gestartet'
    })


def _run_all_blogs_import(store, import_mode, import_id):
    """Führt den Import aller Blog-Posts in einem separaten Thread aus"""
    import time as time_module
    try:
        blogs = ShopifyBlog.objects.filter(store=store)
        total_blogs = blogs.count()
        total_imported = 0
        total_failed = 0

        for idx, blog in enumerate(blogs):
            # Update Progress
            import_progress[import_id].update({
                'message': f'Importiere Blog {idx + 1}/{total_blogs}: {blog.title}...',
                'current': idx,
                'total': total_blogs,
                'success_count': total_imported,
                'failed_count': total_failed,
                'last_update': time_module.time()
            })

            # Importiere Posts für diesen Blog
            blog_sync = ShopifyBlogSyncWithProgress(store, import_id)
            log = blog_sync.import_blog_posts(blog, import_mode=import_mode)
            total_imported += log.products_success
            total_failed += log.products_failed

        # Final status
        message = f'{total_imported} Blog-Posts aus {total_blogs} Blogs importiert'
        if total_failed > 0:
            message += f', {total_failed} fehlgeschlagen'

        import_progress[import_id].update({
            'status': 'completed',
            'success': True,
            'message': message,
            'imported': total_imported,
            'failed': total_failed,
            'success_count': total_imported,
            'failed_count': total_failed,
            'blogs_processed': total_blogs,
            'last_update': time_module.time()
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Exception in all blogs import: {error_details}")

        import_progress[import_id].update({
            'status': 'error',
            'success': False,
            'error': str(e),
            'message': f'Import fehlgeschlagen: {str(e)}',
            'last_update': time_module.time()
        })


@login_required
def blog_post_seo_optimization_view(request, blog_post_id):
    """SEO-Optimierung Seite für Blog-Posts mit KI-Unterstützung"""
    # blog_post_id kann sowohl lokale ID als auch Shopify-ID sein
    blog_post = None
    
    try:
        # Versuche zuerst mit Shopify-ID
        blog_post = ShopifyBlogPost.objects.get(
            shopify_id=str(blog_post_id), 
            blog__store__user=request.user
        )
        print(f"Blog-Post gefunden über Shopify-ID: {blog_post_id}")
    except ShopifyBlogPost.DoesNotExist:
        # Fallback: Versuche mit lokaler ID
        try:
            blog_post = ShopifyBlogPost.objects.get(
                id=blog_post_id, 
                blog__store__user=request.user
            )
            print(f"Blog-Post gefunden über lokale ID: {blog_post_id}")
        except ShopifyBlogPost.DoesNotExist:
            print(f"Blog-Post nicht gefunden - weder Shopify-ID noch lokale ID: {blog_post_id}")
            from django.http import Http404
            raise Http404(f"Blog-Post mit ID {blog_post_id} nicht gefunden")
    
    if request.method == 'POST':
        form = BlogPostSEOOptimizationForm(request.POST, blog_post=blog_post)
        if form.is_valid():
            seo_optimization = form.save()
            return redirect('shopify_manager:blog_post_seo_optimization_detail', pk=seo_optimization.pk)
    else:
        form = BlogPostSEOOptimizationForm(blog_post=blog_post)
    
    # Hole letzte SEO-Optimierungen für diesen Blog-Post
    recent_optimizations = blog_post.seo_optimizations.all()[:5]
    
    context = {
        'blog_post': blog_post,
        'form': form,
        'recent_optimizations': recent_optimizations,
    }
    
    return render(request, 'shopify_manager/blog_post_seo_optimization.html', context)


@login_required
def blog_post_seo_optimization_detail_view(request, pk):
    """Detailansicht einer Blog-Post SEO-Optimierung mit KI-Generierung"""
    seo_optimization = get_object_or_404(
        BlogPostSEOOptimization,
        pk=pk,
        blog_post__blog__store__user=request.user
    )
    
    context = {
        'seo_optimization': seo_optimization,
        'blog_post': seo_optimization.blog_post,
    }
    
    return render(request, 'shopify_manager/blog_post_seo_optimization_detail.html', context)


@login_required
@require_http_methods(["POST"])
def generate_blog_post_seo_ai_view(request, pk):
    """Generiert SEO-Inhalte für Blog-Posts mit KI"""
    seo_optimization = get_object_or_404(
        BlogPostSEOOptimization,
        pk=pk,
        blog_post__blog__store__user=request.user
    )
    
    try:
        from .ai_seo_service import BlogPostSEOService
        
        service = BlogPostSEOService(user=request.user)
        success, result, error = service.generate_seo_content(seo_optimization)
        
        if success:
            return JsonResponse({
                'success': True,
                'generated_title': seo_optimization.generated_seo_title,
                'generated_description': seo_optimization.generated_seo_description,
                'ai_response': result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': error
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der KI-Generierung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def apply_blog_post_seo_optimization_view(request, pk):
    """Wendet generierte SEO-Daten auf Blog-Post an"""
    seo_optimization = get_object_or_404(
        BlogPostSEOOptimization,
        pk=pk,
        blog_post__blog__store__user=request.user
    )
    
    try:
        # Wende die SEO-Optimierung an
        seo_optimization.apply_to_blog_post()
        
        return JsonResponse({
            'success': True,
            'message': 'SEO-Optimierung erfolgreich angewendet',
            'blog_post_url': reverse('shopify_manager:blog_post_detail', kwargs={'pk': seo_optimization.blog_post.pk})
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Anwenden der SEO-Optimierung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def delete_blog_post_local_view(request, blog_post_id):
    """Löscht einen Blog-Post nur lokal (nicht in Shopify)"""
    blog_post = get_object_or_404(ShopifyBlogPost, id=blog_post_id, blog__store__user=request.user)
    
    try:
        post_title = blog_post.title
        blog_post.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Blog-Post "{post_title}" wurde lokal gelöscht'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen: {str(e)}'
        })


@login_required  
@require_http_methods(["POST"])
def sync_blog_post_view(request, blog_post_id):
    """Synchronisiert einen Blog-Post zu Shopify"""
    blog_post = get_object_or_404(ShopifyBlogPost, id=blog_post_id, blog__store__user=request.user)
    
    try:
        from .shopify_api import ShopifyAPIClient
        
        # Erstelle API Client
        api_client = ShopifyAPIClient(blog_post.blog.store)
        
        # Synchronisiere nur SEO-Metadaten zu Shopify (ohne Inhalt, Autor, Datum zu überschreiben)
        success, message = api_client.update_blog_post_seo_only(
            blog_post.blog.shopify_id, 
            blog_post.shopify_id, 
            seo_title=blog_post.seo_title,
            seo_description=blog_post.seo_description
        )
        
        if success:
            # Aktualisiere lokale Daten falls nötig
            blog_post.shopify_updated_at = timezone.now()
            blog_post.needs_sync = False
            blog_post.sync_error = ''  # Leerer String statt None für NOT NULL Feld
            blog_post.last_synced_at = timezone.now()
            blog_post.save(update_fields=['shopify_updated_at', 'needs_sync', 'sync_error', 'last_synced_at'])
            
            return JsonResponse({
                'success': True,
                'message': f'Blog-Post "{blog_post.title}" erfolgreich synchronisiert'
            })
        else:
            # Protokolliere Sync-Fehler
            blog_post.sync_error = f'Sync-Fehler: {message}'
            blog_post.save(update_fields=['sync_error'])
            
            return JsonResponse({
                'success': False,
                'error': f'Fehler beim Synchronisieren: {message}'
            })
        
    except Exception as e:
        # Protokolliere Exception-Fehler
        blog_post.sync_error = f'Exception: {str(e)}'
        blog_post.save(update_fields=['sync_error'])
        
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Synchronisieren: {str(e)}'
        })



@login_required
def unified_seo_optimization_view(request):
    """Unified SEO-Optimierung für Produkte und Blog-Posts"""
    # Hole alle Stores des Users
    stores = ShopifyStore.objects.filter(user=request.user)
    
    # Hole alle Produkte und Blog-Posts
    products = ShopifyProduct.objects.filter(store__user=request.user, status='active').select_related('store')
    blog_posts = ShopifyBlogPost.objects.filter(blog__store__user=request.user, status='published').select_related('blog__store')
    
    # Filter anwenden
    store_filter = request.GET.get('store')
    content_type = request.GET.get('content_type', 'all')  # all, products, blog_posts
    search_query = request.GET.get('search', '')
    
    if store_filter:
        products = products.filter(store_id=store_filter)
        blog_posts = blog_posts.filter(blog__store_id=store_filter)
    
    if search_query:
        products = products.filter(Q(title__icontains=search_query) | Q(body_html__icontains=search_query))
        blog_posts = blog_posts.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query))
    
    # Paginierung
    items_per_page = 20
    
    if content_type == 'products':
        paginator = Paginator(products, items_per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        items = page_obj.object_list
        item_type = 'product'
    elif content_type == 'blog_posts':
        paginator = Paginator(blog_posts, items_per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        items = page_obj.object_list
        item_type = 'blog_post'
    else:
        # Kombiniere beide Listen
        all_items = []
        for product in products:
            all_items.append({
                'type': 'product',
                'object': product,
                'title': product.title,
                'seo_title': product.seo_title,
                'seo_description': product.seo_description,
                'store': product.store
            })
        for blog_post in blog_posts:
            all_items.append({
                'type': 'blog_post',
                'object': blog_post,
                'title': blog_post.title,
                'seo_title': blog_post.seo_title,
                'seo_description': blog_post.seo_description,
                'store': blog_post.blog.store
            })
        
        # Sortiere nach Titel
        all_items.sort(key=lambda x: x['title'])
        
        paginator = Paginator(all_items, items_per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        items = page_obj.object_list
        item_type = 'mixed'
    
    context = {
        'stores': stores,
        'items': items,
        'item_type': item_type,
        'page_obj': page_obj,
        'store_filter': store_filter,
        'content_type': content_type,
        'search_query': search_query,
    }
    
    return render(request, 'shopify_manager/unified_seo_optimization.html', context)


@login_required
def integrated_seo_optimization_view(request, content_type, content_id):
    """Integrierte SEO-Optimierung für Produkte und Blog-Posts auf einer Seite"""
    
    # Bestimme Content-Typ und hole entsprechendes Objekt
    if content_type == 'product':
        try:
            content_object = ShopifyProduct.objects.get(
                Q(id=content_id) | Q(shopify_id=str(content_id)),
                store__user=request.user
            )
            content_title = content_object.title
            content_description = content_object.body_html or ''
            current_seo_title = content_object.seo_title or ''
            current_seo_description = content_object.seo_description or ''
        except ShopifyProduct.DoesNotExist:
            from django.http import Http404
            raise Http404(f"Produkt mit ID {content_id} nicht gefunden")
            
    elif content_type == 'blog_post':
        try:
            content_object = ShopifyBlogPost.objects.get(
                id=content_id,
                blog__store__user=request.user
            )
            content_title = content_object.title
            content_description = content_object.content or content_object.summary or ''
            current_seo_title = content_object.seo_title or ''
            current_seo_description = content_object.seo_description or ''
        except ShopifyBlogPost.DoesNotExist:
            from django.http import Http404
            raise Http404(f"Blog-Post mit ID {content_id} nicht gefunden")
    else:
        from django.http import Http404
        raise Http404("Ungültiger Content-Typ")
    
    context = {
        'content_type': content_type,
        'content_object': content_object,
        'content_title': content_title,
        'content_description': content_description,
        'current_seo_title': current_seo_title,
        'current_seo_description': current_seo_description,
        # AI-Modell-Optionen (bewährte Modelle aus Naturmacher-App)
        'ai_models': [
            # OpenAI (ChatGPT) Modelle - Einzige unterstützte Option
            ('gpt-4.1', 'ChatGPT 4.1 (Neuestes Flagship, 1M Token)'),
            ('gpt-4.1-mini', 'ChatGPT 4.1 Mini (Optimiert)'),
            ('gpt-4.1-nano', 'ChatGPT 4.1 Nano (Schnellstes)'),
            ('gpt-4o', 'ChatGPT 4o (Multimodal)'),
            ('gpt-4o-mini', 'ChatGPT 4o Mini (Schnell, günstig)'),
            ('gpt-4-turbo', 'ChatGPT 4 Turbo (Erweitert)'),
            ('gpt-4', 'ChatGPT 4 (Bewährt)'),
            ('gpt-3.5-turbo', 'ChatGPT 3.5 Turbo (Schnell)'),
            
            # OpenAI Reasoning Modelle
            ('o3', 'OpenAI o3 (Neuestes Reasoning, langsam)'),
            ('o4-mini', 'OpenAI o4 Mini (Schnelles Reasoning)'),
        ]
    }
    
    return render(request, 'shopify_manager/integrated_seo_optimization.html', context)


@login_required
@require_http_methods(["POST"])
def generate_integrated_seo_view(request):
    """Generiert SEO-Inhalte für integrierte Optimierung"""
    import json
    
    try:
        # Parse JSON Request
        data = json.loads(request.body)
        content_type = data.get('content_type')
        content_id = data.get('content_id')
        keywords = data.get('keywords', '')
        ai_model = data.get('ai_model', 'openai-gpt4')
        
        # Validierung
        if not content_type or not content_id:
            return JsonResponse({
                'success': False,
                'error': 'Content-Typ und ID sind erforderlich'
            })
        
        # Hole Content-Objekt
        if content_type == 'product':
            try:
                content_object = ShopifyProduct.objects.get(
                    Q(id=content_id) | Q(shopify_id=str(content_id)),
                    store__user=request.user
                )
                title = content_object.title
                description = content_object.body_html or ''
            except ShopifyProduct.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Produkt nicht gefunden'
                })
                
        elif content_type == 'blog_post':
            try:
                content_object = ShopifyBlogPost.objects.get(
                    id=content_id,
                    blog__store__user=request.user
                )
                title = content_object.title
                description = content_object.content or content_object.summary or ''
            except ShopifyBlogPost.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Blog-Post nicht gefunden'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ungültiger Content-Typ'
            })
        
        # Keywords verarbeiten
        keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
        
        # SEO-Generierung
        if content_type == 'product':
            success, result, message, raw_response = generate_seo_with_ai(
                content_title=title,
                content_description=description,
                keywords=keywords_list,
                ai_model=ai_model,
                user=request.user
            )
        else:  # blog_post
            # Verwende Blog-Post SEO Service
            service = BlogPostSEOService(user=request.user)
            
            # Erstelle temporäres SEO-Optimization Objekt für die Generierung
            from shopify_manager.models import BlogPostSEOOptimization
            temp_seo = BlogPostSEOOptimization(
                blog_post=content_object,
                keywords=keywords,
                ai_model=ai_model
            )
            
            success, message, error_message = service.generate_seo_content(temp_seo)
            
            if success:
                result = {
                    'seo_title': temp_seo.generated_seo_title,
                    'seo_description': temp_seo.generated_seo_description
                }
                raw_response = temp_seo.ai_response_raw
            else:
                result = {}
                message = error_message
        
        if success:
            return JsonResponse({
                'success': True,
                'seo_title': result.get('seo_title', ''),
                'seo_description': result.get('seo_description', ''),
                'message': message,
                'ai_model': ai_model,
                'keywords_used': ', '.join(keywords_list)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der SEO-Generierung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def apply_integrated_seo_view(request):
    """Wendet generierte SEO-Inhalte an"""
    import json
    
    try:
        # Parse JSON Request
        data = json.loads(request.body)
        content_type = data.get('content_type')
        content_id = data.get('content_id')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        seo_title = data.get('seo_title', '').strip()
        seo_description = data.get('seo_description', '').strip()
        
        # Validierung
        if not content_type or not content_id:
            return JsonResponse({
                'success': False,
                'error': 'Content-Typ und ID sind erforderlich'
            })
        
        if not seo_title and not seo_description:
            return JsonResponse({
                'success': False,
                'error': 'Mindestens ein SEO-Feld muss ausgefüllt sein'
            })
        
        # Wende Änderungen an
        if content_type == 'product':
            try:
                content_object = ShopifyProduct.objects.get(
                    Q(id=content_id) | Q(shopify_id=str(content_id)),
                    store__user=request.user
                )
                
                # Hauptfelder NICHT mehr aktualisieren bei SEO-Änderungen
                # um zu verhindern, dass die Produktbeschreibung überschrieben wird
                # if title:
                #     content_object.title = title
                # if description:
                #     content_object.body_html = description
                
                # SEO-Felder aktualisieren
                if seo_title:
                    content_object.seo_title = seo_title
                if seo_description:
                    content_object.seo_description = seo_description
                
                content_object.needs_sync = True
                content_object.save()
                
                updated_fields = []
                # if title: updated_fields.append("Titel")
                # if description: updated_fields.append("Beschreibung")
                if seo_title: updated_fields.append("SEO-Titel")
                if seo_description: updated_fields.append("SEO-Beschreibung")
                
                # Automatische Synchronisation zu Shopify für Produkte
                try:
                    from .shopify_api import ShopifyAPIClient
                    
                    api_client = ShopifyAPIClient(content_object.store)
                    
                    # Aktualisiere NUR SEO-Metafelder (um Beschreibung nicht zu überschreiben)
                    success, sync_message = api_client.update_product_seo_only(
                        content_object.shopify_id,
                        seo_title=content_object.seo_title if seo_title else None,
                        seo_description=content_object.seo_description if seo_description else None
                    )
                    
                    if success:
                        # Aktualisiere lokale Daten
                        content_object.shopify_updated_at = timezone.now()
                        content_object.needs_sync = False
                        content_object.sync_error = ''  # Leerer String statt None für NOT NULL Feld
                        content_object.last_synced_at = timezone.now()
                        content_object.save(update_fields=['shopify_updated_at', 'needs_sync', 'sync_error', 'last_synced_at'])
                        
                        message = f'Produkt "{content_object.title}" erfolgreich aktualisiert und zu Shopify synchronisiert'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                    else:
                        # Sync-Fehler protokollieren
                        content_object.sync_error = f'Sync-Fehler: {sync_message}'
                        content_object.save(update_fields=['sync_error'])
                        
                        message = f'Produkt "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                        message += f' (Sync-Fehler: {sync_message})'
                        
                except Exception as sync_error:
                    # Sync-Exception protokollieren
                    content_object.sync_error = f'Sync-Exception: {str(sync_error)}'
                    content_object.save(update_fields=['sync_error'])
                    
                    message = f'Produkt "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                    if updated_fields:
                        message += f': {", ".join(updated_fields)}'
                    message += f' (Fehler: {str(sync_error)})'
                
                return JsonResponse({
                    'success': True,
                    'message': message
                })
                
            except ShopifyProduct.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Produkt nicht gefunden'
                })
                
        elif content_type == 'blog_post':
            try:
                content_object = ShopifyBlogPost.objects.get(
                    id=content_id,
                    blog__store__user=request.user
                )
                
                # Hauptfelder NICHT mehr aktualisieren bei reinen SEO-Änderungen
                # um zu verhindern, dass Titel/Inhalt überschrieben werden
                # Die SEO-Optimierung soll nur SEO-Metadaten ändern
                # if title and title.strip():
                #     content_object.title = title.strip()
                # if description and description.strip():
                #     content_object.content = description.strip()
                
                # SEO-Felder aktualisieren
                if seo_title:
                    content_object.seo_title = seo_title
                if seo_description:
                    content_object.seo_description = seo_description
                
                # Setze needs_sync für automatische Synchronisation
                content_object.needs_sync = True
                content_object.save()
                
                updated_fields = []
                # if title and title.strip(): updated_fields.append("Titel")
                # if description and description.strip(): updated_fields.append("Inhalt")
                if seo_title: updated_fields.append("SEO-Titel")
                if seo_description: updated_fields.append("SEO-Beschreibung")
                
                # Automatische Synchronisation zu Shopify
                try:
                    from .shopify_api import ShopifyAPIClient
                    
                    api_client = ShopifyAPIClient(content_object.blog.store)
                    
                    # Da Hauptfelder nicht mehr aktualisiert werden, verwende immer SEO-Only Sync
                    main_fields_updated = False  # Fixiert auf False da nur SEO-Updates erfolgen
                    
                    if main_fields_updated:
                        # Wenn Hauptfelder geändert wurden, vollständige Synchronisation
                        blog_post_data = {
                            'title': content_object.title or 'Untitled',  # Fallback für leeren Titel
                            'body_html': content_object.content or '',
                            'summary': content_object.summary or '',
                            'author': content_object.author or '',
                            'tags': content_object.tags or '',
                        }
                        
                        # WICHTIG: published_at beibehalten, sonst wird der Post auf draft gesetzt
                        if content_object.published_at:
                            blog_post_data['published_at'] = content_object.published_at.isoformat()
                        
                        success, updated_article, sync_message = api_client.update_blog_post(
                            content_object.blog.shopify_id, 
                            content_object.shopify_id, 
                            blog_post_data
                        )
                        
                        # Zusätzlich SEO-Metadaten aktualisieren falls vorhanden
                        if success and (seo_title or seo_description):
                            seo_success, seo_message = api_client.update_blog_post_seo_only(
                                content_object.blog.shopify_id, 
                                content_object.shopify_id, 
                                seo_title=content_object.seo_title,
                                seo_description=content_object.seo_description
                            )
                            if not seo_success:
                                sync_message += f"; SEO-Update: {seo_message}"
                    else:
                        # Nur SEO-Metadaten synchronisieren
                        success, sync_message = api_client.update_blog_post_seo_only(
                            content_object.blog.shopify_id, 
                            content_object.shopify_id, 
                            seo_title=content_object.seo_title,
                            seo_description=content_object.seo_description
                        )
                    
                    if success:
                        # Aktualisiere lokale Daten
                        content_object.shopify_updated_at = timezone.now()
                        content_object.needs_sync = False
                        content_object.sync_error = ''  # Leerer String statt None für NOT NULL Feld
                        content_object.last_synced_at = timezone.now()
                        content_object.save(update_fields=['shopify_updated_at', 'needs_sync', 'sync_error', 'last_synced_at'])
                        
                        message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert und zu Shopify synchronisiert'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                    else:
                        # Sync-Fehler protokollieren
                        content_object.sync_error = f'Sync-Fehler: {sync_message}'
                        content_object.save(update_fields=['sync_error'])
                        
                        message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                        message += f' (Sync-Fehler: {sync_message})'
                        
                except Exception as sync_error:
                    # Sync-Exception protokollieren
                    content_object.sync_error = f'Sync-Exception: {str(sync_error)}'
                    content_object.save(update_fields=['sync_error'])
                    
                    message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                    if updated_fields:
                        message += f': {", ".join(updated_fields)}'
                    message += f' (Fehler: {str(sync_error)})'
                
                return JsonResponse({
                    'success': True,
                    'message': message
                })
                
            except ShopifyBlogPost.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Blog-Post nicht gefunden'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ungültiger Content-Typ'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Anwenden der Änderungen: {str(e)}'
        })


@login_required
def product_seo_optimization_view(request, product_id):
    """Separate SEO-Optimierung für Produkte"""
    try:
        product = ShopifyProduct.objects.get(
            Q(id=product_id) | Q(shopify_id=str(product_id)),
            store__user=request.user
        )
    except ShopifyProduct.DoesNotExist:
        from django.http import Http404
        raise Http404(f"Produkt mit ID {product_id} nicht gefunden")
    
    context = {
        'product': product,
        'content_type': 'product',
        'content_id': product.pk,
        'content_title': product.title,
        'current_seo_title': product.seo_title or '',
        'current_seo_description': product.seo_description or '',
    }
    
    return render(request, 'shopify_manager/product_seo_optimization.html', context)


@login_required
def blog_post_seo_optimization_view(request, blog_post_id):
    """Separate SEO-Optimierung für Blog-Posts"""
    try:
        blog_post = ShopifyBlogPost.objects.get(
            id=blog_post_id,
            blog__store__user=request.user
        )
    except ShopifyBlogPost.DoesNotExist:
        from django.http import Http404
        raise Http404(f"Blog-Post mit ID {blog_post_id} nicht gefunden")
    
    context = {
        'blog_post': blog_post,
        'content_type': 'blog_post',
        'content_id': blog_post.pk,
        'content_title': blog_post.title,
        'current_seo_title': blog_post.seo_title or '',
        'current_seo_description': blog_post.seo_description or '',
    }
    
    return render(request, 'shopify_manager/blog_post_seo_optimization.html', context)


@login_required
@require_http_methods(["POST"])
def generate_seo_view(request):
    """Generiert SEO-Inhalte für die neue unified SEO-Optimierung"""
    import json
    
    try:
        # Parse JSON Request
        data = json.loads(request.body)
        content_type = data.get('content_type')
        content_id = data.get('content_id')
        title = data.get('title', '')
        description = data.get('description', '')
        keywords = data.get('keywords', '')
        ai_model = data.get('ai_model', 'openai-gpt4')
        
        # Validierung
        if not content_type or not content_id:
            return JsonResponse({
                'success': False,
                'error': 'Content-Typ und ID sind erforderlich'
            })
        
        # Hole Content-Objekt
        if content_type == 'product':
            try:
                content_object = ShopifyProduct.objects.get(
                    Q(id=content_id) | Q(shopify_id=str(content_id)),
                    store__user=request.user
                )
                title = title or content_object.title
                description = description or content_object.body_html or ''
            except ShopifyProduct.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Produkt nicht gefunden'
                })
                
        elif content_type == 'blog_post':
            try:
                content_object = ShopifyBlogPost.objects.get(
                    id=content_id,
                    blog__store__user=request.user
                )
                title = title or content_object.title
                description = description or content_object.content or content_object.summary or ''
            except ShopifyBlogPost.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Blog-Post nicht gefunden'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ungültiger Content-Typ'
            })
        
        # Keywords verarbeiten
        keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
        
        # SEO-Generierung
        if content_type == 'product':
            success, result, message, raw_response = generate_seo_with_ai(
                content_title=title,
                content_description=description,
                keywords=keywords_list,
                ai_model=ai_model,
                user=request.user
            )
        else:  # blog_post
            # Verwende Blog-Post SEO Service
            service = BlogPostSEOService(user=request.user)
            
            # Erstelle temporäres SEO-Optimization Objekt für die Generierung
            from shopify_manager.models import BlogPostSEOOptimization
            temp_seo = BlogPostSEOOptimization(
                blog_post=content_object,
                keywords=keywords,
                ai_model=ai_model
            )
            
            success, message, error_message = service.generate_seo_content(temp_seo)
            
            if success:
                result = {
                    'seo_title': temp_seo.generated_seo_title,
                    'seo_description': temp_seo.generated_seo_description
                }
                raw_response = temp_seo.ai_response_raw
            else:
                result = {}
                message = error_message
        
        if success:
            return JsonResponse({
                'success': True,
                'seo_title': result.get('seo_title', ''),
                'seo_description': result.get('seo_description', ''),
                'message': message,
                'ai_model': ai_model,
                'keywords_used': ', '.join(keywords_list)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der SEO-Generierung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def apply_seo_view(request):
    """Wendet generierte SEO-Inhalte an für die neue unified SEO-Optimierung"""
    import json
    
    try:
        # Parse JSON Request
        data = json.loads(request.body)
        content_type = data.get('content_type')
        content_id = data.get('content_id')
        # title und description werden für blog_post verwendet, aber nicht für products
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        seo_title = data.get('seo_title', '').strip()
        seo_description = data.get('seo_description', '').strip()
        
        # DEBUG: Protokolliere was empfangen wird
        debug_info = None
        if content_type == 'blog_post':
            debug_info = {
                'content_id': content_id,
                'title_len': len(title),
                'description_len': len(description),
                'seo_title_len': len(seo_title),
                'seo_description_len': len(seo_description),
                'title_value': title[:50] + '...' if len(title) > 50 else title,
                'description_value': description[:50] + '...' if len(description) > 50 else description
            }
            print(f"\n=== BLOG SEO DEBUG ===")
            print(f"Content ID: {content_id}")
            print(f"Title: '{title}' (len: {len(title)})")
            print(f"Description: '{description}' (len: {len(description)})")
            print(f"SEO Title: '{seo_title}' (len: {len(seo_title)})")
            print(f"SEO Description: '{seo_description}' (len: {len(seo_description)})")
            print(f"======================\n")
        
        # Validierung
        if not content_type or not content_id:
            return JsonResponse({
                'success': False,
                'error': 'Content-Typ und ID sind erforderlich'
            })
        
        if not seo_title and not seo_description:
            return JsonResponse({
                'success': False,
                'error': 'Mindestens ein SEO-Feld muss ausgefüllt sein'
            })
        
        # Wende Änderungen an
        if content_type == 'product':
            try:
                content_object = ShopifyProduct.objects.get(
                    Q(id=content_id) | Q(shopify_id=str(content_id)),
                    store__user=request.user
                )
                
                # Hauptfelder NICHT mehr aktualisieren bei SEO-Änderungen
                # um zu verhindern, dass die Produktbeschreibung überschrieben wird
                # if title:
                #     content_object.title = title
                # if description:
                #     content_object.body_html = description
                
                # SEO-Felder aktualisieren
                if seo_title:
                    content_object.seo_title = seo_title
                if seo_description:
                    content_object.seo_description = seo_description
                
                content_object.needs_sync = True
                content_object.save()
                
                updated_fields = []
                # if title: updated_fields.append("Titel")
                # if description: updated_fields.append("Beschreibung")
                if seo_title: updated_fields.append("SEO-Titel")
                if seo_description: updated_fields.append("SEO-Beschreibung")
                
                # Automatische Synchronisation zu Shopify für Produkte
                try:
                    from .shopify_api import ShopifyAPIClient
                    
                    api_client = ShopifyAPIClient(content_object.store)
                    
                    # Aktualisiere NUR SEO-Metafelder (um Beschreibung nicht zu überschreiben)
                    success, sync_message = api_client.update_product_seo_only(
                        content_object.shopify_id,
                        seo_title=content_object.seo_title if seo_title else None,
                        seo_description=content_object.seo_description if seo_description else None
                    )
                    
                    if success:
                        # Aktualisiere lokale Daten
                        content_object.shopify_updated_at = timezone.now()
                        content_object.needs_sync = False
                        content_object.sync_error = ''  # Leerer String statt None für NOT NULL Feld
                        content_object.last_synced_at = timezone.now()
                        content_object.save(update_fields=['shopify_updated_at', 'needs_sync', 'sync_error', 'last_synced_at'])
                        
                        message = f'Produkt "{content_object.title}" erfolgreich aktualisiert und zu Shopify synchronisiert'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                    else:
                        # Sync-Fehler protokollieren
                        content_object.sync_error = f'Sync-Fehler: {sync_message}'
                        content_object.save(update_fields=['sync_error'])
                        
                        message = f'Produkt "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                        message += f' (Sync-Fehler: {sync_message})'
                        
                except Exception as sync_error:
                    # Sync-Exception protokollieren
                    content_object.sync_error = f'Sync-Exception: {str(sync_error)}'
                    content_object.save(update_fields=['sync_error'])
                    
                    message = f'Produkt "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                    if updated_fields:
                        message += f': {", ".join(updated_fields)}'
                    message += f' (Fehler: {str(sync_error)})'
                
                return JsonResponse({
                    'success': True,
                    'message': message
                })
                
            except ShopifyProduct.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Produkt nicht gefunden'
                })
                
        elif content_type == 'blog_post':
            try:
                content_object = ShopifyBlogPost.objects.get(
                    id=content_id,
                    blog__store__user=request.user
                )
                
                # Hauptfelder NICHT mehr aktualisieren bei reinen SEO-Änderungen
                # um zu verhindern, dass Titel/Inhalt überschrieben werden
                # Die SEO-Optimierung soll nur SEO-Metadaten ändern
                # if title and title.strip():
                #     content_object.title = title.strip()
                # if description and description.strip():
                #     content_object.content = description.strip()
                
                # SEO-Felder aktualisieren
                if seo_title:
                    content_object.seo_title = seo_title
                if seo_description:
                    content_object.seo_description = seo_description
                
                # Setze needs_sync für automatische Synchronisation
                content_object.needs_sync = True
                content_object.save()
                
                updated_fields = []
                # if title and title.strip(): updated_fields.append("Titel")
                # if description and description.strip(): updated_fields.append("Inhalt")
                if seo_title: updated_fields.append("SEO-Titel")
                if seo_description: updated_fields.append("SEO-Beschreibung")
                
                # Automatische Synchronisation zu Shopify
                try:
                    from .shopify_api import ShopifyAPIClient
                    
                    api_client = ShopifyAPIClient(content_object.blog.store)
                    
                    # Da Hauptfelder nicht mehr aktualisiert werden, verwende immer SEO-Only Sync
                    main_fields_updated = False  # Fixiert auf False da nur SEO-Updates erfolgen
                    
                    if main_fields_updated:
                        # Wenn Hauptfelder geändert wurden, vollständige Synchronisation
                        blog_post_data = {
                            'title': content_object.title or 'Untitled',  # Fallback für leeren Titel
                            'body_html': content_object.content or '',
                            'summary': content_object.summary or '',
                            'author': content_object.author or '',
                            'tags': content_object.tags or '',
                        }
                        
                        # WICHTIG: published_at beibehalten, sonst wird der Post auf draft gesetzt
                        if content_object.published_at:
                            blog_post_data['published_at'] = content_object.published_at.isoformat()
                        
                        success, updated_article, sync_message = api_client.update_blog_post(
                            content_object.blog.shopify_id, 
                            content_object.shopify_id, 
                            blog_post_data
                        )
                        
                        # Zusätzlich SEO-Metadaten aktualisieren falls vorhanden
                        if success and (seo_title or seo_description):
                            seo_success, seo_message = api_client.update_blog_post_seo_only(
                                content_object.blog.shopify_id, 
                                content_object.shopify_id, 
                                seo_title=content_object.seo_title,
                                seo_description=content_object.seo_description
                            )
                            if not seo_success:
                                sync_message += f"; SEO-Update: {seo_message}"
                    else:
                        # Nur SEO-Metadaten synchronisieren
                        success, sync_message = api_client.update_blog_post_seo_only(
                            content_object.blog.shopify_id, 
                            content_object.shopify_id, 
                            seo_title=content_object.seo_title,
                            seo_description=content_object.seo_description
                        )
                    
                    if success:
                        # Aktualisiere lokale Daten
                        content_object.shopify_updated_at = timezone.now()
                        content_object.needs_sync = False
                        content_object.sync_error = ''  # Leerer String statt None für NOT NULL Feld
                        content_object.last_synced_at = timezone.now()
                        content_object.save(update_fields=['shopify_updated_at', 'needs_sync', 'sync_error', 'last_synced_at'])
                        
                        message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert und zu Shopify synchronisiert'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                    else:
                        # Sync-Fehler protokollieren
                        content_object.sync_error = f'Sync-Fehler: {sync_message}'
                        content_object.save(update_fields=['sync_error'])
                        
                        message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                        if updated_fields:
                            message += f': {", ".join(updated_fields)}'
                        message += f' (Sync-Fehler: {sync_message})'
                        
                except Exception as sync_error:
                    # Sync-Exception protokollieren
                    content_object.sync_error = f'Sync-Exception: {str(sync_error)}'
                    content_object.save(update_fields=['sync_error'])
                    
                    message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert, aber Shopify-Sync fehlgeschlagen'
                    if updated_fields:
                        message += f': {", ".join(updated_fields)}'
                    message += f' (Fehler: {str(sync_error)})'
                
                return JsonResponse({
                    'success': True,
                    'message': message
                })
                
            except ShopifyBlogPost.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Blog-Post nicht gefunden'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ungültiger Content-Typ'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Anwenden der Änderungen: {str(e)}'
        })

# ============================================
# BACKUP & RESTORE VIEWS
# ============================================

from .models import ShopifyBackup, BackupItem, RestoreLog
from .backup_service import ShopifyBackupService
from .restore_service import ShopifyRestoreService
from django.http import HttpResponse


@login_required
def backup_overview(request):
    """Übersicht aller Backups über alle Stores"""
    stores = ShopifyStore.objects.filter(user=request.user)
    all_backups = ShopifyBackup.objects.filter(store__user=request.user).order_by('-created_at')[:20]

    return render(request, 'shopify_manager/backup/backup_overview.html', {
        'stores': stores,
        'recent_backups': all_backups,
    })


@login_required
def backup_list(request, store_id):
    """Übersicht aller Backups für einen Store"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backups = store.backups.all().order_by('-created_at')

    return render(request, 'shopify_manager/backup/backup_list.html', {
        'store': store,
        'backups': backups,
    })


@login_required
def backup_create(request, store_id):
    """Neues Backup erstellen - nur Backup-Objekt anlegen"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # Backup-Typ aus Radio-Button
        backup_type = request.POST.get('backup_type', 'products')
        include_images = request.POST.get('include_images') == 'on'

        try:
            # DB-Verbindung sicherstellen (PythonAnywhere Timeout-Fix)
            from django.db import connection
            connection.ensure_connection()
        except Exception:
            from django.db import connection
            connection.close()

        try:
            # Backup-Objekt erstellen - nur der ausgewählte Typ wird aktiviert
            backup = ShopifyBackup.objects.create(
                user=request.user,
                store=store,
                name=request.POST.get('name', f'Backup {timezone.now().strftime("%Y-%m-%d %H:%M")}'),
                include_products=(backup_type == 'products'),
                include_product_images=(backup_type == 'products' and include_images),
                include_blogs=(backup_type == 'blogs'),
                include_blog_images=(backup_type == 'blogs' and include_images),
                include_collections=(backup_type == 'collections'),
                include_pages=(backup_type == 'pages'),
                include_menus=(backup_type == 'menus'),
                include_redirects=(backup_type == 'redirects'),
                include_metafields=False,  # Nicht mehr als separater Typ
                include_discounts=(backup_type == 'discounts'),
                include_orders=False,  # Nicht mehr als separater Typ
                include_customers=(backup_type == 'customers'),
            )
        except Exception as e:
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': f'Datenbankfehler: {str(e)}'
                })
            else:
                messages.error(request, f'Backup konnte nicht erstellt werden: {str(e)}')
                return redirect('shopify_manager:backup_list', store_id=store.id)

        if is_ajax:
            # Bei AJAX: Nur Backup-ID zurückgeben, Start über separaten Endpunkt
            return JsonResponse({
                'success': True,
                'backup_id': backup.id,
                'start_url': f'/shopify/api/store/{store.id}/backups/{backup.id}/start/',
                'status_url': f'/shopify/api/store/{store.id}/backups/{backup.id}/status/',
                'detail_url': f'/shopify/store/{store.id}/backups/{backup.id}/',
            })
        else:
            # Bei normalem Request: Zur Detail-Seite weiterleiten (Backup startet dort)
            return redirect('shopify_manager:backup_detail', store_id=store.id, backup_id=backup.id)

    return render(request, 'shopify_manager/backup/backup_create.html', {
        'store': store,
    })


@login_required
@require_http_methods(['POST'])
def api_backup_start(request, store_id, backup_id):
    """API: Backup-Prozess starten oder fortsetzen (im Hintergrund-Thread)"""
    import threading

    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    # Prüfen ob Backup bereits läuft oder abgeschlossen
    if backup.status == 'completed':
        return JsonResponse({
            'success': False,
            'error': 'Backup ist bereits abgeschlossen'
        })

    # Bei "running" Status prüfen ob es wirklich noch läuft (Timeout-Check)
    if backup.status == 'running':
        # Wenn weniger als 15 Sekunden seit letzter Änderung, läuft es noch
        from django.utils import timezone
        from datetime import timedelta
        if backup.updated_at and (timezone.now() - backup.updated_at) < timedelta(seconds=15):
            return JsonResponse({
                'success': False,
                'error': 'Backup läuft noch. Bitte warten.'
            })

    # Status sofort auf 'running' setzen
    backup.status = 'running'
    backup.current_step = 'init'
    backup.progress_message = 'Backup wird gestartet...'
    backup.save()

    def run_backup():
        """Führt das Backup im Hintergrund aus"""
        try:
            # Neue DB-Verbindung für den Thread
            from django.db import connection
            connection.close()

            # Objekte neu laden
            store_obj = ShopifyStore.objects.get(id=store_id)
            backup_obj = ShopifyBackup.objects.get(id=backup_id)

            service = ShopifyBackupService(store_obj, backup_obj)
            service.create_backup()
        except Exception as e:
            # Fehler im Backup loggen
            try:
                backup_obj = ShopifyBackup.objects.get(id=backup_id)
                backup_obj.status = 'failed'
                backup_obj.error_message = str(e)
                backup_obj.current_step = 'error'
                backup_obj.progress_message = f'Fehler: {str(e)[:200]}'
                backup_obj.save()
            except:
                pass

    # Backup in separatem Thread starten
    thread = threading.Thread(target=run_backup, daemon=True)
    thread.start()

    # Sofort zurückkehren
    return JsonResponse({
        'success': True,
        'message': 'Backup wurde gestartet',
        'status': 'running',
    })


@login_required
def backup_detail(request, store_id, backup_id):
    """Backup-Details anzeigen mit Pagination und Suche"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.utils import timezone
    from datetime import timedelta

    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    # Stale-Backup-Erkennung: Automatisch pausieren wenn hängen geblieben
    if backup.status == 'running':
        stale_threshold = timezone.now() - timedelta(minutes=3)
        if backup.updated_at < stale_threshold:
            backup.status = 'paused'
            backup.progress_message = 'Automatisch pausiert: Keine Aktivität. Klicken Sie auf Weiter laden.'
            backup.save(update_fields=['status', 'progress_message', 'updated_at'])

    # Items nach Typ gruppieren (nur Counts, nicht alle Items laden)
    item_types = [
        ('product', 'Produkte'),
        ('blog', 'Blogs'),
        ('blog_post', 'Blog-Beiträge'),
        ('collection', 'Collections'),
        ('page', 'Seiten'),
        ('menu', 'Menüs'),
        ('redirect', 'Weiterleitungen'),
        ('metafield', 'Metafields'),
        ('discount', 'Rabattcodes'),
        ('order', 'Bestellungen'),
        ('customer', 'Kunden'),
    ]

    # Nur Counts ermitteln (schnell)
    items_by_type = {}
    first_type_with_items = None
    for item_type, label in item_types:
        count = backup.items.filter(item_type=item_type).count()
        if count > 0:
            items_by_type[item_type] = {
                'label': label,
                'count': count
            }
            if first_type_with_items is None:
                first_type_with_items = item_type

    # Aktiver Tab (Default: erster Typ mit Items)
    active_tab = request.GET.get('tab')
    if active_tab not in items_by_type:
        active_tab = first_type_with_items or 'product'

    # Suchbegriff
    search_query = request.GET.get('q', '').strip()

    # Seite
    page = request.GET.get('page', 1)

    # Items für aktiven Tab mit Pagination und Suche
    active_items = None
    paginator = None
    if active_tab and active_tab in items_by_type:
        items_qs = backup.items.filter(item_type=active_tab).order_by('title')

        # Suche anwenden
        if search_query:
            items_qs = items_qs.filter(title__icontains=search_query)

        # Pagination: 20 pro Seite
        paginator = Paginator(items_qs, 20)
        try:
            active_items = paginator.page(page)
        except PageNotAnInteger:
            active_items = paginator.page(1)
        except EmptyPage:
            active_items = paginator.page(paginator.num_pages)

    # Aktiver Tab Label und Count
    active_tab_label = items_by_type.get(active_tab, {}).get('label', '')
    active_tab_count = items_by_type.get(active_tab, {}).get('count', 0)

    # Restore-Logs
    restore_logs = backup.restore_logs.all().order_by('-restored_at')[:50]

    return render(request, 'shopify_manager/backup/backup_detail.html', {
        'store': store,
        'backup': backup,
        'items_by_type': items_by_type,
        'active_tab': active_tab,
        'active_tab_label': active_tab_label,
        'active_tab_count': active_tab_count,
        'active_items': active_items,
        'search_query': search_query,
        'paginator': paginator,
        'restore_logs': restore_logs,
    })


@login_required
def backup_compare(request, store_id, backup_id):
    """Backup mit aktuellem Shopify-Stand vergleichen"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    if backup.status != 'completed':
        messages.error(request, 'Nur abgeschlossene Backups können verglichen werden.')
        return redirect('shopify_manager:backup_detail', store_id=store_id, backup_id=backup_id)

    from .compare_service import ShopifyCompareService

    # Kategorie-Filter aus GET-Parameter
    category = request.GET.get('category', 'all')

    try:
        service = ShopifyCompareService(store, backup)

        if category == 'all':
            results = service.compare_all()
        else:
            results = {category: service.compare_category(category)}

        summary = service.get_summary(results)

        # Gesamtstatistik
        total_deleted = sum(s.get('deleted', 0) for s in summary.values())
        total_new = sum(s.get('new', 0) for s in summary.values())
        total_changed = sum(s.get('changed', 0) for s in summary.values())

    except Exception as e:
        messages.error(request, f'Fehler beim Vergleich: {str(e)}')
        return redirect('shopify_manager:backup_detail', store_id=store_id, backup_id=backup_id)

    # Kategorie-Labels
    category_labels = {
        'products': 'Produkte',
        'blogs': 'Blogs',
        'blog_posts': 'Blog-Beiträge',
        'collections': 'Collections',
        'pages': 'Seiten',
        'redirects': 'Weiterleitungen',
    }

    return render(request, 'shopify_manager/backup/backup_compare.html', {
        'store': store,
        'backup': backup,
        'results': results,
        'summary': summary,
        'category': category,
        'category_labels': category_labels,
        'total_deleted': total_deleted,
        'total_new': total_new,
        'total_changed': total_changed,
    })


@login_required
def backup_download(request, store_id, backup_id):
    """Backup als ZIP herunterladen"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    if backup.status != 'completed':
        messages.error(request, 'Backup ist noch nicht abgeschlossen')
        return redirect('shopify_manager:backup_detail', store_id=store.id, backup_id=backup.id)

    # ZIP generieren
    service = ShopifyBackupService(store, backup)
    zip_buffer = service.generate_download_zip()

    # Response erstellen
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    filename = f'{backup.name.replace(" ", "_")}_{backup.created_at.strftime("%Y%m%d")}.zip'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required
def backup_delete(request, store_id, backup_id):
    """Backup löschen"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    if request.method == 'POST':
        backup_name = backup.name
        # Erst alle verknüpften Items löschen (wegen MySQL FK-Constraint)
        backup.items.all().delete()
        backup.restore_logs.all().delete()
        backup.delete()
        messages.success(request, f'Backup "{backup_name}" wurde gelöscht')
        return redirect('shopify_manager:backup_list', store_id=store.id)

    return render(request, 'shopify_manager/backup/backup_delete_confirm.html', {
        'store': store,
        'backup': backup,
    })


@login_required
def restore_start(request, store_id, backup_id):
    """Wiederherstellung starten"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    if request.method == 'POST':
        mode = request.POST.get('mode', 'only_missing')
        item_types = request.POST.getlist('item_types')

        service = ShopifyRestoreService(store, backup, mode)

        if 'all' in item_types or not item_types:
            # Alles wiederherstellen
            results = service.restore_all()
        else:
            # Nur ausgewählte Kategorien
            results = {}
            for item_type in item_types:
                results[item_type] = service.restore_category(item_type)

        # Statistik erstellen
        success_count = sum(1 for logs in results.values() for log in logs if log.status == 'success')
        exists_count = sum(1 for logs in results.values() for log in logs if log.status == 'exists')
        failed_count = sum(1 for logs in results.values() for log in logs if log.status == 'failed')

        messages.success(
            request,
            f'Wiederherstellung abgeschlossen: {success_count} erfolgreich, '
            f'{exists_count} bereits vorhanden, {failed_count} fehlgeschlagen'
        )

        return redirect('shopify_manager:backup_detail', store_id=store.id, backup_id=backup.id)

    return render(request, 'shopify_manager/backup/restore_start.html', {
        'store': store,
        'backup': backup,
    })


@login_required
def restore_item(request, store_id, backup_id, item_id):
    """Einzelnes Element wiederherstellen"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)
    item = get_object_or_404(BackupItem, id=item_id, backup=backup)

    if request.method == 'POST':
        mode = request.POST.get('mode', 'only_missing')

        service = ShopifyRestoreService(store, backup, mode)
        log = service.restore_item(item)

        if log.status == 'success':
            messages.success(request, f'{item.title} erfolgreich wiederhergestellt')
        elif log.status == 'exists':
            messages.info(request, f'{item.title} existiert bereits')
        else:
            messages.error(request, f'Wiederherstellung fehlgeschlagen: {log.message}')

        return redirect('shopify_manager:backup_detail', store_id=store.id, backup_id=backup.id)

    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
@require_http_methods(['POST'])
def sync_item_from_shopify(request, store_id, backup_id, item_id):
    """Einzelnes Element vom aktuellen Shopify-Stand aktualisieren (Shopify → Backup)"""
    import requests
    import re

    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)
    item = get_object_or_404(BackupItem, id=item_id, backup=backup)

    base_url = store.get_api_url()
    headers = {
        'X-Shopify-Access-Token': store.access_token,
        'Content-Type': 'application/json'
    }

    try:
        # Je nach Typ den richtigen Endpunkt aufrufen
        if item.item_type == 'product':
            url = f"{base_url}/products/{item.shopify_id}.json"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json().get('product', {})
                item.title = data.get('title', item.title)
                item.raw_data = data
                if data.get('image'):
                    item.image_url = data['image'].get('src', '')
                item.save()
                messages.success(request, f'"{item.title}" wurde von Shopify aktualisiert')
            elif response.status_code == 404:
                messages.warning(request, f'"{item.title}" existiert nicht mehr auf Shopify')
            else:
                messages.error(request, f'Fehler beim Abrufen: {response.status_code}')

        elif item.item_type == 'blog_post':
            # Blog-Post benötigt die Blog-ID
            blog_id = item.parent_id
            if blog_id:
                url = f"{base_url}/blogs/{blog_id}/articles/{item.shopify_id}.json"
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json().get('article', {})
                    item.title = data.get('title', item.title)
                    item.raw_data = data
                    if data.get('image'):
                        item.image_url = data['image'].get('src', '')
                    item.save()
                    messages.success(request, f'"{item.title}" wurde von Shopify aktualisiert')
                elif response.status_code == 404:
                    messages.warning(request, f'"{item.title}" existiert nicht mehr auf Shopify')
                else:
                    messages.error(request, f'Fehler beim Abrufen: {response.status_code}')
            else:
                messages.error(request, 'Blog-ID nicht gefunden')

        elif item.item_type == 'blog':
            url = f"{base_url}/blogs/{item.shopify_id}.json"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json().get('blog', {})
                item.title = data.get('title', item.title)
                item.raw_data = data
                item.save()
                messages.success(request, f'"{item.title}" wurde von Shopify aktualisiert')
            elif response.status_code == 404:
                messages.warning(request, f'"{item.title}" existiert nicht mehr auf Shopify')
            else:
                messages.error(request, f'Fehler beim Abrufen: {response.status_code}')

        elif item.item_type == 'collection':
            # Erst Smart Collection versuchen, dann Custom Collection
            url = f"{base_url}/smart_collections/{item.shopify_id}.json"
            response = requests.get(url, headers=headers)
            if response.status_code == 404:
                url = f"{base_url}/custom_collections/{item.shopify_id}.json"
                response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                collection_data = data.get('smart_collection') or data.get('custom_collection', {})
                item.title = collection_data.get('title', item.title)
                item.raw_data = collection_data
                if collection_data.get('image'):
                    item.image_url = collection_data['image'].get('src', '')
                item.save()
                messages.success(request, f'"{item.title}" wurde von Shopify aktualisiert')
            elif response.status_code == 404:
                messages.warning(request, f'"{item.title}" existiert nicht mehr auf Shopify')
            else:
                messages.error(request, f'Fehler beim Abrufen: {response.status_code}')

        elif item.item_type == 'page':
            url = f"{base_url}/pages/{item.shopify_id}.json"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json().get('page', {})
                item.title = data.get('title', item.title)
                item.raw_data = data
                item.save()
                messages.success(request, f'"{item.title}" wurde von Shopify aktualisiert')
            elif response.status_code == 404:
                messages.warning(request, f'"{item.title}" existiert nicht mehr auf Shopify')
            else:
                messages.error(request, f'Fehler beim Abrufen: {response.status_code}')

        elif item.item_type == 'redirect':
            url = f"{base_url}/redirects/{item.shopify_id}.json"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json().get('redirect', {})
                item.title = f"{data.get('path', '')} → {data.get('target', '')}"
                item.raw_data = data
                item.save()
                messages.success(request, f'Weiterleitung wurde von Shopify aktualisiert')
            elif response.status_code == 404:
                messages.warning(request, f'Weiterleitung existiert nicht mehr auf Shopify')
            else:
                messages.error(request, f'Fehler beim Abrufen: {response.status_code}')

        else:
            messages.warning(request, f'Typ "{item.item_type}" wird noch nicht unterstützt')

    except Exception as e:
        messages.error(request, f'Fehler: {str(e)}')

    # Redirect zurück zur Compare-Seite
    return redirect('shopify_manager:backup_compare', store_id=store.id, backup_id=backup.id)


@login_required
@require_http_methods(['GET'])
def api_backup_status(request, store_id, backup_id):
    """API: Backup-Status abfragen (mit automatischer Stale-Erkennung)"""
    from django.utils import timezone
    from datetime import timedelta

    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)

    # Stale-Backup-Erkennung: Wenn "running" aber seit 3 Minuten kein Update
    if backup.status == 'running':
        stale_threshold = timezone.now() - timedelta(minutes=3)
        if backup.updated_at < stale_threshold:
            # Automatisch pausieren - Backup ist hängen geblieben
            backup.status = 'paused'
            backup.progress_message = 'Automatisch pausiert: Keine Aktivität. Klicken Sie auf Weiter laden.'
            backup.save(update_fields=['status', 'progress_message', 'updated_at'])

    return JsonResponse({
        'status': backup.status,
        'current_step': backup.current_step,
        'progress_message': backup.progress_message,
        'products_count': backup.products_count,
        'blogs_count': backup.blogs_count,
        'posts_count': backup.posts_count,
        'collections_count': backup.collections_count,
        'pages_count': backup.pages_count,
        'menus_count': backup.menus_count,
        'redirects_count': backup.redirects_count,
        'orders_count': backup.orders_count,
        'customers_count': backup.customers_count,
        'total_items': backup.total_items_count,
        'size': backup.get_size_display(),
        'error_message': backup.error_message if backup.status == 'failed' else None,
    })


@login_required
@require_http_methods(['GET'])
def api_backup_item_detail(request, store_id, backup_id, item_id):
    """API: Backup-Item Details abrufen"""
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    backup = get_object_or_404(ShopifyBackup, id=backup_id, store=store)
    item = get_object_or_404(BackupItem, id=item_id, backup=backup)

    # Basis-Daten
    data = {
        'id': item.id,
        'title': item.title,
        'item_type': item.item_type,
        'item_type_display': item.get_item_type_display(),
        'shopify_id': item.shopify_id,
        'created_at': item.created_at.strftime('%d.%m.%Y %H:%M'),
        'image_url': item.image_url,
        'has_image_data': bool(item.image_data),
    }

    # Raw-Daten (ohne Bilder-Binärdaten)
    if item.raw_data:
        raw = item.raw_data.copy() if isinstance(item.raw_data, dict) else {}

        # Formatierte Felder für bessere Anzeige
        if item.item_type == 'product':
            data['details'] = {
                'Titel': raw.get('title', ''),
                'Handle': raw.get('handle', ''),
                'Vendor': raw.get('vendor', ''),
                'Produkttyp': raw.get('product_type', ''),
                'Status': raw.get('status', ''),
                'Tags': raw.get('tags', ''),
                'Beschreibung': raw.get('body_html', '')[:500] + '...' if len(raw.get('body_html', '')) > 500 else raw.get('body_html', ''),
                'Varianten': len(raw.get('variants', [])),
                'Bilder': len(raw.get('images', [])),
            }
        elif item.item_type == 'blog_post':
            data['details'] = {
                'Titel': raw.get('title', ''),
                'Handle': raw.get('handle', ''),
                'Autor': raw.get('author', ''),
                'Tags': raw.get('tags', ''),
                'Veröffentlicht': 'Ja' if raw.get('published') else 'Nein',
                'Zusammenfassung': raw.get('summary_html', '')[:300] if raw.get('summary_html') else '',
                'Inhalt': raw.get('body_html', '')[:500] + '...' if len(raw.get('body_html', '')) > 500 else raw.get('body_html', ''),
            }
        elif item.item_type == 'blog':
            data['details'] = {
                'Titel': raw.get('title', ''),
                'Handle': raw.get('handle', ''),
            }
        elif item.item_type == 'collection':
            data['details'] = {
                'Titel': raw.get('title', ''),
                'Handle': raw.get('handle', ''),
                'Typ': raw.get('collection_type', 'custom'),
                'Veröffentlicht': 'Ja' if raw.get('published') else 'Nein',
                'Beschreibung': raw.get('body_html', '')[:500] if raw.get('body_html') else '',
            }
        elif item.item_type == 'page':
            data['details'] = {
                'Titel': raw.get('title', ''),
                'Handle': raw.get('handle', ''),
                'Veröffentlicht': 'Ja' if raw.get('published') else 'Nein',
                'Inhalt': raw.get('body_html', '')[:500] + '...' if len(raw.get('body_html', '')) > 500 else raw.get('body_html', ''),
            }
        elif item.item_type == 'redirect':
            data['details'] = {
                'Von': raw.get('path', ''),
                'Nach': raw.get('target', ''),
            }
        elif item.item_type == 'menu':
            data['details'] = {
                'Titel': raw.get('title', ''),
                'Handle': raw.get('handle', ''),
                'Einträge': len(raw.get('items', [])),
            }
        elif item.item_type == 'order':
            data['details'] = {
                'Bestellnummer': raw.get('order_number', raw.get('name', '')),
                'Status': raw.get('financial_status', ''),
                'Fulfillment': raw.get('fulfillment_status', 'unfulfilled'),
                'Summe': raw.get('total_price', ''),
                'Währung': raw.get('currency', 'EUR'),
                'Kunde': raw.get('customer', {}).get('email', '') if raw.get('customer') else '',
            }
        elif item.item_type == 'customer':
            data['details'] = {
                'E-Mail': raw.get('email', ''),
                'Name': f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip(),
                'Bestellungen': raw.get('orders_count', 0),
                'Ausgegeben': raw.get('total_spent', ''),
            }
        else:
            data['details'] = raw

        # Voller HTML-Inhalt separat (für Produkte und Blog-Posts)
        if item.item_type in ('product', 'blog_post', 'page', 'collection'):
            data['full_html'] = raw.get('body_html', '')

    return JsonResponse(data)
