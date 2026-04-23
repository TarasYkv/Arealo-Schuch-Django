"""
Video rendering pipeline using JarvisLabs GPU + ComfyUI.
RunPod fallback added 2026-04-02.
Updated 2026-04-07: SceneVideo, auto-shutdown, cost tracking.
"""
import os, json, time, logging, requests, subprocess, base64
from celery import shared_task
from django.conf import settings
from dotenv import load_dotenv
load_dotenv()
from django.utils import timezone

logger = logging.getLogger(__name__)

JARVIS_API_KEY = os.environ.get("JARVIS_API_KEY", "")
JARVIS_GPU_TYPES = ["A100-80GB", "RTX6000Ada", "A6000"]
JARVIS_GPU_TYPE = JARVIS_GPU_TYPES[0]  # primary
JARVIS_MACHINE_ID = os.environ.get("JARVIS_MACHINE_ID", "")
COST_PER_HOUR = 1.49  # India A100-80GB

# RunPod config
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")
RUNPOD_POD_ID = os.environ.get("RUNPOD_POD_ID", "")
RUNPOD_GPU_TYPES = ["NVIDIA A100 80GB SXM", "NVIDIA RTX 6000 Ada", "NVIDIA RTX A6000"]
RUNPOD_COST_PER_HOUR = 0.44
MAX_GPU_RUNTIME_HOURS = 6  # Notfall-Max: GPU wird nach 3h zwangsweise gestoppt  # RTX A6000

# Cached instance info
_cached_url = ""
_cached_machine_id = ""
_active_provider = ""  # "jarvis" or "runpod"


# ============================================================
# RunPod helper functions
# ============================================================

def _runpod_init():
    import runpod
    runpod.api_key = RUNPOD_API_KEY


def _get_runpod_instance():
    """Get RunPod pod status. Returns pod dict or None."""
    _runpod_init()
    import runpod
    try:
        pod = runpod.get_pod(RUNPOD_POD_ID)
        return pod
    except Exception as e:
        logger.warning(f"RunPod get_pod failed: {e}")
        return None


def _get_runpod_comfyui_url():
    """Get ComfyUI URL from running RunPod pod via proxy."""
    pod = _get_runpod_instance()
    if not pod or pod.get("desiredStatus") != "RUNNING":
        return ""
    runtime = pod.get("runtime")
    if not runtime:
        return ""
    # Use RunPod proxy URL format
    return f"https://{RUNPOD_POD_ID}-8188.proxy.runpod.net"


def _ensure_runpod_running():
    """Start/resume RunPod pod. Returns ComfyUI URL or empty string."""
    global _active_provider
    _runpod_init()
    import runpod

    pod = _get_runpod_instance()
    if not pod:
        logger.warning("RunPod: pod not found")
        return ""

    status = pod.get("desiredStatus", "")
    logger.info(f"RunPod pod status: {status}")

    if status == "RUNNING":
        url = _get_runpod_comfyui_url()
        if url and _wait_for_comfyui(url, timeout=10):
            _active_provider = "runpod"
            return url

    if status in ("EXITED", "STOPPED"):
        # Resume on-demand pod
        try:
            from runpod.api.graphql import run_graphql_query
            # On-demand pod — use podResume (not podBidResume)
            query = f'''mutation {{ podResume(input: {{ podId: "{RUNPOD_POD_ID}", gpuCount: 1 }}) {{ id desiredStatus }} }}'''
            logger.info(f"Resuming RunPod pod {RUNPOD_POD_ID}")
            result = run_graphql_query(query)
            logger.info(f"RunPod resume result: {result}")
        except Exception as e:
            logger.error(f"RunPod resume failed: {e}")
            return ""

        # Wait for running + ComfyUI ready (5 min timeout)
        for i in range(60):
            time.sleep(5)
            url = _get_runpod_comfyui_url()
            if url and _wait_for_comfyui(url, timeout=5):
                _active_provider = "runpod"
                logger.info(f"RunPod ComfyUI ready at {url}")
                _update_gpu_activity()
                return url

    logger.warning("RunPod: could not get ComfyUI URL")
    return ""


def _stop_runpod():
    """Stop RunPod pod. Returns True on success."""
    _runpod_init()
    import runpod
    try:
        runpod.stop_pod(RUNPOD_POD_ID)
        logger.info(f"RunPod pod {RUNPOD_POD_ID} stopped")
        return True
    except Exception as e:
        logger.warning(f"RunPod stop failed: {e}")
        return False


# ============================================================
# JarvisLabs helper functions
# ============================================================

def _get_jarvis_client():
    from jarvislabs import Client
    return Client(api_key=JARVIS_API_KEY)


def _get_running_instance():
    """Get running JarvisLabs ComfyUI instance or None."""
    client = _get_jarvis_client()
    for inst in client.instances.list():
        if inst.status == "Running" and "comfyui" in str(getattr(inst, 'template', '')).lower():
            return inst
    # Also check by machine_id
    if JARVIS_MACHINE_ID:
        try:
            inst = client.instances.get(JARVIS_MACHINE_ID)
            if inst.status == "Running":
                return inst
        except Exception:
            pass
    return None


def _get_comfyui_url():
    """Get ComfyUI API URL from running instance (JarvisLabs or RunPod)."""
    global _cached_url, _cached_machine_id, _active_provider

    # Check cached URL first
    if _cached_url:
        try:
            r = requests.get(f"{_cached_url}/system_stats", timeout=5)
            if r.status_code == 200:
                return _cached_url
        except Exception:
            _cached_url = ""

    # Try JarvisLabs
    inst = _get_running_instance()
    if inst:
        _cached_url = inst.endpoints[0] if inst.endpoints else ""
        _cached_machine_id = str(inst.machine_id)
        _active_provider = "jarvis"
        return _cached_url

    # Try RunPod
    url = _get_runpod_comfyui_url()
    if url:
        try:
            r = requests.get(f"{url}/system_stats", timeout=5)
            if r.status_code == 200:
                _cached_url = url
                _active_provider = "runpod"
                return url
        except Exception:
            pass

    return ""


def _get_jupyter_info():
    """Get JupyterLab URL and token from running instance."""
    inst = _get_running_instance()
    if not inst:
        return None, None
    jupyter_url = getattr(inst, 'url', '')
    if "token=" in jupyter_url:
        base = jupyter_url.split("/lab?")[0]
        token = jupyter_url.split("token=")[1].split("&")[0]
        return base, token
    return None, None


def _ensure_instance_running(scene=None, provider=None):
    """Start or resume GPU instance. Returns ComfyUI URL."""
    global _active_provider, _cached_url
    
    if provider != "runpod":
        # Try JarvisLabs - scan ALL instances (ID changes on resume)
        try:
            client = _get_jarvis_client()
            instances = list(client.instances.list())
            
            # Check for running instance
            for inst in instances:
                if inst.status == "Running" and inst.endpoints:
                    url = inst.endpoints[0]
                    logger.info(f"Found running JarvisLabs instance {inst.machine_id}, waiting for ComfyUI at {url}")
                    if _wait_for_comfyui(url, timeout=120):
                        _active_provider = "jarvis"
                        _cached_url = url
                        return url
            
            # Try to resume paused instance
            for inst in instances:
                if inst.status == "Paused":
                    for gpu in JARVIS_GPU_TYPES:
                        try:
                            logger.info(f"Resuming JarvisLabs {inst.machine_id} with {gpu}")
                            result = client.instances.resume(inst.machine_id, gpu_type=gpu)
                            logger.info(f"Resumed: new ID={result.machine_id}")
                            # Wait for ComfyUI
                            url = result.endpoints[0] if result.endpoints else ""
                            if url:
                                for i in range(60):
                                    time.sleep(5)
                                    if _wait_for_comfyui(url, timeout=10):
                                        _active_provider = "jarvis"
                                        _cached_url = url
                                        _update_gpu_activity()
                                        return url
                            break
                        except Exception as e:
                            logger.warning(f"JarvisLabs resume with {gpu} failed: {e}")
                            continue
                    break
        except Exception as e:
            logger.warning(f"JarvisLabs error: {e}")
    
    if provider != "jarvis":
        # Try RunPod fallback
        logger.info("JarvisLabs unavailable, trying RunPod as fallback...")
        url = _ensure_runpod_running()
        if url:
            return url
    
    logger.warning("No GPU provider available (JarvisLabs and RunPod both failed)")
    return ""


def _wait_for_comfyui(url, timeout=300):
    """Wait until ComfyUI is responding."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/system_stats", timeout=10)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False



def _upload_image_to_comfyui(url, local_path):
    """Upload an image to ComfyUI and return the filename for LoadImage node."""
    import os
    if not os.path.exists(local_path):
        logger.warning(f"Image not found: {local_path}")
        return None
    filename = os.path.basename(local_path)
    with open(local_path, "rb") as f:
        r = requests.post(
            f"{url}/upload/image",
            files={"image": (filename, f, "image/png")},
            timeout=60
        )
    if r.status_code == 200:
        data = r.json()
        logger.info(f"Uploaded {filename} to ComfyUI: {data}")
        return data.get("name", filename)
    logger.error(f"Upload failed: {r.status_code} {r.text[:200]}")
    return None

def _submit_workflow(url, workflow):
    """Submit workflow to ComfyUI."""
    r = requests.post(f"{url}/prompt",
        data=json.dumps({"prompt": workflow}),
        headers={"Content-Type": "application/json"},
        timeout=30)
    result = r.json()
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise Exception(f"ComfyUI rejected: {result}")
    return prompt_id


def _poll_status(url, prompt_id, timeout=900, scene_id=None):
    """Poll ComfyUI history for completion. Updates progress in DB.
    Dynamically extends timeout while job is still queued in ComfyUI."""
    from .models import Scene
    start = time.time()
    render_start = None  # tracks when the job actually starts rendering
    # Estimated render times per model (seconds)
    est_times = {'wan-2.2': 600, 'wan-2.1': 400, 'hunyuanvideo': 1800, 'ltx-2-distilled': 60, 'ltx-2': 120, 'cogvideox': 200, 'wan-2.2-5b': 300, 'wan-2.2-14b-rp': 600, 'ltx-video': 60, 'ltx-video-rp': 60, 'hunyuanvideo-rp': 1800}

    scene = None
    est_total = 180  # default estimate
    if scene_id:
        try:
            scene = Scene.objects.get(id=scene_id)
            est_total = est_times.get(scene.model_choice, 180)
        except Exception:
            pass

    while True:
        elapsed = time.time() - start

        # Check if job is still in the ComfyUI queue
        in_queue = False
        try:
            qr = requests.get(f"{url}/queue", timeout=10)
            qdata = qr.json()
            pending = qdata.get("queue_pending", [])
            running = qdata.get("queue_running", [])
            # Check if our prompt_id is in pending queue
            for item in pending:
                if len(item) >= 2 and item[1] == prompt_id:
                    in_queue = True
                    break
            # Check if it is currently running
            is_running = False
            for item in running:
                if len(item) >= 2 and item[1] == prompt_id:
                    is_running = True
                    break
            if is_running and render_start is None:
                render_start = time.time()
                logger.info(f"Job {prompt_id} started rendering after {elapsed:.0f}s in queue")
        except Exception:
            pass

        # Timeout logic: only timeout based on actual render time, not queue wait
        if render_start:
            render_elapsed = time.time() - render_start
            if render_elapsed > timeout:
                return {"status": "timeout"}
        elif not in_queue and elapsed > timeout:
            # Not in queue and not in history yet — something is wrong
            return {"status": "timeout"}
        elif in_queue and elapsed > 7200:
            # Safety: max 2 hour queue wait
            return {"status": "timeout", "message": "Queue wait exceeded 2 hours"}

        try:
            r = requests.get(f"{url}/history/{prompt_id}", timeout=10)
            hist = r.json()
            if prompt_id in hist:
                status = hist[prompt_id].get("status", {})
                if status.get("completed", False):
                    if scene:
                        scene.render_progress = 100
                        scene.save(update_fields=["render_progress"])
                    return {"status": "done", "outputs": hist[prompt_id].get("outputs", {})}
                if status.get("status_str") == "error":
                    msgs = hist[prompt_id].get("messages", [])
                    return {"status": "error", "message": str(msgs)[:500]}
        except Exception:
            pass

        # Update progress estimate
        if scene:
            if in_queue:
                scene.render_progress = 0
                scene.error_message = "In Warteschlange..."
                scene.save(update_fields=["render_progress", "error_message"])
            else:
                actual_elapsed = (time.time() - render_start) if render_start else elapsed
                progress = min(95, int((actual_elapsed / est_total) * 100))
                scene.render_progress = progress
                if scene.error_message == "In Warteschlange...":
                    scene.error_message = ""
                scene.save(update_fields=["render_progress", "error_message"])

        time.sleep(5)
    return {"status": "timeout"}


def _download_video(url, outputs, scene_id):
    """Download MP4 from ComfyUI output (VHS_VideoCombine saves MP4 directly)."""
    media_dir = os.path.join(settings.MEDIA_ROOT, "video", "renders")
    os.makedirs(media_dir, exist_ok=True)

    # VHS_VideoCombine outputs gifs (contains mp4 path), videos, or images
    for node_id, node_out in outputs.items():
        # Handle 'gifs' output (VHS_VideoCombine stores mp4 here)
        for gif in node_out.get("gifs", []):
            params = {"filename": gif["filename"], "type": gif.get("type", "output")}
            if gif.get("subfolder"):
                params["subfolder"] = gif["subfolder"]
            r = requests.get(f"{url}/view", params=params, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                output_path = os.path.join(media_dir, f"scene_{scene_id}_{int(time.time())}.mp4")
                with open(output_path, "wb") as f:
                    f.write(r.content)
                logger.info(f"Downloaded video (gif): {output_path} ({len(r.content)} bytes)")
                return output_path

        for vid in node_out.get("videos", []):
            params = {"filename": vid["filename"], "type": vid.get("type", "output")}
            if vid.get("subfolder"):
                params["subfolder"] = vid["subfolder"]

            r = requests.get(f"{url}/view", params=params, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                output_path = os.path.join(media_dir, f"scene_{scene_id}_{int(time.time())}.mp4")
                with open(output_path, "wb") as f:
                    f.write(r.content)
                logger.info(f"Downloaded video: {output_path} ({len(r.content)} bytes)")
                return output_path

    # Fallback: check for images (old SaveImage approach)
    tmp_dir = os.path.join(settings.MEDIA_ROOT, "video", "tmp", f"frames_{scene_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    images = []
    for node_id, node_out in outputs.items():
        for img in node_out.get("images", []):
            images.append(img)

    if not images:
        return None

    for i, img in enumerate(images):
        params = {"filename": img["filename"], "type": img.get("type", "output")}
        if img.get("subfolder"):
            params["subfolder"] = img["subfolder"]
        r = requests.get(f"{url}/view", params=params, timeout=60)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(os.path.join(tmp_dir, f"frame_{i:05d}.png"), "wb") as f:
                f.write(r.content)

    output_path = os.path.join(media_dir, f"scene_{scene_id}_{int(time.time())}.mp4")
    cmd = ["ffmpeg", "-y", "-framerate", "16",
           "-i", os.path.join(tmp_dir, "frame_%05d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-crf", "18", "-preset", "medium", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    if result.returncode == 0 and os.path.exists(output_path):
        return output_path
    return None


def _update_gpu_activity():
    """Update last activity timestamp on GPUServerState."""
    from .models import GPUServerState
    state = GPUServerState.get()
    state.last_activity = timezone.now()
    state.save(update_fields=["last_activity"])


# ============================================================
# Celery Tasks
# ============================================================

@shared_task
def render_scene_task(scene_id, preview=False, resolution=''):
    """Main rendering task — creates SceneVideo entry.

    preview=True: Quick preview at 240p, 10 steps, 3 sec duration.
    resolution='480p': Upscale to 832x480 (standard).
    resolution='720p': Upscale to 1280x720.
    """
    from .models import Scene, SceneVideo

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        logger.error(f"Scene {scene_id} not found")
        return

    # Create SceneVideo entry
    sv = SceneVideo.objects.create(
        scene=scene,
        model_used=scene.model_choice,
        status='rendering'
    )

    scene.status = "generating"
    scene.render_progress = 0
    scene.error_message = ""
    scene.save(update_fields=["status", "render_progress", "error_message"])
    _update_gpu_activity()


    try:
        # 1. Start/resume GPU
        url = _ensure_instance_running(scene)
        if not url:
            # Auto-retry: schedule retry in 2 minutes
            from video.models import Scene as _S
            _scene = _S.objects.get(id=scene_id)
            _scene.status = "generating"
            _scene.error_message = "⏳ GPU-Server nicht erreichbar. Automatischer Retry in 2 Min..."
            _scene.save(update_fields=["status", "error_message"])
            logger.info(f"GPU unavailable for {scene_id}, scheduling retry in 120s")
            render_scene_task.apply_async(args=[scene_id], countdown=120)
            return

        # 2. Wait for ComfyUI
        if not _wait_for_comfyui(url):
            raise Exception("ComfyUI not responding after timeout")

        # 3. Build workflow
        from .comfyui_workflows.builder import build_workflow

        # Get start/end frame paths if available
        start_img = None
        end_img = None
        if scene.start_frame and scene.start_frame.image:
            local_path = scene.start_frame.image.path
            start_img = _upload_image_to_comfyui(url, local_path)
        if scene.end_frame and scene.end_frame.image:
            local_path = scene.end_frame.image.path
            end_img = _upload_image_to_comfyui(url, local_path)

        import random
        # Determine render parameters based on preview/resolution/scene-quality
        is_hunyuan = (scene.model_choice or '').lower().startswith('hunyuan')
        scene_hunyuan_res = getattr(scene, 'hunyuan_resolution', '480p')
        scene_hunyuan_steps = getattr(scene, 'hunyuan_steps', None)
        scene_hunyuan_cfg = getattr(scene, 'hunyuan_cfg', None)
        scene_hunyuan_flow = getattr(scene, 'hunyuan_flow_shift', None)

        if preview:
            r_width, r_height, r_duration, r_steps = 416, 240, 3, 10
        elif resolution == '720p':
            r_width, r_height, r_duration, r_steps = 1280, 720, scene.duration, scene_hunyuan_steps if is_hunyuan else None
        elif resolution == '480p':
            r_width, r_height, r_duration, r_steps = 832, 480, scene.duration, scene_hunyuan_steps if is_hunyuan else None
        else:
            if is_hunyuan and scene_hunyuan_res == '720p':
                r_width, r_height, r_duration, r_steps = 1280, 720, scene.duration, scene_hunyuan_steps
            else:
                r_width, r_height, r_duration, r_steps = 832, 480, scene.duration, (scene_hunyuan_steps if is_hunyuan else None)

        workflow = build_workflow(
            model_choice=scene.model_choice,
            prompt=scene.prompt.replace("#test", "").strip(),
            negative_prompt=getattr(scene, 'negative_prompt', ''),
            width=r_width, height=r_height,
            duration=r_duration,
            fps=scene.fps if hasattr(scene, 'fps') else 16,
            seed=random.randint(0, 2**32),
            start_image=start_img,
            end_image=end_img,
            steps=r_steps,
            cfg=scene_hunyuan_cfg if is_hunyuan else None,
            flow_shift=scene_hunyuan_flow if is_hunyuan else None,
        )

        # 4. Submit
        render_start = time.time()  # Start timing from actual submit, not from task start
        logger.info(f"Submitting workflow for scene {scene_id} ({scene.model_choice}) via {_active_provider}")
        prompt_id = _submit_workflow(url, workflow)
        logger.info(f"Prompt ID: {prompt_id}")

        # 5. Poll
        # Dynamic timeout based on model + quality
        is_hunyuan = (scene.model_choice or '').lower().startswith('hunyuan')
        scene_steps = getattr(scene, 'hunyuan_steps', 25) or 25
        if is_hunyuan:
            # Hunyuan: be generous — 480p 20 steps on A40 takes ~12-15 min nominally,
            # but under queue contention or Redux+PuLID chain it can hit 30+. Budget 90s/step + 15min buffer.
            poll_timeout = max(2400, scene_steps * 90 + 900)  # min 40 min
        else:
            poll_timeout = 1200
        result = _poll_status(url, prompt_id, timeout=poll_timeout, scene_id=str(scene.id))
        if result["status"] != "done":
            raise Exception(f"Rendering failed: {result}")

        # 6. Download video
        output_path = _download_video(url, result.get("outputs", {}), str(scene_id))

        if not output_path or not os.path.exists(output_path):
            raise Exception("No output video generated")

        # 7. Update SceneVideo
        render_duration = time.time() - render_start
        cost_rate = RUNPOD_COST_PER_HOUR if _active_provider == "runpod" else COST_PER_HOUR
        render_cost = round((render_duration / 3600) * cost_rate, 4)

        rel_path = os.path.relpath(output_path, settings.MEDIA_ROOT)
        sv.video_file = rel_path
        sv.render_duration_sec = round(render_duration, 1)
        sv.render_cost = render_cost
        sv.status = 'done'
        sv.save()

        # Auto-select if first video or scene has no selected video
        if not scene.rendered_videos.filter(is_selected=True).exists():
            sv.is_selected = True
            sv.save(update_fields=["is_selected"])

        # Update scene
        scene.status = "done"
        scene.render_progress = 100
        scene.render_duration_sec = render_duration
        scene.render_cost = render_cost
        scene.save(update_fields=["status", "render_progress", "render_duration_sec", "render_cost"])

        logger.info(f"Scene {scene_id} done via {_active_provider}: {rel_path} ({render_duration:.0f}s, ${render_cost})")

    except Exception as e:
        logger.error(f"Render error for {scene_id}: {e}")
        sv.status = 'error'
        sv.error_message = str(e)[:500]
        sv.save()
        scene.status = "error"
        scene.error_message = str(e)[:500]
        scene.save(update_fields=["status", "error_message"])

    # Schedule auto-shutdown check
    _update_gpu_activity()
    check_auto_shutdown.apply_async(countdown=35)


@shared_task
def start_gpu_server(provider=None):
    """Start/resume GPU server. provider='jarvis' or 'runpod' or None (auto: JarvisLabs first, RunPod fallback)."""
    from .models import GPUServerState
    global _cached_url, _active_provider

    url = _get_comfyui_url()
    if url:
        _update_gpu_activity()
        return {"status": "already_running", "url": url, "provider": _active_provider or "unknown"}

    def _try_jarvis():
        global _cached_url, _active_provider, JARVIS_MACHINE_ID
        try:
            client = _get_jarvis_client()
            instances = list(client.instances.list())

            for inst in instances:
                if inst.status == "Running" and inst.endpoints:
                    _cached_url = inst.endpoints[0]
                    JARVIS_MACHINE_ID = str(inst.machine_id)
                    _active_provider = "jarvis"
                    state = GPUServerState.get()
                    state.is_manually_started = True
                    state.save()
                    _update_gpu_activity()
                    return {"status": "running", "machine_id": str(inst.machine_id), "url": _cached_url, "provider": "jarvis"}

            for inst in instances:
                if inst.status == "Paused":
                    for gpu in JARVIS_GPU_TYPES:
                        try:
                            logger.info(f"Resuming JarvisLabs instance {inst.machine_id} with {gpu}")
                            client.instances.resume(str(inst.machine_id), gpu_type=gpu)
                            _cached_url = ""
                            JARVIS_MACHINE_ID = str(inst.machine_id)
                            _active_provider = "jarvis"
                            state = GPUServerState.get()
                            state.is_manually_started = True
                            state.save()
                            _update_gpu_activity()
                            return {"status": "resuming", "machine_id": str(inst.machine_id), "gpu": gpu, "provider": "jarvis"}
                        except Exception as e:
                            logger.warning(f"JarvisLabs resume with {gpu} failed: {e}")
                            continue
        except Exception as e:
            logger.warning(f"JarvisLabs unavailable in start_gpu_server: {e}")
        return None

    def _try_runpod():
        global _cached_url, _active_provider
        logger.info("Starting RunPod...")
        url = _ensure_runpod_running()
        if url:
            _cached_url = url
            _active_provider = "runpod"
            state = GPUServerState.get()
            state.is_manually_started = True
            state.save()
            _update_gpu_activity()
            return {"status": "running", "url": url, "provider": "runpod", "pod_id": RUNPOD_POD_ID}
        return None

    if provider == "jarvis":
        result = _try_jarvis()
        if result:
            return result
    elif provider == "runpod":
        result = _try_runpod()
        if result:
            return result
    else:
        # Auto: try JarvisLabs first, then RunPod
        result = _try_jarvis()
        if result:
            return result
        logger.info("JarvisLabs unavailable, trying RunPod as fallback...")
        result = _try_runpod()
        if result:
            return result

    return {"status": "no_instance_available"}


@shared_task
def stop_gpu_server():
    """Stop GPU server (JarvisLabs pause or RunPod stop)."""
    global _cached_url, _cached_machine_id, _active_provider

    # --- Try JarvisLabs first ---
    try:
        client = _get_jarvis_client()

        if JARVIS_MACHINE_ID:
            try:
                inst = client.instances.get(JARVIS_MACHINE_ID)
                if inst.status == "Running":
                    client.instances.pause(JARVIS_MACHINE_ID)
                    _cached_url = ""
                    _active_provider = ""
                    return {"status": "paused", "machine_id": str(inst.machine_id), "provider": "jarvis"}
            except Exception:
                pass

        # Fallback: find any running JarvisLabs instance
        for inst in client.instances.list():
            if inst.status == "Running":
                client.instances.pause(str(inst.machine_id))
                _cached_url = ""
                _active_provider = ""
                return {"status": "paused", "machine_id": str(inst.machine_id), "provider": "jarvis"}
    except Exception as e:
        logger.warning(f"JarvisLabs stop check failed: {e}")

    # --- Try RunPod ---
    pod = _get_runpod_instance()
    if pod and pod.get("desiredStatus") == "RUNNING":
        if _stop_runpod():
            _cached_url = ""
            _active_provider = ""
            return {"status": "stopped", "pod_id": RUNPOD_POD_ID, "provider": "runpod"}

    return {"status": "no_running_instance"}


@shared_task
def hard_cap_gpu_shutdown():
    """Notfall-Shutdown nach MAX_GPU_RUNTIME_HOURS, egal was gerade läuft."""
    try:
        status = get_server_status()
    except Exception as e:
        logger.warning(f"hard_cap_gpu_shutdown: status check failed: {e}")
        return {"status": "status_check_failed", "error": str(e)}

    if status.get("status") != "running":
        return {"status": "not_running"}

    uptime_min = status.get("uptime_min", 0) or 0
    max_min = MAX_GPU_RUNTIME_HOURS * 60
    if uptime_min < max_min:
        return {"status": "within_limit", "uptime_min": uptime_min, "max_min": max_min}

    logger.warning(f"HARD CAP: GPU-Server läuft seit {uptime_min} Min, erzwinge Shutdown")
    from .models import Scene
    active = Scene.objects.filter(status="generating")
    for s in active:
        s.status = "error"
        s.error_message = f"Szene abgebrochen wegen 3h-Notfall-Shutdown (Laufzeit {uptime_min}min)"
        s.save(update_fields=["status", "error_message"])

    result = stop_gpu_server()
    try:
        from .models import GPUServerState
        state = GPUServerState.get()
        state.is_manually_started = False
        state.save()
    except Exception:
        pass
    return {"status": "force_stopped", "uptime_min": uptime_min, "result": result}


@shared_task
def check_auto_shutdown():
    """Auto-pause GPU if idle. HARD CAP: force shutdown after MAX_GPU_RUNTIME_HOURS."""
    from .models import Scene, GPUServerState
    from datetime import timedelta

    # Hard cap override (stoppt auch bei aktiven Szenen)
    try:
        st = get_server_status()
        if st.get("status") == "running":
            uptime_min = st.get("uptime_min", 0) or 0
            max_min = MAX_GPU_RUNTIME_HOURS * 60
            if uptime_min >= max_min:
                logger.warning(f"check_auto_shutdown: HARD CAP hit ({uptime_min}>={max_min}min)")
                return hard_cap_gpu_shutdown()
    except Exception as e:
        logger.debug(f"hard-cap check failed: {e}")

    active = Scene.objects.filter(status="generating").count()
    if active > 0:
        logger.info(f"Auto-shutdown skipped: {active} active scenes")
        return {"status": "active", "count": active}

    state = GPUServerState.get()
    now = timezone.now()
    idle_minutes = (now - state.last_activity).total_seconds() / 60
    shutdown_threshold = getattr(state, 'auto_shutdown_minutes', 10) or 10

    if idle_minutes < shutdown_threshold:
        check_auto_shutdown.apply_async(countdown=60)
        return {"status": "grace_period", "idle_min": round(idle_minutes, 1)}

    logger.info(f"Auto-shutdown: idle={idle_minutes:.1f}min")
    result = stop_gpu_server()
    state.is_manually_started = False
    state.save()
    return result

    active = Scene.objects.filter(status="generating").count()
    if active > 0:
        logger.info(f"Auto-shutdown skipped: {active} active scenes")
        return {"status": "active", "count": active}

    state = GPUServerState.get()
    now = timezone.now()
    idle_minutes = (now - state.last_activity).total_seconds() / 60

    if idle_minutes < 5:
        check_auto_shutdown.apply_async(countdown=60)
        return {"status": "grace_period", "idle_min": round(idle_minutes, 1)}

    if state.is_manually_started:
        if idle_minutes < 5:
            check_auto_shutdown.apply_async(countdown=60)
            return {"status": "waiting", "idle_min": round(idle_minutes, 1)}

    logger.info(f"Auto-shutdown: idle={idle_minutes:.1f}min, manual={state.is_manually_started}")
    result = stop_gpu_server()
    state.is_manually_started = False
    state.save()
    return result

# Legacy wrappers
def start_render(scene):
    render_scene_task.delay(str(scene.id))

def get_server_status():
    """Get GPU server status — checks JarvisLabs then RunPod."""
    # Check JarvisLabs - scan ALL instances (machine_id changes on resume)
    try:
        client = _get_jarvis_client()
        for inst in client.instances.list():
            if inst.status == "Running":
                runtime_str = getattr(inst, 'runtime', '0') or '0'
                uptime_min = 0
                if isinstance(runtime_str, str):
                    parts = runtime_str.split()
                    for i, p in enumerate(parts):
                        if p == 'hours' and i > 0: uptime_min += int(parts[i-1]) * 60
                        if p == 'minutes' and i > 0: uptime_min += int(parts[i-1])
                session_cost = round((uptime_min / 60) * COST_PER_HOUR, 2)
                return {
                    "status": "running",
                    "gpu": getattr(inst, 'gpu_type', 'A100-80GB'),
                    "cost_per_hr": COST_PER_HOUR,
                    "machine_id": str(inst.machine_id),
                    "provider": "jarvis",
                    "uptime_min": uptime_min,
                    "session_cost": session_cost,
                }
            elif inst.status == "Paused":
                return {"status": "paused", "machine_id": str(inst.machine_id), "provider": "jarvis"}
    except Exception as e:
        logger.debug(f"JarvisLabs status check failed: {e}")

    # Check RunPod
    try:
        pod = _get_runpod_instance()
        if pod:
            pod_status = pod.get("desiredStatus", "")
            if pod_status == "RUNNING":
                gpu_name = pod.get("machine", {}).get("gpuDisplayName", "A100 SXM")
                # Get uptime via GraphQL (SDK missing uptimeInSeconds)
                uptime_sec = 0
                try:
                    upt_r = requests.post(
                        "https://api.runpod.io/graphql?api_key=" + RUNPOD_API_KEY,
                        json={"query": "{ pod(input: {podId: \"" + RUNPOD_POD_ID + "\"}) { runtime { uptimeInSeconds } } }"},
                        timeout=5)
                    uptime_sec = upt_r.json().get("data", {}).get("pod", {}).get("runtime", {}).get("uptimeInSeconds", 0) or 0
                except Exception:
                    pass
                uptime_min = int(uptime_sec / 60)
                session_cost = round((uptime_min / 60) * RUNPOD_COST_PER_HOUR, 2)
                balance = None
                try:
                    br = requests.post(
                        "https://api.runpod.io/graphql?api_key=" + RUNPOD_API_KEY,
                        json={"query": "{ myself { clientBalance currentSpendPerHr } }"},
                        timeout=5)
                    bd = br.json().get("data", {}).get("myself", {})
                    balance = round(bd.get("clientBalance", 0), 2)
                except Exception:
                    pass
                result = {
                    "status": "running", "gpu": gpu_name,
                    "cost_per_hr": RUNPOD_COST_PER_HOUR,
                    "pod_id": RUNPOD_POD_ID, "provider": "runpod",
                    "uptime_min": uptime_min, "session_cost": session_cost,
                }
                if balance is not None:
                    result["balance"] = balance
                return result
            elif pod_status in ("EXITED", "STOPPED"):
                return {"status": "stopped", "pod_id": RUNPOD_POD_ID, "provider": "runpod"}
    except Exception as e:
        logger.debug(f"RunPod status check failed: {e}")

    return {"status": "stopped"}


@shared_task
def auto_shutdown_gpu():
    """Alias for check_auto_shutdown — registered for Celery Beat compatibility."""
    return check_auto_shutdown()


@shared_task
def cleanup_stuck_scenes():
    """Mark stuck scenes as error — only if no active Celery task."""
    from .models import Scene, SceneVideo
    from datetime import timedelta
    from celery.result import AsyncResult
    cutoff = timezone.now() - timedelta(minutes=180)
    stuck_count = 0
    for s in Scene.objects.filter(status='generating'):
        # Skip if scene has an active Celery task
        if s.celery_task_id:
            try:
                result = AsyncResult(s.celery_task_id)
                if result.state in ('PENDING', 'STARTED', 'RETRY'):
                    continue  # Task is still running or queued
            except Exception:
                pass
        # Check if there's a recent SceneVideo being rendered (within 60 min)
        active_render = s.rendered_videos.filter(
            status='rendering',
            created_at__gt=cutoff
        ).exists()
        if active_render:
            continue  # Still rendering, not stuck
        # Check if any SceneVideo started more than 60min ago
        old_render = s.rendered_videos.filter(
            status='rendering',
            created_at__lt=cutoff
        ).exists()
        if old_render or not s.rendered_videos.filter(status='rendering').exists():
            s.status = 'error'
            s.error_message = 'Render timed out (3h)'
            s.save()
            stuck_count += 1
            logger.info(f'Cleaned up stuck scene {s.id}')
    return {'cleaned': stuck_count}



@shared_task(bind=True, max_retries=None)
def render_project_batched_task(self, project_id):
    """Phase-batched render for an entire project:

      Phase A:  For every scene (in order): frames → ComfyUI /free → Hunyuan render.
                Keeps the Hunyuan model hot in VRAM across scenes, no FLUX<->Hunyuan
                shuffle between scenes.
      Phase B:  Apply text overlays for every scene that has one (CPU ffmpeg).
      Phase C:  Generate voiceovers for every scene that has text (XTTS GPU).
                At the end, re-mux audio into each scene's video.

    This is much faster than per-scene pipelines because the GPU model cache
    only transitions FLUX→Hunyuan once, and XTTS only loads once."""
    from .models import VideoProject, Scene

    holder = f"batch:{project_id}:{self.request.id}"
    if not _acquire_gpu_lock(holder, ttl=14400):
        logger.info(f"Batched: GPU busy, requeue project {project_id} in 60s")
        raise self.retry(countdown=60, exc=Exception("GPU busy"))

    try:
        try:
            project = VideoProject.objects.get(id=project_id)
        except VideoProject.DoesNotExist:
            logger.error(f"Batched pipeline: project {project_id} not found")
            return

        scenes = list(project.scenes.all().order_by('order'))
        if not scenes:
            return

        # Mark all pending/error scenes as generating upfront
        for s in scenes:
            if s.status in ('pending', 'error', 'done'):
                # Skip 'done' scenes only if they already have a video; otherwise re-run
                if s.status == 'done' and s.rendered_videos.filter(status='done').exists():
                    continue
                s.status = 'generating'
                s.render_progress = 0
                s.error_message = 'In Warteschlange'
                s.save(update_fields=['status', 'render_progress', 'error_message'])

        # ---------- Phase A: all FLUX frames (FLUX stays hot in VRAM) ----------
        for s in scenes:
            s.refresh_from_db()
            if s.status == 'done' and s.rendered_videos.filter(status='done').exists():
                continue
            try:
                if s.start_frame_prompt and s.start_frame_prompt.strip() and not s.start_frame:
                    s.error_message = f'Phase 1/4: Frame {s.order}'
                    s.save(update_fields=['error_message'])
                    try:
                        _pipeline_generate_frame(s, 'start')
                    except Exception as e:
                        logger.warning(f"Batched: start-frame failed for {s.id}: {e}")
                    s.refresh_from_db()
                if s.end_frame_prompt and s.end_frame_prompt.strip() and not s.end_frame:
                    s.error_message = f'Phase 1/4: End-Frame {s.order}'
                    s.save(update_fields=['error_message'])
                    try:
                        _pipeline_generate_frame(s, 'end')
                    except Exception as e:
                        logger.warning(f"Batched: end-frame failed for {s.id}: {e}")
                    s.refresh_from_db()
            except Exception as e:
                logger.error(f"Batched Phase A frame {s.id}: {e}")

        # Unload FLUX from VRAM exactly ONCE before switching to Hunyuan
        try:
            url = _get_runpod_comfyui_url()
            if url:
                import requests as _req
                _req.post(f'{url}/free',
                          json={'unload_models': True, 'free_memory': True},
                          timeout=15)
                logger.info("Batched: ComfyUI /free after Phase A (FLUX→Hunyuan switch)")
        except Exception as _e:
            logger.warning(f"Batched: /free failed between A and B: {_e}")

        # ---------- Phase B: all Hunyuan video renders (Hunyuan stays hot) ----------
        for s in scenes:
            s.refresh_from_db()
            if s.status == 'done' and s.rendered_videos.filter(status='done').exists():
                continue
            try:
                s.error_message = f'Phase 2/4: Video {s.order}'
                s.save(update_fields=['error_message'])
                render_scene_task(str(s.id))
                s.refresh_from_db()
            except Exception as e:
                logger.error(f"Batched Phase B video {s.id}: {e}")
                s.status = 'error'
                s.error_message = f'Batch-Render: {str(e)[:400]}'
                s.save(update_fields=['status', 'error_message'])

        # ---------- Phase C: text overlays (CPU, ffmpeg) ----------
        for s in scenes:
            s.refresh_from_db()
            if s.status != 'done':
                continue
            if not (s.text_overlay and s.text_overlay.strip()):
                continue
            try:
                s.error_message = f'Phase 3/4: Overlay {s.order}'
                s.save(update_fields=['error_message'])
                apply_text_overlay_task(str(s.id))
                s.refresh_from_db()
            except Exception as e:
                logger.warning(f"Batched Phase C overlay {s.id}: {e}")

        # ---------- Phase D: voiceovers (XTTS/Piper) + music (MusicGen) ----------
        # Free ComfyUI VRAM for XTTS/MusicGen
        try:
            url = _get_runpod_comfyui_url()
            if url:
                import requests as _req
                _req.post(f'{url}/free',
                          json={'unload_models': True, 'free_memory': True},
                          timeout=15)
        except Exception:
            pass

        # D1: voiceovers
        for s in scenes:
            s.refresh_from_db()
            if s.status != 'done':
                continue
            if not (s.voiceover_text and s.voiceover_text.strip()):
                continue
            try:
                s.error_message = f'Phase 4/5: Voiceover {s.order}'
                s.save(update_fields=['error_message'])
                _pipeline_generate_voiceover(s)
                s.refresh_from_db()
            except Exception as e:
                logger.warning(f"Batched Phase D voiceover {s.id}: {e}")

        # ---------- Phase E: project-level music (one track for all scenes) ----------
        project.refresh_from_db()
        if (project.music_prompt and project.music_prompt.strip()) or project.music_genre:
            try:
                total_dur = sum(s.duration for s in scenes if s.status == 'done')
                if total_dur > 0:
                    for s in scenes:
                        if s.status == 'done':
                            s.error_message = 'Phase 5/5: Projekt-Musik'
                            s.save(update_fields=['error_message'])
                    _pipeline_generate_project_music(project, total_dur)
            except Exception as e:
                logger.warning(f"Batched Phase E project music: {e}")

        # Clear transient error messages on success
        for s in scenes:
            s.refresh_from_db()
            if s.status == 'done' and s.error_message and 'Fehler' not in s.error_message:
                s.error_message = ''
                s.save(update_fields=['error_message'])

        logger.info(f"Batched pipeline done for project {project_id}")
    except Exception as e:
        logger.error(f"Batched pipeline error: {e}")
    finally:
        _release_gpu_lock(holder)


def _acquire_gpu_lock(holder, ttl=5400):
    """Try to acquire a global GPU pipeline lock via Redis SETNX.
    Returns True if acquired. The lock has a TTL so a crashed task doesn't
    permanently block the queue. Callers MUST release via _release_gpu_lock."""
    try:
        import redis as _redis
        from django.conf import settings as _settings
        r = _redis.Redis.from_url(getattr(_settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        return bool(r.set('workloom:gpu_pipeline_lock', holder, nx=True, ex=ttl))
    except Exception as e:
        logger.warning(f"gpu_lock acquire failed: {e}")
        return True  # fail-open: don't block rendering if Redis is down


def _release_gpu_lock(holder):
    try:
        import redis as _redis
        from django.conf import settings as _settings
        r = _redis.Redis.from_url(getattr(_settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        current = r.get('workloom:gpu_pipeline_lock')
        if current and current.decode('utf-8', 'ignore') == holder:
            r.delete('workloom:gpu_pipeline_lock')
    except Exception as e:
        logger.warning(f"gpu_lock release failed: {e}")


@shared_task(bind=True, max_retries=None)
def render_scene_pipeline_task(self, scene_id):
    """Full pipeline for a SINGLE scene: generate frames -> render video -> voiceover.
    Serialized via Redis lock so parallel clicks do not all hit the GPU at once."""
    from .models import Scene
    import time

    # Acquire global GPU pipeline lock. If another task holds it, requeue in 30s.
    holder = f"scene:{scene_id}:{self.request.id}"
    if not _acquire_gpu_lock(holder):
        logger.info(f"Pipeline: GPU busy, requeue scene {scene_id} in 30s")
        raise self.retry(countdown=30, exc=Exception("GPU busy"))

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        logger.error(f"Pipeline: Scene {scene_id} not found")
        _release_gpu_lock(holder)
        return

    project = scene.project
    scene.status = "generating"
    scene.render_progress = 0
    scene.error_message = ""
    scene.save(update_fields=["status", "render_progress", "error_message"])

    try:
        # Step 1: Generate start frame if prompt given and no frame exists
        if scene.start_frame_prompt and scene.start_frame_prompt.strip() and not scene.start_frame:
            scene.error_message = "Generiere Start-Frame..."
            scene.save(update_fields=["error_message"])
            _pipeline_generate_frame(scene, "start")
            scene.refresh_from_db()
        
        # Step 2: Generate end frame if prompt given and no frame exists
        if scene.end_frame_prompt and scene.end_frame_prompt.strip() and not scene.end_frame:
            scene.error_message = "Generiere End-Frame..."
            scene.save(update_fields=["error_message"])
            try:
                _pipeline_generate_frame(scene, "end")
            except Exception as e:
                logger.warning(f"End-frame generation failed (non-critical): {e}")
            scene.refresh_from_db()
        
        # Between FLUX frame generation and Hunyuan video render, force ComfyUI
        # to unload cached models from VRAM. FLUX (~17 GB) + Hunyuan (~8 GB) +
        # encoders (~9 GB) don't coexist well on a single A40 — without explicit
        # free the next scene hit 2-3× slower renders due to VRAM shuffling.
        try:
            url = _get_runpod_comfyui_url()
            if url:
                import requests as _req
                _req.post(f'{url}/free', json={"unload_models": True, "free_memory": True}, timeout=15)
                logger.info(f"ComfyUI /free called before Hunyuan render for scene {scene_id}")
        except Exception as _e:
            logger.warning(f"ComfyUI /free failed (non-critical): {_e}")

        # Step 3: Render the video
        scene.error_message = "Rendere Video..."
        scene.save(update_fields=["error_message"])
        render_scene_task(scene_id)
        scene.refresh_from_db()
        
        if scene.status != "done":
            return  # Render failed, error already set
        
        # Step 4: Generate voiceover if text is set
        if scene.voiceover_text and scene.voiceover_text.strip():
            scene.error_message = "Generiere Voiceover..."
            scene.save(update_fields=["error_message"])
            try:
                _pipeline_generate_voiceover(scene)
                scene.refresh_from_db()
            except Exception as e:
                logger.warning(f"Voiceover generation failed (non-critical): {e}")

        # Step 5: Apply text overlay if set
        if scene.text_overlay and scene.text_overlay.strip():
            scene.error_message = "Brenne Text-Overlay ein..."
            scene.save(update_fields=["error_message"])
            try:
                apply_text_overlay_task(str(scene.id))
                scene.refresh_from_db()
            except Exception as e:
                logger.warning(f"Text overlay failed (non-critical): {e}")

        # Step 6: Generate music if prompt/genre set
        if (scene.music_prompt and scene.music_prompt.strip()) or scene.music_genre:
            scene.error_message = "Generiere Musik..."
            scene.save(update_fields=["error_message"])
            try:
                _pipeline_generate_music(scene)
                scene.refresh_from_db()
            except Exception as e:
                logger.warning(f"Music generation failed (non-critical): {e}")

        scene.error_message = ""
        scene.save(update_fields=["error_message"])
        
    except Exception as e:
        logger.error(f"Pipeline error for scene {scene_id}: {e}")
        scene.status = "error"
        scene.error_message = f"Pipeline: {str(e)[:500]}"
        scene.save(update_fields=["status", "error_message"])
    finally:
        _release_gpu_lock(holder)


FRAME_STYLE_DEFS = {
    'photorealistic': {
        'positive': 'photorealistic, ultra realistic photograph, 8k UHD, DSLR, cinematic lighting, realistic skin texture and pores, natural colors, sharp detail, shallow depth of field, RAW photo, film grain',
        'negative': 'anime, cartoon, drawing, illustration, 2d, painted, rendered, cel-shaded, sketch, comic, manga, unrealistic, artificial',
    },
    'cinematic': {
        'positive': 'cinematic film still, 35mm, anamorphic lens, movie lighting, shallow depth of field, color graded, 8k',
        'negative': 'anime, cartoon, illustration, 2d, flat, sketch, low quality, blurry',
    },
    'editorial': {
        'positive': 'editorial photography, magazine quality, professional lighting, sharp focus, high fashion, 8k',
        'negative': 'anime, cartoon, illustration, 2d, amateur, low quality',
    },
    'documentary': {
        'positive': 'documentary photography, natural light, authentic, candid, photojournalistic, realistic, 8k',
        'negative': 'anime, cartoon, illustration, 2d, staged, artificial, glamour',
    },
    'warm-portrait': {
        'positive': 'warm portrait photography, golden hour light, soft skin tones, intimate, natural, 8k, shallow depth of field',
        'negative': 'anime, cartoon, illustration, 2d, cold, harsh lighting, flat',
    },
    'anime': {
        'positive': 'anime style, high quality anime, detailed anime art, vibrant colors, clean lines',
        'negative': 'photorealistic, photograph, 3d render, low quality',
    },
    'illustration': {
        'positive': 'digital illustration, detailed artwork, professional illustration, vibrant, artistic',
        'negative': 'photorealistic, photograph, blurry, low quality',
    },
    'watercolor': {
        'positive': 'watercolor painting, soft washes, artistic, delicate brushstrokes, pastel tones',
        'negative': 'photorealistic, photograph, digital, sharp, 3d',
    },
    '3d-render': {
        'positive': '3D render, octane render, high detail, subsurface scattering, ray tracing, 8k',
        'negative': 'flat, 2d, sketch, low quality, blurry',
    },
    'none': {
        'positive': '',
        'negative': '',
    },
}


def _apply_frame_style(prompt, style):
    """Inject style-specific positive keywords into the frame prompt
    and return the enhanced prompt. Negative keywords are injected
    separately via the FLUX workflow's negative conditioning."""
    style_def = FRAME_STYLE_DEFS.get(style, FRAME_STYLE_DEFS['photorealistic'])
    pos = style_def['positive']
    if not pos:
        return prompt
    return f"{prompt.rstrip('. ,')}, {pos}"


def _get_frame_style_negative(style):
    """Return the negative prompt keywords for a frame style."""
    style_def = FRAME_STYLE_DEFS.get(style, FRAME_STYLE_DEFS['photorealistic'])
    return style_def['negative']


def _pipeline_generate_frame(scene, slot):
    """Generate a start or end frame for a scene using the configured frame model."""
    from .models import GeneratedFrame
    from django.core.files.base import ContentFile
    import pathlib
    
    prompt = scene.start_frame_prompt if slot == "start" else scene.end_frame_prompt
    if not prompt or not prompt.strip():
        return

    prompt = _apply_frame_style(prompt, getattr(scene, 'frame_style', 'photorealistic'))

    project = scene.project
    frame_model = scene.frame_model or "nano-banana"
    
    # Character gets ALL its images (main + extras) for multi-image PuLID
    character_path = []
    other_ref_paths = []
    first_char = project.characters.first()
    if first_char:
        character_path = first_char.all_image_paths()
    if hasattr(project, "product") and project.product:
        other_ref_paths.append(project.product.image.path)
    if hasattr(project, "still_image") and project.still_image:
        other_ref_paths.append(project.still_image.image.path)
    
    ref_image_paths = list(character_path) + other_ref_paths
    
    # Auto-fallback: FLUX+PuLID without any refs → Gemini
    if frame_model == "flux-pulid" and not character_path and not other_ref_paths:
        logger.info(f"No reference for FLUX, falling back to Gemini")
        frame_model = "nano-banana"
    
    frame = GeneratedFrame.objects.create(project=project, prompt=prompt, status="generating")
    
    try:
        if frame_model == "flux-pulid":
            _pipeline_flux_frame(frame, prompt, character_path, other_ref_paths)
        else:
            _pipeline_gemini_frame(frame, prompt, ref_image_paths, project.user, frame_model)
        
        # Attach to scene
        if slot == "start":
            scene.start_frame = frame
        else:
            scene.end_frame = frame
        scene.save(update_fields=[f"{slot}_frame"])
    except Exception as e:
        frame.status = "error"
        frame.error_message = str(e)[:500]
        frame.save()
        raise


GEMINI_MODELS = {
    "nano-banana": "gemini-3.1-flash-image-preview",
    "gemini-2.5": "gemini-2.5-flash-image-preview",
    "gemini-2.0": "gemini-2.0-flash-preview-image-generation",
}
IMAGEN_MODELS = {
    "imagen-4-fast": "imagen-4.0-fast-generate-preview-06-06",
    "imagen-4": "imagen-4.0-generate-preview-06-06",
    "imagen-4-ultra": "imagen-4.0-ultra-generate-preview-06-06",
}

def _pipeline_gemini_frame(frame, prompt, ref_image_paths, user, frame_model="nano-banana"):
    from google import genai
    from google.genai import types
    from django.core.files.base import ContentFile
    import pathlib
    
    api_key = user.gemini_api_key
    if not api_key:
        raise Exception("Gemini API Key nicht gesetzt")
    
    client = genai.Client(api_key=api_key)
    
    if frame_model in IMAGEN_MODELS:
        response = client.models.generate_images(
            model=IMAGEN_MODELS[frame_model],
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1),
        )
        if response.generated_images:
            img_bytes = response.generated_images[0].image.image_bytes
            filename = "frame_{}.png".format(frame.id)
            frame.image.save(filename, ContentFile(img_bytes), save=True)
            frame.status = "done"
            frame.save()
            return
        raise Exception("Kein Bild in Imagen-Antwort")
    
    gemini_model = GEMINI_MODELS.get(frame_model, "gemini-3.1-flash-image-preview")
    contents = []
    if ref_image_paths:
        contents.append("Erstelle ein Bild basierend auf diesen Referenzbildern und dem folgenden Prompt.")
        for img_path in ref_image_paths:
            img_bytes = pathlib.Path(img_path).read_bytes()
            mime = "image/png" if img_path.endswith(".png") else "image/jpeg"
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
    contents.append(prompt)
    
    response = client.models.generate_content(
        model=gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img_bytes = part.inline_data.data
            filename = "frame_{}.png".format(frame.id)
            frame.image.save(filename, ContentFile(img_bytes), save=True)
            frame.status = "done"
            frame.save()
            return
    raise Exception("Kein Bild in der Gemini-Antwort")


def _pipeline_flux_frame(frame, prompt, character_path=None, other_ref_paths=None):
    """FLUX frame gen with PuLID (character) + Redux (products/stills)."""
    import random
    from django.core.files.base import ContentFile
    from video.views import _build_flux_workflow
    
    url = _ensure_runpod_running()
    if not url:
        raise Exception("RunPod Pod nicht erreichbar")
    
    uploaded_character = []  # list for multi-image PuLID
    uploaded_others = []
    
    if character_path:
        if isinstance(character_path, (list, tuple)):
            for p in character_path:
                up = _upload_image_to_comfyui(url, p)
                if up:
                    uploaded_character.append(up)
        else:
            up = _upload_image_to_comfyui(url, character_path)
            if up:
                uploaded_character.append(up)
    
    if other_ref_paths:
        for p in other_ref_paths:
            name = _upload_image_to_comfyui(url, p)
            if name:
                uploaded_others.append(name)
    
    if not uploaded_character and not uploaded_others:
        raise Exception("Keine Referenzbilder verfügbar")
    
    # Quality params from scene if available
    scene_for_frame = None
    try:
        from video.models import Scene
        scene_for_frame = Scene.objects.filter(start_frame=frame).first() or Scene.objects.filter(end_frame=frame).first()
    except Exception:
        pass
    RES_MAP = {'1024': (1024, 1024), '1080_h': (1920, 1080), '1080_v': (1080, 1920), '2048': (2048, 2048)}
    if scene_for_frame:
        res = scene_for_frame.flux_resolution or '1024'
        steps = scene_for_frame.flux_steps or 24
        guidance = scene_for_frame.flux_guidance or 3.5
        pulid_w = scene_for_frame.pulid_cfg or 1.0
    else:
        res = '1024'; steps = 24; guidance = 3.5; pulid_w = 1.0
    width, height = RES_MAP.get(res, (1024, 1024))
    
    seed = random.randint(0, 2**31 - 1)
    workflow = _build_flux_workflow(uploaded_character, uploaded_others, prompt, seed,
                                     width=width, height=height, steps=steps,
                                     guidance=guidance, pulid_weight=pulid_w)
    
    prompt_id = _submit_workflow(url, workflow)
    result = _poll_status(url, prompt_id, timeout=300, scene_id=None)
    if result.get("status") != "done":
        raise Exception(f"FLUX Render fehlgeschlagen: {result}")
    
    outputs = result.get("outputs", {})
    image_info = None
    for node_id, out in outputs.items():
        if "images" in out and out["images"]:
            image_info = out["images"][0]
            break
    if not image_info:
        raise Exception("Kein Bild in ComfyUI-Output")
    
    filename = image_info["filename"]
    params = {"filename": filename, "subfolder": image_info.get("subfolder", ""), "type": image_info.get("type", "output")}
    r2 = requests.get(f"{url}/view", params=params, timeout=60)
    if r2.status_code != 200:
        raise Exception(f"Bild-Download fehlgeschlagen: {r2.status_code}")
    
    frame_filename = "frame_{}.png".format(frame.id)
    frame.image.save(frame_filename, ContentFile(r2.content), save=True)
    frame.status = "done"
    frame.save()


def _pipeline_generate_voiceover(scene):
    """Generate voiceover via local Piper or RunPod XTTS, then mux into video."""
    from django.core.files.base import ContentFile
    from . import tts as tts_module

    if not scene.voiceover_text or not scene.voiceover_text.strip():
        return

    audio_bytes = tts_module.generate_voiceover(scene)
    if audio_bytes:
        filename = f"voiceover_{str(scene.id)[:8]}.mp3"
        scene.audio_file.save(filename, ContentFile(audio_bytes), save=True)
        try:
            _mux_all_audio_into_video(scene)
        except Exception as _e:
            logger.warning(f"mux after pipeline voiceover failed: {_e}")


def _pipeline_generate_project_music(project, total_duration):
    """Generate ONE music track for the entire project duration."""
    from django.core.files.base import ContentFile
    from . import tts as tts_module

    prompt = (project.music_prompt or '').strip()
    genre = project.music_genre or ''
    if not prompt and not genre:
        return

    # MusicGen max is 30s, so for longer projects generate 30s and loop/extend later
    gen_duration = min(total_duration, 30)
    music_bytes = tts_module.generate_musicgen(prompt, duration_sec=gen_duration, genre=genre)
    if music_bytes:
        filename = f"project_music_{str(project.id)[:8]}.mp3"
        project.music_file.save(filename, ContentFile(music_bytes), save=True)
        logger.info(f"Project music generated: {gen_duration}s for project {project.id}")


def _pipeline_generate_music(scene):
    """Generate background music via MusicGen large on RunPod, then re-mux all audio."""
    from django.core.files.base import ContentFile
    from . import tts as tts_module

    prompt = (scene.music_prompt or '').strip()
    genre = scene.music_genre or ''
    if not prompt and not genre:
        return

    duration = float(scene.duration) if scene.duration else 10
    music_bytes = tts_module.generate_musicgen(prompt, duration_sec=duration, genre=genre)
    if music_bytes:
        filename = f"music_{str(scene.id)[:8]}.mp3"
        scene.music_file.save(filename, ContentFile(music_bytes), save=True)
        try:
            _mux_all_audio_into_video(scene)
        except Exception as _e:
            logger.warning(f"mux after music gen failed: {_e}")


def _mux_all_audio_into_video(scene):
    """Mux voiceover (if any) + music (if any) into scene video.
    Music gets mixed at scene.music_volume level behind the voiceover.
    Creates a new SceneVideo with +audio tag."""
    import subprocess, tempfile, os
    from django.core.files.base import ContentFile
    from .models import SceneVideo

    # Find the clean base video (no +audio, no +overlay)
    original = scene.rendered_videos.filter(status='done').exclude(
        model_used__icontains='+audio').exclude(
        model_used__icontains='+overlay').order_by('-created_at').first()
    if original and original.video_file:
        video_path = original.video_file.path
        base_tag = original.model_used
    elif scene.video_file:
        video_path = scene.video_file.path
        base_tag = scene.model_choice or 'scene'
    else:
        logger.warning(f'mux_all_audio: no base video for scene {scene.id}')
        return None

    has_voice = bool(scene.audio_file and os.path.exists(scene.audio_file.path))
    has_music = bool(scene.music_file and os.path.exists(scene.music_file.path))

    if not has_voice and not has_music:
        return None

    if not os.path.exists(video_path):
        logger.warning(f'mux_all_audio: video file missing: {video_path}')
        return None

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        out_path = tmp.name

    music_vol = scene.music_volume if hasattr(scene, 'music_volume') else 0.3
    music_vol = max(0.05, min(1.0, music_vol))

    try:
        cmd = ['ffmpeg', '-y', '-i', video_path]

        if has_voice and has_music:
            cmd += ['-i', scene.audio_file.path, '-i', scene.music_file.path]
            # Mix voice at full volume + music at music_vol, trim to video length
            cmd += [
                '-filter_complex',
                f'[2:a]volume={music_vol}[m];[1:a][m]amix=inputs=2:duration=shortest[aout]',
                '-map', '0:v:0', '-map', '[aout]',
            ]
        elif has_voice:
            cmd += ['-i', scene.audio_file.path,
                    '-map', '0:v:0', '-map', '1:a:0']
        else:  # only music
            cmd += ['-i', scene.music_file.path,
                    '-filter_complex', f'[1:a]volume={music_vol}[aout]',
                    '-map', '0:v:0', '-map', '[aout]']

        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path]

        result = subprocess.run(cmd, capture_output=True, timeout=180)
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', 'ignore')[-500:]
            logger.warning(f"mux_all_audio ffmpeg failed: {err}")
            return None

        new_video = SceneVideo(
            scene=scene,
            model_used=f'{base_tag}+audio',
            status='done',
            is_selected=True,
            render_duration_sec=0,
            render_cost=0,
        )
        with open(out_path, 'rb') as f:
            new_video.video_file.save(f'audio_{str(scene.id)[:8]}.mp4',
                                      ContentFile(f.read()), save=False)
        new_video.save()

        scene.rendered_videos.exclude(pk=new_video.pk).update(is_selected=False)
        scene.video_file = new_video.video_file
        scene.save(update_fields=['video_file'])
        logger.info(f"mux_all_audio: scene {scene.id} → {new_video.id} (voice={has_voice} music={has_music})")
        return new_video
    finally:
        try:
            os.remove(out_path)
        except Exception:
            pass


def _probe_video_dims(path):
    """Return (width, height) of the video, or (1920, 1080) on failure."""
    import subprocess, json
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height', '-of', 'json', path],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            d = json.loads(r.stdout)
            s = d.get('streams', [{}])[0]
            return int(s.get('width', 1920)), int(s.get('height', 1080))
    except Exception:
        pass
    return 1920, 1080


def _build_drawtext_filter(text, pos_v, pos_h, style, video_width=1920, video_height=1080):
    """Build ffmpeg drawtext filter string + temp textfile path (caller must unlink).
    Wraps the text so it never exceeds ~85% of video width; supports multi-line.
    Returns tuple (filter_string, textfile_path)."""
    import os, tempfile, textwrap

    # Style presets
    styles = {
        'classic':  {'fontsize': 42, 'fontcolor': 'white', 'box': 1, 'boxcolor': 'black@0.55', 'boxborderw': 12, 'borderw': 0, 'bordercolor': 'black'},
        'modern':   {'fontsize': 56, 'fontcolor': 'white', 'box': 0, 'boxcolor': '',            'boxborderw': 0,  'borderw': 4, 'bordercolor': 'black'},
        'subtitle': {'fontsize': 30, 'fontcolor': 'white', 'box': 1, 'boxcolor': 'black@0.7',  'boxborderw': 8,  'borderw': 0, 'bordercolor': 'black'},
        'title':    {'fontsize': 64, 'fontcolor': 'white', 'box': 0, 'boxcolor': '',            'boxborderw': 0,  'borderw': 6, 'bordercolor': 'black'},
    }
    s = styles.get(style, styles['classic'])

    # Scale fontsize down for low-res videos (e.g. 832x480) so it fits
    fs_scale = min(1.0, video_width / 1920.0)
    fontsize = max(18, int(round(s['fontsize'] * fs_scale)))

    # Approx char width for DejaVuSans-Bold ≈ 0.55 * fontsize
    max_width_px = video_width * 0.85
    avg_char_px = fontsize * 0.55
    max_chars = max(8, int(max_width_px / avg_char_px))

    # Wrap: respect any existing newlines from user, wrap each line
    wrapped_lines = []
    for raw_line in text.splitlines() or [text]:
        if not raw_line.strip():
            wrapped_lines.append('')
            continue
        wrapped_lines.extend(textwrap.wrap(raw_line, width=max_chars) or [''])
    wrapped = '\n'.join(wrapped_lines)

    # drawtext reads multi-line cleanly from a textfile= parameter.
    # Using textfile avoids shell/filter escaping headaches entirely.
    tf = tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8')
    tf.write(wrapped)
    tf.close()
    textfile_path = tf.name

    # Vertical position (account for multi-line text height)
    if pos_v == 'top':
        y = '80'
    elif pos_v == 'middle':
        y = '(h-text_h)/2'
    else:  # bottom
        y = 'h-text_h-100'

    # Horizontal position
    if pos_h == 'left':
        x = '60'
    elif pos_h == 'right':
        x = 'w-text_w-60'
    else:  # center
        x = '(w-text_w)/2'

    parts = [
        f"textfile='{textfile_path}'",
        'reload=0',
        f"x={x}", f"y={y}",
        f"fontsize={fontsize}",
        f"fontcolor={s['fontcolor']}",
        "line_spacing=8",
    ]
    if s['box']:
        parts.append(f"box={s['box']}")
        parts.append(f"boxcolor={s['boxcolor']}")
        parts.append(f"boxborderw={s['boxborderw']}")
    if s['borderw']:
        parts.append(f"borderw={max(2, int(round(s['borderw'] * fs_scale)))}")
        parts.append(f"bordercolor={s['bordercolor']}")

    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            parts.append(f"fontfile={fp}")
            break

    return "drawtext=" + ":".join(parts), textfile_path




def _mux_audio_into_video(scene):
    """Mux scene.audio_file into scene.video_file and update scene.video_file to the muxed version.
    Creates a new SceneVideo with model_used='<orig>+audio' that is selected."""
    import subprocess, tempfile, os
    from django.core.files.base import ContentFile
    from .models import SceneVideo

    if not scene.audio_file:
        return None

    # Use the NEWEST clean original (non-overlay, non-audio) version for base
    original = scene.rendered_videos.filter(status='done').exclude(model_used__icontains='+audio').exclude(model_used__icontains='+overlay').order_by('-created_at').first()
    if original and original.video_file:
        video_path = original.video_file.path
        base_tag = original.model_used
    elif scene.video_file:
        video_path = scene.video_file.path
        base_tag = scene.model_choice or 'scene'
    else:
        logger.warning(f'mux_audio: no base video for scene {scene.id}')
        return None

    audio_path = scene.audio_file.path
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        logger.warning(f"mux_audio: missing files video={os.path.exists(video_path)} audio={os.path.exists(audio_path)}")
        return None

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        out_path = tmp.name

    try:
        # -shortest trims to the shorter of video/audio so we don't extend beyond video
        result = subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest',
            out_path
        ], capture_output=True, timeout=180)

        if result.returncode != 0:
            err = result.stderr.decode('utf-8', 'ignore')[-500:]
            logger.warning(f"mux_audio ffmpeg failed: {err}")
            return None

        # Create new SceneVideo
        new_video = SceneVideo(
            scene=scene,
            model_used=f'{base_tag}+audio',
            status='done',
            is_selected=True,
            render_duration_sec=0,
            render_cost=0,
        )
        with open(out_path, 'rb') as f:
            new_video.video_file.save(f'audio_{str(scene.id)[:8]}.mp4', ContentFile(f.read()), save=False)
        new_video.save()

        # Deselect others, set scene.video_file to new muxed version
        scene.rendered_videos.exclude(pk=new_video.pk).update(is_selected=False)
        scene.video_file = new_video.video_file
        scene.save(update_fields=['video_file'])
        logger.info(f"mux_audio: scene {scene.id} → new video {new_video.id}")
        return new_video
    finally:
        try:
            os.remove(out_path)
        except Exception:
            pass



@shared_task
def apply_text_overlay_task(scene_id):
    """Apply text overlay to the currently-selected video via ffmpeg and save as new SceneVideo version."""
    import subprocess, tempfile, os
    from django.core.files.base import ContentFile
    from .models import Scene, SceneVideo

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return {"error": "scene not found"}

    if not scene.text_overlay or not scene.text_overlay.strip():
        return {"error": "kein Overlay-Text gesetzt"}

    # Prefer the newest +audio version as base (so overlay stacks on muxed audio).
    # If no +audio exists, use newest clean render. Always exclude +overlay to avoid stacking.
    base_query = scene.rendered_videos.filter(status='done').exclude(model_used__icontains='+overlay')
    original = base_query.filter(model_used__icontains='+audio').order_by('-created_at').first()
    if not original:
        original = base_query.order_by('-created_at').first()

    if original and original.video_file:
        source_path = original.video_file.path
        base_video = original
    elif scene.video_file:
        source_path = scene.video_file.path
        base_video = None
    else:
        return {"error": "kein Video vorhanden"}

    if not os.path.exists(source_path):
        return {"error": "Video-Datei fehlt auf Disk"}

    vw, vh = _probe_video_dims(source_path)
    filter_str, textfile_path = _build_drawtext_filter(
        scene.text_overlay.strip(),
        scene.overlay_pos_v,
        scene.overlay_pos_h,
        scene.overlay_style,
        video_width=vw,
        video_height=vh,
    )
    logger.warning(f"Overlay scene={scene.id} v={scene.overlay_pos_v} h={scene.overlay_pos_h} style={scene.overlay_style} src_dims={vw}x{vh}")

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        out_path = tmp.name

    try:
        # Probe audio to decide whether to copy an audio stream
        src_has_audio = bool(subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'a',
             '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', source_path],
            capture_output=True, text=True, timeout=10).stdout.strip())

        cmd = ['ffmpeg', '-y', '-i', source_path, '-vf', filter_str,
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '20']
        if src_has_audio:
            cmd += ['-c:a', 'copy']
        cmd.append(out_path)
        result = subprocess.run(cmd, capture_output=True, timeout=300)

        if result.returncode != 0:
            err = result.stderr.decode('utf-8', 'ignore')[-500:]
            return {"error": f"ffmpeg fehlgeschlagen: {err}"}

        scene.rendered_videos.update(is_selected=False)

        new_video = SceneVideo(
            scene=scene,
            model_used=f'{(base_video.model_used if base_video else scene.model_choice or "overlay")}+overlay',
            status='done',
            is_selected=True,
            render_duration_sec=0,
            render_cost=0,
        )
        with open(out_path, 'rb') as f:
            new_video.video_file.save(f'overlay_{str(scene.id)[:8]}.mp4', ContentFile(f.read()), save=False)
        new_video.save()

        scene.video_file = new_video.video_file
        scene.save(update_fields=['video_file'])

        return {"status": "ok", "video_id": str(new_video.id), "video_url": new_video.video_file.url}
    finally:
        try:
            os.remove(out_path)
        except Exception:
            pass
        try:
            os.remove(textfile_path)
        except Exception:
            pass

