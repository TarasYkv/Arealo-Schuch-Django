"""
Online-News-Recherche für den Radiosender.

Sucht via Gemini (Google-Search-Grounding, vorhandener Gemini-Key) aktuelle
Nachrichten zu den in den Einstellungen hinterlegten Themen. Die Zusammen-
fassung in radiotauglichen Text macht anschließend GLM 5.1 (siehe tasks.fetch_news).
"""
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

SEARCH_MODEL = 'gemini-2.5-flash'


def web_research(query, timeout=90):
    """Allgemeine Web-Recherche via Gemini-Google-Search-Grounding.
    Gibt eine kurze, faktische Zusammenfassung (Text) zur Anfrage zurück – oder ''."""
    from . import gemini_tts
    key = gemini_tts.get_gemini_key()
    prompt = (
        f'Recherchiere im Web und beantworte knapp und faktisch (deutsch): {query}\n'
        f'Gib eine kurze Zusammenfassung der wichtigsten, aktuellen Fakten. '
        f'Nenne wenn möglich Quelle/Datum. Wenn du nichts Belastbares findest, sage das.'
    )
    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'tools': [{'google_search': {}}],
    }).encode()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{SEARCH_MODEL}:generateContent?key={key}'
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        parts = r['candidates'][0]['content']['parts']
        return ''.join(p.get('text', '') for p in parts).strip()
    except Exception as e:
        logger.warning(f'Web-Recherche "{query}" fehlgeschlagen: {str(e)[:150]}')
        return ''


def search_topic(topic, max_items=3):
    """Liefert rohe, aktuelle Nachrichten-Stichpunkte zu einem Thema (Gemini-Grounding)."""
    from . import gemini_tts
    key = gemini_tts.get_gemini_key()
    from datetime import date as _d
    _today = _d.today().strftime('%d.%m.%Y')
    prompt = (
        f'Heute ist der {_today}. Suche die {max_items} wichtigsten AKTUELLEN Nachrichten '
        f'der letzten 7 Tage zum Thema "{topic}" (deutschsprachiger Raum bevorzugt). '
        f'Gib je Nachricht 1–2 Sätze MIT konkretem Datum als Stichpunkte: was genau ist '
        f'passiert, wer ist beteiligt. NUR echte, datierte, aktuelle Meldungen/Ereignisse – '
        f'KEINE allgemeinen Ratgeber-Tipps, Saison-Hinweise oder zeitlosen Aussagen. '
        f'Findest du keine echte aktuelle Meldung, antworte nur mit "KEINE".'
    )
    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'tools': [{'google_search': {}}],
    }).encode()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{SEARCH_MODEL}:generateContent?key={key}'
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=90).read())
        parts = r['candidates'][0]['content']['parts']
        return ''.join(p.get('text', '') for p in parts).strip()
    except Exception as e:
        logger.warning(f'News-Suche "{topic}" fehlgeschlagen: {str(e)[:150]}')
        return ''
