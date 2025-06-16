# VOLLSTÄNDIGER CODE FÜR: pdf_sucher/views.py

import os
import io
from datetime import datetime

import fitz  # PyMuPDF
import openai
import numpy as np
from PIL import Image
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from werkzeug.utils import secure_filename

# Setzen des OpenAI API-Schlüssels
openai.api_key = settings.OPENAI_API_KEY


def cosine_similarity(v1, v2):
    """Berechnet die Kosinus-Ähnlichkeit zwischen zwei Vektoren."""
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


def perform_semantic_search(pdf_path, query, page_range, threshold):
    """Führt eine semantische Suche in der PDF mit einem dynamischen Schwellenwert durch."""
    ergebnisse = []
    try:
        doc = fitz.open(pdf_path)
        start_page, end_page = page_range

        text_chunks, chunk_metadata = [], []
        for page_num in range(start_page, end_page):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                text_chunks.append(text)
                chunk_metadata.append({'seitenzahl': page_num + 1})
        doc.close()

        if not text_chunks:
            return []

        chunk_embeddings_response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=text_chunks
        )
        chunk_embeddings = [item['embedding'] for item in chunk_embeddings_response['data']]

        query_embedding_response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=[query]
        )
        query_embedding = query_embedding_response['data'][0]['embedding']

        similarities = []
        for i, chunk_emb in enumerate(chunk_embeddings):
            sim = cosine_similarity(query_embedding, chunk_emb)
            similarities.append((sim, i))

        similarities.sort(key=lambda x: x[0], reverse=True)

        print(f"DEBUG: Suche mit Schwellenwert: {threshold:.4f}")
        print("DEBUG: Top 5 similarity scores:",
              [(round(s, 4), f"Seite {chunk_metadata[i]['seitenzahl']}") for s, i in similarities[:5]])

        for sim, chunk_index in similarities[:5]:
            if sim > threshold:  # Dynamischer Schwellenwert wird hier verwendet
                original_text = text_chunks[chunk_index]
                snippet = original_text[:1000] + ('...' if len(original_text) > 1000 else '')
                ergebnisse.append({
                    'seitenzahl': chunk_metadata[chunk_index]['seitenzahl'],
                    'textstelle': snippet,
                })

        return ergebnisse

    except Exception as e:
        print(f"FEHLER bei der semantischen Suche: {e}")
        return []


def search_text_in_pdf(pdf_path, search_terms, page_range):
    """Durchsucht eine PDF nach einer Liste von exakten Begriffen (Einfache Suche)."""
    ergebnisse = []
    try:
        doc = fitz.open(pdf_path)
        start_page, end_page = page_range
        for page_num in range(start_page, end_page):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            found_terms = [term for term in search_terms if term.lower() in text.lower()]
            if found_terms:
                first_term = found_terms[0]
                pos = text.lower().find(first_term.lower())
                start = max(0, pos - 80)
                end = min(len(text), pos + len(first_term) + 80)
                snippet = text[start:end]
                if start > 0: snippet = "..." + snippet
                if end < len(text): snippet = snippet + "..."
                ergebnisse.append({'seitenzahl': page_num + 1, 'textstelle': snippet})
        doc.close()
    except Exception as e:
        print(f"Fehler bei der einfachen PDF-Suche: {e}")
    return ergebnisse


def pdf_suche(request):
    """Hauptansicht für die PDF-Suche."""
    if request.method == "POST":
        search_type = request.POST.get("search_type")
        suchanfrage = request.POST.get("suchanfrage")
        pdf_file = request.FILES.get("pdf_datei")
        seite_von_str = request.POST.get("seite_von")
        seite_bis_str = request.POST.get("seite_bis")

        if not pdf_file:
            return render(request, "pdf_sucher/suche.html",
                          {"step": "initial", "error_message": "Bitte eine PDF-Datei hochladen."})

        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "pdfs"))
        filename = secure_filename(pdf_file.name)
        base, extension = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{base}_{timestamp}{extension}"
        pdf_filename = fs.save(unique_filename, pdf_file)
        pdf_path = fs.path(pdf_filename)

        try:
            doc = fitz.open(pdf_path)
            start_page = int(seite_von_str) - 1 if seite_von_str.isdigit() else 0
            end_page = int(seite_bis_str) if seite_bis_str.isdigit() else len(doc)
            page_range = (max(0, start_page), min(len(doc), end_page))
            doc.close()
        except Exception as e:
            return render(request, "pdf_sucher/suche.html",
                          {"step": "initial", "error_message": f"PDF konnte nicht verarbeitet werden: {e}"})

        ergebnisse = []
        if search_type == 'ai':
            strictness_value_str = request.POST.get('ai_strictness', '50')
            try:
                strictness_value = float(strictness_value_str)
            except (ValueError, TypeError):
                strictness_value = 50.0

            # Umrechnung des Regler-Wertes (0-100) in einen Schwellenwert (0.65 - 0.85)
            similarity_threshold = 0.65 + (strictness_value / 100.0) * 0.20

            ergebnisse = perform_semantic_search(pdf_path, suchanfrage, page_range, similarity_threshold)

        elif search_type == 'simple':
            search_terms = [term.strip() for term in suchanfrage.split(",")]
            ergebnisse = search_text_in_pdf(pdf_path, search_terms, page_range)

        context = {
            'step': 'results',
            'ergebnisse': ergebnisse,
            'pdf_filename': pdf_filename,
        }
        return render(request, "pdf_sucher/suche.html", context)

    return render(request, "pdf_sucher/suche.html", {"step": "initial"})


def view_pdf(request, filename):
    pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if os.path.exists(pdf_path):
        return FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    raise Http404("PDF nicht gefunden")


def pdf_page_preview(request, filename, page_num):
    pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if not os.path.exists(pdf_path):
        raise Http404("PDF nicht gefunden")
    try:
        doc = fitz.open(pdf_path)
        if 0 < page_num <= len(doc):
            page = doc.load_page(page_num - 1)
            pix = page.get_pixmap(dpi=150)
            img_byte_arr = io.BytesIO()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)
            return HttpResponse(img_byte_arr, content_type="image/png")
        else:
            raise Http404("Seite nicht gefunden")
    except Exception as e:
        print(f"Fehler bei der Vorschauerstellung: {e}")
        raise Http404("Vorschau konnte nicht erstellt werden")