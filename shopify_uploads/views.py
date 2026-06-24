from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.db.models import Q
import base64
import uuid
import json
import os
from functools import wraps
from .models import FotogravurImage


def cors_headers(func):
    """
    Decorator to add CORS headers to API responses.
    Allows requests from naturmacher.de (Shopify store).
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        # Handle preflight OPTIONS request
        if request.method == 'OPTIONS':
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = 'https://naturmacher.de'
            response['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'
            response['Access-Control-Max-Age'] = '86400'  # 24 hours
            return response

        # Call the actual view
        response = func(request, *args, **kwargs)

        # Add CORS headers to response
        response['Access-Control-Allow-Origin'] = 'https://naturmacher.de'
        response['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'
        response['Access-Control-Allow-Credentials'] = 'false'

        return response
    return wrapper


def get_media_url_with_cors(request, file_field):
    """
    Hilfsfunktion: Erstellt URL für Media-Datei mit CORS-Proxy.
    Für PythonAnywhere: Bilder werden durch Django-View mit CORS-Headern serviert.

    Args:
        request: Django request object
        file_field: ImageField oder FileField

    Returns:
        str: Absolute URL mit CORS-Proxy (/shopify-uploads/media/...)
    """
    if not file_field:
        return None

    # Extrahiere relativen Pfad (entferne /media/ prefix)
    file_path = file_field.name  # z.B. "fotogravur/originals/2025/11/test.png"

    # Erstelle URL über unseren CORS-Proxy
    # /shopify-uploads/media/fotogravur/originals/2025/11/test.png
    proxy_url = f'/shopify-uploads/media/{file_path}'

    # Mache absolute URL
    return request.build_absolute_uri(proxy_url)


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

    from django.db.models import Sum, Count
    from django.utils import timezone
    from .models import AiUsageLog
    _all = AiUsageLog.objects.aggregate(n=Count('id'), c=Sum('cost_cents'))
    _nm = AiUsageLog.objects.filter(source='naturmacher').aggregate(n=Count('id'), c=Sum('cost_cents'))
    _ms = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _mo = AiUsageLog.objects.filter(created_at__gte=_ms).aggregate(n=Count('id'), c=Sum('cost_cents'))
    ai_stats = {
        'total_n': _all['n'] or 0, 'total_eur': (_all['c'] or 0) / 100.0,
        'nm_n': _nm['n'] or 0, 'nm_eur': (_nm['c'] or 0) / 100.0,
        'month_n': _mo['n'] or 0, 'month_eur': (_mo['c'] or 0) / 100.0,
    }
    images = list(images)
    for _img in images:
        _ps = _img.processing_settings if isinstance(_img.processing_settings, dict) else {}
        _img.ki_kind = 'gemini' if 'gemini' in str(_ps.get('ai', '') or '').lower() else 'manuell'

    context = {
        'images': images,
        'search_query': search_query,
        'total_count': FotogravurImage.objects.count(),
        'ai_stats': ai_stats,
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

    ps = image.processing_settings if isinstance(image.processing_settings, dict) else {}
    _ai = str(ps.get('ai', '') or '')
    if 'gemini' in _ai.lower():
        ki_info = {'kind': 'gemini', 'label': 'Mit Gemini KI bearbeitet', 'model': _ai}
    else:
        ki_info = {'kind': 'manuell', 'label': 'Manuell / ohne KI bearbeitet', 'model': _ai}

    context = {
        'image': image,
        'ki_info': ki_info,
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
@cors_headers
def upload_image(request):
    """
    API-Endpoint zum Hochladen von konvertierten Bildern
    Wird vom Shopify-Frontend aufgerufen
    Akzeptiert: POST, OPTIONS (für CORS preflight)

    Unterstützt zwei Modi:
    1. Initial Upload: nur original_image_data + unique_id (erstellt Record)
    2. Update: image_data + unique_id (updated existierenden Record)
    3. Full Upload: beide Bilder gleichzeitig
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=405)
    try:
        # Parse JSON request body
        data = json.loads(request.body)

        # Validierung: unique_id ist required, mindestens ein Bild muss vorhanden sein
        if 'unique_id' not in data:
            return JsonResponse({
                'success': False,
                'error': 'Fehlendes Feld: unique_id'
            }, status=400)

        if 'image_data' not in data and 'original_image_data' not in data:
            return JsonResponse({
                'success': False,
                'error': 'Mindestens ein Bild muss vorhanden sein (image_data oder original_image_data)'
            }, status=400)

        # Base64-Bilder dekodieren
        image_binary = None
        if 'image_data' in data and data['image_data']:
            image_data = data['image_data']
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            image_binary = base64.b64decode(image_data)

        original_image_binary = None
        if 'original_image_data' in data and data['original_image_data']:
            original_image_data = data['original_image_data']
            if original_image_data.startswith('data:image'):
                original_image_data = original_image_data.split(',')[1]
            original_image_binary = base64.b64decode(original_image_data)

        # Dateinamen generieren
        filename = f"{data['unique_id']}.png"
        original_filename = f"{data['unique_id']}_original.png"

        # Versuche existierenden Record zu finden, sonst erstelle neuen
        try:
            fotogravur_image = FotogravurImage.objects.get(unique_id=data['unique_id'])
            # Update existierendes Bild
            is_update = True
        except FotogravurImage.DoesNotExist:
            # Erstelle neues Bild
            fotogravur_image = FotogravurImage(
                unique_id=data['unique_id'],
                file_size=len(image_binary) if image_binary else len(original_image_binary),
            )
            is_update = False

        # Schutz: ein bereits KI-optimiertes Gravur-Bild darf NICHT durch die clientseitige
        # (Graustufen-)Version ueberschrieben werden. Nur Metadaten/Original-Bild duerfen rein.
        _ai_locked = bool(
            is_update
            and isinstance(getattr(fotogravur_image, 'processing_settings', None), dict)
            and fotogravur_image.processing_settings.get('ai')
        )
        if _ai_locked:
            image_binary = None  # vorhandenes KI-Gravurbild behalten

        # Felder aktualisieren (optional)
        if 'original_filename' in data:
            fotogravur_image.original_filename = data['original_filename']
        if 'shopify_order_id' in data:
            fotogravur_image.shopify_order_id = data['shopify_order_id']
        if 'shopify_product_id' in data:
            fotogravur_image.shopify_product_id = data['shopify_product_id']
        if 'custom_text' in data:
            fotogravur_image.custom_text = data['custom_text']
        if 'font_family' in data:
            fotogravur_image.font_family = data['font_family']
        if 'processing_settings' in data and not _ai_locked:
            fotogravur_image.processing_settings = data['processing_settings']

        # File size aktualisieren
        if image_binary:
            fotogravur_image.file_size = len(image_binary)
        elif original_image_binary and not is_update:
            fotogravur_image.file_size = len(original_image_binary)

        # S/W-Bild speichern (falls vorhanden)
        if image_binary:
            fotogravur_image.image.save(
                filename,
                ContentFile(image_binary),
                save=False
            )

        # Original-Bild speichern (falls vorhanden)
        if original_image_binary:
            fotogravur_image.original_image.save(
                original_filename,
                ContentFile(original_image_binary),
                save=False
            )

        # Alles speichern
        fotogravur_image.save()

        response_data = {
            'success': True,
            'unique_id': fotogravur_image.unique_id,
            'file_size_kb': fotogravur_image.file_size_kb,
            'is_update': is_update,
        }

        # URLs hinzufügen (falls vorhanden) - WICHTIG: Mit CORS-Proxy für PythonAnywhere
        if fotogravur_image.image:
            response_data['image_url'] = get_media_url_with_cors(request, fotogravur_image.image)
        if fotogravur_image.original_image:
            response_data['original_image_url'] = get_media_url_with_cors(request, fotogravur_image.original_image)

        return JsonResponse(response_data)

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
@cors_headers
def get_image(request, unique_id):
    """
    API-Endpoint zum Abrufen eines Bildes anhand der unique_id
    Akzeptiert: GET, OPTIONS (für CORS preflight)
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests allowed'}, status=405)
    try:
        image = FotogravurImage.objects.get(unique_id=unique_id)

        response_data = {
            'success': True,
            'unique_id': image.unique_id,
            'custom_text': image.custom_text,
            'font_family': image.font_family,
            'processing_settings': image.processing_settings,
            'created_at': image.created_at.isoformat(),
        }

        # URLs nur hinzufügen, wenn vorhanden - mit CORS-Proxy
        if image.image:
            response_data['image_url'] = get_media_url_with_cors(request, image.image)
        if image.original_image:
            response_data['original_image_url'] = get_media_url_with_cors(request, image.original_image)

        return JsonResponse(response_data)
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


@csrf_exempt
def shopify_order_webhook(request):
    """
    Webhook-Endpoint für Shopify Order Creation
    Wird aufgerufen, wenn eine Bestellung abgeschlossen wird
    Aktualisiert FotogravurImage mit Order-ID und benennt Bild um
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=405)

    try:
        import hmac
        import hashlib
        from django.conf import settings
        import os

        # HMAC-Verifizierung (optional, aber empfohlen für Production)
        webhook_secret = os.environ.get('SHOPIFY_WEBHOOK_SECRET', '')
        if webhook_secret:
            hmac_header = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256', '')
            calculated_hmac = hmac.new(
                webhook_secret.encode('utf-8'),
                request.body,
                hashlib.sha256
            ).digest()
            calculated_hmac_b64 = base64.b64encode(calculated_hmac).decode('utf-8')

            if not hmac.compare_digest(calculated_hmac_b64, hmac_header):
                return JsonResponse({'error': 'Invalid HMAC signature'}, status=401)

        # Parse Order Data
        order_data = json.loads(request.body)
        order_id = str(order_data.get('id', ''))
        order_number = order_data.get('order_number', '')

        if not order_id:
            return JsonResponse({'error': 'Missing order_id'}, status=400)

        # Line Items durchgehen und nach Fotogravur-Bildern suchen
        line_items = order_data.get('line_items', [])
        updated_images = []

        for item in line_items:
            properties = item.get('properties', [])

            # Nach "Bild ID" Property suchen
            bild_id = None
            for prop in properties:
                if prop.get('name') == 'Bild ID':
                    bild_id = prop.get('value')
                    break

            if not bild_id:
                continue  # Kein Fotogravur-Bild in diesem Line Item

            # FotogravurImage mit unique_id finden
            try:
                fotogravur_image = FotogravurImage.objects.get(unique_id=bild_id)

                # Order-ID speichern
                fotogravur_image.shopify_order_id = order_id

                # Bild umbenennen auf order_id.png
                from django.core.files.base import File
                import shutil
                import pathlib

                if fotogravur_image.image:
                    # Alten Dateipfad holen
                    old_file = fotogravur_image.image.file
                    old_path = fotogravur_image.image.path

                    # Neuer Filename für S/W-Bild
                    new_filename = f"{order_id}.png"

                    # Speicherort beibehalten, nur Filename ändern
                    old_path_obj = pathlib.Path(old_path)
                    new_path = old_path_obj.parent / new_filename

                    # Datei umbenennen
                    shutil.move(str(old_path_obj), str(new_path))

                    # Model-Feld aktualisieren
                    fotogravur_image.image.name = str(pathlib.Path(fotogravur_image.image.name).parent / new_filename)

                # Original-Bild umbenennen auf order_id_original.png
                if fotogravur_image.original_image:
                    # Alten Dateipfad holen
                    old_original_path = fotogravur_image.original_image.path

                    # Neuer Filename für Original-Bild
                    new_original_filename = f"{order_id}_original.png"

                    # Speicherort beibehalten, nur Filename ändern
                    old_original_path_obj = pathlib.Path(old_original_path)
                    new_original_path = old_original_path_obj.parent / new_original_filename

                    # Datei umbenennen
                    shutil.move(str(old_original_path_obj), str(new_original_path))

                    # Model-Feld aktualisieren
                    fotogravur_image.original_image.name = str(pathlib.Path(fotogravur_image.original_image.name).parent / new_original_filename)

                fotogravur_image.save()

                # Response mit beiden Dateinamen
                image_info = {
                    'unique_id': bild_id,
                    'order_id': order_id,
                    'new_sw_filename': f"{order_id}.png"
                }

                if fotogravur_image.original_image:
                    image_info['new_original_filename'] = f"{order_id}_original.png"

                updated_images.append(image_info)

            except FotogravurImage.DoesNotExist:
                # Bild nicht gefunden - kann vorkommen bei älteren Bestellungen
                continue

        return JsonResponse({
            'success': True,
            'order_id': order_id,
            'order_number': order_number,
            'updated_images': updated_images,
            'count': len(updated_images)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        # Log error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Shopify Webhook Error: {str(e)}', exc_info=True)

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_superuser)
def image_edit(request, unique_id):
    """
    Bildeditor-Ansicht für Laser-Gravur Anpassungen
    Nur für Superuser zugänglich
    """
    image = get_object_or_404(FotogravurImage, unique_id=unique_id)

    # Wenn kein Original vorhanden, verwende das verarbeitete Bild als Basis
    if not image.original_image and image.image:
        context = {
            'image': image,
            'has_original': False,
            'error': 'Kein Original-Bild vorhanden. Bitte verwenden Sie ein Bild mit Original.'
        }
        return render(request, 'shopify_uploads/image_edit.html', context)

    context = {
        'image': image,
        'has_original': bool(image.original_image),
    }
    return render(request, 'shopify_uploads/image_edit.html', context)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def process_image_ajax(request, unique_id):
    """
    AJAX-Endpoint für Bildverarbeitung
    Akzeptiert JSON mit Operation und Parametern, gibt verarbeitetes Bild zurück
    """
    try:
        image = get_object_or_404(FotogravurImage, unique_id=unique_id)

        # Parse JSON request
        data = json.loads(request.body)
        operation = data.get('operation')
        current_image_data = data.get('current_image_data')  # Optional: Aktuelles Canvas-Bild

        if not operation:
            return JsonResponse({
                'success': False,
                'error': 'Operation fehlt'
            }, status=400)

        # Importiere ImageProcessor
        from .image_processing import ImageProcessor
        import base64
        from io import BytesIO
        from PIL import Image as PILImage

        # Verwende aktuelles Canvas-Bild falls vorhanden, sonst Original
        if current_image_data:
            # Entferne "data:image/...;base64," Prefix
            if 'base64,' in current_image_data:
                current_image_data = current_image_data.split('base64,')[1]

            # Dekodiere Base64 zu Bild
            image_bytes = base64.b64decode(current_image_data)
            pil_image = PILImage.open(BytesIO(image_bytes))

            # Initialisiere Prozessor mit PIL-Bild (direkt als Argument)
            processor = ImageProcessor(pil_image)
        else:
            # Verwende Original-Bild als Basis (falls vorhanden)
            source_image = image.original_image if image.original_image else image.image

            if not source_image:
                return JsonResponse({
                    'success': False,
                    'error': 'Kein Bild vorhanden'
                }, status=400)

            # Initialisiere Prozessor
            processor = ImageProcessor(source_image)

        # Führe Operation aus
        success = False
        message = ''

        if operation == 'brightness':
            factor = float(data.get('factor', 1.0))
            success, message = processor.adjust_brightness(factor)

        elif operation == 'contrast':
            factor = float(data.get('factor', 1.0))
            success, message = processor.adjust_contrast(factor)

        elif operation == 'grayscale':
            success, message = processor.convert_to_grayscale()

        elif operation == 'invert':
            success, message = processor.invert()

        elif operation == 'threshold':
            threshold = int(data.get('threshold', 127))
            success, message = processor.apply_threshold(threshold)

        elif operation == 'dithering':
            threshold = int(data.get('threshold', 127))
            method = data.get('method', 'floyd-steinberg')
            success, message = processor.apply_dithering(method=method, threshold=threshold)

        else:
            return JsonResponse({
                'success': False,
                'error': f'Unbekannte Operation: {operation}'
            }, status=400)

        if not success:
            return JsonResponse({
                'success': False,
                'error': message
            }, status=500)

        # Konvertiere Bild zu Base64
        image_base64 = processor.get_current_image_base64()

        return JsonResponse({
            'success': True,
            'image': image_base64,
            'message': message
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiges JSON'
        }, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Image processing error: {str(e)}', exc_info=True)

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def save_processed_image(request, unique_id):
    """
    Speichert das verarbeitete Bild als S/W-Version
    Akzeptiert Base64-Bild-Daten
    """
    try:
        image = get_object_or_404(FotogravurImage, unique_id=unique_id)

        # Parse JSON request
        data = json.loads(request.body)
        image_data = data.get('image_data')
        processing_settings = data.get('processing_settings', {})

        if not image_data:
            return JsonResponse({
                'success': False,
                'error': 'Keine Bilddaten vorhanden'
            }, status=400)

        # Dekodiere Base64-Bild
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]

        image_binary = base64.b64decode(image_data)

        # Speichere als S/W-Bild
        filename = f"{unique_id}_edited.png"
        image.edited_image.save(
            filename,
            ContentFile(image_binary),
            save=False
        )

        # Update file size
        image.file_size = len(image_binary)

        # Speichere Verarbeitungseinstellungen
        # processing_settings (Kundenwerte) bleiben erhalten

        # Save to database
        image.save()

        return JsonResponse({
            'success': True,
            'message': 'Bild erfolgreich gespeichert',
            
            'image_url': image.edited_image.url
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiges JSON'
        }, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Image save error: {str(e)}', exc_info=True)

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def bulk_delete_images(request):
    """
    Bulk-Delete: Löscht mehrere Bilder gleichzeitig
    Akzeptiert JSON mit Array von image_ids
    Löscht sowohl Datenbank-Einträge als auch Bild-Dateien
    """
    try:
        # Parse JSON request
        data = json.loads(request.body)
        image_ids = data.get('image_ids', [])

        if not image_ids:
            return JsonResponse({
                'success': False,
                'error': 'Keine Bild-IDs angegeben'
            }, status=400)

        if not isinstance(image_ids, list):
            return JsonResponse({
                'success': False,
                'error': 'image_ids muss ein Array sein'
            }, status=400)

        # Zähler für gelöschte Bilder
        deleted_count = 0
        errors = []

        # Lösche jedes Bild
        for unique_id in image_ids:
            try:
                image = FotogravurImage.objects.get(unique_id=unique_id)

                # Lösche S/W-Bild
                if image.image:
                    try:
                        image.image.delete(save=False)
                    except Exception as e:
                        errors.append(f"{unique_id}: Fehler beim Löschen des S/W-Bildes - {str(e)}")

                # Lösche Original-Bild
                if image.original_image:
                    try:
                        image.original_image.delete(save=False)
                    except Exception as e:
                        errors.append(f"{unique_id}: Fehler beim Löschen des Original-Bildes - {str(e)}")

                # Lösche Datenbank-Eintrag
                image.delete()
                deleted_count += 1

            except FotogravurImage.DoesNotExist:
                errors.append(f"{unique_id}: Bild nicht gefunden")
            except Exception as e:
                errors.append(f"{unique_id}: Unerwarteter Fehler - {str(e)}")

        # Response erstellen
        response_data = {
            'success': True,
            'deleted_count': deleted_count,
            'requested_count': len(image_ids),
        }

        if errors:
            response_data['errors'] = errors
            response_data['message'] = f'{deleted_count} von {len(image_ids)} Bild(ern) erfolgreich gelöscht. {len(errors)} Fehler aufgetreten.'
        else:
            response_data['message'] = f'{deleted_count} Bild(er) erfolgreich gelöscht.'

        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültiges JSON'
        }, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Bulk delete error: {str(e)}', exc_info=True)

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@cors_headers
def serve_media_with_cors(request, file_path):
    """
    Serviert Media-Dateien mit CORS-Headern.
    Workaround für PythonAnywhere, wo nginx nicht konfiguriert werden kann.

    URL: /shopify-uploads/media/<file_path>
    Beispiel: /shopify-uploads/media/fotogravur/originals/2025/11/test.png
    """
    from django.conf import settings

    if request.method not in ['GET', 'OPTIONS']:
        return HttpResponse('Method not allowed', status=405)

    # OPTIONS preflight ist bereits durch @cors_headers decorator behandelt
    if request.method == 'OPTIONS':
        return HttpResponse(status=204)

    try:
        # Vollständiger Pfad zur Datei
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        # Sicherheitscheck: Stelle sicher, dass die Datei innerhalb von MEDIA_ROOT liegt
        full_path = os.path.abspath(full_path)
        media_root = os.path.abspath(settings.MEDIA_ROOT)

        if not full_path.startswith(media_root):
            raise Http404("Invalid file path")

        # Prüfe ob Datei existiert
        if not os.path.exists(full_path):
            raise Http404("File not found")

        # Öffne und serviere die Datei
        response = FileResponse(open(full_path, 'rb'))

        # Content-Type basierend auf Dateiendung
        if full_path.endswith('.png'):
            response['Content-Type'] = 'image/png'
        elif full_path.endswith(('.jpg', '.jpeg')):
            response['Content-Type'] = 'image/jpeg'
        elif full_path.endswith('.gif'):
            response['Content-Type'] = 'image/gif'
        elif full_path.endswith('.webp'):
            response['Content-Type'] = 'image/webp'
        else:
            response['Content-Type'] = 'application/octet-stream'

        # Cache-Header für bessere Performance
        response['Cache-Control'] = 'public, max-age=2592000'  # 30 Tage

        return response

    except Http404:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Media serve error: {str(e)}', exc_info=True)
        raise Http404("File not found")



_AI_SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


_AI_COST_CENTS = {
    'gemini-3-pro-image-preview': 13.0, 'gemini-3-pro-image': 13.0,
    'gemini-2.5-flash-image': 4.0, 'gemini-3.1-flash-image-preview': 6.7,
    'gemini-2.5-flash': 0.2, 'gemini-2.5-flash-lite': 0.1, 'gemini-flash-latest': 0.3,
}


def _log_ai_usage(source, model, kind, unique_id):
    try:
        from .models import AiUsageLog
        AiUsageLog.objects.create(source=source, model=model or '', kind=kind,
                                  cost_cents=_AI_COST_CENTS.get(model, 0.0), unique_id=unique_id or '')
    except Exception:
        pass


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def ai_optimize_engraving(request, unique_id):
    """KI-Optimierung fuer Lasergravur: Gemini analysiert das Foto und empfiehlt optimale
    Tonwert-Parameter (Helligkeit/Kontrast/Schwellwert/Dithering), die exakt mit PIL angewendet
    werden. Der Bildinhalt (Personen/Umgebung) wird NICHT veraendert."""
    from django.conf import settings as dj_settings
    image = get_object_or_404(FotogravurImage, unique_id=unique_id)
    src = image.original_image if (image.original_image and image.original_image.name) else image.image
    if not src or not src.name:
        return JsonResponse({'success': False, 'error': 'Kein Bild vorhanden'}, status=400)
    api_key = getattr(request.user, 'gemini_api_key', None) or getattr(dj_settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return JsonResponse({'success': False, 'error': 'Kein Gemini-API-Key konfiguriert'}, status=500)
    try:
        import re as _re
        import google.generativeai as genai
        from PIL import Image as PILImage
        from .image_processing import ImageProcessor

        pil = PILImage.open(src)
        if pil.mode != 'RGB':
            pil = pil.convert('RGB')

        prompt = (
            "You are a laser-engraving image specialist. Analyze this photo and recommend the OPTIMAL "
            "tonal processing parameters to convert it into a clean black-and-white image for laser "
            "engraving on a light ceramic surface. Maximize clarity of the main subject (faces, contours). "
            "IMPORTANT: only recommend tonal/processing parameters - do NOT change or describe changing any content. "
            "Return ONLY valid minified JSON (no markdown) with keys: "
            "brightness_factor (number 0.6-1.5, 1.0=neutral), "
            "contrast_factor (number 0.8-2.2, 1.0=neutral), "
            "threshold (integer 0-255), "
            "dithering (one of: floyd-steinberg, ordered, none), "
            "reason (short German sentence). "
            "Guidance: portraits/photos with faces -> floyd-steinberg dithering and moderate contrast; "
            "logos/line art -> dithering none with a hard threshold."
        )

        try:
            _body = json.loads(request.body or b'{}')
        except Exception:
            _body = {}
        _allowed = ['gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-flash-latest', 'gemini-3-flash-preview']
        _mname = _body.get('model') if _body.get('model') in _allowed else 'gemini-2.5-flash'
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(_mname)
        resp = model.generate_content([prompt, pil], safety_settings=_AI_SAFETY)
        txt = (getattr(resp, 'text', '') or '').strip()
        mt = _re.search(r'\{.*\}', txt, _re.S)
        params = json.loads(mt.group(0)) if mt else {}

        bf = float(params.get('brightness_factor', 1.0))
        cf = float(params.get('contrast_factor', 1.0))
        th = int(float(params.get('threshold', 127)))
        dith = str(params.get('dithering', 'floyd-steinberg')).lower().strip()
        reason = str(params.get('reason', ''))[:200]
        bf = max(0.4, min(2.0, bf)); cf = max(0.5, min(3.0, cf)); th = max(0, min(255, th))
        if dith not in ('floyd-steinberg', 'ordered', 'none'):
            dith = 'floyd-steinberg'

        proc = ImageProcessor(pil)
        proc.convert_to_grayscale()
        if abs(bf - 1.0) > 0.001:
            proc.adjust_brightness(bf)
        if abs(cf - 1.0) > 0.001:
            proc.adjust_contrast(cf)
        if dith == 'none':
            proc.apply_threshold(th)
        else:
            proc.apply_dithering(method=dith, threshold=th)

        data_url = proc.get_current_image_base64()
        _log_ai_usage('admin', _mname, 'optimize', unique_id)
        return JsonResponse({
            'success': True,
            'image_data': data_url,
            'settings': {'brightness_factor': bf, 'contrast_factor': cf, 'threshold': th, 'dithering': dith},
            'reason': reason,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'KI-Optimierung fehlgeschlagen: ' + str(e)}, status=500)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def ai_generate_engraving(request, unique_id):
    """Komplett-KI-Bearbeitung (generativ): Nano Banana (gemini-3-pro-image) erzeugt aus dem
    Original ein gravur-optimiertes S/W-Bild. ACHTUNG: generativ - kann Inhalt leicht veraendern."""
    from django.conf import settings as dj_settings
    image = get_object_or_404(FotogravurImage, unique_id=unique_id)
    src = image.original_image if (image.original_image and image.original_image.name) else image.image
    if not src or not src.name:
        return JsonResponse({'success': False, 'error': 'Kein Bild vorhanden'}, status=400)
    api_key = getattr(request.user, 'gemini_api_key', None) or getattr(dj_settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return JsonResponse({'success': False, 'error': 'Kein Gemini-API-Key konfiguriert'}, status=500)
    try:
        from imageforge.services.gemini_generator import GeminiGenerator
        prompt = (
            "Redraw this photograph as a HIGH-CONTRAST BLACK AND WHITE line/stipple artwork for laser "
            "engraving on light ceramic. Represent shading with fine STIPPLING, CROSS-HATCHING and HALFTONE "
            "DOTS - NOT smooth grey gradients. Strong clear contours, well-defined facial features, plain "
            "white background. CRITICAL: keep the person(s), faces, pose and composition EXACTLY as in the "
            "reference - do not add, remove, beautify or restyle anything, only change the rendering style."
        )
        try:
            _body = json.loads(request.body or b'{}')
        except Exception:
            _body = {}
        _allowed = ['gemini-2.5-flash-image', 'gemini-3.1-flash-image-preview', 'gemini-3-pro-image-preview']
        _mname = _body.get('model') if _body.get('model') in _allowed else 'gemini-3.1-flash-image-preview'
        gen = GeminiGenerator(api_key)
        try:
            src_path = src.path
        except Exception:
            src_path = src
        result = gen.generate(prompt=prompt, reference_images=[src_path], model=_mname)
        if not result.get('success'):
            return JsonResponse({'success': False, 'error': result.get('error', 'KI-Bildgenerierung fehlgeschlagen')}, status=500)
        img_data = result.get('image_data') or ''
        if not img_data:
            return JsonResponse({'success': False, 'error': 'Kein Bild von der KI erhalten'}, status=500)
        raw = img_data.split(',', 1)[1] if ',' in str(img_data) else img_data
        # Generatives (Graustufen-)Ergebnis in echtes 1-Bit Gravur-Bild wandeln (Floyd-Steinberg)
        try:
            import io as _io
            from PIL import Image as _PILImage
            from .image_processing import ImageProcessor
            nb = _PILImage.open(_io.BytesIO(base64.b64decode(raw)))
            if nb.mode != 'RGB':
                nb = nb.convert('RGB')
            proc = ImageProcessor(nb)
            proc.convert_to_grayscale()
            proc.apply_dithering(method='floyd-steinberg', threshold=127)
            final = proc.get_current_image_base64()
        except Exception:
            final = 'data:image/png;base64,' + raw
        return JsonResponse({'success': True, 'image_data': final})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'KI-Bearbeitung fehlgeschlagen: ' + str(e)}, status=500)


def _engrave_dither(proc, method='floyd-steinberg', threshold=127, target_width=360, upscale=3):
    """Bewusst grobes Dithering fuer Diodenlaser (z.B. Creality Falcon 2, 40W):
    Das Bild wird vor dem Dithering auf target_width reduziert (LANCZOS), gedithert und
    danach mit NEAREST wieder vergroessert. So werden die einzelnen Laserpunkte gross/klar
    genug, dass der Laser sie trennen kann - sonst verschmelzen sie zu einer Grauflaeche."""
    try:
        from PIL import Image as _IM
        ow, oh = proc.current_image.size
        if ow > target_width:
            nh = max(1, int(round(oh * target_width / float(ow))))
            proc.current_image = proc.current_image.resize((target_width, nh), _IM.LANCZOS)
    except Exception:
        pass
    proc.apply_dithering(method=method, threshold=threshold)
    try:
        from PIL import Image as _IM
        dw, dh = proc.current_image.size
        proc.current_image = proc.current_image.resize((dw * upscale, dh * upscale), _IM.NEAREST)
    except Exception:
        pass


@csrf_exempt
@cors_headers
def ai_optimize_public(request, unique_id):
    """OEFFENTLICH (Shop): optimiert das Foto fuer die Lasergravur. Versucht zuerst Nano Banana 2
    (generativ); falls das Modell kein Bild liefert (z.B. Safety-Filter bei Personen), Fallback auf
    die Analyse-Variante (Gemini Vision empfiehlt Werte -> PIL-Dithering). Speichert als 'image'."""
    if request.method == 'OPTIONS':
        return JsonResponse({})
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST'}, status=405)
    from django.conf import settings as dj_settings
    from django.contrib.auth import get_user_model
    image = get_object_or_404(FotogravurImage, unique_id=unique_id)
    src = image.original_image if (image.original_image and image.original_image.name) else None
    if not src:
        return JsonResponse({'success': False, 'error': 'Kein Original-Bild vorhanden'}, status=400)
    api_key = getattr(dj_settings, 'GEMINI_API_KEY', None)
    if not api_key:
        U = get_user_model()
        owner = U.objects.filter(username='taras').first() or U.objects.filter(is_superuser=True).exclude(gemini_api_key='').first()
        api_key = getattr(owner, 'gemini_api_key', None) if owner else None
    if not api_key:
        return JsonResponse({'success': False, 'error': 'Kein Gemini-Key'}, status=500)
    try:
        import io as _io, re as _re
        from PIL import Image as _PILImage
        from .image_processing import ImageProcessor
        pil = _PILImage.open(src)
        if pil.mode != 'RGB':
            pil = pil.convert('RGB')

        proc = None
        preview_url = None
        _block_reason = None
        model_used = 'gemini-3.1-flash-image-preview'

        # --- Versuch 1: generativ (Nano Banana 2) ---
        try:
            from imageforge.services.gemini_generator import GeminiGenerator
            gprompt = (
                "Convert this photograph into a clean black-and-white stipple/halftone artwork for LASER ENGRAVING "
                "on light cream ceramic. CRITICAL: the ENTIRE background must be 100% PURE WHITE and completely EMPTY "
                "- fully remove the studio / wall / backdrop, cut out ONLY the main subject(s) (the people), and put "
                "absolutely NO dots, shading, grey or texture anywhere in the background. Draw only the subject(s) "
                "with clear stippling and halftone dots; render dark areas (hair, dark clothing, shadows) as a DENSE "
                "DARK-GREY stipple/halftone (not a flat solid black blob) so they read dark but stay textured. Keep "
                "strong contrast and clearly defined edges so it engraves well. Keep the person(s), faces, pose and "
                "composition EXACTLY as in the reference."
            )
            try:
                src_path = src.path
            except Exception:
                src_path = src
            gres = GeminiGenerator(api_key).generate(prompt=gprompt, reference_images=[src_path], model='gemini-3.1-flash-image-preview')
            if gres.get('success') and gres.get('image_data'):
                rb = gres['image_data']
                raw = rb.split(',', 1)[1] if ',' in str(rb) else rb
                nb = _PILImage.open(_io.BytesIO(base64.b64decode(raw)))
                if nb.mode != 'RGB':
                    nb = nb.convert('RGB')
                proc = ImageProcessor(nb)
                proc.convert_to_grayscale()
                proc.adjust_brightness(1.12)
                # Tiefen gezielt anheben: dunkle Flaechen heller, Highlights unberuehrt
                _lut = []
                for _i in range(256):
                    _v = _i + (45.0 * (1.0 - _i / 200.0) if _i < 200 else 0.0)
                    if _v >= 230:
                        _v = 255
                    _lut.append(int(min(255, _v)))
                try:
                    if proc.current_image.mode != 'RGB':
                        proc.current_image = proc.current_image.convert('RGB')
                    proc.current_image = proc.current_image.point(_lut * 3)
                except Exception:
                    pass
                preview_url = proc.get_current_image_base64()
                _engrave_dither(proc, method='floyd-steinberg', threshold=127)
            else:
                _ge = str(gres.get('error', '')).lower()
                _pf_keys = ('public figure', 'public person', 'person of public', 'real people',
                            'real person', 'real individual', 'identifiable person', 'depict real',
                            'depicting real', 'celebrity', 'celebrities', 'known person',
                            'images of real', 'cannot create images of real', 'famous', 'politician',
                            'actual person', 'specific real')
                if any(_k in _ge for _k in _pf_keys):
                    _block_reason = 'public_figure'
        except Exception:
            proc = None

        # Als Person des oeffentlichen Lebens erkannt -> nicht bearbeiten, klare Meldung
        if _block_reason == 'public_figure':
            return JsonResponse({
                'success': False,
                'reason': 'public_figure',
                'error': ('Leider k\u00f6nnen wir dieses Bild nicht automatisch f\u00fcr die Gravur '
                          'bearbeiten, da es sich offenbar um eine Person des \u00f6ffentlichen Lebens '
                          'handelt. Bitte verwende ein privates Foto.')
            }, status=200)

        # Generative Freistellung nicht moeglich (Safety-Filter bei z.B. Minderjaehrigen o.ae.).
        # -> Signal an den Shop, die clientseitige body-pix-Freistellung zu verwenden.
        if proc is None:
            return JsonResponse({'success': False, 'reason': 'use_clientside'}, status=200)

        final_url = proc.get_current_image_base64()
        final_raw = final_url.split(',', 1)[1]
        image.image.save(f"{unique_id}.png", ContentFile(base64.b64decode(final_raw)), save=False)
        image.processing_settings = {'ai': model_used, 'dithering': 'floyd-steinberg'}
        image.save()
        _log_ai_usage('naturmacher', model_used, 'optimize', unique_id)
        return JsonResponse({'success': True, 'image_data': final_url, 'preview_image': preview_url or final_url})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'KI-Optimierung fehlgeschlagen: ' + str(e)}, status=500)
