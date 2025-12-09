import requests
import re
import time
import random
import logging
from urllib.parse import quote_plus, quote
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import json

logger = logging.getLogger(__name__)


class MultiSourceQuestionFinder:
    """
    Findet Fragen aus mehreren Quellen:
    1. Google Autocomplete (Hauptquelle)
    2. Reddit API (r/FragReddit, r/de)
    3. Quora Scraping
    """

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.timeout = 15

    def search_questions(self, keyword: str, language: str = 'de') -> Dict[str, Any]:
        """
        Sucht nach Fragen aus allen Quellen
        """
        all_questions = []
        sources_used = []

        # 1. Google Autocomplete (Hauptquelle)
        try:
            google_questions = self._get_google_autocomplete_questions(keyword)
            if google_questions:
                all_questions.extend(google_questions)
                sources_used.append('google_autocomplete')
                logger.info(f"Google Autocomplete: {len(google_questions)} Fragen gefunden")
        except Exception as e:
            logger.error(f"Google Autocomplete Fehler: {e}")

        # Kleine Pause zwischen Anfragen
        time.sleep(random.uniform(0.5, 1.0))

        # 2. Reddit API
        try:
            reddit_questions = self._get_reddit_questions(keyword)
            if reddit_questions:
                all_questions.extend([q for q in reddit_questions if q not in all_questions])
                sources_used.append('reddit')
                logger.info(f"Reddit: {len(reddit_questions)} Fragen gefunden")
        except Exception as e:
            logger.error(f"Reddit Fehler: {e}")

        # Kleine Pause
        time.sleep(random.uniform(0.5, 1.0))

        # 3. Quora
        try:
            quora_questions = self._get_quora_questions(keyword)
            if quora_questions:
                all_questions.extend([q for q in quora_questions if q not in all_questions])
                sources_used.append('quora')
                logger.info(f"Quora: {len(quora_questions)} Fragen gefunden")
        except Exception as e:
            logger.error(f"Quora Fehler: {e}")

        # Duplikate entfernen und sortieren
        unique_questions = self._deduplicate_questions(all_questions)

        logger.info(f"Gesamt: {len(unique_questions)} einzigartige Fragen aus {sources_used}")

        return {
            'success': True,
            'paa_questions': unique_questions[:20],
            'related_questions': [],
            'keyword': keyword,
            'sources': sources_used,
            'source': ', '.join(sources_used) if sources_used else 'none'
        }

    def _get_google_autocomplete_questions(self, keyword: str) -> List[str]:
        """
        Holt Fragen via Google Autocomplete API
        Kombiniert Keyword mit deutschen Fragewörtern
        """
        questions = []

        # Deutsche Frage-Präfixe (wie AnswerThePublic)
        question_prefixes = [
            'was ist', 'was sind', 'was bedeutet', 'was kostet', 'was macht',
            'wie', 'wie funktioniert', 'wie macht man', 'wie lange', 'wie viel',
            'warum', 'warum ist', 'warum gibt es',
            'wann', 'wann sollte', 'wann ist',
            'wo', 'wo kann man', 'wo gibt es', 'wo bekommt man',
            'wer', 'wer kann', 'wer macht',
            'welche', 'welcher', 'welches',
            'kann man', 'ist', 'sind', 'gibt es',
        ]

        # Auch Keyword + Fragewort am Ende
        question_suffixes = [
            'was ist das', 'wie funktioniert', 'kosten', 'erfahrungen',
            'vorteile', 'nachteile', 'vergleich', 'alternative',
            'tipps', 'anleitung', 'kaufen', 'test',
        ]

        # Präfix-Suchen
        for prefix in question_prefixes[:15]:  # Limit um Rate-Limiting zu vermeiden
            try:
                query = f"{prefix} {keyword}"
                suggestions = self._fetch_google_suggestions(query)
                for s in suggestions:
                    if self._is_question(s) or prefix.startswith(('was', 'wie', 'warum', 'wann', 'wo', 'wer')):
                        cleaned = self._clean_question(s)
                        if cleaned and cleaned not in questions:
                            questions.append(cleaned)

                time.sleep(random.uniform(0.1, 0.3))
            except Exception as e:
                logger.debug(f"Autocomplete für '{prefix}' fehlgeschlagen: {e}")
                continue

        # Suffix-Suchen
        for suffix in question_suffixes[:8]:
            try:
                query = f"{keyword} {suffix}"
                suggestions = self._fetch_google_suggestions(query)
                for s in suggestions:
                    cleaned = self._clean_question(s)
                    if cleaned and cleaned not in questions:
                        # Als Frage formatieren wenn nötig
                        if not cleaned.endswith('?'):
                            cleaned = f"Was ist {cleaned}?" if 'ist' not in cleaned.lower() else cleaned
                        questions.append(cleaned)

                time.sleep(random.uniform(0.1, 0.3))
            except Exception:
                continue

        return questions

    def _fetch_google_suggestions(self, query: str) -> List[str]:
        """
        Holt Suggestions von Google Autocomplete API
        """
        url = f"https://suggestqueries.google.com/complete/search"
        params = {
            'client': 'firefox',  # Gibt JSON zurück
            'q': query,
            'hl': 'de',
            'gl': 'de',
        }

        response = self.session.get(
            url,
            params=params,
            headers=self.headers,
            timeout=self.timeout
        )

        if response.status_code == 200:
            data = response.json()
            if len(data) > 1 and isinstance(data[1], list):
                return data[1]
        return []

    def _get_reddit_questions(self, keyword: str) -> List[str]:
        """
        Sucht Fragen auf Reddit (r/FragReddit, r/de, r/germany)
        """
        questions = []

        # Suche in deutschen Subreddits
        subreddits = ['FragReddit', 'de', 'germany']

        for subreddit in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/search.json"
                params = {
                    'q': keyword,
                    'restrict_sr': 'on',
                    'sort': 'relevance',
                    'limit': 25,
                }

                response = self.session.get(
                    url,
                    params=params,
                    headers={'User-Agent': 'QuestionFinder/1.0'},
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get('data', {}).get('children', [])

                    for post in posts:
                        title = post.get('data', {}).get('title', '')
                        if title and self._is_question(title):
                            cleaned = self._clean_question(title)
                            if cleaned and len(cleaned) > 15 and cleaned not in questions:
                                questions.append(cleaned)

                time.sleep(random.uniform(0.5, 1.0))  # Reddit Rate-Limit beachten

            except Exception as e:
                logger.debug(f"Reddit r/{subreddit} Fehler: {e}")
                continue

        return questions[:15]  # Max 15 Reddit-Fragen

    def _get_quora_questions(self, keyword: str) -> List[str]:
        """
        Scrapet Fragen von Quora
        """
        questions = []

        try:
            # Quora Suche
            search_url = f"https://www.quora.com/search?q={quote_plus(keyword)}"

            response = self.session.get(
                search_url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Quora Frage-Selektoren (können sich ändern)
                selectors = [
                    'span.q-text',
                    'a.q-box span',
                    'div.q-text span',
                    'span[class*="question"]',
                ]

                for selector in selectors:
                    try:
                        elements = soup.select(selector)
                        for el in elements:
                            text = el.get_text(strip=True)
                            if self._is_question(text):
                                cleaned = self._clean_question(text)
                                if cleaned and len(cleaned) > 15 and cleaned not in questions:
                                    questions.append(cleaned)
                    except Exception:
                        continue

                # Fallback: Suche nach Frage-Patterns im HTML
                if not questions:
                    text_content = soup.get_text()
                    question_pattern = r'([A-ZÄÖÜ][^.!?\n]{15,120}\?)'
                    matches = re.findall(question_pattern, text_content)
                    for match in matches:
                        cleaned = self._clean_question(match)
                        if cleaned and keyword.lower() in cleaned.lower():
                            if cleaned not in questions:
                                questions.append(cleaned)

        except Exception as e:
            logger.debug(f"Quora Fehler: {e}")

        return questions[:10]  # Max 10 Quora-Fragen

    def _is_question(self, text: str) -> bool:
        """Prüft ob ein Text eine Frage ist"""
        if not text or len(text) < 10:
            return False

        question_starters = [
            'was ', 'wie ', 'warum ', 'wann ', 'wo ', 'wer ', 'welche ', 'welcher ', 'welches ',
            'kann ', 'kannst ', 'ist ', 'sind ', 'hat ', 'haben ', 'gibt ', 'soll ', 'muss ', 'darf ',
            'what ', 'how ', 'why ', 'when ', 'where ', 'who ', 'which ', 'can ', 'is ', 'are ',
            'kennt ', 'weiß ', 'habt ', 'sollte ', 'könnte ', 'würde ',
        ]
        text_lower = text.lower().strip()

        return text.endswith('?') or any(text_lower.startswith(q) for q in question_starters)

    def _clean_question(self, text: str) -> str:
        """Bereinigt eine Frage"""
        if not text:
            return ""

        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)

        # Entferne führende Zahlen/Aufzählungen
        text = re.sub(r'^\d+[\.\)]\s*', '', text)

        # Entferne Reddit-typische Prefixe
        text = re.sub(r'^\[.*?\]\s*', '', text)
        text = re.sub(r'^r/\w+\s*', '', text)

        # Füge Fragezeichen hinzu wenn nötig
        if not text.endswith('?') and self._is_question(text):
            text += '?'

        return text

    def _deduplicate_questions(self, questions: List[str]) -> List[str]:
        """Entfernt ähnliche Duplikate"""
        unique = []
        for q in questions:
            q_lower = q.lower()
            # Prüfe ob sehr ähnliche Frage bereits existiert
            is_duplicate = False
            for existing in unique:
                existing_lower = existing.lower()
                # Einfacher Ähnlichkeitscheck
                if q_lower in existing_lower or existing_lower in q_lower:
                    is_duplicate = True
                    break
                # Oder wenn 80% der Wörter gleich sind
                q_words = set(q_lower.split())
                existing_words = set(existing_lower.split())
                if len(q_words) > 3 and len(existing_words) > 3:
                    overlap = len(q_words & existing_words) / min(len(q_words), len(existing_words))
                    if overlap > 0.8:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique.append(q)

        return unique


# Alias für Kompatibilität mit bestehendem Code
class GoogleQuestionScraper(MultiSourceQuestionFinder):
    """Alias für Abwärtskompatibilität"""
    pass
