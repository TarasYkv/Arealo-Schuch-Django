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


@shared_task(bind=True, time_limit=600, soft_time_limit=540,
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

    def _validation_prompt(question, council_results, rag_sources):
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
                parts.append(f'\n--- Modell {i}: {name} ---\n{text[:4000]}')
            else:
                parts.append(f'\n--- Modell {i}: {name} — Fehler: {r.get("error")} ---')
        if rag_sources:
            parts.append('\n\n=== RAG-QUELLEN ===')
            for s in rag_sources:
                parts.append(f'\n[{s.idx}] {s.authors} ({s.year}). {s.title}\n{s.text[:1500]}')
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
            res = council_service.ask_council(rq.question, user, council_ids)
            rq.raw_responses = {'council': res['results']}
            rq.models_used = council_ids
            rq.duration_s = res['duration_s']
            rq.total_cost_usd = res.get('total_cost_usd', 0.0)
            rq.answer = _format_council_summary(res['results'])

        elif mode == 'hybrid':
            cfg = council_service.MODELS.get(primary)
            if not cfg:
                raise ValueError(f'Unbekanntes Primär-Modell: {primary}')
            if not council_ids:
                council_ids = ['gpt', 'gemini', 'deepseek']
            cres = council_service.ask_council(rq.question, user, council_ids)
            try:
                sources = rag_service.retrieve(rq.question, top_k=top_k)
            except Exception:
                sources = []
            rq.sources = [s.as_dict() for s in sources]
            validation_prompt = _validation_prompt(rq.question, cres['results'], sources)
            val_res = council_service._call_one(
                primary, validation_prompt, user, max_tokens=2500, timeout=300)
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
