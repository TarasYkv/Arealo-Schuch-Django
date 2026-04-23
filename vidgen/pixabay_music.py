"""
Pixabay Music API Integration für VidGen
Kostenlose lizenzfreie Musik von Pixabay
"""
import requests
import os
import tempfile


# Mood-Mapping zu Pixabay-Kategorien
MOOD_TO_CATEGORY = {
    'happy': 'beats',
    'chill': 'ambient',
    'dramatic': 'cinematic',
    'corporate': 'corporate',
    'inspiring': 'inspiring',
    'romantic': 'romantic',
    'sad': 'ambient',
    'energetic': 'beats',
    'calm': 'ambient',
}


def get_pixabay_music(
    api_key: str,
    mood: str = 'corporate',
    min_duration: int = 30,
    max_duration: int = 300,
) -> tuple[str | None, dict | None]:
    """
    Holt einen passenden Musik-Track von Pixabay.
    
    Args:
        api_key: Pixabay API Key
        mood: Stimmung (happy, chill, dramatic, etc.)
        min_duration: Minimale Dauer in Sekunden
        max_duration: Maximale Dauer in Sekunden
    
    Returns:
        tuple: (filepath, track_info) oder (None, None) bei Fehler
    """
    
    category = MOOD_TO_CATEGORY.get(mood, 'corporate')
    
    # Pixabay Music API
    url = "https://pixabay.com/api/videos/music/"
    params = {
        'key': api_key,
        'q': category,
        'min_duration': min_duration,
        'max_duration': max_duration,
        'order': 'popular',
        'per_page': 10,
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('hits'):
            print(f"Keine Pixabay-Musik gefunden für mood={mood}")
            return None, None
        
        # Ersten passenden Track nehmen
        track = data['hits'][0]
        audio_url = track.get('audio')
        
        if not audio_url:
            print("Kein Audio-URL in Pixabay-Response")
            return None, None
        
        # Download
        audio_response = requests.get(audio_url, timeout=60)
        audio_response.raise_for_status()
        
        # Temporäre Datei
        fd, filepath = tempfile.mkstemp(suffix='.mp3')
        with os.fdopen(fd, 'wb') as f:
            f.write(audio_response.content)
        
        track_info = {
            'id': track.get('id'),
            'title': track.get('tags', 'Unknown'),
            'duration': track.get('duration'),
            'source': 'pixabay',
        }
        
        print(f"Pixabay-Musik heruntergeladen: {track_info['title']} ({track_info['duration']}s)")
        return filepath, track_info
        
    except requests.RequestException as e:
        print(f"Pixabay API Fehler: {e}")
        return None, None
    except Exception as e:
        print(f"Pixabay Fehler: {e}")
        return None, None
