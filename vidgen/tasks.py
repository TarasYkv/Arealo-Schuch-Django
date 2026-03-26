import os
import json
import subprocess
import tempfile
import requests
from decimal import Decimal
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from billiard.exceptions import WorkerLostError
from django.conf import settings
from django.utils import timezone
from openai import OpenAI

import asyncio
from .lyria_music import generate_background_music, MOOD_PROMPTS
from .models import MusicTrack

# === SCRIPT TEMPLATES ===

SCRIPT_PROMPTS = {
    'job_intro': """Erstelle ein {duration}-Sekunden Videoskript über den Beruf "{title}".

Struktur:
1. Hook (5 Sek): Spannende Frage oder Fakt
2. Aufgaben (15 Sek): Was macht man in diesem Beruf?
3. Gehalt (10 Sek): Wie viel verdient man? (recherchiere aktuelle Zahlen)
4. Voraussetzungen (10 Sek): Ausbildung, Skills
5. CTA (5 Sek): "Folgt für mehr Berufsvideos!"

Schreibe NUR den gesprochenen Text, keine Regieanweisungen.
Kurze, prägnante Sätze. Maximal 600 Zeichen.""",

    'product': """Erstelle ein {duration}-Sekunden Produktvideo-Skript für "{title}".

Struktur:
1. Problem (8 Sek): Welches Problem löst es?
2. Lösung (12 Sek): Wie funktioniert das Produkt?
3. Vorteile (7 Sek): Was macht es besonders?
4. CTA (3 Sek): "Jetzt entdecken!"

NUR gesprochener Text, maximal 400 Zeichen.""",

    'tutorial': """Erstelle ein {duration}-Sekunden Tutorial-Skript: "{title}".

Struktur:
1. Was lernst du? (5 Sek)
2. Schritt 1 (12 Sek)
3. Schritt 2 (12 Sek)
4. Schritt 3 (12 Sek)
5. Zusammenfassung (4 Sek)

NUR gesprochener Text, maximal 600 Zeichen.""",

    'facts': """Erstelle ein {duration}-Sekunden Fakten-Video über "{title}".

5 interessante Fakten, jeweils ~8 Sekunden.
Starte jeden Fakt mit einer Überraschung.

NUR gesprochener Text, maximal 550 Zeichen.""",

    'comparison': """Erstelle ein {duration}-Sekunden Vergleichsvideo: "{title}".

Struktur:
1. Intro (5 Sek): Was vergleichen wir?
2. Option A Vorteile (12 Sek)
3. Option B Vorteile (12 Sek)
4. Fazit (12 Sek): Wann was besser ist
5. CTA (4 Sek)

NUR gesprochener Text, maximal 600 Zeichen.""",

    'top_list': """Erstelle ein {duration}-Sekunden Top-5-Listen Video: "{title}".

5 Punkte, vom 5. zum 1. Platz.
Je Punkt ~10 Sekunden.

NUR gesprochener Text, maximal 650 Zeichen.""",

    'motivation': """Erstelle ein {duration}-Sekunden Motivationsvideo über "{title}".

Inspirierend, emotional, kraftvoll.
Ende mit einem starken Call-to-Action.

NUR gesprochener Text, maximal 400 Zeichen.""",

    'tips': """Erstelle ein {duration}-Sekunden Tipps-Video: "{title}".

3-4 praktische, sofort umsetzbare Tipps.
Kurz und knackig.

NUR gesprochener Text, maximal 600 Zeichen.""",


    'hook_story': """Erstelle ein {duration}-Sekunden Viral-Video über "{title}".

WICHTIG: Starte mit einem KRASSEN Hook!
Struktur:
1. HOOK (3 Sek): Schockierender Fakt oder kontroverse Aussage
2. Kontext (10 Sek): Warum ist das wichtig?
3. Story/Erklärung (25 Sek): Die ganze Geschichte
4. Twist/Pointe (5 Sek): Überraschende Wendung
5. CTA (2 Sek): "Folgt für mehr!"

NUR gesprochener Text, maximal 600 Zeichen.""",

    'pov': """Erstelle ein {duration}-Sekunden POV-Video: "{title}".

Perspektive: Du bist der Zuschauer in dieser Situation.
Starte mit "POV: ..." und beschreibe die Szene.
Emotional, relatable, authentisch.

NUR gesprochener Text, maximal 400 Zeichen.""",

    'storytime': """Erstelle ein {duration}-Sekunden Storytime-Video über "{title}".

Erzähle eine packende Geschichte:
1. Setup (10 Sek): Wann/Wo/Wer
2. Konflikt (15 Sek): Was ist passiert?
3. Höhepunkt (15 Sek): Der verrückte Teil
4. Auflösung (10 Sek): Wie ging es aus?

Persönlich, emotional, fesselnd.
NUR gesprochener Text, maximal 650 Zeichen.""",

    'hot_take': """Erstelle ein {duration}-Sekunden Hot-Take-Video: "{title}".

Kontroverse, aber begründete Meinung.
1. Statement (5 Sek): Deine These
2. Begründung (20 Sek): Warum du das denkst
3. Challenge (5 Sek): "Ändere meine Meinung!"

Selbstbewusst, provokant, aber respektvoll.
NUR gesprochener Text, maximal 400 Zeichen.""",

    'before_after': """Erstelle ein {duration}-Sekunden Vorher/Nachher-Video: "{title}".

1. VORHER (12 Sek): Der alte Zustand, Probleme
2. TRANSFORMATION (8 Sek): Was wurde gemacht?
3. NACHHER (12 Sek): Das Ergebnis, Verbesserungen
4. CTA (3 Sek): "Probier es selbst!"

NUR gesprochener Text, maximal 450 Zeichen.""",

    'unpopular_opinion': """Erstelle ein {duration}-Sekunden Unpopular-Opinion-Video: "{title}".

1. "Unpopular Opinion:" (3 Sek)
2. Die kontroverse Meinung (7 Sek)
3. Begründung mit Argumenten (18 Sek)
4. "Fight me in den Kommentaren" (2 Sek)

Mutig, ehrlich, diskussionswürdig.
NUR gesprochener Text, maximal 400 Zeichen.""",

    'things_nobody_tells': """Erstelle ein {duration}-Sekunden Video: "Dinge über {title} die dir keiner sagt".

4-5 Insider-Infos die Anfänger nicht wissen.
Jeder Punkt ~9 Sekunden.
Starte mit: "Niemand sagt dir das über..."

NUR gesprochener Text, maximal 600 Zeichen.""",

    'this_or_that': """Erstelle ein {duration}-Sekunden Dies-oder-Das-Video: "{title}".

Vergleiche zwei Optionen:
1. Intro (5 Sek): Die Frage stellen
2. Option A (12 Sek): Vorteile
3. Option B (12 Sek): Vorteile  
4. Deine Wahl (8 Sek): Was würdest du nehmen und warum?
5. "Was wählt ihr?" (3 Sek)

NUR gesprochener Text, maximal 550 Zeichen.""",
}



def get_or_generate_music(project):
    """
    Holt passende Musik aus der Bibliothek, Pixabay, oder generiert neue via Lyria.
    Fallback-Reihenfolge: Bibliothek -> Pixabay -> Lyria
    Returns: tuple (path, was_generated) - was_generated=True wenn neu generiert
    """
    from .pixabay_music import get_pixabay_music
    
    # Custom Prompt hat Vorrang
    if project.custom_music_prompt:
        custom_prompt = project.custom_music_prompt
        mood = 'custom'
    elif project.background_music and project.background_music != 'none':
        mood = project.background_music
        custom_prompt = None
    else:
        return None, False
    
    # Musik-Dauer bestimmen
    if project.music_duration and project.music_duration > 0:
        duration = project.music_duration
    else:
        duration = project.target_duration or 45
    
    # 1. In lokaler Bibliothek suchen (kostenlos, schnell)
    if not custom_prompt:
        existing = MusicTrack.objects.filter(
            mood=mood,
            duration__gte=duration
        ).first()
        
        if existing:
            existing.usage_count += 1
            existing.save()
            return existing.audio_file.path, False
    
    # 2. Pixabay versuchen (kostenlos, schnell)
    user = project.user
    pixabay_key = getattr(user, 'pixabay_api_key', None)
    if pixabay_key and not custom_prompt:
        try:
            filepath, track_info = get_pixabay_music(
                api_key=pixabay_key,
                mood=mood,
                min_duration=max(30, duration - 30),
                max_duration=duration + 60
            )
            if filepath:
                # In Bibliothek speichern für späteren Gebrauch
                from django.core.files import File
                track = MusicTrack.objects.create(
                    prompt=f"Pixabay: {track_info.get('title', mood)}",
                    mood=mood,
                    duration=track_info.get('duration', duration),
                    usage_count=1,
                    tags=f"pixabay,{mood}"
                )
                with open(filepath, 'rb') as f:
                    track.audio_file.save(f"pixabay_{mood}_{track.id}.mp3", File(f))
                track.save()
                
                # Pixabay ist kostenlos
                from decimal import Decimal
                project.cost_music = Decimal('0.00')
                project.save(update_fields=['cost_music'])
                
                return track.audio_file.path, True
        except Exception as e:
            print(f"Pixabay Fehler (Fallback zu Lyria): {e}")
    
    # 3. Lyria als Fallback (kostenpflichtig, langsam)
    gemini_key = getattr(user, 'gemini_api_key', None) or getattr(user, 'google_api_key', None)
    if not gemini_key:
        if not pixabay_key:
            raise ValueError("Weder Pixabay noch Gemini API Key hinterlegt. Bitte in den Profileinstellungen eintragen.")
        raise ValueError("Pixabay fehlgeschlagen und kein Gemini API Key für Lyria Fallback.")
    
    try:
        if custom_prompt:
            full_prompt = custom_prompt
        else:
            base_prompt = MOOD_PROMPTS.get(mood, MOOD_PROMPTS['corporate'])
            full_prompt = f"{base_prompt}, passend fuer Video ueber {project.title}"
        
        # Async ausfuehren MIT TIMEOUT
        async def _generate_with_timeout():
            return await asyncio.wait_for(
                generate_background_music(
                    mood=mood if not custom_prompt else None,
                    custom_prompt=full_prompt,
                    duration=duration + 10,
                    api_key=gemini_key
                ),
                timeout=180
            )
        
        output_path = asyncio.run(_generate_with_timeout())
        
        # In Bibliothek speichern
        from django.core.files import File
        track = MusicTrack.objects.create(
            prompt=full_prompt,
            mood=mood,
            duration=duration + 10,
            usage_count=1,
            tags=f"lyria,{mood},{project.title[:30]}"
        )
        with open(output_path, 'rb') as f:
            track.audio_file.save(f"lyria_{mood}_{track.id}.wav", File(f))
        track.save()
        
        # Lyria-Kosten
        from decimal import Decimal
        project.cost_music = Decimal('0.05')
        project.save(update_fields=['cost_music'])
        
        return track.audio_file.path, True
        
    except asyncio.TimeoutError:
        raise ValueError("Lyria Musik-Timeout (180s). Tipp: Pixabay API Key in Profileinstellungen hinzufügen für schnellere Musik.")
    except Exception as e:
        import traceback; traceback.print_exc()
        raise ValueError(f"Musik-Generierung fehlgeschlagen: {str(e) or type(e).__name__}")


@shared_task(bind=True, soft_time_limit=1800, time_limit=1860, acks_late=True, reject_on_worker_lost=True)
def generate_video(self, project_id):
    """Haupttask: Generiert ein komplettes Video"""
    from .models import VideoProject
    
    project = VideoProject.objects.get(id=project_id)
    
    try:
        # 1. Skript generieren
        project.status = 'script'
        project.progress = 10
        project.save()
        generate_script(project)
        
        # 2. Audio generieren
        project.status = 'audio'
        project.progress = 30
        project.save()
        audio_path, duration = generate_audio(project)
        
        # 3. Pexels Clips holen
        project.status = 'clips'
        project.progress = 50
        project.save()
        clips = fetch_pexels_clips_smart(project, duration)
        
        # 4. Remotion rendern
        project.status = 'rendering'
        project.progress = 70
        project.save()
        video_path = render_video(project, audio_path, clips, duration)
        
        # 5. Komprimieren
        project.status = 'compressing'
        project.progress = 90
        project.save()
        final_path = compress_video(video_path)
        
        # 6. In Videos-App speichern
        save_to_videos_app(project, final_path)
        
        # Fertig!
        project.status = 'done'
        project.progress = 100
        project.completed_at = timezone.now()
        project.calculate_total_cost()
        project.save()
        
        # Batch updaten falls vorhanden
        if project.batch:
            project.batch.update_progress()
        
        return {'status': 'success', 'project_id': str(project.id)}
        
    except SoftTimeLimitExceeded:
        project.status = 'failed'
        project.error_message = 'Task Timeout: Video-Generierung dauerte zu lange (>30 Min). Bitte mit kürzerer Dauer oder 720p erneut versuchen.'
        project.save()
        if project.batch:
            project.batch.update_progress()
        raise
        
    except Exception as e:
        project.status = 'failed'
        project.error_message = str(e)
        project.save()
        
        if project.batch:
            project.batch.update_progress()
        
        raise


def generate_script(project):
    """Generiert das Skript mit GPT oder verwendet custom_script"""
    from .models import VideoProject
    
    # Falls eigener Text vorhanden, diesen verwenden
    if hasattr(project, 'custom_script') and project.custom_script and project.custom_script.strip():
        project.script = project.custom_script.strip()
        project.save()
        return project.script
    
    # Falls Template "custom" aber kein Text -> Fehler
    if project.template == 'custom':
        raise ValueError("Template 'Eigener Text' gewählt, aber kein Text eingegeben!")
    
    user = project.user
    api_key = user.openai_api_key
    
    if not api_key:
        raise ValueError("Kein OpenAI API-Key hinterlegt")
    
    client = OpenAI(api_key=api_key)
    
    # Prompt aus Template
    template = project.template
    prompt_template = SCRIPT_PROMPTS.get(template, SCRIPT_PROMPTS['facts'])
    prompt = prompt_template.format(title=project.title, duration=project.target_duration)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Du bist ein erfahrener Video-Skript-Autor für TikTok und YouTube Shorts. Schreibe kurze, packende Skripte. WICHTIG: Verwende KEINE Emojis oder Sonderzeichen, nur reinen Text!"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )
    
    script = response.choices[0].message.content.strip()
    project.script = script
    
    # Kosten tracken (gpt-4o-mini: $0.15/1M input, $0.60/1M output)
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost = (input_tokens * 0.00015 / 1000) + (output_tokens * 0.0006 / 1000)
    project.cost_script = Decimal(str(round(cost, 6)))
    project.save()
    
    return script


def generate_audio(project):
    """Generiert TTS Audio und holt Timestamps"""
    user = project.user
    api_key = user.openai_api_key
    
    if not api_key:
        raise ValueError("Kein OpenAI API-Key hinterlegt")
    
    client = OpenAI(api_key=api_key)
    
    # TTS generieren
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=project.voice,
        input=project.script,
        speed=0.95
    )
    
    # Temporäre Datei speichern
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, 'voiceover.mp3')
    
    with open(audio_path, 'wb') as f:
        f.write(response.content)
    
    # Kosten tracken (tts-1-hd: $15/1M chars)
    chars = len(project.script)
    cost = chars * 0.015 / 1000
    project.cost_tts = Decimal(str(round(cost, 6)))
    
    # Audio-Dauer ermitteln
    import subprocess
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
         '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    
    # Whisper für Timestamps
    with open(audio_path, 'rb') as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )
    
    # Whisper Kosten ($0.006/min)
    whisper_cost = (duration / 60) * 0.006
    project.cost_whisper = Decimal(str(round(whisper_cost, 6)))
    
    # Timestamps speichern
    timestamps_path = os.path.join(temp_dir, 'timestamps.json')
    with open(timestamps_path, 'w') as f:
        json.dump({
            'words': [{'word': w.word, 'start': w.start, 'end': w.end} 
                      for w in transcript.words]
        }, f)
    
    # Audio im Projekt speichern
    from django.core.files.base import ContentFile
    with open(audio_path, 'rb') as f:
        project.audio_file.save(f'voiceover_{project.id}.mp3', ContentFile(f.read()), save=True)
    
    project.save()
    
    return audio_path, duration



def extract_keywords_for_segments(script_text, num_segments, user=None):
    """Extrahiert Keywords für jeden Video-Abschnitt mit GPT"""
    # User's OpenAI API Key verwenden
    if user and user.openai_api_key:
        api_key = user.openai_api_key
    else:
        raise ValueError("Kein OpenAI API Key hinterlegt")
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""Analysiere dieses Videoskript und extrahiere für {num_segments} Video-Abschnitte jeweils 1-2 passende Suchbegriffe für Stock-Videos.

Skript:
{script_text}

Gib für jeden Abschnitt englische Suchbegriffe zurück, die zu passenden B-Roll Videos führen.
Format: Ein Begriff pro Zeile, {num_segments} Zeilen total.
Nur die Suchbegriffe, keine Nummerierung oder Erklärungen.

Beispiel für ein Feuerwehr-Video:
fire truck
firefighter training
emergency rescue
burning building
fire station"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7
    )
    
    keywords = response.choices[0].message.content.strip().split('\n')
    # Bereinigen und auf Anzahl begrenzen
    keywords = [k.strip() for k in keywords if k.strip()][:num_segments]
    
    # Falls zu wenige, mit generischem Begriff auffüllen
    while len(keywords) < num_segments:
        keywords.append("professional business")
    
    return keywords


def fetch_pexels_clips_smart(project, duration):
    """Holt thematisch passende Clips von Pexels basierend auf Skript-Inhalt"""
    from .models import PexelsClip
    
    user = project.user
    api_key = getattr(user, 'pexels_api_key', None)
    
    if not api_key:
        raise ValueError("Kein Pexels API-Key hinterlegt")
    
    headers = {'Authorization': api_key}
    
    # Anzahl benötigter Clips berechnen (4 Sek pro Clip)
    num_clips_needed = max(5, (int(duration) // 4) + 2)
    
    # Keywords für jeden Abschnitt extrahieren
    script_text = project.script or project.title
    keywords = extract_keywords_for_segments(script_text, num_clips_needed, user=project.user)
    
    print(f"Smart Keywords: {keywords}")
    
    temp_dir = tempfile.mkdtemp()
    clips = []
    used_video_ids = set()  # Vermeidet Duplikate
    
    for i, keyword in enumerate(keywords):
        # Pexels API aufrufen
        response = requests.get(
            'https://api.pexels.com/videos/search',
            headers=headers,
            params={
                'query': keyword,
                'orientation': 'portrait',
                'size': 'medium',
                'per_page': 5
            }
        )
        
        if response.status_code != 200:
            print(f"Pexels API Fehler für '{keyword}': {response.status_code}")
            continue
        
        videos = response.json().get('videos', [])
        
        # Finde ein Video das noch nicht verwendet wurde
        selected_video = None
        for video in videos:
            if video['id'] not in used_video_ids:
                selected_video = video
                used_video_ids.add(video['id'])
                break
        
        if not selected_video:
            # Fallback: erstes Video nehmen auch wenn Duplikat
            if videos:
                selected_video = videos[0]
            else:
                # Generische Suche als Fallback
                fallback_response = requests.get(
                    'https://api.pexels.com/videos/search',
                    headers=headers,
                    params={
                        'query': 'professional work',
                        'orientation': 'portrait',
                        'per_page': 3
                    }
                )
                fallback_videos = fallback_response.json().get('videos', [])
                if fallback_videos:
                    selected_video = fallback_videos[0]
        
        if not selected_video:
            continue
        
        # Beste Qualität finden
        video_files = sorted(
            selected_video['video_files'],
            key=lambda x: x.get('height', 0),
            reverse=True
        )
        
        best_file = None
        for vf in video_files:
            if vf.get('height', 0) >= 1080:
                best_file = vf
                break
        
        if not best_file:
            best_file = video_files[0]
        
        # Download
        clip_path = os.path.join(temp_dir, f'clip{i+1}.mp4')
        clip_response = requests.get(best_file['link'], stream=True)
        
        with open(clip_path, 'wb') as f:
            for chunk in clip_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        clips.append({
            'path': clip_path,
            'pexels_id': str(selected_video['id']),
            'duration': selected_video.get('duration', 10),
            'width': best_file.get('width', 1080),
            'height': best_file.get('height', 1920),
            'keyword': keyword  # Für Debugging
        })
        
        print(f"Clip {i+1}: '{keyword}' -> Video {selected_video['id']}")
    
    return clips

def render_video(project, audio_path, clips, duration):
    """Rendert das Video mit Remotion (lokal oder Modal)"""
    
    # Aufloesung basierend auf Einstellung
    if hasattr(project, 'resolution') and project.resolution == '720p':
        width, height = 720, 1280
    else:
        width, height = project.get_platform_resolution()
    fps = 30
    total_frames = int(duration * fps) + fps  # +1 Sekunde Buffer
    
    # Remotion-Projekt vorbereiten
    remotion_dir = '/var/www/workloom/remotion'
    temp_dir = os.path.dirname(audio_path)
    
    # Musik aus Bibliothek oder generieren
    music_path = None
    music_was_generated = False
    
    # 1. Prüfen ob Track bereits ausgewählt
    if hasattr(project, 'selected_music_track') and project.selected_music_track:
        if project.selected_music_track.audio_file:
            music_path = project.selected_music_track.audio_file.path
            print(f"Musik aus Bibliothek: {music_path}")
    
    # 2. Falls kein Track ausgewählt, aber Musik gewünscht -> Pixabay/Lyria
    if not music_path and (project.background_music != 'none' or project.custom_music_prompt):
        try:
            music_path, music_was_generated = get_or_generate_music(project)
            if music_path:
                import shutil
                music_dest = os.path.join(remotion_dir, 'public', 'background_music.wav')
                shutil.copy(music_path, music_dest)
                if music_was_generated:
                    print(f"Neue Musik generiert: {music_path}")
        except Exception as e:
            import traceback; traceback.print_exc()

    # Konfiguration erstellen
    config = {
        'title': project.title,
        'duration': duration,
        'width': width,
        'height': height,
        'fps': fps,
        'totalFrames': total_frames,
        'clips': len(clips),
        'titlePosition': project.title_position,
        'watermark': project.watermark,
        'hasOverlay': bool(project.overlay_file),
        'overlayStart': project.overlay_start,
        'overlayPosition': project.overlay_position,
        'overlayWidth': project.overlay_width,
        'overlayDuration': project.overlay_duration,
        'introStyle': project.intro_style,
        'transitionStyle': project.transition_style,
        'lowerThirdText': project.lower_third_text,
        'lowerThirdStart': project.lower_third_start,
        'showProgressBar': project.show_progress_bar,
        'progressBarColor': project.progress_bar_color,
        'emojiAnimations': project.emoji_animations,
        'kenBurnsEffect': project.ken_burns_effect,
        'colorGrading': project.color_grading,
        'quoteText': project.quote_text,
        'quoteAuthor': project.quote_author,
        'quoteTime': project.quote_time,
        'quoteDuration': project.quote_duration,
        'factBoxText': project.fact_box_text,
        'factBoxTime': project.fact_box_time,
        'factBoxDuration': project.fact_box_duration,
        'backgroundMusic': project.background_music,
        'hasMusicFile': music_path is not None,
        'musicVolume': project.music_volume,
        'soundEffects': project.sound_effects,
        'audioDucking': project.audio_ducking,
        'isDiscussion': project.is_discussion,
        'speaker1Name': project.speaker1_name,
        'speaker2Name': project.speaker2_name,
    }
    
    # === RENDER BACKEND AUSWAHL ===
    render_backend = getattr(project, 'render_backend', 'local')
    
    if render_backend == 'modal':
        # Modal Cloud GPU Rendering
        print(f"🚀 Verwende Modal Cloud für GPU-Rendering...")
        try:
            from vidgen.modal_client import render_on_modal
            return render_on_modal(project, audio_path, clips, duration, config)
        except Exception as e:
            print(f"⚠️ Modal Rendering fehlgeschlagen: {e}")
            print(f"   Fallback auf lokales Rendering...")
            # Fallback zu lokal
    
    # === LOKALES RENDERING (Original-Code) ===
    print(f"💻 Verwende lokales Rendering (Hetzner Server)...")
    
    # Clips kopieren
    for i, clip in enumerate(clips):
        dest = os.path.join(remotion_dir, 'public', f'clip{i+1}.mp4')
        subprocess.run(['cp', clip['path'], dest])
    
    # Audio kopieren
    subprocess.run(['cp', audio_path, os.path.join(remotion_dir, 'public', 'voiceover.mp3')])
    
    # Timestamps kopieren
    timestamps_path = os.path.join(temp_dir, 'timestamps.json')
    subprocess.run(['cp', timestamps_path, os.path.join(remotion_dir, 'public', 'timestamps.json')])
    
    # Config schreiben
    with open(os.path.join(remotion_dir, 'public', 'config.json'), 'w') as f:
        json.dump(config, f)
    
    # Overlay kopieren falls vorhanden
    if project.overlay_file:
        overlay_dest = os.path.join(remotion_dir, 'public', 'overlay' + os.path.splitext(project.overlay_file.name)[1])
        subprocess.run(['cp', project.overlay_file.path, overlay_dest])
    
    # Remotion rendern
    output_path = os.path.join(temp_dir, 'output.mp4')
    
    result = subprocess.run(
        [
            'npx', 'remotion', 'render',
            'VidGenVideo',
            output_path,
            '--codec', 'h264',
            '--crf', '23',
            '--concurrency', '1',
            '--timeout', '120000',
        ],
        cwd=remotion_dir,
        capture_output=True,
        text=True,
        timeout=1800  # 30 Minuten Timeout
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Remotion Render fehlgeschlagen: {result.stderr}")
    
    return output_path

def compress_video(video_path):
    """Komprimiert das Video für Upload"""
    
    output_path = video_path.replace('.mp4', '_compressed.mp4')
    
    subprocess.run([
        'ffmpeg', '-y',
        '-i', video_path,
        '-c:v', 'libx264',
        '-crf', '26',
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '128k',
        output_path
    ], check=True)
    
    return output_path


def save_to_videos_app(project, video_path):
    """Speichert das fertige Video in der Videos-App"""
    from videos.models import Video, UserStorage
    from django.core.files import File
    import subprocess
    
    # Thumbnail generieren (erstes Frame)
    thumbnail_path = video_path.replace('.mp4', '_thumb.jpg')
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-ss', '00:00:01',  # 1 Sekunde ins Video
            '-vframes', '1',
            '-vf', 'scale=480:-1',  # 480px breit, Höhe proportional
            '-q:v', '2',
            '-y',  # Überschreiben falls existiert
            thumbnail_path
        ], check=True, capture_output=True)
    except Exception as e:
        print(f'Thumbnail generation failed: {e}')
        thumbnail_path = None
    
    # Video-Datei lesen
    with open(video_path, 'rb') as f:
        video_file = File(f, name=f'{project.title.replace(" ", "_")}.mp4')
        
        # Thumbnail lesen falls vorhanden
        thumbnail_file = None
        if thumbnail_path and os.path.exists(thumbnail_path):
            thumbnail_file = File(open(thumbnail_path, 'rb'), name=f'{project.title.replace(" ", "_")}_thumb.jpg')
        
        # Video-Objekt erstellen
        video = Video.objects.create(
            user=project.user,
            title=project.title,
            description=f"Automatisch generiert mit VidGen\nTemplate: {project.get_template_display()}\nPlattform: {project.get_platform_display()}",
            video_file=video_file,
            thumbnail=thumbnail_file,
            file_size=os.path.getsize(video_path)
        )
        
        # Thumbnail-Datei schließen
        if thumbnail_file:
            thumbnail_file.close()
    
    # Temporäres Thumbnail löschen
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
    
    # Projekt mit Video verknüpfen
    project.video = video
    project.save()
    
    # User Storage aktualisieren
    try:
        storage = UserStorage.objects.get(user=project.user)
        storage.used_storage += video.file_size
        storage.save()
    except UserStorage.DoesNotExist:
        pass
    
    return video


def cleanup_stale_videos():
    """Findet und markiert hängende Video-Projekte als failed"""
    from .models import VideoProject
    
    stale_threshold = timezone.now() - timedelta(minutes=30)
    
    # Finde Videos die seit >30 Min im Status 'processing' oder 'rendering' sind
    stale_videos = VideoProject.objects.filter(
        status__in=['processing', 'rendering', 'generating'],
        updated_at__lt=stale_threshold
    )
    
    count = 0
    for video in stale_videos:
        video.status = 'failed'
        video.error_message = f'Task Timeout: Video hing >30 Minuten bei {video.progress}%. Bitte erneut versuchen.'
        video.save()
        count += 1
        print(f'Marked stale: {video.title} (was at {video.progress}%)')
    
    return f'Cleaned up {count} stale videos'


@shared_task
def process_batch(batch_id):
    """Verarbeitet einen Batch von Videos"""
    from .models import VideoBatch, VideoProject
    
    batch = VideoBatch.objects.get(id=batch_id)
    keywords = batch.get_keywords_list()
    
    for i, keyword in enumerate(keywords):
        # Projekt für jedes Keyword erstellen
        project = VideoProject.objects.create(
            user=batch.user,
            batch=batch,
            title=keyword,
            template=batch.template,
            platform=batch.platform,
            voice=batch.voice,
            title_position=batch.title_position,
            target_duration=batch.target_duration,
            resolution=getattr(batch, 'resolution', '1080p'),
            custom_script=batch.custom_script,
            watermark=batch.watermark,
        )
        
        # Video generieren
        generate_video.delay(str(project.id))
    
    return f'Batch {batch_id}: {len(keywords)} videos queued'


# ============================================
# EINZELNE SCHRITTE für manuellen Workflow
# ============================================

def generate_script_only(project):
    """Nur Skript generieren - für manuellen Workflow"""
    from openai import OpenAI
    
    user = project.user
    api_key = user.openai_api_key
    if not api_key:
        raise ValueError("Kein OpenAI API Key hinterlegt")
    
    client = OpenAI(api_key=api_key)
    
    template = project.template
    title = project.title
    duration = project.target_duration
    
    prompt = SCRIPT_PROMPTS.get(template, SCRIPT_PROMPTS['job_intro'])
    prompt = prompt.format(title=title, duration=duration)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.8
    )
    
    script = response.choices[0].message.content.strip()
    
    # Kosten tracken
    from decimal import Decimal
    project.cost_script = Decimal('0.001')
    project.save(update_fields=['cost_script'])
    
    return script


def generate_audio_only(project):
    """Nur Audio generieren - für manuellen Workflow"""
    from openai import OpenAI
    import tempfile
    import os
    from decimal import Decimal
    from django.core.files import File
    
    user = project.user
    api_key = user.openai_api_key
    if not api_key:
        raise ValueError("Kein OpenAI API Key hinterlegt")
    
    client = OpenAI(api_key=api_key)
    
    script = project.script or project.custom_script
    if not script:
        raise ValueError("Kein Skript vorhanden")
    
    voice = project.voice or 'echo'
    
    # TTS generieren
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=script
    )
    
    # Temporäre Datei speichern
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, 'voiceover.mp3')
    response.stream_to_file(audio_path)
    
    # Dauer berechnen
    from pydub import AudioSegment
    audio = AudioSegment.from_mp3(audio_path)
    duration = len(audio) / 1000.0
    
    # TTS Kosten (~$0.015 pro 1000 Zeichen)
    tts_cost = (len(script) / 1000) * 0.015
    project.cost_tts = Decimal(str(round(tts_cost, 6)))
    
    # Audio-Datei im Projekt speichern
    audio_filename = f"vidgen_{project.id}.mp3"
    with open(audio_path, 'rb') as f:
        project.audio_file.save(audio_filename, File(f), save=False)
    
    project.save(update_fields=['cost_tts', 'audio_file'])
    
    # Temp-Datei aufräumen
    try:
        os.remove(audio_path)
        os.rmdir(temp_dir)
    except:
        pass
    
    return project.audio_file.path, duration


def fetch_clips_only(project, custom_keywords=None):
    """Nur Clips suchen - für manuellen Workflow"""
    from .models import PexelsClip
    import requests
    import tempfile
    import os
    
    user = project.user
    api_key = getattr(user, 'pexels_api_key', None)
    if not api_key:
        raise ValueError("Kein Pexels API Key hinterlegt")
    
    # Alte Clips löschen
    project.clips.all().delete()
    
    # Keywords bestimmen
    if custom_keywords and len(custom_keywords) > 0:
        keywords = custom_keywords
    else:
        # Keywords aus Skript extrahieren
        keywords = extract_keywords_for_segments(
            project.script or project.title,
            12,
            user=user
        )
    
    headers = {'Authorization': api_key}
    clips = []
    
    for i, keyword in enumerate(keywords[:12]):
        response = requests.get(
            'https://api.pexels.com/videos/search',
            headers=headers,
            params={'query': keyword, 'per_page': 5, 'orientation': 'portrait'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('videos'):
                video = data['videos'][0]
                
                # Beste Qualität finden
                video_files = sorted(
                    video.get('video_files', []),
                    key=lambda x: x.get('height', 0),
                    reverse=True
                )
                
                if video_files:
                    video_url = video_files[0].get('link')
                    
                    # Video herunterladen
                    temp_dir = tempfile.mkdtemp()
                    clip_path = os.path.join(temp_dir, f'clip_{i}.mp4')
                    
                    video_response = requests.get(video_url)
                    with open(clip_path, 'wb') as f:
                        f.write(video_response.content)
                    
                    # In DB speichern
                    from django.core.files import File
                    clip = PexelsClip.objects.create(
                        project=project,
                        pexels_id=str(video['id']),
                        search_query=keyword,
                        duration=video.get('duration', 0),
                        width=video.get('width', 0),
                        height=video.get('height', 0),
                        order=i
                    )
                    with open(clip_path, 'rb') as f:
                        clip.video_file.save(f'clip_{project.id}_{i}.mp4', File(f))
                    clip.save()
                    clips.append(clip)
    
    return clips


def search_single_clip(project, clip_index, keyword):
    """Einzelnen Clip neu suchen - gibt ANDERES Video zurück"""
    from .models import PexelsClip
    import requests
    import tempfile
    import os
    import random
    
    user = project.user
    api_key = getattr(user, 'pexels_api_key', None)
    if not api_key:
        raise ValueError("Kein Pexels API Key hinterlegt")
    
    headers = {'Authorization': api_key}
    
    # Alte pexels_id holen (falls vorhanden)
    old_clip = project.clips.filter(order=clip_index).first()
    old_pexels_id = old_clip.pexels_id if old_clip else None
    
    response = requests.get(
        'https://api.pexels.com/videos/search',
        headers=headers,
        params={'query': keyword, 'per_page': 15, 'orientation': 'portrait'}  # Mehr Videos holen
    )
    
    if response.status_code != 200:
        raise ValueError(f"Pexels API Fehler: {response.status_code}")
    
    data = response.json()
    if not data.get('videos'):
        raise ValueError(f"Keine Videos gefunden für: {keyword}")
    
    # Versuche ein ANDERES Video zu finden
    videos = data['videos']
    available_videos = [v for v in videos if v['id'] != old_pexels_id]
    
    if available_videos:
        video = random.choice(available_videos)  # Zufälliges ANDERES Video
    else:
        video = videos[0]  # Fallback: erstes Video
    video_files = sorted(
        video.get('video_files', []),
        key=lambda x: x.get('height', 0),
        reverse=True
    )
    
    if not video_files:
        raise ValueError("Keine Video-Dateien verfügbar")
    
    video_url = video_files[0].get('link')
    
    # Video herunterladen
    temp_dir = tempfile.mkdtemp()
    clip_path = os.path.join(temp_dir, f'clip_{clip_index}.mp4')
    
    video_response = requests.get(video_url)
    with open(clip_path, 'wb') as f:
        f.write(video_response.content)
    
    # Alten Clip löschen oder aktualisieren
    old_clip = project.clips.filter(order=clip_index).first()
    if old_clip:
        old_clip.delete()
    
    # Neuen Clip speichern
    from django.core.files import File
    clip = PexelsClip.objects.create(
        project=project,
        pexels_id=str(video['id']),
        search_query=keyword,
        duration=video.get('duration', 0),
        width=video.get('width', 0),
        height=video.get('height', 0),
        order=clip_index
    )
    with open(clip_path, 'rb') as f:
        clip.video_file.save(f'clip_{project.id}_{clip_index}.mp4', File(f))
    clip.save()
    
    return clip


@shared_task
def render_video_only(project_id):
    """Nur Rendering - als Celery Task für manuellen Workflow"""
    from .models import VideoProject
    
    project = VideoProject.objects.get(id=project_id)
    
    try:
        # Hier den bestehenden Render-Code aufrufen
        # Vereinfachte Version - nutzt die bestehende Logik
        project.status = 'rendering'
        project.progress = 70
        project.save()
        
        # ... Render-Logik aus generate_video Task
        # Für jetzt: Task generate_video mit Flag aufrufen
        generate_video(project_id, start_from='render')
        
    except Exception as e:
        project.status = 'failed'
        project.error_message = str(e)
        project.save()


@shared_task(bind=True, soft_time_limit=300, time_limit=330)
def generate_music_task(self, project_id, music_style=None, custom_prompt=None):
    """Celery Task für asynchrone Musikgenerierung"""
    from .models import VideoProject
    
    project = VideoProject.objects.get(id=project_id)
    
    # Projekt aktualisieren
    if music_style:
        project.background_music = music_style
    if custom_prompt:
        project.custom_music_prompt = custom_prompt
    project.save()
    
    try:
        # get_or_generate_music returns tuple (path, was_generated)
        result = get_or_generate_music(project)
        if result is None or result[0] is None:
            return {"success": False, "error": "Keine Musik-Konfiguration"}
        music_path, was_generated = result
        return {
            'success': True,
            'path': music_path,
            'was_generated': was_generated,
            'mood': project.background_music
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
