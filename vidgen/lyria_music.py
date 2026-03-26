"""
Lyria Music Generation für VidGen
Nutzt Google Gemini API für AI-generierte Hintergrundmusik
"""
import asyncio
import os
import wave
from pathlib import Path

# Konfiguration
MODEL = 'models/lyria-realtime-exp'
OUTPUT_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16-bit

# Timeouts
CONNECT_TIMEOUT = 30  # Sekunden für Verbindungsaufbau
CHUNK_TIMEOUT = 10    # Sekunden pro Chunk
TOTAL_TIMEOUT = 120   # Maximale Gesamtzeit


class LyriaMusicGenerator:
    def __init__(self, api_key: str):
        from google import genai
        self.client = genai.Client(
            api_key=api_key,
            http_options={'api_version': 'v1alpha'},
        )
    
    async def generate_music(
        self, 
        prompt: str, 
        duration_seconds: int = 30,
        output_path: str = None,
        bpm: int = None,
        scale: str = None
    ) -> str:
        """
        Generiert Musik basierend auf einem Text-Prompt.
        MIT TIMEOUT-HANDLING!
        """
        from google.genai import types
        
        if output_path is None:
            output_path = f"/tmp/music_{hash(prompt)}.wav"
        
        audio_chunks = []
        target_chunks = int(duration_seconds * (OUTPUT_RATE / 4200))
        
        try:
            # Gesamter Vorgang mit Timeout
            async with asyncio.timeout(TOTAL_TIMEOUT):
                async with self.client.aio.live.music.connect(model=MODEL) as session:
                    # Prompt setzen
                    await asyncio.wait_for(
                        session.set_weighted_prompts([
                            types.WeightedPrompt(text=prompt, weight=1.0)
                        ]),
                        timeout=CONNECT_TIMEOUT
                    )
                    
                    # Config setzen
                    config = types.LiveMusicGenerationConfig()
                    if bpm:
                        config.bpm = bpm
                    if scale:
                        config.scale = scale
                    await asyncio.wait_for(
                        session.set_music_generation_config(config),
                        timeout=CONNECT_TIMEOUT
                    )
                    
                    # Musik starten
                    await asyncio.wait_for(session.play(), timeout=CONNECT_TIMEOUT)
                    
                    # Audio empfangen mit Chunk-Timeout
                    chunk_count = 0
                    last_chunk_time = asyncio.get_event_loop().time()
                    
                    async for message in session.receive():
                        current_time = asyncio.get_event_loop().time()
                        
                        # Chunk-Timeout prüfen
                        if current_time - last_chunk_time > CHUNK_TIMEOUT:
                            print(f"Chunk timeout nach {chunk_count} chunks")
                            break
                        
                        if message.server_content and hasattr(message.server_content, 'audio_chunks'):
                            if message.server_content.audio_chunks:
                                audio_data = message.server_content.audio_chunks[0].data
                                audio_chunks.append(audio_data)
                                chunk_count += 1
                                last_chunk_time = current_time
                                
                                if chunk_count >= target_chunks:
                                    await session.pause()
                                    break
                    
                    # Mindestens einige Chunks erforderlich
                    if chunk_count < 10:
                        raise ValueError(f"Zu wenige Audio-Chunks empfangen: {chunk_count}")
        
        except asyncio.TimeoutError:
            raise TimeoutError(f"Lyria Musik-Generierung Timeout nach {TOTAL_TIMEOUT}s")
        except Exception as e:
            raise RuntimeError(f"Lyria Musik-Generierung fehlgeschlagen: {str(e)}")
        
        # Als WAV speichern
        if not audio_chunks:
            raise ValueError("Keine Audio-Daten empfangen")
        
        with wave.open(output_path, 'wb') as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(SAMPLE_WIDTH)
            wav_file.setframerate(OUTPUT_RATE)
            wav_file.writeframes(b''.join(audio_chunks))
        
        print(f"Lyria: {chunk_count} chunks -> {output_path}")
        return output_path


# Mood-zu-Prompt Mapping für VidGen
MOOD_PROMPTS = {
    'upbeat': 'upbeat energetic happy pop music, positive vibes, major key',
    'corporate': 'professional corporate background music, modern business, inspiring',
    'emotional': 'emotional cinematic orchestral music, dramatic, touching',
    'chill': 'relaxed chill lofi beats, calm ambient, peaceful',
    'news': 'serious news broadcast music, urgent but professional, dramatic',
    'tech': 'modern electronic tech music, futuristic, innovative',
    'acoustic': 'warm acoustic guitar music, organic, heartfelt',
    'dramatic': 'epic dramatic orchestral music, intense, powerful',
}


async def generate_background_music(
    mood: str = None,
    custom_prompt: str = None,
    duration: int = 45,
    output_dir: str = '/var/www/workloom/media/music_library',
    api_key: str = None
) -> str:
    """
    Hilfsfunktion für VidGen.
    MIT TIMEOUT-HANDLING!
    
    Args:
        mood: Einer der vordefinierten Moods (upbeat, corporate, etc.)
        custom_prompt: Eigene Beschreibung (überschreibt mood)
        duration: Länge in Sekunden
        output_dir: Verzeichnis für generierte Musik
        api_key: Google/Gemini API Key (required!)
    
    Returns:
        Pfad zur generierten Datei
    
    Raises:
        ValueError: Kein API Key
        TimeoutError: Generierung dauert zu lange
        RuntimeError: Generierung fehlgeschlagen
    """
    # API Key muss vom User kommen - kein Fallback auf environment!
    if not api_key:
        raise ValueError("Kein Google/Gemini API Key. Bitte in den Profileinstellungen hinterlegen.")
    
    # Prompt bestimmen
    if custom_prompt:
        prompt = custom_prompt
    elif mood and mood in MOOD_PROMPTS:
        prompt = MOOD_PROMPTS[mood]
    else:
        prompt = MOOD_PROMPTS['corporate']  # Default
    
    # Output-Pfad
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{mood or 'custom'}_{hash(prompt) % 10000}.wav"
    output_path = os.path.join(output_dir, filename)
    
    # Generieren mit Timeout
    generator = LyriaMusicGenerator(api_key)
    result = await generator.generate_music(
        prompt=prompt,
        duration_seconds=duration,
        output_path=output_path
    )
    
    return result


if __name__ == '__main__':
    # Test
    import sys
    mood = sys.argv[1] if len(sys.argv) > 1 else 'upbeat'
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("GEMINI_API_KEY nicht gesetzt!")
        sys.exit(1)
    result = asyncio.run(generate_background_music(mood=mood, duration=30, api_key=api_key))
    print(f"Generated: {result}")
