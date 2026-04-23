"""
TTS-Provider für VideoStudio-Voiceovers.

Unterstützt:
- Piper (lokal auf CPU, deutsche Stimmen: Thorsten, Karlsson, Kerstin, Eva)
- Coqui XTTS-v2 (auf RunPod GPU, Voice-Cloning fähig)

Funktionen liefern mp3-Bytes zurück und passen Audio-Länge bei Bedarf an Video-Dauer an.
"""
import os
import subprocess
import tempfile
import wave
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PIPER_VOICES_DIR = Path('/var/www/workloom/video/piper_voices')

# Mapping: audio_model value -> Piper voice file
PIPER_VOICE_MAP = {
    # Single-speaker voices
    'piper-thorsten-medium': ('de_DE-thorsten-medium', None),
    'piper-thorsten-high':   ('de_DE-thorsten-high', None),
    'piper-karlsson':        ('de_DE-karlsson-low', None),
    'piper-kerstin':         ('de_DE-kerstin-low', None),
    'piper-eva':             ('de_DE-eva_k-x_low', None),
    'piper-pavoque':         ('de_DE-pavoque-low', None),
    'piper-ramona':          ('de_DE-ramona-low', None),
    # Thorsten Emotional (8 emotions)
    'piper-thorsten-amused':    ('de_DE-thorsten_emotional-medium', 0),
    'piper-thorsten-angry':     ('de_DE-thorsten_emotional-medium', 1),
    'piper-thorsten-disgusted': ('de_DE-thorsten_emotional-medium', 2),
    'piper-thorsten-drunk':     ('de_DE-thorsten_emotional-medium', 3),
    'piper-thorsten-neutral':   ('de_DE-thorsten_emotional-medium', 4),
    'piper-thorsten-sleepy':    ('de_DE-thorsten_emotional-medium', 5),
    'piper-thorsten-surprised': ('de_DE-thorsten_emotional-medium', 6),
    'piper-thorsten-whisper':   ('de_DE-thorsten_emotional-medium', 7),
    # MLS (multi-speaker, selected)
    'piper-mls-male-1':   ('de_DE-mls-medium', 0),    # Speaker 2422
    'piper-mls-male-2':   ('de_DE-mls-medium', 1),    # Speaker 4536
    'piper-mls-female-1': ('de_DE-mls-medium', 2),    # Speaker 2037
    'piper-mls-female-2': ('de_DE-mls-medium', 3),    # Speaker 9565
}

# XTTS built-in speakers — kuratiert für deutsche Aussprache (Community-Feedback)
XTTS_PRESETS = {
    # Weiblich
    'xtts-daisy':    'Daisy Studious',
    'xtts-gracie':   'Gracie Wise',
    'xtts-claribel': 'Claribel Dervla',
    'xtts-ana':      'Ana Florence',
    'xtts-tammie':   'Tammie Ema',
    'xtts-alison':   'Alison Dietlinde',
    'xtts-sofia':    'Sofia Hellen',
    # Männlich
    'xtts-baldur':   'Baldur Sanjin',
    'xtts-viktor-e': 'Viktor Eka',
    'xtts-andrew':   'Andrew Chipper',
    'xtts-damien':   'Damien Black',
    'xtts-viktor-m': 'Viktor Menelaos',
    'xtts-dionisio': 'Dionisio Schuyler',
    'xtts-craig':    'Craig Gutsy',
    # Voice-Clone
    'xtts-clone': None,
    # Legacy-Keys für Rückwärtskompatibilität
    'xtts-female-1': 'Daisy Studious',
    'xtts-female-2': 'Gracie Wise',
    'xtts-male-1':   'Baldur Sanjin',
    'xtts-male-2':   'Viktor Eka',
}


def get_audio_duration(path):
    """Return audio duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'default=nk=1:nw=1', path],
            capture_output=True, text=True, timeout=15
        )
        return float(result.stdout.strip() or 0)
    except Exception as e:
        logger.warning(f'ffprobe failed for {path}: {e}')
        return 0.0


def adjust_audio_to_duration(input_path, output_path, target_sec, max_speedup=1.5):
    """
    Passt Audio an target_sec an.
    - Wenn Audio länger als Video: ffmpeg atempo (bis max_speedup fach beschleunigen)
    - Wenn Audio kürzer: nichts tun (bleibt wie es ist)
    - Output: mp3
    """
    current = get_audio_duration(input_path)
    if current <= 0:
        # Fallback: nur konvertieren
        subprocess.run(['ffmpeg', '-y', '-i', input_path, '-codec:a', 'libmp3lame', '-b:a', '128k', output_path],
                       capture_output=True, timeout=60)
        return

    if current > target_sec:
        speedup = current / target_sec
        if speedup > max_speedup:
            # Zu viel Beschleunigung -> trim auf max
            speedup = max_speedup
        # atempo unterstützt 0.5-2.0 pro Filter, wir verketten falls nötig
        filters = []
        remaining = speedup
        while remaining > 2.0:
            filters.append('atempo=2.0')
            remaining /= 2.0
        filters.append(f'atempo={remaining:.4f}')
        filter_str = ','.join(filters)
        subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-filter:a', filter_str,
            '-codec:a', 'libmp3lame', '-b:a', '128k',
            output_path
        ], capture_output=True, timeout=120)
    else:
        subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-codec:a', 'libmp3lame', '-b:a', '128k',
            output_path
        ], capture_output=True, timeout=60)


def generate_piper(text, audio_model='piper-thorsten-medium', target_duration_sec=None):
    """Generate mp3 bytes via Piper CLI (subprocess — releases RAM after)."""
    mapping = PIPER_VOICE_MAP.get(audio_model)
    if not mapping:
        mapping = PIPER_VOICE_MAP['piper-thorsten-medium']
    voice_name, speaker_id = mapping

    model_path = PIPER_VOICES_DIR / f'{voice_name}.onnx'
    if not model_path.exists():
        raise Exception(f'Piper voice nicht gefunden: {model_path}')

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
        wav_path = tmp_wav.name
    try:
        cmd = ['/var/www/workloom/venv/bin/piper', '-m', str(model_path), '-f', wav_path]
        if speaker_id is not None:
            cmd += ['-s', str(speaker_id)]
        result = subprocess.run(
            cmd,
            input=text.encode('utf-8'),
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', 'ignore')[-500:]
            raise Exception(f'Piper CLI Fehler: {err}')

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_mp3:
            mp3_path = tmp_mp3.name
        try:
            if target_duration_sec:
                adjust_audio_to_duration(wav_path, mp3_path, target_duration_sec)
            else:
                subprocess.run([
                    'ffmpeg', '-y', '-i', wav_path,
                    '-codec:a', 'libmp3lame', '-b:a', '128k', mp3_path
                ], capture_output=True, timeout=60)

            with open(mp3_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def generate_xtts(text, audio_model='xtts-female-1', reference_audio_path=None, target_duration_sec=None, pod_id='wa18zzf5519lfj'):
    """
    Generate mp3 bytes via Coqui XTTS-v2 on RunPod.
    Pod must be running; does NOT auto-start.
    """
    from . import tasks as video_tasks

    # Get SSH port for the pod. If the pod is sleeping, auto-resume.
    # If runtime.ports is empty (pod still booting), poll for up to 90s.
    import time as _time
    try:
        import runpod
        runpod.api_key = video_tasks.RUNPOD_API_KEY
        pod = runpod.get_pod(pod_id)
        if pod.get('desiredStatus') != 'RUNNING':
            try:
                video_tasks.start_gpu_server(provider='runpod')
            except Exception as _e:
                raise Exception(f'XTTS Pod konnte nicht gestartet werden: {_e}')
            # Poll for RUNNING state
            for _ in range(30):
                _time.sleep(3)
                pod = runpod.get_pod(pod_id)
                if pod.get('desiredStatus') == 'RUNNING':
                    break
            else:
                raise Exception(f'XTTS Pod {pod_id} startet noch — bitte gleich nochmal versuchen.')

        ssh_ip = None
        ssh_port = None
        for _ in range(20):  # up to ~60s waiting for ports to populate
            rt = pod.get('runtime') or {}
            for p in rt.get('ports') or []:
                if p.get('privatePort') == 22:
                    ssh_ip = p.get('ip')
                    ssh_port = p.get('publicPort')
                    break
            if ssh_port:
                break
            _time.sleep(3)
            pod = runpod.get_pod(pod_id)
        if not ssh_port:
            raise Exception('XTTS Pod SSH-Port nicht verfügbar (Pod noch am Booten?)')
    except Exception as e:
        raise Exception(f'Pod-Info Fehler: {e}')

    # Map model to XTTS speaker
    speaker = XTTS_PRESETS.get(audio_model, 'Daisy Studious')
    use_clone = (audio_model == 'xtts-clone') and reference_audio_path

    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as tmp_txt:
        tmp_txt.write(text)
        local_txt = tmp_txt.name

    try:
        # Upload text file + optional reference audio to pod
        remote_txt = '/tmp/xtts_input.txt'
        subprocess.run([
            'scp', '-P', str(ssh_port), '-o', 'StrictHostKeyChecking=no',
            local_txt, f'root@{ssh_ip}:{remote_txt}'
        ], check=True, capture_output=True, timeout=30)

        ref_arg = ''
        if use_clone and os.path.exists(reference_audio_path):
            remote_ref = '/tmp/xtts_ref.wav'
            subprocess.run([
                'scp', '-P', str(ssh_port), '-o', 'StrictHostKeyChecking=no',
                reference_audio_path, f'root@{ssh_ip}:{remote_ref}'
            ], check=True, capture_output=True, timeout=30)
            ref_arg = f'--speaker_wav {remote_ref}'

        # Run XTTS on pod
        if use_clone:
            remote_cmd = (
                'export COQUI_TOS_AGREED=1 && export TTS_HOME=/workspace/xtts_models && source /workspace/xtts_venv/bin/activate && '
                'tts --text "$(cat /tmp/xtts_input.txt)" '
                '--model_name tts_models/multilingual/multi-dataset/xtts_v2 '
                f'{ref_arg} --language_idx de --out_path /tmp/xtts_out.wav'
            )
        else:
            remote_cmd = (
                'export COQUI_TOS_AGREED=1 && export TTS_HOME=/workspace/xtts_models && source /workspace/xtts_venv/bin/activate && '
                'tts --text "$(cat /tmp/xtts_input.txt)" '
                '--model_name tts_models/multilingual/multi-dataset/xtts_v2 '
                f'--speaker_idx "{speaker}" --language_idx de --out_path /tmp/xtts_out.wav'
            )

        result = subprocess.run([
            'ssh', '-p', str(ssh_port), '-o', 'StrictHostKeyChecking=no',
            f'root@{ssh_ip}', remote_cmd
        ], capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise Exception(f'XTTS-Fehler: {result.stderr[-500:]}')

        # Download result
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
            local_wav = tmp_wav.name
        subprocess.run([
            'scp', '-P', str(ssh_port), '-o', 'StrictHostKeyChecking=no',
            f'root@{ssh_ip}:/tmp/xtts_out.wav', local_wav
        ], check=True, capture_output=True, timeout=60)

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_mp3:
            local_mp3 = tmp_mp3.name
        try:
            if target_duration_sec:
                adjust_audio_to_duration(local_wav, local_mp3, target_duration_sec)
            else:
                subprocess.run([
                    'ffmpeg', '-y', '-i', local_wav,
                    '-codec:a', 'libmp3lame', '-b:a', '128k', local_mp3
                ], capture_output=True, timeout=60)
            with open(local_mp3, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(local_wav):
                os.remove(local_wav)
            if os.path.exists(local_mp3):
                os.remove(local_mp3)
    finally:
        if os.path.exists(local_txt):
            os.remove(local_txt)


def generate_voiceover(scene):
    """
    Zentrale Dispatch-Funktion. Gibt mp3-bytes zurück.
    Passt Länge an scene.duration an.
    """
    text = scene.voiceover_text.strip()
    if not text:
        return None

    audio_model = scene.audio_model or 'piper-thorsten-medium'
    target_sec = float(scene.duration) if scene.duration else None

    if audio_model.startswith('piper-'):
        return generate_piper(text, audio_model=audio_model, target_duration_sec=target_sec)
    elif audio_model.startswith('xtts-'):
        ref_path = None
        if scene.voice_reference_audio:
            ref_path = scene.voice_reference_audio.path
        return generate_xtts(text, audio_model=audio_model, reference_audio_path=ref_path, target_duration_sec=target_sec)
    else:
        raise Exception(f'Unbekanntes Audio-Modell: {audio_model}')


# ─────────────────────────────────────────────────
# MusicGen (on RunPod GPU via SSH)
# ─────────────────────────────────────────────────

GENRE_PROMPT_MAP = {
    'cinematic': 'cinematic film score, orchestral, emotional',
    'lofi': 'lo-fi chill hip hop beat, relaxed, warm',
    'corporate': 'upbeat corporate background music, positive, motivational',
    'epic': 'epic trailer music, powerful drums, brass, heroic',
    'ambient': 'ambient atmospheric soundscape, ethereal pads, calm',
    'happy': 'happy upbeat music, cheerful, bright',
    'sad': 'sad melancholic piano music, emotional, gentle',
    'dramatic': 'dramatic tension music, suspenseful, intense strings',
    'romantic': 'romantic gentle music, soft strings, warm piano',
    'electronic': 'electronic synth music, modern, rhythmic',
    'acoustic': 'acoustic guitar folk music, warm, natural',
    'piano': 'solo piano music, expressive, classical',
}


def generate_musicgen(prompt, duration_sec=10, genre='', pod_id='wa18zzf5519lfj'):
    """Generate music via MusicGen large on RunPod. Returns mp3 bytes."""
    from . import tasks as video_tasks
    import time as _time

    full_prompt = prompt.strip()
    if genre and genre in GENRE_PROMPT_MAP:
        full_prompt = f"{GENRE_PROMPT_MAP[genre]}, {full_prompt}" if full_prompt else GENRE_PROMPT_MAP[genre]
    if not full_prompt:
        full_prompt = 'background music, instrumental'

    duration_sec = min(max(3, duration_sec), 30)

    # Get SSH port (with retry like XTTS)
    try:
        import runpod
        runpod.api_key = video_tasks.RUNPOD_API_KEY
        pod = runpod.get_pod(pod_id)
        if pod.get('desiredStatus') != 'RUNNING':
            try:
                video_tasks.start_gpu_server(provider='runpod')
            except Exception as _e:
                raise Exception(f'MusicGen Pod konnte nicht gestartet werden: {_e}')
            for _ in range(30):
                _time.sleep(3)
                pod = runpod.get_pod(pod_id)
                if pod.get('desiredStatus') == 'RUNNING':
                    break

        ssh_ip = None
        ssh_port = None
        for _ in range(20):
            rt = pod.get('runtime') or {}
            for p in rt.get('ports') or []:
                if p.get('privatePort') == 22:
                    ssh_ip = p.get('ip')
                    ssh_port = p.get('publicPort')
                    break
            if ssh_port:
                break
            _time.sleep(3)
            pod = runpod.get_pod(pod_id)
        if not ssh_port:
            raise Exception('MusicGen Pod SSH-Port nicht verfügbar')
    except Exception as e:
        raise Exception(f'Pod-Info Fehler: {e}')

    remote_out = '/tmp/musicgen_output.wav'
    safe_prompt = full_prompt.replace("'", "'\\''")

    gen_script = f"""
source /workspace/musicgen_venv/bin/activate
export TORCH_HOME=/workspace/musicgen_models
export HF_HOME=/workspace/musicgen_models
python3 -c "
from audiocraft.models import MusicGen
import soundfile as sf
model = MusicGen.get_pretrained('facebook/musicgen-large')
model.set_generation_params(duration={duration_sec})
wav = model.generate(['{safe_prompt}'])
audio = wav[0].cpu().squeeze().numpy()
sf.write('{remote_out}', audio, 32000)
print('done')
"
"""

    try:
        result = subprocess.run([
            'ssh', '-p', str(ssh_port), '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            f'root@{ssh_ip}', gen_script.strip()
        ], capture_output=True, timeout=300)

        if result.returncode != 0:
            err = result.stderr.decode('utf-8', 'ignore')[-500:]
            raise Exception(f'MusicGen fehlgeschlagen: {err}')

        # Download result
        local_wav = tempfile.mktemp(suffix='.wav')
        subprocess.run([
            'scp', '-P', str(ssh_port), '-o', 'StrictHostKeyChecking=no',
            f'root@{ssh_ip}:{remote_out}', local_wav
        ], capture_output=True, timeout=60, check=True)

        # Convert WAV to MP3
        local_mp3 = tempfile.mktemp(suffix='.mp3')
        subprocess.run([
            'ffmpeg', '-y', '-i', local_wav,
            '-codec:a', 'libmp3lame', '-b:a', '192k', local_mp3
        ], capture_output=True, timeout=60, check=True)

        with open(local_mp3, 'rb') as f:
            mp3_bytes = f.read()

        os.remove(local_wav)
        os.remove(local_mp3)
        return mp3_bytes

    except subprocess.TimeoutExpired:
        raise Exception('MusicGen Timeout (>5 Min)')
    except Exception as e:
        raise Exception(f'MusicGen Fehler: {e}')
