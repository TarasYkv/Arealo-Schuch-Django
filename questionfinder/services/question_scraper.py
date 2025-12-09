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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        self.timeout = 20

    def search_questions(self, keyword: str, language: str = 'de') -> Dict[str, Any]:
        """
        Sucht nach Fragen zu einem Keyword
        """
        try:
            encoded_keyword = quote_plus(keyword)

            # Verschiedene Suchvarianten für bessere PAA-Ergebnisse
            search_queries = [
                f"{keyword} fragen",
                f"was ist {keyword}",
                keyword
            ]

            all_paa = []
            all_related = []

            for query in search_queries[:1]:  # Nur erste Query um Rate-Limiting zu vermeiden
                encoded_q = quote_plus(query)
                search_url = f"https://www.google.com/search?q={encoded_q}&hl=de&gl=de"

                logger.info(f"Scraping URL: {search_url}")

                response = self.session.get(
                    search_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                logger.info(f"Response Status: {response.status_code}, Length: {len(response.text)}")

                if response.status_code != 200:
                    logger.warning(f"Non-200 status: {response.status_code}")
                    continue

                # Prüfe ob wir eine echte Google-Seite bekommen haben
                if 'google' not in response.text.lower() and len(response.text) < 1000:
                    logger.warning("Response seems invalid (too short or no google reference)")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Debug: Speichere HTML für Analyse (nur erste 5000 Zeichen)
                logger.debug(f"HTML Preview: {response.text[:2000]}")

                paa = self._extract_paa_questions(soup, response.text)
                related = self._extract_related_searches(soup)

                all_paa.extend([q for q in paa if q not in all_paa])
                all_related.extend([q for q in related if q not in all_related])

                # Pause zwischen Anfragen
                time.sleep(random.uniform(1.5, 3.0))

            # Wenn kein Scraping funktioniert, generiere Fragen aus dem Keyword
            if not all_paa and not all_related:
                logger.warning(f"No questions found via scraping for '{keyword}'. Generating fallback questions.")
                all_paa = self._generate_fallback_questions(keyword)

            logger.info(f"Final: {len(all_paa)} PAA, {len(all_related)} Related für '{keyword}'")

            return {
                'success': True,
                'paa_questions': all_paa[:15],
                'related_questions': all_related[:10],
                'keyword': keyword,
                'source': 'fallback' if not all_related else 'google'
            }

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error (möglicherweise PythonAnywhere Whitelist): {e}")
            # Fallback zu generierten Fragen
            fallback = self._generate_fallback_questions(keyword)
            return {
                'success': True,
                'paa_questions': fallback,
                'related_questions': [],
                'keyword': keyword,
                'source': 'fallback',
                'note': 'Google-Zugriff nicht möglich, Fragen wurden generiert'
            }
        except requests.RequestException as e:
            logger.error(f"Request-Fehler: {e}")
            fallback = self._generate_fallback_questions(keyword)
            return {
                'success': True,
                'paa_questions': fallback,
                'related_questions': [],
                'keyword': keyword,
                'source': 'fallback'
            }
        except Exception as e:
            logger.error(f"Fehler beim Scraping: {e}", exc_info=True)
            fallback = self._generate_fallback_questions(keyword)
            return {
                'success': True,
                'paa_questions': fallback,
                'related_questions': [],
                'keyword': keyword,
                'source': 'fallback'
            }

    def _extract_paa_questions(self, soup: BeautifulSoup, raw_html: str = "") -> List[str]:
        """
        Extrahiert People Also Ask Fragen
        """
        questions = []

        # Methode 1: CSS-Selektoren für PAA-Container
        paa_selectors = [
            # Neue Google PAA Selektoren (2024)
            'div[data-sgrd] span',
            'div.related-question-pair span',
            'div[jsname="Cpkphb"] span',
            'div.wQiwMc span',
            'div[data-q] span',
            'g-accordion-expander span',
            # Ältere Selektoren
            'div.ULSxyf span',
            'div.xpc span',
            'div[data-hveid] div[role="button"] span',
        ]

        for selector in paa_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if self._is_question(text) and text not in questions:
                        cleaned = self._clean_question(text)
                        if cleaned and 15 < len(cleaned) < 200:
                            questions.append(cleaned)
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")

        # Methode 2: Suche nach Frage-Patterns im gesamten Text
        if not questions and raw_html:
            # Suche nach typischen PAA-Patterns
            paa_pattern = r'data-q="([^"]+\?)"'
            matches = re.findall(paa_pattern, raw_html)
            for match in matches:
                cleaned = self._clean_question(match)
                if cleaned and cleaned not in questions:
                    questions.append(cleaned)

        # Methode 3: Regex auf den gesamten Text
        if not questions:
            all_text = soup.get_text()
            question_patterns = [
                r'((?:Was|Wie|Warum|Wann|Wo|Wer|Welche|Welcher|Welches|Kann|Kannst|Ist|Sind|Hat|Haben|Gibt|Soll|Muss|Darf)[^.!?\n]{15,120}\?)',
            ]

            for pattern in question_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                for match in matches:
                    cleaned = self._clean_question(match)
                    if cleaned and len(cleaned) > 15 and cleaned not in questions:
                        # Filtere irrelevante Matches
                        if not any(x in cleaned.lower() for x in ['cookie', 'datenschutz', 'nutzungsbedingungen', 'javascript']):
                            questions.append(cleaned)

        return questions[:15]

    def _extract_related_searches(self, soup: BeautifulSoup) -> List[str]:
        """
        Extrahiert verwandte Suchen
        """
        related = []

        related_selectors = [
            'div.k8XOCe a',
            'div.s75CSd a',
            'a.k8XOCe',
            'div.brs_col a',
            'div[data-ved] a[href*="search"]',
        ]

        for selector in related_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and 3 < len(text) < 80 and text not in related:
                        # Filtere irrelevante Links
                        if not any(x in text.lower() for x in ['anmelden', 'mehr', 'weitere', 'einstellungen']):
                            related.append(text)
            except Exception:
                continue

        return related[:10]

    def _generate_fallback_questions(self, keyword: str) -> List[str]:
        """
        Generiert typische Fragen basierend auf dem Keyword,
        wenn Google-Scraping nicht funktioniert
        """
        templates = [
            f"Was ist {keyword}?",
            f"Wie funktioniert {keyword}?",
            f"Warum ist {keyword} wichtig?",
            f"Was kostet {keyword}?",
            f"Wo kann man {keyword} kaufen?",
            f"Welche {keyword} sind die besten?",
            f"Wie lange dauert {keyword}?",
            f"Was sind die Vorteile von {keyword}?",
            f"Gibt es Alternativen zu {keyword}?",
            f"Für wen ist {keyword} geeignet?",
            f"Wann sollte man {keyword} verwenden?",
            f"Wie wählt man {keyword} aus?",
        ]
        return templates

    def _is_question(self, text: str) -> bool:
        """Prüft ob ein Text eine Frage ist"""
        if not text or len(text) < 10:
            return False

        question_starters = [
            'was ', 'wie ', 'warum ', 'wann ', 'wo ', 'wer ', 'welche ', 'welcher ', 'welches ',
            'kann ', 'kannst ', 'ist ', 'sind ', 'hat ', 'haben ', 'gibt ', 'soll ', 'muss ', 'darf ',
            'what ', 'how ', 'why ', 'when ', 'where ', 'who ', 'which ', 'can ', 'is ', 'are ',
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

        if not text.endswith('?') and self._is_question(text):
            text += '?'

        return text
