from celery import shared_task
from django.core.files.base import ContentFile
from pathlib import Path
import time
import json
import requests
import subprocess
import os

# Thunder Compute config (dynamically updated)
THUNDER_HOST = "62.169.159.253"
THUNDER_PORT = "30098"
THUNDER_USER = "ubuntu"
THUNDER_KEY = "/var/www/.ssh/thunder_compute"
COMFYUI_PORT = 8188

# ComfyUI snapshot
COMFYUI_SNAPSHOT_NAME = "workloom-comfyui-final"
COMFYUI_SNAPSHOT_ID = "Ne7JwcObN6y39QtwEnQu"

# LaoZhang API config
LAOZHANG_BASE = "https://api.laozhang.ai/v1"

# Thunder models (rendered via ComfyUI)
THUNDER_MODELS = {
    "cogvideox": "wan",
    "wan-2.1": "wan",
    "wan-2.2": "wan",
    "wan-2.5-480p": "wan",
    "wan-2.5-720p": "wan",
    "wan-2.5-1080p": "wan",
    "wan-2.6-720p": "wan",
    "wan-2.6-1080p": "wan",
    "ltx-2-distilled": "ltx",
    "hunyuanvideo": "hunyuan",
}

LAOZHANG_MODELS = {
    "veo-3.1-fast": "veo-3.1-fast",
    "veo-3.1": "veo-3.1",
    "veo-3.1-fast-fl": "veo-3.1-fast-fl",
    "veo-3.1-fl": "veo-3.1-fl",
    "veo-3.1-relaxed": "veo-3.1-relaxed",
    "veo-3.1-relaxed-fl": "veo-3.1-relaxed-fl",
    "sora-2": "sora-2",
    "sora-2-pro": "sora-2-pro",
    "sora-image": "sora-image",
    "sora-character": "sora-character",
    "minimax-m2.1": "minimax-m2.1",
    "minimax-m2.5": "minimax-m2.5",
    "minimax-m2.7": "minimax-m2.7",
}


def _ssh_cmd(cmd, timeout=600, retries=3):
    """Run command on Thunder Compute via SSH with retry logic."""
    import time as _time
    last_err = None
    for attempt in range(retries):
        try:
            proc = subprocess.Popen(
                ["ssh", "-i", THUNDER_KEY, "-p", THUNDER_PORT,
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=10",
                 "-o", "ServerAliveInterval=15",
                 "-o", "ServerAliveCountMax=4",
                 f"{THUNDER_USER}@{THUNDER_HOST}", cmd],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            if proc.returncode != 0:
                err = stderr.decode()[:300]
                if proc.returncode == 255:
                    last_err = f"SSH error (rc={proc.returncode}): {err}"
                    _time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"SSH error (rc={proc.returncode}): {err}")
            return stdout.decode().strip()
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=5)
            except:
                pass
            last_err = f"SSH timeout after {timeout}s (attempt {attempt+1}/{retries})"
            _time.sleep(2)
    raise RuntimeError(f"SSH failed after {retries} retries: {last_err}")


def _scp_to(local_path, remote_path):
    """Upload file to Thunder Compute via SCP."""
    subprocess.run(
        ["scp", "-i", THUNDER_KEY, "-P", THUNDER_PORT,
         "-o", "StrictHostKeyChecking=no",
         local_path, f"{THUNDER_USER}@{THUNDER_HOST}:{remote_path}"],
        capture_output=True, timeout=120
    )


def _scp_from(remote_path, local_path):
    """Download file from Thunder Compute via SCP."""
    subprocess.run(
        ["scp", "-i", THUNDER_KEY, "-P", THUNDER_PORT,
         "-o", "StrictHostKeyChecking=no",
         f"{THUNDER_USER}@{THUNDER_HOST}:{remote_path}", local_path],
        capture_output=True, timeout=120
    )


# === Thunder Compute On-Demand Management ===
import urllib3
urllib3.disable_warnings()

THUNDER_API = "https://api.thundercompute.com:8443"
THUNDER_TOKEN = os.environ.get("THUNDER_API_KEY", "3b6d282ebeb7945d95c141925fc4ac6c0cd118da34192ce876d48cebf5d73be1")
THUNDER_HEADERS = {"Authorization": f"Bearer {THUNDER_TOKEN}", "Content-Type": "application/json"}
# Legacy Flask snapshot (kept as fallback)
SNAPSHOT_NAME = "workloom-video-server-v7"


def _thunder_api(path, method="GET", data=None, timeout=30):
    import requests as _r
    url = f"{THUNDER_API}{path}"
    if method == "GET":
        resp = _r.get(url, headers=THUNDER_HEADERS, verify=False, timeout=10)
    else:
        resp = _r.post(url, headers=THUNDER_HEADERS, json=data, verify=False, timeout=timeout)
    return resp.json()


def _get_thunder_instance():
    """Get first running instance."""
    try:
        instances = _thunder_api("/instances/list")
        for k, v in instances.items():
            if v.get("status") == "RUNNING":
                return k, v
    except:
        pass
    return None, None


def _save_ssh_key(key_pem):
    """Save SSH key to file."""
    with open(THUNDER_KEY, "w") as f:
        f.write(key_pem)
    os.chmod(THUNDER_KEY, 0o600)


def _comfyui_health_check(ip=None, port=None):
    """Check if ComfyUI is responding on the remote instance via SSH."""
    try:
        out = _ssh_cmd(
            f"curl -sf http://localhost:{COMFYUI_PORT}/system_stats",
            timeout=10
        )
        data = json.loads(out)
        return data.get("system", {}).get("ram", {}) is not None
    except:
        return False


def _ensure_thunder_running():
    """Start Thunder Compute instance with ComfyUI if not running. Returns (ip, port)."""
    global THUNDER_HOST, THUNDER_PORT

    # Check if instance is already running
    idx, inst = _get_thunder_instance()
    if inst:
        ip, port = inst["ip"], str(inst["port"])
        THUNDER_HOST, THUNDER_PORT = ip, port
        
        # Check if ComfyUI is already running
        if _comfyui_health_check():
            return ip, port
        
        # Try to start ComfyUI (instance up but ComfyUI not running)
        _start_comfyui()
        if _comfyui_health_check():
            return ip, port
        
        # Wait for ComfyUI to start
        for i in range(30):
            time.sleep(10)
            if _comfyui_health_check():
                return ip, port
        raise RuntimeError("Thunder Compute: ComfyUI not responding after 5 min")

    # === Create new instance from ComfyUI snapshot ===
    snap_id = COMFYUI_SNAPSHOT_ID
    
    # Also try by name as fallback
    try:
        snapshots = _thunder_api("/snapshots/list")
        if isinstance(snapshots, dict):
            snapshots = [{"id": k, **v} for k, v in snapshots.items()]
        for snap in (snapshots if isinstance(snapshots, list) else []):
            if COMFYUI_SNAPSHOT_NAME in snap.get("name", ""):
                snap_id = snap.get("id") or snap.get("uuid")
                break
    except:
        pass

    if not snap_id:
        raise RuntimeError("No ComfyUI Thunder Compute snapshot found")

    # Create instance from snapshot
    result = _thunder_api("/instances/create", "POST", {
        "cpu_cores": 8,
        "disk_size_gb": 200,
        "gpu_type": "A100XL",
        "num_gpus": 1,
        "mode": "prototyping",
        "template": "base",
        "snapshot_id": snap_id,
        "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM9n5lBIsD9bHh44bwmgSJ3qtBFPw/05OiF3nQ4SlNzO",
    }, timeout=60)
    
    # Also create snapshot after models are installed (uses InstanceID with capital)
    # Snapshot creation requires InstanceID field (capital I and D)
    
    # Also create snapshot after models are installed (uses InstanceID with capital)
    # Snapshot creation requires InstanceID field (capital I and D)

    # Save the new SSH key
    new_key = result.get("key", "")
    if new_key:
        _save_ssh_key(new_key)

    # Wait for instance to be RUNNING (usually ~30 seconds)
    for i in range(30):
        time.sleep(5)
        idx, inst = _get_thunder_instance()
        if inst and inst.get("status") == "RUNNING":
            ip, port = inst["ip"], str(inst["port"])
            THUNDER_HOST, THUNDER_PORT = ip, port
            break
    else:
        raise RuntimeError("Thunder Compute: instance creation timeout")

    # Start ComfyUI on the instance
    _start_comfyui()
    
    # Wait for ComfyUI to be ready
    for i in range(60):
        time.sleep(5)
        if _comfyui_health_check():
            return ip, port

    raise RuntimeError("Thunder Compute: ComfyUI not responding after instance start")


def _start_comfyui():
    """Start ComfyUI on the Thunder Compute instance via SSH."""
    # Kill any existing ComfyUI screen session
    _ssh_cmd("screen -S comfy -X quit 2>/dev/null; pkill -f 'main.py.*8188' 2>/dev/null", timeout=10)
    time.sleep(2)
    
    # Start ComfyUI in screen session
    _ssh_cmd(
        f"screen -dmS comfy bash -c '"
        f"cd /home/ubuntu/ComfyUI && "
        f"python3 main.py --listen 0.0.0.0 --port {COMFYUI_PORT} "
        f"--output-directory /home/ubuntu/ComfyUI/output "
        f">> /tmp/comfyui.log 2>&1'",
        timeout=15
    )


def _upload_image_to_comfyui(local_img_path, remote_name):
    """Upload an image to ComfyUI's input directory on Thunder Compute."""
    remote_path = f"/home/ubuntu/ComfyUI/input/{remote_name}"
    _scp_to(local_img_path, remote_path)
    return remote_name


# === ComfyUI API Functions ===

def _comfyui_submit_workflow(workflow_json):
    """Submit a workflow to ComfyUI. Returns prompt_id."""
    # Write workflow to temp file on remote
    workflow_b64 = __import__('base64').b64encode(
        json.dumps(workflow_json).encode()
    ).decode()
    
    _ssh_cmd(
        f"echo '{workflow_b64}' | base64 -d > /tmp/comfy_workflow.json",
        timeout=10
    )
    
    # Submit via curl to ComfyUI API
    output = _ssh_cmd(
        f"curl -sf -X POST http://localhost:{COMFYUI_PORT}/prompt "
        f"-H 'Content-Type: application/json' "
        f"-d @/tmp/comfy_workflow.json",
        timeout=30
    )
    
    result = json.loads(output)
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI: no prompt_id returned: {output}")
    return prompt_id


def _comfyui_poll_status(prompt_id):
    """Poll ComfyUI for workflow status. Returns (status, outputs)."""
    output = _ssh_cmd(
        f"curl -sf http://localhost:{COMFYUI_PORT}/history/{prompt_id}",
        timeout=15
    )
    
    if not output.strip():
        return "pending", {}
    
    history = json.loads(output)
    prompt_data = history.get(prompt_id, {})
    
    status = prompt_data.get("status", {})
    status_str = status.get("status_str", "pending")
    
    if status_str == "success":
        outputs = prompt_data.get("outputs", {})
        return "done", outputs
    elif status_str == "error":
        msgs = status.get("messages", [])
        err_msg = str(msgs) if msgs else "Unknown error"
        return "error", {"error": err_msg}
    elif status_str in ("running", "in progress"):
        return "running", {}
    
    return "pending", {}


def _comfyui_download_output(filename, subfolder="", output_type="output"):
    """Download output file from ComfyUI via SSH curl + SCP."""
    # Build the view URL
    params = f"filename={filename}"
    if subfolder:
        params += f"&subfolder={subfolder}"
    params += f"&type={output_type}"
    
    # Use SSH to download the file locally on the Thunder instance first
    # Then SCP it to our server
    remote_tmp = f"/tmp/comfy_output_{filename}"
    
    _ssh_cmd(
        f"curl -sf 'http://localhost:{COMFYUI_PORT}/view?{params}' "
        f"-o {remote_tmp}",
        timeout=120
    )
    
    # Verify file exists and has content
    size_check = _ssh_cmd(f"stat -c %s {remote_tmp} 2>/dev/null || echo 0", timeout=10)
    if int(size_check) < 1000:
        raise RuntimeError(f"ComfyUI output too small ({size_check} bytes): {filename}")
    
    return remote_tmp


def _thunder_idle_shutdown():
    """Delete instance immediately after render."""
    idx, inst = _get_thunder_instance()
    if not inst or inst.get("status") != "RUNNING":
        return
    uuid = inst.get("uuid", idx)
    try:
        _thunder_api(f"/instances/{uuid}/delete", "POST", timeout=30)
    except:
        pass


def _thunder_idle_check():
    """Check if idle - called by celery beat every 1 min."""
    import datetime as _dt
    idx, inst = _get_thunder_instance()
    if not inst or inst.get("status") != "RUNNING":
        return
    # Safety net: kill after 20 minutes
    try:
        created = inst.get("createdAt", "")
        if created:
            start = _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
            age = (_dt.datetime.now(_dt.timezone.utc) - start).total_seconds()
            if age > 1800:  # 30 minutes
                import logging
                logging.warning(f"Thunder instance running {int(age/60)}min - force deleting")
                _thunder_api(f"/instances/{inst.get("uuid", idx)}/delete", "POST", timeout=30)
                return
    except:
        pass
    # Check if ComfyUI has active prompts
    try:
        output = _ssh_cmd(f"curl -sf http://localhost:{COMFYUI_PORT}/queue", timeout=10)
        queue = json.loads(output)
        running = queue.get("queue_running", [])
        pending = queue.get("queue_pending", [])
        if not running and not pending:
            # No active jobs - shut down
            _thunder_api(f"/instances/{inst.get("uuid", idx)}/delete", "POST", timeout=30)
    except:
        pass


def _render_thunder_comfyui(scene, api_key=None):
    """Render video on Thunder Compute GPU via ComfyUI API."""
    global THUNDER_HOST, THUNDER_PORT
    from video.comfyui_workflows.builder import build_workflow
    
    # Start instance + ComfyUI (~35-60 seconds)
    ip, port = _ensure_thunder_running()

    model = scene.model_choice or "wan-2.2"
    prompt = (scene.prompt or "A beautiful cinematic scene").replace("#test", "").strip()

    # Upload start/end frames to ComfyUI input directory
    start_image_name = None
    end_image_name = None
    
    if scene.start_frame and scene.start_frame.image:
        img_path = scene.start_frame.image.path
        ext = Path(img_path).suffix or ".jpg"
        start_image_name = f"scene_{scene.id}_start{ext}"
        _upload_image_to_comfyui(img_path, start_image_name)

    if scene.end_frame and scene.end_frame.image:
        img_path = scene.end_frame.image.path
        ext = Path(img_path).suffix or ".jpg"
        end_image_name = f"scene_{scene.id}_end{ext}"
        _upload_image_to_comfyui(img_path, end_image_name)

    # Build workflow
    workflow = build_workflow(
        model_choice=model,
        prompt=prompt,
        num_frames=min((scene.duration or 5) * 8, 81),
        seed=scene.seed or 42,
        steps=scene.num_steps or None,
        guidance_scale=scene.guidance_scale or None,
        start_image=start_image_name,
        end_image=end_image_name,
        negative_prompt=scene.negative_prompt or "",
    )

    # Submit to ComfyUI
    prompt_id = _comfyui_submit_workflow(workflow)

    # Poll for completion: watch output directory for new PNG files
    render_start = time.time()
    # Clear old output files first
    _ssh_cmd("mkdir -p /home/ubuntu/ComfyUI/output/workloom && rm -f /home/ubuntu/ComfyUI/output/workloom/*.png /home/ubuntu/ComfyUI/output/workloom/*.mp4", timeout=5)
    
    done = False
    for poll_i in range(180):  # up to 15 minutes
        time.sleep(5)
        
        # Check queue status
        try:
            queue_out = _ssh_cmd(f"curl -sf http://localhost:{COMFYUI_PORT}/queue", timeout=5)
            queue = json.loads(queue_out) if queue_out.strip() else {}
            running = queue.get("queue_running", [])
            pending = queue.get("queue_pending", [])
            
            # Check if there are output files
            count_out = _ssh_cmd("ls /home/ubuntu/ComfyUI/output/workloom/*.png 2>/dev/null | wc -l", timeout=5)
            num_files = int(count_out.strip()) if count_out.strip() else 0
            
            if num_files > 0 and not running and not pending:
                done = True
        except:
            pass
        
        if done:
            # Collect all output images from SaveImage node
            # Get output files from ComfyUI output directory
            output_dir = "/home/ubuntu/ComfyUI/output/workloom"
            # List all files created after render started
            list_cmd = f"find {output_dir} -name '*.png' -newer {output_dir}/.. -mmin -30 | sort"
            files_str = _ssh_cmd(list_cmd, timeout=10)
            if not files_str.strip():
                # Fallback: list all PNG files sorted by time
                files_str = _ssh_cmd(f"ls -t {output_dir}/*.png 2>/dev/null | head -100", timeout=10)
            
            all_images = []
            for fpath in files_str.strip().split("\n"):
                if fpath and fpath.endswith(".png"):
                    all_images.append({"filename": fpath.split("/")[-1], "subfolder": "workloom", "type": "output"})
            
            if not all_images:
                raise RuntimeError(f"ComfyUI: no PNG files found in {output_dir}")
            
            # Download all frames to remote tmp dir
            remote_dir = f"/tmp/comfy_frames_{scene.id}"
            _ssh_cmd(f"mkdir -p {remote_dir} && rm -f {remote_dir}/*", timeout=5)
            
            frame_idx = 0
            for img_info in all_images:
                filename = img_info.get("filename", "")
                if not filename:
                    continue
                
                # Copy from output dir to frames dir
                src = f"/home/ubuntu/ComfyUI/output/workloom/{filename}"
                remote_frame = f"{remote_dir}/frame_{frame_idx:04d}.png"
                _ssh_cmd(f"cp {src} {remote_frame}", timeout=10)
                frame_idx += 1
            
            if frame_idx == 0:
                raise RuntimeError("ComfyUI: no frames downloaded")
            
            # Rename frames to sequential numbering for ffmpeg
            rename_cmd = (
                f"cd {remote_dir} && "
                "a=0; for f in $(ls *.png | sort); do "
                "mv \"$f\" \"$(printf 'frame_%04d.png' $a)\"; "
                "a=$((a+1)); done"
            )
            _ssh_cmd(rename_cmd, timeout=30)

            # Rename frames to sequential numbering for ffmpeg
            rename_cmd = (
                f"cd {remote_dir} && "
                "a=0; for f in $(ls *.png | sort); do "
                "mv \"$f\" \"$(printf 'frame_%04d.png' $a)\"; "
                "a=$((a+1)); done"
            )
            _ssh_cmd(rename_cmd, timeout=30)

            # Rename frames to sequential numbering for ffmpeg
            rename_cmd = (
                f"cd {remote_dir} && "
                "a=0; for f in $(ls *.png | sort); do "
                "mv \"$f\" \"$(printf 'frame_%04d.png' $a)\"; "
                "a=$((a+1)); done"
            )
            _ssh_cmd(rename_cmd, timeout=30)

            # Convert frames to MP4 using ffmpeg on remote
            remote_mp4 = f"{remote_dir}/output.mp4"
            fps = scene.fps or 16
            _ssh_cmd(
                f"ffmpeg -y -framerate {fps} -i {remote_dir}/frame_%04d.png "
                f"-c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium {remote_mp4} 2>/dev/null",
                timeout=120
            )
            
            # Verify mp4
            size_check = _ssh_cmd(f"stat -c %s {remote_mp4} 2>/dev/null || echo 0", timeout=5)
            if int(size_check) < 5000:
                raise RuntimeError(f"ComfyUI: ffmpeg output too small ({size_check} bytes)")
            
            # Download MP4 to local
            local_file = f"/tmp/scene_{scene.id}.mp4"
            _scp_from(remote_mp4, local_file)
            
            # Cleanup remote
            _ssh_cmd(f"rm -rf {remote_dir}", timeout=5)
            
            render_seconds = round(time.time() - render_start, 1)
            video_bytes = Path(local_file).read_bytes()
            
            return video_bytes, render_seconds, 0
        
        elif status == "error":
            raise RuntimeError(f"ComfyUI render error: {outputs.get('error', 'unknown')}")

    raise RuntimeError("ComfyUI render timeout: no result after 15 minutes")


def _render_laozhang(scene, api_key):
    """Render video via LaoZhang API"""
    model = LAOZHANG_MODELS.get(scene.model_choice, scene.model_choice)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": scene.prompt or "", "size": "1280x720", "seconds": str(scene.duration or 5)}

    resp = requests.post(f"{LAOZHANG_BASE}/video/generations", json=payload, headers=headers, timeout=60)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"LaoZhang error: {data['error']}")

    video_id = data.get("id") or data.get("data", {}).get("id")
    if not video_id:
        raise RuntimeError(f"No video ID in response: {data}")

    for _ in range(60):
        time.sleep(10)
        poll = requests.get(f"{LAOZHANG_BASE}/video/generations/{video_id}", headers=headers, timeout=30)
        poll_data = poll.json()
        status = poll_data.get("status") or poll_data.get("data", {}).get("status", "")
        if status in ("success", "completed", "done"):
            video_url = poll_data.get("url") or poll_data.get("data", {}).get("url", "")
            if video_url:
                video_resp = requests.get(video_url, timeout=180)
                return video_resp.content, 0, 0
            break
        elif status in ("failed", "error"):
            raise RuntimeError(f"LaoZhang generation failed: {poll_data}")

    raise RuntimeError("LaoZhang: generation timed out")


@shared_task(bind=True)
def render_scene_task(self, scene_id):
    from video.models import Scene, VideoAPIKey
    scene = Scene.objects.get(pk=scene_id)

    try:
        scene.status = 'generating'
        scene.error_message = ''
        scene.save()

        start_time = time.time()
        model = scene.model_choice or "wan-2.2"
        is_thunder = model in THUNDER_MODELS

        api_key = None
        try:
            key_obj = VideoAPIKey.objects.filter(user=scene.project.user).first()
            if key_obj:
                api_key = key_obj.api_key
        except:
            pass

        if is_thunder:
            video_bytes, render_sec, cost = _render_thunder_comfyui(scene, api_key)
        else:
            if not api_key:
                raise RuntimeError("API-Key benötigt. Bitte unter Einstellungen eingeben.")
            video_bytes, render_sec, cost = _render_laozhang(scene, api_key)

        elapsed = time.time() - start_time
        if not cost:
            cost = round(elapsed / 3600 * 0.78, 4)

        filename = f"scene_{scene.id}.mp4"
        scene.video_file.save(filename, ContentFile(video_bytes), save=True)
        scene.render_duration_sec = round(elapsed, 1)
        scene.render_cost = cost
        scene.status = 'done'
        scene.save()

    except Exception as e:
        try:
            scene = Scene.objects.get(pk=scene_id)
            scene.status = 'error'
            scene.error_message = str(e)[:500]
            scene.save()
        except:
            pass


@shared_task(bind=True)
def cleanup_stuck_scenes():
    from django.utils import timezone
    from datetime import timedelta
    from video.models import Scene
    cutoff = timezone.now() - timedelta(minutes=60)
    stuck = Scene.objects.filter(status='generating', created_at__lt=cutoff)
    count = stuck.count()
    for s in stuck:
        s.status = 'error'
        s.error_message = 'Auto-cancelled: stuck for 10+ minutes'
        s.save()
    return f'Reset {count} stuck scenes'


@shared_task(bind=True)
def thunder_auto_shutdown(self):
    """Celery Beat task: check every 1 min, shutdown if idle."""
    _thunder_idle_check()
