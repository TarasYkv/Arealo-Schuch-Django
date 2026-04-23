import os
import subprocess
import requests
from uuid import uuid4
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import VideoProject, VideoAsset, GeneratedImage, VideoScene
from .kie_service import KieService


def get_user_id(request):
    if request.user.is_authenticated:
        return str(request.user.id)
    return request.headers.get('X-User-Id', 'anonymous')


def get_api_key(request):
    # Erst vom eingeloggten User holen
    if request.user.is_authenticated and hasattr(request.user, 'kie_api_key') and request.user.kie_api_key:
        return request.user.kie_api_key
    # Fallback auf Header
    return request.headers.get('X-Api-Key', '')


from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def index(request):
    """Main video creator page"""
    context = {
        'has_api_key': bool(get_api_key(request)),
        'user_id': get_user_id(request),
    }
    return render(request, 'videocreator/index.html', context)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def projects_list(request):
    user_id = get_user_id(request)
    
    if request.method == 'GET':
        projects = VideoProject.objects.filter(user_id=user_id)
        return JsonResponse([{
            'id': str(p.id),
            'name': p.name,
            'exported_video_url': p.exported_video_url,
            'created_at': p.created_at.isoformat(),
            'updated_at': p.updated_at.isoformat(),
        } for p in projects], safe=False)
    
    elif request.method == 'POST':
        data = json.loads(request.body)
        project = VideoProject.objects.create(
            user_id=user_id,
            name=data.get('name', 'Neues Projekt')
        )
        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
        }, status=201)


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def project_detail(request, project_id):
    user_id = get_user_id(request)
    
    try:
        project = VideoProject.objects.get(pk=project_id, user_id=user_id)
    except VideoProject.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
    if request.method == 'GET':
        assets = [{
            'id': str(a.id),
            'type': a.type,
            'name': a.name,
            'url': a.file.url if a.file else None,
            'original_name': a.original_name,
        } for a in project.assets.all()]
        
        scenes = [{
            'id': str(s.id),
            'order': s.order,
            'start_frame': str(s.start_frame_id) if s.start_frame_id else None,
            'end_frame': str(s.end_frame_id) if s.end_frame_id else None,
            'start_frame_url': s.start_frame.image.url if s.start_frame and s.start_frame.image else (s.start_frame.image_url if s.start_frame else None),
            'end_frame_url': s.end_frame.image.url if s.end_frame and s.end_frame.image else (s.end_frame.image_url if s.end_frame else None),
            'prompt': s.prompt,
            'video_model': s.video_model,
            'duration': s.duration,
            'video_task_id': s.video_task_id,
            'video_url': s.video_url,
            'video_status': s.video_status,
            'audio_source': s.audio_source,
            'audio_tts_text': s.audio_tts_text,
            'audio_task_id': s.audio_task_id,
            'audio_url': s.audio_url,
            'audio_status': s.audio_status,
        } for s in project.scenes.all()]
        
        generated_images = [{
            'id': str(i.id),
            'prompt': i.prompt,
            'model': i.model,
            'url': i.image.url if i.image else i.image_url,
            'task_id': i.task_id,
            'status': i.status,
            'created_at': i.created_at.isoformat(),
        } for i in project.generated_images.all()]
        
        return JsonResponse({
            'id': str(project.id),
            'name': project.name,
            'exported_video_url': project.exported_video_url,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'assets': assets,
            'scenes': scenes,
            'generated_images': generated_images,
        })
    
    elif request.method == 'DELETE':
        project.delete()
        return JsonResponse({}, status=204)


@csrf_exempt
@require_http_methods(["POST"])
def upload_asset(request, project_id):
    user_id = get_user_id(request)
    
    try:
        project = VideoProject.objects.get(pk=project_id, user_id=user_id)
    except VideoProject.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
    asset_type = request.POST.get('type')
    file = request.FILES.get('file')
    name = request.POST.get('name', file.name if file else '')
    
    if not file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    if asset_type not in ['character', 'style', 'product']:
        return JsonResponse({'error': 'Invalid asset type'}, status=400)
    
    # Check character limit
    if asset_type == 'character':
        count = VideoAsset.objects.filter(project=project, type='character').count()
        if count >= 3:
            return JsonResponse({'error': 'Maximum 3 characters allowed'}, status=400)
    
    # Replace existing style/product
    if asset_type in ['style', 'product']:
        VideoAsset.objects.filter(project=project, type=asset_type).delete()
    
    asset = VideoAsset.objects.create(
        project=project,
        type=asset_type,
        name=name,
        file=file,
        original_name=file.name
    )
    
    return JsonResponse({
        'id': str(asset.id),
        'type': asset.type,
        'name': asset.name,
        'url': asset.file.url,
        'original_name': asset.original_name,
    }, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_asset(request, project_id, asset_id):
    user_id = get_user_id(request)
    
    try:
        asset = VideoAsset.objects.get(pk=asset_id, project_id=project_id, project__user_id=user_id)
    except VideoAsset.DoesNotExist:
        return JsonResponse({'error': 'Asset not found'}, status=404)
    
    asset.delete()
    return JsonResponse({}, status=204)


@csrf_exempt
@require_http_methods(["POST"])
def create_scene(request, project_id):
    user_id = get_user_id(request)
    
    try:
        project = VideoProject.objects.get(pk=project_id, user_id=user_id)
    except VideoProject.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
    max_order = VideoScene.objects.filter(project=project).count()
    scene = VideoScene.objects.create(project=project, order=max_order)
    
    return JsonResponse({
        'id': str(scene.id),
        'order': scene.order,
        'start_frame': None,
        'end_frame': None,
        'prompt': '',
        'video_model': scene.video_model,
        'duration': scene.duration,
        'video_status': scene.video_status,
        'audio_status': scene.audio_status,
    }, status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def scene_detail(request, project_id, scene_id):
    user_id = get_user_id(request)
    
    try:
        scene = VideoScene.objects.get(pk=scene_id, project_id=project_id, project__user_id=user_id)
    except VideoScene.DoesNotExist:
        return JsonResponse({'error': 'Scene not found'}, status=404)
    
    if request.method == 'DELETE':
        scene.delete()
        return JsonResponse({}, status=204)
    
    elif request.method == 'PATCH':
        data = json.loads(request.body)
        
        if 'start_frame' in data:
            scene.start_frame_id = data['start_frame']
        if 'end_frame' in data:
            scene.end_frame_id = data['end_frame']
        if 'prompt' in data:
            scene.prompt = data['prompt']
        if 'video_model' in data:
            scene.video_model = data['video_model']
        if 'duration' in data:
            scene.duration = data['duration']
        
        scene.save()
        
        return JsonResponse({
            'id': str(scene.id),
            'order': scene.order,
            'start_frame': str(scene.start_frame_id) if scene.start_frame_id else None,
            'end_frame': str(scene.end_frame_id) if scene.end_frame_id else None,
            'prompt': scene.prompt,
            'video_model': scene.video_model,
            'duration': scene.duration,
            'video_status': scene.video_status,
            'audio_status': scene.audio_status,
        })


@csrf_exempt
@require_http_methods(["POST"])
def generate_image(request, project_id):
    user_id = get_user_id(request)
    api_key = get_api_key(request)
    
    if not api_key:
        return JsonResponse({'error': 'API key required'}, status=401)
    
    try:
        project = VideoProject.objects.get(pk=project_id, user_id=user_id)
    except VideoProject.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
    data = json.loads(request.body)
    prompt = data.get('prompt')
    model = data.get('model', 'nano-banana-pro')
    image_inputs = data.get('image_inputs', [])
    aspect_ratio = data.get('aspect_ratio', '16:9')
    resolution = data.get('resolution', '1K')
    
    if not prompt:
        return JsonResponse({'error': 'Prompt required'}, status=400)
    
    kie = KieService(api_key)
    result = kie.generate_image(
        prompt=prompt,
        model=model,
        image_inputs=image_inputs,
        aspect_ratio=aspect_ratio,
        resolution=resolution
    )
    
    if result.get('code') != 200:
        return JsonResponse({'error': result.get('msg', 'Generation failed')}, status=400)
    
    image = GeneratedImage.objects.create(
        project=project,
        prompt=prompt,
        model=model,
        task_id=result.get('data', {}).get('taskId'),
        status='generating'
    )
    
    return JsonResponse({
        'id': str(image.id),
        'task_id': image.task_id,
        'status': 'generating'
    })


@csrf_exempt
@require_http_methods(["POST"])
def generate_video(request, project_id, scene_id):
    user_id = get_user_id(request)
    api_key = get_api_key(request)
    
    if not api_key:
        return JsonResponse({'error': 'API key required'}, status=401)
    
    try:
        scene = VideoScene.objects.select_related('start_frame', 'end_frame').get(
            pk=scene_id, project_id=project_id, project__user_id=user_id
        )
    except VideoScene.DoesNotExist:
        return JsonResponse({'error': 'Scene not found'}, status=404)
    
    if not scene.start_frame:
        return JsonResponse({'error': 'Start frame required'}, status=400)
    
    kie = KieService(api_key)
    
    # Build image URLs
    base_url = request.build_absolute_uri('/')[:-1]
    start_url = base_url + (scene.start_frame.image.url if scene.start_frame.image else scene.start_frame.image_url)
    image_urls = [start_url]
    
    if scene.end_frame:
        end_url = base_url + (scene.end_frame.image.url if scene.end_frame.image else scene.end_frame.image_url)
        image_urls.append(end_url)
    
    # Use unified generate_video method
    result = kie.generate_video(
        prompt=scene.prompt,
        model=scene.video_model,
        image_urls=image_urls,
        duration=scene.duration
    )
    
    if result.get('code') != 200:
        return JsonResponse({'error': result.get('msg', 'Generation failed')}, status=400)
    
    # Get task ID - different response formats
    task_id = result.get('data', {}).get('taskId') or result.get('taskId')
    
    scene.video_task_id = task_id
    scene.video_status = 'generating'
    scene.save()
    
    return JsonResponse({
        'task_id': task_id,
        'status': 'generating'
    })


@csrf_exempt
@require_http_methods(["POST"])
def generate_audio(request, project_id, scene_id):
    user_id = get_user_id(request)
    api_key = get_api_key(request)
    
    if not api_key:
        return JsonResponse({'error': 'API key required'}, status=401)
    
    data = json.loads(request.body)
    text = data.get('text', '')
    
    if not text:
        return JsonResponse({'error': 'Text required'}, status=400)
    
    try:
        scene = VideoScene.objects.get(
            pk=scene_id, project_id=project_id, project__user_id=user_id
        )
    except VideoScene.DoesNotExist:
        return JsonResponse({'error': 'Scene not found'}, status=404)
    
    kie = KieService(api_key)
    result = kie.generate_tts(text=text)
    
    if result.get('code') != 200:
        return JsonResponse({'error': result.get('msg', 'Generation failed')}, status=400)
    
    scene.audio_source = 'tts'
    scene.audio_tts_text = text
    scene.audio_task_id = result.get('data', {}).get('taskId')
    scene.audio_status = 'generating'
    scene.save()
    
    return JsonResponse({
        'task_id': scene.audio_task_id,
        'status': 'generating'
    })


@csrf_exempt
@require_http_methods(["GET"])
def check_task(request, task_id):
    api_key = get_api_key(request)
    
    if not api_key:
        return JsonResponse({'error': 'API key required'}, status=401)
    
    kie = KieService(api_key)
    result = kie.check_task(task_id)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
def export_project(request, project_id):
    user_id = get_user_id(request)
    
    try:
        project = VideoProject.objects.get(pk=project_id, user_id=user_id)
    except VideoProject.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
    scenes = VideoScene.objects.filter(
        project=project,
        video_status='done'
    ).exclude(video_file='').order_by('order')
    
    if not scenes:
        return JsonResponse({'error': 'No completed videos to export'}, status=400)
    
    export_dir = os.path.join(settings.MEDIA_ROOT, 'videocreator', 'exports')
    os.makedirs(export_dir, exist_ok=True)
    
    output_filename = f"{uuid4()}.mp4"
    output_path = os.path.join(export_dir, output_filename)
    concat_file = os.path.join(export_dir, f"concat_{uuid4()}.txt")
    
    with open(concat_file, 'w') as f:
        for scene in scenes:
            video_path = os.path.join(settings.MEDIA_ROOT, scene.video_file.name)
            f.write(f"file '{video_path}'\n")
    
    try:
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy', '-y', output_path
        ], check=True, capture_output=True)
        
        project.exported_video_url = f'/media/videocreator/exports/{output_filename}'
        project.save()
        
        return JsonResponse({
            'url': project.exported_video_url,
            'filename': output_filename
        })
    except subprocess.CalledProcessError:
        return JsonResponse({'error': 'Export failed'}, status=500)
    finally:
        if os.path.exists(concat_file):
            os.unlink(concat_file)


@csrf_exempt
@require_http_methods(["POST"])
def callback(request):
    """Callback endpoint for kie.ai async tasks"""
    data = json.loads(request.body)
    task_id = data.get('taskId')
    task_status = data.get('status')
    output = data.get('output', {})
    
    if not task_id:
        return JsonResponse({'error': 'Task ID required'}, status=400)
    
    # Check generated images
    image = GeneratedImage.objects.filter(task_id=task_id).first()
    if image:
        if task_status in ['completed', 'success']:
            image_url = output.get('image_url') or (output.get('urls') or [None])[0]
            if image_url:
                # Set image_url field first for persistence
                image.image_url = image_url
                try:
                    response = requests.get(image_url, timeout=30)
                    filename = f"{image.id}.png"
                    filepath = os.path.join(settings.MEDIA_ROOT, 'videocreator', 'generated', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    image.image = f'videocreator/generated/{filename}'
                    image.status = 'done'
                except Exception:
                    # Even if download fails, we have the URL
                    image.status = 'done'
            else:
                image.status = 'error'
        else:
            image.status = 'error'
        image.save()
        return JsonResponse({'received': True})
    
    # Check scenes (video)
    scene = VideoScene.objects.filter(video_task_id=task_id).first()
    if scene:
        if task_status in ['completed', 'success']:
            video_url = output.get('video_url')
            if video_url:
                try:
                    response = requests.get(video_url, timeout=60)
                    filename = f"{scene.id}.mp4"
                    filepath = os.path.join(settings.MEDIA_ROOT, 'videocreator', 'generated', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    scene.video_file = f'videocreator/generated/{filename}'
                    scene.video_status = 'done'
                except Exception:
                    scene.video_status = 'error'
        else:
            scene.video_status = 'error'
        scene.save()
        return JsonResponse({'received': True})
    
    # Check scenes (audio)
    scene = VideoScene.objects.filter(audio_task_id=task_id).first()
    if scene:
        if task_status in ['completed', 'success']:
            audio_url = output.get('audio_url')
            if audio_url:
                try:
                    response = requests.get(audio_url, timeout=30)
                    filename = f"{scene.id}_audio.mp3"
                    filepath = os.path.join(settings.MEDIA_ROOT, 'videocreator', 'generated', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    scene.audio_file = f'videocreator/generated/{filename}'
                    scene.audio_status = 'done'
                except Exception:
                    scene.audio_status = 'error'
        else:
            scene.audio_status = 'error'
        scene.save()
        return JsonResponse({'received': True})
    
    return JsonResponse({'received': True, 'unknown': True})
