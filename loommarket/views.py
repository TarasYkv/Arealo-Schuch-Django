"""
LoomMarket Views - B2B-Marketing mit Instagram-Integration.
"""
import io
import re
import json
import zipfile
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import (
    Business, BusinessImage, MockupTemplate,
    MarketingCampaign, SocialMediaCaption, SocialMediaPost
)
from .services import InstagramScraper, ImageSearcher, ImageProcessor, CaptionGenerator
from .services.image_processor import MockupGenerator

logger = logging.getLogger(__name__)


def remove_emojis(text: str) -> str:
    """
    Entfernt Emojis und andere nicht-BMP Unicode-Zeichen aus Text.
    MySQL utf8 (nicht utf8mb4) kann keine 4-Byte Unicode-Zeichen speichern.
    """
    if not text:
        return text
    # Entferne alle Zeichen außerhalb des BMP (Basic Multilingual Plane)
    # Das sind alle Zeichen mit Codepoint > 0xFFFF (4-Byte UTF-8)
    return ''.join(char for char in text if ord(char) <= 0xFFFF)


# ============================================================================
# DASHBOARD
# ============================================================================

@login_required
def dashboard(request):
    """LoomMarket Dashboard - Übersicht."""
    businesses = Business.objects.filter(user=request.user).order_by('-created_at')[:5]
    campaigns = MarketingCampaign.objects.filter(user=request.user).order_by('-created_at')[:5]
    templates = MockupTemplate.objects.filter(user=request.user, is_active=True).count()

    # Statistiken
    total_mockups = MarketingCampaign.objects.filter(user=request.user, mockup_image__isnull=False).count()
    total_posts = SocialMediaPost.objects.filter(campaign__user=request.user, status='published').count()

    stats = {
        'businesses': Business.objects.filter(user=request.user).count(),
        'campaigns': MarketingCampaign.objects.filter(user=request.user).count(),
        'mockups': total_mockups,
        'posts': total_posts,
    }

    context = {
        'recent_businesses': businesses,
        'recent_campaigns': campaigns,
        'stats': stats,
    }
    return render(request, 'loommarket/dashboard.html', context)


# ============================================================================
# BUSINESS MANAGEMENT
# ============================================================================

@login_required
def add_business(request):
    """Seite zum Hinzufügen eines neuen Unternehmens via Instagram."""
    if request.method == 'POST':
        # Check if this is an AJAX save request (has business_id = from JS form)
        business_id = request.POST.get('business_id')

        if business_id:
            # AJAX Save Request
            try:
                name = request.POST.get('name', '').strip()
                website = request.POST.get('website', '').strip()
                bio = request.POST.get('bio', '').strip()

                business = Business.objects.get(pk=business_id, user=request.user)
                business.name = remove_emojis(name) if name else business.name
                business.website = website or business.website
                business.bio = remove_emojis(bio) if bio else business.bio
                business.status = 'completed'
                business.save()

                # Return JSON for AJAX
                return JsonResponse({
                    'success': True,
                    'redirect_url': f'/loommarket/businesses/{business.id}/'
                })
            except Business.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Unternehmen nicht gefunden'}, status=404)
            except Exception as e:
                logger.exception(f"Error saving business: {e}")
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

        # Fallback: Regular form POST (ohne business_id)
        instagram_username = request.POST.get('instagram_username', '').strip()

        if not instagram_username:
            messages.error(request, "Bitte gib einen Instagram-Namen ein.")
            return render(request, 'loommarket/add_business.html')

        # Normalisieren
        scraper = InstagramScraper()
        normalized = scraper.normalize_username(instagram_username)

        # Prüfen ob bereits vorhanden
        if Business.objects.filter(user=request.user, instagram_username=normalized).exists():
            messages.warning(request, f"@{normalized} ist bereits in deiner Liste.")
            return redirect('loommarket:business_list')

        # Erstellen
        business = Business.objects.create(
            user=request.user,
            instagram_username=normalized,
            status='pending'
        )

        messages.success(request, f"@{normalized} wurde hinzugefügt.")
        return redirect('loommarket:business_detail', pk=business.pk)

    return render(request, 'loommarket/add_business.html')


@login_required
def business_list(request):
    """Liste aller gespeicherten Unternehmen."""
    businesses = Business.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'businesses': businesses,
    }
    return render(request, 'loommarket/business_list.html', context)


@login_required
def business_detail(request, pk):
    """Detailansicht eines Unternehmens mit Bildern."""
    business = get_object_or_404(Business, pk=pk, user=request.user)
    images = business.images.all().order_by('-is_logo', 'order', '-created_at')
    campaigns = business.campaigns.all().order_by('-created_at')[:5]

    context = {
        'business': business,
        'images': images,
        'campaigns': campaigns,
    }
    return render(request, 'loommarket/business_detail.html', context)


@login_required
@require_POST
def business_delete(request, pk):
    """Löscht ein Unternehmen."""
    business = get_object_or_404(Business, pk=pk, user=request.user)
    name = business.display_name
    business.delete()
    messages.success(request, f"{name} wurde gelöscht.")
    return redirect('loommarket:business_list')


# ============================================================================
# API: INSTAGRAM & IMAGE SEARCH
# ============================================================================

@login_required
@require_POST
def api_search_instagram(request):
    """API: Erstellt Business basierend auf Instagram-Username."""
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()

        if not username:
            return JsonResponse({'success': False, 'error': 'Bitte Instagram-Username angeben'}, status=400)

        # Normalisieren
        scraper = InstagramScraper()
        normalized = scraper.normalize_username(username)

        # Business erstellen oder holen
        business, created = Business.objects.get_or_create(
            user=request.user,
            instagram_username=normalized,
            defaults={
                'status': 'completed',
                'name': normalized,  # Username als Default-Name
            }
        )

        # Versuche Instagram-Daten zu scrapen (optional, kann fehlschlagen)
        try:
            profile_data = scraper.get_profile_data_for_business(normalized)
            if profile_data.get('success'):
                if profile_data.get('name'):
                    business.name = remove_emojis(profile_data['name'])
                if profile_data.get('bio'):
                    business.bio = remove_emojis(profile_data['bio'])
                if profile_data.get('website'):
                    business.website = profile_data['website']
                if profile_data.get('follower_count'):
                    business.follower_count = profile_data['follower_count']
                business.save()
        except Exception as e:
            logger.warning(f"Instagram scraping failed for @{normalized}: {e}")
            # Kein Fehler - wir haben das Business bereits erstellt

        return JsonResponse({
            'success': True,
            'business_id': business.id,
            'name': business.name or normalized,
            'bio': business.bio or '',
            'website': business.website or '',
            'follower_count': business.follower_count or 0,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        logger.exception(f"Error in api_search_instagram: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_search_images(request, business_id):
    """API: Sucht Logos und Produktbilder für ein Unternehmen."""
    try:
        business = get_object_or_404(Business, pk=business_id, user=request.user)

        # Suchbegriff: Name oder Instagram-Username
        search_term = business.name or business.instagram_username

        # Bildersuche - User-spezifische Google API-Keys verwenden
        google_api_key = getattr(request.user, 'google_search_api_key', None)
        google_cx = getattr(request.user, 'google_search_cx', None)
        searcher = ImageSearcher(google_api_key=google_api_key, google_cx=google_cx)
        results = searcher.search_and_download(
            company_name=search_term,
            max_logos=8,
            max_products=12
        )

        saved_images = []

        # Logos speichern
        for idx, logo_data in enumerate(results['logos']):
            img = BusinessImage.objects.create(
                business=business,
                image=logo_data['image'],
                source_url=logo_data.get('source_url'),
                source='search',
                is_logo=True if idx == 0 else False,  # Erstes Logo als Standard
                order=idx,
                width=logo_data.get('width', 0),
                height=logo_data.get('height', 0),
                file_size=logo_data.get('file_size', 0),
            )
            saved_images.append({
                'id': img.id,
                'url': img.image.url,
                'is_logo': img.is_logo,
                'type': 'logo',
            })

        # Produktbilder speichern
        for idx, product_data in enumerate(results['products']):
            img = BusinessImage.objects.create(
                business=business,
                image=product_data['image'],
                source_url=product_data.get('source_url'),
                source='search',
                is_logo=False,
                order=100 + idx,
                width=product_data.get('width', 0),
                height=product_data.get('height', 0),
                file_size=product_data.get('file_size', 0),
            )
            saved_images.append({
                'id': img.id,
                'url': img.image.url,
                'is_logo': img.is_logo,
                'type': 'product',
            })

        return JsonResponse({
            'success': True,
            'images': saved_images,
            'logos_count': len(results['logos']),
            'products_count': len(results['products']),
        })

    except Exception as e:
        logger.exception(f"Error in api_search_images: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_upload_image(request, business_id):
    """API: Manuelles Hochladen eines Bildes."""
    try:
        business = get_object_or_404(Business, pk=business_id, user=request.user)

        if 'image' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'Kein Bild hochgeladen'}, status=400)

        uploaded_file = request.FILES['image']
        is_logo = request.POST.get('is_logo', 'false').lower() == 'true'

        # Bild speichern
        img = BusinessImage.objects.create(
            business=business,
            image=uploaded_file,
            source='manual',
            is_logo=is_logo,
            order=0 if is_logo else 999,
        )

        # Bildgröße ermitteln
        from PIL import Image as PILImage
        try:
            pil_img = PILImage.open(img.image)
            img.width = pil_img.width
            img.height = pil_img.height
            img.file_size = img.image.size
            img.save()
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'image': {
                'id': img.id,
                'url': img.image.url,
                'is_logo': img.is_logo,
            }
        })

    except Exception as e:
        logger.exception(f"Error in api_upload_image: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_delete_image(request, image_id):
    """API: Löscht ein Bild."""
    try:
        image = get_object_or_404(BusinessImage, pk=image_id, business__user=request.user)
        image.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_set_logo(request, image_id):
    """API: Setzt ein Bild als Logo."""
    try:
        image = get_object_or_404(BusinessImage, pk=image_id, business__user=request.user)
        image.is_logo = True
        image.save()  # save() kümmert sich um das Entfernen anderer Logos
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_refresh_instagram(request, business_id):
    """API: Aktualisiert die Instagram-Profildaten."""
    try:
        business = get_object_or_404(Business, pk=business_id, user=request.user)

        # Instagram-Daten neu laden
        scraper = InstagramScraper()
        profile_data = scraper.scrape_profile(business.instagram_username)

        if profile_data['success']:
            # Daten aktualisieren (Emojis entfernen für MySQL-Kompatibilität)
            if profile_data.get('name'):
                business.name = remove_emojis(profile_data['name'])
            if profile_data.get('bio'):
                business.bio = remove_emojis(profile_data['bio'])
            if profile_data.get('website'):
                business.website = profile_data['website']
            if profile_data.get('follower_count'):
                business.follower_count = profile_data['follower_count']
            if profile_data.get('profile_picture_url'):
                business.profile_picture_url = profile_data['profile_picture_url']

            business.save()

            return JsonResponse({
                'success': True,
                'message': 'Instagram-Daten aktualisiert',
                'data': {
                    'name': business.name,
                    'bio': business.bio,
                    'website': business.website,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': profile_data.get('error', 'Konnte Instagram-Profil nicht laden')
            })

    except Exception as e:
        logger.exception(f"Error in api_refresh_instagram: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_refresh_impressum(request, business_id):
    """API: Aktualisiert das Impressum von Instagram und Website."""
    try:
        from .services import WebsiteScraper

        business = get_object_or_404(Business, pk=business_id, user=request.user)

        # Instagram Bio ist das "Impressum" auf Instagram
        business.impressum_instagram = business.bio

        # Website Impressum suchen
        if business.website:
            scraper = WebsiteScraper()
            result = scraper.find_impressum(business.website)

            if result['success']:
                business.impressum_website = result['impressum_text']
                business.impressum_website_url = result['impressum_url']
                business.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Impressum aktualisiert',
                    'impressum_found': True,
                })
            else:
                business.impressum_website = None
                business.impressum_website_url = None
                business.save()
                return JsonResponse({
                    'success': True,
                    'message': result.get('error', 'Kein Impressum gefunden'),
                    'impressum_found': False,
                })
        else:
            business.save()
            return JsonResponse({
                'success': True,
                'message': 'Keine Website vorhanden',
                'impressum_found': False,
            })

    except Exception as e:
        logger.exception(f"Error in api_refresh_impressum: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================================
# MOCKUP TEMPLATES
# ============================================================================

@login_required
def template_list(request):
    """Liste aller Mockup-Vorlagen."""
    templates = MockupTemplate.objects.filter(user=request.user).order_by('name')

    context = {
        'templates': templates,
    }
    return render(request, 'loommarket/template_list.html', context)


@login_required
def template_create(request):
    """Neue Mockup-Vorlage erstellen."""
    # ImageForge Bilder laden
    from imageforge.models import ImageGeneration, ProductMockup

    # Generierte Bilder (für beide Felder nutzbar)
    imageforge_generated = ImageGeneration.objects.filter(
        user=request.user,
        generated_image__isnull=False
    ).exclude(generated_image='').order_by('-created_at')[:30]

    # ProductMockup: Original-Produktbilder (ohne Gravur)
    product_mockups = ProductMockup.objects.filter(
        user=request.user
    ).exclude(product_image='').order_by('-created_at')[:30]

    # Kombinierte Listen für Template
    # Blank: Original-Produktbilder + alle generierten
    imageforge_blank_images = []
    for pm in product_mockups:
        if pm.product_image:
            imageforge_blank_images.append({
                'id': f'pm_{pm.id}',
                'url': pm.product_image.url,
                'type': 'product_mockup',
                'name': pm.name or 'Produktbild',
                'date': pm.created_at,
            })

    for ig in imageforge_generated:
        imageforge_blank_images.append({
            'id': f'ig_{ig.id}',
            'url': ig.generated_image.url,
            'type': 'generation',
            'name': 'Generiert',
            'date': ig.created_at,
        })

    # Engraved: Style-Referenzen + generierte Mockups + alle generierten
    imageforge_engraved_images = []
    for pm in product_mockups:
        if pm.style_reference_image:
            imageforge_engraved_images.append({
                'id': f'pm_style_{pm.id}',
                'url': pm.style_reference_image.url,
                'type': 'style_reference',
                'name': pm.name or 'Gravur-Beispiel',
                'date': pm.created_at,
            })
        if pm.mockup_image:
            imageforge_engraved_images.append({
                'id': f'pm_gen_{pm.id}',
                'url': pm.mockup_image.url,
                'type': 'generated_mockup',
                'name': pm.name or 'Generiertes Mockup',
                'date': pm.created_at,
            })

    for ig in imageforge_generated:
        imageforge_engraved_images.append({
            'id': f'ig_{ig.id}',
            'url': ig.generated_image.url,
            'type': 'generation',
            'name': 'Generiert',
            'date': ig.created_at,
        })

    context = {
        'imageforge_blank_images': imageforge_blank_images,
        'imageforge_engraved_images': imageforge_engraved_images,
    }

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        default_background_prompt = request.POST.get('default_background_prompt', '').strip()

        # ImageForge IDs (Format: pm_X, pm_style_X, pm_gen_X, ig_X)
        imageforge_blank_id = request.POST.get('imageforge_blank_id', '').strip()
        imageforge_engraved_id = request.POST.get('imageforge_engraved_id', '').strip()

        if not name:
            messages.error(request, "Bitte gib einen Namen ein.")
            return render(request, 'loommarket/template_form.html', context)

        # Bilder prüfen: entweder Upload oder ImageForge
        has_blank = 'product_image_blank' in request.FILES or imageforge_blank_id
        has_engraved = 'product_image_engraved' in request.FILES or imageforge_engraved_id

        if not has_blank or not has_engraved:
            messages.error(request, "Bitte wähle beide Produktbilder aus (Upload oder ImageForge).")
            return render(request, 'loommarket/template_form.html', context)

        # Template erstellen
        template = MockupTemplate(
            user=request.user,
            name=name,
            description=description,
            default_background_prompt=default_background_prompt,
        )

        # Hilfsfunktion um Bild aus ID zu holen
        def get_image_from_id(img_id):
            if img_id.startswith('pm_style_'):
                pk = img_id.replace('pm_style_', '')
                pm = ProductMockup.objects.get(pk=pk, user=request.user)
                return pm.style_reference_image
            elif img_id.startswith('pm_gen_'):
                pk = img_id.replace('pm_gen_', '')
                pm = ProductMockup.objects.get(pk=pk, user=request.user)
                return pm.mockup_image
            elif img_id.startswith('pm_'):
                pk = img_id.replace('pm_', '')
                pm = ProductMockup.objects.get(pk=pk, user=request.user)
                return pm.product_image
            elif img_id.startswith('ig_'):
                pk = img_id.replace('ig_', '')
                ig = ImageGeneration.objects.get(pk=pk, user=request.user)
                return ig.generated_image
            return None

        # Blank-Bild setzen
        if 'product_image_blank' in request.FILES:
            template.product_image_blank = request.FILES['product_image_blank']
        elif imageforge_blank_id:
            try:
                template.product_image_blank = get_image_from_id(imageforge_blank_id)
            except (ProductMockup.DoesNotExist, ImageGeneration.DoesNotExist):
                messages.error(request, "ImageForge-Bild nicht gefunden.")
                return render(request, 'loommarket/template_form.html', context)

        # Engraved-Bild setzen
        if 'product_image_engraved' in request.FILES:
            template.product_image_engraved = request.FILES['product_image_engraved']
        elif imageforge_engraved_id:
            try:
                template.product_image_engraved = get_image_from_id(imageforge_engraved_id)
            except (ProductMockup.DoesNotExist, ImageGeneration.DoesNotExist):
                messages.error(request, "ImageForge-Bild nicht gefunden.")
                return render(request, 'loommarket/template_form.html', context)

        template.save()
        messages.success(request, f"Vorlage '{name}' wurde erstellt.")
        return redirect('loommarket:template_list')

    return render(request, 'loommarket/template_form.html', context)


@login_required
def template_edit(request, pk):
    """Mockup-Vorlage bearbeiten."""
    from imageforge.models import ImageGeneration, ProductMockup

    template = get_object_or_404(MockupTemplate, pk=pk, user=request.user)

    # Gleiche Bildlisten wie bei template_create
    imageforge_generated = ImageGeneration.objects.filter(
        user=request.user,
        generated_image__isnull=False
    ).exclude(generated_image='').order_by('-created_at')[:30]

    product_mockups = ProductMockup.objects.filter(
        user=request.user
    ).exclude(product_image='').order_by('-created_at')[:30]

    # Blank-Bilder
    imageforge_blank_images = []
    for pm in product_mockups:
        if pm.product_image:
            imageforge_blank_images.append({
                'id': f'pm_{pm.id}',
                'url': pm.product_image.url,
                'type': 'product_mockup',
                'name': pm.name or 'Produktbild',
                'date': pm.created_at,
            })
    for ig in imageforge_generated:
        imageforge_blank_images.append({
            'id': f'ig_{ig.id}',
            'url': ig.generated_image.url,
            'type': 'generation',
            'name': 'Generiert',
            'date': ig.created_at,
        })

    # Engraved-Bilder
    imageforge_engraved_images = []
    for pm in product_mockups:
        if pm.style_reference_image:
            imageforge_engraved_images.append({
                'id': f'pm_style_{pm.id}',
                'url': pm.style_reference_image.url,
                'type': 'style_reference',
                'name': pm.name or 'Gravur-Beispiel',
                'date': pm.created_at,
            })
        if pm.mockup_image:
            imageforge_engraved_images.append({
                'id': f'pm_gen_{pm.id}',
                'url': pm.mockup_image.url,
                'type': 'generated_mockup',
                'name': pm.name or 'Generiertes Mockup',
                'date': pm.created_at,
            })
    for ig in imageforge_generated:
        imageforge_engraved_images.append({
            'id': f'ig_{ig.id}',
            'url': ig.generated_image.url,
            'type': 'generation',
            'name': 'Generiert',
            'date': ig.created_at,
        })

    # Hilfsfunktion
    def get_image_from_id(img_id):
        if img_id.startswith('pm_style_'):
            pk = img_id.replace('pm_style_', '')
            pm = ProductMockup.objects.get(pk=pk, user=request.user)
            return pm.style_reference_image
        elif img_id.startswith('pm_gen_'):
            pk = img_id.replace('pm_gen_', '')
            pm = ProductMockup.objects.get(pk=pk, user=request.user)
            return pm.mockup_image
        elif img_id.startswith('pm_'):
            pk = img_id.replace('pm_', '')
            pm = ProductMockup.objects.get(pk=pk, user=request.user)
            return pm.product_image
        elif img_id.startswith('ig_'):
            pk = img_id.replace('ig_', '')
            ig = ImageGeneration.objects.get(pk=pk, user=request.user)
            return ig.generated_image
        return None

    if request.method == 'POST':
        template.name = request.POST.get('name', template.name).strip()
        template.description = request.POST.get('description', '').strip()
        template.default_background_prompt = request.POST.get('default_background_prompt', '').strip()
        template.is_active = request.POST.get('is_active', 'off') == 'on'

        imageforge_blank_id = request.POST.get('imageforge_blank_id', '').strip()
        imageforge_engraved_id = request.POST.get('imageforge_engraved_id', '').strip()

        # Blank-Bild aktualisieren
        if 'product_image_blank' in request.FILES:
            template.product_image_blank = request.FILES['product_image_blank']
        elif imageforge_blank_id:
            try:
                template.product_image_blank = get_image_from_id(imageforge_blank_id)
            except (ProductMockup.DoesNotExist, ImageGeneration.DoesNotExist):
                pass

        # Engraved-Bild aktualisieren
        if 'product_image_engraved' in request.FILES:
            template.product_image_engraved = request.FILES['product_image_engraved']
        elif imageforge_engraved_id:
            try:
                template.product_image_engraved = get_image_from_id(imageforge_engraved_id)
            except (ProductMockup.DoesNotExist, ImageGeneration.DoesNotExist):
                pass

        template.save()
        messages.success(request, f"Vorlage '{template.name}' wurde aktualisiert.")
        return redirect('loommarket:template_list')

    context = {
        'template': template,
        'imageforge_blank_images': imageforge_blank_images,
        'imageforge_engraved_images': imageforge_engraved_images,
        'edit_mode': True,
    }
    return render(request, 'loommarket/template_form.html', context)


@login_required
@require_POST
def template_delete(request, pk):
    """Mockup-Vorlage löschen."""
    template = get_object_or_404(MockupTemplate, pk=pk, user=request.user)
    name = template.name
    template.delete()
    messages.success(request, f"Vorlage '{name}' wurde gelöscht.")
    return redirect('loommarket:template_list')


# ============================================================================
# CAMPAIGNS
# ============================================================================

@login_required
def campaign_list(request):
    """Liste aller Kampagnen."""
    campaigns = MarketingCampaign.objects.filter(user=request.user).order_by('-created_at')
    businesses = Business.objects.filter(user=request.user).order_by('name')

    context = {
        'campaigns': campaigns,
        'businesses': businesses,
    }
    return render(request, 'loommarket/campaign_list.html', context)


@login_required
def campaign_create(request, business_id):
    """Neue Kampagne für ein Unternehmen erstellen."""
    business = get_object_or_404(Business, pk=business_id, user=request.user)
    templates = MockupTemplate.objects.filter(user=request.user, is_active=True)
    images = business.images.all().order_by('-is_logo', 'order')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        template_id = request.POST.get('selected_template') or request.POST.get('template_id')
        design_image_id = request.POST.get('selected_image') or request.POST.get('design_image_id')
        background_prompt = request.POST.get('background_prompt', '').strip()

        template = None
        if template_id:
            template = get_object_or_404(MockupTemplate, pk=template_id, user=request.user)

        design_image = None
        if design_image_id:
            design_image = get_object_or_404(BusinessImage, pk=design_image_id, business=business)

        campaign = MarketingCampaign.objects.create(
            user=request.user,
            name=name or f"Kampagne {business.display_name}",
            business=business,
            template=template,
            design_image=design_image,
            background_prompt=background_prompt or (template.default_background_prompt if template else ''),
            status='draft',
        )

        messages.success(request, "Kampagne wurde erstellt.")
        return redirect('loommarket:campaign_detail', pk=campaign.pk)

    context = {
        'business': business,
        'templates': templates,
        'images': images,
    }
    return render(request, 'loommarket/campaign_create.html', context)


@login_required
def campaign_detail(request, pk):
    """Kampagnen-Detail mit Workflow."""
    campaign = get_object_or_404(MarketingCampaign, pk=pk, user=request.user)
    captions = campaign.captions.all()
    posts = campaign.posts.all()

    # Plattformen für Caption-Generierung
    available_platforms = [
        ('instagram', 'Instagram', 'bi-instagram'),
        ('facebook', 'Facebook', 'bi-facebook'),
        ('linkedin', 'LinkedIn', 'bi-linkedin'),
        ('pinterest', 'Pinterest', 'bi-pinterest'),
        ('twitter', 'Twitter/X', 'bi-twitter-x'),
        ('bluesky', 'Bluesky', 'bi-cloud'),
    ]

    # Check if Upload-Post API is configured
    has_upload_api = bool(
        getattr(request.user, 'upload_post_api_key', None) and
        getattr(request.user, 'upload_post_user_id', None)
    )

    context = {
        'campaign': campaign,
        'captions': captions,
        'posts': posts,
        'available_platforms': available_platforms,
        'has_upload_api': has_upload_api,
    }
    return render(request, 'loommarket/campaign_detail.html', context)


@login_required
@require_POST
def campaign_delete(request, pk):
    """Kampagne löschen."""
    campaign = get_object_or_404(MarketingCampaign, pk=pk, user=request.user)
    campaign.delete()
    messages.success(request, "Kampagne wurde gelöscht.")
    return redirect('loommarket:campaign_list')


# ============================================================================
# API: CAMPAIGN ACTIONS
# ============================================================================

@login_required
@require_POST
def api_generate_mockup(request, campaign_id):
    """API: Generiert Mockup-Bilder für eine Kampagne."""
    try:
        # Format aus Request lesen (feed, story, both)
        if request.body:
            try:
                data = json.loads(request.body)
                mockup_format = data.get('format', 'both')
            except json.JSONDecodeError:
                mockup_format = 'both'
        else:
            mockup_format = 'both'

        campaign = get_object_or_404(MarketingCampaign, pk=campaign_id, user=request.user)

        if not campaign.template:
            return JsonResponse({'success': False, 'error': 'Keine Vorlage ausgewählt'}, status=400)

        if not campaign.design_image:
            return JsonResponse({'success': False, 'error': 'Kein Design-Bild ausgewählt'}, status=400)

        # Status aktualisieren
        campaign.status = 'mockup_generating'
        campaign.save()

        # Mockup generieren
        generator = MockupGenerator(request.user)

        # Bestimme welche Formate generiert werden sollen
        generate_feed = mockup_format in ('feed', 'both')
        generate_story = mockup_format in ('story', 'both')

        result = generator.generate_mockup(
            template=campaign.template,
            design_image=campaign.design_image,
            background_prompt=campaign.background_prompt,
            generate_feed=generate_feed,
            generate_story=generate_story,
        )

        if result['success']:
            import base64
            from django.core.files.base import ContentFile

            if result.get('feed_image'):
                # Base64-String zu ContentFile konvertieren
                image_data = base64.b64decode(result['feed_image'])
                campaign.mockup_image.save(
                    f'mockup_{campaign.id}_feed.jpg',
                    ContentFile(image_data),
                    save=False
                )
            if result.get('story_image'):
                # Base64-String zu ContentFile konvertieren
                image_data = base64.b64decode(result['story_image'])
                campaign.mockup_image_story.save(
                    f'mockup_{campaign.id}_story.jpg',
                    ContentFile(image_data),
                    save=False
                )

            campaign.status = 'mockup_ready'
            campaign.error_message = None
        else:
            campaign.status = 'failed'
            campaign.error_message = result['error']

        campaign.save()

        return JsonResponse({
            'success': result['success'],
            'mockup_url': campaign.mockup_image.url if campaign.mockup_image else None,
            'story_url': campaign.mockup_image_story.url if campaign.mockup_image_story else None,
            'error': result.get('error'),
        })

    except Exception as e:
        logger.exception(f"Error generating mockup: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_generate_captions(request, campaign_id):
    """API: Generiert Captions für alle Plattformen."""
    try:
        # JSON-Body optional - Standardwerte verwenden wenn leer
        if request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
        platforms = data.get('platforms', ['instagram', 'facebook', 'linkedin'])

        campaign = get_object_or_404(MarketingCampaign, pk=campaign_id, user=request.user)

        # Caption Generator
        generator = CaptionGenerator(request.user)

        # Produkt-Name aus Template
        product_name = campaign.template.name if campaign.template else "Personalisiertes Produkt"

        # Captions generieren
        results = generator.generate_all_captions(
            business_name=campaign.business.display_name,
            product_name=product_name,
            instagram_username=campaign.business.instagram_username,
            platforms=platforms,
        )

        saved_captions = []

        for platform, caption_data in results.items():
            if caption_data['success']:
                # Existierende Caption aktualisieren oder neue erstellen
                caption, created = SocialMediaCaption.objects.update_or_create(
                    campaign=campaign,
                    platform=platform,
                    defaults={
                        'title': caption_data.get('title'),
                        'caption_text': caption_data.get('caption_text'),
                        'hashtags': caption_data.get('hashtags'),
                        'mention_username': campaign.business.instagram_username,
                    }
                )

                saved_captions.append({
                    'platform': platform,
                    'title': caption.title,
                    'caption_text': caption.caption_text,
                    'hashtags': caption.hashtags,
                })

        # Status aktualisieren
        if saved_captions:
            campaign.status = 'ready'
            campaign.save()

        return JsonResponse({
            'success': True,
            'captions': saved_captions,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        logger.exception(f"Error generating captions: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================================
# POSTS
# ============================================================================

@login_required
@require_POST
def api_publish_post(request, post_id):
    """API: Veröffentlicht einen Post über Upload-Post.com."""
    try:
        import requests as http_requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        import base64

        post = get_object_or_404(SocialMediaPost, pk=post_id, campaign__user=request.user)
        campaign = post.campaign

        # Upload-Post API-Key prüfen
        upload_post_api_key = getattr(request.user, 'upload_post_api_key', None)
        upload_post_user_id = getattr(request.user, 'upload_post_user_id', None)

        if not upload_post_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post API-Key nicht konfiguriert. Bitte in API-Einstellungen hinzufügen.'
            }, status=400)

        if not upload_post_user_id:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post User-ID nicht konfiguriert.'
            }, status=400)

        # Bild auswählen (Story oder Feed)
        if post.post_type == 'story' and campaign.mockup_image_story:
            image_file = campaign.mockup_image_story
        else:
            image_file = campaign.mockup_image

        if not image_file:
            return JsonResponse({'success': False, 'error': 'Kein Mockup-Bild vorhanden'}, status=400)

        # Bild als Base64
        with image_file.open('rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # API-Request vorbereiten
        api_url = 'https://api.upload-post.com/api/upload_photos'
        api_key_clean = ''.join(c for c in upload_post_api_key if c.isascii() and c.isprintable()).strip()

        headers = {
            'Authorization': f'Apikey {api_key_clean}',
        }

        # Form-Daten
        form_data = [
            ('user', upload_post_user_id),
            ('title', post.post_text[:2200]),  # Instagram-Limit
            ('platform[]', post.platform),
        ]

        # Story-Parameter (falls unterstützt)
        if post.post_type == 'story':
            form_data.append(('type', 'story'))

        files = {
            'file': (f'mockup_{campaign.id}.jpg', base64.b64decode(image_base64), 'image/jpeg')
        }

        # Session mit Retry
        session = http_requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        # Request senden
        post.status = 'publishing'
        post.save()

        response = session.post(
            api_url,
            data=form_data,
            files=files,
            headers=headers,
            timeout=60
        )

        if response.status_code in [200, 201, 202]:
            result = response.json()
            post.status = 'published'
            post.external_post_id = str(result.get('id', ''))
            post.published_at = timezone.now()
            post.error_message = None
            post.save()

            # Kampagnen-Status aktualisieren
            campaign.status = 'posted'
            campaign.save()

            return JsonResponse({
                'success': True,
                'message': f'Post auf {post.get_platform_display()} veröffentlicht!',
                'external_id': post.external_post_id,
            })
        else:
            error_msg = f"Fehler {response.status_code}: {response.text[:200]}"
            post.status = 'failed'
            post.error_message = error_msg
            post.save()

            return JsonResponse({'success': False, 'error': error_msg}, status=500)

    except Exception as e:
        logger.exception(f"Error publishing post: {e}")
        if 'post' in locals():
            post.status = 'failed'
            post.error_message = str(e)
            post.save()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def download_post(request, post_id):
    """Download: Bild + Caption als ZIP."""
    post = get_object_or_404(SocialMediaPost, pk=post_id, campaign__user=request.user)
    campaign = post.campaign

    # Bild auswählen
    if post.post_type == 'story' and campaign.mockup_image_story:
        image_file = campaign.mockup_image_story
    else:
        image_file = campaign.mockup_image

    if not image_file:
        messages.error(request, "Kein Mockup-Bild vorhanden.")
        return redirect('loommarket:campaign_detail', pk=campaign.pk)

    # ZIP erstellen
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Bild hinzufügen
        with image_file.open('rb') as f:
            zf.writestr(f'mockup_{post.platform}.jpg', f.read())

        # Caption als Text-Datei
        caption_text = post.post_text
        zf.writestr(f'caption_{post.platform}.txt', caption_text.encode('utf-8'))

    buffer.seek(0)

    # Response
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    filename = f"loommarket_{campaign.business.instagram_username}_{post.platform}.zip"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required
def download_all(request, campaign_id):
    """Download: Alle Mockups + Captions als ZIP."""
    campaign = get_object_or_404(MarketingCampaign, pk=campaign_id, user=request.user)

    if not campaign.mockup_image:
        messages.error(request, "Kein Mockup-Bild vorhanden.")
        return redirect('loommarket:campaign_detail', pk=campaign.pk)

    # ZIP erstellen
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Feed-Mockup
        if campaign.mockup_image:
            with campaign.mockup_image.open('rb') as f:
                zf.writestr('mockup_feed.jpg', f.read())

        # Story-Mockup
        if campaign.mockup_image_story:
            with campaign.mockup_image_story.open('rb') as f:
                zf.writestr('mockup_story.jpg', f.read())

        # Alle Captions
        for caption in campaign.captions.all():
            caption_text = caption.full_caption
            zf.writestr(f'caption_{caption.platform}.txt', caption_text.encode('utf-8'))

    buffer.seek(0)

    # Response
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    filename = f"loommarket_{campaign.business.instagram_username}_all.zip"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
