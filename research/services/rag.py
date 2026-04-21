"""RAG-Service: Qdrant-Suche + Claude Opus Synthese.

Nutzt die lokale Qdrant-Instanz (127.0.0.1:6333) und den Anthropic-API-Key
aus dem User-Profil (accounts.CustomUser.anthropic_api_key) oder dem .env.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from django.conf import settings

# Lazy-Imports, damit Django startet, auch wenn eines dieser Pakete fehlt.
# Erst bei tatsächlichem Aufruf wird geladen.


QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION = "workloom_library"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model_cache = {"model": None}


def _get_embed_model():
    if _model_cache["model"] is None:
        from sentence_transformers import SentenceTransformer
        _model_cache["model"] = SentenceTransformer(EMBED_MODEL_NAME)
    return _model_cache["model"]


SYS_PROMPT_RAG = """Du bist ein wissenschaftlicher Assistent für eine Promotion zu
adaptiver RGBW-Beleuchtung in der Post-Harvest-Lagerung. Beantworte die Frage
des Doktoranden AUSSCHLIESSLICH auf Basis der gelieferten Quellen. Zitiere nach
jeder Aussage mit [Nummer] (z.B. [1] oder [2,3]). Wenn die Quellen die Frage
nicht beantworten, sage das klar. Antworte auf Deutsch, präzise und
wissenschaftlich. Mache keine Aussagen, die nicht durch die Quellen belegt sind.
"""


@dataclass
class Source:
    idx: int
    title: str
    authors: str
    year: str
    filename: str
    text: str
    score: float
    reference_id: int | None = None

    def as_dict(self) -> dict:
        return {
            'idx': self.idx,
            'title': self.title,
            'authors': self.authors,
            'year': self.year,
            'filename': self.filename,
            'text': self.text,
            'score': self.score,
            'reference_id': self.reference_id,
        }


def retrieve(question: str, top_k: int = 6) -> list[Source]:
    """Finde die top_k relevantesten Chunks in Qdrant."""
    from qdrant_client import QdrantClient

    model = _get_embed_model()
    qvec = model.encode([question], normalize_embeddings=True)[0].tolist()
    client = QdrantClient(url=QDRANT_URL, timeout=30)
    hits = client.query_points(
        collection_name=COLLECTION,
        query=qvec,
        limit=top_k,
        with_payload=True,
    ).points

    # Versuche, Qdrant-Hits mit library.Reference zu verlinken (über filename)
    ref_by_file = _lookup_references({h.payload.get('filename') for h in hits})

    sources: list[Source] = []
    for i, h in enumerate(hits, 1):
        p = h.payload
        fn = p.get('filename', '')
        sources.append(Source(
            idx=i,
            title=p.get('title', '') or '',
            authors=p.get('authors', '') or '',
            year=p.get('year', '') or '',
            filename=fn,
            text=p.get('text', '') or '',
            score=float(h.score),
            reference_id=ref_by_file.get(fn),
        ))
    return sources


def _lookup_references(filenames: set[str]) -> dict[str, int]:
    """Map: filename → library.Reference.pk (falls vorhanden)."""
    if not filenames:
        return {}
    try:
        from library.models import Reference
    except Exception:
        return {}
    # Suche Referenzen, deren note die Datei enthält (siehe import_learnloom)
    result: dict[str, int] = {}
    for fn in filenames:
        if not fn:
            continue
        ref = (Reference.objects
               .filter(notes__icontains=fn)
               .values_list('pk', 'notes')
               .first())
        if ref:
            result[fn] = ref[0]
    return result


def _get_anthropic_key(user) -> str | None:
    """NUR User-Profil, kein Env-Fallback (siehe council._get_api_key)."""
    if user and hasattr(user, 'anthropic_api_key') and user.anthropic_api_key:
        return user.anthropic_api_key.strip()
    return None


def synthesize(question: str, sources: list[Source], api_key: str,
               model: str = 'claude-opus-4-7',
               max_tokens: int = 1500) -> tuple[str, dict]:
    """Schicke Frage + Quellen an Claude, gib (Antwort, Token-Usage) zurück."""
    import anthropic

    ctx_lines = []
    for s in sources:
        cite = f"[{s.idx}] {s.authors} ({s.year}). {s.title}"
        ctx_lines.append(f"--- Quelle {s.idx} ---\n{cite}\nDatei: {s.filename}\n\n{s.text}\n")
    context = "\n".join(ctx_lines)

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        system=SYS_PROMPT_RAG,
        messages=[{
            'role': 'user',
            'content': f'FRAGE:\n{question}\n\nQUELLEN:\n{context}',
        }],
    )
    tokens = {
        'input': getattr(resp.usage, 'input_tokens', 0) or 0,
        'output': getattr(resp.usage, 'output_tokens', 0) or 0,
    }
    return resp.content[0].text, tokens


def ask_rag(question: str, user, top_k: int = 6,
            model: str = 'claude-opus-4-7',
            model_id: str = 'opus') -> dict:
    """End-to-end: Frage → Sources → Antwort. Wirft bei Fehler."""
    from .council import calculate_cost

    t0 = time.time()
    api_key = _get_anthropic_key(user)
    if not api_key:
        raise RuntimeError(
            'Kein Anthropic-API-Key hinterlegt. Trage deinen eigenen Key unter '
            '/research/keys/ ein. (Kein Fallback aus der Server-Konfiguration.)')
    sources = retrieve(question, top_k=top_k)
    if not sources:
        raise RuntimeError('Keine Treffer in der Bibliothek. Index leer?')
    answer, tokens = synthesize(question, sources, api_key, model=model)
    cost = calculate_cost(model_id, tokens)
    return {
        'answer': answer,
        'sources': [s.as_dict() for s in sources],
        'duration_s': time.time() - t0,
        'models_used': [model_id],
        'tokens': tokens,
        'cost_usd': cost,
    }
