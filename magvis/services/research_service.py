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
    # Erweitert um: Wikipedia (sekundaer, aber zitiert Primaerquellen),
    # Branchenmagazine, Berufsverbaende.
    STATISTICS_WHITELIST = (
        # Bund
        'destatis.de', 'bundesregierung.de', 'bmfsfj.de', 'bmg.de',
        'bmuv.de', 'bmf.de', 'bmwk.de', 'bmas.de', 'bmel.de', 'bmi.bund.de',
        'bmbf.de', 'bzga.de', 'bsi.bund.de', 'bka.de', 'bafa.de',
        'bbsr.bund.de', 'bib.bund.de', 'bmwsb.bund.de', 'bzgesundheit.de',
        # Forschung & Wissenschaft
        'rki.de', 'iab.de', 'iwd.de', 'iwkoeln.de', 'diw.de', 'ifo.de', 'wsi.de',
        'pestel-institut.de', 'wzb.eu', 'bibb.de', 'dipf.de',
        'kmk.org', 'daad.de', 'forschung.de', 'forschung-und-lehre.de',
        'dji.de', 'mpib-berlin.mpg.de', 'leibniz-gemeinschaft.de',
        'studienkompass.de', 'hochschulkompass.de', 'studienwahl.de',
        # Stiftungen & Verbaende (mit Statistik-Reputation)
        'bertelsmann-stiftung.de', 'boeckler.de', 'rosalux.de',
        'vbw-bayern.de', 'arbeitgeber.de', 'dgb.de', 'verdi.de',
        'stifterverband.org', 'koerber-stiftung.de', 'mercator-zukunftsgespraeche.de',
        # EU & International
        'ec.europa.eu', 'eurostat.ec.europa.eu', 'europarl.europa.eu',
        'oecd.org', 'who.int', 'unicef.de', 'imf.org', 'worldbank.org',
        # Branchenstatistik (frei zugaenglich)
        'statista.com',  # Headlines/Titles oft frei
        'gfk.com', 'yougov.de', 'civey.com',
        # Laender (Auswahl)
        'statistik-bw.de', 'statistik.bayern.de', 'it.nrw',
        'statistik-berlin-brandenburg.de',
        # Wikipedia (sekundaer — zitiert Primaerquellen, hat oft echte Zahlen)
        'de.wikipedia.org', 'en.wikipedia.org',
        # Berufs-spezifische Quellen
        'arbeitsagentur.de', 'kfw.de',
        'pwc.de', 'mckinsey.de', 'deloitte.com', 'kpmg.de',
        # Berufsverbaende & Kammern
        'ihk.de', 'dihk.de', 'zdh.de', 'handwerksblatt.de',
        'aerzteblatt.de', 'kbv.de', 'bvkj.de',
        # Pressemitteilungen (oft mit Primaerquellen)
        'presseportal.de', 'ots.at', 'idw-online.de',
        # Magazine/Fachpresse mit eigenen Studien
        'deutschlandfunk.de', 'tagesschau.de', 'zeit.de',
        'spiegel.de', 'faz.net', 'sueddeutsche.de', 'handelsblatt.com',
    )

    # Pretty-Names fuer Source-Anzeige (Anchor-Text in der Stat-Box).
    # Wird nach Cross-Whitelist-URL-Korrektur verwendet, damit der
    # Anchor-Text zur tatsaechlich verlinkten Domain passt.
    SOURCE_DISPLAY_NAMES = {
        'destatis.de': 'Statistisches Bundesamt',
        'de.wikipedia.org': 'Wikipedia',
        'en.wikipedia.org': 'Wikipedia',
        'statista.com': 'Statista',
        'de.statista.com': 'Statista',
        'bmfsfj.de': 'Bundesministerium für Familie',
        'bmg.de': 'Bundesministerium für Gesundheit',
        'bmwk.de': 'Bundesministerium für Wirtschaft',
        'bmas.de': 'Bundesministerium für Arbeit',
        'bmbf.de': 'Bundesministerium für Bildung',
        'bundesregierung.de': 'Bundesregierung',
        'rki.de': 'Robert Koch-Institut',
        'kmk.org': 'Kultusministerkonferenz',
        'bibb.de': 'Bundesinstitut für Berufsbildung',
        'iab.de': 'Institut für Arbeitsmarkt- und Berufsforschung',
        'iwd.de': 'Institut der deutschen Wirtschaft',
        'iwkoeln.de': 'Institut der deutschen Wirtschaft',
        'arbeitsagentur.de': 'Bundesagentur für Arbeit',
        'oecd.org': 'OECD',
        'who.int': 'WHO',
        'unicef.de': 'UNICEF',
        'imf.org': 'IWF',
        'worldbank.org': 'Weltbank',
        'ec.europa.eu': 'Europäische Kommission',
        'eurostat.ec.europa.eu': 'Eurostat',
        'bertelsmann-stiftung.de': 'Bertelsmann Stiftung',
        'boeckler.de': 'Hans-Böckler-Stiftung',
        'tagesschau.de': 'Tagesschau',
        'zeit.de': 'Zeit Online',
        'spiegel.de': 'Spiegel',
        'faz.net': 'FAZ',
        'sueddeutsche.de': 'Süddeutsche Zeitung',
        'handelsblatt.com': 'Handelsblatt',
        'aerzteblatt.de': 'Deutsches Ärzteblatt',
        'ihk.de': 'IHK',
        'dihk.de': 'DIHK',
        'zdh.de': 'Zentralverband des Deutschen Handwerks',
        'presseportal.de': 'Presseportal',
        'idw-online.de': 'Informationsdienst Wissenschaft',
        'hochschulkompass.de': 'Hochschulkompass',
        'dji.de': 'Deutsches Jugendinstitut',
    }

    @classmethod
    def is_whitelisted(cls, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(host == d or host.endswith('.' + d) for d in cls.STATISTICS_WHITELIST)

    @classmethod
    def pretty_source_name(cls, url: str) -> str:
        """Liefert einen lesbaren Quell-Namen aus der URL — als Anchor-Text in der Stat-Box.

        Bei unbekannten Whitelist-Domains wird der Hostname als Fallback genutzt
        (z.B. 'spiegel.de' wenn keine Pretty-Name-Eintragung existiert).
        """
        host = urlparse(url).netloc.lower().replace('www.', '')
        if host in cls.SOURCE_DISPLAY_NAMES:
            return cls.SOURCE_DISPLAY_NAMES[host]
        # Suffix-Match (de.statista.com -> statista.com)
        for domain, name in cls.SOURCE_DISPLAY_NAMES.items():
            if host.endswith('.' + domain) or host == domain:
                return name
        return host

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

    def analyze_top_competitors(self, topic: str, n: int = 8) -> list[dict]:
        """Holt Body-Text der Top-N organischen Treffer fuer Skyscraper-Recherche.

        Filtert Marktplaetze, Preisvergleiche, Social Networks, eigene Domain raus —
        liefert nur echte redaktionelle Beitraege/Konkurrenz-Blogs.
        """
        EXTRA_BLOCKED = (
            'idealo.', 'otto.de', 'check24.', 'shopping.google',
            'galaxus.', 'kaufland.', 'wayfair.', 'real.de',
            'ladenzeile.', 'preisvergleich.', 'metro.de',
            'mediamarkt.', 'saturn.', 'thomann.', 'zalando.',
            'aboutyou.', 'douglas.', 'ikea.', 'depot-online.',
            'duden.de',  # Lexikon, kein Wettbewerber-Content
        )
        try:
            results = self.search(topic, num_results=min(n + 6, 12))
        except Exception as exc:
            logger.warning('Competitor-Search fehlgeschlagen: %s', exc)
            return []

        filtered = []
        for r in results:
            url = r.get('url', '')
            if not url or self._is_blocked(url):
                continue
            host = urlparse(url).netloc.lower()
            if any(b in host for b in EXTRA_BLOCKED):
                continue
            filtered.append(r)
            if len(filtered) >= n:
                break

        # Body-Text der Top-7 holen
        for i, r in enumerate(filtered[:7]):
            if i > 0:
                time.sleep(random.uniform(0.3, 0.6))
            try:
                r['body_text'] = self._extract_text(r['url'], max_length=2500)
            except Exception:
                r['body_text'] = ''

        # Treffer ohne nennenswerten Body-Text rausschmeissen
        filtered = [r for r in filtered if len((r.get('body_text') or '').strip()) > 200]
        return filtered

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
        """Verifiziert Stat (Zahl ODER Aussage) gegen Brave-Snippet + Live-HTML.

        Mehrere Stufen, akzeptiert wenn IRGENDEINE matched:
        - Wert exakt + Variants im Snippet/Content/Live-HTML
        - Kern-Zahl (falls value Zahl enthaelt)
        - Excerpt-Substring (25+ Zeichen)
        - Bei Aussagen (kein value-Match noetig): nur Excerpt-Substring entscheidet
        """
        url = stat.get('source_url', '')
        value = (stat.get('value', '') or '').strip()
        excerpt = (stat.get('quote_excerpt', '') or '').strip()
        if not value:
            return False
        # Wichtig: Wenn die GLM-URL leer oder nicht-whitelisted ist, NICHT
        # sofort verwerfen — Stage 1b (Cross-Whitelist) kann die richtige
        # URL aus den search_results finden und das Stat-Dict korrigieren.
        url_is_valid = bool(url) and self.is_whitelisted(url)

        norm_value = re.sub(r'\s+', '', value).lower()
        norm_value_clean = norm_value.replace('.', '').replace(',', '').replace(' ', '')
        core_num_match = re.search(r'(\d+(?:[,.]\d+)?)', value)
        core_num = core_num_match.group(1).lower() if core_num_match else ''
        # Kern-Zahl ohne Tausenderpunkte ("373.000" -> "373000") fuer matching
        core_num_clean = core_num.replace('.', '').replace(',', '').replace(' ', '')
        excerpt_norm = re.sub(r'\s+', ' ', excerpt[:60].lower().replace('\xa0', ' '))

        def matches(text: str) -> bool:
            t = re.sub(r'\s+', ' ', text).replace('\xa0', ' ').lower()
            t_clean = re.sub(r'[.,\s]', '', t)
            # 1) Wert-Match: exakt, ohne Komma/Punkt, ohne Whitespace
            if norm_value in t or norm_value_clean in t_clean:
                return True
            # 2) Kern-Zahl-Match: auch "373000" matched "373.000" oder "373 000"
            if core_num:
                if core_num in t or core_num.replace(',', '.') in t:
                    return True
                if core_num_clean and core_num_clean in t_clean:
                    return True
            # 3) Excerpt-Substring: gelockert von 25 auf 15 Zeichen
            if len(excerpt) >= 15 and excerpt_norm[:15] in t:
                return True
            # 4) Schlagwort-Match: gelockert von 60% auf 40%
            words = [w for w in re.findall(r'\b\w{4,}\b', value.lower()) if w]
            if len(words) >= 2:
                hits = sum(1 for w in words if w in t)
                if hits / len(words) >= 0.4:
                    return True
            return False

        # Stufe 1: Brave-Snippet/Content der angegebenen URL (nur wenn valide)
        if url_is_valid and search_results:
            for r in search_results:
                if r.get('url') != url:
                    continue
                haystack = r.get('snippet', '') + ' ' + r.get('content', '')
                if matches(haystack):
                    return True

        # Stufe 1b: Cross-Whitelist-Match — durchlaeuft IMMER alle Whitelist-Treffer.
        # Greift auch wenn url_is_valid=False (GLM gab keine oder NICHT-whitelisted URL).
        # Bei Match wird die korrekte URL ins Stat-Dict uebernommen.
        if search_results:
            for r in search_results:
                cand_url = r.get('url', '')
                if not cand_url or cand_url == url or not self.is_whitelisted(cand_url):
                    continue
                haystack = r.get('snippet', '') + ' ' + r.get('content', '')
                if matches(haystack):
                    stat['source_url'] = cand_url
                    # source_name IMMER an die korrigierte URL anpassen, damit
                    # Anchor-Text und Link-Ziel zusammenpassen
                    stat['source_name'] = self.pretty_source_name(cand_url)
                    logger.info('  ↪ Stat-URL korrigiert auf %s (%s)',
                                cand_url, stat['source_name'])
                    return True

        # Stufe 2: Live-Fetch der angegebenen URL — nur wenn valide whitelisted
        if not url_is_valid:
            return False
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
            resp.raise_for_status()
        except Exception:
            return False

        text = re.sub(r'<[^>]+>', ' ', resp.text)
        return matches(text)

    def format_for_llm(self, results: list[dict]) -> str:
        """Komprimiertes Format fuer LLM-System-Prompt."""
        parts = []
        for i, r in enumerate(results[:5], start=1):
            content = (r.get('content') or r.get('snippet', ''))[:600]
            parts.append(f'[Q{i}] {r.get("title", "")}\n{content}\n')
        return '\n'.join(parts)
