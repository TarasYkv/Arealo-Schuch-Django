"""
ComfyUI Video Generation Tasks for Workloom
Handles: GPU instance management (Thunder Compute), ComfyUI API, video rendering pipeline
"""
import json, os, time, logging, subprocess
from pathlib import Path
from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# ── Thunder Compute API ──
THUNDER_API_TOKEN = "3b6d282ebeb7945d95c141925fc4ac6c0cd118da34192ce876d48cebf5d73be1"
THUNDER_API_URL = "https://api.thundercompute.com:8443"

# Snapshot with ComfyUI + all models + ffmpeg
COMFYUI_SNAPSHOT_ID = "Ne7JwcObN6y39QtwEnQu"

# Connection state (updated dynamically)
THUNDER_SSH_KEY = "/var/www/.ssh/thunder_compute"
COMFYUI_PORT = 8188


def _thunder_api(endpoint, method="GET", data=None, timeout=30):
    """Call Thunder Compute REST API."""
    import requests as req_lib
    url = f"{THUNDER_API_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {THUNDER_API_TOKEN}", "Content-Type": "application/json"}
    try:
        if method == "GET":
            r = req_lib.get(url, headers=headers, timeout=timeout, verify=False)
        else:
            r = req_lib.post(url, headers=headers, json=data, timeout=timeout, verify=False)
        return r.json() if r.text.strip() else {}
    except Exception as e:
        logger.warning(f"Thunder API error: {e}")
        return {}


def _get_thunder_instance():
    """Get running instance info. Returns (index, instance_dict) or (None, None)."""
    data = _thunder_api("/instances/list")
    if not data:
        return None, None
    for idx, inst in data.items():
        if inst.get("status") == "RUNNING":
            return idx, inst
    return None, None


def _ssh_cmd(cmd, timeout=30):
    """Run SSH command on Thunder instance. Returns stdout string."""
    _, inst = _get_thunder_instance()
    if not inst:
        raise RuntimeError("No running Thunder Compute instance")
    host = inst["ip"]
    port = inst["port"]
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-i", THUNDER_SSH_KEY,
        "-p", str(port),
        f"ubuntu@{host}",
        cmd
    ]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(f"SSH error (rc={result.returncode}): {result.stderr[:200]}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"SSH command timed out: {cmd[:100]}")


def _scp_from(remote_path, local_path):
    """Download file from Thunder instance via SCP."""
    _, inst = _get_thunder_instance()
    if not inst:
        raise RuntimeError("No running Thunder instance")
    host = inst["ip"]
    port = inst["port"]
    scp_cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-i", THUNDER_SSH_KEY,
        "-P", str(port),
        f"ubuntu@{host}:{remote_path}",
        local_path
    ]
    result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"SCP error: {result.stderr[:200]}")


def _ensure_instance_running(max_wait=120):
    """Ensure a Thunder Compute instance is running. Returns (host, port)."""
    # Check if already running
    _, inst = _get_thunder_instance()
    if inst:
        # Test SSH connectivity
        try:
            out = _ssh_cmd("echo ok", timeout=10)
            if "ok" in out:
                return inst["ip"], inst["port"]
        except:
            pass  # Instance exists but not reachable, create new

    # Create new instance from snapshot
    logger.info(f"Creating Thunder instance from snapshot {COMFYUI_SNAPSHOT_ID}...")
    result = _thunder_api("/instances/create", "POST", {
        "cpu_cores": 8,
        "disk_size_gb": 200,
        "gpu_type": "A100XL",
        "num_gpus": 1,
        "mode": "prototyping",
        "template": "base",
        "snapshot_id": COMFYUI_SNAPSHOT_ID,
        "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM9n5lBIsD9bHh44bwmgSJ3qtBFPw/05OiF3nQ4SlNzO",
    }, timeout=60)

    # Wait for instance to become RUNNING
    start = time.time()
    while time.time() - start < max_wait:
        time.sleep(10)
        _, inst = _get_thunder_instance()
        if inst and inst.get("status") == "RUNNING":
            # Wait for SSH to be available
            for _ in range(12):
                try:
                    out = _ssh_cmd("echo ok", timeout=5)
                    if "ok" in out:
                        # Start ComfyUI
                        _ssh_cmd("pkill -f main.py 2>/dev/null; cd /home/ubuntu/ComfyUI && nohup python3 main.py --listen 0.0.0.0 --port 8188 > /tmp/comfyui.log 2>&1 &", timeout=15)
                        time.sleep(8)
                        # Verify ComfyUI is up
                        for _ in range(10):
                            try:
                                check = _ssh_cmd(f"curl -sf http://localhost:{COMFYUI_PORT}/system_stats", timeout=5)
                                if check and "comfyui" in check.lower():
                                    logger.info(f"Instance ready: {inst['ip']}:{inst['port']}")
                                    return inst["ip"], inst["port"]
                            except:
                                pass
                            time.sleep(3)
                        break
                except:
                    pass
                time.sleep(5)
            break

    raise RuntimeError("Failed to start Thunder instance within timeout")


def _shutdown_instance():
    """Delete the running instance."""
    idx, inst = _get_thunder_instance()
    if not inst:
        return
    uuid = inst.get("uuid", idx)
    try:
        _thunder_api(f"/instances/{uuid}/delete", "POST", timeout=30)
        logger.info("Thunder instance shut down")
    except Exception as e:
        logger.warning(f"Failed to shutdown instance: {e}")


def _submit_comfyui_prompt(workflow_json):
    """Submit workflow to ComfyUI and return prompt_id."""
    # Write workflow to remote file
    workflow_str = json.dumps(workflow_json)
    escaped = workflow_str.replace("'", "'\\''")
    _ssh_cmd(f"echo '{escaped}' > /tmp/workflow.json", timeout=10)
    
    result = _ssh_cmd(
        f"curl -sf -X POST http://localhost:{COMFYUI_PORT}/prompt "
        f"-H 'Content-Type: application/json' -d @/tmp/workflow.json",
        timeout=30
    )
    
    try:
        data = json.loads(result)
        prompt_id = data.get("prompt_id") or data.get("number")
        if not prompt_id:
            # Check for error
            error = data.get("error", data.get("node_errors", "Unknown error"))
            raise RuntimeError(f"ComfyUI prompt rejected: {error}")
        return prompt_id
    except json.JSONDecodeError:
        raise RuntimeError(f"ComfyUI invalid response: {result[:200]}")


def _wait_for_render(prompt_id, max_wait=600):
    """Wait for ComfyUI to finish rendering. Returns True if done."""
    # Clear old output files first
    _ssh_cmd("rm -f /home/ubuntu/ComfyUI/output/workloom/*.png /home/ubuntu/ComfyUI/output/workloom/*.mp4 2>/dev/null", timeout=5)
    
    start = time.time()
    while time.time() - start < max_wait:
        time.sleep(5)
        try:
            # Check queue
            queue_out = _ssh_cmd(f"curl -sf http://localhost:{COMFYUI_PORT}/queue", timeout=5)
            queue = json.loads(queue_out) if queue_out else {}
            running = queue.get("queue_running", [])
            pending = queue.get("queue_pending", [])
            
            # Check for output files
            count_out = _ssh_cmd(
                "find /home/ubuntu/ComfyUI/output/workloom -name '*.png' -newer /tmp/workflow.json 2>/dev/null | wc -l",
                timeout=5
            )
            num_files = int(count_out) if count_out.strip().isdigit() else 0
            
            if num_files > 0 and not running and not pending:
                return True
        except:
            pass
    
    return False


def _collect_output_video(scene_id, fps):
    """Collect PNG frames from ComfyUI output and convert to MP4."""
    remote_dir = f"/tmp/frames_{scene_id}"
    
    # Create frames dir and copy PNGs with sequential names
    _ssh_cmd(f"mkdir -p {remote_dir}", timeout=5)
    _ssh_cmd(
        f"cd /home/ubuntu/ComfyUI/output/workloom && "
        f"a=0; for f in $(ls *.png | sort); do "
        f"mv \"$f\" {remote_dir}/$(printf '%04d.png' $a); "
        f"a=$((a+1)); done",
        timeout=30
    )
    
    # Count frames
    count = _ssh_cmd(f"ls {remote_dir}/*.png 2>/dev/null | wc -l", timeout=5)
    num_frames = int(count.strip()) if count.strip().isdigit() else 0
    
    if num_frames == 0:
        raise RuntimeError("No PNG frames found in output directory")
    
    logger.info(f"Collected {num_frames} frames for scene {scene_id}")
    
    # Convert to MP4 with ffmpeg
    remote_mp4 = f"{remote_dir}/output.mp4"
    _ssh_cmd(
        f"ffmpeg -y -framerate {fps} -i {remote_dir}/%04d.png "
        f"-c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium {remote_mp4} 2>/dev/null",
        timeout=120
    )
    
    # Verify output
    size = _ssh_cmd(f"stat -c %s {remote_mp4} 2>/dev/null || echo 0", timeout=5)
    if int(size.strip()) < 5000:
        raise RuntimeError(f"ffmpeg output too small: {size.strip()} bytes")
    
    # Download to local
    local_file = f"/tmp/scene_{scene_id}.mp4"
    _scp_from(remote_mp4, local_file)
    
    # Cleanup remote
    _ssh_cmd(f"rm -rf {remote_dir}", timeout=5)
    
    return local_file


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def render_scene_task(scene_id):
    """Main render task: Create video from scene using ComfyUI on GPU."""
    from video.models import Scene
    from video.comfyui_workflows.builder import build_workflow

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        logger.error(f"Scene {scene_id} not found")
        return

    scene.status = "rendering"
    scene.save(update_fields=["status"])
    
    render_start = time.time()
    
    try:
        # 1. Ensure GPU instance is running
        logger.info(f"Scene {scene_id}: Starting render, model={scene.model_choice}")
        host, port = _ensure_instance_running()
        
        # 2. Build workflow
        workflow = build_workflow(
            model_choice=scene.model_choice or "wan-2.2",
            prompt=scene.prompt,
            num_frames=scene.num_frames if hasattr(scene, 'num_frames') else None,
            width=scene.width if hasattr(scene, 'width') else None,
            height=scene.height if hasattr(scene, 'height') else None,
            fps=scene.fps or 16,
            seed=scene.seed if hasattr(scene, 'seed') else None,
            steps=scene.num_steps or 20,
            guidance_scale=scene.guidance_scale or 5.0,
            negative_prompt=scene.negative_prompt or "",
            filename_prefix=f"workloom/scene_{scene_id}",
        )
        
        # 3. Submit to ComfyUI
        prompt_id = _submit_comfyui_prompt(workflow)
        logger.info(f"Scene {scene_id}: ComfyUI prompt {prompt_id} submitted")
        
        # 4. Wait for render
        done = _wait_for_render(prompt_id)
        if not done:
            raise RuntimeError("ComfyUI render timeout")
        
        # 5. Collect output
        render_seconds = round(time.time() - render_start, 1)
        fps = scene.fps or 16
        local_file = _collect_output_video(scene_id, fps)
        
        # 6. Save video
        video_bytes = Path(local_file).read_bytes()
        filename = f"scene_{scene_id}.mp4"
        scene.video_file.save(filename, ContentFile(video_bytes), save=True)
        
        # 7. Update scene
        scene.status = "done"
        scene.render_duration_sec = render_seconds
        scene.render_cost = round(render_seconds / 3600 * 0.78, 2)  # A100XL $0.78/h
        scene.save()
        
        logger.info(f"Scene {scene_id}: Render complete in {render_seconds}s, Cost: ${scene.render_cost}")
        
        # 8. Schedule shutdown after 2 minutes (give time for any queued renders)
        try:
            shutdown_scene.delay(120)
        except:
            pass  # shutdown_scene not registered as task
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Scene {scene_id}: Render failed: {error_msg}")
        try:
            scene = Scene.objects.get(id=scene_id)
            scene.status = "error"
            scene.error_message = error_msg[:1000]
            scene.render_duration_sec = round(time.time() - render_start, 1)
            scene.save()
        except:
            pass


@shared_task
def shutdown_scene():
    """Shutdown GPU instance after render."""
    # Only shutdown if no renders are currently running
    from video.models import Scene
    rendering = Scene.objects.filter(status="rendering").exists()
    if not rendering:
        time.sleep(10)  # Small delay to be sure
        rendering = Scene.objects.filter(status="rendering").exists()
        if not rendering:
            _shutdown_instance()
