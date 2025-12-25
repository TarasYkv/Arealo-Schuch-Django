from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404, StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST
from .models import Video, UserStorage
from .forms import VideoUploadForm
from .utils import generate_video_thumbnail, get_video_duration
# Tasks removed - direct video hosting without conversion
import os
import logging
import mimetypes
import requests
from wsgiref.util import FileWrapper


@login_required
def video_list(request):
    """List all videos for the current user"""
    from .subscription_sync import StorageSubscriptionSync
    from .storage_management import StorageOverageService
    
    videos = Video.objects.filter(user=request.user)
    user_storage = StorageSubscriptionSync.sync_user_storage(request.user)
    
    # Check for storage overage and handle accordingly
    StorageOverageService.check_user_storage_overage(request.user)
    # Refresh storage object to get updated restriction info
    user_storage.refresh_from_db()
    
    context = {
        'videos': videos,
        'user_storage': user_storage,
        'used_percentage': (user_storage.used_storage / user_storage.max_storage * 100) if user_storage.max_storage > 0 else 0,
        'is_storage_exceeded': user_storage.is_storage_exceeded(),
        'restriction_message': user_storage.get_restriction_message(),
        'can_upload': user_storage.can_upload(),
        'can_share': user_storage.can_share(),
    }
    return render(request, 'videos/video_list.html', context)


@login_required
def video_upload(request):
    """Handle video upload"""
    from .subscription_sync import StorageSubscriptionSync
    from .storage_management import StorageOverageService
    
    user_storage = StorageSubscriptionSync.sync_user_storage(request.user)
    
    # Check for storage overage and restrictions
    StorageOverageService.check_user_storage_overage(request.user)
    user_storage.refresh_from_db()
    
    # Block upload if user can't upload due to restrictions
    if not user_storage.can_upload():
        messages.error(request, user_storage.get_restriction_message())
        return redirect('videos:list')
    
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.user = request.user
            
            # Check file size
            file_size = request.FILES['video_file'].size
            if not user_storage.has_storage_available(file_size):
                available_mb = (user_storage.max_storage - user_storage.used_storage) / (1024 * 1024)
                needed_mb = file_size / (1024 * 1024)
                total_needed_mb = (user_storage.used_storage + file_size) / (1024 * 1024)
                
                error_message = (
                    f'Nicht genügend Speicherplatz verfügbar. '
                    f'Verfügbar: {available_mb:.1f} MB, '
                    f'benötigt: {needed_mb:.1f} MB '
                    f'(gesamt: {total_needed_mb:.1f} MB von {user_storage.get_max_storage_mb():.0f} MB). '
                    f'Bitte löschen Sie Videos oder erweitern Sie Ihren Tarif.'
                )
                messages.error(request, error_message)
                return redirect('videos:upload')
            
            video.file_size = file_size
            video.save()
            
            # Generate thumbnail
            try:
                generate_video_thumbnail(video)
                # Try to get video duration
                video.duration = get_video_duration(video.video_file.path)
                video.save()
            except Exception as e:
                # Log error but don't fail the upload
                print(f"Error generating thumbnail: {e}")
            
            # Update user storage immediately
            user_storage.used_storage += file_size
            user_storage.save()
            
            messages.success(request, 'Video erfolgreich hochgeladen!')
            return redirect('videos:list')
    else:
        form = VideoUploadForm()
    
    context = {
        'form': form,
        'user_storage': user_storage,
        'used_percentage': (user_storage.used_storage / user_storage.max_storage * 100) if user_storage.max_storage > 0 else 0,
        'available_storage_bytes': user_storage.max_storage - user_storage.used_storage,
        'can_upload': user_storage.can_upload(),
        'restriction_message': user_storage.get_restriction_message(),
    }
    return render(request, 'videos/video_upload.html', context)


@login_required
def video_detail(request, video_id):
    """Video detail view for owner"""
    from .subscription_sync import StorageSubscriptionSync
    from .storage_management import StorageOverageService
    
    video = get_object_or_404(Video, id=video_id, user=request.user)
    user_storage = StorageSubscriptionSync.sync_user_storage(request.user)
    
    # Check for storage overage and restrictions
    StorageOverageService.check_user_storage_overage(request.user)
    user_storage.refresh_from_db()
    
    context = {
        'video': video,
        'user_storage': user_storage,
        'can_share': user_storage.can_share(),
        'restriction_message': user_storage.get_restriction_message(),
    }
    return render(request, 'videos/video_detail.html', context)


def video_view(request, unique_id):
    """Public video view page"""
    video = get_object_or_404(Video, unique_id=unique_id)
    
    # Check if the video owner has sharing restrictions
    try:
        user_storage, created = UserStorage.objects.get_or_create(user=video.user)
        if not user_storage.can_share():
            return render(request, 'videos/video_restricted.html', {
                'video': video,
                'restriction_message': 'Dieses Video ist aufgrund von Speicherüberschreitung nicht verfügbar.'
            })
    except Exception:
        pass  # If storage check fails, allow access
    
    return render(request, 'videos/video_view.html', {'video': video})


@xframe_options_exempt
def video_embed(request, unique_id):
    """Embeddable video player"""
    video = get_object_or_404(Video, unique_id=unique_id)
    
    # Check if the video owner has sharing restrictions
    try:
        user_storage, created = UserStorage.objects.get_or_create(user=video.user)
        if not user_storage.can_share():
            return render(request, 'videos/video_embed_restricted.html', {
                'video': video,
                'restriction_message': 'Video nicht verfügbar'
            })
    except Exception:
        pass  # If storage check fails, allow access
    
    return render(request, 'videos/video_embed.html', {'video': video})


def video_stream(request, unique_id):
    """Stream video file - supports external embedding (Shopify, etc.)"""
    video = get_object_or_404(Video, unique_id=unique_id)

    # Check if the video owner has sharing restrictions
    try:
        user_storage, created = UserStorage.objects.get_or_create(user=video.user)
        if not user_storage.can_share():
            return HttpResponse('Video nicht verfügbar', status=403)
    except Exception:
        pass  # If storage check fails, allow access

    # Use the uploaded video file directly
    video_file = video.video_file
    path = video_file.path

    # Get file size and content type
    file_size = os.path.getsize(path)
    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or 'video/mp4'

    # Handle range requests for video seeking
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = range_header.replace('bytes=', '').split('-') if range_header else None

    if range_match:
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else file_size - 1

        # Open file and seek to start position
        file_handle = open(path, 'rb')
        file_handle.seek(start)

        # Create response with partial content
        response = StreamingHttpResponse(
            FileWrapper(file_handle, 8192),
            status=206,
            content_type=content_type
        )
        response['Content-Length'] = str(end - start + 1)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    else:
        # Full file response
        response = StreamingHttpResponse(
            FileWrapper(open(path, 'rb'), 8192),
            content_type=content_type
        )
        response['Content-Length'] = str(file_size)

    response['Accept-Ranges'] = 'bytes'

    # CORS headers for external embedding (Shopify, etc.)
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Range'
    response['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range, Accept-Ranges'

    # Track video access
    video.track_access()

    return response


@login_required
def video_delete(request, video_id):
    """Delete video"""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    
    if request.method == 'POST':
        # Update user storage
        user_storage = UserStorage.objects.get(user=request.user)
        user_storage.used_storage -= video.file_size
        user_storage.save()
        
        # Delete video file
        if video.video_file:
            video.video_file.delete()
        
        # Delete thumbnail
        if video.thumbnail:
            video.thumbnail.delete()
        
        video.delete()
        messages.success(request, 'Video erfolgreich gelöscht.')
        return redirect('videos:list')
    
    return render(request, 'videos/video_confirm_delete.html', {'video': video})


@login_required
def storage_management(request):
    """Storage management page for users with Stripe integration"""
    from .subscription_sync import StorageSubscriptionSync
    
    # Sync storage with Stripe subscription
    user_storage = StorageSubscriptionSync.sync_user_storage(request.user)
    plan_info = StorageSubscriptionSync.get_user_plan_info(request.user)
    available_plans = StorageSubscriptionSync.get_available_plans()
    
    videos = Video.objects.filter(user=request.user)
    
    context = {
        'user_storage': user_storage,
        'videos': videos,
        'video_count': videos.count(),
        'plan_info': plan_info,
        'available_plans': available_plans,
        'used_percentage': plan_info['used_percentage'],
        'available_space_mb': plan_info['available_mb'],
    }
    return render(request, 'videos/storage_management.html', context)


@login_required
@require_POST
def set_video_priority(request, video_id):
    """Set video priority for archiving decisions"""
    video = get_object_or_404(Video, id=video_id, user=request.user)
    
    priority = request.POST.get('priority')
    try:
        priority = int(priority)
        if priority in [choice[0] for choice in Video.PRIORITY_CHOICES]:
            video.priority = priority
            video.save()
            
            priority_name = dict(Video.PRIORITY_CHOICES)[priority]
            
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'priority': priority,
                    'priority_name': priority_name
                })
            
            messages.success(request, f'Priorität für "{video.title}" auf "{priority_name}" gesetzt.')
        else:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'success': False, 'error': 'Invalid priority'})
            messages.error(request, 'Ungültige Priorität.')
    except (ValueError, TypeError):
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'success': False, 'error': 'Invalid priority value'})
        messages.error(request, 'Ungültige Priorität.')
    
    return redirect('videos:list')


@login_required
def video_priority_manager(request):
    """Video priority management page"""
    from .storage_management import VideoArchivingService
    
    user_storage, created = UserStorage.objects.get_or_create(user=request.user)
    
    # Get all videos with archival scores
    archivable_videos = VideoArchivingService.get_archivable_videos_for_user(request.user)
    
    # Calculate potential archiving scenarios
    overage_mb = max(0, user_storage.get_overage_amount_mb())
    
    context = {
        'user_storage': user_storage,
        'archivable_videos': archivable_videos,
        'overage_mb': overage_mb,
        'is_storage_exceeded': user_storage.is_storage_exceeded(),
        'priority_choices': Video.PRIORITY_CHOICES,
        'total_videos': len(archivable_videos),
    }
    
    if overage_mb > 0:
        # Show which videos would be archived if needed
        videos_to_archive = VideoArchivingService.get_archivable_videos_for_user(
            request.user, 
            target_mb=overage_mb + 10  # Extra buffer
        )
        context['videos_to_archive'] = videos_to_archive
        context['archive_count'] = len(videos_to_archive)
        context['archive_size_mb'] = sum(v['size_mb'] for v in videos_to_archive)
    
    return render(request, 'videos/priority_manager.html', context)


@login_required
def archived_videos(request):
    """View archived videos"""
    archived_videos = Video.objects.filter(user=request.user, status='archived').order_by('-archived_at')
    user_storage, created = UserStorage.objects.get_or_create(user=request.user)
    
    context = {
        'archived_videos': archived_videos,
        'user_storage': user_storage,
        'archived_count': archived_videos.count(),
    }
    return render(request, 'videos/archived_videos.html', context)


@login_required
@require_POST 
def restore_video(request, video_id):
    """Restore an archived video"""
    video = get_object_or_404(Video, id=video_id, user=request.user, status='archived')
    user_storage, created = UserStorage.objects.get_or_create(user=request.user)
    
    # Check if user has enough storage space
    if user_storage.used_storage + video.file_size > user_storage.max_storage:
        available_mb = (user_storage.max_storage - user_storage.used_storage) / (1024 * 1024)
        video_mb = video.file_size / (1024 * 1024)
        
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': False,
                'error': f'Nicht genügend Speicherplatz. Verfügbar: {available_mb:.1f}MB, benötigt: {video_mb:.1f}MB'
            })
        
        messages.error(request, f'Nicht genügend Speicherplatz für Wiederherstellung. Verfügbar: {available_mb:.1f}MB, benötigt: {video_mb:.1f}MB')
        return redirect('videos:archived')
    
    # Restore video
    video.restore()
    user_storage.used_storage += video.file_size
    user_storage.save()
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({
            'success': True,
            'message': f'Video "{video.title}" wiederhergestellt.'
        })
    
    messages.success(request, f'Video "{video.title}" erfolgreich wiederhergestellt.')
    return redirect('videos:archived')


@login_required
def storage_optimizer(request):
    """Storage optimization tool - show large/old videos for deletion"""
    from django.db.models import Q
    from django.utils import timezone
    from datetime import timedelta
    
    user_storage, created = UserStorage.objects.get_or_create(user=request.user)
    
    # Get videos sorted by different criteria
    videos = Video.objects.filter(user=request.user, status='active')
    
    # Large videos (>50MB)
    large_videos = videos.filter(file_size__gt=50*1024*1024).order_by('-file_size')[:10]
    
    # Old videos (>90 days)
    ninety_days_ago = timezone.now() - timedelta(days=90)
    old_videos = videos.filter(created_at__lt=ninety_days_ago).order_by('created_at')[:10]
    
    # Rarely accessed videos
    rarely_accessed = videos.filter(
        Q(access_count__lte=2) | Q(last_accessed__lt=timezone.now() - timedelta(days=30))
    ).order_by('access_count', 'last_accessed')[:10]
    
    # Calculate potential savings
    total_large_size = sum(v.file_size for v in large_videos) / (1024*1024)
    total_old_size = sum(v.file_size for v in old_videos) / (1024*1024)
    total_rare_size = sum(v.file_size for v in rarely_accessed) / (1024*1024)
    
    context = {
        'user_storage': user_storage,
        'large_videos': large_videos,
        'old_videos': old_videos,
        'rarely_accessed': rarely_accessed,
        'total_large_size': total_large_size,
        'total_old_size': total_old_size,
        'total_rare_size': total_rare_size,
        'is_storage_exceeded': user_storage.is_storage_exceeded(),
        'overage_mb': user_storage.get_overage_amount_mb(),
    }
    
    return render(request, 'videos/storage_optimizer.html', context)


@login_required
@csrf_exempt
@require_POST
def api_upload_video(request):
    """API endpoint for uploading videos from StreamRec"""
    from django.core.files.base import ContentFile
    from .subscription_sync import StorageSubscriptionSync
    from .storage_management import StorageOverageService
    import json
    import base64
    
    try:
        # Parse JSON data from request
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            return JsonResponse({'success': False, 'error': 'Content-Type muss application/json sein'}, status=400)
        
        # Get required fields
        title = data.get('title', 'StreamRec Aufnahme')
        description = data.get('description', '')
        video_data = data.get('video_data')  # Base64 encoded video data
        file_format = data.get('format', 'webm')
        
        if not video_data:
            return JsonResponse({'success': False, 'error': 'video_data ist erforderlich'}, status=400)
        
        # Check user storage
        user_storage = StorageSubscriptionSync.sync_user_storage(request.user)
        StorageOverageService.check_user_storage_overage(request.user)
        user_storage.refresh_from_db()
        
        if not user_storage.can_upload():
            return JsonResponse({
                'success': False, 
                'error': user_storage.get_restriction_message()
            }, status=403)
        
        # Decode base64 video data
        try:
            video_bytes = base64.b64decode(video_data)
            file_size = len(video_bytes)
        except Exception as e:
            return JsonResponse({'success': False, 'error': 'Ungültige video_data (Base64 dekodierung fehlgeschlagen)'}, status=400)
        
        # Check storage availability
        if not user_storage.has_storage_available(file_size):
            available_mb = (user_storage.max_storage - user_storage.used_storage) / (1024 * 1024)
            needed_mb = file_size / (1024 * 1024)
            
            return JsonResponse({
                'success': False,
                'error': f'Nicht genügend Speicherplatz. Verfügbar: {available_mb:.1f} MB, benötigt: {needed_mb:.1f} MB'
            }, status=413)
        
        # Create video object
        video = Video(
            user=request.user,
            title=title,
            description=description,
            file_size=file_size
        )
        
        # Create file content
        filename = f"streamrec_{video.unique_id}.{file_format}"
        video_file = ContentFile(video_bytes, name=filename)
        video.video_file.save(filename, video_file)
        
        # Save video
        video.save()
        
        # Update user storage
        user_storage.used_storage += file_size
        user_storage.save()
        
        # Generate thumbnail (optional, don't fail if it doesn't work)
        try:
            generate_video_thumbnail(video)
            video.duration = get_video_duration(video.video_file.path)
            video.save()
        except Exception as e:
            print(f"Error generating thumbnail for API upload: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Video erfolgreich gespeichert!',
            'video': {
                'id': video.id,
                'unique_id': str(video.unique_id),
                'title': video.title,
                'share_link': video.share_link,
                'embed_url': video.get_embed_url(),
                'file_size_mb': round(video.file_size / (1024 * 1024), 2),
                'duration': video.duration,
                'created_at': video.created_at.isoformat()
            },
            'storage': {
                'used_mb': round(user_storage.get_used_storage_mb(), 2),
                'max_mb': round(user_storage.get_max_storage_mb(), 2),
                'used_percentage': round((user_storage.used_storage / user_storage.max_storage * 100), 1),
                'available_mb': round((user_storage.max_storage - user_storage.used_storage) / (1024 * 1024), 2)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Server Fehler: {str(e)}'}, status=500)


@login_required 
def api_storage_status(request):
    """API endpoint to check storage status"""
    from .subscription_sync import StorageSubscriptionSync
    from .storage_management import StorageOverageService
    
    try:
        user_storage = StorageSubscriptionSync.sync_user_storage(request.user)
        StorageOverageService.check_user_storage_overage(request.user)
        user_storage.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'storage': {
                'used_mb': round(user_storage.get_used_storage_mb(), 2),
                'max_mb': round(user_storage.get_max_storage_mb(), 2),
                'used_percentage': round((user_storage.used_storage / user_storage.max_storage * 100), 1),
                'available_mb': round((user_storage.max_storage - user_storage.used_storage) / (1024 * 1024), 2),
                'can_upload': user_storage.can_upload(),
                'can_share': user_storage.can_share(),
                'is_exceeded': user_storage.is_storage_exceeded(),
                'restriction_message': user_storage.get_restriction_message(),
                'tier_name': user_storage.get_tier_name(),
                'current_price': float(user_storage.get_current_price())
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Fehler beim Abrufen des Speicherstatus: {str(e)}'}, status=500)


# ==================== SOCIAL MEDIA POSTING ====================

@login_required
@require_POST
def api_generate_social_text(request, video_id):
    """API: KI-gestützte Generierung von Titel, Beschreibung und Hashtags für Social Media"""
    import json

    video = get_object_or_404(Video, id=video_id, user=request.user)

    try:
        data = json.loads(request.body)
        user_input = data.get('input_text', '')
        platforms = data.get('platforms', [])

        if not user_input:
            # Fallback auf Video-Titel und Beschreibung
            user_input = f"{video.title}. {video.description}"

        # KI-API auswählen basierend auf verfügbaren Keys
        user = request.user
        result = None

        # OpenAI versuchen
        if user.openai_api_key:
            result = _generate_with_openai(user, user_input, platforms)
        # Anthropic als Fallback
        elif user.anthropic_api_key:
            result = _generate_with_anthropic(user, user_input, platforms)
        # Gemini als Fallback
        elif user.gemini_api_key:
            result = _generate_with_gemini(user, user_input, platforms)
        else:
            return JsonResponse({
                'success': False,
                'error': 'Kein KI-API-Key konfiguriert. Bitte in den Einstellungen einen OpenAI, Anthropic oder Gemini API-Key hinzufügen.'
            }, status=400)

        if result:
            return JsonResponse({
                'success': True,
                'title': result.get('title', ''),
                'description': result.get('description', ''),
                'hashtags': result.get('hashtags', '')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'KI-Generierung fehlgeschlagen. Bitte versuche es erneut.'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Fehler: {str(e)}'}, status=500)


def _generate_with_openai(user, input_text, platforms):
    """Generiert Social Media Texte mit OpenAI"""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=user.openai_api_key)

        platform_str = ', '.join(platforms) if platforms else 'Instagram, Facebook, LinkedIn, TikTok, YouTube'

        prompt = f"""Erstelle optimierte Social Media Inhalte für ein Video basierend auf diesem Text:

"{input_text}"

Zielplattformen: {platform_str}

Erstelle:
1. Einen kurzen, ansprechenden Titel (max. 60 Zeichen)
2. Eine Beschreibung (max. 300 Zeichen) mit Call-to-Action
3. Relevante Hashtags (5-10 Stück, mit # Zeichen)

Antworte NUR im JSON-Format:
{{"title": "...", "description": "...", "hashtags": "#tag1 #tag2 #tag3"}}"""

        response = client.chat.completions.create(
            model=user.preferred_openai_model or 'gpt-4o-mini',
            messages=[
                {"role": "system", "content": "Du bist ein Social Media Marketing Experte. Antworte immer auf Deutsch und nur im JSON-Format."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        import json
        content = response.choices[0].message.content.strip()
        # JSON aus der Antwort extrahieren
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]

        return json.loads(content.strip())

    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None


def _generate_with_anthropic(user, input_text, platforms):
    """Generiert Social Media Texte mit Anthropic"""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=user.anthropic_api_key)

        platform_str = ', '.join(platforms) if platforms else 'Instagram, Facebook, LinkedIn, TikTok, YouTube'

        prompt = f"""Erstelle optimierte Social Media Inhalte für ein Video basierend auf diesem Text:

"{input_text}"

Zielplattformen: {platform_str}

Erstelle:
1. Einen kurzen, ansprechenden Titel (max. 60 Zeichen)
2. Eine Beschreibung (max. 300 Zeichen) mit Call-to-Action
3. Relevante Hashtags (5-10 Stück, mit # Zeichen)

Antworte NUR im JSON-Format:
{{"title": "...", "description": "...", "hashtags": "#tag1 #tag2 #tag3"}}"""

        response = client.messages.create(
            model=user.preferred_anthropic_model or 'claude-3-5-sonnet-20241022',
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        import json
        content = response.content[0].text.strip()
        # JSON aus der Antwort extrahieren
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]

        return json.loads(content.strip())

    except Exception as e:
        print(f"Anthropic Error: {e}")
        return None


def _generate_with_gemini(user, input_text, platforms):
    """Generiert Social Media Texte mit Google Gemini"""
    try:
        import google.generativeai as genai

        genai.configure(api_key=user.gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        platform_str = ', '.join(platforms) if platforms else 'Instagram, Facebook, LinkedIn, TikTok, YouTube'

        prompt = f"""Erstelle optimierte Social Media Inhalte für ein Video basierend auf diesem Text:

"{input_text}"

Zielplattformen: {platform_str}

Erstelle:
1. Einen kurzen, ansprechenden Titel (max. 60 Zeichen)
2. Eine Beschreibung (max. 300 Zeichen) mit Call-to-Action
3. Relevante Hashtags (5-10 Stück, mit # Zeichen)

Antworte NUR im JSON-Format:
{{"title": "...", "description": "...", "hashtags": "#tag1 #tag2 #tag3"}}"""

        response = model.generate_content(prompt)

        import json
        content = response.text.strip()
        # JSON aus der Antwort extrahieren
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]

        return json.loads(content.strip())

    except Exception as e:
        print(f"Gemini Error: {e}")
        return None


@login_required
@require_POST
def api_post_to_social(request, video_id):
    """API: Postet ein Video über Upload-Post.com auf Social Media Plattformen"""
    import json
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from django.utils import timezone
    import logging

    logger = logging.getLogger(__name__)
    video = get_object_or_404(Video, id=video_id, user=request.user)

    try:
        # Upload-Post API-Key vom User holen
        upload_post_api_key = request.user.upload_post_api_key
        upload_post_user_id = request.user.upload_post_user_id

        if not upload_post_api_key:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post API-Key nicht konfiguriert. Bitte in den API-Einstellungen hinzufügen.'
            }, status=400)

        if not upload_post_user_id:
            return JsonResponse({
                'success': False,
                'error': 'Upload-Post User-ID nicht konfiguriert. Bitte in den API-Einstellungen hinzufügen.'
            }, status=400)

        # API-Key bereinigen
        api_key_clean = ''.join(c for c in upload_post_api_key if c.isascii() and c.isprintable()).strip()

        # Request Body parsen
        data = json.loads(request.body)
        platforms = data.get('platforms', [])
        scheduled_date = data.get('scheduled_date', '')  # ISO-8601 Format
        title = data.get('title', video.title)
        description = data.get('description', video.description)
        hashtags = data.get('hashtags', '')
        platform_options = data.get('platform_options', {})

        if not platforms:
            return JsonResponse({
                'success': False,
                'error': 'Keine Plattformen ausgewählt.'
            }, status=400)

        # Video-Datei prüfen
        video_file = video.video_file
        if not video_file:
            return JsonResponse({
                'success': False,
                'error': 'Kein Video vorhanden.'
            }, status=400)

        # Prüfe Dateigröße (Upload-Post hat möglicherweise Limits)
        file_size_mb = video.file_size / (1024 * 1024)
        if file_size_mb > 100:  # 100MB Limit
            return JsonResponse({
                'success': False,
                'error': f'Video zu groß ({file_size_mb:.1f}MB). Maximum: 100MB'
            }, status=400)

        # Video-Datei lesen
        video_file.seek(0)
        video_data = video_file.read()
        video_name = video_file.name.split('/')[-1]

        # Content Type bestimmen
        if video_name.endswith('.mp4'):
            content_type = 'video/mp4'
        elif video_name.endswith('.webm'):
            content_type = 'video/webm'
        elif video_name.endswith('.mov'):
            content_type = 'video/quicktime'
        else:
            content_type = 'video/mp4'

        # Video-Link erstellen (öffentlicher Link zum Video)
        video_link = request.build_absolute_uri(f'/videos/v/{video.unique_id}/')

        # Vollständige Beschreibung mit Hashtags
        full_description = f"{description}\n\n{hashtags}" if hashtags else description

        # Upload-Post API aufrufen - Korrekter Endpoint laut Dokumentation
        api_url = 'https://api.upload-post.com/api/upload'

        headers = {
            'Authorization': f'Apikey {api_key_clean}',
        }

        # Form-Daten erstellen gemäß Upload-Post Dokumentation
        form_data = [
            ('user', upload_post_user_id),
            ('title', title),  # Video-Titel
            ('description', full_description),  # Beschreibung mit Hashtags
        ]

        # Plattformen hinzufügen
        for platform in platforms:
            form_data.append(('platform[]', platform))

        # Plattform-spezifische Parameter gemäß Upload-Post Dokumentation
        # Instagram Optionen
        if 'instagram' in platforms:
            ig_opts = platform_options.get('instagram', {})
            form_data.append(('media_type', ig_opts.get('media_type', 'REELS')))
            if ig_opts.get('share_to_feed', True):
                form_data.append(('share_to_feed', 'true'))

        # TikTok Optionen
        if 'tiktok' in platforms:
            tt_opts = platform_options.get('tiktok', {})
            form_data.append(('privacy_level', tt_opts.get('privacy_level', 'PUBLIC_TO_EVERYONE')))
            if tt_opts.get('disable_comment', False):
                form_data.append(('disable_comment', 'true'))
            if tt_opts.get('disable_duet', False):
                form_data.append(('disable_duet', 'true'))

        # YouTube Optionen
        if 'youtube' in platforms:
            yt_opts = platform_options.get('youtube', {})
            form_data.append(('privacyStatus', yt_opts.get('privacyStatus', 'public')))
            form_data.append(('categoryId', yt_opts.get('categoryId', '22')))
            if yt_opts.get('madeForKids', False):
                form_data.append(('madeForKids', 'true'))

        # Facebook Optionen
        if 'facebook' in platforms:
            fb_opts = platform_options.get('facebook', {})
            form_data.append(('facebook_media_type', fb_opts.get('facebook_media_type', 'REELS')))

        # LinkedIn Optionen
        if 'linkedin' in platforms:
            li_opts = platform_options.get('linkedin', {})
            form_data.append(('visibility', li_opts.get('visibility', 'PUBLIC')))

        if scheduled_date:
            form_data.append(('scheduled_date', scheduled_date))

        import io
        # Video-Feld heißt 'video' (singular) laut Dokumentation
        files = {'video': (video_name, io.BytesIO(video_data), content_type)}

        # Session mit Retry-Logik erstellen
        session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        logger.info(f"[Video Social] Posting Video {video.id} auf: {platforms}")

        response = None
        try:
            response = session.post(api_url, headers=headers, data=form_data, files=files, timeout=180, verify=True)
        except requests.exceptions.SSLError as ssl_err:
            logger.warning(f"[Video Social] SSL-Fehler, versuche ohne Verifizierung: {ssl_err}")
            # Fallback ohne SSL-Verifizierung
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            # Video-Datei neu lesen da BytesIO verbraucht wurde
            video_file.seek(0)
            video_data = video_file.read()
            files = {'video': (video_name, io.BytesIO(video_data), content_type)}
            try:
                response = session.post(api_url, headers=headers, data=form_data, files=files, timeout=180, verify=False)
            except Exception as inner_e:
                logger.error(f"[Video Social] Auch ohne SSL-Verifizierung fehlgeschlagen: {inner_e}")
                return JsonResponse({
                    'success': False,
                    'error': f'SSL-Verbindungsfehler zu Upload-Post.com. Bitte später erneut versuchen.'
                }, status=503)
        except requests.exceptions.Timeout:
            return JsonResponse({
                'success': False,
                'error': 'Timeout beim Upload. Das Video ist möglicherweise zu groß.'
            }, status=504)
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"[Video Social] Verbindungsfehler: {conn_err}")
            return JsonResponse({
                'success': False,
                'error': 'Verbindung zu Upload-Post.com fehlgeschlagen. Bitte später erneut versuchen.'
            }, status=503)

        if response and response.status_code in [200, 202]:
            result = response.json()
            logger.info(f"[Video Social] Erfolgreich gepostet: {result}")

            # Posted URLs aus Response extrahieren
            posted_urls = {}
            if 'results' in result:
                for platform, data in result.get('results', {}).items():
                    if isinstance(data, dict) and data.get('success') and data.get('url'):
                        posted_urls[platform] = data['url']

                        # YouTube Shorts: zusätzlich den normalen watch-Link für Embed
                        if platform.lower() == 'youtube':
                            youtube_url = data.get('url', '')
                            video_id = data.get('video_id', '')

                            if '/shorts/' in youtube_url:
                                if video_id:
                                    posted_urls['youtube_watch'] = f'https://www.youtube.com/watch?v={video_id}'
                                else:
                                    # Video-ID aus Shorts-URL extrahieren
                                    import re
                                    match = re.search(r'/shorts/([a-zA-Z0-9_-]+)', youtube_url)
                                    if match:
                                        extracted_id = match.group(1)
                                        posted_urls['youtube_watch'] = f'https://www.youtube.com/watch?v={extracted_id}'

            # Request-ID speichern falls Background-Upload
            request_id = result.get('request_id', '')
            is_background = 'background' in result.get('message', '').lower()

            # Video-Model aktualisieren
            video.social_platforms_posted = ','.join(platforms)
            video.social_posted_at = timezone.now() if not scheduled_date else None
            video.social_scheduled_at = scheduled_date if scheduled_date else None
            video.social_post_title = title
            video.social_post_description = description
            video.social_post_hashtags = hashtags
            video.social_post_error = ''
            video.social_posted_urls = posted_urls  # URLs persistent speichern
            video.social_request_id = request_id  # Request-ID für Status-Check
            video.save()

            # Nachricht anpassen wenn Background-Upload
            if is_background and not posted_urls:
                message = f'Video wird im Hintergrund auf {", ".join(platforms)} hochgeladen. Klicke "Status prüfen" um die Links abzurufen.'
            elif scheduled_date:
                message = f'Video für {scheduled_date} geplant!'
            else:
                message = f'Video erfolgreich auf {", ".join(platforms)} gepostet!'

            return JsonResponse({
                'success': True,
                'message': message,
                'platforms': platforms,
                'posted_urls': posted_urls,
                'request_id': request_id,
                'is_background': is_background,
                'result': result
            })
        elif response:
            error_msg = f"Upload-Post Fehler: {response.status_code} - {response.text[:200]}"
            logger.error(f"[Video Social] {error_msg}")
            video.social_post_error = error_msg
            video.save()

            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=400)
        else:
            return JsonResponse({
                'success': False,
                'error': 'Unbekannter Fehler beim Upload'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        error_msg = f'Fehler: {str(e)}'
        logger.exception(f"[Video Social] Exception: {error_msg}")
        try:
            video.social_post_error = error_msg
            video.save()
        except Exception:
            pass
        return JsonResponse({'success': False, 'error': error_msg}, status=500)


@login_required
def api_social_status(request, video_id):
    """API: Holt den Social Media Posting-Status eines Videos"""
    video = get_object_or_404(Video, id=video_id, user=request.user)

    platforms_posted = video.social_platforms_posted.split(',') if video.social_platforms_posted else []

    return JsonResponse({
        'success': True,
        'video_id': video.id,
        'platforms_posted': platforms_posted,
        'posted_at': video.social_posted_at.isoformat() if video.social_posted_at else None,
        'scheduled_at': video.social_scheduled_at.isoformat() if video.social_scheduled_at else None,
        'title': video.social_post_title,
        'description': video.social_post_description,
        'hashtags': video.social_post_hashtags,
        'error': video.social_post_error
    })


@login_required
@require_POST
def api_check_upload_status(request, video_id):
    """API: Prüft den Upload-Status bei Background-Uploads und holt URLs"""
    logger = logging.getLogger(__name__)
    video = get_object_or_404(Video, id=video_id, user=request.user)

    if not video.social_request_id:
        return JsonResponse({
            'success': False,
            'error': 'Keine Request-ID vorhanden. Video wurde nicht im Hintergrund hochgeladen.'
        }, status=400)

    # API-Key holen
    upload_post_api_key = request.user.upload_post_api_key
    if not upload_post_api_key:
        return JsonResponse({
            'success': False,
            'error': 'Upload-Post API-Key nicht konfiguriert.'
        }, status=400)

    api_key_clean = ''.join(c for c in upload_post_api_key if c.isascii() and c.isprintable()).strip()

    try:
        # Status-API aufrufen
        status_url = f'https://api.upload-post.com/api/uploadposts/status?request_id={video.social_request_id}'
        headers = {
            'Authorization': f'Apikey {api_key_clean}',
        }

        response = requests.get(status_url, headers=headers, timeout=30)
        logger.info(f"[Video Status] Response: {response.status_code} - {response.text[:500]}")

        if response.status_code == 200:
            result = response.json()

            # URLs extrahieren - results ist eine Liste von Objekten
            posted_urls = {}
            results_list = result.get('results', [])
            if isinstance(results_list, list):
                for item in results_list:
                    if isinstance(item, dict) and item.get('success') and item.get('post_url'):
                        platform = item.get('platform', 'unknown')
                        post_url = item.get('post_url')
                        posted_urls[platform] = post_url

            # URLs im Video speichern
            if posted_urls:
                video.social_posted_urls = posted_urls
                video.save()

            status = result.get('status', 'unknown')
            return JsonResponse({
                'success': True,
                'status': status,
                'posted_urls': posted_urls,
                'message': 'URLs erfolgreich abgerufen!' if posted_urls else f'Status: {status}',
                'result': result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'API Fehler: {response.status_code} - {response.text[:200]}'
            }, status=400)

    except Exception as e:
        logger.error(f"[Video Status] Error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
