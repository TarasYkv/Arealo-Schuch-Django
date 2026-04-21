import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AskForm, ApiKeyForm, PROVIDER_KEY_FIELDS
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
            return _execute_ask(request, form)
    else:
        form = AskForm()
    return render(request, 'research/ask.html', {
        'form': form,
        'council_models': council_service.MODELS,
    })


def _execute_ask(request, form):
    mode = form.cleaned_data['mode']
    question = form.cleaned_data['question']
    primary = form.cleaned_data.get('primary_model') or 'opus'
    council_ids = form.cleaned_data.get('council_models') or []
    top_k = form.cleaned_data.get('top_k') or 6

    rq = ResearchQuery.objects.create(
        owner=request.user, question=question, mode=mode,
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
            primary_cfg = council_service.MODELS.get(primary)
            primary_model_name = primary_cfg['model'] if primary_cfg else 'claude-opus-4-7'
            rag_res = rag_service.ask_rag(question, request.user, top_k=top_k,
                                          model=primary_model_name, model_id=primary)
            rq.sources = rag_res['sources']
            hybrid_prompt = _hybrid_prompt(question, rag_res)
            if not council_ids:
                council_ids = ['gpt', 'gemini', 'deepseek']
            cres = council_service.ask_council(hybrid_prompt, request.user, council_ids)
            rq.answer = rag_res['answer']
            rq.raw_responses = {
                'rag': {'model': primary, 'tokens': rag_res.get('tokens', {}),
                        'cost_usd': rag_res.get('cost_usd', 0.0)},
                'council': cres['results'],
            }
            rq.models_used = [primary] + council_ids
            rq.duration_s = rag_res['duration_s'] + cres['duration_s']
            rq.total_cost_usd = rag_res.get('cost_usd', 0.0) + cres.get('total_cost_usd', 0.0)
        else:
            raise ValueError(f'Unbekannter Modus: {mode}')
    except Exception as e:
        logger.exception('research ask failed')
        rq.error = f'{type(e).__name__}: {e}'
        messages.error(request, f'Anfrage fehlgeschlagen: {rq.error}')
    rq.save()
    return redirect(rq.get_absolute_url())


def _hybrid_prompt(question: str, rag_res: dict) -> str:
    parts = [
        'Du sollst eine wissenschaftliche Frage beantworten. Zuerst bekommst du',
        'eine bereits erstellte Antwort auf Basis der eigenen Bibliothek.',
        'Prüfe diese Antwort kritisch, ergänze eigene Perspektiven, und weise auf',
        'wichtige Aspekte hin, die in der Bibliothek evtl. fehlen.',
        '',
        f'FRAGE:\n{question}',
        '',
        'BIBLIOTHEKS-ANTWORT:\n' + rag_res.get('answer', ''),
        '',
        'Deine Antwort (deutsch, prägnant, max. 500 Wörter):',
    ]
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
def history(request):
    qs = ResearchQuery.objects.filter(owner=request.user)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'research/history.html', {'page': page})


@login_required
def api_keys(request):
    """Verwaltung aller LLM-Provider-Keys des Users. Keys werden verschlüsselt."""
    if request.method == 'POST':
        form = ApiKeyForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'API-Keys gespeichert.')
            return redirect('research:api_keys')
    else:
        form = ApiKeyForm(instance=request.user)
    # Pro Feld: prüfe, ob gesetzt (aus User-Obj), damit Template Status anzeigen kann
    key_status = {f[0]: bool(getattr(request.user, f[0], None)) for f in PROVIDER_KEY_FIELDS}
    return render(request, 'research/api_keys.html', {
        'form': form,
        'fields_meta': PROVIDER_KEY_FIELDS,
        'key_status': key_status,
    })
