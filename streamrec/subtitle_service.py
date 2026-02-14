"""
Subtitle Service for StreamRec
Uses OpenAI Whisper API for transcription and generates WebVTT subtitles
"""
import os
import tempfile
import logging
import subprocess
from datetime import timedelta

logger = logging.getLogger(__name__)

# OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')


def format_timestamp(seconds: float) -> str:
    """Convert seconds to WebVTT timestamp format (HH:MM:SS.mmm)"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{milliseconds:03d}"


def extract_audio(video_path: str, audio_path: str) -> bool:
    """Extract audio from video file using ffmpeg"""
    try:
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr.decode()}")
            return False
        return True
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return False


def transcribe_with_whisper(audio_path: str, language: str = 'de') -> dict:
    """
    Transcribe audio using OpenAI Whisper API
    Returns segments with timestamps
    """
    import urllib.request
    import urllib.error
    import json
    
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")
    
    url = "https://api.openai.com/v1/audio/transcriptions"
    
    # Read audio file
    with open(audio_path, 'rb') as f:
        audio_data = f.read()
    
    # Build multipart form data
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    body = []
    
    # Add file
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="file"; filename="audio.wav"')
    body.append(b'Content-Type: audio/wav')
    body.append(b'')
    body.append(audio_data)
    
    # Add model
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="model"')
    body.append(b'')
    body.append(b'whisper-1')
    
    # Add language
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="language"')
    body.append(b'')
    body.append(language.encode())
    
    # Add response format (verbose_json for timestamps)
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="response_format"')
    body.append(b'')
    body.append(b'verbose_json')
    
    # Add timestamp granularities
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="timestamp_granularities[]"')
    body.append(b'')
    body.append(b'segment')
    
    body.append(f'--{boundary}--'.encode())
    body.append(b'')
    
    body_bytes = b'\r\n'.join(body)
    
    req = urllib.request.Request(url, data=body_bytes)
    req.add_header('Authorization', f'Bearer {OPENAI_API_KEY}')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode())
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"Whisper API error: {e.code} - {error_body}")
        raise


def generate_webvtt(segments: list) -> str:
    """
    Generate WebVTT subtitle file from Whisper segments
    """
    lines = ["WEBVTT", ""]
    
    for i, segment in enumerate(segments, 1):
        start = format_timestamp(segment.get('start', 0))
        end = format_timestamp(segment.get('end', 0))
        text = segment.get('text', '').strip()
        
        if text:
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")
    
    return "\n".join(lines)


def create_subtitles_for_video(video_path: str, output_vtt_path: str, language: str = 'de') -> dict:
    """
    Main function: Create subtitles for a video file
    
    Args:
        video_path: Path to the video file
        output_vtt_path: Where to save the .vtt file
        language: Language code (default: 'de' for German)
    
    Returns:
        dict with 'success', 'message', and optionally 'transcript'
    """
    try:
        # Create temp file for audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            audio_path = tmp.name
        
        try:
            # Step 1: Extract audio
            logger.info(f"Extracting audio from {video_path}")
            if not extract_audio(video_path, audio_path):
                return {'success': False, 'message': 'Audio extraction failed'}
            
            # Check audio file size (Whisper limit: 25MB)
            audio_size = os.path.getsize(audio_path)
            if audio_size > 25 * 1024 * 1024:
                return {'success': False, 'message': 'Audio too large (max 25MB)'}
            
            # Step 2: Transcribe with Whisper
            logger.info("Transcribing with Whisper API...")
            result = transcribe_with_whisper(audio_path, language)
            
            segments = result.get('segments', [])
            if not segments:
                # If no segments, create one from full text
                segments = [{
                    'start': 0,
                    'end': result.get('duration', 10),
                    'text': result.get('text', '')
                }]
            
            # Step 3: Generate WebVTT
            logger.info("Generating WebVTT...")
            vtt_content = generate_webvtt(segments)
            
            # Step 4: Save VTT file
            with open(output_vtt_path, 'w', encoding='utf-8') as f:
                f.write(vtt_content)
            
            logger.info(f"Subtitles saved to {output_vtt_path}")
            
            return {
                'success': True,
                'message': 'Subtitles created successfully',
                'transcript': result.get('text', ''),
                'segments': len(segments),
                'duration': result.get('duration', 0)
            }
            
        finally:
            # Cleanup temp audio file
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
    except Exception as e:
        logger.exception(f"Subtitle creation error: {e}")
        return {'success': False, 'message': str(e)}
