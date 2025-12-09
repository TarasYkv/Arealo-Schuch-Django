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
        Jede Frage enthält ihre Herkunft (source)
        """
        all_questions = []  # Liste von dicts: {'question': str, 'source': str}
        sources_used = []

        # 1. Google Autocomplete (Hauptquelle)
        try:
            google_questions = self._get_google_autocomplete_questions(keyword)
            if google_questions:
                for q in google_questions:
                    all_questions.append({'question': q, 'source': 'google'})
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
                existing = [q['question'] for q in all_questions]
                for q in reddit_questions:
                    if q not in existing:
                        all_questions.append({'question': q, 'source': 'reddit'})
                sources_used.append('reddit')
                logger.info(f"Reddit: {len(reddit_questions)} Fragen gefunden")
        except Exception as e:
            logger.error(f"Reddit Fehler: {e}")

        # Kleine Pause
        time.sleep(random.uniform(0.5, 1.0))

        # 3. StackExchange deaktiviert (NICHT auf PythonAnywhere Whitelist)
        # try:
        #     stackexchange_questions = self._get_stackexchange_questions(keyword)
        #     ...
        # except Exception as e:
        #     logger.error(f"StackExchange Fehler: {e}")

        # Duplikate entfernen
        unique_questions = self._deduplicate_questions_with_source(all_questions)

        logger.info(f"Gesamt: {len(unique_questions)} einzigartige Fragen aus {sources_used}")

        return {
            'success': True,
            'paa_questions': unique_questions[:25],
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
        Sucht Fragen auf Reddit (international)
        Fragen werden später von der KI übersetzt
        """
        questions = []

        # Reddit benötigt einen spezifischen User-Agent
        reddit_headers = {
            'User-Agent': 'python:questionfinder:v1.0 (by /u/workloom)',
            'Accept': 'application/json',
        }

        try:
            # Globale Reddit-Suche
            url = "https://www.reddit.com/search.json"
            params = {
                'q': keyword,
                'sort': 'relevance',
                'limit': 25,
                't': 'year',  # Letztes Jahr
                'type': 'link',
            }

            logger.info(f"Reddit: Suche '{keyword}' auf www.reddit.com")

            response = self.session.get(
                url,
                params=params,
                headers=reddit_headers,
                timeout=self.timeout
            )

            logger.info(f"Reddit: Status={response.status_code}, Länge={len(response.text)}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    posts = data.get('data', {}).get('children', [])
                    logger.info(f"Reddit: {len(posts)} Posts in Response")

                    for post in posts:
                        post_data = post.get('data', {})
                        title = post_data.get('title', '')
                        subreddit = post_data.get('subreddit', '')

                        if title and len(title) > 10:
                            cleaned = self._clean_question(title)
                            if cleaned and len(cleaned) > 15 and cleaned not in questions:
                                questions.append(cleaned)
                                logger.debug(f"Reddit r/{subreddit}: {cleaned[:50]}...")

                except json.JSONDecodeError as e:
                    logger.error(f"Reddit: JSON Parse Error: {e}")
                    logger.error(f"Reddit Response (first 500 chars): {response.text[:500]}")

            elif response.status_code == 403:
                logger.error("Reddit: 403 Forbidden - User-Agent Problem?")
            elif response.status_code == 429:
                logger.error("Reddit: 429 Rate-Limit - Zu viele Anfragen")
            else:
                logger.error(f"Reddit: Unerwarteter Status {response.status_code}")
                logger.error(f"Reddit Response: {response.text[:200]}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Reddit: ConnectionError - {str(e)[:100]}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Reddit: Timeout - {e}")
        except Exception as e:
            logger.error(f"Reddit: {type(e).__name__}: {e}", exc_info=True)

        logger.info(f"Reddit: {len(questions)} Fragen extrahiert")
        return questions[:15]

    def _get_stackexchange_questions(self, keyword: str) -> List[str]:
        """
        Sucht Fragen auf StackExchange (stackoverflow, superuser, etc.)
        API ist kostenlos und auf PythonAnywhere Whitelist
        """
        questions = []

        # StackExchange Sites für deutsche/allgemeine Fragen
        sites = ['stackoverflow', 'superuser', 'askubuntu']

        try:
            # StackExchange API - kostenlos, kein Key nötig für einfache Suchen
            url = "https://api.stackexchange.com/2.3/search"
            params = {
                'order': 'desc',
                'sort': 'relevance',
                'intitle': keyword,
                'site': 'stackoverflow',
                'pagesize': 20,
                'filter': 'default',
            }

            logger.info(f"StackExchange: Anfrage für '{keyword}'")

            response = self.session.get(
                url,
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )

            logger.info(f"StackExchange: Status {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    items = data.get('items', [])
                    logger.info(f"StackExchange: {len(items)} Fragen gefunden")

                    for item in items:
                        title = item.get('title', '')
                        if title and len(title) > 10:
                            # HTML-Entities dekodieren
                            import html
                            title = html.unescape(title)
                            cleaned = self._clean_question(title)
                            if cleaned and cleaned not in questions:
                                questions.append(cleaned)

                except json.JSONDecodeError as e:
                    logger.error(f"StackExchange: JSON Parse Error: {e}")

            elif response.status_code == 400:
                logger.warning("StackExchange: Bad Request (400)")
            else:
                logger.warning(f"StackExchange: Status {response.status_code}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"StackExchange: Verbindungsfehler: {e}")
        except Exception as e:
            logger.error(f"StackExchange Fehler: {type(e).__name__}: {e}")

        logger.info(f"StackExchange gesamt: {len(questions)} Fragen gefunden")
        return questions[:10]

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
        """Entfernt ähnliche Duplikate (für einfache String-Listen)"""
        unique = []
        for q in questions:
            q_lower = q.lower()
            is_duplicate = False
            for existing in unique:
                existing_lower = existing.lower()
                if q_lower in existing_lower or existing_lower in q_lower:
                    is_duplicate = True
                    break
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

    def _deduplicate_questions_with_source(self, questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Entfernt ähnliche Duplikate (für Fragen mit Source-Info)"""
        unique = []
        for item in questions:
            q = item['question']
            q_lower = q.lower()
            is_duplicate = False
            for existing_item in unique:
                existing_lower = existing_item['question'].lower()
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
                unique.append(item)
        return unique


# Alias für Kompatibilität mit bestehendem Code
class GoogleQuestionScraper(MultiSourceQuestionFinder):
    """Alias für Abwärtskompatibilität"""
    pass
