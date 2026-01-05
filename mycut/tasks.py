# mycut/tasks.py

"""
Celery Tasks fuer MyCut Video-Editor.
Handhabt asynchrone Video-Verarbeitung und Export.
Funktioniert auch ohne Celery (synchroner Fallback).
"""

import os
import logging
import tempfile
import subprocess
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)

# Celery optional - funktioniert auch ohne
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Dummy-Decorator wenn Celery nicht installiert
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@shared_task(bind=True, max_retries=2)
def export_video(self_or_project_id, project_id_or_job_id: int = None, export_job_id: int = None) -> dict:
    """
    Celery Task: Exportiert ein bearbeitetes Video.
    Funktioniert mit Celery (self, project_id, job_id) oder direkt (project_id, job_id).

    Workflow:
    1. Timeline-Clips laden und sortieren
    2. Video-Segmente extrahieren (mit Trims)
    3. Text-Overlays und Untertitel anwenden
    4. Segmente zusammenfuegen
    5. Ausgabe komprimieren
    6. Ergebnis speichern

    Args:
        project_id: ID des EditProject
        export_job_id: ID des ExportJob

    Returns:
        dict mit status und output_path
    """
    # Handle beide Aufruf-Konventionen: Celery (self, proj, job) vs direkt (proj, job)
    if CELERY_AVAILABLE and hasattr(self_or_project_id, 'request'):
        # Celery-Aufruf: self ist Task-Objekt
        project_id = project_id_or_job_id
        # export_job_id kommt vom Parameter
    else:
        # Direkter Aufruf: self_or_project_id ist project_id
        project_id = self_or_project_id
        export_job_id = project_id_or_job_id

    from .models import EditProject, ExportJob, TimelineClip
    from .services.ffmpeg_service import FFmpegService, has_ffmpeg

    # Export-Job laden
    try:
        export_job = ExportJob.objects.get(id=export_job_id)
        project = EditProject.objects.get(id=project_id)
    except (ExportJob.DoesNotExist, EditProject.DoesNotExist) as e:
        logger.error(f"Export job or project not found: {e}")
        return {'status': 'failed', 'error': str(e)}

    # FFmpeg pruefen
    if not has_ffmpeg():
        export_job.fail("FFmpeg ist nicht installiert")
        return {'status': 'failed', 'error': 'FFmpeg not available'}

    # Progress-Update-Helper
    def update_progress(percent: int, message: str = ''):
        export_job.progress = percent
        export_job.save(update_fields=['progress'])
        project.processing_progress = percent
        project.processing_message = message
        project.save(update_fields=['processing_progress', 'processing_message'])
        logger.info(f"Export progress: {percent}% - {message}")

    try:
        update_progress(5, 'Export wird vorbereitet...')

        # Export-Settings laden
        export_settings = export_job.export_settings
        quality = export_settings.get('quality', project.export_quality)
        output_format = export_settings.get('format', project.export_format)
        burn_subtitles = export_settings.get('burn_subtitles', False)

        # Source-Video Pfad
        source_path = project.source_video.video_file.path
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Quell-Video nicht gefunden: {source_path}")

        # Temporaerer Ordner fuer Zwischendateien
        with tempfile.TemporaryDirectory(prefix='mycut_export_') as temp_dir:

            # Video-Info holen
            video_info = FFmpegService.get_video_info(source_path)
            total_duration = video_info.get('duration', 0) * 1000  # in ms

            update_progress(10, 'Timeline wird analysiert...')

            # Timeline-Clips laden (nur Video-Clips)
            clips = list(project.clips.filter(
                clip_type='video',
                is_hidden=False
            ).order_by('start_time'))

            # Falls keine Clips, komplettes Video exportieren
            if not clips:
                clips = [{
                    'source_start': 0,
                    'source_end': total_duration,
                    'speed': 1.0,
                    'is_muted': False,
                    'volume': 1.0,
                }]
            else:
                clips = []
                for c in project.clips.filter(clip_type='video', is_hidden=False).order_by('start_time'):
                    source_start = c.source_start or 0
                    source_end = c.source_end if c.source_end > 0 else c.duration
                    # Falls source_end immer noch 0, ueberspringe
                    if source_end <= source_start:
                        source_end = source_start + (c.duration or total_duration)
                    clips.append({
                        'source_start': source_start,
                        'source_end': source_end,
                        'speed': c.speed or 1.0,
                        'is_muted': c.is_muted,
                        'volume': c.volume or 1.0,
                    })

            # Falls keine gueltigen Clips, komplettes Video
            if not clips:
                clips = [{
                    'source_start': 0,
                    'source_end': total_duration,
                    'speed': 1.0,
                    'is_muted': False,
                    'volume': 1.0,
                }]

            update_progress(15, f'{len(clips)} Clip(s) werden verarbeitet...')

            # Segmente extrahieren
            segment_paths = []
            for i, clip in enumerate(clips):
                progress = 15 + int((i / len(clips)) * 40)
                update_progress(progress, f'Segment {i+1}/{len(clips)} wird verarbeitet...')

                segment_path = os.path.join(temp_dir, f'segment_{i:04d}.mp4')

                # Segment trimmen
                _extract_segment(
                    source_path,
                    segment_path,
                    clip['source_start'],
                    clip['source_end'],
                    clip['speed'],
                    clip['is_muted'],
                    clip['volume']
                )

                if os.path.exists(segment_path):
                    segment_paths.append(segment_path)

            if not segment_paths:
                raise RuntimeError("Keine Segmente konnten extrahiert werden")

            update_progress(55, 'Segmente werden zusammengefuegt...')

            # Segmente zusammenfuegen
            if len(segment_paths) == 1:
                merged_path = segment_paths[0]
            else:
                merged_path = os.path.join(temp_dir, 'merged.mp4')
                _concat_segments(segment_paths, merged_path)

            update_progress(65, 'Overlays werden angewendet...')

            # Text-Overlays anwenden
            overlay_path = merged_path
            text_overlays = list(project.text_overlays.all())

            if text_overlays:
                overlay_path = os.path.join(temp_dir, 'with_overlays.mp4')
                _apply_text_overlays(merged_path, overlay_path, text_overlays)

            update_progress(75, 'Untertitel werden verarbeitet...')

            # Untertitel einbrennen (falls aktiviert)
            subtitle_path = overlay_path
            if burn_subtitles:
                subtitles = list(project.subtitles.all())
                if subtitles:
                    # SRT erstellen
                    srt_path = os.path.join(temp_dir, 'subtitles.srt')
                    _create_srt_file(subtitles, srt_path)

                    subtitle_path = os.path.join(temp_dir, 'with_subtitles.mp4')
                    FFmpegService.burn_subtitles(overlay_path, subtitle_path, srt_path)

            update_progress(85, f'Video wird komprimiert ({quality})...')

            # Finale Komprimierung
            output_filename = f"{project.unique_id}_{quality}.{output_format}"
            final_path = os.path.join(temp_dir, output_filename)

            FFmpegService.compress_video(subtitle_path, final_path, quality)

            if not os.path.exists(final_path):
                raise RuntimeError("Finale Datei konnte nicht erstellt werden")

            update_progress(95, 'Export wird gespeichert...')

            # Dateigröße ermitteln
            file_size = os.path.getsize(final_path)

            # Datei in Django FileField speichern
            with open(final_path, 'rb') as f:
                export_job.output_file.save(
                    output_filename,
                    ContentFile(f.read()),
                    save=False
                )

            # Job als abgeschlossen markieren
            export_job.status = 'completed'
            export_job.completed_at = timezone.now()
            export_job.file_size = file_size
            export_job.progress = 100
            export_job.save()

            # Projekt-Status aktualisieren
            project.status = 'completed'
            project.processing_progress = 100
            project.processing_message = 'Export abgeschlossen!'
            project.save(update_fields=['status', 'processing_progress', 'processing_message'])

            logger.info(f"Export completed: {export_job.output_file.url}")

            return {
                'status': 'completed',
                'output_url': export_job.output_file.url,
                'file_size': file_size,
            }

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        export_job.fail(str(e))
        project.status = 'error'
        project.processing_message = f'Fehler: {str(e)}'
        project.save(update_fields=['status', 'processing_message'])

        # Retry bei bestimmten Fehlern
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)

        return {'status': 'failed', 'error': str(e)}


def _extract_segment(
    source_path: str,
    output_path: str,
    start_ms: float,
    end_ms: float,
    speed: float = 1.0,
    is_muted: bool = False,
    volume: float = 1.0
) -> bool:
    """
    Extrahiert ein Video-Segment mit optionalen Modifikationen.
    """
    start_sec = start_ms / 1000
    duration_sec = (end_ms - start_ms) / 1000

    # Validierung
    if duration_sec <= 0:
        logger.error(f"Invalid segment duration: {duration_sec}s (start={start_ms}ms, end={end_ms}ms)")
        return False

    logger.info(f"Extracting segment: {start_sec}s - {end_ms/1000}s (duration={duration_sec}s)")

    # Filter bauen
    video_filters = []
    audio_filters = []

    # Speed-Aenderung
    if speed != 1.0 and 0.5 <= speed <= 4.0:
        video_filters.append(f"setpts={1/speed}*PTS")

        # Audio-Tempo (0.5-2.0 Range)
        remaining = speed
        tempo_filters = []
        while remaining > 2.0:
            tempo_filters.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5:
            tempo_filters.append("atempo=0.5")
            remaining *= 2.0
        tempo_filters.append(f"atempo={remaining}")
        audio_filters.extend(tempo_filters)

    # Lautstaerke
    if volume != 1.0:
        audio_filters.append(f"volume={volume}")

    try:
        if is_muted:
            # Nur Video, kein Audio
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_sec),
                '-i', source_path,
                '-t', str(duration_sec),
                '-an',  # Kein Audio
                '-c:v', 'libx264', '-preset', 'fast',
            ]
            if video_filters:
                cmd.extend(['-vf', ','.join(video_filters)])
            cmd.append(output_path)
        else:
            # Video und Audio
            cmd = ['ffmpeg', '-y', '-ss', str(start_sec), '-i', source_path, '-t', str(duration_sec)]

            if video_filters or audio_filters:
                # Filter anwenden - muss re-encoden
                filter_complex = []
                if video_filters:
                    filter_complex.append(f"[0:v]{','.join(video_filters)}[v]")
                if audio_filters:
                    filter_complex.append(f"[0:a]{','.join(audio_filters)}[a]")

                cmd.extend(['-filter_complex', ';'.join(filter_complex)])

                if video_filters:
                    cmd.extend(['-map', '[v]'])
                else:
                    cmd.extend(['-map', '0:v'])

                if audio_filters:
                    cmd.extend(['-map', '[a]'])
                else:
                    cmd.extend(['-map', '0:a'])

                # Re-Encoding nur wenn Filter aktiv
                cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac', output_path])
            else:
                # SCHNELL: Keine Filter -> Stream Copy (10x schneller!)
                cmd.extend(['-c', 'copy', output_path])

        # Timeout: 5 Minuten pro Segment
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            # Fallback: Einfaches Kopieren ohne Filter
            cmd_simple = [
                'ffmpeg', '-y',
                '-ss', str(start_sec),
                '-i', source_path,
                '-t', str(duration_sec),
                '-c', 'copy',
                output_path
            ]
            subprocess.run(cmd_simple, capture_output=True, check=True, timeout=300)

        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Segment extraction timed out after 5 minutes")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Segment extraction failed: {e}")
        return False


def _concat_segments(segment_paths: list, output_path: str) -> bool:
    """
    Fuegt mehrere Video-Segmente zusammen.
    """
    try:
        # Concat-Datei erstellen
        concat_file = output_path + '.txt'
        with open(concat_file, 'w') as f:
            for path in segment_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Concat-Datei loeschen
        if os.path.exists(concat_file):
            os.unlink(concat_file)

        if result.returncode != 0:
            logger.error(f"Concat error: {result.stderr}")
            # Fallback: Re-encode
            cmd_reencode = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.replace('.txt', '_list.txt'),
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'aac',
                output_path
            ]
            # Neue Concat-Datei erstellen
            with open(concat_file.replace('.txt', '_list.txt'), 'w') as f:
                for path in segment_paths:
                    f.write(f"file '{path}'\n")
            subprocess.run(cmd_reencode, capture_output=True, check=True)

        return True

    except Exception as e:
        logger.error(f"Concat failed: {e}")
        return False


def _apply_text_overlays(input_path: str, output_path: str, overlays: list) -> bool:
    """
    Wendet Text-Overlays auf ein Video an.
    """
    if not overlays:
        return False

    try:
        # Drawtext-Filter fuer alle Overlays bauen
        drawtext_filters = []

        for overlay in overlays:
            # Text escapen
            text = str(overlay.text).replace("'", "\\'").replace(":", "\\:")

            # Position berechnen (% zu Pixel)
            # W = Video-Breite, H = Video-Hoehe
            x_pos = f"(W*{overlay.position_x/100})"
            y_pos = f"(H*{overlay.position_y/100})"

            # Style extrahieren
            style = overlay.style or {}
            font_size = style.get('size', 48)
            font_color = style.get('color', '#FFFFFF').replace('#', '0x')

            # Zeitbereich (ms zu s)
            start_sec = overlay.start_time / 1000
            end_sec = overlay.end_time / 1000

            # Drawtext-Filter
            dt = (
                f"drawtext=text='{text}'"
                f":x={x_pos}-tw/2"  # Zentriert
                f":y={y_pos}-th/2"
                f":fontsize={font_size}"
                f":fontcolor={font_color}"
                f":enable='between(t,{start_sec},{end_sec})'"
            )

            # Shadow hinzufuegen wenn aktiviert
            if style.get('shadow', True):
                dt += ":shadowcolor=black:shadowx=2:shadowy=2"

            drawtext_filters.append(dt)

        # Alle Filter kombinieren
        vf = ','.join(drawtext_filters)

        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"Text overlay warning: {result.stderr}")
            # Bei Fehler: Ohne Overlays kopieren
            import shutil
            shutil.copy(input_path, output_path)

        return True

    except Exception as e:
        logger.error(f"Text overlay failed: {e}")
        return False


def _create_srt_file(subtitles: list, output_path: str) -> bool:
    """
    Erstellt eine SRT-Datei aus Subtitle-Objekten.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitles, 1):
                start = _ms_to_srt_time(sub.start_time)
                end = _ms_to_srt_time(sub.end_time)
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{sub.text}\n\n")
        return True
    except Exception as e:
        logger.error(f"SRT creation failed: {e}")
        return False


def _ms_to_srt_time(ms: float) -> str:
    """Konvertiert Millisekunden zu SRT-Zeitformat (00:00:00,000)."""
    hours = int(ms // 3600000)
    minutes = int((ms % 3600000) // 60000)
    seconds = int((ms % 60000) // 1000)
    millis = int(ms % 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


@shared_task
def cleanup_old_exports(days: int = 7):
    """
    Bereinigt alte Export-Jobs und deren Dateien.
    Sollte periodisch via Celery Beat ausgefuehrt werden.
    """
    from .models import ExportJob
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)

    old_jobs = ExportJob.objects.filter(
        created_at__lt=cutoff,
        status__in=['completed', 'failed']
    )

    deleted_count = 0
    for job in old_jobs:
        # Datei loeschen falls vorhanden
        if job.output_file:
            try:
                job.output_file.delete(save=False)
            except Exception as e:
                logger.warning(f"Could not delete export file: {e}")

        job.delete()
        deleted_count += 1

    logger.info(f"Cleaned up {deleted_count} old export jobs")
    return {'deleted': deleted_count}


# =============================================================================
# CHUNKED EXPORT - Verarbeitet einen Schritt pro API-Aufruf
# =============================================================================

def export_step(project_id: int, export_job_id: int) -> dict:
    """
    Verarbeitet EINEN Schritt des Exports.
    Wird vom Client wiederholt aufgerufen bis fertig.

    Schritte:
    1. init - Vorbereitung, Clips laden
    2. segment_N - Jedes Segment einzeln extrahieren
    3. concat - Segmente zusammenfuegen
    4. overlays - Text-Overlays anwenden
    5. subtitles - Untertitel einbrennen
    6. compress - Finale Komprimierung
    7. save - Datei speichern

    Returns:
        dict mit:
        - status: 'processing', 'completed', 'failed'
        - progress: 0-100
        - next_step: Naechster Schritt (oder None wenn fertig)
        - message: Status-Nachricht
    """
    from .models import EditProject, ExportJob
    from .services.ffmpeg_service import FFmpegService, has_ffmpeg
    import shutil

    try:
        export_job = ExportJob.objects.get(id=export_job_id)
        project = EditProject.objects.get(id=project_id)
    except (ExportJob.DoesNotExist, EditProject.DoesNotExist) as e:
        logger.error(f"Export job or project not found: {e}")
        return {'status': 'failed', 'error': str(e), 'progress': 0}

    # State aus export_settings laden
    state = export_job.export_settings.copy()
    current_step = state.get('current_step', 'init')

    # Persistenter Temp-Ordner (ueberlebt Request-Grenzen)
    temp_dir = f"/tmp/mycut_export_{export_job_id}"
    os.makedirs(temp_dir, exist_ok=True)

    def update_state(new_state: dict):
        """Speichert State in DB."""
        export_job.export_settings.update(new_state)
        export_job.save(update_fields=['export_settings'])

    def update_progress(percent: int, message: str = ''):
        """Aktualisiert Fortschritt."""
        export_job.progress = percent
        export_job.save(update_fields=['progress'])
        project.processing_progress = percent
        project.processing_message = message
        project.save(update_fields=['processing_progress', 'processing_message'])

    try:
        # =====================================================
        # STEP: INIT
        # =====================================================
        if current_step == 'init':
            if not has_ffmpeg():
                export_job.fail("FFmpeg ist nicht installiert")
                return {'status': 'failed', 'error': 'FFmpeg not available', 'progress': 0}

            # Source-Video pruefen
            source_path = project.source_video.video_file.path
            if not os.path.exists(source_path):
                export_job.fail(f"Quell-Video nicht gefunden: {source_path}")
                return {'status': 'failed', 'error': 'Source video not found', 'progress': 0}

            # Video-Info holen
            video_info = FFmpegService.get_video_info(source_path)
            total_duration = video_info.get('duration', 0) * 1000

            # Clips laden
            clips_data = []
            db_clips = list(project.clips.filter(
                clip_type='video',
                is_hidden=False
            ).order_by('start_time'))

            if not db_clips:
                # Komplettes Video als ein Clip
                clips_data.append({
                    'source_start': 0,
                    'source_end': total_duration,
                    'speed': 1.0,
                    'is_muted': False,
                    'volume': 1.0,
                })
            else:
                for c in db_clips:
                    source_start = c.source_start or 0
                    source_end = c.source_end if c.source_end > 0 else c.duration
                    if source_end <= source_start:
                        source_end = source_start + (c.duration or total_duration)
                    clips_data.append({
                        'source_start': source_start,
                        'source_end': source_end,
                        'speed': c.speed or 1.0,
                        'is_muted': c.is_muted,
                        'volume': c.volume or 1.0,
                    })

            # State speichern
            update_state({
                'current_step': 'segment_0',
                'clips': clips_data,
                'total_clips': len(clips_data),
                'segment_paths': [],
                'source_path': source_path,
                'temp_dir': temp_dir,
            })
            update_progress(5, 'Export vorbereitet...')

            return {
                'status': 'processing',
                'progress': 5,
                'next_step': 'segment_0',
                'message': f'{len(clips_data)} Clip(s) werden verarbeitet...',
                'total_steps': len(clips_data) + 5,  # segments + concat + overlays + subtitles + compress + save
            }

        # =====================================================
        # STEP: SEGMENT_N - Einzelnes Segment extrahieren
        # =====================================================
        if current_step.startswith('segment_'):
            segment_idx = int(current_step.split('_')[1])
            clips = state.get('clips', [])
            source_path = state.get('source_path')
            segment_paths = state.get('segment_paths', [])

            if segment_idx >= len(clips):
                # Alle Segmente fertig -> weiter zu concat
                update_state({'current_step': 'concat'})
                return {
                    'status': 'processing',
                    'progress': 55,
                    'next_step': 'concat',
                    'message': 'Segmente werden zusammengefuegt...',
                }

            clip = clips[segment_idx]
            segment_path = os.path.join(temp_dir, f'segment_{segment_idx:04d}.mp4')

            # Segment extrahieren
            success = _extract_segment(
                source_path,
                segment_path,
                clip['source_start'],
                clip['source_end'],
                clip['speed'],
                clip['is_muted'],
                clip['volume']
            )

            if success and os.path.exists(segment_path):
                segment_paths.append(segment_path)

            # Progress berechnen (Segmente = 5-55%)
            progress = 5 + int((segment_idx + 1) / len(clips) * 50)
            next_step = f'segment_{segment_idx + 1}'

            update_state({
                'current_step': next_step,
                'segment_paths': segment_paths,
            })
            update_progress(progress, f'Segment {segment_idx + 1}/{len(clips)} verarbeitet...')

            return {
                'status': 'processing',
                'progress': progress,
                'next_step': next_step,
                'message': f'Segment {segment_idx + 1}/{len(clips)} verarbeitet',
            }

        # =====================================================
        # STEP: CONCAT - Segmente zusammenfuegen
        # =====================================================
        if current_step == 'concat':
            segment_paths = state.get('segment_paths', [])

            if not segment_paths:
                export_job.fail("Keine Segmente konnten extrahiert werden")
                return {'status': 'failed', 'error': 'No segments', 'progress': 55}

            if len(segment_paths) == 1:
                merged_path = segment_paths[0]
            else:
                merged_path = os.path.join(temp_dir, 'merged.mp4')
                _concat_segments(segment_paths, merged_path)

            update_state({
                'current_step': 'overlays',
                'merged_path': merged_path,
            })
            update_progress(65, 'Overlays werden angewendet...')

            return {
                'status': 'processing',
                'progress': 65,
                'next_step': 'overlays',
                'message': 'Segmente zusammengefuegt',
            }

        # =====================================================
        # STEP: OVERLAYS - Text-Overlays anwenden
        # =====================================================
        if current_step == 'overlays':
            merged_path = state.get('merged_path')
            text_overlays = list(project.text_overlays.all())

            if text_overlays:
                overlay_path = os.path.join(temp_dir, 'with_overlays.mp4')
                _apply_text_overlays(merged_path, overlay_path, text_overlays)
                if os.path.exists(overlay_path):
                    merged_path = overlay_path

            update_state({
                'current_step': 'subtitles',
                'overlay_path': merged_path,
            })
            update_progress(75, 'Untertitel werden verarbeitet...')

            return {
                'status': 'processing',
                'progress': 75,
                'next_step': 'subtitles',
                'message': 'Overlays angewendet',
            }

        # =====================================================
        # STEP: SUBTITLES - Untertitel einbrennen
        # =====================================================
        if current_step == 'subtitles':
            overlay_path = state.get('overlay_path')
            burn_subtitles = state.get('burn_subtitles', False)

            subtitle_path = overlay_path
            if burn_subtitles:
                subtitles = list(project.subtitles.all())
                if subtitles:
                    srt_path = os.path.join(temp_dir, 'subtitles.srt')
                    _create_srt_file(subtitles, srt_path)

                    subtitle_path = os.path.join(temp_dir, 'with_subtitles.mp4')
                    FFmpegService.burn_subtitles(overlay_path, subtitle_path, srt_path)

            update_state({
                'current_step': 'compress',
                'subtitle_path': subtitle_path,
            })
            update_progress(85, 'Video wird komprimiert...')

            return {
                'status': 'processing',
                'progress': 85,
                'next_step': 'compress',
                'message': 'Untertitel verarbeitet',
            }

        # =====================================================
        # STEP: COMPRESS - Finale Komprimierung
        # =====================================================
        if current_step == 'compress':
            subtitle_path = state.get('subtitle_path')
            quality = state.get('quality', project.export_quality)
            output_format = state.get('format', project.export_format)

            output_filename = f"{project.unique_id}_{quality}.{output_format}"
            final_path = os.path.join(temp_dir, output_filename)

            FFmpegService.compress_video(subtitle_path, final_path, quality)

            if not os.path.exists(final_path):
                export_job.fail("Finale Datei konnte nicht erstellt werden")
                return {'status': 'failed', 'error': 'Compression failed', 'progress': 85}

            update_state({
                'current_step': 'save',
                'final_path': final_path,
                'output_filename': output_filename,
            })
            update_progress(95, 'Export wird gespeichert...')

            return {
                'status': 'processing',
                'progress': 95,
                'next_step': 'save',
                'message': 'Video komprimiert',
            }

        # =====================================================
        # STEP: SAVE - Datei speichern und aufraumen
        # =====================================================
        if current_step == 'save':
            final_path = state.get('final_path')
            output_filename = state.get('output_filename')

            # Dateigroesse ermitteln
            file_size = os.path.getsize(final_path)

            # Datei in Django FileField speichern
            from django.core.files.base import ContentFile
            with open(final_path, 'rb') as f:
                export_job.output_file.save(
                    output_filename,
                    ContentFile(f.read()),
                    save=False
                )

            # Job als abgeschlossen markieren
            export_job.status = 'completed'
            export_job.completed_at = timezone.now()
            export_job.file_size = file_size
            export_job.progress = 100
            export_job.save()

            # Projekt-Status aktualisieren
            project.status = 'completed'
            project.processing_progress = 100
            project.processing_message = 'Export abgeschlossen!'
            project.save(update_fields=['status', 'processing_progress', 'processing_message'])

            # Temp-Ordner aufraumen
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Could not cleanup temp dir: {e}")

            logger.info(f"Chunked export completed: {export_job.output_file.url}")

            return {
                'status': 'completed',
                'progress': 100,
                'next_step': None,
                'message': 'Export abgeschlossen!',
                'output_url': export_job.output_file.url,
                'file_size': file_size,
            }

        # Unbekannter Step
        return {'status': 'failed', 'error': f'Unknown step: {current_step}', 'progress': 0}

    except Exception as e:
        logger.error(f"Export step failed: {e}", exc_info=True)
        export_job.fail(str(e))
        project.status = 'error'
        project.processing_message = f'Fehler: {str(e)}'
        project.save(update_fields=['status', 'processing_message'])

        # Temp-Ordner aufraumen bei Fehler
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass

        return {'status': 'failed', 'error': str(e), 'progress': export_job.progress}
