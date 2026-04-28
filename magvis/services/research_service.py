"""Web-Research-Service fuer magvis (Port aus blogprep, vereinfacht).

Holt 3-5 DuckDuckGo-Ergebnisse zum Topic und extrahiert die Texte fuer
LLM-Kontext, sodass der Blog faktenreiche, nicht-generische Inhalte hat.
"""
from __future__ import annotations

import logging
import random
import re
import time
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MagvisResearchService:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8',
    }
    TIMEOUT = 12

    # Vertrauenswuerdige Domains fuer Statistiken (frei abrufbar ohne Login).
    STATISTICS_WHITELIST = (
        # Bund
        'destatis.de', 'bundesregierung.de', 'bmfsfj.de', 'bmg.de',
        'bmuv.de', 'bmf.de', 'bmwk.de', 'bmas.de', 'bmel.de', 'bmi.bund.de',
        'bmbf.de', 'bzga.de', 'bsi.bund.de', 'bka.de', 'bafa.de',
        # Forschung & Wissenschaft
        'rki.de', 'iab.de', 'iwd.de', 'diw.de', 'ifo.de', 'wsi.de',
        'pestel-institut.de', 'wzb.eu', 'bibb.de', 'dipf.de',
        'kmk.org', 'daad.de', 'forschung.de',
        # Stiftungen & Verbaende (mit Statistik-Reputation)
        'bertelsmann-stiftung.de', 'boeckler.de', 'rosalux.de',
        'vbw-bayern.de', 'arbeitgeber.de', 'dgb.de', 'verdi.de',
        # EU & International
        'ec.europa.eu', 'eurostat.ec.europa.eu', 'europarl.europa.eu',
        'oecd.org', 'who.int', 'unicef.de', 'imf.org', 'worldbank.org',
        # Branchenstatistik (frei zugaenglich)
        'statista.com',  # Headlines/Titles oft frei
        'gfk.com', 'yougov.de', 'civey.com',
        # Laender (Auswahl)
        'statistik-bw.de', 'statistik.bayern.de', 'it.nrw',
        'statistik-berlin-brandenburg.de',
    )

    @classmethod
    def is_whitelisted(cls, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(host == d or host.endswith('.' + d) for d in cls.STATISTICS_WHITELIST)

    def __init__(self, user=None):
        """Wenn user.brave_api_key gesetzt: Brave Search API nutzen, sonst DDG."""
        self.user = user
        self.brave_key = getattr(user, 'brave_api_key', None) if user else None

    def search(self, query: str, num_results: int = 5) -> list[dict]:
        """Web-Suche. Brave Search API mit Fallback auf DuckDuckGo HTML."""
        if self.brave_key:
            results = self._brave(query, num_results)
            if results:
                logger.info('Research via Brave Search: %d Treffer', len(results))
            else:
                logger.info('Brave lieferte keine Treffer — Fallback DDG')
                results = self._ddg_html(query, num_results)
        else:
            results = self._ddg_html(query, num_results)

        for i, r in enumerate(results):
            try:
                if i > 0:
                    time.sleep(random.uniform(0.3, 0.8))
                r['content'] = self._extract_text(r['url'], max_length=2500)
            except Exception:
                r['content'] = ''
        return results

    def _brave(self, query: str, num_results: int) -> list[dict]:
        """Brave Search API — https://api.search.brave.com/res/v1/web/search"""
        try:
            resp = requests.get(
                'https://api.search.brave.com/res/v1/web/search',
                params={'q': query, 'count': num_results,
                        'country': 'DE', 'search_lang': 'de'},
                headers={'X-Subscription-Token': self.brave_key,
                         'Accept': 'application/json'},
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning('Brave Search Fehler: %s', exc)
            return []

        data = resp.json()
        out = []
        for item in (data.get('web', {}).get('results', []) or [])[:num_results]:
            url = item.get('url', '')
            if not url or self._is_blocked(url):
                continue
            out.append({
                'title': item.get('title', ''),
                'url': url,
                'snippet': item.get('description', '')
                           or item.get('extra_snippets', [''])[0] if item.get('extra_snippets') else '',
            })
        return out

    def _ddg_html(self, query: str, num_results: int) -> list[dict]:
        url = f'https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=de-de'
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning('DDG-Suche fehlgeschlagen: %s', exc)
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        out = []
        for el in soup.select('.result, .web-result')[:num_results * 2]:
            link = el.select_one('.result__a, h2 a')
            snippet = el.select_one('.result__snippet')
            if not link:
                continue
            href = link.get('href', '')
            # DDG redirect entfernen
            m = re.search(r'uddg=([^&]+)', href)
            if m:
                from urllib.parse import unquote
                href = unquote(m.group(1))
            if not href.startswith('http') or self._is_blocked(href):
                continue
            out.append({
                'title': link.get_text(strip=True),
                'url': href,
                'snippet': snippet.get_text(strip=True) if snippet else '',
            })
            if len(out) >= num_results:
                break
        return out

    def _is_blocked(self, url: str) -> bool:
        bad = ('youtube.com', 'pinterest.', 'amazon.', 'ebay.',
               'instagram.com', 'facebook.com', 'tiktok.com',
               'naturmacher.de')
        host = urlparse(url).netloc.lower()
        return any(b in host for b in bad)

    def _extract_text(self, url: str, max_length: int = 2500) -> str:
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
            resp.raise_for_status()
        except Exception:
            return ''
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
            tag.decompose()
        article = (soup.select_one('article') or soup.select_one('main')
                   or soup.select_one('.content') or soup.body or soup)
        text = article.get_text(separator=' ', strip=True) if article else ''
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_length]

    def search_statistics(self, topic: str, num_results: int = 8) -> list[dict]:
        """Sucht gezielt Statistik-Quellen aus der Whitelist.

        Mehrere parallele Queries mit Pausen + Whitelist-Filter.
        Holt HTML-Content fuer Live-Verifikation. Snippets bleiben primaere
        Verifikations-Quelle (was Brave aus der Live-Seite extrahiert hat).
        """
        queries = [
            f'{topic} statistik',
            f'{topic} studie zahlen',
            f'{topic} prozent anzahl',
            f'{topic} site:destatis.de OR site:statista.com OR site:eurostat.ec.europa.eu',
        ]
        all_results = []
        seen_urls = set()
        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(1.5)  # Rate-Limit respektieren
            try:
                results = self._brave(query, num_results) if self.brave_key else self._ddg_html(query, num_results)
            except Exception as exc:
                logger.warning('Stat-Search Query %d fehlgeschlagen: %s', i + 1, exc)
                continue
            for r in results:
                url = r.get('url', '')
                if url in seen_urls or not self.is_whitelisted(url):
                    continue
                seen_urls.add(url)
                all_results.append(r)
            if len(all_results) >= num_results:
                break

        # Content extrahieren
        for i, r in enumerate(all_results):
            try:
                if i > 0:
                    time.sleep(random.uniform(0.3, 0.7))
                r['content'] = self._extract_text(r['url'], max_length=4000)
            except Exception:
                r['content'] = ''

        return all_results

    def verify_statistic(self, stat: dict, search_results: list[dict] | None = None) -> bool:
        """Verifiziert Statistik 4-stufig (vom strengsten zum lockersten Match).

        Stufe 1: Wert + Excerpt im RECHERCHE-CONTENT (was Brave/Web extrahiert hat).
        Stufe 2: Wert exakt im Live-HTML der Source-URL.
        Stufe 3: Kern-Zahl aus value im Live-HTML.
        Stufe 4: Excerpt-Substring (25+ Zeichen) im Live-HTML oder im Brave-Snippet.

        Akzeptiert wenn IRGENDEINE Stufe matched (statt strenger AND).
        """
        url = stat.get('source_url', '')
        value = (stat.get('value', '') or '').strip()
        excerpt = (stat.get('quote_excerpt', '') or '').strip()
        if not url or not value or not self.is_whitelisted(url):
            return False

        norm_value = re.sub(r'\s+', '', value).lower()
        norm_value_clean = norm_value.replace('.', '').replace(',', '')
        core_num_match = re.search(r'(\d+(?:[,.]\d+)?)', value)
        core_num = core_num_match.group(1).lower() if core_num_match else ''

        # Stufe 1: im Recherche-Content (Brave-Snippet + extrahierter HTML-Body) suchen
        if search_results:
            for r in search_results:
                if r.get('url') != url:
                    continue
                haystack = (r.get('snippet', '') + ' ' + r.get('content', '')).lower()
                haystack_clean = re.sub(r'[.,]', '', haystack)
                if norm_value in haystack or norm_value_clean in haystack_clean:
                    return True
                if core_num and (core_num in haystack or core_num.replace(',', '.') in haystack):
                    return True
                if len(excerpt) >= 25 and excerpt[:30].lower() in haystack:
                    return True

        # Stufe 2-4: Live-Fetch
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
            resp.raise_for_status()
        except Exception:
            # Fallback: wenn schon im Snippet bestaetigt → false hier ist OK
            return False

        text = re.sub(r'<[^>]+>', ' ', resp.text)
        norm_text = re.sub(r'\s+', ' ', text).replace('\xa0', ' ').lower()
        norm_text_clean = re.sub(r'[.,]', '', norm_text)

        if norm_value in norm_text or norm_value_clean in norm_text_clean:
            return True
        if core_num and (core_num in norm_text or core_num.replace(',', '.') in norm_text):
            return True
        if len(excerpt) >= 25 and excerpt[:30].lower() in norm_text:
            return True

        return False

    def format_for_llm(self, results: list[dict]) -> str:
        """Komprimiertes Format fuer LLM-System-Prompt."""
        parts = []
        for i, r in enumerate(results[:5], start=1):
            content = (r.get('content') or r.get('snippet', ''))[:600]
            parts.append(f'[Q{i}] {r.get("title", "")}\n{content}\n')
        return '\n'.join(parts)
