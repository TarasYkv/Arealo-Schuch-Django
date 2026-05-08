"""Celery-Tasks für asynchrone Research-Anfragen.

Ohne Async laufen Council-Abfragen oft länger als Cloudflares 100s-Timeout (524).
Daher:
- View erstellt ResearchQuery(status='pending') und dispatcht `execute_research_query`
- Frontend pollt /research/ask/<id>/status/ alle 2s
- Wenn status='done' oder 'failed' → Detail-Seite zeigt Ergebnis
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(time_limit=600, soft_time_limit=540, queue='research')
def refresh_graph_meta(query_id: int):
    """Re-generiert graph_meta fuer eine bestehende ResearchQuery.
    Wird von der query_graph-View bei ?refresh=1 angetrieben — async damit
    der Web-Request nicht in den Cloudflare-100s-Timeout laeuft.
    """
    from .models import ResearchQuery
    from .views import _generate_graph_meta
    try:
        rq = ResearchQuery.objects.get(pk=query_id)
    except ResearchQuery.DoesNotExist:
        return
    raw = rq.raw_responses if isinstance(rq.raw_responses, dict) else {}
    council_results = raw.get('council') or []
    redak = raw.get('redakteur') or raw.get('primary_validation') or {}
    redakteur_text = redak.get('text', '') if isinstance(redak, dict) else ''
    graph_meta = _generate_graph_meta(
        rq.question, council_results, rq.owner, redakteur_text=redakteur_text,
    )
    if graph_meta.get('models') or graph_meta.get('clusters'):
        raw['graph_meta'] = graph_meta
        rq.raw_responses = raw
        rq.save(update_fields=['raw_responses'])
    return {'pk': query_id, 'ok': bool(graph_meta.get('models'))}


@shared_task(bind=True, time_limit=2400, soft_time_limit=2280,
             queue='research')
def execute_research_query(self, query_id: int):
    """Führt eine ResearchQuery (RAG/Council/Hybrid) im Worker aus."""
    from .models import ResearchQuery
    from .services import rag as rag_service
    from .services import council as council_service

    # Lokale Helper importiert innerhalb der Task — vermeidet Circular-Imports.
    def _format_council_summary(results):
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

    def _redaktion_prompt(question, council_results):
        """Strikt redaktioneller Prompt — Primaer-Modell ordnet die Council-
        Antworten in einen lesbaren Bericht, OHNE eigene Inhalte zu erfinden.

        Im Unterschied zu _validation_prompt:
          - keine RAG-Quellen, keine Faktencheck-Aufgabe
          - keine Aufforderung zu eigener Synthese / Konsolidierung
          - ausdrueckliches "nichts dazudichten"
        """
        parts = [
            'Du bist Redakteur. Deine EINZIGE Aufgabe ist, die Antworten der',
            'verschiedenen KI-Modelle zur folgenden Frage in einen lesbaren',
            'Bericht zu STRUKTURIEREN.',
            '',
            'ABSOLUT VERBOTEN:',
            '- Eigene Ideen, Hypothesen oder Behauptungen erfinden, die nicht',
            '  in mindestens einer Modell-Antwort stehen.',
            '- Quellen, Studien oder DOIs ergaenzen, die nicht in den',
            '  Antworten erwaehnt sind.',
            '- "Vermutlich"/"Wahrscheinlich"/"Es ist anzunehmen" ohne dass ein',
            '  Modell genau dies behauptet hat.',
            '',
            'ERLAUBT:',
            '- Aehnliche Ideen mehrerer Modelle zu einem Cluster zusammenfassen.',
            '- Modelle EXPLIZIT mit Namen nennen ("Claude Opus meint X,',
            '  GPT meint Y, Gemini fuegt Z hinzu").',
            '- Originalformulierungen leicht straffen fuer Lesbarkeit.',
            '- Widersprueche zwischen Modellen sichtbar machen.',
            '',
            f'FRAGE:\n{question}',
            '',
            '=== ANTWORTEN DER MODELLE ===',
        ]
        for i, r in enumerate(council_results, 1):
            name = r.get('display', r.get('model'))
            if r.get('ok'):
                text = (r.get('text') or '').strip()
                parts.append(f'\n--- {name} ---\n{text[:3500]}')
            else:
                parts.append(f'\n--- {name} — Fehler: {r.get("error")} ---')
        parts.append('\n\nOUTPUT-FORMAT (Markdown):')
        parts.append(
            '\n## Idee 1: [kurzer Titel der Idee]\n'
            '**Vorgeschlagen von:** [Modell-Name explizit]\n'
            '**Mitgetragen von:** [andere Modelle, falls aehnliche Idee — sonst weglassen]\n\n'
            '[2-4 Saetze Beschreibung — STRIKT aus den Antworten, keine eigene Anreicherung]\n\n'
            '**Was daran besonders:** [Begruendung warum diese Idee bemerkenswert '
            'ist — STRIKT auf Basis der Modell-Antworten]\n\n'
            '[Falls Widerspruch zu einer anderen Idee: "⚠ Konflikt mit Idee X: ..."]\n'
        )
        parts.append(
            '\nWiederhole das Format fuer jede eigenstaendige Idee. '
            'Beginne mit den Ideen, die mehrere Modelle gemeinsam haben '
            '(hoehere Konfidenz), dann einzeln vorgeschlagene Ideen.'
        )
        return '\n'.join(parts)

    def _validation_prompt(question, council_results, rag_sources):
        # Konservativer Cut: Council-Antworten auf 3500 Zeichen, RAG-Quellen
        # auf volle Länge (nur Top-5). Typische Council-Antwort ist 1500-3000
        # Zeichen, d.h. 3500 genug für die allermeisten ohne Qualitätsverlust.
        parts = [
            'Du bist ein wissenschaftlicher Reviewer. Mehrere KI-Modelle haben',
            'dieselbe Frage beantwortet. Dein Auftrag:',
            '',
            '1. **Validieren:** Welche Aussagen sind konsistent (hohe Konfidenz)? '
            'Welche widersprüchlich oder nur einzeln?',
            '2. **Diskutieren:** Gewichte die Unterschiede. Welches Modell argumentiert '
            'stärker, wo? Welche Aussagen sind plausibel, welche fraglich?',
            '3. **Ergänzen:** Fehlt etwas Wichtiges? (RAG-Quellen als Faktencheck.)',
            '4. **Synthetisieren:** Schreibe eine konsolidierte, wissenschaftlich '
            'präzise Antwort auf Deutsch.',
            '',
            f'ORIGINALFRAGE:\n{question}',
            '',
            '=== ANTWORTEN DER MODELLE ===',
        ]
        for i, r in enumerate(council_results, 1):
            name = r.get('display', r.get('model'))
            if r.get('ok'):
                text = (r.get('text') or '').strip()
                parts.append(f'\n--- Modell {i}: {name} ---\n{text[:3500]}')
            else:
                parts.append(f'\n--- Modell {i}: {name} — Fehler: {r.get("error")} ---')
        if rag_sources:
            parts.append('\n\n=== RAG-QUELLEN (Faktencheck) ===')
            # Top-5 statt 6 — die sechste ist erfahrungsgemäß am schwächsten;
            # spart ~1500 Tokens ohne erkennbaren Qualitätsverlust
            for s in rag_sources[:5]:
                parts.append(f'\n[{s.idx}] {s.authors} ({s.year}). {s.title}\n{s.text}')
        parts.append(
            '\n\nFormatiere die Antwort in Markdown mit: '
            '1. **Konsens**, 2. **Streitpunkte**, 3. **Ergänzung**, '
            '4. **Konsolidierte Antwort**.'
        )
        return '\n'.join(parts)

    try:
        rq = ResearchQuery.objects.get(pk=query_id)
    except ResearchQuery.DoesNotExist:
        logger.warning('ResearchQuery %s nicht gefunden', query_id)
        return

    rq.status = 'running'
    rq.started_at = timezone.now()
    rq.save(update_fields=['status', 'started_at'])

    params = rq.params or {}
    mode = params.get('mode', rq.mode or 'rag')
    primary = params.get('primary_model', 'glm')
    council_ids = params.get('council_models', [])
    top_k = int(params.get('top_k', 6))

    user = rq.owner

    # Incremental-Save-Helper: Nach jedem fertigen Modell die Antwort in
    # die DB schreiben. Bei Worker-Crash sind so alle bis dahin gelieferten
    # Antworten gerettet (statt komplett verloren).
    def _incremental_save(result_dict):
        try:
            rq.refresh_from_db(fields=['raw_responses'])
        except Exception:
            pass
        raw = rq.raw_responses if isinstance(rq.raw_responses, dict) else {}
        council_list = raw.get('council') or []
        # Duplikate ueberspringen falls Modell schon drin (z.B. nach Restart)
        if not any(r.get('model') == result_dict.get('model') for r in council_list):
            council_list.append(result_dict)
        raw['council'] = council_list
        rq.raw_responses = raw
        rq.save(update_fields=['raw_responses', 'updated_at']) if hasattr(rq, 'updated_at') else rq.save(update_fields=['raw_responses'])

    try:
        if mode == 'rag':
            cfg = council_service.MODELS.get(primary)
            model_name = cfg['model'] if cfg else 'anthropic/claude-opus-4.7'
            res = rag_service.ask_rag(rq.question, user, top_k=top_k,
                                      model=model_name, model_id=primary)
            rq.answer = res['answer']
            rq.sources = res['sources']
            rq.models_used = [primary]
            rq.duration_s = res['duration_s']
            rq.total_cost_usd = res.get('cost_usd', 0.0)
            rq.raw_responses = {'rag': {
                'model': primary,
                'tokens': res.get('tokens', {}),
                'cost_usd': res.get('cost_usd', 0.0),
            }}

        elif mode == 'council':
            if not council_ids:
                raise ValueError('Bitte mindestens ein Council-Modell auswählen.')
            res = council_service.ask_council(
                rq.question, user, council_ids,
                progress_callback=_incremental_save,
            )
            # raw_responses wurde schon incremental gespeichert, hier nur ueberschreiben
            # damit results stabil sortiert sind.
            rq.refresh_from_db(fields=['raw_responses'])
            raw = rq.raw_responses or {}
            raw['council'] = res['results']
            rq.raw_responses = raw
            rq.models_used = council_ids
            rq.duration_s = res['duration_s']
            rq.total_cost_usd = res.get('total_cost_usd', 0.0)
            rq.answer = _format_council_summary(res['results'])

        elif mode == 'council_edited':
            # Council parallel, dann primary_model als Redakteur — strukturiert
            # die Antworten ohne eigene Inhalte zu erfinden.
            if not council_ids:
                raise ValueError('Bitte mindestens ein Council-Modell auswählen.')
            cfg = council_service.MODELS.get(primary)
            if not cfg:
                raise ValueError(f'Unbekanntes Primär-Modell: {primary}')
            cres = council_service.ask_council(
                rq.question, user, council_ids,
                progress_callback=_incremental_save,
            )
            redaktion_prompt = _redaktion_prompt(rq.question, cres['results'])
            red_res = council_service._call_one(
                primary, redaktion_prompt, user, max_tokens=8000, timeout=300)
            if red_res.get('ok'):
                rq.answer = red_res['text']
            else:
                # Falls Redakteur ausfaellt: fallback auf rohe Council-Liste mit Hinweis.
                rq.answer = (f'(Redakteur-Synthese fehlgeschlagen: {red_res.get("error")})\n\n'
                             + _format_council_summary(cres['results']))
            # graph_meta vorab generieren — damit Brain-Graph-Aufruf instant
            # rendert (Cloudflare hat 100s Origin-Timeout, GLM-Call dauert
            # 30-90s — wuerde 524 ausloesen wenn synchron in der View).
            graph_meta = {}
            try:
                from .views import _generate_graph_meta
                graph_meta = _generate_graph_meta(
                    rq.question, cres['results'], user,
                    redakteur_text=(red_res.get('text') or '') if red_res.get('ok') else '',
                )
            except Exception as exc:
                logger.warning('graph_meta-Vorabgenerierung fehlgeschlagen: %s', exc)
            rq.raw_responses = {
                'redakteur': red_res,
                'council': cres['results'],
                'graph_meta': graph_meta,
            }
            rq.models_used = [primary] + list(council_ids)
            rq.duration_s = cres['duration_s'] + (red_res.get('duration_s') or 0)
            rq.total_cost_usd = (cres.get('total_cost_usd', 0.0)
                                 + (red_res.get('cost_usd') or 0.0))

        elif mode == 'hybrid':
            cfg = council_service.MODELS.get(primary)
            if not cfg:
                raise ValueError(f'Unbekanntes Primär-Modell: {primary}')
            if not council_ids:
                council_ids = ['gpt', 'gemini', 'deepseek']
            cres = council_service.ask_council(
                rq.question, user, council_ids,
                progress_callback=_incremental_save,
            )
            try:
                sources = rag_service.retrieve(rq.question, top_k=top_k)
            except Exception:
                sources = []
            rq.sources = [s.as_dict() for s in sources]
            validation_prompt = _validation_prompt(rq.question, cres['results'], sources)
            val_res = council_service._call_one(
                primary, validation_prompt, user, max_tokens=8000, timeout=300)
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
            rq.models_used = [primary] + list(council_ids)
            rq.duration_s = cres['duration_s'] + (val_res.get('duration_s') or 0)
            rq.total_cost_usd = (cres.get('total_cost_usd', 0.0)
                                 + (val_res.get('cost_usd') or 0.0))
        else:
            raise ValueError(f'Unbekannter Modus: {mode}')

        rq.status = 'done'

    except Exception as e:
        logger.exception('research query %s failed', query_id)
        rq.error = f'{type(e).__name__}: {e}'
        rq.status = 'failed'

    rq.finished_at = timezone.now()
    rq.save()
    return rq.status
