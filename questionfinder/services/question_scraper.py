import requests
import re
import time
import random
import logging
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class GoogleQuestionScraper:
    """
    Scraper für Google People Also Ask und verwandte Fragen
    """

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.timeout = 15

    def search_questions(self, keyword: str, language: str = 'de') -> Dict[str, Any]:
        """
        Sucht nach Fragen zu einem Keyword

        Returns:
            {
                'success': bool,
                'paa_questions': List[str],      # People Also Ask
                'related_questions': List[str],  # Related Searches
                'error': str (optional)
            }
        """
        try:
            # Google-Suche durchführen
            encoded_keyword = quote_plus(keyword)

            # Google-Domain für DE
            search_url = f"https://www.google.de/search?q={encoded_keyword}&hl=de&gl=de"

            response = self.session.get(
                search_url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            # Kurze Pause um Rate-Limiting zu vermeiden
            time.sleep(random.uniform(1.0, 2.5))

            # HTML parsen
            soup = BeautifulSoup(response.text, 'html.parser')

            # PAA extrahieren
            paa_questions = self._extract_paa_questions(soup)

            # Related Searches extrahieren
            related_questions = self._extract_related_searches(soup)

            logger.info(f"Gefunden: {len(paa_questions)} PAA, {len(related_questions)} Related für '{keyword}'")

            return {
                'success': True,
                'paa_questions': paa_questions,
                'related_questions': related_questions,
                'keyword': keyword
            }

        except requests.RequestException as e:
            logger.error(f"Request-Fehler bei Google-Suche: {e}")
            return {
                'success': False,
                'error': f'Netzwerkfehler: {str(e)}',
                'paa_questions': [],
                'related_questions': []
            }
        except Exception as e:
            logger.error(f"Fehler beim Scraping: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Fehler: {str(e)}',
                'paa_questions': [],
                'related_questions': []
            }

    def _extract_paa_questions(self, soup: BeautifulSoup) -> List[str]:
        """
        Extrahiert People Also Ask Fragen aus dem HTML
        """
        questions = []

        # PAA-Container suchen (Google ändert Selektoren regelmäßig)
        # Mehrere Selektoren versuchen
        paa_selectors = [
            'div[data-sgrd]',
            'div.related-question-pair',
            'div[jsname="Cpkphb"]',
            'div.ULSxyf',
            'g-accordion-expander',
            'div[data-hveid] span',
        ]

        for selector in paa_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)

                if self._is_question(text) and text not in questions:
                    cleaned = self._clean_question(text)
                    if cleaned and len(cleaned) > 10 and len(cleaned) < 200:
                        questions.append(cleaned)

        # Alternative: Direkt nach Frage-Patterns suchen
        if not questions:
            all_text = soup.get_text()
            question_patterns = [
                r'((?:Was|Wie|Warum|Wann|Wo|Wer|Welche|Kann|Ist|Sind|Hat|Haben|Gibt)[^.!?]{10,150}\?)',
                r'((?:What|How|Why|When|Where|Who|Which|Can|Is|Are|Does|Do)[^.!?]{10,150}\?)'
            ]

            for pattern in question_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                for match in matches:
                    cleaned = self._clean_question(match)
                    if cleaned and len(cleaned) > 10 and cleaned not in questions:
                        questions.append(cleaned)

        return questions[:15]

    def _extract_related_searches(self, soup: BeautifulSoup) -> List[str]:
        """
        Extrahiert verwandte Suchen von Google
        """
        related = []

        # Related Searches Container
        related_selectors = [
            'div.k8XOCe',
            'div.s75CSd',
            'a.k8XOCe span',
            'div.brs_col span',
            'div[data-ved] a span',
        ]

        for selector in related_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 3 and len(text) < 100 and text not in related:
                    related.append(text)

        return related[:10]

    def _is_question(self, text: str) -> bool:
        """Prüft ob ein Text eine Frage ist"""
        question_starters = [
            'was ', 'wie ', 'warum ', 'wann ', 'wo ', 'wer ', 'welche ',
            'kann ', 'ist ', 'sind ', 'hat ', 'haben ', 'gibt ',
            'what ', 'how ', 'why ', 'when ', 'where ', 'who ', 'which ',
        ]
        text_lower = text.lower()
        return text.endswith('?') or any(text_lower.startswith(q) for q in question_starters)

    def _clean_question(self, text: str) -> str:
        """Bereinigt eine Frage"""
        # Entferne führende/trailing Whitespace
        text = text.strip()

        # Entferne mehrfache Leerzeichen
        text = re.sub(r'\s+', ' ', text)

        # Entferne HTML-Artefakte
        text = re.sub(r'<[^>]+>', '', text)

        # Sicherstellen, dass Fragezeichen am Ende
        if not text.endswith('?') and self._is_question(text):
            text += '?'

        return text
