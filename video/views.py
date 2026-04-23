from celery import shared_task
import json
import base64
import pathlib
import os
import threading
from io import BytesIO
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from google import genai
from google.genai import types
from .models import VideoProject, Character, Product, StillImage, GeneratedFrame, Scene


# === Background rendering ===


FRAME_MODEL_TO_GEMINI = {
    'nano-banana': 'gemini-3.1-flash-image-preview',
    'gemini-2.5': 'gemini-2.5-flash-image-preview',
    'gemini-2.0': 'gemini-2.0-flash-preview-image-generation',
}

FRAME_MODEL_TO_IMAGEN = {
    'imagen-4-fast': 'imagen-4.0-fast-generate-preview-06-06',
    'imagen-4': 'imagen-4.0-generate-preview-06-06',
    'imagen-4-ultra': 'imagen-4.0-ultra-generate-preview-06-06',
}


def _render_in_background(scene_id):
    """Render video - Thunder Compute GPU (ComfyUI) or LaoZhang API"""
    import requests as _requests
    import time as _time
    from pathlib import Path as _Path
    import base64 as _base64
    
    try:
        scene = Scene.objects.get(pk=scene_id)
        scene.status = 'generating'
        scene.error_message = ''
        scene.render_progress = 0
        scene.save()

        _start = _time.time()
        
        # Get active provider
        from video.models import VideoAPIKey
        api_key_obj = VideoAPIKey.objects.filter(user=scene.project.user, is_active=True).first()
        if not api_key_obj:
            raise Exception('Kein API-Key konfiguriert. Bitte unter Video Studio -> API Keys einen Key hinzufuegen.')

        provider = api_key_obj.provider
        model = scene.model_choice
        
        # Auto-detect: Thunder models always use Thunder Compute (ComfyUI)
        THUNDER_MODELS_SET = {
            'cogvideox', 'wan-2.1', 'wan-2.2', 'wan-2.2',
            'wan-2.5-480p', 'wan-2.5-720p', 'wan-2.5-1080p',
            'wan-2.6-720p', 'wan-2.6-1080p',
            'ltx-2-distilled', 'hunyuanvideo'
        }
        if model in THUNDER_MODELS_SET:
            provider = 'thunder' 
        prompt = (scene.prompt or 'A beautiful cinematic scene').replace('#test', '').strip()

        if provider == 'thunder':
            # Thunder Compute A100 via ComfyUI API (auto-starts ComfyUI)
            from video.tasks import (
                _ensure_thunder_running, _ssh_cmd, _scp_from, _scp_to,
                _comfyui_submit_workflow, _comfyui_poll_status, _comfyui_download_output,
                COMFYUI_PORT
            )
            from video.comfyui_workflows.builder import build_workflow
            
            # Start ComfyUI server if needed (~35-60 seconds)
            ip, port = _ensure_thunder_running()
            
            # Upload start/end frames to ComfyUI input directory
            start_image_name = None
            end_image_name = None
            
            if scene.start_frame and scene.start_frame.image:
                img_path = scene.start_frame.image.path
                ext = _Path(img_path).suffix or '.jpg'
                start_image_name = 'scene_%s_start%s' % (scene.id, ext)
                _scp_to(img_path, '/home/ubuntu/ComfyUI/input/%s' % start_image_name)
            
            if scene.end_frame and scene.end_frame.image:
                img_path = scene.end_frame.image.path
                ext = _Path(img_path).suffix or '.jpg'
                end_image_name = 'scene_%s_end%s' % (scene.id, ext)
                _scp_to(img_path, '/home/ubuntu/ComfyUI/input/%s' % end_image_name)
            
            # Build ComfyUI workflow
            workflow = build_workflow(
                model_choice=model,
                prompt=prompt,
                num_frames=min((scene.duration or 5) * 8, 81),
                seed=scene.seed or 42,
                steps=scene.num_steps or None,
                guidance_scale=scene.guidance_scale or None,
                start_image=start_image_name,
                end_image=end_image_name,
                negative_prompt=scene.negative_prompt or '',
            )
            
            # Submit workflow to ComfyUI
            prompt_id = _comfyui_submit_workflow(workflow)
            
            # Estimated render times per model (seconds)
            _est_times = {'wan-2.2': 190, 'wan-2.1': 190, 'hunyuanvideo': 100, 'ltx-2-distilled': 60, 'cogvideox': 120}
            _est_total = _est_times.get(model, 180)
            
            # Poll for completion (up to 15 minutes)
            render_start = _time.time()
            result = {}
            for _poll in range(180):
                _time.sleep(5)
                # Update progress estimate
                _elapsed = _time.time() - render_start
                _progress = min(95, int((_elapsed / _est_total) * 100))
                try:
                    scene.render_progress = _progress
                    scene.save(update_fields=['render_progress'])
                except Exception:
                    pass
                try:
                    status, outputs = _comfyui_poll_status(prompt_id)
                    if status == 'done':
                        # Find output video file
                        video_info = None
                        for node_id, node_output in outputs.items():
                            if 'videos' in node_output:
                                video_info = node_output['videos'][0]
                                break
                            elif 'images' in node_output:
                                video_info = node_output['images'][0]
                                break
                        
                        if not video_info:
                            raise Exception('ComfyUI: no output found in: %s' % outputs)
                        
                        filename = video_info.get('filename', '')
                        subfolder = video_info.get('subfolder', '')
                        output_type = video_info.get('type', 'output')
                        
                        if not filename:
                            raise Exception('ComfyUI: no filename in output: %s' % video_info)
                        
                        # Download video from Thunder Compute
                        remote_tmp = _comfyui_download_output(filename, subfolder, output_type)
                        local_file = '/tmp/scene_%s.mp4' % scene.id
                        _scp_from(remote_tmp, local_file)
                        _ssh_cmd('rm -f %s' % remote_tmp, timeout=5)
                        
                        video_bytes = _Path(local_file).read_bytes()
                        render_sec = round(_time.time() - render_start, 1)
                        
                        filename_out = 'scene_%s.mp4' % str(scene.id)[:8]
                        scene.video_file.save(filename_out, ContentFile(video_bytes), save=False)
                        scene.status = 'done'
                        scene.render_progress = 100
                        scene.render_duration_sec = render_sec
                        scene.render_cost = 0
                        scene.save()
                        return
                    
                    elif status == 'error':
                        raise Exception('ComfyUI render error: %s' % outputs.get('error', 'unknown'))
                
                except Exception as poll_err:
                    if 'ComfyUI render error' in str(poll_err):
                        raise
                    # Connection errors - keep polling
                    pass
            else:
                raise Exception('Render timeout: no result after 15 minutes')

        elif provider == 'laozhang':
            base_url = 'https://api.laozhang.ai/v1'
            headers = {'Authorization': 'Bearer %s' % api_key_obj.api_key, 'Content-Type': 'application/json'}
            
            resp = _requests.post('%s/video/generations' % base_url, headers=headers, json={
                'model': model,
                'prompt': prompt,
                'size': '1280x720',
                'seconds': str(scene.duration or 5),
            }, timeout=30)
            
            if resp.status_code != 200:
                raise Exception('LaoZhang API Error: %s - %s' % (resp.status_code, resp.text[:200]))
            
            data = resp.json()
            video_id = data.get('id')
            if not video_id:
                raise Exception('No video ID returned: %s' % data)
            
            for _ in range(60):
                _time.sleep(5)
                poll = _requests.get('%s/video/generations/%s' % (base_url, video_id), headers=headers, timeout=30)
                poll_data = poll.json()
                status = poll_data.get('status', 'unknown')
                
                if status == 'completed':
                    video_url = poll_data.get('video_url') or poll_data.get('url') or poll_data.get('result_url')
                    if not video_url:
                        raise Exception('Video completed but no URL returned')
                    video_resp = _requests.get(video_url, timeout=60)
                    if video_resp.status_code == 200:
                        filename = 'scene_%s.mp4' % str(scene.id)[:8]
                        scene.video_file.save(filename, ContentFile(video_resp.content), save=False)
                        elapsed = _time.time() - _start
                        scene.status = 'done'
                        scene.render_duration_sec = round(elapsed, 1)
                        scene.render_cost = 0
                        scene.save()
                        return
                    else:
                        raise Exception('Download failed: %s' % video_resp.status_code)
                elif status in ('failed', 'error'):
                    raise Exception('Video generation failed: %s' % poll_data.get('message', 'unknown error'))
            
            raise Exception('Timeout: Video nicht nach 5 Minuten fertig')

        else:
            raise Exception('Provider %s noch nicht implementiert' % provider)

    except Exception as e:
        try:
            scene = Scene.objects.get(pk=scene_id)
            scene.status = 'error'
            scene.error_message = str(e)[:500]
            scene.save()
        except Exception:
            pass
# === PROJECT VIEWS ===

@login_required
def project_list(request):
    projects = VideoProject.objects.filter(user=request.user)
    return render(request, 'video/project_list.html', {'projects': projects})


@login_required
def project_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            project = VideoProject.objects.create(user=request.user, name=name)
            for i in range(1, 4):
                char_img = request.FILES.get('character_{}'.format(i))
                char_name = request.POST.get('character_{}_name'.format(i), '').strip()
                if char_img and char_name:
                    Character.objects.create(project=project, name=char_name, image=char_img)
            product_img = request.FILES.get('product')
            product_name = request.POST.get('product_name', '').strip()
            if product_img and product_name:
                Product.objects.create(project=project, name=product_name, image=product_img)
            still_img = request.FILES.get('still_image')
            still_name = request.POST.get('still_name', '').strip()
            if still_img and still_name:
                StillImage.objects.create(project=project, name=still_name, image=still_img)
            return redirect('video:project_detail', pk=project.pk)
    return render(request, 'video/project_create.html')


@login_required
def project_detail(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    context = {
        'project': project,
        'characters': project.characters.all(),
        'product': getattr(project, 'product', None),
        'still_image': getattr(project, 'still_image', None),
        'frames': project.frames.all().order_by('-created_at'),
        'scenes': project.scenes.all().order_by('order'),
    }
    return render(request, 'video/project_detail.html', context)


@login_required
@require_POST
@csrf_exempt
def project_delete(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    project.delete()
    return redirect('video:project_list')


# === CHARACTER VIEWS ===

@login_required
@require_POST
@csrf_exempt
def character_add(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    if project.characters.count() >= 3:
        return JsonResponse({'error': 'Maximal 3 Charaktere erlaubt'}, status=400)
    name = request.POST.get('name', '').strip()
    image = request.FILES.get('image')
    if name and image:
        char = Character.objects.create(project=project, name=name, image=image)
        return JsonResponse({'ok': True, 'id': str(char.id), 'name': char.name, 'image_url': char.image.url})
    return JsonResponse({'error': 'Name und Bild erforderlich'}, status=400)


@login_required
@require_POST
@csrf_exempt
@csrf_exempt
@login_required
def character_image_add(request, char_id):
    """Upload additional reference image(s) to an existing Character."""
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from video.models import Character, CharacterImage
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    character = get_object_or_404(Character, pk=char_id, project__user=request.user)
    files = request.FILES.getlist('images') or ([request.FILES.get('image')] if request.FILES.get('image') else [])
    files = [f for f in files if f]
    if not files:
        return JsonResponse({'error': 'Keine Datei'}, status=400)
    max_order = character.extra_images.count()
    created = []
    for i, f in enumerate(files):
        ci = CharacterImage.objects.create(
            character=character,
            image=f,
            order=max_order + i,
        )
        created.append({'id': str(ci.id), 'image_url': ci.image.url})
    return JsonResponse({'status': 'ok', 'added': len(created), 'images': created})


@csrf_exempt
@login_required
def character_image_delete(request, image_id):
    """Delete an additional reference image."""
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from video.models import CharacterImage
    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'POST/DELETE only'}, status=405)
    img = get_object_or_404(CharacterImage, pk=image_id, character__project__user=request.user)
    if img.image:
        try: img.image.delete(save=False)
        except: pass
    img.delete()
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@login_required
def character_delete(request, char_id):
    char = get_object_or_404(Character, pk=char_id, project__user=request.user)
    char.delete()
    return JsonResponse({'ok': True})


# === PRODUCT VIEWS ===

@login_required
@csrf_exempt
def product_add(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        image = request.FILES.get('image')
        if name and image:
            Product.objects.filter(project=project).delete()
            Product.objects.create(project=project, name=name, image=image)
        return redirect('video:project_detail', pk=pk)
    return redirect('video:project_detail', pk=pk)


@login_required
@require_POST
@csrf_exempt
def product_delete(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    Product.objects.filter(project=project).delete()
    return JsonResponse({'ok': True})


# === STILL IMAGE VIEWS ===

@login_required
@csrf_exempt
def still_add(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        image = request.FILES.get('image')
        if name and image:
            StillImage.objects.filter(project=project).delete()
            StillImage.objects.create(project=project, name=name, image=image)
        return redirect('video:project_detail', pk=pk)
    return redirect('video:project_detail', pk=pk)


@login_required
@require_POST
@csrf_exempt
def still_delete(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    StillImage.objects.filter(project=project).delete()
    return JsonResponse({'ok': True})


# === FRAME GENERATION (Nano Banana 2 / Gemini) ===

@login_required
@require_POST
@csrf_exempt
def frame_generate(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    prompt = request.POST.get('prompt', '').strip()
    if not prompt:
        return JsonResponse({'error': 'Prompt erforderlich'}, status=400)

    api_key = request.user.gemini_api_key
    if not api_key:
        return JsonResponse({'error': 'Gemini API Key nicht gesetzt.'}, status=400)

    ref_image_paths = []
    for char in project.characters.all():
        ref_image_paths.extend(char.all_image_paths())
    if hasattr(project, 'product') and project.product:
        ref_image_paths.append(project.product.image.path)
    if hasattr(project, 'still_image') and project.still_image:
        ref_image_paths.append(project.still_image.image.path)

    frame = GeneratedFrame.objects.create(project=project, prompt=prompt, status='generating')

    try:
        client = genai.Client(api_key=api_key)

        contents = []
        if ref_image_paths:
            contents.append('Erstelle ein Bild basierend auf diesen Referenzbildern und dem folgenden Prompt.')
            for img_path in ref_image_paths:
                img_bytes = pathlib.Path(img_path).read_bytes()
                mime = 'image/png' if img_path.endswith('.png') else 'image/jpeg'
                contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

        contents.append(prompt)

        response = client.models.generate_content(
            model='gemini-3.1-flash-image-preview',
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE'],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_bytes = part.inline_data.data
                filename = 'frame_{}.png'.format(frame.id)
                frame.image.save(filename, ContentFile(img_bytes), save=True)
                frame.status = 'done'
                frame.save()
                return JsonResponse({
                    'ok': True,
                    'frame_id': str(frame.id),
                    'image_url': frame.image.url,
                })

        frame.status = 'error'
        frame.error_message = 'Kein Bild in der Antwort'
        frame.save()
        return JsonResponse({'error': 'Kein Bild generiert'}, status=500)

    except Exception as e:
        frame.status = 'error'
        frame.error_message = str(e)
        frame.save()
        return JsonResponse({'error': str(e)}, status=500)



# === FRAME GENERATION (FLUX + PuLID - Local ComfyUI) ===

@login_required
@require_POST
@csrf_exempt
def frame_generate_flux(request, pk):
    """Generate a character frame using FLUX + PuLID on RunPod ComfyUI."""
    import time, uuid
    import requests as _requests
    from video.tasks import _ensure_runpod_running, _upload_image_to_comfyui, _submit_workflow, _poll_status

    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    prompt = request.POST.get('prompt', '').strip()
    if not prompt:
        return JsonResponse({'error': 'Prompt erforderlich'}, status=400)

    ref_image_paths = []
    for char in project.characters.all():
        ref_image_paths.extend(char.all_image_paths())
    if hasattr(project, 'product') and project.product:
        ref_image_paths.append(project.product.image.path)

    if not ref_image_paths:
        return JsonResponse({'error': 'Mindestens ein Charakter-Bild erforderlich für FLUX+PuLID'}, status=400)

    frame = GeneratedFrame.objects.create(project=project, prompt=prompt, status='generating')

    try:
        # Ensure RunPod is running
        url = _ensure_runpod_running()
        if not url:
            raise Exception('RunPod Pod nicht erreichbar')

        # Upload reference image to ComfyUI
        first_ref = ref_image_paths[0]
        uploaded_name = _upload_image_to_comfyui(url, first_ref)
        if not uploaded_name:
            raise Exception('Referenzbild-Upload fehlgeschlagen')

        # Build PuLID+FLUX workflow
        import random
        seed = random.randint(0, 2**31 - 1)
        workflow = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "fp8_e4m3fn"}},
            "2": {"class_type": "DualCLIPLoader", "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            }},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux_ae.safetensors"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
            "6": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
            "7": {"class_type": "PulidFluxModelLoader", "inputs": {"pulid_file": "pulid_flux_v0.9.1.safetensors"}},
            "8": {"class_type": "PulidFluxInsightFaceLoader", "inputs": {"provider": "CUDA"}},
            "9": {"class_type": "PulidFluxEvaClipLoader", "inputs": {}},
            "10": {"class_type": "ApplyPulidFlux", "inputs": {
                "model": ["1", 0],
                "pulid_flux": ["7", 0],
                "eva_clip": ["9", 0],
                "face_analysis": ["8", 0],
                "image": ["6", 0],
                "weight": 1.0,
                "start_at": 0.0,
                "end_at": 1.0,
            }},
            "11": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
            "12": {"class_type": "BasicGuider", "inputs": {"model": ["10", 0], "conditioning": ["4", 0]}},
            "13": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
            "14": {"class_type": "BasicScheduler", "inputs": {"scheduler": "simple", "steps": 20, "denoise": 1.0, "model": ["10", 0]}},
            "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
            "16": {"class_type": "SamplerCustomAdvanced", "inputs": {
                "noise": ["15", 0],
                "guider": ["12", 0],
                "sampler": ["13", 0],
                "sigmas": ["14", 0],
                "latent_image": ["11", 0],
            }},
            "17": {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["3", 0]}},
            "18": {"class_type": "SaveImage", "inputs": {"filename_prefix": "flux_frame", "images": ["17", 0]}},
        }

        # Submit and poll
        prompt_id = _submit_workflow(url, workflow)
        result = _poll_status(url, prompt_id, timeout=300, scene_id=None)

        if result.get("status") != "done":
            raise Exception(f"Render failed: {result}")

        # Download the generated image
        outputs = result.get("outputs", {})
        image_info = None
        for node_id, out in outputs.items():
            if 'images' in out and out['images']:
                image_info = out['images'][0]
                break

        if not image_info:
            raise Exception("Kein Bild in ComfyUI-Output")

        filename = image_info['filename']
        subfolder = image_info.get('subfolder', '')
        img_type = image_info.get('type', 'output')

        params = {'filename': filename, 'subfolder': subfolder, 'type': img_type}
        r2 = _requests.get(f'{url}/view', params=params, timeout=60)
        if r2.status_code != 200:
            raise Exception(f"Bild-Download fehlgeschlagen: {r2.status_code}")

        frame_filename = 'frame_{}.png'.format(frame.id)
        frame.image.save(frame_filename, ContentFile(r2.content), save=True)
        frame.status = 'done'
        frame.save()

        return JsonResponse({
            'ok': True,
            'frame_id': str(frame.id),
            'image_url': frame.image.url,
        })

    except Exception as e:
        frame.status = 'error'
        frame.error_message = str(e)[:500]
        frame.save()
        return JsonResponse({'error': str(e)}, status=500)



# === FRAME UPLOAD (lokal) ===

@login_required
@require_POST
@csrf_exempt
def frame_upload(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    image = request.FILES.get('image')
    frame_type = request.POST.get('frame_type', 'unassigned')
    name = request.POST.get('name', 'Upload')

    if not image:
        return JsonResponse({'error': 'Bild erforderlich'}, status=400)

    frame = GeneratedFrame.objects.create(
        project=project,
        prompt='Upload: {}'.format(name),
        frame_type=frame_type,
        status='done',
    )
    frame.image.save('upload_{}_{}'.format(frame.id, image.name), image, save=True)

    return JsonResponse({
        'ok': True,
        'frame_id': str(frame.id),
        'image_url': frame.image.url,
    })


@login_required
@require_POST
@csrf_exempt
def frame_update_type(request, frame_id):
    frame = get_object_or_404(GeneratedFrame, pk=frame_id, project__user=request.user)
    frame_type = request.POST.get('frame_type', 'unassigned')
    if frame_type in dict(GeneratedFrame.FRAME_TYPES):
        frame.frame_type = frame_type
        frame.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'Ungueltiger Typ'}, status=400)


@login_required
@require_POST
@csrf_exempt
def frame_delete(request, frame_id):
    frame = get_object_or_404(GeneratedFrame, pk=frame_id, project__user=request.user)
    frame.delete()
    return JsonResponse({'ok': True})


# === SCENE VIEWS ===

@login_required
@require_POST
@csrf_exempt
def scene_add(request, pk):
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    prompt = request.POST.get('prompt', '').strip()
    start_frame_id = request.POST.get('start_frame')
    end_frame_id = request.POST.get('end_frame')
    duration = int(request.POST.get('duration', 5))

    start_frame = get_object_or_404(GeneratedFrame, pk=start_frame_id, project=project) if start_frame_id else None
    end_frame = get_object_or_404(GeneratedFrame, pk=end_frame_id, project=project) if end_frame_id else None

    order = project.scenes.count()
    scene = Scene.objects.create(
        project=project, prompt=prompt,
        start_frame=start_frame, end_frame=end_frame,
        duration=duration, order=order,
    )
    return JsonResponse({'ok': True, 'scene_id': str(scene.id)})


@login_required
@require_POST
@csrf_exempt
def scene_update_frames(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    data = json.loads(request.body)
    slot = data.get('slot')
    frame_id = data.get('frame_id')

    frame = None
    if frame_id:
        frame = get_object_or_404(GeneratedFrame, pk=frame_id, project=scene.project)

    if slot == 'start':
        scene.start_frame = frame
    elif slot == 'end':
        scene.end_frame = frame

    scene.save()
    return JsonResponse({'ok': True})


def _regenerate_voiceover_for_duration(scene):
    """Nach Duration-Änderung: Voiceover mit neuer Ziel-Dauer neu generieren + mux."""
    from django.core.files.base import ContentFile
    from . import tts as tts_module
    import logging
    _logger = logging.getLogger(__name__)
    try:
        audio_bytes = tts_module.generate_voiceover(scene)
        if audio_bytes:
            filename = f"voiceover_{str(scene.id)[:8]}.mp3"
            scene.audio_file.save(filename, ContentFile(audio_bytes), save=True)
            _logger.info(f"Regenerated voiceover for scene {scene.id} after duration change")
            if scene.video_file:
                try:
                    from video.tasks import _mux_all_audio_into_video
                    _mux_all_audio_into_video(scene)
                except Exception as _e:
                    _logger.warning(f"mux after duration regen failed: {_e}")
    except Exception as e:
        _logger.warning(f"Could not regenerate voiceover after duration change: {e}")


@login_required
@require_POST
@csrf_exempt
def scene_update(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    data = json.loads(request.body)
    if 'prompt' in data:
        scene.prompt = data['prompt']
    duration_changed = False
    if 'duration' in data:
        old_duration = scene.duration
        scene.duration = int(data['duration'])
        duration_changed = (old_duration != scene.duration)
    if 'model_choice' in data:
        scene.model_choice = data['model_choice']
    if 'with_audio' in data:
        scene.with_audio = bool(data['with_audio'])
    if 'start_frame_prompt' in data:
        scene.start_frame_prompt = data['start_frame_prompt']
    if 'end_frame_prompt' in data:
        scene.end_frame_prompt = data['end_frame_prompt']
    if 'voiceover_text' in data:
        scene.voiceover_text = data['voiceover_text']
    if 'frame_model' in data:
        scene.frame_model = data['frame_model']
    for of in ['text_overlay', 'overlay_pos_v', 'overlay_pos_h', 'overlay_style']:
        if of in data:
            setattr(scene, of, data[of] or '')
    # Quality fields
    for qf in ['quality_preset', 'flux_resolution', 'hunyuan_resolution', 'audio_model']:
        if qf in data:
            setattr(scene, qf, data[qf] or '')
    for qf in ['flux_steps', 'hunyuan_steps']:
        if qf in data and data[qf] not in (None, ''):
            try: setattr(scene, qf, int(data[qf]))
            except: pass
    for qf in ['flux_guidance', 'pulid_cfg', 'hunyuan_cfg', 'hunyuan_flow_shift']:
        if qf in data and data[qf] not in (None, ''):
            try: setattr(scene, qf, float(data[qf]))
            except: pass
    scene.save()
    if duration_changed and scene.audio_file and scene.voiceover_text:
        _regenerate_voiceover_for_duration(scene)
    return JsonResponse({'ok': True})


@login_required
@require_POST
@csrf_exempt
def scene_generate(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    # Allow generation even without frames (text-to-video)

    if scene.status == 'generating':
        return JsonResponse({'ok': True, 'status': 'already_generating'})

    # Check for preview/resolution query params
    preview = request.GET.get('preview') == '1'
    resolution = request.GET.get('resolution', '')  # '480p' or '720p'

    # Always use the full pipeline unless this is an explicit preview request.
    # Pipeline handles: missing frames → video render → voiceover → text overlay.
    if not preview:
        from .tasks import render_scene_pipeline_task
        result = render_scene_pipeline_task.delay(str(scene.id))
        scene.status = 'generating'
        scene.celery_task_id = result.id
        scene.save(update_fields=['status', 'celery_task_id'])
        return JsonResponse({'ok': True, 'status': 'generating_pipeline', 'task_id': result.id})

    # Preview mode: render video only, skip frame gen / voiceover / overlay
    from .tasks import render_scene_task
    result = render_scene_task.delay(str(scene.id), preview=preview, resolution=resolution)

    scene.status = 'generating'
    scene.celery_task_id = result.id
    scene.save(update_fields=['status', 'celery_task_id'])

    return JsonResponse({'ok': True, 'status': 'generating', 'task_id': result.id})


@login_required
@require_POST
@csrf_exempt


@login_required
@require_POST
@csrf_exempt
def scene_frame_generate(request, scene_id):
    """Generate start or end frame for a specific scene.

    Uses scene.start_frame_prompt or scene.end_frame_prompt and scene.frame_model.
    Attaches the generated frame to the scene as start_frame or end_frame.
    """
    import uuid
    slot = request.POST.get('slot', 'start')  # 'start' or 'end'
    if slot not in ('start', 'end'):
        return JsonResponse({'error': 'slot muss "start" oder "end" sein'}, status=400)

    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    project = scene.project

    prompt = scene.start_frame_prompt if slot == 'start' else scene.end_frame_prompt
    if not prompt or not prompt.strip():
        return JsonResponse({'error': f'Kein {slot}-Frame Prompt gesetzt'}, status=400)

    frame_model = scene.frame_model or 'nano-banana'

    # Apply frame style to prompt (photorealistic keywords etc.)
    from video.tasks import _apply_frame_style
    prompt = _apply_frame_style(prompt, getattr(scene, 'frame_style', 'photorealistic'))

    # Collect reference images — first character gives all its images (main + extras)
    character_paths = []
    other_ref_paths = []
    first_char = project.characters.first()
    if first_char:
        character_paths = first_char.all_image_paths()
    if hasattr(project, 'product') and project.product:
        other_ref_paths.append(project.product.image.path)
    if hasattr(project, 'still_image') and project.still_image:
        other_ref_paths.append(project.still_image.image.path)

    # Combined list for Gemini (which mixes everything)
    ref_image_paths = (list(character_paths) if character_paths else []) + other_ref_paths

    # Auto-fallback: FLUX+PuLID with no refs at all → Gemini
    if frame_model == "flux-pulid" and not character_paths and not other_ref_paths:
        frame_model = 'nano-banana'

    frame = GeneratedFrame.objects.create(project=project, prompt=prompt, status='generating')

    try:
        if frame_model == 'flux-pulid':
            _generate_frame_flux(frame, prompt, character_paths, other_ref_paths)
        else:
            _generate_frame_gemini(frame, prompt, ref_image_paths, request.user, frame_model)

        # Attach to scene
        if slot == 'start':
            scene.start_frame = frame
        else:
            scene.end_frame = frame
        scene.save(update_fields=[f'{slot}_frame'])

        return JsonResponse({
            'ok': True,
            'frame_id': str(frame.id),
            'image_url': frame.image.url,
            'slot': slot,
        })
    except Exception as e:
        frame.status = 'error'
        frame.error_message = str(e)[:500]
        frame.save()
        return JsonResponse({'error': str(e)}, status=500)


def _generate_frame_gemini(frame, prompt, ref_image_paths, user, frame_model='nano-banana'):
    """Generate frame using Gemini or Imagen models."""
    api_key = user.gemini_api_key
    if not api_key:
        raise Exception('Gemini API Key nicht gesetzt')

    client = genai.Client(api_key=api_key)

    # Imagen models: text-to-image only, no reference
    if frame_model in FRAME_MODEL_TO_IMAGEN:
        imagen_model = FRAME_MODEL_TO_IMAGEN[frame_model]
        response = client.models.generate_images(
            model=imagen_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1),
        )
        if response.generated_images:
            img_bytes = response.generated_images[0].image.image_bytes
            filename = 'frame_{}.png'.format(frame.id)
            frame.image.save(filename, ContentFile(img_bytes), save=True)
            frame.status = 'done'
            frame.save()
            return
        raise Exception('Kein Bild in Imagen-Antwort')

    # Gemini image models with reference support
    gemini_model = FRAME_MODEL_TO_GEMINI.get(frame_model, 'gemini-3.1-flash-image-preview')
    contents = []
    if ref_image_paths:
        contents.append('Erstelle ein Bild basierend auf diesen Referenzbildern und dem folgenden Prompt.')
        for img_path in ref_image_paths:
            img_bytes = pathlib.Path(img_path).read_bytes()
            mime = 'image/png' if img_path.endswith('.png') else 'image/jpeg'
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
    contents.append(prompt)

    response = client.models.generate_content(
        model=gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img_bytes = part.inline_data.data
            filename = 'frame_{}.png'.format(frame.id)
            frame.image.save(filename, ContentFile(img_bytes), save=True)
            frame.status = 'done'
            frame.save()
            return

    raise Exception('Kein Bild in der Gemini-Antwort')


def _build_flux_workflow(uploaded_characters, uploaded_others, prompt, seed, width=1024, height=1024, steps=24, guidance=3.5, pulid_weight=1.0):
    """Build FLUX workflow with PuLID (for character face) and Redux (for product/still refs).

    uploaded_character: filename on ComfyUI of the character image (with face) or None
    uploaded_others: list of filenames for product/still reference images
    prompt: text prompt
    seed: random seed
    """
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors",
            "type": "flux"
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux_ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
    }

    # Start with base model
    model_ref = ["1", 0]
    conditioning_ref = ["4", 0]

    # Apply PuLID for character(s) - chain multiple images for better face consistency
    if uploaded_characters:
        if isinstance(uploaded_characters, str):
            uploaded_characters = [uploaded_characters]
        # Limit to 5 images max (PuLID performance)
        uploaded_characters = uploaded_characters[:5]
        wf["7"] = {"class_type": "PulidFluxModelLoader", "inputs": {"pulid_file": "pulid_flux_v0.9.1.safetensors"}}
        wf["8"] = {"class_type": "PulidFluxInsightFaceLoader", "inputs": {"provider": "CUDA"}}
        wf["9"] = {"class_type": "PulidFluxEvaClipLoader", "inputs": {}}
        for idx, char_img in enumerate(uploaded_characters):
            load_node = f"6_{idx}"
            apply_node = f"10_{idx}"
            wf[load_node] = {"class_type": "LoadImage", "inputs": {"image": char_img}}
            # First image gets full weight, subsequent get reduced weight to avoid overfitting
            w = pulid_weight if idx == 0 else max(0.3, pulid_weight * 0.7)
            wf[apply_node] = {"class_type": "ApplyPulidFlux", "inputs": {
                "model": model_ref, "pulid_flux": ["7", 0], "eva_clip": ["9", 0],
                "face_analysis": ["8", 0], "image": [load_node, 0],
                "weight": w, "start_at": 0.0, "end_at": 1.0,
            }}
            model_ref = [apply_node, 0]

    # Apply Redux for each product/still reference
    if uploaded_others:
        wf["20"] = {"class_type": "StyleModelLoader", "inputs": {"style_model_name": "flux1-redux-dev.safetensors"}}
        wf["21"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "sigclip_vision_patch14_384.safetensors"}}

        current_cond = conditioning_ref
        for idx, img_name in enumerate(uploaded_others):
            load_node = f"30_{idx}"
            enc_node = f"31_{idx}"
            apply_node = f"32_{idx}"
            wf[load_node] = {"class_type": "LoadImage", "inputs": {"image": img_name}}
            wf[enc_node] = {"class_type": "CLIPVisionEncode", "inputs": {
                "clip_vision": ["21", 0], "image": [load_node, 0], "crop": "center"
            }}
            wf[apply_node] = {"class_type": "StyleModelApply", "inputs": {
                "conditioning": current_cond,
                "style_model": ["20", 0],
                "clip_vision_output": [enc_node, 0],
                "strength": 0.8 if idx == 0 else 0.5,
                "strength_type": "multiply"
            }}
            current_cond = [apply_node, 0]
        conditioning_ref = current_cond

    # Sampler chain
    wf["11"] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
    wf["12"] = {"class_type": "BasicGuider", "inputs": {"model": model_ref, "conditioning": conditioning_ref}}
    wf["13"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    wf["14"] = {"class_type": "BasicScheduler", "inputs": {"scheduler": "simple", "steps": steps, "denoise": 1.0, "model": model_ref}}
    wf["15"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    wf["16"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": ["15", 0], "guider": ["12", 0], "sampler": ["13", 0],
        "sigmas": ["14", 0], "latent_image": ["11", 0],
    }}
    wf["17"] = {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["3", 0]}}
    wf["18"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "flux_frame", "images": ["17", 0]}}

    return wf


def _generate_frame_flux(frame, prompt, character_path=None, other_ref_paths=None):
    """character_path can be a single path string or a list of paths (multi-image PuLID)."""
    """Generate frame using FLUX with optional PuLID (character) + Redux (products/stills)."""
    import random
    import requests as _requests
    from video.tasks import _ensure_runpod_running, _upload_image_to_comfyui, _submit_workflow, _poll_status

    url = _ensure_runpod_running()
    if not url:
        raise Exception('RunPod Pod nicht erreichbar')

    uploaded_character = []
    uploaded_others = []

    if character_path:
        paths = character_path if isinstance(character_path, (list, tuple)) else [character_path]
        for p in paths:
            up = _upload_image_to_comfyui(url, p)
            if up:
                uploaded_character.append(up)
        if not uploaded_character:
            raise Exception('Character-Bild Upload fehlgeschlagen')

    if other_ref_paths:
        for path in other_ref_paths:
            name = _upload_image_to_comfyui(url, path)
            if name:
                uploaded_others.append(name)

    if not uploaded_character and not uploaded_others:
        raise Exception('Mindestens ein Referenzbild (Character/Produkt/Still) erforderlich')

    seed = random.randint(0, 2**31 - 1)
    # Resolve resolution from scene (or default)
    RES_MAP = {'1024': (1024, 1024), '1080_h': (1920, 1080), '1080_v': (1080, 1920), '2048': (2048, 2048)}
    scene_obj = getattr(frame, 'scene', None) or getattr(frame, 'project_frame', None)
    flux_res = '1024'
    flux_steps = 24
    flux_guidance = 3.5
    pulid_cfg = 1.0
    try:
        from video.models import Scene
        scene_for_frame = Scene.objects.filter(start_frame=frame).first() or Scene.objects.filter(end_frame=frame).first()
        if scene_for_frame:
            flux_res = scene_for_frame.flux_resolution or '1024'
            flux_steps = scene_for_frame.flux_steps or 24
            flux_guidance = scene_for_frame.flux_guidance or 3.5
            pulid_cfg = scene_for_frame.pulid_cfg or 1.0
    except Exception:
        pass
    width, height = RES_MAP.get(flux_res, (1024, 1024))
    # Ensure uploaded_character is a list for multi-image PuLID
    if isinstance(uploaded_character, str):
        uploaded_characters = [uploaded_character]
    elif isinstance(uploaded_character, list):
        uploaded_characters = uploaded_character
    else:
        uploaded_characters = []
    workflow = _build_flux_workflow(uploaded_characters, uploaded_others, prompt, seed,
                                     width=width, height=height, steps=flux_steps,
                                     guidance=flux_guidance, pulid_weight=pulid_cfg)

    prompt_id = _submit_workflow(url, workflow)
    result = _poll_status(url, prompt_id, timeout=300, scene_id=None)
    if result.get("status") != "done":
        raise Exception(f"FLUX Render fehlgeschlagen: {result}")

    outputs = result.get("outputs", {})
    image_info = None
    for node_id, out in outputs.items():
        if 'images' in out and out['images']:
            image_info = out['images'][0]
            break
    if not image_info:
        raise Exception("Kein Bild in ComfyUI-Output")

    filename = image_info['filename']
    params = {'filename': filename, 'subfolder': image_info.get('subfolder', ''), 'type': image_info.get('type', 'output')}
    r2 = _requests.get(f'{url}/view', params=params, timeout=60)
    if r2.status_code != 200:
        raise Exception(f"Bild-Download fehlgeschlagen: {r2.status_code}")

    frame_filename = 'frame_{}.png'.format(frame.id)
    frame.image.save(frame_filename, ContentFile(r2.content), save=True)
    frame.status = 'done'
    frame.save()





@login_required
@require_POST
@csrf_exempt
def scene_pipeline(request, scene_id):
    """Trigger full pipeline: frames -> video -> voiceover"""
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    if scene.status == 'generating':
        return JsonResponse({'ok': True, 'status': 'already_generating'})
    from .tasks import render_scene_pipeline_task
    result = render_scene_pipeline_task.delay(str(scene.id))
    scene.status = 'generating'
    scene.celery_task_id = result.id
    scene.save(update_fields=['status', 'celery_task_id'])
    return JsonResponse({'ok': True, 'task_id': result.id})


@login_required
@require_POST
@csrf_exempt
def project_pipeline_all(request, pk):
    """Trigger the phase-batched pipeline for ALL scenes in a project:
    Phase A: all frames+video renders (Hunyuan model stays hot),
    Phase B: all text overlays (ffmpeg CPU),
    Phase C: all voiceovers + audio mux (XTTS)."""
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    from .tasks import render_project_batched_task
    result = render_project_batched_task.delay(str(project.id))
    started = 0
    for scene in project.scenes.all().order_by('order'):
        if scene.status == 'generating':
            continue
        if scene.status == 'done' and scene.rendered_videos.filter(status='done').exists():
            continue
        scene.status = 'generating'
        scene.celery_task_id = result.id
        scene.error_message = 'In Warteschlange'
        scene.save(update_fields=['status', 'celery_task_id', 'error_message'])
        started += 1
    return JsonResponse({'ok': True, 'started': started, 'task_id': result.id})


def scene_delete(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    scene.delete()
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
@login_required
def cancel_scene(request, scene_id):
    """Hard-cancel a scene render: revoke Celery task, interrupt ComfyUI job,
    clear ComfyUI queue, and reset scene status."""
    from video.models import Scene
    from celery.result import AsyncResult
    import requests as _req
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)

    errors = []

    # 1. Revoke Celery task with SIGTERM → kills worker subprocess
    if scene.celery_task_id:
        try:
            AsyncResult(scene.celery_task_id).revoke(terminate=True, signal='SIGTERM')
        except Exception as e:
            errors.append(f'celery_revoke: {e}')

    # 2. Interrupt the currently running ComfyUI job on the pod
    try:
        from .tasks import _get_runpod_comfyui_url
        url = _get_runpod_comfyui_url()
        try:
            _req.post(f'{url}/interrupt', timeout=5)
        except Exception as e:
            errors.append(f'comfyui_interrupt: {e}')
        # 3. Clear pending queue
        try:
            _req.post(f'{url}/queue', json={'clear': True}, timeout=5)
        except Exception as e:
            errors.append(f'comfyui_queue_clear: {e}')
    except Exception as e:
        errors.append(f'pod_url: {e}')

    # 4. Reset scene status
    scene.status = 'pending'
    scene.error_message = 'Abgebrochen durch Nutzer'
    scene.render_progress = 0
    scene.celery_task_id = None
    scene.save(update_fields=['status', 'error_message', 'render_progress', 'celery_task_id'])

    return JsonResponse({'ok': True, 'status': 'cancelled', 'warnings': errors})

@csrf_exempt
def scene_generate_all(request, pk):
    from django.shortcuts import get_object_or_404, redirect
    from video.models import VideoProject
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    for scene in project.scenes.all():
        if scene.status in ('pending', 'error'):
            scene.status = 'generating'
            scene.error_message = ''
            scene.save()
            render_scene_task.delay(str(scene.id))
    return redirect('video:project_detail', pk=pk)

@login_required
def scene_download_all(request, pk):
    from django.shortcuts import get_object_or_404
    from django.http import HttpResponse, FileResponse
    from .models import VideoProject, Scene
    import subprocess, tempfile, os, zipfile

    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    mode = request.GET.get('mode', 'individual')
    scenes = project.scenes.filter(status='done').order_by('order')

    # Collect video files (prefer selected SceneVideo, fallback to scene.video_file)
    video_paths = []
    for s in scenes:
        selected = s.rendered_videos.filter(is_selected=True).first()
        if selected and selected.video_file:
            video_paths.append(selected.video_file.path)
        elif s.video_file:
            video_paths.append(s.video_file.path)

    if not video_paths:
        return redirect('video:project_detail', pk=pk)

    if mode == 'merged':
        # Merge via ffmpeg filter_complex concat. Re-encodes to a uniform
        # 1920x1080/30fps/stereo-48k target so mismatched codecs/resolutions
        # AND mixed audio/silent inputs all concat cleanly (silent inputs get
        # generated silence via anullsrc so concat's a=1 requirement holds).
        try:
            def _has_audio(path):
                try:
                    r = subprocess.run(
                        ['ffprobe', '-v', 'error', '-select_streams', 'a',
                         '-show_entries', 'stream=codec_type',
                         '-of', 'csv=p=0', path],
                        capture_output=True, text=True, timeout=10)
                    return bool(r.stdout.strip())
                except Exception:
                    return False
            has_audio = [_has_audio(vp) for vp in video_paths]

            output_path = tempfile.mktemp(suffix='.mp4')
            cmd = ['ffmpeg', '-y']
            for vp in video_paths:
                cmd += ['-i', vp]
            silent_idx_start = len(video_paths)
            for ha in has_audio:
                if not ha:
                    cmd += ['-f', 'lavfi', '-t', '60',
                            '-i', 'anullsrc=r=48000:cl=stereo']

            parts = []
            silent_counter = 0
            for i in range(len(video_paths)):
                parts.append(
                    f'[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,'
                    f'pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]')
                if has_audio[i]:
                    parts.append(
                        f'[{i}:a]aformat=sample_rates=48000:'
                        f'channel_layouts=stereo[a{i}]')
                else:
                    parts.append(
                        f'[{silent_idx_start + silent_counter}:a]'
                        f'aformat=sample_rates=48000:channel_layouts=stereo[a{i}]')
                    silent_counter += 1
            concat_inputs = ''.join(f'[v{i}][a{i}]' for i in range(len(video_paths)))

            # If project has a music track, mix it into the merged output
            project_music = project.music_file.path if project.music_file else None
            if project_music and os.path.exists(project_music):
                music_vol = project.music_volume if hasattr(project, 'music_volume') else 0.3
                music_input_idx = len(video_paths) + silent_counter
                cmd += ['-i', project_music]
                parts.append(
                    f'{concat_inputs}concat=n={len(video_paths)}:v=1:a=1[outv][outa_raw]')
                parts.append(
                    f'[{music_input_idx}:a]volume={music_vol},aloop=loop=-1:size=2e+09[music_loop]')
                parts.append(
                    f'[outa_raw][music_loop]amix=inputs=2:duration=shortest[outa]')
            else:
                parts.append(
                    f'{concat_inputs}concat=n={len(video_paths)}:v=1:a=1[outv][outa]')

            filter_complex = ';'.join(parts)
            cmd += ['-filter_complex', filter_complex,
                    '-map', '[outv]', '-map', '[outa]']

            cmd += ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '20',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart',
                    output_path]
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0 or not os.path.exists(output_path):
                import logging
                logging.getLogger('django').error(
                    'scene_download_all merge failed: %s',
                    result.stderr.decode('utf-8', 'ignore')[-500:])
                return redirect('video:project_detail', pk=pk)
            response = FileResponse(open(output_path, 'rb'), content_type='video/mp4')
            response['Content-Disposition'] = f'attachment; filename="{project.name}_merged.mp4"'
            return response
        except Exception as e:
            import logging
            logging.getLogger('django').error(
                'scene_download_all merge exception: %s', e)
            return redirect('video:project_detail', pk=pk)
    else:
        # Individual videos as ZIP
        try:
            output_path = tempfile.mktemp(suffix='.zip')
            with zipfile.ZipFile(output_path, 'w') as zf:
                for i, vp in enumerate(video_paths):
                    zf.write(vp, f'scene_{i+1}.mp4')
            response = FileResponse(open(output_path, 'rb'), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{project.name}_scenes.zip"'
            return response
        except Exception as e:
            return redirect('video:project_detail', pk=pk)

def thumbnail(request, pk, frame_type):
    from django.http import HttpResponse, HttpResponseNotFound
    from .models import Scene
    from pathlib import Path as _Path
    try:
        scene = Scene.objects.get(id=pk)
        frame = scene.start_frame if frame_type == 'start' else scene.end_frame
        if frame and frame.image:
            img_data = _Path(frame.image.path).read_bytes()
            import imghdr
            img_type = imghdr.what(None, img_data) or "jpeg"
            return HttpResponse(img_data, content_type=f"image/{img_type}")
    except Scene.DoesNotExist:
        pass
    return HttpResponseNotFound()

@csrf_exempt
def scene_update(request, scene_id):
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from video.models import Scene
    import json as _json, logging as _log
    _logger = _log.getLogger('django')
    scene = get_object_or_404(Scene, pk=scene_id)
    if request.method == 'POST':
        # Support both JSON body and form POST
        try:
            data = _json.loads(request.body) if request.body else {}
        except:
            data = {}
        # Merge with POST data
        for field in ['prompt', 'negative_prompt']:
            val = data.get(field) or request.POST.get(field)
            if val is not None:
                setattr(scene, field, val)
        for field in ['model_choice', 'gpu_choice', 'aspect_ratio']:
            val = data.get(field) or request.POST.get(field)
            if val is not None:
                setattr(scene, field, val)
        old_duration = scene.duration
        for field in ['duration', 'num_steps', 'seed', 'fps']:
            val = data.get(field) or request.POST.get(field)
            if val is not None:
                setattr(scene, field, int(val))
        duration_changed = (old_duration != scene.duration)
        for field in ['guidance_scale']:
            val = data.get(field) or request.POST.get(field)
            if val is not None:
                setattr(scene, field, float(val))
        # Text fields for pipeline (saved as-is, including empty strings)
        for field in ['start_frame_prompt', 'end_frame_prompt', 'voiceover_text', 'frame_model', 'frame_style', 'audio_model', 'quality_preset', 'flux_resolution', 'hunyuan_resolution', 'text_overlay', 'overlay_pos_v', 'overlay_pos_h', 'overlay_style', 'music_prompt', 'music_genre']:
            if field in data:
                setattr(scene, field, data[field] or '')
            elif field in request.POST:
                setattr(scene, field, request.POST.get(field, ''))
        # Integer quality fields
        for field in ['flux_steps', 'hunyuan_steps']:
            val = data.get(field) or request.POST.get(field)
            if val not in (None, ''):
                try: setattr(scene, field, int(val))
                except: pass
        # Float quality fields
        for field in ['flux_guidance', 'pulid_cfg', 'hunyuan_cfg', 'hunyuan_flow_shift', 'music_volume']:
            val = data.get(field) or request.POST.get(field)
            if val not in (None, ''):
                try: setattr(scene, field, float(val))
                except: pass
        scene.save()
        if duration_changed and scene.audio_file and scene.voiceover_text:
            _regenerate_voiceover_for_duration(scene)
    return JsonResponse({"ok": True})

@login_required
@require_POST
@csrf_exempt
def scene_generate_music(request, scene_id):
    import json as _json
    from django.core.files.base import ContentFile
    from . import tts as tts_module

    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    try:
        data = _json.loads(request.body) if request.body else {}
    except Exception:
        data = {}

    prompt = data.get('music_prompt', '').strip()
    genre = data.get('music_genre', '')
    if prompt:
        scene.music_prompt = prompt
    if genre is not None:
        scene.music_genre = genre
    scene.save(update_fields=['music_prompt', 'music_genre'])

    if not prompt and not genre:
        return JsonResponse({'error': 'Bitte Genre oder Prompt angeben'}, status=400)

    try:
        music_bytes = tts_module.generate_musicgen(
            prompt, duration_sec=float(scene.duration or 10), genre=genre)
        if not music_bytes:
            return JsonResponse({'error': 'Musik-Generierung leer'}, status=500)
        filename = f"music_{str(scene.id)[:8]}.mp3"
        scene.music_file.save(filename, ContentFile(music_bytes), save=True)
        if scene.video_file or scene.rendered_videos.filter(status='done').exists():
            try:
                from video.tasks import _mux_all_audio_into_video
                _mux_all_audio_into_video(scene)
            except Exception as _e:
                import traceback; traceback.print_exc()
        return JsonResponse({'status': 'ok', 'music_url': scene.music_file.url})
    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'error': str(e)[:400]}, status=500)


@csrf_exempt
def scene_delete(request, scene_id):
    from django.shortcuts import get_object_or_404, redirect
    from video.models import Scene
    scene = get_object_or_404(Scene, pk=scene_id)
    project_id = scene.project_id
    scene.delete()
    return redirect('video:project_detail', pk=project_id)


# ============ API Key Management ============


def character_thumbnail(request, char_id):
    from django.http import HttpResponse, HttpResponseNotFound
    from .models import Character
    from pathlib import Path as _Path
    try:
        char = Character.objects.get(id=char_id)
        if char.image:
            img_data = _Path(char.image.path).read_bytes()
            import imghdr
            img_type = imghdr.what(None, img_data) or "jpeg"
            return HttpResponse(img_data, content_type=f"image/{img_type}")
    except Character.DoesNotExist:
        pass
    return HttpResponseNotFound()


def product_thumbnail(request, prod_id):
    from django.http import HttpResponse, HttpResponseNotFound
    from .models import Product
    from pathlib import Path as _Path
    try:
        prod = Product.objects.get(id=prod_id)
        if prod.image:
            img_data = _Path(prod.image.path).read_bytes()
            import imghdr
            img_type = imghdr.what(None, img_data) or "jpeg"
            return HttpResponse(img_data, content_type=f"image/{img_type}")
    except Product.DoesNotExist:
        pass
    return HttpResponseNotFound()


def stillimage_thumbnail(request, still_id):
    from django.http import HttpResponse, HttpResponseNotFound
    from .models import StillImage
    from pathlib import Path as _Path
    try:
        still = StillImage.objects.get(id=still_id)
        if still.image:
            img_data = _Path(still.image.path).read_bytes()
            import imghdr
            img_type = imghdr.what(None, img_data) or "jpeg"
            return HttpResponse(img_data, content_type=f"image/{img_type}")
    except StillImage.DoesNotExist:
        pass
    return HttpResponseNotFound()


def frame_thumbnail(request, frame_id):
    from django.http import HttpResponse, HttpResponseNotFound
    from .models import GeneratedFrame
    from pathlib import Path as _Path
    try:
        frame = GeneratedFrame.objects.get(id=frame_id)
        if frame.image:
            img_data = _Path(frame.image.path).read_bytes()
            import imghdr
            img_type = imghdr.what(None, img_data) or "jpeg"
            return HttpResponse(img_data, content_type=f"image/{img_type}")
    except GeneratedFrame.DoesNotExist:
        pass
    return HttpResponseNotFound()

def api_keys(request):
    from django.shortcuts import render
    from video.models import VideoAPIKey
    keys = VideoAPIKey.objects.filter(user=request.user)
    return render(request, 'video/api_keys.html', {'keys': keys})

def api_key_save(request):
    from django.shortcuts import redirect
    from video.models import VideoAPIKey
    if request.method == 'POST':
        provider = request.POST.get('provider', 'laozhang')
        api_key = request.POST.get('api_key', '').strip()
        if api_key:
            VideoAPIKey.objects.update_or_create(
                user=request.user, provider=provider,
                defaults={'api_key': api_key, 'is_active': True}
            )
    return redirect('video:api_keys')

def api_key_delete(request, key_id):
    from django.shortcuts import get_object_or_404, redirect
    from video.models import VideoAPIKey
    key = get_object_or_404(VideoAPIKey, pk=key_id, user=request.user)
    key.delete()
    return redirect('video:api_keys')


# ============ Voiceover ============

@csrf_exempt
def scene_voiceover(request, scene_id):
    import json
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from django.core.files.base import ContentFile
    from video.models import Scene
    from . import tts as tts_module

    scene = get_object_or_404(Scene, pk=scene_id)
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    text = data.get("voiceover_text", "").strip()
    audio_model = data.get("audio_model", "piper-thorsten-medium")

    if not text:
        return JsonResponse({"error": "Kein Text angegeben"}, status=400)

    # Word limit based on video duration
    max_words = max(1, int(scene.duration * 2.5))
    word_count = len(text.split())
    if word_count > max_words:
        return JsonResponse({"error": f"Text zu lang: {word_count} Wörter, max. {max_words} ({scene.duration}s Video)"}, status=400)

    scene.voiceover_text = text
    scene.audio_model = audio_model
    scene.save()

    try:
        audio_bytes = tts_module.generate_voiceover(scene)
        if not audio_bytes:
            return JsonResponse({"error": "Voiceover-Generierung leer"}, status=500)

        filename = f"voiceover_{str(scene.id)[:8]}.mp3"
        scene.audio_file.save(filename, ContentFile(audio_bytes), save=True)
        # Auto-mux into video if video exists
        if scene.video_file:
            try:
                from video.tasks import _mux_audio_into_video
                _mux_audio_into_video(scene)
            except Exception as _e:
                import traceback; traceback.print_exc()
        return JsonResponse({"status": "ok", "audio_url": scene.audio_file.url})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)[:400]}, status=500)



@csrf_exempt
@login_required
def scene_upload_voice_ref(request, scene_id):
    """Upload eines Voice-Clone Referenzaudios für XTTS-Clone.
    Konvertiert beliebiges Audioformat (webm/ogg/mp3/...) via ffmpeg zu 16kHz mono WAV."""
    import subprocess, tempfile, os
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from django.core.files.base import ContentFile
    from video.models import Scene

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    file = request.FILES.get('voice_reference_audio')
    if not file:
        return JsonResponse({'error': 'Keine Datei'}, status=400)

    if file.size > 15 * 1024 * 1024:
        return JsonResponse({'error': 'Datei zu groß (max 15 MB)'}, status=400)

    # Temp-Save und ffmpeg-Konvertierung zu 16kHz mono WAV
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(file.name)[1] or '.bin', delete=False) as tmp_in:
        for chunk in file.chunks():
            tmp_in.write(chunk)
        in_path = tmp_in.name

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_out:
        out_path = tmp_out.name

    try:
        result = subprocess.run([
            'ffmpeg', '-y', '-i', in_path,
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
            out_path
        ], capture_output=True, timeout=60)
        if result.returncode != 0:
            return JsonResponse({
                'error': f'Audio-Konvertierung fehlgeschlagen: {result.stderr.decode("utf-8", "ignore")[-200:]}'
            }, status=400)

        # Dauer prüfen
        dur_result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'default=nk=1:nw=1', out_path
        ], capture_output=True, text=True, timeout=15)
        duration = float(dur_result.stdout.strip() or 0)
        if duration < 3:
            return JsonResponse({'error': f'Aufnahme zu kurz ({duration:.1f}s) — mind. 3 Sekunden'}, status=400)

        with open(out_path, 'rb') as f:
            scene.voice_reference_audio.save(
                f'voice_clone_{str(scene.id)[:8]}.wav',
                ContentFile(f.read()),
                save=True
            )
        return JsonResponse({
            'status': 'ok',
            'path': scene.voice_reference_audio.url,
            'duration': round(duration, 1)
        })
    finally:
        for p in (in_path, out_path):
            try:
                os.remove(p)
            except Exception:
                pass


@csrf_exempt
@login_required
def scene_voiceover_preview(request, scene_id):
    """Generate voiceover preview WITHOUT requiring a rendered video.
    Does not check scene.status, does not check word limits strictly."""
    import json
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from django.core.files.base import ContentFile
    from video.models import Scene
    from . import tts as tts_module

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    text = data.get("voiceover_text", "").strip()
    audio_model = data.get("audio_model", scene.audio_model or "piper-thorsten-medium")

    if not text:
        return JsonResponse({"error": "Kein Text angegeben"}, status=400)

    # Save text + model to scene for persistence (don't wait for full render)
    scene.voiceover_text = text
    scene.audio_model = audio_model
    scene.save(update_fields=["voiceover_text", "audio_model"])

    try:
        audio_bytes = tts_module.generate_voiceover(scene)
        if not audio_bytes:
            return JsonResponse({"error": "Leere Audio-Ausgabe"}, status=500)
        filename = f"voiceover_{str(scene.id)[:8]}.mp3"
        scene.audio_file.save(filename, ContentFile(audio_bytes), save=True)
        # Auto-mux into video if video exists
        if scene.video_file:
            try:
                from video.tasks import _mux_audio_into_video
                _mux_audio_into_video(scene)
            except Exception as _e:
                import traceback; traceback.print_exc()
        return JsonResponse({"status": "ok", "audio_url": scene.audio_file.url})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)[:400]}, status=500)


@csrf_exempt
@login_required
def scene_apply_overlay(request, scene_id):
    """Trigger text overlay render as a Celery task."""
    import json
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from video.models import Scene

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

    # Save overlay settings to scene
    for field in ['text_overlay', 'overlay_pos_v', 'overlay_pos_h', 'overlay_style']:
        if field in data:
            setattr(scene, field, data[field] or '')
    scene.save()

    if not scene.text_overlay or not scene.text_overlay.strip():
        return JsonResponse({'error': 'Kein Overlay-Text eingegeben'}, status=400)

    if not scene.video_file and not scene.rendered_videos.exists():
        return JsonResponse({'error': 'Kein Video zum Überlagern vorhanden'}, status=400)

    from video.tasks import apply_text_overlay_task
    apply_text_overlay_task.delay(str(scene.id))
    return JsonResponse({'status': 'queued'})





def _combine_neg(user_neg):
    DEFAULT_NEG = "anime, cartoon, drawing, illustration, 2d, painted, rendered, cel-shaded, low quality, blurry, distorted, deformed, warped, flickering, jitter, low contrast, oversaturated, pixelated, compression artifacts, watermark, text, logo, bad anatomy, extra limbs, mutated face, disfigured"
    user_neg = (user_neg or '').strip()
    return f"{DEFAULT_NEG}, {user_neg}"[:1000] if user_neg else DEFAULT_NEG

@csrf_exempt
@login_required
@login_required
@require_POST
@csrf_exempt
def project_update_music(request, pk):
    import json as _json
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    try:
        data = _json.loads(request.body) if request.body else {}
    except Exception:
        data = {}
    changed = []
    for field in ['music_genre', 'music_prompt']:
        if field in data:
            setattr(project, field, data[field] or '')
            changed.append(field)
    if 'music_volume' in data:
        try:
            project.music_volume = float(data['music_volume'])
            changed.append('music_volume')
        except Exception:
            pass
    if changed:
        project.save(update_fields=changed)
    return JsonResponse({'ok': True})


@login_required
@require_POST
@csrf_exempt
def project_generate_music(request, pk):
    from django.core.files.base import ContentFile
    from . import tts as tts_module
    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    prompt = (project.music_prompt or '').strip()
    genre = project.music_genre or ''
    if not prompt and not genre:
        return JsonResponse({'error': 'Bitte Genre oder Prompt angeben'}, status=400)
    total_dur = sum(s.duration for s in project.scenes.all())
    gen_dur = min(max(total_dur, 5), 30)
    try:
        music_bytes = tts_module.generate_musicgen(prompt, duration_sec=gen_dur, genre=genre)
        if not music_bytes:
            return JsonResponse({'error': 'Musik-Generierung leer'}, status=500)
        filename = f"project_music_{str(project.id)[:8]}.mp3"
        project.music_file.save(filename, ContentFile(music_bytes), save=True)
        return JsonResponse({'status': 'ok', 'music_url': project.music_file.url})
    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'error': str(e)[:400]}, status=500)


def project_import_script(request, pk):
    """Parse a structured script and create Scenes from it."""
    import json
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from video.models import VideoProject, Scene
    from video.script_parser import parse_script, extract_project_metadata

    project = get_object_or_404(VideoProject, pk=pk, user=request.user)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    script_text = data.get('script_text', '').strip()
    replace_scenes = data.get('replace', False)

    if not script_text:
        return JsonResponse({'error': 'Kein Skript-Text'}, status=400)

    scenes_data = parse_script(script_text)
    if not scenes_data:
        return JsonResponse({'error': 'Keine Szenen im Skript erkannt. Format prüfen: "SZENE 1 — ..." Header erforderlich.'}, status=400)

    # Optional: replace existing scenes
    if replace_scenes:
        project.scenes.all().delete()
        offset = 0
    else:
        offset = project.scenes.count()

    # Extract metadata for project defaults
    meta = extract_project_metadata(script_text)
    update_fields = []
    if meta.get('title') and not project.name:
        project.name = meta['title'][:200]
        update_fields.append('name')
    if meta.get('music_genre'):
        project.music_genre = meta['music_genre']
        update_fields.append('music_genre')
    if meta.get('music_prompt'):
        project.music_prompt = meta['music_prompt'][:500]
        update_fields.append('music_prompt')
    if meta.get('music_volume') is not None:
        project.music_volume = meta['music_volume']
        update_fields.append('music_volume')
    if update_fields:
        project.save(update_fields=update_fields)

    created_ids = []
    for i, sd in enumerate(scenes_data):
        scene = Scene.objects.create(
            project=project,
            order=offset + sd['order'],
            duration=sd['duration'],
            prompt=sd['prompt'][:2000] if sd['prompt'] else '',
            start_frame_prompt=sd['start_frame_prompt'][:2000] if sd['start_frame_prompt'] else '',
            voiceover_text=sd['voiceover_text'][:1000] if sd['voiceover_text'] else '',
            text_overlay=sd['text_overlay'][:500] if sd['text_overlay'] else '',
            negative_prompt=_combine_neg(sd.get('negative_prompt', '')),
            music_prompt=sd.get('music_prompt', '')[:500],
            music_genre=sd.get('music_genre', '')[:20],
            music_volume=sd.get('music_volume', 0.3),
            aspect_ratio=meta.get('aspect_ratio', 'auto'),
            status='pending',
        )
        created_ids.append(str(scene.id))

    return JsonResponse({
        'status': 'ok',
        'created': len(created_ids),
        'scene_ids': created_ids,
    })

# ============================================================
# VoiceClone Views (gespeicherte Voice-Clones)
# ============================================================

@csrf_exempt
@login_required
def voice_clones_list(request):
    """GET: Liste aller Voice-Clones des Users.
    Optional query param ?scene_id=<uuid> returns active_clone_id."""
    from django.http import JsonResponse
    from video.models import VoiceClone, Scene

    clones = VoiceClone.objects.filter(user=request.user).order_by('-created_at')
    data = [{
        'id': str(c.id),
        'name': c.name,
        'audio_url': c.audio_file.url if c.audio_file else '',
        'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
    } for c in clones]

    active_clone_id = None
    scene_id = request.GET.get('scene_id')
    if scene_id:
        try:
            scene = Scene.objects.filter(pk=scene_id, project__user=request.user).first()
            if scene and scene.voice_clone_id:
                active_clone_id = str(scene.voice_clone_id)
        except Exception:
            pass

    return JsonResponse({'clones': data, 'active_clone_id': active_clone_id})


@csrf_exempt
@login_required
def voice_clones_create(request):
    """POST: Erstelle gespeicherten Voice-Clone aus hochgeladener Audio-Datei.
    Akzeptiert beliebige Audioformate (werden zu 16kHz mono WAV konvertiert)."""
    import subprocess, tempfile, os
    from django.http import JsonResponse
    from django.core.files.base import ContentFile
    from video.models import VoiceClone

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    name = (request.POST.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Name fehlt'}, status=400)
    if len(name) > 100:
        return JsonResponse({'error': 'Name zu lang (max 100)'}, status=400)

    file = request.FILES.get('audio_file')
    if not file:
        return JsonResponse({'error': 'Keine Datei'}, status=400)
    if file.size > 15 * 1024 * 1024:
        return JsonResponse({'error': 'Datei zu groß (max 15 MB)'}, status=400)

    # ffmpeg convert
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(file.name)[1] or '.bin', delete=False) as tmp_in:
        for chunk in file.chunks():
            tmp_in.write(chunk)
        in_path = tmp_in.name
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_out:
        out_path = tmp_out.name
    try:
        result = subprocess.run([
            'ffmpeg', '-y', '-i', in_path,
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
            out_path
        ], capture_output=True, timeout=60)
        if result.returncode != 0:
            return JsonResponse({'error': f'Audio-Konvertierung fehlgeschlagen'}, status=400)

        dur_result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'default=nk=1:nw=1', out_path
        ], capture_output=True, text=True, timeout=15)
        duration = float(dur_result.stdout.strip() or 0)
        if duration < 3:
            return JsonResponse({'error': f'Aufnahme zu kurz ({duration:.1f}s) — mind. 3 Sekunden'}, status=400)

        clone = VoiceClone(user=request.user, name=name)
        with open(out_path, 'rb') as f:
            clone.audio_file.save(f'vclone_{name[:20]}.wav', ContentFile(f.read()), save=False)
        clone.save()
        return JsonResponse({
            'status': 'ok',
            'id': str(clone.id),
            'name': clone.name,
            'audio_url': clone.audio_file.url,
            'duration': round(duration, 1),
        })
    finally:
        for p in (in_path, out_path):
            try:
                os.remove(p)
            except Exception:
                pass


@csrf_exempt
@login_required
def voice_clones_delete(request, clone_id):
    """POST/DELETE: Lösche Voice-Clone."""
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from video.models import VoiceClone

    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'POST/DELETE only'}, status=405)

    clone = get_object_or_404(VoiceClone, pk=clone_id, user=request.user)
    if clone.audio_file:
        try:
            clone.audio_file.delete(save=False)
        except Exception:
            pass
    clone.delete()
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@login_required
def scene_apply_voice_clone(request, scene_id):
    """POST: Setzt scene.voice_reference_audio auf eine gespeicherte Voice-Clone."""
    import json
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    from django.core.files.base import ContentFile
    from video.models import Scene, VoiceClone

    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    clone_id = data.get('clone_id')
    if not clone_id:
        return JsonResponse({'error': 'clone_id fehlt'}, status=400)

    clone = get_object_or_404(VoiceClone, pk=clone_id, user=request.user)

    # Kopiere die Clone-Audio als scene.voice_reference_audio
    with clone.audio_file.open('rb') as f:
        scene.voice_reference_audio.save(
            f'voice_clone_{str(scene.id)[:8]}.wav',
            ContentFile(f.read()),
            save=False
        )
    scene.voice_clone = clone
    scene.save()
    return JsonResponse({
        'status': 'ok',
        'clone_id': str(clone.id),
        'clone_name': clone.name,
        'path': scene.voice_reference_audio.url,
    })


# ============================================================
# SceneVideo Views
# ============================================================

@login_required
@require_POST
@csrf_exempt
def select_scene_video(request, scene_id, video_id):
    """Select a rendered video as the active video for a scene."""
    from .models import SceneVideo
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    video = get_object_or_404(SceneVideo, pk=video_id, scene=scene)
    scene.rendered_videos.update(is_selected=False)
    video.is_selected = True
    video.save(update_fields=["is_selected"])
    return JsonResponse({"ok": True, "video_id": str(video_id)})


@login_required
def scene_videos(request, scene_id):
    """List all rendered videos for a scene."""
    from .models import SceneVideo
    scene = get_object_or_404(Scene, pk=scene_id, project__user=request.user)
    videos = scene.rendered_videos.all().order_by("-created_at")
    data = []
    for v in videos:
        data.append({
            "id": str(v.id), "status": v.status, "model_used": v.model_used,
            "render_duration_sec": v.render_duration_sec, "render_cost": v.render_cost,
            "is_selected": v.is_selected,
            "video_url": v.video_file.url if v.video_file else None,
            "created_at": v.created_at.isoformat(),
            "error_message": v.error_message if v.status == "error" else "",
        })
    return JsonResponse({"videos": data})


@login_required
@require_POST
@csrf_exempt
def delete_scene_video(request, video_id):
    """Delete a rendered video."""
    from .models import SceneVideo
    video = get_object_or_404(SceneVideo, pk=video_id, scene__project__user=request.user)
    scene = video.scene
    was_selected = video.is_selected
    video.delete()
    if was_selected:
        latest = scene.rendered_videos.first()
        if latest:
            latest.is_selected = True
            latest.save(update_fields=["is_selected"])
    return JsonResponse({"ok": True})


@login_required
def model_info(request):
    """Return model capabilities for frontend."""
    from .comfyui_workflows.builder import get_model_info
    return JsonResponse(get_model_info())


# ============ AJAX Status API ============

def scene_status_api(request, pk):
    from django.shortcuts import get_object_or_404 as _get
    from django.http import JsonResponse
    from video.models import Scene, VideoProject
    project = _get(VideoProject, pk=pk)
    scenes = Scene.objects.filter(project=project)
    data = []
    for s in scenes:
        item = {
            'id': str(s.id),
            'status': s.status,
            'progress': s.render_progress if s.status == 'generating' else (100 if s.status == 'done' else 0),
            'error': (s.error_message or '')[:100],
            'duration': s.render_duration_sec,
            'cost': float(s.render_cost or 0),
            'videos': [],
        }
        for sv in s.rendered_videos.all():
            vid = {
                'id': str(sv.id),
                'status': sv.status,
                'selected': sv.is_selected,
            }
            if sv.video_file:
                vid['url'] = sv.video_file.url
            if sv.render_duration_sec:
                vid['duration'] = sv.render_duration_sec
            if sv.render_cost:
                vid['cost'] = float(sv.render_cost)
            item['videos'].append(vid)
        data.append(item)
    return JsonResponse({'scenes': data})
