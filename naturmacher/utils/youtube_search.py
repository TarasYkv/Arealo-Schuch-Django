import requests
import re
from urllib.parse import quote_plus
import time
import random
from bs4 import BeautifulSoup
from .api_helpers import get_user_api_key


def search_youtube_videos_api(query, max_results=3, user=None):
    """
    Sucht nach YouTube-Videos über die offizielle YouTube Data API.
    
    Args:
        query (str): Suchbegriff
        max_results (int): Maximale Anzahl der Ergebnisse (Standard: 3)
        user: Django User object für API-Key-Abfrage
    
    Returns:
        list: Liste mit YouTube-URLs
    """
    try:
        # Hole API-Key für YouTube
        api_key = get_user_api_key(user, 'youtube') if user else None
        
        if not api_key:
            # Fallback zu Web-Scraping wenn kein API-Key verfügbar
            return search_youtube_videos_fallback(query, max_results)
        
        # Bereinige den Suchbegriff
        search_query = clean_search_query(query)
        
        # YouTube Data API v3 URL
        api_url = "https://www.googleapis.com/youtube/v3/search"
        
        # API-Parameter
        params = {
            'part': 'id,snippet',
            'q': search_query,
            'type': 'video',
            'maxResults': max_results,
            'order': 'relevance',
            'regionCode': 'DE',  # Deutsche Ergebnisse bevorzugen
            'relevanceLanguage': 'de',  # Deutsche Sprache bevorzugen
            'safeSearch': 'moderate',
            'key': api_key
        }
        
        # API-Anfrage
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extrahiere Video-URLs
        youtube_urls = []
        for item in data.get('items', []):
            video_id = item['id']['videoId']
            youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
        
        return youtube_urls
        
    except Exception as e:
        print(f"Fehler bei YouTube API-Suche: {e}")
        # Fallback zu Web-Scraping
        return search_youtube_videos_fallback(query, max_results)


def search_youtube_videos_fallback(query, max_results=3):
    """
    Fallback-Funktion für YouTube-Suche über Web-Scraping.
    Wird verwendet wenn kein API-Key verfügbar ist.
    
    Args:
        query (str): Suchbegriff
        max_results (int): Maximale Anzahl der Ergebnisse (Standard: 3)
    
    Returns:
        list: Liste mit YouTube-URLs
    """
    try:
        # Bereinige den Suchbegriff
        search_query = clean_search_query(query)
        
        # Erstelle YouTube-Such-URL
        encoded_query = quote_plus(search_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        
        # Headers für die Anfrage
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Anfrage mit Timeout
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Extrahiere Video-IDs aus der Antwort
        video_ids = extract_video_ids(response.text)
        
        # Konvertiere zu YouTube-URLs
        youtube_urls = []
        for video_id in video_ids[:max_results]:
            youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
        
        return youtube_urls
        
    except Exception as e:
        print(f"Fehler beim Suchen von YouTube-Videos (Fallback): {e}")
        return []


def search_youtube_videos(query, max_results=3, user=None):
    """
    Hauptfunktion für YouTube-Videosuche. 
    Versucht zuerst API, dann Fallback zu Web-Scraping.
    
    Args:
        query (str): Suchbegriff
        max_results (int): Maximale Anzahl der Ergebnisse (Standard: 3)
        user: Django User object für API-Key-Abfrage
    
    Returns:
        list: Liste mit YouTube-URLs
    """
    return search_youtube_videos_api(query, max_results, user)


def clean_search_query(query):
    """
    Bereinigt den Suchbegriff für bessere YouTube-Suchergebnisse.
    
    Args:
        query (str): Ursprünglicher Suchbegriff
    
    Returns:
        str: Bereinigter Suchbegriff
    """
    # Entferne HTML-Tags
    query = re.sub(r'<[^>]+>', '', query)
    
    # Entferne Sonderzeichen und Zahlen am Anfang
    query = re.sub(r'^\d+\.\s*', '', query)
    
    # Entferne "Schulung", "Training", "Übung" etc.
    query = re.sub(r'\b(Schulung|Training|Übung|Lektion|Kapitel)\b', '', query, flags=re.IGNORECASE)
    
    # Ersetze Umlaute und Sonderzeichen
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
    }
    for old, new in replacements.items():
        query = query.replace(old, new)
    
    # Entferne mehrfache Leerzeichen
    query = re.sub(r'\s+', ' ', query).strip()
    
    # Füge nur minimal relevante Schlüsselwörter hinzu für bessere Ergebnisse
    if query:
        query += " tutorial deutsch"
    
    return query


def extract_video_ids(html_content):
    """
    Extrahiert Video-IDs aus dem HTML-Inhalt der YouTube-Suchergebnisse.
    
    Args:
        html_content (str): HTML-Inhalt der YouTube-Suchseite
    
    Returns:
        list: Liste mit Video-IDs
    """
    video_ids = []
    
    # Verschiedene Regex-Muster für Video-IDs
    patterns = [
        r'"videoId":"([^"]+)"',
        r'watch\?v=([^"&]+)',
        r'/watch\?v=([^"&]+)',
        r'videoId["\']:\s*["\']([^"\']+)["\']'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        for match in matches:
            if len(match) == 11 and match not in video_ids:  # YouTube Video-IDs sind 11 Zeichen lang
                video_ids.append(match)
    
    return video_ids


def get_youtube_videos_for_training(training_title, training_description="", thema_name="", user=None):
    """
    Findet passende YouTube-Videos für ein Training.
    
    Args:
        training_title (str): Titel des Trainings
        training_description (str): Beschreibung des Trainings
        thema_name (str): Name des Themas
        user: Django User object für API-Key-Abfrage
    
    Returns:
        list: Liste mit YouTube-URLs
    """
    # Erstelle verschiedene Suchbegriffe - Priorität auf Schulungstitel
    search_queries = []
    
    # 1. Hauptsuchbegriff: Nur der Schulungstitel (höchste Priorität)
    if training_title:
        search_queries.append(training_title)
    
    # 2. Fallback: Titel + Thema (falls der Titel allein nicht genug Ergebnisse liefert)
    if training_title and thema_name and len(search_queries) < 2:
        search_queries.append(f"{training_title} {thema_name}")
    
    # 3. Letzter Fallback: Beschreibung (nur wenn Titel nicht verfügbar)
    if not training_title and training_description:
        desc_words = training_description.split()[:3]  # Reduziert auf 3 Wörter für fokussiertere Suche
        search_queries.append(" ".join(desc_words))
    
    # Sammle alle gefundenen Videos
    all_videos = []
    
    for query in search_queries:
        if query.strip():
            videos = search_youtube_videos(query, max_results=2, user=user)
            all_videos.extend(videos)
            
            # Kleine Pause zwischen Anfragen (nur bei Web-Scraping nötig)
            if not user or not get_user_api_key(user, 'youtube'):
                time.sleep(random.uniform(0.5, 1.5))
    
    # Entferne Duplikate und begrenze auf 3 Videos
    unique_videos = []
    seen_ids = set()
    
    for video_url in all_videos:
        video_id = extract_video_id_from_url(video_url)
        if video_id and video_id not in seen_ids:
            unique_videos.append(video_url)
            seen_ids.add(video_id)
            
            if len(unique_videos) >= 3:
                break
    
    return unique_videos


def extract_video_id_from_url(url):
    """
    Extrahiert die Video-ID aus einer YouTube-URL.
    
    Args:
        url (str): YouTube-URL
    
    Returns:
        str: Video-ID oder None
    """
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&\n?#]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^&\n?#]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def validate_youtube_urls(urls):
    """
    Validiert eine Liste von YouTube-URLs.
    
    Args:
        urls (list): Liste mit YouTube-URLs
    
    Returns:
        list: Liste mit gültigen YouTube-URLs
    """
    valid_urls = []
    
    for url in urls:
        video_id = extract_video_id_from_url(url)
        if video_id and len(video_id) == 11:
            # Stelle sicher, dass die URL im korrekten Format ist
            clean_url = f"https://www.youtube.com/watch?v={video_id}"
            valid_urls.append(clean_url)
    
    return valid_urls