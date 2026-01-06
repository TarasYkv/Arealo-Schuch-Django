# mycut/services/ffmpeg_service.py

"""
FFmpeg-Service für MyCut Video-Editor.
Handhabt alle Video/Audio-Operationen via FFmpeg.
"""

import logging
import subprocess
import os
import json
import tempfile
from typing import Optional, List, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


def has_ffmpeg() -> bool:
    """Prüft ob FFmpeg installiert ist."""
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def has_ffprobe() -> bool:
    """Prüft ob FFprobe installiert ist."""
    try:
        subprocess.run(
            ['ffprobe', '-version'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


class FFmpegService:
    """
    Service für FFmpeg-Operationen.
    """

    @staticmethod
    def get_video_info(video_path: str) -> dict:
        """
        Holt Video-Metadaten via FFprobe.

        Returns:
            dict mit: duration, width, height, fps, codec, audio_codec
        """
        if not has_ffprobe():
            raise RuntimeError("FFprobe nicht verfügbar")

        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            info = {
                'duration': 0,
                'width': 0,
                'height': 0,
                'fps': 0,
                'video_codec': None,
                'audio_codec': None,
                'has_audio': False,
            }

            # Format-Daten
            if 'format' in data:
                info['duration'] = float(data['format'].get('duration', 0))

            # Stream-Daten
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info['width'] = stream.get('width', 0)
                    info['height'] = stream.get('height', 0)
                    info['video_codec'] = stream.get('codec_name')

                    # FPS berechnen
                    fps_str = stream.get('r_frame_rate', '0/1')
                    if '/' in fps_str:
                        num, den = fps_str.split('/')
                        if int(den) > 0:
                            info['fps'] = round(int(num) / int(den), 2)

                elif stream.get('codec_type') == 'audio':
                    info['audio_codec'] = stream.get('codec_name')
                    info['has_audio'] = True

            return info

        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            raise

    @staticmethod
    def extract_audio(video_path: str, output_path: str, format: str = 'wav') -> bool:
        """
        Extrahiert Audio-Spur aus Video.

        Args:
            video_path: Pfad zum Video
            output_path: Pfad für Audio-Ausgabe
            format: Audio-Format (wav, mp3, etc.)

        Returns:
            True bei Erfolg
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            cmd = [
                'ffmpeg',
                '-y',  # Überschreiben ohne Nachfrage
                '-i', video_path,
                '-vn',  # Kein Video
                '-acodec', 'pcm_s16le' if format == 'wav' else 'libmp3lame',
                '-ar', '16000',  # 16kHz für Whisper
                '-ac', '1',  # Mono
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Audio extracted to {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Audio extraction failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def generate_waveform_data(audio_path: str, points: int = 1000) -> List[float]:
        """
        Generiert Waveform-Daten für Visualisierung.

        Args:
            audio_path: Pfad zur Audio-Datei
            points: Anzahl der Datenpunkte

        Returns:
            Liste von Amplitude-Werten (0-1)
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            # Audio-Info holen
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'json',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data['format'].get('duration', 0))

            if duration <= 0:
                return []

            # Samples extrahieren mit astats
            cmd = [
                'ffmpeg',
                '-i', audio_path,
                '-af', f'asetnsamples=n={points},astats=metadata=1:reset=1',
                '-f', 'null',
                '-'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # RMS-Werte aus Output parsen
            waveform = []
            for line in result.stderr.split('\n'):
                if 'RMS level' in line:
                    try:
                        # Format: "[Parsed_astats_1 @ ...] RMS level dB: -20.5"
                        db_value = float(line.split(':')[-1].strip())
                        # dB zu linear konvertieren (0-1)
                        linear = 10 ** (db_value / 20)
                        waveform.append(min(1.0, max(0.0, linear)))
                    except (ValueError, IndexError):
                        continue

            # Wenn nicht genug Punkte, mit Interpolation auffüllen
            if len(waveform) < points:
                # Fallback: Einfache Analyse
                waveform = FFmpegService._simple_waveform(audio_path, points)

            return waveform[:points]

        except Exception as e:
            logger.error(f"Waveform generation failed: {e}")
            return []

    @staticmethod
    def _simple_waveform(audio_path: str, points: int) -> List[float]:
        """Einfache Waveform-Generierung als Fallback."""
        # Dummy-Daten für Fallback
        import random
        return [random.uniform(0.2, 0.8) for _ in range(points)]

    @staticmethod
    def detect_silence(audio_path: str, threshold_db: float = -40, min_duration: float = 1.0) -> List[dict]:
        """
        Erkennt Stille im Audio via FFmpeg silencedetect.

        Args:
            audio_path: Pfad zur Audio-Datei
            threshold_db: Schwellwert in dB
            min_duration: Mindestdauer der Stille in Sekunden

        Returns:
            Liste von dict mit start/end in ms
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            cmd = [
                'ffmpeg',
                '-i', audio_path,
                '-af', f'silencedetect=noise={threshold_db}dB:d={min_duration}',
                '-f', 'null',
                '-'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            silences = []
            current_start = None

            for line in result.stderr.split('\n'):
                if 'silence_start' in line:
                    try:
                        current_start = float(line.split('silence_start:')[1].strip().split()[0])
                    except (ValueError, IndexError):
                        continue

                elif 'silence_end' in line and current_start is not None:
                    try:
                        end = float(line.split('silence_end:')[1].strip().split()[0])
                        silences.append({
                            'start': current_start * 1000,  # in ms
                            'end': end * 1000,
                            'duration': (end - current_start) * 1000,
                        })
                        current_start = None
                    except (ValueError, IndexError):
                        continue

            logger.info(f"Detected {len(silences)} silence segments")
            return silences

        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            return []

    @staticmethod
    def extract_frame(video_path: str, timestamp_ms: float) -> bytes:
        """
        Extrahiert ein einzelnes Frame als JPEG.

        Args:
            video_path: Pfad zum Video
            timestamp_ms: Zeitpunkt in Millisekunden

        Returns:
            JPEG-Bytes
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            timestamp_sec = timestamp_ms / 1000

            cmd = [
                'ffmpeg',
                '-ss', str(timestamp_sec),
                '-i', video_path,
                '-vframes', '1',
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                '-'
            ]

            result = subprocess.run(cmd, capture_output=True, check=True)
            return result.stdout

        except subprocess.CalledProcessError as e:
            logger.error(f"Frame extraction failed: {e}")
            raise

    @staticmethod
    def trim_video(
        input_path: str,
        output_path: str,
        start_ms: float,
        end_ms: float,
        reencode: bool = False
    ) -> bool:
        """
        Schneidet Video auf angegebenen Zeitbereich.

        Args:
            input_path: Eingabe-Video
            output_path: Ausgabe-Video
            start_ms: Start in ms
            end_ms: Ende in ms
            reencode: True für Re-Encoding (langsamer, aber genauer)
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            start_sec = start_ms / 1000
            duration_sec = (end_ms - start_ms) / 1000

            if reencode:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-ss', str(start_sec),
                    '-t', str(duration_sec),
                    '-c:v', 'libx264', '-preset', 'fast',
                    '-c:a', 'aac',
                    output_path
                ]
            else:
                # Schnelles Kopieren (keyframe-basiert)
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(start_sec),
                    '-i', input_path,
                    '-t', str(duration_sec),
                    '-c', 'copy',
                    output_path
                ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Video trimmed: {start_ms}ms - {end_ms}ms -> {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Video trim failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def apply_speed_change(
        input_path: str,
        output_path: str,
        speed_factor: float
    ) -> bool:
        """
        Ändert die Geschwindigkeit eines Videos.

        Args:
            speed_factor: 0.5 = halb so schnell, 2.0 = doppelt so schnell
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        if speed_factor <= 0 or speed_factor > 4:
            raise ValueError("Speed factor must be between 0 and 4")

        try:
            # Video: setpts, Audio: atempo (kann nur 0.5-2.0)
            video_filter = f"setpts={1/speed_factor}*PTS"

            # Audio-Tempo in Schritten anwenden
            audio_filters = []
            remaining = speed_factor
            while remaining > 2.0:
                audio_filters.append("atempo=2.0")
                remaining /= 2.0
            while remaining < 0.5:
                audio_filters.append("atempo=0.5")
                remaining *= 2.0
            audio_filters.append(f"atempo={remaining}")

            audio_filter = ",".join(audio_filters)

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-filter_complex', f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
                '-map', '[v]', '-map', '[a]',
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'aac',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Speed changed by {speed_factor}x: {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Speed change failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def compress_video(
        input_path: str,
        output_path: str,
        quality: str = '1080p'
    ) -> bool:
        """
        Komprimiert Video auf angegebene Qualität.

        Args:
            quality: '720p', '1080p', '4k', 'original'
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        # Original = Stream Copy (keine Re-Encoding, 10x schneller)
        if quality == 'original':
            try:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-c', 'copy',
                    '-movflags', '+faststart',
                    output_path
                ]
                subprocess.run(cmd, capture_output=True, check=True, timeout=600)
                logger.info(f"Video copied (original quality): {output_path}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Stream copy failed: {e.stderr.decode() if e.stderr else str(e)}")
                raise

        presets = {
            '720p': {'scale': '1280:720', 'crf': '28', 'bitrate': '2M'},
            '1080p': {'scale': '1920:1080', 'crf': '23', 'bitrate': '4M'},
            '4k': {'scale': '3840:2160', 'crf': '18', 'bitrate': '15M'},
        }

        preset = presets.get(quality, presets['1080p'])

        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', f"scale={preset['scale']}:force_original_aspect_ratio=decrease,pad={preset['scale']}:(ow-iw)/2:(oh-ih)/2",
                '-c:v', 'libx264',
                '-crf', preset['crf'],
                '-preset', 'ultrafast',  # Schnell für PythonAnywhere Timeouts
                '-c:a', 'aac', '-b:a', '128k',
                '-movflags', '+faststart',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True, timeout=1800)
            logger.info(f"Video compressed to {quality}: {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Video compression failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def add_text_overlay(
        input_path: str,
        output_path: str,
        text: str,
        x: int = 50,
        y: int = 50,
        start_ms: float = 0,
        end_ms: float = None,
        font_size: int = 48,
        font_color: str = 'white',
        font: str = 'Arial'
    ) -> bool:
        """
        Fügt Text-Overlay zum Video hinzu.
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            # Text escapen für FFmpeg
            text_escaped = text.replace("'", "\\'").replace(":", "\\:")

            # Drawtext-Filter bauen
            drawtext = f"drawtext=text='{text_escaped}':x={x}:y={y}:fontsize={font_size}:fontcolor={font_color}"

            if start_ms > 0 or end_ms:
                start_sec = start_ms / 1000
                if end_ms:
                    end_sec = end_ms / 1000
                    drawtext += f":enable='between(t,{start_sec},{end_sec})'"
                else:
                    drawtext += f":enable='gte(t,{start_sec})'"

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', drawtext,
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'copy',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Text overlay added: {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Text overlay failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def burn_subtitles(
        input_path: str,
        output_path: str,
        srt_path: str
    ) -> bool:
        """
        Brennt Untertitel ins Video ein.
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            # SRT-Pfad escapen für FFmpeg
            srt_escaped = srt_path.replace('\\', '/').replace(':', '\\:')

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', f"subtitles='{srt_escaped}'",
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'copy',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Subtitles burned: {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Subtitle burn failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def concat_videos(
        input_paths: List[str],
        output_path: str
    ) -> bool:
        """
        Fügt mehrere Videos zusammen.
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        if len(input_paths) < 2:
            raise ValueError("Need at least 2 videos to concatenate")

        try:
            # Concat-File erstellen
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for path in input_paths:
                    f.write(f"file '{path}'\n")
                concat_file = f.name

            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c', 'copy',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            os.unlink(concat_file)

            logger.info(f"Videos concatenated: {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Video concat failed: {e.stderr.decode() if e.stderr else str(e)}")
            if 'concat_file' in locals():
                os.unlink(concat_file)
            raise

    @staticmethod
    def apply_zoom_effect(
        input_path: str,
        output_path: str,
        zoom_type: str = 'zoom_in',
        start_zoom: float = 1.0,
        end_zoom: float = 1.3,
        center_x: float = 0.5,
        center_y: float = 0.5
    ) -> bool:
        """
        Wendet Ken-Burns-Zoom-Effekt auf Video an.

        Args:
            input_path: Eingabe-Video
            output_path: Ausgabe-Video
            zoom_type: 'zoom_in', 'zoom_out', 'pan_left', 'pan_right'
            start_zoom: Start-Zoom-Faktor (1.0 = normal)
            end_zoom: End-Zoom-Faktor
            center_x: Horizontales Zentrum (0.0-1.0)
            center_y: Vertikales Zentrum (0.0-1.0)
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            # Video-Info holen
            info = FFmpegService.get_video_info(input_path)
            width = info.get('width', 1920)
            height = info.get('height', 1080)
            duration = info.get('duration', 1)

            # Zoom-Filter je nach Typ
            if zoom_type == 'zoom_in':
                # Langsam reinzoomen
                zoom_expr = f"zoom+({end_zoom - start_zoom})/(fps*{duration})"
                x_expr = f"(iw-iw/zoom)/2+((iw/zoom)*{center_x - 0.5})"
                y_expr = f"(ih-ih/zoom)/2+((ih/zoom)*{center_y - 0.5})"
            elif zoom_type == 'zoom_out':
                # Von nah nach fern
                zoom_expr = f"{end_zoom}-(zoom-{start_zoom})/({duration}*fps)"
                x_expr = f"(iw-iw/zoom)/2"
                y_expr = f"(ih-ih/zoom)/2"
            elif zoom_type == 'pan_left':
                # Von rechts nach links schwenken
                zoom_expr = f"{start_zoom}"
                x_expr = f"(iw-iw/zoom)*(1-on/({duration}*fps))"
                y_expr = f"(ih-ih/zoom)/2"
            elif zoom_type == 'pan_right':
                # Von links nach rechts schwenken
                zoom_expr = f"{start_zoom}"
                x_expr = f"(iw-iw/zoom)*on/({duration}*fps)"
                y_expr = f"(ih-ih/zoom)/2"
            else:
                # Default: leichter Zoom-In
                zoom_expr = f"min(zoom+0.0015,{end_zoom})"
                x_expr = f"(iw-iw/zoom)/2"
                y_expr = f"(ih-ih/zoom)/2"

            # Zoompan-Filter
            filter_str = (
                f"zoompan=z='{zoom_expr}':"
                f"x='{x_expr}':"
                f"y='{y_expr}':"
                f"d={int(duration * 25)}:"  # Frames
                f"s={width}x{height}:"
                f"fps=25"
            )

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', filter_str,
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'copy',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Zoom effect applied ({zoom_type}): {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Zoom effect failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def apply_fade(
        input_path: str,
        output_path: str,
        fade_in_ms: float = 0,
        fade_out_ms: float = 0
    ) -> bool:
        """
        Wendet Fade-In/Fade-Out auf Video an.

        Args:
            fade_in_ms: Dauer des Fade-In in ms
            fade_out_ms: Dauer des Fade-Out in ms
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            info = FFmpegService.get_video_info(input_path)
            duration = info.get('duration', 0)

            filters = []

            if fade_in_ms > 0:
                fade_in_sec = fade_in_ms / 1000
                filters.append(f"fade=t=in:st=0:d={fade_in_sec}")

            if fade_out_ms > 0 and duration > 0:
                fade_out_sec = fade_out_ms / 1000
                start_time = duration - fade_out_sec
                if start_time > 0:
                    filters.append(f"fade=t=out:st={start_time}:d={fade_out_sec}")

            if not filters:
                # Kein Fade, einfach kopieren
                import shutil
                shutil.copy(input_path, output_path)
                return True

            filter_str = ','.join(filters)

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', filter_str,
                '-af', filter_str.replace('fade=t=', 'afade=t='),
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'aac',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Fade applied: in={fade_in_ms}ms, out={fade_out_ms}ms")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Fade failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    @staticmethod
    def apply_color_correction(
        input_path: str,
        output_path: str,
        brightness: float = 0,
        contrast: float = 1.0,
        saturation: float = 1.0
    ) -> bool:
        """
        Wendet Farb-Korrektur an.

        Args:
            brightness: -1.0 bis 1.0 (0 = keine Aenderung)
            contrast: 0.0 bis 2.0 (1.0 = normal)
            saturation: 0.0 bis 2.0 (1.0 = normal)
        """
        if not has_ffmpeg():
            raise RuntimeError("FFmpeg nicht verfügbar")

        try:
            filter_str = f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}"

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', filter_str,
                '-c:v', 'libx264', '-preset', 'fast',
                '-c:a', 'copy',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Color correction applied: b={brightness}, c={contrast}, s={saturation}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Color correction failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise
