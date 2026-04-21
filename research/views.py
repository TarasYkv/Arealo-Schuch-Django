import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
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
        form = AskForm()
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
    })


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
def history(request):
    qs = ResearchQuery.objects.filter(owner=request.user)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'research/history.html', {'page': page})


# api_keys-View entfernt: wird zentral unter /accounts/neue-api-einstellungen/ verwaltet.
