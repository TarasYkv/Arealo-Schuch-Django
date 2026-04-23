#!/usr/bin/env python3
"""
Thunder Compute On-Demand Manager for Workloom
- Start instance from snapshot when render job comes in
- Auto-stop (delete) after 10 min idle
"""

import os, sys, json, time, subprocess, threading
import requests

API = "https://api.thundercompute.com:8443"
TOKEN = os.environ.get("THUNDER_API_KEY", "3b6d282ebeb7945d95c141925fc4ac6c0cd118da34192ce876d48cebf5d73be1")
SNAPSHOT_ID = None  # Will be discovered
INSTANCE_UUID = "2z5bcdel"
SSH_KEY = "/root/.ssh/thunder_compute"
SSH_HOST = "154.54.100.231"
SSH_PORT = "31498"
SSH_USER = "ubuntu"
IDLE_TIMEOUT = 600  # 10 minutes

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def list_snapshots():
    r = requests.get(f"{API}/snapshots/list", headers=HEADERS, verify=False, timeout=10)
    return r.json()

def list_instances():
    r = requests.get(f"{API}/instances/list", headers=HEADERS, verify=False, timeout=10)
    return r.json()

def get_instance():
    instances = list_instances()
    for k, v in instances.items():
        if v.get("uuid") == INSTANCE_UUID or v.get("name") == INSTANCE_UUID:
            return v
    return None

def is_server_ready():
    """Check if Flask server is responding"""
    try:
        ssh_cmd = f"ssh -i {SSH_KEY} -p {SSH_PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=5 {SSH_USER}@{SSH_HOST} 'curl -s http://localhost:8888/health'"
        r = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return data.get("status") == "ok"
    except:
        pass
    return False

def create_instance_from_snapshot(snapshot_id):
    """Create a new instance from snapshot"""
    r = requests.post(f"{API}/instances/create", headers=HEADERS, json={
        "snapshot_id": snapshot_id,
        "gpu_type": "A100XL",
        "num_gpus": 1,
        "cpu_cores": 8,
        "memory": 64,
        "storage": 100,
        "mode": "prototyping",
        "template": "base"
    }, verify=False, timeout=30)
    return r.json()

def delete_instance(instance_id):
    """Delete (stop) an instance"""
    r = requests.post(f"{API}/instances/{instance_id}/delete", headers=HEADERS, verify=False, timeout=30)
    return r.json()

def update_ssh_config(new_ip, new_port):
    """Update global SSH config for new instance"""
    global SSH_HOST, SSH_PORT
    SSH_HOST = new_ip
    SSH_PORT = str(new_port)

def ensure_server_running():
    """Make sure the server is running. Start if needed. Returns (ip, port) or raises."""
    inst = get_instance()
    if inst and inst.get("status") == "RUNNING":
        update_ssh_config(inst["ip"], inst["port"])
        if is_server_ready():
            return inst["ip"], inst["port"]
        else:
            # Server running but Flask not ready - wait
            for i in range(30):
                if is_server_ready():
                    return SSH_HOST, SSH_PORT
                time.sleep(10)
            raise Exception("Server running but Flask not responding after 5 min")
    
    # Need to create from snapshot
    snapshots = list_snapshots()
    snap_id = None
    for k, v in snapshots.items():
        if "workloom" in v.get("name", "").lower() or "video" in v.get("name", "").lower():
            snap_id = v.get("id") or v.get("uuid") or k
            break
    if not snap_id:
        # Use latest snapshot
        for k, v in snapshots.items():
            snap_id = v.get("id") or v.get("uuid") or k
    
    if not snap_id:
        raise Exception("No snapshot found to create instance from")
    
    print(f"Creating instance from snapshot {snap_id}...")
    result = create_instance_from_snapshot(snap_id)
    print(f"Create result: {result}")
    
    # Wait for instance to be ready
    for i in range(60):  # 10 min timeout
        time.sleep(10)
        inst = get_instance()
        if inst and inst.get("status") == "RUNNING":
            update_ssh_config(inst["ip"], inst["port"])
            # Update Workloom's known SSH config
            os.system(f"ssh-keygen -R [{SSH_HOST}]:{SSH_PORT} 2>/dev/null")
            if is_server_ready():
                return SSH_HOST, SSH_PORT
        print(f"Waiting for instance... ({i+1}/60)")
    
    raise Exception("Instance creation timeout")

def stop_if_idle():
    """Delete instance if idle for too long"""
    inst = get_instance()
    if not inst or inst.get("status") != "RUNNING":
        return
    try:
        ssh_cmd = f"ssh -i {SSH_KEY} -p {SSH_PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=5 {SSH_USER}@{SSH_HOST} 'curl -s http://localhost:8888/health'"
        r = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            # If no model loaded and no active generation
            if not data.get("loaded_models") and data.get("vram_free_gb", 0) > 50:
                # Check if any render is in progress
                ssh_cmd2 = f"ssh -i {SSH_KEY} -p {SSH_PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=5 {SSH_USER}@{SSH_HOST} 'ls /tmp/video_*.mp4 -t 2>/dev/null | head -1; ps aux | grep python | grep -v grep'"
                r2 = subprocess.run(ssh_cmd2, shell=True, capture_output=True, text=True, timeout=10)
                # Simple heuristic: if no python process is using GPU
                if "python" not in r2.stdout or "generate" not in r2.stdout.lower():
                    print("Server idle, creating snapshot and shutting down...")
                    # Create fresh snapshot
                    requests.post(f"{API}/snapshots/create", headers=HEADERS, json={
                        "InstanceID": inst["uuid"],
                        "Name": "workloom-video-server"
                    }, verify=False, timeout=60)
                    # Delete instance
                    delete_instance(inst["uuid"])
                    print("Instance stopped!")
                    return True
    except Exception as e:
        print(f"Idle check error: {e}")
    return False

# === Integration for Workloom render_scene_task ===

def render_on_thunder(prompt, model, start_image=None, end_image=None, duration=5, fps=16):
    """Main entry point for rendering a video on Thunder Compute"""
    # 1. Ensure server is running
    ip, port = ensure_server_running()
    
    # 2. SCP start/end images if needed
    ssh_prefix = f"ssh -i {SSH_KEY} -p {port} -o StrictHostKeyChecking=no {SSH_USER}@{ip}"
    scp_prefix = f"scp -i {SSH_KEY} -P {port} -o StrictHostKeyChecking=no"
    
    start_url = None
    end_url = None
    
    if start_image:
        # Upload start image
        remote_path = f"/tmp/start_{int(time.time())}.png"
        os.system(f"{scp_prefix} {start_image} {SSH_USER}@{ip}:{remote_path}")
        start_url = f"file://{remote_path}"
    
    if end_image:
        remote_path = f"/tmp/end_{int(time.time())}.png"
        os.system(f"{scp_prefix} {end_image} {SSH_USER}@{ip}:{remote_path}")
        end_url = f"file://{remote_path}"
    
    # 3. Call Flask API
    payload = {
        "prompt": prompt,
        "model": model,
        "fps": fps,
        "duration": duration
    }
    if start_url:
        payload["start_image_url"] = start_url
    if end_url:
        payload["end_image_url"] = end_url
    
    import urllib.request
    api_url = f"http://{ip}:8888/generate"
    # Use SSH tunnel instead
    ssh_tunnel = f"{ssh_prefix} 'curl -s -X POST http://localhost:8888/generate -H \"Content-Type: application/json\" -d {json.dumps(json.dumps(payload))}'"
    
    r = subprocess.run(ssh_tunnel, shell=True, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise Exception(f"Render failed: {r.stderr}")
    
    result = json.loads(r.stdout)
    
    # 4. SCP video back
    if result.get("status") == "done":
        local_path = result["file"]
        scp_cmd = f"{scp_prefix} {SSH_USER}@{ip}:{local_path} /tmp/video_{int(time.time())}.mp4"
        os.system(scp_cmd)
    
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "status":
        inst = get_instance()
        if inst:
            print(f"Instance: {inst['uuid']} | Status: {inst['status']} | IP: {inst['ip']}:{inst['port']}")
        else:
            print("No instance found")
    
    elif cmd == "stop":
        inst = get_instance()
        if inst:
            print(f"Stopping {inst['uuid']}...")
            print(delete_instance(inst["uuid"]))
        else:
            print("No instance to stop")
    
    elif cmd == "start":
        ip, port = ensure_server_running()
        print(f"Server ready: {ip}:{port}")
    
    elif cmd == "idle-check":
        stop_if_idle()
    
    elif cmd == "snapshots":
        print(json.dumps(list_snapshots(), indent=2))
