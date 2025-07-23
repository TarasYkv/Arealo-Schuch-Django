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
import mimetypes
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
    """Stream video file"""
    video = get_object_or_404(Video, unique_id=unique_id)
    
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
