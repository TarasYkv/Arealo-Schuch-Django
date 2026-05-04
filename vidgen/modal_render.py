"""
Modal.com GPU-Rendering für VidGen
Schnelles Video-Rendering auf Cloud-GPUs
"""
import modal
import os
import subprocess
import json
import tempfile
from pathlib import Path

# Modal App Definition
app = modal.App("vidgen-renderer")

# Docker Image mit VORINSTALLIERTEM Remotion!
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "ffmpeg",
        "curl",
        "git",
        # Für Chromium/Puppeteer (Remotion braucht das)
        "chromium",
        "libnss3",
        "libatk1.0-0",
        "libatk-bridge2.0-0",
        "libcups2",
        "libdrm2",
        "libxkbcommon0",
        "libxcomposite1",
        "libxdamage1",
        "libxfixes3",
        "libxrandr2",
        "libgbm1",
        "libasound2",
        "libpango-1.0-0",
        "libcairo2",
    )
    .run_commands(
        # Node.js 20 LTS installieren
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        # Remotion GLOBAL installieren (einmalig im Image!)
        "npm install -g @remotion/cli@4.0.438",
    )
    .pip_install("requests")
    .env({
        "PUPPETEER_SKIP_CHROMIUM_DOWNLOAD": "true",
        "PUPPETEER_EXECUTABLE_PATH": "/usr/bin/chromium",
        "NODE_ENV": "production",
    })
)


@app.function(
    image=image,
    gpu="T4",
    cpu=4,
    timeout=600,  # 10 Minuten max (sollte 2-3 Min dauern)
    memory=8192,
)
def render_video_gpu(
    config: dict,
    audio_data: bytes,
    timestamps_data: bytes,
    clips_data: list[bytes],
    remotion_files: dict[str, str],
    music_data: bytes | None = None,
    overlay_data: bytes | None = None,
) -> bytes:
    """
    Rendert ein Video auf Modal GPU.
    OPTIMIERT: Kein npm install mehr bei jedem Render!
    """
    
    # Arbeitsverzeichnis
    work_dir = Path("/tmp/remotion_render")
    work_dir.mkdir(parents=True, exist_ok=True)
    
    remotion_dir = work_dir / "project"
    public_dir = remotion_dir / "public"
    src_dir = remotion_dir / "src"
    
    # Projekt Setup (SCHNELL - nur Dateien schreiben, kein npm install!)
    setup_remotion_project_fast(remotion_dir, remotion_files)
    
    # Public-Ordner vorbereiten
    public_dir.mkdir(parents=True, exist_ok=True)
    
    # Dateien schreiben
    (public_dir / "voiceover.mp3").write_bytes(audio_data)
    (public_dir / "timestamps.json").write_bytes(timestamps_data)
    (public_dir / "config.json").write_text(json.dumps(config))
    
    for i, clip_bytes in enumerate(clips_data):
        (public_dir / f"clip{i+1}.mp4").write_bytes(clip_bytes)
    
    if music_data:
        (public_dir / "background_music.wav").write_bytes(music_data)
    
    if overlay_data:
        (public_dir / "overlay.png").write_bytes(overlay_data)
    
    print(f"Rendering: {config.get('title', 'Untitled')}")
    print(f"Duration: {config.get('duration', 0)}s, Clips: {len(clips_data)}, Frames: {config.get('totalFrames', 0)}")
    
    # Remotion rendern - OPTIMIERT
    output_path = work_dir / "output.mp4"
    
    env = os.environ.copy()
    env["PUPPETEER_EXECUTABLE_PATH"] = "/usr/bin/chromium"
    
    # Berechne optimale Concurrency basierend auf Frames
    total_frames = config.get('totalFrames', 900)
    # T4 hat 16GB VRAM, kann viele Frames parallel
    concurrency = min(16, max(4, total_frames // 100))
    
    print(f"Using concurrency: {concurrency}")
    
    result = subprocess.run(
        [
            "remotion", "render",  # Global installiert!
            "VidGenVideo",
            str(output_path),
            "--codec", "h264",
            "--crf", "23",
            "--concurrency", str(concurrency),
            "--timeout", "120000",
            "--gl", "angle",  # Hardware-beschleunigt!
            "--enable-multi-process-on-linux",
        ],
        cwd=str(remotion_dir),
        capture_output=True,
        text=True,
        timeout=500,
        env=env,
    )
    
    if result.returncode != 0:
        print(f"STDOUT: {result.stdout[-1000:]}")
        print(f"STDERR: {result.stderr[-1000:]}")
        raise RuntimeError(f"Render failed: {result.stderr[-500:]}")
    
    print("Rendering complete, compressing...")
    
    # Komprimieren mit NVIDIA GPU
    compressed_path = work_dir / "output_compressed.mp4"
    
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-hwaccel", "cuda", "-i", str(output_path),
             "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq",
             "-b:v", "4M", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart",
             str(compressed_path)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        print("Compressed with NVIDIA NVENC")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback zu CPU
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(output_path),
             "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "26", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart",
             str(compressed_path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        print("Compressed with CPU (fallback)")
    
    return compressed_path.read_bytes()


def setup_remotion_project_fast(remotion_dir: Path, remotion_files: dict[str, str]):
    """
    SCHNELLES Projekt-Setup - nur Dateien schreiben!
    Remotion ist bereits global installiert.
    """
    
    remotion_dir.mkdir(parents=True, exist_ok=True)
    src_dir = remotion_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    # Source-Dateien schreiben
    for filename, content in remotion_files.items():
        if filename in ["VidGenVideo.tsx", "Root.tsx", "index.ts"]:
            (src_dir / filename).write_text(content)
        else:
            (remotion_dir / filename).write_text(content)
    
    # Minimale package.json (nur für TypeScript/React Types)
    minimal_package = {
        "name": "vidgen-render",
        "version": "1.0.0",
        "type": "module",
        "dependencies": {
            "react": "^19.0.0",
            "react-dom": "^19.0.0",
            "remotion": "^4.0.438",
            "@remotion/cli": "^4.0.438"
        }
    }
    (remotion_dir / "package.json").write_text(json.dumps(minimal_package, indent=2))
    
    # Schnelles lokales Install (nur Types, Remotion CLI ist global)
    print("Quick npm install (types only)...")
    result = subprocess.run(
        ["npm", "install", "--prefer-offline", "--no-audit", "--no-fund"],
        cwd=str(remotion_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    if result.returncode != 0:
        # Ignoriere npm Fehler - Remotion CLI ist global verfügbar
        print(f"npm warning (non-fatal): {result.stderr[:200]}")
    
    print("Setup complete!")


@app.function(image=image, timeout=60)
def health_check() -> dict:
    """Prüft ob Modal-Setup funktioniert"""
    import shutil
    
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    node_ok = shutil.which("node") is not None
    chromium_ok = shutil.which("chromium") is not None
    remotion_ok = shutil.which("remotion") is not None
    
    node_version = subprocess.run(
        ["node", "--version"], 
        capture_output=True, 
        text=True
    ).stdout.strip() if node_ok else "N/A"
    
    remotion_version = subprocess.run(
        ["remotion", "--version"], 
        capture_output=True, 
        text=True
    ).stdout.strip() if remotion_ok else "N/A"
    
    try:
        gpu_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        gpu_name = gpu_result.stdout.strip() if gpu_result.returncode == 0 else "No GPU"
    except FileNotFoundError:
        gpu_name = "N/A"
    
    return {
        "status": "ok",
        "ffmpeg": ffmpeg_ok,
        "node": node_ok,
        "node_version": node_version,
        "chromium": chromium_ok,
        "remotion": remotion_ok,
        "remotion_version": remotion_version,
        "gpu": gpu_name,
    }


@app.local_entrypoint()
def main():
    print("Testing Modal VidGen Renderer...")
    print("Health Check:")
    result = health_check.remote()
    for k, v in result.items():
        print(f"  {k}: {v}")
