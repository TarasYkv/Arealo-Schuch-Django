from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.db.models import Q
import base64
import uuid
import json
from .models import FotogravurImage


def is_superuser(user):
    """Prüft, ob der Benutzer ein Superuser ist"""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def image_list(request):
    """
    Listenansicht aller hochgeladenen Fotogravur-Bilder
    Nur für Superuser zugänglich
    """
    # Suchfunktion
    search_query = request.GET.get('q', '')
    images = FotogravurImage.objects.all()

    if search_query:
        images = images.filter(
            Q(unique_id__icontains=search_query) |
            Q(shopify_order_id__icontains=search_query) |
            Q(custom_text__icontains=search_query) |
            Q(original_filename__icontains=search_query)
        )

    context = {
        'images': images,
        'search_query': search_query,
        'total_count': FotogravurImage.objects.count(),
    }
    return render(request, 'shopify_uploads/image_list.html', context)


@login_required
@user_passes_test(is_superuser)
def image_detail(request, unique_id):
    """
    Detailansicht eines einzelnen Bildes
    Nur für Superuser zugänglich
    """
    image = get_object_or_404(FotogravurImage, unique_id=unique_id)

    context = {
        'image': image,
    }
    return render(request, 'shopify_uploads/image_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def image_delete(request, unique_id):
    """
    Löscht ein Bild
    Nur für Superuser zugänglich
    """
    image = get_object_or_404(FotogravurImage, unique_id=unique_id)

    if request.method == 'POST':
        # Bild und Datei löschen
        if image.image:
            image.image.delete()
        image.delete()
        messages.success(request, f'Bild {unique_id} wurde erfolgreich gelöscht.')
        return redirect('shopify_uploads:image_list')

    context = {
        'image': image,
    }
    return render(request, 'shopify_uploads/image_delete_confirm.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def upload_image(request):
    """
    API-Endpoint zum Hochladen von konvertierten Bildern
    Wird vom Shopify-Frontend aufgerufen
    """
    try:
        # Parse JSON request body
        data = json.loads(request.body)

        # Validierung
        required_fields = ['image_data', 'unique_id']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Fehlendes Feld: {field}'
                }, status=400)

        # Base64-Bild dekodieren
        image_data = data['image_data']
        if image_data.startswith('data:image'):
            # Entferne "data:image/png;base64," prefix
            image_data = image_data.split(',')[1]

        image_binary = base64.b64decode(image_data)

        # Dateiname generieren
        filename = f"{data['unique_id']}.png"

        # FotogravurImage erstellen
        fotogravur_image = FotogravurImage(
            unique_id=data['unique_id'],
            original_filename=data.get('original_filename', ''),
            shopify_order_id=data.get('shopify_order_id', ''),
            shopify_product_id=data.get('shopify_product_id', ''),
            custom_text=data.get('custom_text', ''),
            font_family=data.get('font_family', ''),
            processing_settings=data.get('processing_settings', {}),
            file_size=len(image_binary),
        )

        # Bild speichern
        fotogravur_image.image.save(
            filename,
            ContentFile(image_binary),
            save=True
        )

        return JsonResponse({
            'success': True,
            'unique_id': fotogravur_image.unique_id,
            'image_url': fotogravur_image.image.url,
            'file_size_kb': fotogravur_image.file_size_kb,
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiges JSON-Format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_image(request, unique_id):
    """
    API-Endpoint zum Abrufen eines Bildes anhand der unique_id
    """
    try:
        image = FotogravurImage.objects.get(unique_id=unique_id)
        return JsonResponse({
            'success': True,
            'unique_id': image.unique_id,
            'image_url': request.build_absolute_uri(image.image.url),
            'custom_text': image.custom_text,
            'font_family': image.font_family,
            'processing_settings': image.processing_settings,
            'created_at': image.created_at.isoformat(),
        })
    except FotogravurImage.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bild nicht gefunden'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
