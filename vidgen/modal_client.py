"""
Modal Client für VidGen - Ruft GPU-Rendering auf Modal.com auf
"""
import json
import os
import modal
from pathlib import Path


def render_on_modal(project, audio_path, clips, duration, config):
    """
    Sendet Rendering-Job an Modal und gibt fertiges Video zurück.
    """
    
    # Remotion Source-Dateien laden
    remotion_src_dir = Path(__file__).parent / 'remotion_src'
    remotion_files = {}
    
    for f in ['VidGenVideo.tsx', 'Root.tsx', 'index.ts', 'package.json', 'tsconfig.json', 'remotion.config.ts']:
        fp = remotion_src_dir / f
        if fp.exists():
            remotion_files[f] = fp.read_text()
    
    if not remotion_files:
        raise RuntimeError('Remotion Source-Dateien nicht gefunden!')
    
    # Dateien laden
    audio_data = Path(audio_path).read_bytes()
    
    # Timestamps laden
    temp_dir = os.path.dirname(audio_path)
    timestamps_path = os.path.join(temp_dir, 'timestamps.json')
    timestamps_data = Path(timestamps_path).read_bytes()
    
    # Clips laden
    clips_data = [Path(clip['path']).read_bytes() for clip in clips]
    
    # Musik laden falls vorhanden
    music_path = os.path.join('/var/www/workloom/remotion/public', 'background_music.wav')
    music_data = Path(music_path).read_bytes() if os.path.exists(music_path) else None
    
    # Overlay laden falls vorhanden
    overlay_data = None
    if project.overlay_file:
        overlay_data = project.overlay_file.read()
    
    print(f'🚀 Sende Video an Modal Cloud (GPU-Rendering)...')
    print(f'   Audio: {len(audio_data)/1024:.1f} KB')
    print(f'   Clips: {len(clips_data)}')
    print(f'   Musik: {"Ja" if music_data else "Nein"}')
    
    # Deployed Modal Function aufrufen
    render_video_gpu = modal.Function.from_name('vidgen-renderer', 'render_video_gpu')
    
    result_bytes = render_video_gpu.remote(
        config=config,
        audio_data=audio_data,
        timestamps_data=timestamps_data,
        clips_data=clips_data,
        remotion_files=remotion_files,
        music_data=music_data,
        overlay_data=overlay_data,
    )
    
    # Ergebnis speichern
    output_path = os.path.join(temp_dir, 'output.mp4')
    Path(output_path).write_bytes(result_bytes)
    
    # Modal Kosten tracken (~$0.02 pro Render)
    from decimal import Decimal
    project.cost_modal = Decimal('0.02')
    project.save(update_fields=['cost_modal'])
    
    print(f'✅ Modal Rendering fertig: {len(result_bytes)/1024/1024:.1f} MB (Kosten: $0.02)')
    
    return output_path


def check_modal_available():
    """Prüft ob Modal verfügbar ist"""
    try:
        health_check = modal.Function.from_name('vidgen-renderer', 'health_check')
        result = health_check.remote()
        return result.get('status') == 'ok'
    except Exception as e:
        print(f'Modal nicht verfügbar: {e}')
        return False
