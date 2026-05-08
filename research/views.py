import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AskForm
from .models import ResearchQuery
from .services import rag as rag_service
from .services import council as council_service

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    from django.db.models import Sum, Count
    queries_qs = ResearchQuery.objects.filter(owner=request.user)
    queries = queries_qs[:20]
    agg = queries_qs.aggregate(
        total_cost=Sum('total_cost_usd'),
        count=Count('id'),
    )
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(url=rag_service.QDRANT_URL, timeout=5)
        info = qc.get_collection(rag_service.COLLECTION)
        index_stats = {
            'points': info.points_count,
            'status': str(info.status),
            'online': True,
        }
    except Exception as e:
        index_stats = {'online': False, 'error': str(e)}
    return render(request, 'research/dashboard.html', {
        'queries': queries,
        'index_stats': index_stats,
        'council_models': council_service.MODELS,
        'total_cost_usd': agg['total_cost'] or 0.0,
        'total_queries': agg['count'] or 0,
    })


@login_required
def ask(request):
    if request.method == 'POST':
        form = AskForm(request.POST)
        if form.is_valid():
            return _execute_ask_async(request, form)
    else:
        # Pre-fill aus einer bestehenden Anfrage + spezifischer Modell-Antwort —
        # erlaubt "Drill-down": vom Brain-Graph-Modal aus weiterforschen.
        initial = {}
        src_pk = request.GET.get('source_query')
        src_model = request.GET.get('source_model')
        if src_pk:
            try:
                src_q = ResearchQuery.objects.get(pk=src_pk, owner=request.user)
            except (ResearchQuery.DoesNotExist, ValueError):
                src_q = None
            if src_q:
                src_text = ''
                src_label = ''
                if src_model and isinstance(src_q.raw_responses, dict):
                    council = src_q.raw_responses.get('council') or []
                    for r in council:
                        if r.get('model') == src_model:
                            src_text = (r.get('text') or '').strip()
                            src_label = r.get('display') or src_model
                            break
                # Falls kein spezifisches Modell oder text leer: fallback auf
                # Hauptantwort der Source-Query
                if not src_text:
                    src_text = (src_q.answer or '').strip()
                    src_label = 'Synthese-Antwort'
                if src_text:
                    initial['question'] = (
                        f'Vertiefe folgenden Aspekt aus Anfrage #{src_q.pk} '
                        f'({src_label}):\n\n'
                        f'>>> {src_text[:1500]}{"…" if len(src_text) > 1500 else ""} <<<\n\n'
                        f'Originale Frage war: "{src_q.question[:200]}"\n\n'
                        f'Meine Folgefrage: '
                    )
                    initial['mode'] = 'council_edited'
        form = AskForm(initial=initial) if initial else AskForm()
    return render(request, 'research/ask.html', {
        'form': form,
        'council_models': council_service.MODELS,
        'council_models_json': council_service.MODELS,
    })


def _execute_ask_async(request, form):
    """Erstellt ResearchQuery im Status 'pending' und dispatcht den Celery-Task.
    Frontend pollt dann den Status bis 'done' oder 'failed'."""
    from .tasks import execute_research_query

    mode = form.cleaned_data['mode']
    question = form.cleaned_data['question']
    primary = form.cleaned_data.get('primary_model') or 'glm'
    council_ids = list(form.cleaned_data.get('council_models') or [])
    top_k = int(form.cleaned_data.get('top_k') or 6)

    rq = ResearchQuery.objects.create(
        owner=request.user, question=question, mode=mode, status='pending',
        params={
            'mode': mode,
            'primary_model': primary,
            'council_models': council_ids,
            'top_k': top_k,
        },
    )
    try:
        execute_research_query.delay(rq.pk)
    except Exception as e:
        # Fallback: synchron ausführen (z.B. wenn Celery/Redis down ist)
        logger.exception('Celery dispatch failed — running synchronously')
        from .tasks import execute_research_query as task_fn
        task_fn.apply(args=[rq.pk])
    return redirect(rq.get_absolute_url())


def _execute_ask(request, form):
    """Alte synchrone Variante — nicht mehr aktiv verwendet, aber erhalten
    als Referenz/Notfall-Fallback falls Celery nicht verfügbar ist."""
    mode = form.cleaned_data['mode']
    question = form.cleaned_data['question']
    primary = form.cleaned_data.get('primary_model') or 'opus'
    council_ids = form.cleaned_data.get('council_models') or []
    top_k = form.cleaned_data.get('top_k') or 6

    rq = ResearchQuery.objects.create(
        owner=request.user, question=question, mode=mode, status='done',
    )
    try:
        if mode == 'rag':
            primary_cfg = council_service.MODELS.get(primary)
            primary_model_name = primary_cfg['model'] if primary_cfg else 'claude-opus-4-7'
            res = rag_service.ask_rag(question, request.user, top_k=top_k,
                                      model=primary_model_name, model_id=primary)
            rq.answer = res['answer']
            rq.sources = res['sources']
            rq.models_used = [primary]
            rq.duration_s = res['duration_s']
            rq.total_cost_usd = res.get('cost_usd', 0.0)
            # Token/Cost des RAG-Calls auch strukturiert ablegen
            rq.raw_responses = {'rag': {
                'model': primary,
                'tokens': res.get('tokens', {}),
                'cost_usd': res.get('cost_usd', 0.0),
            }}
        elif mode == 'council':
            if not council_ids:
                raise ValueError('Bitte mindestens ein Council-Modell auswählen.')
            res = council_service.ask_council(question, request.user, council_ids)
            rq.raw_responses = {'council': res['results']}
            rq.models_used = council_ids
            rq.duration_s = res['duration_s']
            rq.total_cost_usd = res.get('total_cost_usd', 0.0)
            rq.answer = _format_council_summary(res['results'])
        elif mode == 'hybrid':
            # Hybrid = Council zuerst ABFRAGEN, dann Primär-Modell VALIDIERT
            # und DISKUTIERT die Council-Antworten (mit RAG-Kontext, falls vorhanden).
            primary_cfg = council_service.MODELS.get(primary)
            if not primary_cfg:
                raise ValueError(f'Unbekanntes Primär-Modell: {primary}')
            if not council_ids:
                council_ids = ['gpt', 'gemini', 'deepseek']
            # Parallele Council-Abfrage mit der Originalfrage
            cres = council_service.ask_council(question, request.user, council_ids)
            # RAG-Quellen für Validierung (optional)
            try:
                sources = rag_service.retrieve(question, top_k=top_k)
            except Exception:
                sources = []
            rq.sources = [s.as_dict() for s in sources]
            # Primär-Modell: validiere die Council-Antworten + diskutiere
            validation_prompt = _validation_prompt(question, cres['results'], sources)
            val_res = council_service._call_one(
                primary, validation_prompt, request.user, max_tokens=2500, timeout=180)
            if val_res.get('ok'):
                rq.answer = val_res['text']
            else:
                rq.answer = (f'(Primär-Validierung fehlgeschlagen: {val_res.get("error")})\n\n'
                             + _format_council_summary(cres['results']))
            rq.raw_responses = {
                'primary_validation': val_res,
                'council': cres['results'],
                'rag_sources_count': len(sources),
            }
            rq.models_used = [primary] + council_ids
            rq.duration_s = cres['duration_s'] + (val_res.get('duration_s') or 0)
            rq.total_cost_usd = (cres.get('total_cost_usd', 0.0)
                                 + (val_res.get('cost_usd') or 0.0))
        else:
            raise ValueError(f'Unbekannter Modus: {mode}')
    except Exception as e:
        logger.exception('research ask failed')
        rq.error = f'{type(e).__name__}: {e}'
        messages.error(request, f'Anfrage fehlgeschlagen: {rq.error}')
    rq.save()
    return redirect(rq.get_absolute_url())


def _validation_prompt(question: str, council_results: list[dict],
                       rag_sources: list) -> str:
    parts = [
        'Du bist ein wissenschaftlicher Reviewer. Mehrere KI-Modelle haben',
        'dieselbe Frage beantwortet. Dein Auftrag:',
        '',
        '1. **Validieren:** Welche Aussagen sind über die Modelle hinweg konsistent '
        '(hohe Konfidenz)? Welche sind widersprüchlich oder nur in einer Antwort '
        'enthalten (niedrige Konfidenz)?',
        '2. **Diskutieren:** Gewichte die Unterschiede. Welches Modell argumentiert '
        'stärker, wo? Welche Aussagen sind plausibel, welche fraglich?',
        '3. **Ergänzen:** Fehlt etwas Wichtiges in allen Antworten? (Nutze die '
        'untenstehenden RAG-Quellen als Faktencheck, falls vorhanden.)',
        '4. **Synthetisieren:** Schreibe eine konsolidierte, wissenschaftlich '
        'präzise Antwort auf Deutsch, die alle wertvollen Beiträge integriert.',
        '',
        f'ORIGINALFRAGE:\n{question}',
        '',
        '=== ANTWORTEN DER MODELLE ===',
    ]
    for i, r in enumerate(council_results, 1):
        name = r.get('display', r.get('model'))
        if r.get('ok'):
            text = (r.get('text') or '').strip()
            parts.append(f'\n--- Modell {i}: {name} ---\n{text[:4000]}')
        else:
            parts.append(f'\n--- Modell {i}: {name} — Fehler: {r.get("error")} ---')

    if rag_sources:
        parts.append('\n\n=== RAG-QUELLEN (aus eigener Library, Faktencheck) ===')
        for s in rag_sources:
            parts.append(f'\n[{s.idx}] {s.authors} ({s.year}). {s.title}\n{s.text[:1500]}')

    parts.append(
        '\n\nFormatiere deine Antwort in Markdown mit den Abschnitten:\n'
        '1. **Konsens** (konsistente Aussagen),\n'
        '2. **Streitpunkte** (widersprüchliche/unsichere Aussagen),\n'
        '3. **Ergänzung** (was fehlt),\n'
        '4. **Konsolidierte Antwort** (finale Synthese).'
    )
    return '\n'.join(parts)


def _format_council_summary(results: list[dict]) -> str:
    lines = ['## Council-Antworten\n']
    for r in results:
        head = f"### {r.get('display', r.get('model'))}"
        if r.get('duration_s') is not None:
            head += f" ({r['duration_s']:.1f}s)"
        lines.append(head)
        if r.get('ok'):
            lines.append(r.get('text', '')[:3000])
        else:
            lines.append(f"_Fehler: {r.get('error', '-')}_")
        lines.append('')
    return '\n'.join(lines)


@login_required
def query_detail(request, pk):
    rq = get_object_or_404(ResearchQuery, pk=pk, owner=request.user)
    council_results = rq.raw_responses.get('council', []) if isinstance(rq.raw_responses, dict) else []
    return render(request, 'research/query_detail.html', {
        'q': rq,
        'council_results': council_results,
        'is_share': False,
    })


def _parse_redakteur_clusters(redakteur_text: str, council_results: list[dict]) -> dict[str, int]:
    """Aus dem Redakteur-Markdown extrahieren, welche Modelle gemeinsam an
    welcher Idee beteiligt waren. Gibt Mapping model_id -> cluster_idx zurück.
    """
    import re
    if not redakteur_text or not council_results:
        return {}
    # display-name -> model_id, plus model_id -> model_id (Falls Modell direkt
    # mit ID erwaehnt wurde).
    name_to_id: dict[str, str] = {}
    for r in council_results:
        mid = r.get('model') or ''
        name = r.get('display') or ''
        if name and mid:
            name_to_id[name.lower()] = mid
        if mid:
            name_to_id[mid.lower()] = mid
    cluster_map: dict[str, int] = {}
    sections = re.split(r'^##\s*Idee\s*\d+', redakteur_text, flags=re.MULTILINE)
    cluster_idx = 0
    for sec in sections[1:]:  # erste Sektion vor erster "## Idee" ignorieren
        proposers_text = ''
        for label in ('Vorgeschlagen von', 'Mitgetragen von'):
            m = re.search(rf'\*\*{label}:\*\*\s*([^\n]+)', sec)
            if m:
                proposers_text += ' ' + m.group(1)
        if not proposers_text.strip():
            continue
        ptxt = proposers_text.lower()
        any_match = False
        for name, mid in name_to_id.items():
            if name in ptxt and mid not in cluster_map:
                cluster_map[mid] = cluster_idx
                any_match = True
        if any_match:
            cluster_idx += 1
    return cluster_map


def _generate_graph_meta(question: str, council_results: list, user,
                          redakteur_text: str = '') -> dict:
    """Ein einziger GLM-Call der pro Modell Stichpunkte (Hover-Anzeige) und
    fuer alle Modelle zusammen die Cluster-Zuordnung liefert. Optional auch
    Stichpunkte fuer den Redakteur-Output.

    Returns dict mit:
      models: { model_id: { summary: [str, ...], cluster: int } }
      clusters: [ { id: int, name: str, model_ids: [str] } ]
      redakteur_summary: [str, ...] (falls redakteur_text vorhanden)
    """
    from .services import council as council_service
    # Antworten kompakt zusammenstellen — IDs + display-Name + Antwort gekürzt
    blocks = []
    valid_ids = []
    for r in council_results:
        if not r.get('ok'):
            continue
        text = (r.get('text') or '').strip()
        if not text:
            continue
        mid = r.get('model') or '?'
        name = r.get('display') or mid
        valid_ids.append(mid)
        blocks.append(f'### {mid} ({name})\n{text[:2500]}')
    if not blocks:
        return {'models': {}, 'clusters': [], 'redakteur_summary': []}
    redakteur_block = ''
    if redakteur_text:
        redakteur_block = f'\n\n=== REDAKTEUR-SYNTHESE (eigener Text, brauche ich auch in Stichpunkten) ===\n{redakteur_text[:4000]}'
    prompt = (
        'Du bist Redakteur. Mehrere KI-Modelle haben dieselbe Frage beantwortet.\n'
        'Deine drei Aufgaben — STRIKT aus den Antworten, nichts dazudichten:\n\n'
        '1. Pro Modell: liefere 4-6 Stichpunkte (jeweils ca. 5-10 Wörter, also\n'
        '   knappe Halbsätze — KEINE ganzen Sätze, aber auch nicht nur 3 Wörter).\n'
        '   Sie sollen den Kern UND die spezifischen Akzente der Antwort dieses\n'
        '   Modells zeigen. Schreibe so, dass man im Hover beim Lesen versteht\n'
        '   WAS das Modell konkret gesagt hat.\n'
        '   Beispiel gut: ["Cyan-Licht 480nm hemmt Ethylen-Synthese",\n'
        '                  "Wirkung speziell bei Banane gezeigt",\n'
        '                  "Stützt sich auf Wang et al. 2019",\n'
        '                  "Empfohlene Lichtdosis: 50 µmol/m²/s",\n'
        '                  "Effekt nimmt nach 7 Tagen ab"]\n'
        '   Beispiel schlecht (zu kurz): ["Ethylen", "Banane", "Wang 2019"]\n'
        '   Beispiel schlecht (zu lang): ganze Sätze mit "Das Modell argumentiert..."\n\n'
        '2. Cluster die Modelle nach inhaltlicher Ähnlichkeit ihrer Antworten.\n'
        '   Gleiche/sehr ähnliche Antworten -> gleiches Cluster.\n'
        '   Unterschiedliche Schwerpunkte -> verschiedene Cluster.\n'
        '   Pro Cluster ein kurzer beschreibender Name (max 4 Wörter).\n'
        '   Wichtig: TATSÄCHLICHE Ähnlichkeit, nicht nur ein einzelnes Stichwort.\n'
        '   Es muss NICHT jedes Modell in einem Cluster mit anderen sein —\n'
        '   ein einzelnes Modell kann auch ein Solo-Cluster bilden.\n'
        '   Ziel: 2-5 Cluster bei mehreren Modellen.\n\n'
        '3. Falls eine REDAKTEUR-SYNTHESE-Sektion unten vorhanden ist:\n'
        '   liefere ebenfalls 4-6 Halbsatz-Stichpunkte (5-10 Wörter) im Feld\n'
        '   "redakteur_summary" — selbe Stilregeln wie bei den Modellen.\n'
        '   Falls keine Redakteur-Sektion: leeres Array.\n\n'
        f'FRAGE:\n{question}\n\n'
        '=== ANTWORTEN DER MODELLE (mit ID) ===\n'
        + '\n\n'.join(blocks)
        + redakteur_block
        + '\n\n=== OUTPUT-FORMAT (NUR dieses JSON, keine Erklaerung drumherum) ===\n'
        + '{\n'
        + '  "models": {\n'
        + '    "<model_id>": { "summary": ["...", "...", "...", "..."], "cluster": <int> }\n'
        + '  },\n'
        + '  "clusters": [\n'
        + '    { "id": <int>, "name": "<kurzer Cluster-Name>", "model_ids": ["<id1>", "<id2>"] }\n'
        + '  ],\n'
        + '  "redakteur_summary": ["...", "...", "...", "..."]\n'
        + '}\n'
        + 'Verwende AUSSCHLIESSLICH die Modell-IDs aus den Sektionen oben '
        + f'({", ".join(valid_ids)}).'
    )
    # Wichtig: no_continuation=True — Continuation zerstoert JSON (zweiter
    # Call kommt mit "fortsetzen"-Prompt der nicht JSON liefert -> kaputtes
    # Stueckwerk). max_tokens=12000 damit JSON in einem Rutsch passt.
    # timeout=360s damit GLM auch bei viel Input genug Zeit hat.
    try:
        res = council_service._call_one(
            'glm', prompt, user, max_tokens=12000, timeout=360,
            no_continuation=True,
        )
    except Exception as exc:
        logger.warning('graph_meta GLM-Call fehlgeschlagen: %s', exc)
        return {'models': {}, 'clusters': [], 'redakteur_summary': []}
    if not res.get('ok'):
        logger.warning('graph_meta GLM-Antwort nicht ok: %s', res.get('error'))
        return {'models': {}, 'clusters': [], 'redakteur_summary': []}
    text = (res.get('text') or '').strip()
    data = _parse_graph_meta_json(text)
    if not data:
        logger.warning(
            'graph_meta JSON-Parse fehlgeschlagen — text-len=%s, head: %s, tail: %s',
            len(text), text[:200], text[-200:] if len(text) > 200 else '',
        )
        return {'models': {}, 'clusters': [], 'redakteur_summary': []}
    return _normalize_graph_meta(data)


def _normalize_graph_meta(data: dict) -> dict:
    """GLM haelt sich nicht immer ans Schema. Normalisiere beide Formen:
    - models als dict {id: {summary, cluster}} ODER list [{id, ...}]
    - cluster als int ODER cluster_ids als Liste (nimm erstes)
    - summary als Liste ODER kurzbeschreibung als String
    - cluster-id-Strings wie "c2" -> 2
    """
    def _coerce_cluster_id(val):
        if val is None:
            return -1
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            s = val.strip().lstrip('cC').lstrip('luster').lstrip()
            try:
                return int(s)
            except ValueError:
                return -1
        if isinstance(val, list) and val:
            return _coerce_cluster_id(val[0])
        return -1

    def _coerce_summary(meta):
        if not isinstance(meta, dict):
            return []
        for key in ('summary', 'stichpunkte', 'bullets'):
            v = meta.get(key)
            if isinstance(v, list):
                return [str(x).strip() for x in v if x]
            if isinstance(v, str) and v.strip():
                return [v.strip()]
        for key in ('kurzbeschreibung', 'description', 'text'):
            v = meta.get(key)
            if isinstance(v, str) and v.strip():
                return [v.strip()]
        return []

    def _coerce_cluster_value(meta):
        if not isinstance(meta, dict):
            return -1
        for key in ('cluster', 'cluster_id'):
            if key in meta:
                return _coerce_cluster_id(meta[key])
        if 'cluster_ids' in meta:
            return _coerce_cluster_id(meta['cluster_ids'])
        return -1

    raw_models = data.get('models', {})
    models: dict = {}
    if isinstance(raw_models, dict):
        for mid, meta in raw_models.items():
            models[str(mid)] = {
                'summary': _coerce_summary(meta),
                'cluster': _coerce_cluster_value(meta),
            }
    elif isinstance(raw_models, list):
        for entry in raw_models:
            if not isinstance(entry, dict):
                continue
            mid = entry.get('id') or entry.get('model_id') or entry.get('model')
            if not mid:
                continue
            models[str(mid)] = {
                'summary': _coerce_summary(entry),
                'cluster': _coerce_cluster_value(entry),
            }

    raw_clusters = data.get('clusters', [])
    clusters: list = []
    if isinstance(raw_clusters, list):
        for c in raw_clusters:
            if not isinstance(c, dict):
                continue
            cid = _coerce_cluster_id(c.get('id'))
            if cid < 0:
                continue
            name = (c.get('name') or c.get('title') or c.get('label') or f'Cluster {cid + 1}').strip()
            mids = c.get('model_ids') or c.get('models') or c.get('member_ids') or []
            if not isinstance(mids, list):
                mids = []
            clusters.append({
                'id': cid,
                'name': name[:60],
                'model_ids': [str(m) for m in mids if m],
            })
    elif isinstance(raw_clusters, dict):
        # GLM könnte auch dict liefern: {"c0": {name, models}, "c1": ...}
        for key, c in raw_clusters.items():
            if not isinstance(c, dict):
                continue
            cid = _coerce_cluster_id(key)
            name = (c.get('name') or c.get('title') or f'Cluster {cid + 1}').strip()
            mids = c.get('model_ids') or c.get('models') or []
            clusters.append({
                'id': cid,
                'name': name[:60],
                'model_ids': [str(m) for m in mids if m] if isinstance(mids, list) else [],
            })

    redakteur_summary = data.get('redakteur_summary') or data.get('redakteur') or []
    if isinstance(redakteur_summary, str):
        redakteur_summary = [redakteur_summary]
    elif not isinstance(redakteur_summary, list):
        redakteur_summary = []

    return {
        'models': models,
        'clusters': clusters,
        'redakteur_summary': redakteur_summary,
    }


def _parse_graph_meta_json(text: str) -> dict | None:
    """Robuste JSON-Extraktion fuer graph_meta-Output:
    1. Markdown-Codeblock-Wrapper (```json ... ```) entfernen.
    2. Versuche kompletten Text als JSON.
    3. Fallback: outermost {} Pair extrahieren.
    """
    if not text:
        return None
    s = text.strip()
    if s.startswith('```'):
        lines = s.split('\n')
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        s = '\n'.join(lines).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find('{')
    end = s.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


@login_required
def query_graph(request, pk):
    """Brain-Graph der Council-Antworten mit Cluster-Layout."""
    rq = get_object_or_404(ResearchQuery, pk=pk, owner=request.user)
    raw = rq.raw_responses if isinstance(rq.raw_responses, dict) else {}
    council = raw.get('council') or []
    if isinstance(council, list) and council:
        council_results = council
    else:
        council_results = []
    redak = raw.get('redakteur') or raw.get('primary_validation') or {}
    redakteur_text = redak.get('text', '') if isinstance(redak, dict) else ''

    # Graph-Meta (Stichpunkte + Cluster) — wird beim Council-Run in tasks.py
    # vorab generiert und in raw_responses['graph_meta'] gecached.
    # Beim ?refresh=1 wird neu generiert — ABER NUR via async Celery-Task,
    # niemals synchron in der View (Cloudflare 100s-Origin-Timeout = 524).
    graph_meta = raw.get('graph_meta') or None
    refresh = request.GET.get('refresh') == '1'
    if refresh and council_results:
        # Async re-generation: triggere im celery-research Worker
        try:
            from .tasks import refresh_graph_meta
            refresh_graph_meta.delay(rq.pk)
            messages.info(
                request,
                'Brain-Graph wird neu analysiert — bitte in 30-90 Sekunden die Seite neu laden.'
            )
        except Exception as exc:
            logger.warning('refresh_graph_meta-Trigger fehlgeschlagen: %s', exc)

    # Fallback: alte regex-Logik aus dem Redakteur-Markdown
    cluster_map_fallback = _parse_redakteur_clusters(redakteur_text, council_results)
    meta_models = (graph_meta or {}).get('models', {})
    clusters = (graph_meta or {}).get('clusters', [])
    cluster_names = {c.get('id'): c.get('name', '') for c in clusters if isinstance(c, dict)}

    # Daten fuer JS aufbereiten
    nodes = []
    for r in council_results:
        mid = r.get('model') or '?'
        meta = meta_models.get(mid) or {}
        cluster = meta.get('cluster')
        if cluster is None:
            cluster = cluster_map_fallback.get(mid, -1)
        full_text = (r.get('text') or '').strip()
        bullets = meta.get('summary') or []
        if not bullets:
            # Fallback-Summary: erste 200 Zeichen wenn keine Stichpunkte
            bullets = [(full_text[:180] + ('…' if len(full_text) > 180 else ''))] if full_text else []
        # Truncation-Indikator: explizites Flag aus _call_one ODER heuristisch
        # wenn output-Tokens exakt am alten 1500-Limit kleben (Legacy-Anfragen).
        out_toks = (r.get('tokens') or {}).get('output', 0)
        truncated = bool(r.get('truncated')) or (out_toks in (1500, 2000, 4000) and full_text and not full_text.rstrip().endswith(('.', '!', '?', ')', ']')))
        nodes.append({
            'id': mid,
            'name': r.get('display') or mid,
            'cluster': cluster,
            'summary': bullets,  # jetzt ein Array von Stichpunkten
            'full_text': full_text,
            'ok': bool(r.get('ok')),
            'error': r.get('error') or '',
            'duration_s': r.get('duration_s'),
            'truncated': truncated,
        })
    redakteur_node = None
    if redakteur_text:
        red_id = redak.get('model') or 'redakteur'
        red_name = redak.get('display') or 'Redakteur'
        red_summary = (graph_meta or {}).get('redakteur_summary') or []
        if not red_summary:
            red_summary = [(redakteur_text[:160] + ('…' if len(redakteur_text) > 160 else ''))]
        redakteur_node = {
            'id': red_id,
            'name': red_name,
            'full_text': redakteur_text,
            'summary': red_summary,
            'duration_s': redak.get('duration_s'),
        }
    return render(request, 'research/query_graph.html', {
        'q': rq,
        'nodes_json': json.dumps(nodes, ensure_ascii=False),
        'redakteur_json': json.dumps(redakteur_node, ensure_ascii=False) if redakteur_node else 'null',
        'has_redakteur': bool(redakteur_node),
        'cluster_names_json': json.dumps(cluster_names, ensure_ascii=False),
    })


def _build_query_markdown(rq) -> str:
    """Baut die Markdown-Repraesentation einer ResearchQuery (Frage + Antwort
    + Council-Rohantworten + Redakteur-Output + Quellen)."""
    lines = [
        f'# Anfrage #{rq.pk}',
        '',
        f'**Datum:** {rq.created_at:%d.%m.%Y %H:%M}',
        f'**Modus:** {rq.get_mode_display()}',
    ]
    if rq.models_used:
        lines.append(f'**Modelle:** {", ".join(rq.models_used)}')
    if rq.duration_s:
        lines.append(f'**Dauer:** {rq.duration_s:.1f}s')
    if rq.total_cost_usd:
        lines.append(f'**Kosten:** ${rq.total_cost_usd:.4f}')
    lines += ['', '---', '', '## Frage', '', rq.question, '']

    if rq.answer:
        lines += ['## Antwort', '', rq.answer, '']

    raw = rq.raw_responses if isinstance(rq.raw_responses, dict) else {}
    council = raw.get('council')
    if isinstance(council, list) and council:
        lines += ['---', '', '## Council-Rohantworten (alle Modelle)', '']
        for r in council:
            name = r.get('display') or r.get('model', '?')
            dur = f' · {r["duration_s"]:.1f}s' if r.get('duration_s') is not None else ''
            lines.append(f'### {name}{dur}')
            lines.append('')
            if r.get('ok'):
                lines.append((r.get('text') or '').strip())
            else:
                lines.append(f'_Fehler: {r.get("error", "-")}_')
            lines.append('')

    redak = raw.get('redakteur') or raw.get('primary_validation')
    if isinstance(redak, dict) and redak.get('text'):
        lines += ['---', '',
                  f'## Redakteur-/Primaer-Modell-Output ({redak.get("display") or redak.get("model","?")})',
                  '', redak['text'], '']

    if rq.sources:
        lines += ['---', '', '## Quellen (RAG)', '']
        for s in rq.sources:
            if not isinstance(s, dict):
                continue
            title = s.get('title') or '-'
            authors = s.get('authors') or '?'
            year = s.get('year') or '?'
            lines.append(f'- **{title}** — {authors} ({year})')
            if s.get('text'):
                snippet = (s['text'] or '').strip().replace('\n', ' ')[:300]
                lines.append(f'  > {snippet}...')
        lines.append('')
    return '\n'.join(lines)


# Modernes Print-/Web-CSS fuer HTML- und PDF-Export
_QUERY_HTML_CSS = """
@page { size: A4; margin: 14mm 14mm 16mm 14mm; }
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 9.5pt; line-height: 1.5; color: #0f172a; background: #fff;
}
body { padding: 18px 24px; max-width: 920px; margin: 0 auto; }

/* H1 = Cover-Title mit Gradient-Akzent */
h1 {
  font-size: 18pt; font-weight: 700; margin: 0 0 6pt; color: #0f172a;
  letter-spacing: -0.015em;
  padding: 4pt 0 8pt;
  border-bottom: 3px solid;
  border-image: linear-gradient(90deg, #6366f1, #8b5cf6, #ec4899) 1;
}

/* H2 = Section-Title — Section-Pill mit Akzent-Bar */
h2 {
  font-size: 13pt; font-weight: 700; margin: 18pt 0 6pt;
  padding: 4pt 0 4pt 10pt;
  color: #1e293b;
  border-left: 4px solid #6366f1;
  background: linear-gradient(90deg, #eef2ff 0%, transparent 100%);
  border-radius: 0 4px 4px 0;
  page-break-after: avoid;
}

/* H3 = Modell-Header in Council-Sektion — farblich akzentuiert */
h3 {
  font-size: 11pt; font-weight: 600; margin: 12pt 0 4pt;
  padding: 3pt 8pt;
  color: #ffffff;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 6px;
  display: inline-block;
  letter-spacing: 0.005em;
  page-break-after: avoid;
}
/* Variation für jede dritte H3 — abwechselnde Farbtöne */
h3:nth-of-type(3n+1) { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }
h3:nth-of-type(3n+2) { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
h3:nth-of-type(3n)   { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }

h4 { font-size: 9.5pt; font-weight: 600; margin: 8pt 0 3pt; color: #475569; }
p { margin: 5pt 0; }
strong { font-weight: 600; color: #0f172a; }
em { font-style: italic; color: #475569; }
a { color: #4f46e5; text-decoration: none; border-bottom: 1px dotted #c7d2fe; }
ul, ol { margin: 5pt 0; padding-left: 18px; }
li { margin: 1.5pt 0; }
li::marker { color: #6366f1; }
hr {
  border: none; height: 1.5px; margin: 14pt 0;
  background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
}
blockquote {
  margin: 6pt 0; padding: 6pt 12pt;
  border-left: 4px solid #6366f1;
  background: #f8fafc; color: #475569;
  border-radius: 0 6px 6px 0;
  font-size: 9pt;
  page-break-inside: avoid;
}
code {
  background: #eef2ff; border: 1px solid #c7d2fe; color: #4338ca;
  padding: 0.5pt 4pt;
  border-radius: 3px; font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 8.5pt; font-weight: 500;
}
pre {
  background: #0f172a; color: #e2e8f0; padding: 8pt 10pt; border-radius: 6px;
  overflow-x: auto; font-size: 8pt; line-height: 1.5;
  page-break-inside: avoid;
  border-left: 3px solid #6366f1;
}
pre code { background: none; border: none; padding: 0; color: inherit; }

table {
  border-collapse: collapse; margin: 8pt 0; width: 100%; font-size: 8.5pt;
  page-break-inside: avoid;
  border-radius: 4px; overflow: hidden;
}
th, td { border: 1px solid #e2e8f0; padding: 4pt 7pt; text-align: left; }
th {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #fff;
  font-weight: 600; letter-spacing: 0.01em;
}
tr:nth-child(even) td { background: #f8fafc; }

/* Meta-Header oben (Datum/Modus/Modelle) — als Info-Pillen-Reihe */
h1 + p { color: #64748b; font-size: 9pt; margin: 4pt 0 12pt; line-height: 1.7; }
h1 + p strong { color: #4338ca; }

@media print {
  body { padding: 0; }
  h2, h3 { page-break-after: avoid; }
  pre, table, blockquote { page-break-inside: avoid; }
}
"""


def _markdown_to_html(md_text: str) -> str:
    """Konvertiert Markdown zu HTML via markdown-it-py (gleiche Render-Engine
    wie marked.js im Frontend, gfm-Tabellen + breaks aktiviert)."""
    from markdown_it import MarkdownIt
    # 'linkify': True braucht das linkify-it-py-Modul (nicht installiert).
    # gfm-like setzt es per Default auf True — wir muessen explizit auf False.
    md = MarkdownIt('gfm-like', {'breaks': True, 'html': False, 'linkify': False})
    return md.render(md_text)


def _build_query_html(rq) -> str:
    """Standalone-HTML der Anfrage mit eingebettetem Stylesheet — geeignet
    fuer Download (.html) UND als WeasyPrint-Input fuers PDF."""
    md_text = _build_query_markdown(rq)
    body_html = _markdown_to_html(md_text)
    title = f'Anfrage #{rq.pk} · {rq.get_mode_display()}'
    return (
        '<!DOCTYPE html>\n'
        '<html lang="de"><head>\n'
        '<meta charset="utf-8">\n'
        f'<title>{title}</title>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
        '<style>' + _QUERY_HTML_CSS + '</style>\n'
        '</head><body>\n'
        + body_html
        + '\n</body></html>'
    )


@login_required
def query_download(request, pk):
    """Markdown-Download (Format-Auswahl via ?format=md|html|pdf)."""
    rq = get_object_or_404(ResearchQuery, pk=pk, owner=request.user)
    fmt = (request.GET.get('format') or 'md').lower()

    if fmt == 'html':
        html = _build_query_html(rq)
        response = HttpResponse(html, content_type='text/html; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="research-{rq.pk}.html"'
        return response

    if fmt == 'pdf':
        html = _build_query_html(rq)
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        except Exception as exc:
            logger.exception('PDF-Render fehlgeschlagen')
            return HttpResponse(f'PDF-Render-Fehler: {exc}', status=500,
                                content_type='text/plain; charset=utf-8')
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="research-{rq.pk}.pdf"'
        return response

    # Default: markdown
    body = _build_query_markdown(rq)
    response = HttpResponse(body, content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="research-{rq.pk}.md"'
    return response


@login_required
def query_status(request, pk):
    """JSON-Endpoint fürs Polling aus dem Detail-Template."""
    rq = get_object_or_404(ResearchQuery, pk=pk, owner=request.user)
    elapsed = None
    if rq.started_at:
        end = rq.finished_at or timezone.now()
        elapsed = (end - rq.started_at).total_seconds()
    return JsonResponse({
        'status': rq.status,
        'elapsed_s': elapsed,
        'error': rq.error or None,
    })


@login_required
def query_toggle_share(request, pk):
    """Toggelt is_public — schaltet Public-Share-Link an/aus."""
    rq = get_object_or_404(ResearchQuery, pk=pk, owner=request.user)
    rq.is_public = not rq.is_public
    rq.save(update_fields=['is_public'])
    return JsonResponse({
        'is_public': rq.is_public,
        'share_url': request.build_absolute_uri(
            f"/research/share/{rq.share_token}/"
        ) if rq.is_public else None,
    })


def _share_get(token):
    """Holt eine ResearchQuery via share_token. Nur lesend, nur wenn is_public."""
    rq = get_object_or_404(ResearchQuery, share_token=token, is_public=True)
    return rq


def share_detail(request, token):
    """Public-Detail-Ansicht ohne Login. Gleiche Template wie query_detail,
    aber mit is_share=True — UI versteckt interaktive Elemente."""
    rq = _share_get(token)
    council_results = rq.raw_responses.get('council', []) if isinstance(rq.raw_responses, dict) else []
    return render(request, 'research/query_detail.html', {
        'q': rq,
        'council_results': council_results,
        'is_share': True,
    })


def share_graph(request, token):
    """Public-Brain-Graph ohne Login."""
    rq = _share_get(token)
    raw = rq.raw_responses if isinstance(rq.raw_responses, dict) else {}
    council = raw.get('council') or []
    council_results = council if isinstance(council, list) else []
    redak = raw.get('redakteur') or raw.get('primary_validation') or {}
    redakteur_text = redak.get('text', '') if isinstance(redak, dict) else ''
    graph_meta = raw.get('graph_meta') or {}
    cluster_map_fallback = _parse_redakteur_clusters(redakteur_text, council_results)
    meta_models = (graph_meta or {}).get('models', {})
    clusters = (graph_meta or {}).get('clusters', [])
    cluster_names = {c.get('id'): c.get('name', '') for c in clusters if isinstance(c, dict)}
    nodes = []
    for r in council_results:
        mid = r.get('model') or '?'
        meta = meta_models.get(mid) or {}
        cluster = meta.get('cluster')
        if cluster is None:
            cluster = cluster_map_fallback.get(mid, -1)
        full_text = (r.get('text') or '').strip()
        bullets = meta.get('summary') or []
        if not bullets:
            bullets = [(full_text[:180] + ('…' if len(full_text) > 180 else ''))] if full_text else []
        out_toks = (r.get('tokens') or {}).get('output', 0)
        truncated = bool(r.get('truncated')) or (out_toks in (1500, 2000, 4000) and full_text and not full_text.rstrip().endswith(('.', '!', '?', ')', ']')))
        nodes.append({
            'id': mid, 'name': r.get('display') or mid, 'cluster': cluster,
            'summary': bullets, 'full_text': full_text,
            'ok': bool(r.get('ok')), 'error': r.get('error') or '',
            'duration_s': r.get('duration_s'), 'truncated': truncated,
        })
    redakteur_node = None
    if redakteur_text:
        red_summary = (graph_meta or {}).get('redakteur_summary') or []
        if not red_summary:
            red_summary = [(redakteur_text[:160] + ('…' if len(redakteur_text) > 160 else ''))]
        redakteur_node = {
            'id': redak.get('model') or 'redakteur',
            'name': redak.get('display') or 'Redakteur',
            'full_text': redakteur_text, 'summary': red_summary,
            'duration_s': redak.get('duration_s'),
        }
    return render(request, 'research/query_graph.html', {
        'q': rq,
        'nodes_json': json.dumps(nodes, ensure_ascii=False),
        'redakteur_json': json.dumps(redakteur_node, ensure_ascii=False) if redakteur_node else 'null',
        'has_redakteur': bool(redakteur_node),
        'cluster_names_json': json.dumps(cluster_names, ensure_ascii=False),
        'is_share': True,
    })


def share_download(request, token):
    """Public-Download (Markdown/HTML/PDF) ohne Login."""
    rq = _share_get(token)
    fmt = (request.GET.get('format') or 'md').lower()
    if fmt == 'html':
        html = _build_query_html(rq)
        response = HttpResponse(html, content_type='text/html; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="research-{rq.pk}.html"'
        return response
    if fmt == 'pdf':
        html = _build_query_html(rq)
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="research-{rq.pk}.pdf"'
        return response
    body = _build_query_markdown(rq)
    response = HttpResponse(body, content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="research-{rq.pk}.md"'
    return response


@login_required
def history(request):
    qs = ResearchQuery.objects.filter(owner=request.user)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'research/history.html', {'page': page})


@login_required
def stats(request):
    """Verbrauchsstatistik: Pro Modell + Pro Tag, einstellbarer Zeitraum."""
    from datetime import timedelta, datetime, date
    from collections import defaultdict

    # Zeitraum — GET-Parameter `range` in (today, 7d, 30d, 90d, all, custom)
    today = timezone.localdate()
    rng = request.GET.get('range', '30d')
    since = None
    until = None
    if rng == 'today':
        since = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    elif rng == '7d':
        since = timezone.now() - timedelta(days=7)
    elif rng == '30d':
        since = timezone.now() - timedelta(days=30)
    elif rng == '90d':
        since = timezone.now() - timedelta(days=90)
    elif rng == 'custom':
        s = request.GET.get('since')
        u = request.GET.get('until')
        if s:
            try:
                since = timezone.make_aware(datetime.strptime(s, '%Y-%m-%d'))
            except ValueError:
                since = None
        if u:
            try:
                until = timezone.make_aware(datetime.strptime(u, '%Y-%m-%d') + timedelta(days=1))
            except ValueError:
                until = None

    queries_qs = ResearchQuery.objects.filter(owner=request.user, status='done')
    if since:
        queries_qs = queries_qs.filter(created_at__gte=since)
    if until:
        queries_qs = queries_qs.filter(created_at__lt=until)

    # Aggregations
    per_model = defaultdict(lambda: {'queries': 0, 'input_tokens': 0,
                                     'output_tokens': 0, 'cost': 0.0})
    per_day = defaultdict(lambda: {'cost': 0.0, 'queries': 0})
    per_day_per_model = defaultdict(lambda: defaultdict(float))
    total_cost = 0.0
    total_queries = 0
    total_input = 0
    total_output = 0

    def _accum(day, model_id, tokens, cost):
        t_in = int((tokens or {}).get('input', 0) or 0)
        t_out = int((tokens or {}).get('output', 0) or 0)
        c = float(cost or 0)
        per_model[model_id]['queries'] += 1
        per_model[model_id]['input_tokens'] += t_in
        per_model[model_id]['output_tokens'] += t_out
        per_model[model_id]['cost'] += c
        per_day_per_model[day][model_id] += c
        nonlocal_state['in'] += t_in
        nonlocal_state['out'] += t_out

    nonlocal_state = {'in': 0, 'out': 0}

    for q in queries_qs.iterator():
        total_queries += 1
        total_cost += float(q.total_cost_usd or 0)
        d = timezone.localtime(q.created_at).date().isoformat()
        per_day[d]['queries'] += 1
        per_day[d]['cost'] += float(q.total_cost_usd or 0)

        rr = q.raw_responses or {}
        if 'rag' in rr and isinstance(rr['rag'], dict):
            _accum(d, rr['rag'].get('model', '?'),
                   rr['rag'].get('tokens'), rr['rag'].get('cost_usd'))
        if 'primary_validation' in rr and isinstance(rr['primary_validation'], dict):
            pv = rr['primary_validation']
            _accum(d, pv.get('model', '?'),
                   pv.get('tokens'), pv.get('cost_usd'))
        for r in rr.get('council', []) or []:
            if isinstance(r, dict):
                _accum(d, r.get('model', '?'),
                       r.get('tokens'), r.get('cost_usd'))

    total_input = nonlocal_state['in']
    total_output = nonlocal_state['out']

    # Stabile, gut unterscheidbare Farbpalette für Modelle
    PALETTE = [
        '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4',
        '#8b5cf6', '#ec4899', '#14b8a6', '#0ea5e9', '#84cc16',
        '#f97316', '#a855f7', '#22c55e', '#eab308', '#3b82f6',
        '#e11d48', '#d946ef', '#0891b2', '#059669', '#ca8a04',
        '#dc2626', '#7c3aed', '#0284c7', '#65a30d', '#be185d',
    ]
    # Sortiere Modelle nach Gesamtkosten (teuerste zuerst → stabile Farbzuweisung)
    sorted_model_ids = sorted(per_model.keys(),
                              key=lambda m: per_model[m]['cost'], reverse=True)
    color_map = {mid: PALETTE[i % len(PALETTE)]
                 for i, mid in enumerate(sorted_model_ids)}

    # Prepare sorted list for template
    model_rows = []
    for mid in sorted_model_ids:
        d = per_model[mid]
        cfg = council_service.MODELS.get(mid)
        display = cfg['name'] if cfg else mid
        provider = cfg['provider'] if cfg else '—'
        model_rows.append({
            'id': mid,
            'display': display,
            'provider': provider,
            'color': color_map[mid],
            'queries': d['queries'],
            'input_tokens': d['input_tokens'],
            'output_tokens': d['output_tokens'],
            'cost': d['cost'],
            'cost_share': (d['cost'] / total_cost * 100) if total_cost else 0,
        })

    # Day-series mit Model-Segmenten für stacked bar chart
    day_series = []
    max_day_cost = max((v['cost'] for v in per_day.values()), default=0.0) or 1
    for d, meta in sorted(per_day.items()):
        # Segmente: sortiert nach Kosten desc pro Tag
        segs_raw = sorted(per_day_per_model.get(d, {}).items(),
                          key=lambda kv: kv[1], reverse=True)
        segs = []
        for mid, cost in segs_raw:
            if cost <= 0:
                continue
            cfg = council_service.MODELS.get(mid)
            display = cfg['name'] if cfg else mid
            segs.append({
                'id': mid,
                'display': display,
                'cost': cost,
                'share_of_day': (cost / meta['cost'] * 100) if meta['cost'] else 0,
                'color': color_map.get(mid, '#94a3b8'),
            })
        day_series.append((d, {
            'cost': meta['cost'],
            'queries': meta['queries'],
            'height_pct': (meta['cost'] / max_day_cost * 100) if max_day_cost else 0,
            'segments': segs,
        }))

    return render(request, 'research/stats.html', {
        'rng': rng,
        'since': since,
        'until': until,
        'total_cost': total_cost,
        'total_queries': total_queries,
        'total_input': total_input,
        'total_output': total_output,
        'model_rows': model_rows,
        'day_series': day_series,
        'max_day_cost': max_day_cost,
        'custom_since': request.GET.get('since', ''),
        'custom_until': request.GET.get('until', ''),
    })


# api_keys-View entfernt: wird zentral unter /accounts/neue-api-einstellungen/ verwaltet.
