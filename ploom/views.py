import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.utils import timezone

from .models import (
    PLoomSettings, ProductTheme, PLoomProduct,
    PLoomProductImage, PLoomProductVariant, PLoomHistory, PLoomFavoritePrice
)
from .forms import (
    PLoomSettingsForm, ProductThemeForm, PLoomProductForm,
    PLoomProductVariantForm, ImageUploadForm
)

logger = logging.getLogger(__name__)


# ============================================================================
# Dashboard & Einstellungen
# ============================================================================

@login_required
def dashboard(request):
    """P-Loom Dashboard"""
    products = PLoomProduct.objects.filter(user=request.user)
    themes = ProductTheme.objects.filter(user=request.user)

    # Statistiken
    stats = {
        'total_products': products.count(),
        'draft_products': products.filter(status='draft').count(),
        'ready_products': products.filter(status='ready').count(),
        'uploaded_products': products.filter(status='uploaded').count(),
        'total_themes': themes.count(),
    }

    # Letzte Produkte
    recent_products = products.order_by('-created_at')[:5]

    context = {
        'stats': stats,
        'recent_products': recent_products,
        'themes': themes,
    }
    return render(request, 'ploom/dashboard.html', context)


@login_required
def settings_view(request):
    """P-Loom Einstellungen"""
    settings_obj, created = PLoomSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = PLoomSettingsForm(request.POST, instance=settings_obj, user=request.user)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Einstellungen gespeichert'})
        return JsonResponse({'success': False, 'errors': form.errors})

    form = PLoomSettingsForm(instance=settings_obj, user=request.user)
    return render(request, 'ploom/settings.html', {'form': form})


# ============================================================================
# Themes
# ============================================================================

@login_required
def theme_list(request):
    """Liste aller Themes"""
    themes = ProductTheme.objects.filter(user=request.user)
    return render(request, 'ploom/theme_list.html', {'themes': themes})


@login_required
def theme_create(request):
    """Neues Theme erstellen"""
    if request.method == 'POST':
        form = ProductThemeForm(request.POST)
        if form.is_valid():
            theme = form.save(commit=False)
            theme.user = request.user
            theme.save()
            return redirect('ploom:theme_list')
    else:
        form = ProductThemeForm()

    return render(request, 'ploom/theme_form.html', {'form': form, 'is_new': True})


@login_required
def theme_edit(request, theme_id):
    """Theme bearbeiten"""
    theme = get_object_or_404(ProductTheme, pk=theme_id, user=request.user)

    if request.method == 'POST':
        form = ProductThemeForm(request.POST, instance=theme)
        if form.is_valid():
            form.save()
            return redirect('ploom:theme_list')
    else:
        form = ProductThemeForm(instance=theme)

    return render(request, 'ploom/theme_form.html', {'form': form, 'theme': theme, 'is_new': False})


@login_required
def theme_delete(request, theme_id):
    """Theme löschen"""
    theme = get_object_or_404(ProductTheme, pk=theme_id, user=request.user)
    if request.method == 'POST':
        theme.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'POST required'})


# ============================================================================
# Produkte
# ============================================================================

@login_required
def product_list(request):
    """Liste aller Produkte"""
    products = PLoomProduct.objects.filter(user=request.user)

    # Filter
    status = request.GET.get('status')
    if status:
        products = products.filter(status=status)

    search = request.GET.get('search')
    if search:
        products = products.filter(
            Q(title__icontains=search) |
            Q(tags__icontains=search) |
            Q(vendor__icontains=search)
        )

    # Sortierung
    sort = request.GET.get('sort', '-created_at')
    products = products.order_by(sort)

    # Pagination
    paginator = Paginator(products, 12)
    page = request.GET.get('page', 1)
    products = paginator.get_page(page)

    context = {
        'products': products,
        'status_filter': status,
        'search_query': search,
    }
    return render(request, 'ploom/product_list.html', context)


@login_required
def product_create(request):
    """Neues Produkt erstellen"""
    if request.method == 'POST':
        form = PLoomProductForm(request.POST, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()

            # Preis zum Verlauf hinzufügen wenn gesetzt
            if product.price:
                _save_price_to_history(request.user, product.price)

            return redirect('ploom:product_edit', product_id=product.id)
    else:
        # Standard-Werte aus Theme laden
        initial = {}
        default_theme = ProductTheme.objects.filter(user=request.user, is_default=True).first()
        if default_theme:
            initial['theme'] = default_theme
            initial['price'] = default_theme.default_price
            initial['compare_at_price'] = default_theme.default_compare_at_price
            initial['vendor'] = default_theme.default_vendor
            initial['product_type'] = default_theme.default_product_type
            initial['tags'] = default_theme.default_tags

        # Standard-Store laden
        settings_obj = PLoomSettings.objects.filter(user=request.user).first()
        if settings_obj and settings_obj.default_store:
            initial['shopify_store'] = settings_obj.default_store

        form = PLoomProductForm(initial=initial, user=request.user)

    themes = ProductTheme.objects.filter(user=request.user)
    return render(request, 'ploom/product_create.html', {
        'form': form,
        'themes': themes,
        'is_new': True
    })


@login_required
def product_edit(request, product_id):
    """Produkt bearbeiten"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    if request.method == 'POST':
        form = PLoomProductForm(request.POST, instance=product, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)

            # Metafelder verarbeiten
            metafields_json = request.POST.get('product_metafields_json', '{}')
            try:
                product.product_metafields = json.loads(metafields_json) if metafields_json else {}
            except json.JSONDecodeError:
                product.product_metafields = {}

            product.save()

            # Preis zum Verlauf hinzufügen wenn geändert
            if product.price:
                _save_price_to_history(request.user, product.price)

            # Metafeld-Werte zum Verlauf hinzufügen
            if product.product_metafields:
                _save_metafields_to_history(request.user, product.product_metafields)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Produkt gespeichert'})
            # Auf der gleichen Seite bleiben mit Erfolgsmeldung
            messages.success(request, 'Produkt erfolgreich gespeichert!')
            return redirect('ploom:product_edit', product_id=product.id)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = PLoomProductForm(instance=product, user=request.user)

    # Varianten und Bilder
    variants = product.variants.all()
    images = product.images.all()
    themes = ProductTheme.objects.filter(user=request.user)

    context = {
        'form': form,
        'product': product,
        'variants': variants,
        'images': images,
        'themes': themes,
        'is_new': False,
    }
    return render(request, 'ploom/product_create.html', context)


@login_required
def product_delete(request, product_id):
    """Produkt löschen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    if request.method == 'POST':
        product.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
@require_POST
def api_products_bulk_delete(request):
    """Mehrere Produkte gleichzeitig löschen"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    product_ids = data.get('product_ids', [])

    if not product_ids:
        return JsonResponse({'success': False, 'error': 'Keine Produkte ausgewählt'})

    # Nur Produkte des aktuellen Benutzers löschen
    deleted_count, _ = PLoomProduct.objects.filter(
        pk__in=product_ids,
        user=request.user
    ).delete()

    return JsonResponse({
        'success': True,
        'deleted_count': deleted_count,
        'message': f'{deleted_count} Produkt(e) gelöscht'
    })


@login_required
def product_duplicate(request, product_id):
    """Produkt duplizieren"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    # Kopie erstellen
    new_product = PLoomProduct.objects.create(
        user=request.user,
        theme=product.theme,
        title=f"{product.title} (Kopie)",
        description=product.description,
        vendor=product.vendor,
        product_type=product.product_type,
        tags=product.tags,
        seo_title=product.seo_title,
        seo_description=product.seo_description,
        price=product.price,
        compare_at_price=product.compare_at_price,
        product_metafields=product.product_metafields,
        category_metafields=product.category_metafields,
        collection_id=product.collection_id,
        collection_name=product.collection_name,
        shopify_store=product.shopify_store,
    )

    # Varianten kopieren
    for variant in product.variants.all():
        PLoomProductVariant.objects.create(
            product=new_product,
            title=variant.title,
            sku=variant.sku,
            price=variant.price,
            compare_at_price=variant.compare_at_price,
            option1_name=variant.option1_name,
            option1_value=variant.option1_value,
            option2_name=variant.option2_name,
            option2_value=variant.option2_value,
            option3_name=variant.option3_name,
            option3_value=variant.option3_value,
            barcode=variant.barcode,
            inventory_quantity=variant.inventory_quantity,
            inventory_policy=variant.inventory_policy,
            weight=variant.weight,
            weight_unit=variant.weight_unit,
            requires_shipping=variant.requires_shipping,
            taxable=variant.taxable,
            position=variant.position,
        )

    # Bilder kopieren (nur Referenzen, nicht die Dateien)
    for image in product.images.all():
        PLoomProductImage.objects.create(
            product=new_product,
            source=image.source,
            imageforge_generation=image.imageforge_generation,
            imageforge_mockup=image.imageforge_mockup,
            image=image.image,
            alt_text=image.alt_text,
            position=image.position,
            is_featured=image.is_featured,
        )

    return redirect('ploom:product_edit', product_id=new_product.id)


# ============================================================================
# Varianten API
# ============================================================================

@login_required
@require_POST
def api_variant_add(request, product_id):
    """Variante hinzufügen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST

    variant = PLoomProductVariant.objects.create(
        product=product,
        title=data.get('title', ''),
        sku=data.get('sku', ''),
        price=data.get('price') or product.price,
        compare_at_price=data.get('compare_at_price') or product.compare_at_price,
        option1_name=data.get('option1_name', ''),
        option1_value=data.get('option1_value', ''),
        option2_name=data.get('option2_name', ''),
        option2_value=data.get('option2_value', ''),
        option3_name=data.get('option3_name', ''),
        option3_value=data.get('option3_value', ''),
        inventory_quantity=data.get('inventory_quantity', 0),
        barcode=data.get('barcode', ''),
        weight=data.get('weight'),
        weight_unit=data.get('weight_unit', 'kg'),
        cost=data.get('cost'),
        position=product.variants.count(),
    )

    return JsonResponse({
        'success': True,
        'variant': {
            'id': variant.pk,
            'title': str(variant),
            'sku': variant.sku,
            'price': str(variant.price) if variant.price else None,
        }
    })


@login_required
@require_POST
def api_variant_update(request, product_id, variant_id):
    """Variante aktualisieren"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    variant = get_object_or_404(PLoomProductVariant, pk=variant_id, product=product)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST

    for field in ['title', 'sku', 'price', 'compare_at_price',
                  'option1_name', 'option1_value', 'option2_name', 'option2_value',
                  'option3_name', 'option3_value', 'barcode', 'inventory_quantity',
                  'inventory_policy', 'weight', 'weight_unit', 'requires_shipping', 'taxable', 'cost']:
        if field in data:
            setattr(variant, field, data[field])

    variant.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_variant_delete(request, product_id, variant_id):
    """Variante löschen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    variant = get_object_or_404(PLoomProductVariant, pk=variant_id, product=product)
    variant.delete()
    return JsonResponse({'success': True})


@login_required
def api_variant_get(request, product_id, variant_id):
    """Variante abrufen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    variant = get_object_or_404(PLoomProductVariant, pk=variant_id, product=product)

    return JsonResponse({
        'success': True,
        'variant': {
            'id': variant.id,
            'title': variant.title or '',
            'sku': variant.sku or '',
            'price': str(variant.price) if variant.price else '',
            'compare_at_price': str(variant.compare_at_price) if variant.compare_at_price else '',
            'option1_name': variant.option1_name or '',
            'option1_value': variant.option1_value or '',
            'option2_name': variant.option2_name or '',
            'option2_value': variant.option2_value or '',
            'option3_name': variant.option3_name or '',
            'option3_value': variant.option3_value or '',
            'barcode': variant.barcode or '',
            'inventory_quantity': variant.inventory_quantity,
            'weight': str(variant.weight) if variant.weight else '',
            'weight_unit': variant.weight_unit or 'kg',
            'cost': str(variant.cost) if variant.cost else '',
        }
    })


# ============================================================================
# Bilder API
# ============================================================================

@login_required
@require_POST
def api_image_upload(request, product_id):
    """Bild hochladen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    if 'image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Kein Bild hochgeladen'})

    image_file = request.FILES['image']
    alt_text = request.POST.get('alt_text', '')
    filename = request.POST.get('filename', '')

    image = PLoomProductImage.objects.create(
        product=product,
        source='upload',
        image=image_file,
        alt_text=alt_text,
        filename=filename,
        position=product.images.count(),
        is_featured=not product.images.exists(),  # Erstes Bild ist Hauptbild
    )

    return JsonResponse({
        'success': True,
        'image': {
            'id': image.pk,
            'url': image.image_url,
            'filename': image.filename,
            'alt_text': image.alt_text,
            'is_featured': image.is_featured,
        }
    })


@login_required
@require_POST
def api_image_reorder(request, product_id):
    """Bildreihenfolge ändern"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    try:
        data = json.loads(request.body)
        order = data.get('order', [])
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    for position, image_id in enumerate(order):
        PLoomProductImage.objects.filter(
            pk=image_id,
            product=product
        ).update(position=position)

    return JsonResponse({'success': True})


@login_required
@require_POST
def api_image_delete(request, product_id, image_id):
    """Bild löschen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    image = get_object_or_404(PLoomProductImage, pk=image_id, product=product)

    was_featured = image.is_featured
    image.delete()

    # Wenn Hauptbild gelöscht wurde, nächstes Bild zum Hauptbild machen
    if was_featured:
        next_image = product.images.first()
        if next_image:
            next_image.is_featured = True
            next_image.save()

    return JsonResponse({'success': True})


@login_required
@require_POST
def api_image_set_featured(request, product_id, image_id):
    """Bild als Hauptbild setzen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    image = get_object_or_404(PLoomProductImage, pk=image_id, product=product)

    # Alle anderen Bilder: is_featured = False
    product.images.update(is_featured=False)
    image.is_featured = True
    image.save()

    return JsonResponse({'success': True})


@login_required
def api_imageforge_generations(request):
    """ImageForge Generierungen abrufen mit Paginierung"""
    try:
        from imageforge.models import ImageGeneration

        page = int(request.GET.get('page', 1))
        per_page = 12

        generations = ImageGeneration.objects.filter(
            user=request.user,
            generated_image__isnull=False
        ).order_by('-created_at')

        total_count = generations.count()
        total_pages = (total_count + per_page - 1) // per_page

        start = (page - 1) * per_page
        end = start + per_page
        generations = generations[start:end]

        items = [{
            'id': gen.id,
            'url': gen.generated_image.url if gen.generated_image else None,
            'prompt': gen.generation_prompt[:50] if gen.generation_prompt else '',
            'created_at': gen.created_at.isoformat(),
        } for gen in generations if gen.generated_image]

        return JsonResponse({
            'success': True,
            'items': items,
            'page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'has_prev': page > 1,
            'has_next': page < total_pages,
        })
    except ImportError:
        return JsonResponse({'success': False, 'error': 'ImageForge nicht installiert'})


@login_required
def api_imageforge_mockups(request):
    """ImageForge Mockups abrufen mit Paginierung"""
    try:
        from imageforge.models import ProductMockup

        page = int(request.GET.get('page', 1))
        per_page = 12

        mockups = ProductMockup.objects.filter(
            user=request.user,
            mockup_image__isnull=False
        ).order_by('-created_at')

        total_count = mockups.count()
        total_pages = (total_count + per_page - 1) // per_page

        start = (page - 1) * per_page
        end = start + per_page
        mockups = mockups[start:end]

        items = [{
            'id': mockup.id,
            'url': mockup.mockup_image.url if mockup.mockup_image else None,
            'name': mockup.name or 'Mockup',
            'created_at': mockup.created_at.isoformat(),
        } for mockup in mockups if mockup.mockup_image]

        return JsonResponse({
            'success': True,
            'items': items,
            'page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'has_prev': page > 1,
            'has_next': page < total_pages,
        })
    except ImportError:
        return JsonResponse({'success': False, 'error': 'ImageForge nicht installiert'})


@login_required
@require_POST
def api_image_from_imageforge(request, product_id):
    """Bild aus ImageForge hinzufügen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    source_type = data.get('source_type')  # 'generation' oder 'mockup'
    source_id = data.get('source_id')
    filename = data.get('filename', '').strip()

    if source_type == 'generation':
        from imageforge.models import ImageGeneration
        source = get_object_or_404(ImageGeneration, pk=source_id, user=request.user)
        image = PLoomProductImage.objects.create(
            product=product,
            source='imageforge_generation',
            imageforge_generation=source,
            filename=filename,
            alt_text=data.get('alt_text', ''),
            position=product.images.count(),
            is_featured=not product.images.exists(),
        )
    elif source_type == 'mockup':
        from imageforge.models import ProductMockup
        source = get_object_or_404(ProductMockup, pk=source_id, user=request.user)
        image = PLoomProductImage.objects.create(
            product=product,
            source='imageforge_mockup',
            imageforge_mockup=source,
            filename=filename,
            alt_text=data.get('alt_text', ''),
            position=product.images.count(),
            is_featured=not product.images.exists(),
        )
    else:
        return JsonResponse({'success': False, 'error': 'Ungültiger source_type'})

    return JsonResponse({
        'success': True,
        'image': {
            'id': image.pk,
            'url': image.image_url,
            'filename': image.filename,
            'alt_text': image.alt_text,
            'is_featured': image.is_featured,
        }
    })


@login_required
@require_POST
def api_image_set_variant(request, product_id, image_id):
    """Bild einer Variante zuweisen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)
    image = get_object_or_404(PLoomProductImage, pk=image_id, product=product)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    variant_id = data.get('variant_id', '')

    # Validieren wenn Variante angegeben
    if variant_id:
        variant = product.variants.filter(pk=variant_id).first()
        if not variant:
            return JsonResponse({'success': False, 'error': 'Variante nicht gefunden'})

    image.variant_id = str(variant_id) if variant_id else ''
    image.save()

    return JsonResponse({
        'success': True,
        'image_id': image.pk,
        'variant_id': image.variant_id
    })


@login_required
@require_POST
def api_image_from_url(request, product_id):
    """Bild von externer URL hinzufügen (Shopify CDN, Videos, etc.)"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    url = data.get('url', '').strip()
    filename = data.get('filename', '').strip()
    alt_text = data.get('alt_text', '').strip()

    if not url:
        return JsonResponse({'success': False, 'error': 'URL erforderlich'})

    # Bild erstellen
    image = PLoomProductImage.objects.create(
        product=product,
        source='external_url',
        external_url=url,
        filename=filename,
        alt_text=alt_text or filename,
        position=product.images.count(),
        is_featured=not product.images.exists(),
    )

    # Im Verlauf speichern
    from .models import PLoomImageHistory
    PLoomImageHistory.objects.update_or_create(
        user=request.user,
        url=url,
        defaults={
            'source': 'external_url',
            'filename': filename,
            'alt_text': alt_text,
            'thumbnail_url': url,
        }
    )

    return JsonResponse({
        'success': True,
        'image': {
            'id': image.pk,
            'url': image.image_url,
            'filename': image.filename,
            'alt_text': image.alt_text,
            'is_featured': image.is_featured,
        }
    })


@login_required
def api_image_history(request):
    """Bild-Verlauf abrufen"""
    from .models import PLoomImageHistory

    history = PLoomImageHistory.objects.filter(user=request.user)[:30]

    items = [{
        'id': item.id,
        'url': item.url,
        'thumbnail_url': item.thumbnail_url or item.url,
        'filename': item.filename,
        'alt_text': item.alt_text,
        'source': item.source,
        'usage_count': item.usage_count,
    } for item in history]

    return JsonResponse({'success': True, 'items': items})


@login_required
@require_POST
def api_image_from_history(request, product_id):
    """Bild aus Verlauf hinzufügen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    history_id = data.get('history_id')
    filename = data.get('filename', '').strip()
    alt_text = data.get('alt_text', '').strip()

    from .models import PLoomImageHistory
    history_item = get_object_or_404(PLoomImageHistory, pk=history_id, user=request.user)

    # Verwendung erhöhen
    history_item.usage_count += 1
    history_item.save()

    # Bild erstellen
    image = PLoomProductImage.objects.create(
        product=product,
        source='external_url',
        external_url=history_item.url,
        filename=filename or history_item.filename,
        alt_text=alt_text or history_item.alt_text,
        position=product.images.count(),
        is_featured=not product.images.exists(),
    )

    return JsonResponse({
        'success': True,
        'image': {
            'id': image.pk,
            'url': image.image_url,
            'filename': image.filename,
            'alt_text': image.alt_text,
            'is_featured': image.is_featured,
        }
    })


# ============================================================================
# KI-Generierung API
# ============================================================================

@login_required
@require_POST
def api_generate_title(request):
    """Titel mit KI generieren"""
    from .services.ai_service import PLoomAIService

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    product_name = data.get('product_name', '')
    keywords = data.get('keywords', '')

    if not product_name:
        return JsonResponse({'success': False, 'error': 'Produktname erforderlich'})

    try:
        service = PLoomAIService(request.user)
        result = service.generate_title(product_name, keywords)

        if result:
            # Im Verlauf speichern
            PLoomHistory.objects.create(
                user=request.user,
                field_type='title',
                content=result,
                prompt_used=f"Produkt: {product_name}, Keywords: {keywords}",
                ai_model_used=service.model
            )

        return JsonResponse({'success': True, 'content': result})
    except Exception as e:
        logger.error(f"Error generating title: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def api_generate_description(request):
    """Beschreibung mit KI generieren"""
    from .services.ai_service import PLoomAIService

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    product_name = data.get('product_name', '')
    keywords = data.get('keywords', '')
    tone = data.get('tone', 'professional')

    if not product_name:
        return JsonResponse({'success': False, 'error': 'Produktname erforderlich'})

    try:
        service = PLoomAIService(request.user)
        result = service.generate_description(product_name, keywords, tone)

        if result:
            PLoomHistory.objects.create(
                user=request.user,
                field_type='description',
                content=result,
                prompt_used=f"Produkt: {product_name}, Keywords: {keywords}, Ton: {tone}",
                ai_model_used=service.model
            )

        return JsonResponse({'success': True, 'content': result})
    except Exception as e:
        logger.error(f"Error generating description: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def api_generate_seo(request):
    """SEO-Texte mit KI generieren"""
    from .services.ai_service import PLoomAIService

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    product_name = data.get('product_name', '')
    description = data.get('description', '')
    keywords = data.get('keywords', '')

    if not product_name:
        return JsonResponse({'success': False, 'error': 'Produktname erforderlich'})

    try:
        service = PLoomAIService(request.user)
        result = service.generate_seo(product_name, description, keywords)

        if result:
            # SEO-Titel speichern
            if result.get('seo_title'):
                PLoomHistory.objects.create(
                    user=request.user,
                    field_type='seo_title',
                    content=result['seo_title'],
                    prompt_used=f"Produkt: {product_name}",
                    ai_model_used=service.model
                )
            # SEO-Beschreibung speichern
            if result.get('seo_description'):
                PLoomHistory.objects.create(
                    user=request.user,
                    field_type='seo_description',
                    content=result['seo_description'],
                    prompt_used=f"Produkt: {product_name}",
                    ai_model_used=service.model
                )

        return JsonResponse({'success': True, 'content': result})
    except Exception as e:
        logger.error(f"Error generating SEO: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def api_generate_tags(request):
    """Tags mit KI generieren"""
    from .services.ai_service import PLoomAIService

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    product_name = data.get('product_name', '')
    description = data.get('description', '')

    if not product_name:
        return JsonResponse({'success': False, 'error': 'Produktname erforderlich'})

    try:
        service = PLoomAIService(request.user)
        result = service.generate_tags(product_name, description)

        if result:
            PLoomHistory.objects.create(
                user=request.user,
                field_type='tags',
                content=result,
                prompt_used=f"Produkt: {product_name}",
                ai_model_used=service.model
            )

        return JsonResponse({'success': True, 'content': result})
    except Exception as e:
        logger.error(f"Error generating tags: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# SEO Komplett-Generator
# ============================================================================

@login_required
@require_POST
def api_generate_all(request):
    """Alle SEO-Felder auf einmal generieren"""
    from .services.ai_service import PLoomAIService

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    keyword = data.get('keyword', '').strip()
    language = data.get('language', 'de')

    if not keyword:
        return JsonResponse({'success': False, 'error': 'Keyword erforderlich'})

    try:
        service = PLoomAIService(request.user)
        result = service.generate_all_seo_content(keyword, language)

        if result:
            # Alle generierten Inhalte in History speichern
            for field_type, content in result.items():
                if content and field_type in ['title', 'description', 'seo_title', 'seo_description', 'tags']:
                    PLoomHistory.objects.create(
                        user=request.user,
                        field_type=field_type,
                        content=content,
                        prompt_used=f"SEO-Generator: {keyword}",
                        ai_model_used=service.model
                    )

        return JsonResponse({'success': True, 'content': result})
    except Exception as e:
        logger.error(f"Error generating all SEO content: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# Verlauf API
# ============================================================================

@login_required
def api_history(request, field_type):
    """Verlauf für ein Feldtyp abrufen"""
    if field_type not in ['title', 'description', 'seo_title', 'seo_description', 'tags']:
        return JsonResponse({'success': False, 'error': 'Ungültiger Feldtyp'})

    page = int(request.GET.get('page', 1))
    per_page = 12

    # Deduplizierte Einträge (neueste zuerst)
    history = PLoomHistory.objects.filter(
        user=request.user,
        field_type=field_type
    ).values('content').annotate(
        latest=Max('created_at')
    ).order_by('-latest')

    paginator = Paginator(list(history), per_page)
    page_obj = paginator.get_page(page)

    items = [{'content': item['content']} for item in page_obj]

    return JsonResponse({
        'success': True,
        'items': items,
        'has_next': page_obj.has_next(),
        'has_prev': page_obj.has_previous(),
        'page': page,
        'total_pages': paginator.num_pages,
    })


@login_required
def api_history_prices(request):
    """Preis-Verlauf abrufen (aus Produkten + Favoriten)"""
    page = int(request.GET.get('page', 1))
    per_page = 12

    # Favoriten-Preise
    favorites = PLoomFavoritePrice.objects.filter(user=request.user)

    # Preise aus Produkten (dedupliziert)
    product_prices = PLoomProduct.objects.filter(
        user=request.user,
        price__isnull=False
    ).values_list('price', flat=True).distinct()

    # Kombinieren
    items = []

    # Favoriten zuerst
    for fav in favorites:
        items.append({
            'price': str(fav.price),
            'label': fav.label,
            'is_favorite': True,
            'usage_count': fav.usage_count,
        })

    # Dann Produkt-Preise (ohne Duplikate mit Favoriten)
    favorite_prices = set(str(f.price) for f in favorites)
    for price in product_prices:
        if str(price) not in favorite_prices:
            items.append({
                'price': str(price),
                'label': '',
                'is_favorite': False,
            })

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = items[start:end]

    return JsonResponse({
        'success': True,
        'items': paginated_items,
        'has_next': end < len(items),
        'has_prev': page > 1,
        'page': page,
    })


@login_required
def api_metafield_history(request, metafield_key):
    """Verlauf für ein Metafeld abrufen"""
    page = int(request.GET.get('page', 1))
    per_page = 10

    # Deduplizierte Einträge (neueste zuerst)
    history = PLoomHistory.objects.filter(
        user=request.user,
        field_type='metafield',
        metafield_key=metafield_key
    ).values('content').annotate(
        latest=Max('created_at')
    ).order_by('-latest')

    paginator = Paginator(list(history), per_page)
    page_obj = paginator.get_page(page)

    items = [{'content': item['content']} for item in page_obj]

    return JsonResponse({
        'success': True,
        'items': items,
        'has_next': page_obj.has_next(),
        'has_prev': page_obj.has_previous(),
        'page': page,
        'total_pages': paginator.num_pages,
    })


@login_required
@require_POST
def api_favorite_price_add(request):
    """Preis zu Favoriten hinzufügen"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    price = data.get('price')
    label = data.get('label', '')

    if not price:
        return JsonResponse({'success': False, 'error': 'Preis erforderlich'})

    fav, created = PLoomFavoritePrice.objects.get_or_create(
        user=request.user,
        price=price,
        defaults={'label': label}
    )

    if not created and label:
        fav.label = label
        fav.save()

    return JsonResponse({'success': True, 'created': created})


# ============================================================================
# Theme API
# ============================================================================

@login_required
def api_theme_details(request, theme_id):
    """Theme-Details für Formular-Übernahme abrufen"""
    try:
        theme = get_object_or_404(ProductTheme, pk=theme_id, user=request.user)
        return JsonResponse({
            'success': True,
            'theme': {
                'id': theme.id,
                'name': theme.name,
                'title_template': theme.title_template,
                'description_template': theme.description_template,
                'seo_title_template': theme.seo_title_template,
                'seo_description_template': theme.seo_description_template,
                'default_price': str(theme.default_price) if theme.default_price else '',
                'default_compare_at_price': str(theme.default_compare_at_price) if theme.default_compare_at_price else '',
                'default_vendor': theme.default_vendor,
                'default_product_type': theme.default_product_type,
                'default_tags': theme.default_tags,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# Shopify API
# ============================================================================

@login_required
def api_shopify_collections(request):
    """Shopify Collections abrufen"""
    store_id = request.GET.get('store_id')

    if not store_id:
        # Standard-Store aus Einstellungen
        settings_obj = PLoomSettings.objects.filter(user=request.user).first()
        if settings_obj and settings_obj.default_store:
            store_id = settings_obj.default_store.id
        else:
            return JsonResponse({'success': False, 'error': 'Kein Store ausgewählt'})

    try:
        from shopify_manager.models import ShopifyStore
        from shopify_manager.shopify_api import ShopifyAPIClient

        store = get_object_or_404(ShopifyStore, pk=store_id, user=request.user)
        client = ShopifyAPIClient(store)

        # Collections abrufen (Custom + Smart)
        success, collections, error = client.fetch_collections()

        if not success:
            return JsonResponse({'success': False, 'error': error})

        return JsonResponse({'success': True, 'collections': collections})
    except Exception as e:
        logger.error(f"Error fetching collections: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_shopify_metafields(request):
    """Shopify Metafeld-Definitionen abrufen"""
    store_id = request.GET.get('store_id')

    if not store_id:
        # Standard-Store aus Einstellungen
        settings_obj = PLoomSettings.objects.filter(user=request.user).first()
        if settings_obj and settings_obj.default_store:
            store_id = settings_obj.default_store.id
        else:
            return JsonResponse({'success': False, 'error': 'Kein Store ausgewählt'})

    try:
        from shopify_manager.models import ShopifyStore
        store = get_object_or_404(ShopifyStore, pk=store_id, user=request.user)

        from .services.shopify_service import PLoomShopifyService
        service = PLoomShopifyService(store)
        success, definitions, error = service.get_metafield_definitions()

        return JsonResponse({
            'success': True,
            'definitions': definitions,
            'error': error if error else None
        })
    except Exception as e:
        logger.error(f"Error fetching metafield definitions: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_shopify_templates(request):
    """Shopify Product Templates abrufen"""
    store_id = request.GET.get('store_id')

    if not store_id:
        # Standard-Store aus Einstellungen
        settings_obj = PLoomSettings.objects.filter(user=request.user).first()
        if settings_obj and settings_obj.default_store:
            store_id = settings_obj.default_store.id
        else:
            return JsonResponse({'success': False, 'error': 'Kein Store ausgewählt'})

    try:
        from shopify_manager.models import ShopifyStore
        from shopify_manager.shopify_api import ShopifyAPIClient

        store = get_object_or_404(ShopifyStore, pk=store_id, user=request.user)
        client = ShopifyAPIClient(store)

        success, templates, error = client.fetch_product_templates()

        if not success:
            return JsonResponse({'success': False, 'error': error})

        return JsonResponse({'success': True, 'templates': templates})
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_shopify_publications(request):
    """Shopify Sales Channels / Veröffentlichungskanäle abrufen"""
    store_id = request.GET.get('store_id')

    if not store_id:
        # Standard-Store aus Einstellungen
        settings_obj = PLoomSettings.objects.filter(user=request.user).first()
        if settings_obj and settings_obj.default_store:
            store_id = settings_obj.default_store.id
        else:
            return JsonResponse({'success': False, 'error': 'Kein Store ausgewählt'})

    try:
        from shopify_manager.models import ShopifyStore
        from .services.shopify_service import PLoomShopifyService

        store = get_object_or_404(ShopifyStore, pk=store_id, user=request.user)
        service = PLoomShopifyService(store)

        success, publications, error = service.get_publications()

        if not success:
            return JsonResponse({'success': False, 'error': error})

        return JsonResponse({'success': True, 'publications': publications})
    except Exception as e:
        logger.error(f"Error fetching publications: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def api_shopify_upload(request, product_id):
    """Produkt zu Shopify hochladen"""
    product = get_object_or_404(PLoomProduct, pk=product_id, user=request.user)

    if not product.shopify_store:
        return JsonResponse({'success': False, 'error': 'Kein Shopify Store ausgewählt'})

    try:
        from .services.shopify_service import PLoomShopifyService

        service = PLoomShopifyService(product.shopify_store)
        success, shopify_id, error = service.create_draft_product(product)

        if success:
            product.status = 'uploaded'
            product.shopify_product_id = shopify_id
            product.uploaded_at = timezone.now()
            product.upload_error = ''
            product.save()
            return JsonResponse({
                'success': True,
                'shopify_product_id': shopify_id,
                'message': 'Produkt erfolgreich als Entwurf hochgeladen'
            })
        else:
            product.status = 'error'
            product.upload_error = error
            product.save()
            return JsonResponse({'success': False, 'error': error})

    except Exception as e:
        logger.error(f"Error uploading to Shopify: {e}")
        product.status = 'error'
        product.upload_error = str(e)
        product.save()
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# Hilfsfunktionen
# ============================================================================

def _save_price_to_history(user, price):
    """Speichert einen Preis im Verlauf (automatisch aus Produkten)"""
    # Prüfen ob Preis schon als Favorit existiert
    exists = PLoomFavoritePrice.objects.filter(user=user, price=price).exists()
    if exists:
        # Verwendungszähler erhöhen
        PLoomFavoritePrice.objects.filter(user=user, price=price).update(
            usage_count=models.F('usage_count') + 1
        )


def _save_metafields_to_history(user, metafields):
    """Speichert Metafeld-Werte im Verlauf"""
    for key, value in metafields.items():
        if value:  # Nur nicht-leere Werte speichern
            # Prüfen ob dieser Wert für dieses Metafeld schon existiert
            exists = PLoomHistory.objects.filter(
                user=user,
                field_type='metafield',
                metafield_key=key,
                content=value
            ).exists()

            if not exists:
                PLoomHistory.objects.create(
                    user=user,
                    field_type='metafield',
                    metafield_key=key,
                    content=value
                )


# Import für models.F
from django.db.models import F, Max


# ============================================================================
# Browser-basierte Tests (nur für Superuser)
# ============================================================================

@login_required
def run_tests(request):
    """Führt Browser-basierte Tests aus (nur für Superuser)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Nur für Superuser'}, status=403)

    from .tests import PLoomTestRunner, cleanup_test_data

    # Tests ausführen
    runner = PLoomTestRunner(request.user)
    results = runner.run_all_tests()

    # Test-Daten aufräumen
    cleanup_test_data(request.user)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(results)

    return render(request, 'ploom/tests.html', {'results': results})
