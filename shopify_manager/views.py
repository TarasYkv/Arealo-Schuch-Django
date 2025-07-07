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

from .models import ShopifyStore, ShopifyProduct, ShopifySyncLog, ProductSEOOptimization, SEOAnalysisResult, ShopifyBlog, ShopifyBlogPost, BlogPostSEOOptimization
from .ai_seo_service import generate_seo_with_ai, BlogPostSEOService
from .forms import (
    ShopifyStoreForm, ShopifyProductEditForm, ProductFilterForm, 
    BulkActionForm, ProductImportForm, SEOOptimizationForm, BlogPostSEOOptimizationForm, BlogPostFilterForm
)
from .shopify_api import ShopifyAPIClient, ShopifyProductSync, ShopifyBlogSync


class ShopifyStoreListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Stores des Benutzers"""
    model = ShopifyStore
    template_name = 'shopify_manager/store_list.html'
    context_object_name = 'stores'
    
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
    paginate_by = 20
    
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
        
        return queryset.select_related('store')
    
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
        
        messages.success(self.request, 'Produkt erfolgreich aktualisiert. Synchronisation erforderlich.')
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
    """Importiert Produkte von Shopify"""
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
    
    limit = form.cleaned_data.get('limit', 50)  # Standardwert falls nicht gesetzt
    import_mode = form.cleaned_data['import_mode']
    overwrite_existing = form.cleaned_data['overwrite_existing']
    import_images = form.cleaned_data['import_images']
    
    # Bei "Alle Produkte" ist das Limit irrelevant
    if import_mode == 'all':
        limit = None  # Wird in der _fetch_all_products Methode ignoriert
    
    try:
        sync = ShopifyProductSync(store)
        log = sync.import_products(
            limit=limit,
            import_mode=import_mode,
            overwrite_existing=overwrite_existing,
            import_images=import_images
        )
        
        if log.status == 'success':
            message = f'{log.products_success} Produkte erfolgreich importiert'
            if import_mode == 'all' and overwrite_existing:
                message += ' (alle lokalen Produkte wurden überschrieben)'
        elif log.status == 'partial':
            message = f'{log.products_success} Produkte importiert, {log.products_failed} Fehler aufgetreten'
            if import_mode == 'all' and overwrite_existing:
                message += ' (alle lokalen Produkte wurden überschrieben)'
        else:
            message = f'Import fehlgeschlagen: {log.error_message}'
        
        # Zusätzliche Details für Debugging
        details = {
            'import_mode': import_mode,
            'limit_used': limit if import_mode != 'all' else 'alle',
            'products_processed': log.products_processed,
            'overwrite_existing': overwrite_existing,
            'import_images': import_images
        }
        
        return JsonResponse({
            'success': log.status in ['success', 'partial'],
            'message': message,
            'products_imported': log.products_success,
            'products_failed': log.products_failed,
            'details': details,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
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
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
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
            product_title=seo_optimization.original_title,
            product_description=seo_optimization.original_description,
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
def alt_text_manager_view(request):
    """Alt-Text Manager für alle Bildtypen"""
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
    
    if not all([store_id, product_id, image_id]):
        return JsonResponse({
            'success': False,
            'error': 'Fehlende Parameter'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        # Shopify API Call zum Aktualisieren des Alt-Textes
        api_client = ShopifyAPIClient(store)
        
        # Hole das aktuelle Produkt
        success, product, message = api_client.fetch_product(product_id)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': f'Produkt nicht gefunden: {message}'
            })
        
        # Finde das entsprechende Bild und aktualisiere den Alt-Text
        images = product.get('images', [])
        updated_images = []
        image_found = False
        
        for image in images:
            if str(image.get('id')) == str(image_id):
                image['alt'] = alt_text
                image_found = True
            updated_images.append(image)
        
        if not image_found:
            return JsonResponse({
                'success': False,
                'error': 'Bild nicht gefunden'
            })
        
        # Aktualisiere die Bilder in Shopify
        success, updated_product, message = api_client.update_product_images(product_id, updated_images)
        
        if success:
            # Aktualisiere auch die lokale Datenbank
            try:
                local_product = ShopifyProduct.objects.get(
                    shopify_id=product_id, 
                    store=store
                )
                
                # Update raw_shopify_data
                if hasattr(local_product, 'raw_shopify_data') and local_product.raw_shopify_data:
                    local_product.raw_shopify_data = updated_product
                    local_product.save(update_fields=['raw_shopify_data'])
                
            except ShopifyProduct.DoesNotExist:
                # Produkt nicht in lokaler DB - ignorieren
                pass
            
            return JsonResponse({
                'success': True,
                'message': 'Alt-Text erfolgreich aktualisiert'
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
def generate_alt_text_view(request):
    """Generiert Alt-Text für ein Bild mittels KI"""
    image_url = request.POST.get('image_url')
    product_id = request.POST.get('product_id')
    
    if not image_url:
        return JsonResponse({
            'success': False,
            'error': 'Bild-URL fehlt'
        })
    
    try:
        # Hier würde normalerweise eine KI-basierte Bilderkennung stattfinden
        # Für jetzt verwenden wir eine einfache Fallback-Lösung
        
        # Hole Produktinformationen für Kontext
        if product_id:
            try:
                # Versuche lokales Produkt zu finden für Kontext
                local_product = ShopifyProduct.objects.filter(
                    shopify_id=product_id,
                    store__user=request.user
                ).first()
                
                if local_product:
                    # Generiere Alt-Text basierend auf Produkttitel
                    product_title = local_product.title
                    product_type = local_product.product_type or "Produkt"
                    vendor = local_product.vendor or ""
                    
                    # Einfache Alt-Text Generierung basierend auf Produktdaten
                    alt_text_parts = []
                    
                    if vendor:
                        alt_text_parts.append(vendor)
                    
                    alt_text_parts.append(product_title[:50])  # Titel begrenzen
                    
                    if product_type and product_type.lower() not in product_title.lower():
                        alt_text_parts.append(product_type)
                    
                    generated_alt_text = " - ".join(alt_text_parts)
                    
                    # Auf 125 Zeichen begrenzen
                    if len(generated_alt_text) > 125:
                        generated_alt_text = generated_alt_text[:122] + "..."
                    
                else:
                    generated_alt_text = "Produktbild"
                    
            except Exception:
                generated_alt_text = "Produktbild"
        else:
            generated_alt_text = "Bild"
        
        return JsonResponse({
            'success': True,
            'alt_text': generated_alt_text
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der Alt-Text Generierung: {str(e)}'
        })


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
    paginate_by = 20
    
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
        
        context['filter_form'] = filter_form
        
        paginator = Paginator(posts, 10)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        
        # Statistiken für diesen Blog
        context['stats'] = {
            'total_posts': self.object.posts.count(),
            'published_posts': self.object.posts.filter(status='published').count(),
            'draft_posts': self.object.posts.filter(status='draft').count(),
        }
        
        return context


class ShopifyBlogPostListView(LoginRequiredMixin, ListView):
    """Liste aller Shopify Blog-Posts"""
    model = ShopifyBlogPost
    template_name = 'shopify_manager/blog_post_list.html'
    context_object_name = 'posts'
    paginate_by = 20
    
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
        
        blog_id = self.request.GET.get('blog')
        if blog_id:
            queryset = queryset.filter(blog_id=blog_id)
        
        # Sortierung
        sort = self.request.GET.get('sort', '-published_at')
        if sort:
            queryset = queryset.order_by(sort)
        
        return queryset.select_related('blog')
    
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


@login_required
@require_http_methods(["POST"])
def import_blog_posts_view(request):
    """Importiert Blog-Posts für einen bestimmten Blog"""
    blog_id = request.POST.get('blog_id')
    import_mode = request.POST.get('import_mode', 'new_only')  # new_only oder all
    
    if not blog_id:
        return JsonResponse({
            'success': False,
            'error': 'Blog-ID fehlt'
        })
    
    blog = get_object_or_404(ShopifyBlog, id=blog_id, store__user=request.user)
    
    try:
        blog_sync = ShopifyBlogSync(blog.store)
        log = blog_sync.import_blog_posts(blog, import_mode=import_mode)
        
        message = f'{log.products_success} Blog-Posts importiert'
        if import_mode == 'all':
            message += ' (alle lokalen Blog-Posts wurden überschrieben)'
        
        return JsonResponse({
            'success': log.status in ['success', 'partial'],
            'message': message,
            'imported': log.products_success,
            'failed': log.products_failed,
            'status': log.status,
            'import_mode': import_mode
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Blog-Post-Import: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def update_blog_alt_text_view(request):
    """Aktualisiert den Alt-Text eines Blog-Post Bildes"""
    store_id = request.POST.get('store_id')
    blog_post_id = request.POST.get('blog_post_id')
    alt_text = request.POST.get('alt_text', '').strip()
    
    if not all([store_id, blog_post_id]):
        return JsonResponse({
            'success': False,
            'error': 'Fehlende Parameter'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    blog_post = get_object_or_404(ShopifyBlogPost, shopify_id=blog_post_id, blog__store=store)
    
    try:
        # Update des lokalen Blog-Posts
        blog_post.featured_image_alt = alt_text
        blog_post.save(update_fields=['featured_image_alt'])
        
        # TODO: Shopify API Update für Blog-Posts
        # Hier würde normalerweise der Shopify API Call für Blog-Post Updates stehen
        # Shopify API für Blog-Posts ist komplexer und erfordert separate Implementierung
        
        return JsonResponse({
            'success': True,
            'message': 'Alt-Text erfolgreich aktualisiert (lokal gespeichert)'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Aktualisieren des Blog Alt-Textes: {str(e)}'
        })


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
    """Importiert alle Blog-Posts für alle Blogs eines Stores"""
    store_id = request.POST.get('store_id')
    
    if not store_id:
        return JsonResponse({
            'success': False,
            'error': 'Store-ID fehlt'
        })
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    try:
        # Hole alle Blogs für diesen Store
        blogs = ShopifyBlog.objects.filter(store=store)
        
        if not blogs.exists():
            return JsonResponse({
                'success': False,
                'error': 'Keine Blogs gefunden. Bitte importieren Sie zuerst Blogs für diesen Store.'
            })
        
        blog_sync = ShopifyBlogSync(store)
        total_imported = 0
        total_failed = 0
        
        # Importiere Posts für jeden Blog
        for blog in blogs:
            log = blog_sync.import_blog_posts(blog)
            total_imported += log.products_success
            total_failed += log.products_failed
        
        return JsonResponse({
            'success': True,
            'message': f'{total_imported} Blog-Posts aus {blogs.count()} Blogs importiert',
            'imported': total_imported,
            'failed': total_failed,
            'blogs_processed': blogs.count()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Import aller Blog-Posts: {str(e)}'
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
        
        # Bereite Blog-Post Daten für Shopify vor
        blog_post_data = {
            'title': blog_post.title,
            'body_html': blog_post.content,
            'summary': blog_post.summary,
            'author': blog_post.author,
            'tags': blog_post.tags,
            'published_at': blog_post.published_at.isoformat() if blog_post.published_at else None,
            'seo_title': blog_post.seo_title,
            'seo_description': blog_post.seo_description,
            'featured_image': {
                'url': blog_post.featured_image_url,
                'alt': blog_post.featured_image_alt
            } if blog_post.featured_image_url else None
        }
        
        # Synchronisiere zu Shopify
        success, updated_post, message = api_client.update_blog_post(
            blog_post.blog.shopify_id, 
            blog_post.shopify_id, 
            blog_post_data
        )
        
        if success:
            # Aktualisiere lokale Daten falls nötig
            blog_post.shopify_updated_at = timezone.now()
            blog_post.save(update_fields=['shopify_updated_at'])
            
            return JsonResponse({
                'success': True,
                'message': f'Blog-Post "{blog_post.title}" erfolgreich synchronisiert'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Fehler beim Synchronisieren: {message}'
            })
        
    except Exception as e:
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
    products = ShopifyProduct.objects.filter(store__user=request.user).select_related('store')
    blog_posts = ShopifyBlogPost.objects.filter(blog__store__user=request.user).select_related('blog__store')
    
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
            # Claude (Anthropic) Modelle - Empfohlen
            ('claude-opus-4', 'Claude Opus 4 (Höchste Qualität)'),
            ('claude-sonnet-4', 'Claude Sonnet 4 (Ausgezeichnet)'),
            ('claude-sonnet-3.7', 'Claude Sonnet 3.7 (Extended Reasoning)'),
            ('claude-sonnet-3.5-new', 'Claude Sonnet 3.5 (Aktualisiert)'),
            ('claude-sonnet-3.5', 'Claude Sonnet 3.5 (Bewährt)'),
            ('claude-haiku-3.5-new', 'Claude Haiku 3.5 (Schnell, neu)'),
            ('claude-haiku-3.5', 'Claude Haiku 3.5 (Schnell)'),
            
            # OpenAI (ChatGPT) Modelle - Standard
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
            
            # Google Gemini Modelle
            ('gemini-2.5-pro', 'Gemini 2.5 Pro (Höchste Performance)'),
            ('gemini-2.5-flash', 'Gemini 2.5 Flash (Bestes Preis-Leistung)'),
            ('gemini-2.0-flash', 'Gemini 2.0 Flash (Verfügbar)'),
            ('gemini-2.0-pro', 'Gemini 2.0 Pro (Beste Coding Performance)'),
            ('gemini-1.5-flash', 'Gemini 1.5 Flash (Bewährt, schnell)'),
            ('gemini-1.5-pro', 'Gemini 1.5 Pro (Kraftvoll)'),
            ('gemini', 'Gemini (Kostenlos)'),
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
                product_title=title,
                product_description=description,
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
        
        if not title and not description and not seo_title and not seo_description:
            return JsonResponse({
                'success': False,
                'error': 'Mindestens ein Feld muss ausgefüllt sein'
            })
        
        # Wende Änderungen an
        if content_type == 'product':
            try:
                content_object = ShopifyProduct.objects.get(
                    Q(id=content_id) | Q(shopify_id=str(content_id)),
                    store__user=request.user
                )
                
                # Hauptfelder aktualisieren
                if title:
                    content_object.title = title
                if description:
                    content_object.body_html = description
                
                # SEO-Felder aktualisieren
                if seo_title:
                    content_object.seo_title = seo_title
                if seo_description:
                    content_object.seo_description = seo_description
                
                content_object.needs_sync = True
                content_object.save()
                
                updated_fields = []
                if title: updated_fields.append("Titel")
                if description: updated_fields.append("Beschreibung")
                if seo_title: updated_fields.append("SEO-Titel")
                if seo_description: updated_fields.append("SEO-Beschreibung")
                
                message = f'Produkt "{content_object.title}" erfolgreich aktualisiert'
                if updated_fields:
                    message += f': {", ".join(updated_fields)}'
                
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
                
                # Hauptfelder aktualisieren
                if title:
                    content_object.title = title
                if description:
                    content_object.content = description
                
                # SEO-Felder aktualisieren
                if seo_title:
                    content_object.seo_title = seo_title
                if seo_description:
                    content_object.seo_description = seo_description
                
                content_object.save()
                
                updated_fields = []
                if title: updated_fields.append("Titel")
                if description: updated_fields.append("Inhalt")
                if seo_title: updated_fields.append("SEO-Titel")
                if seo_description: updated_fields.append("SEO-Beschreibung")
                
                message = f'Blog-Post "{content_object.title}" erfolgreich aktualisiert'
                if updated_fields:
                    message += f': {", ".join(updated_fields)}'
                
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