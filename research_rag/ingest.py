#!/usr/bin/env python3
"""Ingest-Pipeline: PDF → PyMuPDF → Chunks → Embeddings → Qdrant.

(GROBID-Variante liegt in ingest_grobid.py, ist aber für Batch zu langsam.)

Nutzung:
    python ingest.py                # alle PDFs aus ./pdfs/
    python ingest.py path/to/x.pdf  # nur eine Datei
    python ingest.py --reset        # Qdrant-Collection neu anlegen (Achtung: löscht vorhandene!)

Designentscheidungen:
- Embedding-Modell: BAAI/bge-small-en-v1.5 (384-dim, schnell, gut für Englisch).
- PyMuPDF extrahiert pro Seite, dann Chunks von ca. 450 Wörtern mit 50 Wort Overlap.
- Qdrant-Collection: "workloom_library".
- Filename-basiert als sekundäre Metadaten (besser als keine).
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

import fitz  # pymupdf
import time
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "pdfs"

QDRANT_URL = "http://localhost:6333"
COLLECTION = "workloom_library"
# all-MiniLM-L6-v2 ist ca. 3x schneller als bge-small auf CPU,
# kaum Qualitätsverlust für wiss. Englisch.
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DIM = 384
CHUNK_WORDS = 450
CHUNK_OVERLAP = 50


def extract_text_and_meta(pdf_path: Path) -> tuple[str, dict]:
    """Text via PyMuPDF + simple Heuristik für Titel/Autoren aus Metadaten + erste Seite."""
    doc = fitz.open(pdf_path)
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()

    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    full_text = "\n".join(pages)

    # Fallback: Titel aus erster Zeile der ersten Seite, wenn Metadaten leer
    if not title and pages:
        first = pages[0].strip().split("\n")
        for line in first[:5]:
            if len(line) > 20 and not line.isupper():
                title = line[:200]
                break

    # Jahr aus Dateinamen oder Text
    year = ""
    m = re.search(r"\b(19|20)\d{2}\b", pdf_path.name)
    if m:
        year = m.group(0)
    elif pages:
        m = re.search(r"\b(19|20)\d{2}\b", pages[0][:2000])
        if m:
            year = m.group(0)

    return full_text, {
        "title": title[:300],
        "authors": author[:400],
        "year": year,
    }


def chunk_text(text: str, chunk_words: int = CHUNK_WORDS,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Teile in Wort-Chunks mit Overlap."""
    words = re.findall(r"\S+", text)
    if not words:
        return []
    chunks = []
    step = max(1, chunk_words - overlap)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_words])
        if len(chunk) > 100:
            chunks.append(chunk)
        if i + chunk_words >= len(words):
            break
    return chunks


def stable_id(text: str) -> int:
    h = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big") & 0x7FFFFFFFFFFFFFFF


def ensure_collection(client: QdrantClient, reset: bool = False):
    exists = client.collection_exists(COLLECTION)
    if exists and reset:
        client.delete_collection(COLLECTION)
        exists = False
    if not exists:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"  Collection '{COLLECTION}' angelegt.")


def already_indexed(client: QdrantClient, filename: str) -> bool:
    """Prüfe, ob für diese Datei schon Punkte existieren."""
    res = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(must=[FieldCondition(
            key="filename", match=MatchValue(value=filename))]),
        limit=1, with_payload=False, with_vectors=False,
    )
    return bool(res[0])


def ingest_pdf(pdf_path: Path, model, client, batch_size: int = 128,
               skip_existing: bool = True) -> int:
    if skip_existing and already_indexed(client, pdf_path.name):
        print("  (bereits indexiert — skip)", flush=True)
        return 0

    t0 = time.time()
    try:
        text, meta = extract_text_and_meta(pdf_path)
    except Exception as e:
        print(f"  ✗ Fehler beim Parsen: {e}", flush=True)
        return 0
    t_extract = time.time() - t0

    chunks = chunk_text(text)
    if not chunks:
        print("  ✗ (keine Chunks)", flush=True)
        return 0

    t1 = time.time()
    embeddings = model.encode(chunks, batch_size=batch_size,
                              normalize_embeddings=True,
                              show_progress_bar=False).tolist()
    t_embed = time.time() - t1

    points = []
    for idx, (chunk, vec) in enumerate(zip(chunks, embeddings)):
        pid = stable_id(pdf_path.name + f"|{idx}")
        points.append(PointStruct(
            id=pid,
            vector=vec,
            payload={
                "filename": pdf_path.name,
                "title": meta["title"] or pdf_path.stem[:80],
                "authors": meta["authors"],
                "year": meta["year"],
                "chunk_idx": idx,
                "text": chunk,
            },
        ))

    t2 = time.time()
    client.upsert(collection_name=COLLECTION, points=points)
    t_upsert = time.time() - t2

    title_display = (meta["title"] or pdf_path.stem)[:55]
    print(f"  ✓ {len(points):3d} Chunks  "
          f"(extract={t_extract:.1f}s embed={t_embed:.1f}s upsert={t_upsert:.1f}s)  "
          f"|  {title_display}", flush=True)
    return len(points)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?", help="Einzelnes PDF (sonst: alle aus pdfs/)")
    ap.add_argument("--reset", action="store_true", help="Collection vorher löschen")
    args = ap.parse_args()

    print(f"Lade Embedding-Modell: {EMBED_MODEL_NAME} ...", flush=True)
    model = SentenceTransformer(EMBED_MODEL_NAME)
    print("  OK.", flush=True)

    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, reset=args.reset)

    if args.pdf:
        pdfs = [Path(args.pdf)]
    else:
        pdfs = sorted(PDF_DIR.glob("*.pdf"))

    print(f"\n{len(pdfs)} PDF(s) zu verarbeiten.\n", flush=True)
    total = 0
    t_start = time.time()
    for i, p in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] {p.name}", flush=True)
        total += ingest_pdf(p, model, client, skip_existing=not args.reset)

    dt = time.time() - t_start
    info = client.get_collection(COLLECTION)
    print(f"\nFertig in {dt:.1f}s. {total} Chunks in dieser Runde. "
          f"Collection insg: {info.points_count}", flush=True)


if __name__ == "__main__":
    main()
