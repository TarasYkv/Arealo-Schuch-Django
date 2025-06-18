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

        # Extrahiere relevante Begriffe aus der Query für Hervorhebung
        query_terms = [term.strip() for term in query.split() if len(term.strip()) > 2]

        for sim, chunk_index in similarities[:5]:
            if sim > threshold:  # Dynamischer Schwellenwert wird hier verwendet
                original_text = text_chunks[chunk_index]
                
                # Extrahiere relevanten Kontext mit max 9 Zeilen
                context_snippet = extract_context_around_terms(original_text, query_terms, max_lines=9)
                
                # Hervorhebung für AI-Suche basierend auf Query-Begriffen
                highlighted_snippet = highlight_terms_in_text(context_snippet, query_terms)
                
                ergebnisse.append({
                    'seitenzahl': chunk_metadata[chunk_index]['seitenzahl'],
                    'textstelle': context_snippet,
                    'textstelle_highlighted': highlighted_snippet
                })

        return ergebnisse

    except Exception as e:
        print(f"FEHLER bei der semantischen Suche: {e}")
        return []


def highlight_terms_in_text(text, search_terms):
    """Hebt Suchbegriffe im Text farblich hervor."""
    import re
    highlighted_text = text
    
    # Sortiere Suchbegriffe nach Länge (längste zuerst) um Überlappungen zu vermeiden
    sorted_terms = sorted(search_terms, key=len, reverse=True)
    
    for term in sorted_terms:
        if term and len(term.strip()) > 1:  # Nur nicht-leere Begriffe mit mehr als 1 Zeichen
            # Case-insensitive Ersetzung mit HTML-Markierung
            pattern = re.compile(re.escape(term.strip()), re.IGNORECASE)
            highlighted_text = pattern.sub(f'<mark style="background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px;">{term.strip()}</mark>', highlighted_text)
    
    return highlighted_text


def extract_context_around_terms(text, search_terms, max_lines=9):
    """Extrahiert relevanten Kontext um Suchbegriffe herum und limitiert auf max_lines."""
    import re
    
    if not search_terms:
        lines = text.split('\n')
        return '\n'.join(lines[:max_lines]) + ('...' if len(lines) > max_lines else '')
    
    # Finde alle Positionen der Suchbegriffe
    positions = []
    for term in search_terms:
        if term and len(term.strip()) > 1:
            for match in re.finditer(re.escape(term.strip()), text, re.IGNORECASE):
                positions.append(match.start())
    
    if not positions:
        lines = text.split('\n')
        return '\n'.join(lines[:max_lines]) + ('...' if len(lines) > max_lines else '')
    
    # Finde die beste Position für den Kontext (erste Fundstelle)
    best_pos = min(positions)
    
    # Extrahiere Kontext um diese Position
    context_start = max(0, best_pos - 300)
    context_end = min(len(text), best_pos + 700)
    context = text[context_start:context_end]
    
    # Auf Zeilenbasis begrenzen
    lines = context.split('\n')
    if len(lines) > max_lines:
        # Versuche die relevanteste Stelle zu finden
        relevant_lines = []
        for i, line in enumerate(lines):
            line_has_term = any(term.lower() in line.lower() for term in search_terms if term and len(term.strip()) > 1)
            if line_has_term or len(relevant_lines) < max_lines:
                relevant_lines.append(line)
            if len(relevant_lines) >= max_lines:
                break
        context = '\n'.join(relevant_lines)
        if len(lines) > max_lines:
            context += '...'
    
    # Präfix/Suffix hinzufügen wenn Text abgeschnitten wurde
    if context_start > 0:
        context = '...' + context
    if context_end < len(text):
        context = context + '...'
    
    return context


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
                
                # Extrahiere relevanten Kontext mit max 9 Zeilen für einfache Suche
                context_snippet = extract_context_around_terms(text, found_terms, max_lines=9)
                if not context_snippet.strip():
                    context_snippet = snippet
                
                # Hervorhebung der Suchbegriffe im Snippet
                highlighted_snippet = highlight_terms_in_text(context_snippet, found_terms)
                
                ergebnisse.append({
                    'seitenzahl': page_num + 1, 
                    'textstelle': context_snippet,
                    'textstelle_highlighted': highlighted_snippet
                })
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

        # Suchbegriffe für die Vorschau vorbereiten
        if search_type == 'simple':
            search_terms_for_preview = search_terms
        else:  # AI-Suche
            search_terms_for_preview = [term.strip() for term in suchanfrage.split() if len(term.strip()) > 2]
        
        context = {
            'step': 'results',
            'ergebnisse': ergebnisse,
            'pdf_filename': pdf_filename,
            'search_terms': ','.join(search_terms_for_preview),
            'search_type': search_type,
            'suchanfrage': suchanfrage,
        }
        return render(request, "pdf_sucher/suche.html", context)

    return render(request, "pdf_sucher/suche.html", {"step": "initial"})


def view_pdf(request, filename):
    pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if os.path.exists(pdf_path):
        return FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    raise Http404("PDF nicht gefunden")


def highlight_context_in_pdf_page(page, context_text, highlight_color=[1, 1, 0]):
    """Hebt den gefundenen Kontext im PDF hervor basierend auf dem extrahierten Text."""
    import re
    
    if not context_text or not context_text.strip():
        return
    
    # Bereinige den Kontext-Text von Markierungen und extrahiere relevante Phrasen
    clean_context = re.sub(r'<[^>]+>', '', context_text)  # Entferne HTML-Tags
    clean_context = clean_context.replace('...', '').strip()  # Entferne Ellipsen
    
    # Extrahiere bedeutungsvolle Phrasen (mindestens 3 Wörter zusammen)
    words = clean_context.split()
    phrases = []
    
    # Erstelle Phrasen verschiedener Längen
    for length in [5, 4, 3]:  # Längere Phrasen zuerst
        for i in range(len(words) - length + 1):
            phrase = ' '.join(words[i:i+length])
            if len(phrase.strip()) > 10:  # Mindestlänge für Phrasen
                phrases.append(phrase.strip())
    
    # Füge auch einzelne wichtige Wörter hinzu (länger als 4 Zeichen)
    for word in words:
        if len(word) > 4 and word.isalpha():
            phrases.append(word)
    
    # Entferne Duplikate und sortiere nach Länge
    phrases = sorted(list(set(phrases)), key=len, reverse=True)
    
    highlighted_count = 0
    max_highlights = 10  # Begrenze die Anzahl der Hervorhebungen
    
    for phrase in phrases:
        if highlighted_count >= max_highlights:
            break
            
        # Suche nach der Phrase im PDF
        text_instances = page.search_for(phrase)
        if text_instances:
            for inst in text_instances:
                # Orange Hervorhebung für Kontext (unterschiedlich von gelb für Suchbegriffe)
                highlight = page.add_highlight_annot(inst)
                highlight.set_colors({"stroke": [1, 0.65, 0]})  # Orange
                highlight.update()
                highlighted_count += 1
                if highlighted_count >= max_highlights:
                    break
            break  # Stoppe nach der ersten erfolgreichen Phrase


def pdf_page_preview(request, filename, page_num):
    pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if not os.path.exists(pdf_path):
        raise Http404("PDF nicht gefunden")
    
    # Suchbegriffe aus GET-Parameter extrahieren
    search_terms = request.GET.get('search_terms', '').split(',') if request.GET.get('search_terms') else []
    search_terms = [term.strip() for term in search_terms if term.strip()]
    
    # Kontext-Text für KI-Suche extrahieren
    context_text = request.GET.get('context_text', '')
    search_type = request.GET.get('search_type', 'simple')
    
    try:
        doc = fitz.open(pdf_path)
        if 0 < page_num <= len(doc):
            page = doc.load_page(page_num - 1)
            
            # Hervorhebung der Suchbegriffe auf der PDF-Seite (gelb)
            if search_terms:
                for term in search_terms:
                    if term and len(term.strip()) > 1:  # Nur nicht-leere Begriffe
                        # Finde alle Vorkommen des Begriffs auf der Seite
                        text_instances = page.search_for(term.strip())
                        for inst in text_instances:
                            # Gelbe Hervorhebung hinzufügen
                            highlight = page.add_highlight_annot(inst)
                            highlight.set_colors({"stroke": [1, 1, 0]})  # Gelb
                            highlight.update()
            
            # Zusätzliche Kontext-Hervorhebung für KI-Suche (orange)
            if search_type == 'ai' and context_text:
                highlight_context_in_pdf_page(page, context_text)
            
            pix = page.get_pixmap(dpi=150)
            img_byte_arr = io.BytesIO()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)
            doc.close()
            return HttpResponse(img_byte_arr, content_type="image/png")
        else:
            raise Http404("Seite nicht gefunden")
    except Exception as e:
        print(f"Fehler bei der Vorschauerstellung: {e}")
        raise Http404("Vorschau konnte nicht erstellt werden")