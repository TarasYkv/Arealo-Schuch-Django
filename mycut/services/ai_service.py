# mycut/services/ai_service.py

"""
AI-Service für MyCut Video-Editor.
Verwendet OpenAI Whisper API für Transkription und Analyse.
"""

import logging
import re
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


# Filler-Wörter für verschiedene Sprachen
FILLER_WORDS = {
    'de': [
        'ähm', 'äh', 'ehm', 'eh', 'hm', 'hmm',
        'also', 'quasi', 'halt', 'irgendwie', 'sozusagen',
        'eigentlich', 'praktisch', 'gewissermaßen', 'so',
        'ja', 'ne', 'nee', 'gell', 'oder', 'weißt du',
    ],
    'en': [
        'um', 'uh', 'uhm', 'er', 'ah', 'hmm',
        'like', 'basically', 'actually', 'literally',
        'you know', 'I mean', 'kind of', 'sort of',
        'right', 'so', 'well', 'anyway',
    ],
}


class MyCutAIService:
    """
    AI-Service für Transkription und Analyse.
    """

    def __init__(self, user):
        """
        Initialisiert den Service mit User-spezifischem API-Key.

        Args:
            user: Django User-Objekt mit openai_api_key Attribut
        """
        self.user = user
        self.client = None

        # API-Key aus User-Profil laden
        api_key = getattr(user, 'openai_api_key', None)
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            logger.warning(f"User {user.username} has no OpenAI API key configured")

    def is_available(self) -> bool:
        """Prüft ob der Service verfügbar ist."""
        return self.client is not None

    def transcribe_audio(self, audio_path: str, language: str = 'de') -> dict:
        """
        Transkribiert Audio mit OpenAI Whisper API.

        Args:
            audio_path: Pfad zur Audio-Datei (WAV, MP3, etc.)
            language: Sprache für die Transkription

        Returns:
            dict mit:
                - text: Vollständige Transkription
                - segments: Liste von Segmenten mit Timestamps
                - language: Erkannte Sprache
                - words: Wort-Level-Timestamps (wenn verfügbar)
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        try:
            with open(audio_path, 'rb') as audio_file:
                # Whisper API mit verbose_json für Wort-Timestamps
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"]
                )

            # Response zu dict konvertieren
            result = {
                'text': response.text,
                'language': getattr(response, 'language', language),
                'duration': getattr(response, 'duration', 0),
                'segments': [],
                'words': [],
            }

            # Segmente extrahieren
            if hasattr(response, 'segments') and response.segments:
                for seg in response.segments:
                    segment_data = {
                        'id': getattr(seg, 'id', 0),
                        'start': getattr(seg, 'start', 0) * 1000,  # in ms
                        'end': getattr(seg, 'end', 0) * 1000,
                        'text': getattr(seg, 'text', '').strip(),
                    }
                    result['segments'].append(segment_data)

            # Wort-Timestamps extrahieren
            if hasattr(response, 'words') and response.words:
                for word in response.words:
                    word_data = {
                        'word': getattr(word, 'word', ''),
                        'start': getattr(word, 'start', 0) * 1000,  # in ms
                        'end': getattr(word, 'end', 0) * 1000,
                    }
                    result['words'].append(word_data)

            logger.info(f"Transcription completed: {len(result['segments'])} segments, {len(result['words'])} words")
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def detect_filler_words(self, transcription: dict, language: str = 'de') -> list:
        """
        Erkennt Filler-Wörter in der Transkription.

        Args:
            transcription: Ergebnis von transcribe_audio()
            language: Sprache für Filler-Wort-Liste

        Returns:
            Liste von dict mit:
                - type: 'filler_word'
                - start_time: Start in ms
                - end_time: Ende in ms
                - text: Erkanntes Wort
                - confidence: Konfidenz (0-1)
        """
        suggestions = []
        filler_list = FILLER_WORDS.get(language, FILLER_WORDS['de'])

        words = transcription.get('words', [])

        for word_data in words:
            word = word_data.get('word', '').lower().strip()
            # Satzzeichen entfernen
            word_clean = re.sub(r'[^\w\säöüß]', '', word)

            if word_clean in filler_list:
                suggestions.append({
                    'type': 'filler_word',
                    'start_time': word_data.get('start', 0),
                    'end_time': word_data.get('end', 0),
                    'text': word_data.get('word', ''),
                    'confidence': 0.9,  # Hohe Konfidenz bei exakter Übereinstimmung
                })

        logger.info(f"Detected {len(suggestions)} filler words")
        return suggestions

    def detect_silence_from_transcription(self, transcription: dict, min_gap_ms: float = 1000) -> list:
        """
        Erkennt Stille/Pausen basierend auf Lücken in der Transkription.

        Args:
            transcription: Ergebnis von transcribe_audio()
            min_gap_ms: Mindestdauer einer Pause in ms

        Returns:
            Liste von dict mit Pausen-Informationen
        """
        suggestions = []
        words = transcription.get('words', [])

        if len(words) < 2:
            return suggestions

        for i in range(1, len(words)):
            prev_end = words[i - 1].get('end', 0)
            curr_start = words[i].get('start', 0)
            gap = curr_start - prev_end

            if gap >= min_gap_ms:
                suggestions.append({
                    'type': 'silence',
                    'start_time': prev_end,
                    'end_time': curr_start,
                    'text': f'{gap / 1000:.1f}s Pause',
                    'confidence': 0.85,
                    'duration_ms': gap,
                })

        logger.info(f"Detected {len(suggestions)} silence gaps")
        return suggestions

    def analyze_speech_speed(self, transcription: dict, window_ms: float = 5000) -> list:
        """
        Analysiert die Sprechgeschwindigkeit und findet langsame Abschnitte.

        Args:
            transcription: Ergebnis von transcribe_audio()
            window_ms: Fensterbreite für die Analyse

        Returns:
            Liste von Speed-Änderungs-Vorschlägen
        """
        suggestions = []
        words = transcription.get('words', [])

        if len(words) < 5:
            return suggestions

        # Wörter pro Minute berechnen (Durchschnitt)
        total_duration = words[-1].get('end', 0) - words[0].get('start', 0)
        if total_duration <= 0:
            return suggestions

        avg_wpm = len(words) / (total_duration / 60000)

        # Sliding Window für lokale WPM
        for i in range(0, len(words) - 5, 3):
            window_words = words[i:i + 10]
            if len(window_words) < 5:
                continue

            window_start = window_words[0].get('start', 0)
            window_end = window_words[-1].get('end', 0)
            window_duration = window_end - window_start

            if window_duration <= 0:
                continue

            local_wpm = len(window_words) / (window_duration / 60000)

            # Wenn deutlich langsamer als Durchschnitt (< 70%)
            if local_wpm < avg_wpm * 0.7:
                speed_factor = min(1.5, avg_wpm / local_wpm)
                suggestions.append({
                    'type': 'speed_up',
                    'start_time': window_start,
                    'end_time': window_end,
                    'text': f'Langsamer Abschnitt ({local_wpm:.0f} WPM)',
                    'confidence': 0.7,
                    'suggested_value': round(speed_factor, 2),
                })

        logger.info(f"Detected {len(suggestions)} slow speech sections")
        return suggestions

    def analyze_for_auto_edit(self, transcription: dict, language: str = 'de') -> dict:
        """
        Führt alle Analysen durch und gibt kombinierte Vorschläge zurück.

        Args:
            transcription: Ergebnis von transcribe_audio()
            language: Sprache

        Returns:
            dict mit allen Vorschlägen kategorisiert
        """
        return {
            'filler_words': self.detect_filler_words(transcription, language),
            'silence': self.detect_silence_from_transcription(transcription),
            'speed_changes': self.analyze_speech_speed(transcription),
            'total_suggestions': 0,  # Wird unten aktualisiert
        }
