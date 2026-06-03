"""Pipeline-Service: parallele Abfrage externer Literatur-Quellen.

Mode: 'pipeline' im research-Modul. Liefert pro Layer Trefferzahl + Top-Papers
fuer eine freie Frage oder spezifisches Mechanismus/Produkt-Tupel.

Layer (alle optional via params['enabled_layers']):
  1. pubmed      — NCBI E-utilities (esearch + esummary)
  2. semantic    — Semantic Scholar Graph API (paper/search)
  3. openalex    — OpenAlex (/works)
  4. epmc        — Europe PMC (PubMed + AGRICOLA + AGRIS + Patente)
  5. crossref    — CrossRef (DOI-Suche + Citation-Counts)
  6. lens        — Lens.org Scholarly + Patent (nur wenn Token vorhanden)

Kein DB-Cache — jede Query frisch (per Anforderung des Users).
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# Default-Mailto fuer polite-Pool-Konventionen (OpenAlex, Crossref, EuropePMC)
DEFAULT_MAILTO = 'kontakt@workloom.de'
USER_AGENT_BASE = 'Workloom-Research-Pipeline/1.0'

# Globaler Rate-Limiter fuer Semantic Scholar (Free-Tier: 1 req/s laut Doku,
# in Praxis aber wesentlich strikter via Per-IP-Quota — ~100 req / 5 min).
# Ohne API-Key haengt die Quote an der IP, weshalb alle parallelen Calls
# durch denselben Lock gehen muessen, sonst gibt es 429.
_S2_LOCK = threading.Lock()
_S2_LAST_CALL = [0.0]   # mutable list als Closure-Box
_S2_MIN_INTERVAL = 6.0  # Sekunden zwischen Calls; sehr konservativ wegen IP-Limit
# Globaler Cooldown-Timer: wenn 429 mehrfach gesehen wurde, blockt der
# Layer alle weiteren Calls fuer X Sekunden komplett (damit nicht jeder
# neue Pipeline-Request denselben Hammer auf S2 macht).
_S2_BLOCKED_UNTIL = [0.0]


LAYERS = {
    'pubmed':   {'name': 'PubMed E-utilities',     'kind': 'literature',
                 'desc': 'NCBI Biomedizin (~36 Mio Papers, MeSH-kontrolliert)'},
    'semantic': {'name': 'Semantic Scholar',       'kind': 'literature',
                 'desc': 'Allen-AI ~210 Mio (Konferenzen + Pre-Prints)'},
    'openalex': {'name': 'OpenAlex',               'kind': 'literature',
                 'desc': '~250 Mio (breiteste Coverage, Concepts)'},
    'epmc':     {'name': 'Europe PMC',             'kind': 'literature',
                 'desc': 'PubMed + AGRICOLA + AGRIS + Patente'},
    'crossref': {'name': 'CrossRef',               'kind': 'literature',
                 'desc': '~145 Mio DOIs (Validierung + Citations)'},
    'lens':     {'name': 'Lens.org (Scholar+Pat.)', 'kind': 'patent_scholarly',
                 'desc': 'Papers + Patente kombiniert (Token noetig)'},
}


# ---- HTTP-Helper -------------------------------------------------------------

def _http_get_json(url, headers=None, timeout=20, retries=2, backoff=2.0):
    """GET JSON mit polite User-Agent + Retry bei 429/5xx."""
    headers = dict(headers or {})
    headers.setdefault('User-Agent', f'{USER_AGENT_BASE} (mailto:{DEFAULT_MAILTO})')
    headers.setdefault('Accept', 'application/json')
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = f'HTTP {e.code}'
            if e.code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(backoff ** (attempt + 1))
                continue
            try:
                body = e.read()[:500].decode('utf-8', errors='replace')
            except Exception:
                body = ''
            return {'_error': f'HTTP {e.code}: {body[:200]}'}
        except Exception as e:
            last_err = str(e)[:120]
            if attempt < retries:
                time.sleep(backoff ** (attempt + 1))
                continue
            return {'_error': last_err}
    return {'_error': last_err or 'unknown'}


def _http_post_json(url, body, headers=None, timeout=30):
    headers = dict(headers or {})
    headers.setdefault('User-Agent', f'{USER_AGENT_BASE} (mailto:{DEFAULT_MAILTO})')
    headers.setdefault('Content-Type', 'application/json')
    headers.setdefault('Accept', 'application/json')
    data = json.dumps(body).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read()[:500].decode('utf-8', errors='replace')
        except Exception:
            err_body = ''
        return {'_error': f'HTTP {e.code}: {err_body[:200]}'}
    except Exception as e:
        return {'_error': str(e)[:120]}


def _get_key(env_name, settings_attr=None):
    """API-Key aus ENV oder settings holen. None wenn nichts gesetzt."""
    val = os.environ.get(env_name)
    if val:
        return val.strip()
    if settings_attr:
        val = getattr(settings, settings_attr, None)
        if val:
            return val.strip()
    return None


# ---- Layer-Adapter ----------------------------------------------------------

def layer_pubmed(query, max_papers=10):
    """NCBI E-utilities: esearch + esummary fuer Top-N Papers."""
    api_key = _get_key('PUBMED_API_KEY', 'PUBMED_API_KEY')
    base_search = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    base_summary = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi'

    params = {
        'db': 'pubmed',
        'term': query,
        'retmode': 'json',
        'retmax': str(max_papers),
        'sort': 'relevance',
    }
    if api_key:
        params['api_key'] = api_key
    d = _http_get_json(base_search + '?' + urllib.parse.urlencode(params))
    if '_error' in d:
        return {'layer': 'pubmed', 'ok': False, 'error': d['_error'],
                'hit_count': 0, 'papers': []}
    es = d.get('esearchresult', {})
    total = int(es.get('count', 0))
    ids = es.get('idlist', []) or []
    papers = []
    if ids:
        sp = {'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'json'}
        if api_key:
            sp['api_key'] = api_key
        sd = _http_get_json(base_summary + '?' + urllib.parse.urlencode(sp))
        if '_error' not in sd:
            res = sd.get('result', {})
            for pid in ids:
                p = res.get(pid)
                if not p:
                    continue
                authors = ', '.join(a.get('name', '') for a in (p.get('authors') or [])[:5])
                papers.append({
                    'id': pid,
                    'title': p.get('title', ''),
                    'authors': authors,
                    'year': (p.get('pubdate') or '')[:4],
                    'journal': p.get('source', ''),
                    'doi': next((x['value'] for x in p.get('articleids', [])
                                 if x.get('idtype') == 'doi'), ''),
                    'url': f'https://pubmed.ncbi.nlm.nih.gov/{pid}/',
                })
    return {'layer': 'pubmed', 'ok': True, 'hit_count': total, 'papers': papers}


def layer_semantic(query, max_papers=10):
    """Semantic Scholar Graph API. Mit globalem Rate-Limit + Cooldown bei
    wiederholten 429, weil S2 im Free-Tier sehr restriktiv ist (IP-basiert).

    Strategie:
      - Mindestens _S2_MIN_INTERVAL Sekunden zwischen Calls.
      - Bei 429: 5 Retries mit Backoff 10s, 20s, 40s, 80s, 160s.
      - Wenn ALLE Retries fehlschlagen: globaler Cooldown 5 Min, in dem alle
        weiteren S2-Calls sofort ohne Versuch ein klares „Rate-Limit"-Result
        zurueckliefern. Verhindert, dass parallele/Folge-Requests S2 weiter
        hammern und so noch laenger geblockt werden.
    """
    api_key = _get_key('SEMANTIC_SCHOLAR_API_KEY', 'SEMANTIC_SCHOLAR_API_KEY')

    # Cooldown-Check: wenn S2 grade global geblockt ist, sofort skippen
    now = time.time()
    if _S2_BLOCKED_UNTIL[0] > now:
        wait_left = int(_S2_BLOCKED_UNTIL[0] - now)
        return {'layer': 'semantic', 'ok': False,
                'error': f'S2 rate-limited (Cooldown {wait_left}s; bitte API-Key freischalten)',
                'hit_count': 0, 'papers': []}

    base = 'https://api.semanticscholar.org/graph/v1/paper/search'
    fields = 'title,authors,year,venue,citationCount,externalIds,abstract,openAccessPdf'
    params = {'query': query, 'limit': str(max_papers), 'fields': fields}
    headers = {}
    if api_key:
        headers['x-api-key'] = api_key

    # Globaler Lock: erzwingt mindestens _S2_MIN_INTERVAL Sekunden zwischen
    # zwei S2-Calls, auch wenn parallele Threads requesten.
    with _S2_LOCK:
        elapsed = time.time() - _S2_LAST_CALL[0]
        if elapsed < _S2_MIN_INTERVAL:
            time.sleep(_S2_MIN_INTERVAL - elapsed)

        # Custom Retry-Loop mit aggressivem Backoff (10-20-40-80-160s)
        d = None
        for attempt in range(5):
            d = _http_get_json(base + '?' + urllib.parse.urlencode(params),
                               headers=headers, timeout=45, retries=0)
            _S2_LAST_CALL[0] = time.time()
            if '_error' not in d:
                break
            err = d['_error']
            if 'HTTP 429' in err and attempt < 4:
                wait = 10 * (2 ** attempt)  # 10, 20, 40, 80, 160
                logger.info('S2 429 attempt %d, sleeping %ds', attempt + 1, wait)
                time.sleep(wait)
                continue
            break

    if d is None or '_error' in d:
        err_msg = (d or {}).get('_error', 'unknown')
        # Wenn 429 trotz aller Retries: globaler Cooldown 5 Min
        if 'HTTP 429' in err_msg:
            _S2_BLOCKED_UNTIL[0] = time.time() + 300
            err_msg = ('S2 rate-limited nach 5 Retries (Cooldown 5 min aktiviert). '
                       'Empfehlung: SEMANTIC_SCHOLAR_API_KEY in ENV setzen.')
            logger.warning('S2 global cooldown for 5 min')
        return {'layer': 'semantic', 'ok': False,
                'error': err_msg, 'hit_count': 0, 'papers': []}
    total = int(d.get('total', 0))
    papers = []
    for p in d.get('data', []) or []:
        authors = ', '.join(a.get('name', '') for a in (p.get('authors') or [])[:5])
        doi = (p.get('externalIds') or {}).get('DOI', '')
        pid = (p.get('externalIds') or {}).get('PubMed', '') or p.get('paperId', '')
        papers.append({
            'id': pid,
            'title': p.get('title', ''),
            'authors': authors,
            'year': str(p.get('year', '') or ''),
            'journal': p.get('venue', ''),
            'doi': doi,
            'citation_count': p.get('citationCount', 0),
            'url': f'https://www.semanticscholar.org/paper/{p.get("paperId", "")}',
        })
    return {'layer': 'semantic', 'ok': True, 'hit_count': total, 'papers': papers}


def layer_openalex(query, max_papers=10):
    """OpenAlex /works."""
    base = 'https://api.openalex.org/works'
    params = {
        'search': query,
        'per_page': str(max_papers),
        'sort': 'relevance_score:desc',
        'mailto': DEFAULT_MAILTO,
    }
    d = _http_get_json(base + '?' + urllib.parse.urlencode(params))
    if '_error' in d:
        return {'layer': 'openalex', 'ok': False, 'error': d['_error'],
                'hit_count': 0, 'papers': []}
    total = int(d.get('meta', {}).get('count', 0))
    papers = []
    for w in d.get('results', []) or []:
        authors = ', '.join(
            (a.get('author') or {}).get('display_name', '')
            for a in (w.get('authorships') or [])[:5]
        )
        doi = (w.get('doi') or '').replace('https://doi.org/', '')
        host = (w.get('primary_location') or {}).get('source') or {}
        papers.append({
            'id': w.get('id', ''),
            'title': w.get('display_name', ''),
            'authors': authors,
            'year': str(w.get('publication_year', '') or ''),
            'journal': host.get('display_name', ''),
            'doi': doi,
            'citation_count': w.get('cited_by_count', 0),
            'url': w.get('id', ''),  # OpenAlex-IDs sind URLs
        })
    return {'layer': 'openalex', 'ok': True, 'hit_count': total, 'papers': papers}


def layer_epmc(query, max_papers=10):
    """Europe PMC."""
    base = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'
    params = {
        'query': query,
        'resultType': 'core',
        'format': 'json',
        'pageSize': str(max_papers),
        'sort': 'CITED desc',
    }
    d = _http_get_json(base + '?' + urllib.parse.urlencode(params))
    if '_error' in d:
        return {'layer': 'epmc', 'ok': False, 'error': d['_error'],
                'hit_count': 0, 'papers': []}
    total = int(d.get('hitCount', 0))
    papers = []
    for r in (d.get('resultList', {}) or {}).get('result', []) or []:
        authors = r.get('authorString', '')[:200]
        pid = r.get('id', '')
        src = r.get('source', '')
        url = ''
        if src == 'MED':
            url = f'https://pubmed.ncbi.nlm.nih.gov/{pid}/'
        elif src == 'PMC':
            url = f'https://europepmc.org/article/PMC/{pid}'
        elif r.get('doi'):
            url = f'https://doi.org/{r.get("doi")}'
        papers.append({
            'id': pid,
            'source_db': src,
            'title': r.get('title', ''),
            'authors': authors,
            'year': str(r.get('pubYear', '') or ''),
            'journal': r.get('journalTitle', ''),
            'doi': r.get('doi', ''),
            'citation_count': r.get('citedByCount', 0),
            'url': url,
        })
    return {'layer': 'epmc', 'ok': True, 'hit_count': total, 'papers': papers}


def layer_crossref(query, max_papers=10):
    """CrossRef /works."""
    base = 'https://api.crossref.org/works'
    params = {
        'query': query,
        'rows': str(max_papers),
        'sort': 'relevance',
        'mailto': DEFAULT_MAILTO,
    }
    d = _http_get_json(base + '?' + urllib.parse.urlencode(params))
    if '_error' in d:
        return {'layer': 'crossref', 'ok': False, 'error': d['_error'],
                'hit_count': 0, 'papers': []}
    msg = d.get('message', {})
    total = int(msg.get('total-results', 0))
    papers = []
    for w in msg.get('items', []) or []:
        authors = ', '.join(
            f'{a.get("given", "")} {a.get("family", "")}'.strip()
            for a in (w.get('author') or [])[:5]
        )
        year = ''
        for k in ('published-print', 'published-online', 'issued'):
            d_parts = (w.get(k) or {}).get('date-parts', [[]])
            if d_parts and d_parts[0]:
                year = str(d_parts[0][0])
                break
        journal = (w.get('container-title') or [''])[0]
        doi = w.get('DOI', '')
        title = (w.get('title') or [''])[0]
        papers.append({
            'id': doi,
            'title': title,
            'authors': authors,
            'year': year,
            'journal': journal,
            'doi': doi,
            'citation_count': w.get('is-referenced-by-count', 0),
            'url': f'https://doi.org/{doi}' if doi else '',
        })
    return {'layer': 'crossref', 'ok': True, 'hit_count': total, 'papers': papers}


def layer_lens(query, max_papers=10):
    """Lens.org Scholarly. Erfordert LENS_API_TOKEN."""
    token = _get_key('LENS_API_TOKEN', 'LENS_API_TOKEN')
    if not token:
        return {'layer': 'lens', 'ok': False, 'error': 'kein LENS_API_TOKEN gesetzt',
                'hit_count': 0, 'papers': []}
    url = 'https://api.lens.org/scholarly/search'
    body = {
        'query': {'match': {'title_abstract': query}},
        'size': max_papers,
        'sort': [{'date_published': 'desc'}],
    }
    headers = {'Authorization': f'Bearer {token}'}
    d = _http_post_json(url, body, headers=headers, timeout=30)
    if '_error' in d:
        return {'layer': 'lens', 'ok': False, 'error': d['_error'],
                'hit_count': 0, 'papers': []}
    total = int(d.get('total', 0))
    # Inhalt durchschleifen wie bei den anderen Layern
    papers = []
    for it in d.get('data', []) or []:
        authors = ', '.join(
            f'{a.get("first_name", "")} {a.get("last_name", "")}'.strip()
            for a in (it.get('authors') or [])[:5]
        )
        papers.append({
            'id': it.get('lens_id', ''),
            'title': it.get('title', ''),
            'authors': authors,
            'year': str(it.get('year_published', '') or ''),
            'journal': (it.get('source') or {}).get('title', ''),
            'doi': next((x.get('value', '') for x in it.get('external_ids', [])
                         if x.get('type') == 'doi'), ''),
            'citation_count': it.get('scholarly_citations_count', 0),
            'url': f'https://www.lens.org/lens/scholar/article/{it.get("lens_id", "")}',
        })
    return {'layer': 'lens', 'ok': True, 'hit_count': total, 'papers': papers}


LAYER_FUNCS = {
    'pubmed':   layer_pubmed,
    'semantic': layer_semantic,
    'openalex': layer_openalex,
    'epmc':     layer_epmc,
    'crossref': layer_crossref,
    'lens':     layer_lens,
}


def lens_patent_count(query):
    """Patent-Suche ueber Lens.org. Liefert nur Hit-Count (kein Detail).
    Gibt None zurueck wenn Token fehlt oder API-Fehler.
    """
    token = _get_key('LENS_API_TOKEN', 'LENS_API_TOKEN')
    if not token:
        return None
    url = 'https://api.lens.org/patent/search'
    body = {
        'query': {'match': {'title_abstract': query}},
        'size': 1,
    }
    headers = {'Authorization': f'Bearer {token}'}
    d = _http_post_json(url, body, headers=headers, timeout=20)
    if '_error' in d:
        return None
    return int(d.get('total', 0))


# ---- Co-Occurrence-Spezifitaet ---------------------------------------------

def _hit_count_only(layer_key, query):
    """Schnelle Counter-Variante pro Layer (nur Total, keine Papers)."""
    fn = LAYER_FUNCS.get(layer_key)
    if not fn:
        return None
    r = fn(query, max_papers=1)
    if r.get('ok'):
        return int(r.get('hit_count', 0))
    return None


def cooccurrence_analysis(mechanism, product, enabled_layers):
    """Co-Occurrence-Spezifitaet:

        spezifitaet = count(M AND P) / sqrt(count(M) * count(P))

    Pro Layer drei Counts plus Spezifitaet, am Ende ein Mittel ueber alle.
    Layer parallel, drei Queries pro Layer aber sequentiell innerhalb (sonst
    Rate-Limit-Risiko bei Semantic Scholar).
    """
    import math as _math
    out = []

    def _one(layer_key):
        m_q = mechanism.strip()
        p_q = product.strip()
        both_q = f'({m_q}) AND ({p_q})'
        c_m = _hit_count_only(layer_key, m_q)
        c_p = _hit_count_only(layer_key, p_q)
        c_b = _hit_count_only(layer_key, both_q)
        if c_m is None or c_p is None or c_b is None:
            return {'layer': layer_key, 'ok': False,
                    'error': 'mindestens eine Query schlug fehl',
                    'count_M': c_m, 'count_P': c_p, 'count_MP': c_b,
                    'specificity': None}
        if c_m > 0 and c_p > 0:
            spec = c_b / _math.sqrt(c_m * c_p)
        else:
            spec = 0.0
        return {'layer': layer_key, 'ok': True,
                'count_M': c_m, 'count_P': c_p, 'count_MP': c_b,
                'specificity': round(spec, 5)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_one, lk): lk for lk in enabled_layers
                if lk in LAYER_FUNCS}
        for f in concurrent.futures.as_completed(futs):
            try:
                out.append(f.result())
            except Exception as e:
                out.append({'layer': futs[f], 'ok': False,
                            'error': str(e)[:120], 'count_M': None,
                            'count_P': None, 'count_MP': None,
                            'specificity': None})

    # Konsistente Reihenfolge wie in enabled_layers
    order_map = {lk: i for i, lk in enumerate(enabled_layers)}
    out.sort(key=lambda r: order_map.get(r['layer'], 99))

    # Aggregierter Mittelwert ueber alle erfolgreichen Layer
    specs = [r['specificity'] for r in out
             if r.get('ok') and r.get('specificity') is not None]
    mean_spec = sum(specs) / len(specs) if specs else 0.0
    # Median (robuster gegen Outlier wie z.B. CrossRef-AND-Permissivitaet)
    sorted_specs = sorted(specs)
    if sorted_specs:
        mid = len(sorted_specs) // 2
        if len(sorted_specs) % 2:
            median_spec = sorted_specs[mid]
        else:
            median_spec = 0.5 * (sorted_specs[mid - 1] + sorted_specs[mid])
    else:
        median_spec = 0.0
    return {'per_layer': out, 'mean_specificity': round(mean_spec, 5),
            'median_specificity': round(median_spec, 5),
            'n_layers': len(specs)}


# ---- Mechanism-Weighting -----------------------------------------------------

def _to_7stufen(x):
    """Mappe kontinuierliches 0..1 auf 7-Stufen-Skala."""
    bins = [0.05, 0.15, 0.35, 0.55, 0.75, 0.95]
    levels = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    for i, b in enumerate(bins):
        if x < b:
            return levels[i]
    return 1.0


def compute_weighting(results, cooc=None, patent_query=None):
    """Berechne bis zu 6 Gewichtungs-Indikatoren + Final-Score.

    Indikatoren:
      - specificity:  Co-Occurrence-Median (nur wenn cooc gegeben)
      - citation:     log-summe der Top-Paper-Citations, normalisiert auf [0,1]
      - trend:        Anteil Papers aus den letzten 5 Jahren
      - convergence:  Anteil aktiver Layer mit >= 10 Treffern
      - patent:       Lens.org Patent-Count fuer patent_query (nur wenn Token)
      - diversity:    unique_authors / total_authors aus allen Papers

    Gewichte werden DYNAMISCH normalisiert je nach verfuegbaren Indikatoren.
    Basis-Gewichte (wenn alle 6 verfuegbar):
      0.22 spec + 0.18 cite + 0.10 trend + 0.20 conv + 0.18 patent + 0.12 div = 1.00
    Wenn Indikator fehlt: dessen Gewicht wird auf die uebrigen umverteilt.
    """
    import math as _math
    import datetime as _dt

    ok_results = [r for r in results if r.get('ok')]
    all_papers = []
    for r in ok_results:
        for p in (r.get('papers') or []):
            all_papers.append(p)

    # Citation-Score: log-Summe ueber Top-Papers
    citations = [int(p.get('citation_count') or 0) for p in all_papers]
    if citations:
        # log(1+c) summiert, dann normalisiert: 100 (= guter Wert) → 1.0
        raw_cite = sum(_math.log1p(c) for c in citations)
        cite_n = min(raw_cite / max(len(citations) * 4.0, 1.0), 1.0)
    else:
        raw_cite = 0.0
        cite_n = 0.0

    # Trend-Score: Anteil Papers aus den letzten 5 Jahren
    this_year = _dt.datetime.utcnow().year
    threshold = this_year - 5
    years_valid = []
    recent_count = 0
    for p in all_papers:
        try:
            y = int(str(p.get('year') or '0')[:4])
        except Exception:
            continue
        if y < 1900 or y > this_year + 2:
            continue
        years_valid.append(y)
        if y >= threshold:
            recent_count += 1
    if years_valid:
        trend = recent_count / len(years_valid)
    else:
        trend = 0.0

    # Konvergenz: Anteil Layer die ok UND >=10 Treffer haben
    layers_with_hits = sum(
        1 for r in ok_results if (r.get('hit_count') or 0) >= 10)
    total_layers = max(len(results), 1)
    convergence = layers_with_hits / total_layers

    # Spezifitaet aus cooc (Median bevorzugt, robuster)
    has_cooc = bool(cooc)
    spec = None
    if has_cooc:
        spec = cooc.get('median_specificity')
        if spec is None:
            spec = cooc.get('mean_specificity', 0.0)
        # Auf [0,1] clampen — CrossRef kann theoretisch >1 liefern
        spec = max(0.0, min(spec, 1.0))

    # Patent-Score (nur wenn Lens-Token + Query gegeben)
    patent_count = None
    patent_n = None
    if patent_query:
        patent_count = lens_patent_count(patent_query)
        if patent_count is not None:
            # 100 Patente = 1.0, log-Norm
            patent_n = min(_math.log1p(patent_count) / _math.log1p(100), 1.0)

    # Author-Diversity ueber alle geladenen Papers
    all_authors = []
    for p in all_papers:
        au_str = (p.get('authors') or '').strip()
        if not au_str:
            continue
        for a in au_str.split(','):
            an = a.strip().lower()
            # Initials trimmen, nur Nachname-artige Bestandteile
            if an and len(an) > 2:
                all_authors.append(an)
    if all_authors:
        unique_authors = len(set(all_authors))
        diversity_n = unique_authors / len(all_authors)
    else:
        unique_authors = 0
        diversity_n = 0.0

    # Dynamische Gewichtung basierend auf verfuegbaren Indikatoren
    BASE_WEIGHTS = {
        'specificity': 0.22, 'citation': 0.18, 'trend': 0.10,
        'convergence': 0.20, 'patent': 0.18, 'diversity': 0.12,
    }
    available = {
        'specificity': spec if spec is not None else None,
        'citation':    cite_n,
        'trend':       trend,
        'convergence': convergence,
        'patent':      patent_n if patent_n is not None else None,
        'diversity':   diversity_n,
    }
    active = {k: v for k, v in available.items() if v is not None}
    sum_base = sum(BASE_WEIGHTS[k] for k in active)
    weights = {k: round(BASE_WEIGHTS[k] / sum_base, 4) for k in active}
    final = sum(weights[k] * v for k, v in active.items())

    return {
        'specificity':    None if spec is None else round(spec, 5),
        'citation':       round(cite_n, 3),
        'citation_raw':   round(raw_cite, 1),
        'n_citations':    len(citations),
        'trend':          round(trend, 3),
        'n_recent':       recent_count,
        'n_dated':        len(years_valid),
        'convergence':    round(convergence, 3),
        'layers_hits':    layers_with_hits,
        'layers_total':   total_layers,
        'patent':         None if patent_n is None else round(patent_n, 3),
        'patent_count':   patent_count,
        'diversity':      round(diversity_n, 3),
        'unique_authors': unique_authors,
        'total_authors':  len(all_authors),
        'final':          round(final, 3),
        'final_7stufen':  _to_7stufen(final),
        'weights':        weights,
        'has_cooc':       has_cooc,
        'has_patent':     patent_n is not None,
    }


# ---- Synthese ---------------------------------------------------------------

def _summarize_markdown(question, results, product_filter='', cooc=None, weighting=None):
    """Erzeugt Markdown-Antwort mit Layer-Tabelle + Top-Papers + Konsens-Hinweis.
    Wenn `cooc` (cooccurrence_analysis-Ergebnis) gegeben ist, wird zusaetzlich
    eine Spezifitaets-Tabelle eingefuegt. Wenn `weighting` gegeben ist, wird
    eine Mechanism-Weighting-Box am Anfang gerendert.
    """
    lines = []
    if product_filter:
        lines.append(f'# Pipeline-Suche: „{question}" (Filter: {product_filter})\n')
    else:
        lines.append(f'# Pipeline-Suche: „{question}"\n')

    # Mechanism-Weighting-Box (immer wenn berechnet)
    if weighting:
        lines.append('## Mechanism-Weighting — Gewichtungs-Score w_(p,M)\n')
        lines.append('| Indikator | Wert | Detail |')
        lines.append('|-----------|-----:|--------|')
        if weighting.get('specificity') is not None:
            lines.append(f'| Spezifitaet (Median) | {weighting["specificity"]:.4f} | aus Co-Occurrence-Analyse |')
        lines.append(f'| Citation-Score | {weighting["citation"]:.3f} | log-Summe = {weighting["citation_raw"]:.1f} über {weighting["n_citations"]} Papers |')
        lines.append(f'| Trend-Score | {weighting["trend"]:.3f} | {weighting["n_recent"]}/{weighting["n_dated"]} Papers aus den letzten 5 Jahren |')
        lines.append(f'| Konvergenz | {weighting["convergence"]:.3f} | {weighting["layers_hits"]}/{weighting["layers_total"]} Layer mit ≥10 Treffern |')
        if weighting.get('patent') is not None:
            lines.append(f'| Patent-Score | {weighting["patent"]:.3f} | {weighting["patent_count"]} Patente (Lens.org) |')
        lines.append(f'| Author-Diversity | {weighting["diversity"]:.3f} | {weighting["unique_authors"]} unique / {weighting["total_authors"]} Autoren gesamt |')
        ws = weighting.get('weights', {})
        ws_str = ' + '.join(f'{w:.2f}·{k[:4]}' for k, w in ws.items())
        lines.append(f'\n**Gewichtungsformel (dynamisch):** {ws_str}\n')
        lines.append(f'**FINAL w_(p,M):** **{weighting["final"]:.3f}**  →  '
                     f'7-Stufen-Skala: **{weighting["final_7stufen"]}**\n')
        if not weighting.get('has_cooc'):
            lines.append('_Hinweis: Spezifität nicht aktiv (kein Filter oder '
                         'Co-Occurrence-Checkbox nicht gesetzt). Gewichtung '
                         'auf restliche Indikatoren umverteilt._\n')
        if not weighting.get('has_patent'):
            lines.append('_Hinweis: Patent-Score nicht aktiv (kein '
                         'LENS_API_TOKEN oder Lens-Layer deaktiviert)._\n')

    # Co-Occurrence-Spezifitaet (falls aktiv) — zuerst, weil sie die wichtigste
    # Interpretation der Ergebnisse ist
    if cooc and cooc.get('per_layer'):
        lines.append('## Co-Occurrence-Spezifität — Gewichtungs-Indikator\n')
        lines.append(
            f'Wie spezifisch ist die Verbindung zwischen **„{question}"** und '
            f'**„{product_filter}"**? Berechnung pro Layer: '
            f'`spezifität = count(M ∩ P) / √(count(M) × count(P))`. '
            f'Werte nahe 1 = sehr spezifische Verbindung; Werte nahe 0 = '
            f'beide Begriffe kommen oft vor, aber selten zusammen.\n')
        lines.append('| Layer | count(M) | count(P) | count(M∩P) | Spezifität |')
        lines.append('|-------|---------:|---------:|-----------:|-----------:|')
        for r in cooc['per_layer']:
            layer = LAYERS.get(r['layer'], {}).get('name', r['layer'])
            if r.get('ok'):
                lines.append(
                    f'| {layer} | {r["count_M"]:,} | {r["count_P"]:,} | '
                    f'{r["count_MP"]:,} | {r["specificity"]:.5f} |')
            else:
                lines.append(f'| {layer} | — | — | — | ✗ {r.get("error", "")[:40]} |')
        lines.append('')
        ms = cooc.get('mean_specificity', 0.0)
        n = cooc.get('n_layers', 0)
        lines.append(f'**Mittlere Spezifität** (über {n} aktive Layer): **{ms:.5f}**\n')
        # Interpretations-Hinweis
        if ms >= 0.01:
            lines.append('→ Hohe spezifische Verbindung: die beiden Konzepte werden '
                         'in der Literatur regelmäßig gemeinsam diskutiert.')
        elif ms >= 0.001:
            lines.append('→ Mittlere spezifische Verbindung: Begriffe existieren beide '
                         'breit, kommen aber in Schnittliteratur überschaubar oft vor.')
        else:
            lines.append('→ Schwache spezifische Verbindung: trotz hoher Einzeltreffer '
                         'gibt es kaum gemeinsame Literatur — die Mechanismus-Produkt-'
                         'Verbindung ist in der publizierten Forschung selten.')
        lines.append('')

    # Layer-Tabelle
    lines.append('## Layer-Ergebnisse\n')
    lines.append('| Layer | Treffer | Status | Top-Citation |')
    lines.append('|-------|--------:|--------|-------------:|')
    for r in results:
        layer = LAYERS.get(r['layer'], {}).get('name', r['layer'])
        if r.get('ok'):
            top_cite = 0
            for p in r.get('papers', []):
                top_cite = max(top_cite, int(p.get('citation_count', 0) or 0))
            status = '✓'
            lines.append(f'| {layer} | {r["hit_count"]:,} | {status} | {top_cite} |')
        else:
            lines.append(f'| {layer} | — | ✗ {r.get("error", "Fehler")[:60]} | — |')
    lines.append('')

    # Aggregierte Statistik
    ok_results = [r for r in results if r.get('ok')]
    total_hits = sum(r.get('hit_count', 0) for r in ok_results)
    lines.append(f'**Gesamttreffer (Summe aller Layer):** {total_hits:,}')
    lines.append(f'**Aktive Layer:** {len(ok_results)} von {len(results)}\n')

    # Top-Papers pro Layer
    lines.append('## Top-Papers pro Layer\n')
    for r in results:
        if not r.get('ok') or not r.get('papers'):
            continue
        layer = LAYERS.get(r['layer'], {}).get('name', r['layer'])
        lines.append(f'### {layer}\n')
        for i, p in enumerate(r['papers'][:5], 1):
            au = p.get('authors', '')[:120]
            t = (p.get('title', '') or '').strip()
            yr = p.get('year', '')
            jn = p.get('journal', '')
            url = p.get('url', '')
            cite = p.get('citation_count')
            cite_str = f' — {cite} Zitationen' if cite else ''
            link = f'[Link]({url})' if url else ''
            lines.append(f'{i}. **{t}** ({yr}){cite_str}')
            lines.append(f'   {au}; *{jn}* {link}\n')

    return '\n'.join(lines)


def _flat_sources(results):
    """Fuer ResearchQuery.sources: Liste aller Papers ueber alle Layer hinweg."""
    out = []
    for r in results:
        if not r.get('ok'):
            continue
        for p in r.get('papers', []):
            out.append({
                'title': p.get('title', ''),
                'authors': p.get('authors', ''),
                'year': p.get('year', ''),
                'filename': p.get('journal', ''),
                'doi': p.get('doi', ''),
                'url': p.get('url', ''),
                'score': float(p.get('citation_count') or 0),
                'reference_id': p.get('id', ''),
                'layer': r['layer'],
            })
    return out


# ---- Eintrittspunkt fuer den Worker ----------------------------------------

def run_pipeline(question, params=None):
    """Fuehrt die aktivierten Layer parallel aus und liefert dict mit
    answer (Markdown), sources (Liste), raw_responses (dict mit roher Layer-
    Ausgabe). Wird vom Celery-Task in tasks.py aufgerufen.

    params:
      enabled_layers: list[str] — z.B. ['pubmed','semantic','openalex','epmc']
      max_papers:     int       — Top-N pro Layer (Default 10)
      product_filter: str       — wird der Frage angehangen (Default '')
      cooccurrence:   bool      — wenn True und product_filter gesetzt, wird
                                  zusaetzlich eine Spezifitaets-Analyse pro
                                  Layer durchgefuehrt (3 Zaehlqueries pro Layer)
    """
    params = params or {}
    enabled = params.get('enabled_layers') or ['pubmed', 'semantic', 'openalex',
                                                'epmc', 'crossref']
    max_papers = int(params.get('max_papers', 10))
    product_filter = (params.get('product_filter') or '').strip()
    do_cooccurrence = bool(params.get('cooccurrence', False)) and bool(product_filter)

    full_query = question.strip()
    if product_filter:
        full_query = f'({question.strip()}) AND ({product_filter})'

    # Parallel ausfuehren, max 6 Threads
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {}
        for lk in enabled:
            fn = LAYER_FUNCS.get(lk)
            if not fn:
                continue
            futures[ex.submit(fn, full_query, max_papers)] = lk
        for f in concurrent.futures.as_completed(futures):
            try:
                results.append(f.result())
            except Exception as e:
                logger.exception('Pipeline-Layer %s exception', futures[f])
                results.append({'layer': futures[f], 'ok': False,
                                'error': str(e)[:120], 'hit_count': 0,
                                'papers': []})

    # Konsistente Reihenfolge wie in `enabled`
    order_map = {lk: i for i, lk in enumerate(enabled)}
    results.sort(key=lambda r: order_map.get(r['layer'], 99))

    cooc = None
    if do_cooccurrence:
        cooc = cooccurrence_analysis(question, product_filter, enabled)

    # Mechanism-Weighting immer mitberechnen (Spezifitaet nur wenn cooc,
    # Patent nur wenn Lens-Token + Lens-Layer aktiv)
    patent_query = full_query if 'lens' in enabled else None
    weighting = compute_weighting(results, cooc=cooc, patent_query=patent_query)

    answer = _summarize_markdown(question, results, product_filter,
                                  cooc=cooc, weighting=weighting)
    sources = _flat_sources(results)
    raw_responses = {'pipeline': results, 'query_used': full_query,
                     'weighting': weighting}
    if cooc:
        raw_responses['cooccurrence'] = cooc

    return {
        'answer': answer,
        'sources': sources,
        'raw_responses': raw_responses,
        'models_used': [LAYERS[lk]['name'] for lk in enabled if lk in LAYERS],
    }
