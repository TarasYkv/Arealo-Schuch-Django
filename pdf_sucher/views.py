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


def expand_search_terms_with_ai(query, perspective="sales"):
    """Erweitert Suchbegriffe mit KI um verwandte und interessante Begriffe zu finden."""
    try:
        # Definiere perspektivspezifische Prompts
        if perspective == "sales":
            role_context = """
            Du bist ein erfahrener Vertriebsmitarbeiter eines Leuchtenherstellers.
            Erweitere die Suchanfrage um Begriffe, die für den Vertrieb wichtig sind:
            - Produkteigenschaften und Verkaufsargumente
            - Preise, Konditionen und Lieferbedingungen
            - Zertifizierungen und Qualitätsstandards
            - Kundenanforderungen und Anwendungsbereiche
            - Marktpositionierung und Wettbewerbsvorteile
            
            Beispiel für "LED Beleuchtung":
            LED, Beleuchtung, Leuchte, Preis, Kosten, Energieeffizienz, Garantie, Lieferzeit, CE-Kennzeichnung, Anwendung, Einsatzbereich, Wartung
            """
        else:  # technical
            role_context = """
            Du bist ein erfahrener Entwickler/Techniker eines Leuchtenherstellers.
            Erweitere die Suchanfrage um Begriffe, die für die technische Entwicklung wichtig sind:
            - Detaillierte technische Spezifikationen
            - Normen, Standards und Vorschriften
            - Installationsdetails und Montageanforderungen
            - Elektrische Parameter und Schaltpläne
            - Materialien und technische Umsetzung
            
            Beispiel für "LED Beleuchtung":
            LED, Spannung, Strom, Leistung, Lumen, Kelvin, CRI, IP-Schutzart, IK-Schutzklasse, DIN, EN, VDE, Schaltplan, Anschluss, Kabel
            """

        expansion_prompt = f"""
        {role_context}

        Ursprüngliche Anfrage: "{query}"

        WICHTIG: Erweitere NUR um Begriffe, die thematisch eng verwandt mit der ursprünglichen Anfrage sind.
        - Verwende Synonyme und Fachbegriffe der ursprünglichen Begriffe
        - Füge KEINE allgemeinen Beleuchtungsbegriffe hinzu, wenn sie nicht zum Kontext passen
        - Konzentriere dich auf die spezifische Bedeutung der Anfrage
        - Wenn die Anfrage sehr spezifisch ist, erweitere nur minimal

        Gib eine kommaseparierte Liste von 12-15 eng verwandten Suchbegriffen zurück.

        Erweiterte Begriffe für "{query}":
        """
        
        print(f"DEBUG: Sende OpenAI-Anfrage für '{query}' mit Perspektive '{perspective}'")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": expansion_prompt}],
            max_tokens=200,
            temperature=0.3
        )
        print(f"DEBUG: OpenAI-Antwort erhalten")
        
        expanded_terms = response.choices[0].message.content.strip()
        # Bereinige und splitte die Begriffe
        terms = [term.strip() for term in expanded_terms.split(',') if term.strip()]
        
        print(f"DEBUG: Erweiterte Suchbegriffe ({perspective}): {terms}")
        return terms
        
    except Exception as e:
        print(f"FEHLER bei der Begriffserweiterung: {e}")
        # Fallback: Verwende ursprüngliche Query-Begriffe
        fallback_terms = [term.strip() for term in query.split() if len(term.strip()) > 1]
        print(f"DEBUG: Fallback zu ursprünglichen Begriffen: {fallback_terms}")
        return fallback_terms


def perform_semantic_search(pdf_path, query, page_range, strictness_threshold, perspective="sales"):
    """Führt eine KI-gestützte Suche durch, die verwandte Begriffe findet und danach sucht."""
    ergebnisse = []
    try:
        doc = fitz.open(pdf_path)
        start_page, end_page = page_range

        # 1. Erweitere Suchbegriffe mit KI basierend auf der gewählten Perspektive
        expanded_search_terms = expand_search_terms_with_ai(query, perspective)
        original_query_terms = [term.strip() for term in query.split() if len(term.strip()) > 1]
        
        # Falls KI-Erweiterung fehlschlägt, verwende nur ursprüngliche Begriffe
        if not expanded_search_terms:
            expanded_search_terms = original_query_terms.copy()
            print(f"DEBUG: KI-Erweiterung fehlgeschlagen, verwende nur ursprüngliche Begriffe: {expanded_search_terms}")
        
        print(f"DEBUG: Original-Begriffe: {original_query_terms}")
        print(f"DEBUG: Erweiterte Begriffe: {expanded_search_terms}")
        
        # 2. Durchsuche alle Seiten nach den erweiterten Begriffen
        for page_num in range(start_page, end_page):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if not text.strip():
                continue
                
            # Finde alle Begriffe auf dieser Seite
            found_terms = []
            original_found = []
            extended_found = []
            
            for term in expanded_search_terms:
                if term.lower() in text.lower():
                    found_terms.append(term)
                    # Klassifiziere: Original oder erweitert?
                    if any(orig_term.lower() == term.lower() or orig_term.lower() in term.lower() or term.lower() in orig_term.lower() 
                           for orig_term in original_query_terms):
                        original_found.append(term)
                    else:
                        extended_found.append(term)
            
            if found_terms:
                # 3. Berechne Relevanz basierend auf Strenge-Einstellung
                # Strenge = wie wichtig ursprüngliche vs. erweiterte Begriffe sind
                original_weight = strictness_threshold  # 0.1 = wenig streng, 0.8 = sehr streng
                extended_weight = 1 - strictness_threshold
                
                # Score basierend auf gefundenen Original- und erweiterten Begriffen
                original_score = len(original_found) / max(len(original_query_terms), 1) * original_weight
                extended_score = len(extended_found) / max(len(expanded_search_terms) - len(original_query_terms), 1) * extended_weight
                
                relevance_score = original_score + extended_score
                
                # Jede Seite mit gefundenen Begriffen wird angezeigt
                if True:  # Temporär: Zeige alle Fundstellen
                    print(f"DEBUG: Seite {page_num + 1}")
                    print(f"  Original gefunden: {original_found} (Score: {original_score:.3f})")
                    print(f"  Erweitert gefunden: {extended_found} (Score: {extended_score:.3f})")
                    print(f"  Gesamt-Relevanz: {relevance_score:.3f}")
                    
                    # Extrahiere relevanten Kontext
                    context_snippet = extract_context_around_terms(text, found_terms, max_lines=9)
                    highlighted_snippet = highlight_terms_in_text(context_snippet, found_terms, original_query_terms)
                    
                    ergebnisse.append({
                        'seitenzahl': page_num + 1,
                        'textstelle': context_snippet,
                        'textstelle_highlighted': highlighted_snippet,
                        'relevance_score': relevance_score,
                        'found_terms': found_terms,
                        'original_found': original_found,
                        'extended_found': extended_found
                    })
        
        doc.close()
        
        # 4. Sortiere nach Relevanz und wende Strenge-Filter an
        ergebnisse.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        print(f"DEBUG: {len(ergebnisse)} Gesamtergebnisse gefunden")
        if ergebnisse:
            print("DEBUG: Top Relevanz-Scores:", [round(r['relevance_score'], 3) for r in ergebnisse[:5]])
        
        # Wende Strenge-basierte Filterung an
        if ergebnisse:
            # Bei Strenge > 0.5: Nur Ergebnisse mit ursprünglichen Begriffen
            if strictness_threshold > 0.5:
                strict_results = [r for r in ergebnisse if r.get('original_found', [])]
                if strict_results:
                    print(f"DEBUG: Strenge Filterung: {len(strict_results)} von {len(ergebnisse)} Ergebnissen (nur mit ursprünglichen Begriffen)")
                    return strict_results
                else:
                    print(f"DEBUG: Strenge Filterung ergab keine Ergebnisse - zeige beste 3")
                    return ergebnisse[:3]
            else:
                # Bei niedriger Strenge: Alle Ergebnisse
                print(f"DEBUG: Lockere Filterung: Zeige alle {len(ergebnisse)} gefundenen Ergebnisse")
                return ergebnisse
        else:
            print("DEBUG: Keine Ergebnisse gefunden")
            return []

    except Exception as e:
        print(f"FEHLER bei der semantischen Suche: {e}")
        return []


def perform_semantic_search_with_selected_terms(pdf_path, query, page_range, strictness_threshold, perspective="sales", selected_expanded_terms=None):
    """Führt eine KI-gestützte Suche durch mit vorausgewählten erweiterten Begriffen."""
    ergebnisse = []
    try:
        doc = fitz.open(pdf_path)
        start_page, end_page = page_range

        # 1. Verwende ursprüngliche Begriffe plus ausgewählte erweiterte Begriffe
        original_query_terms = [term.strip() for term in query.split() if len(term.strip()) > 1]
        
        # Kombiniere ursprüngliche und ausgewählte erweiterte Begriffe
        if selected_expanded_terms:
            all_search_terms = original_query_terms + selected_expanded_terms
        else:
            # Fallback: Verwende automatisch generierte erweiterte Begriffe wenn keine ausgewählt wurden
            expanded_search_terms = expand_search_terms_with_ai(query, perspective)
            all_search_terms = original_query_terms + expanded_search_terms
        
        print(f"DEBUG: Original-Begriffe: {original_query_terms}")
        print(f"DEBUG: Alle Suchbegriffe: {all_search_terms}")
        
        # 2. Durchsuche alle Seiten nach den kombinierten Begriffen
        for page_num in range(start_page, end_page):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if not text.strip():
                continue
                
            # Finde alle Begriffe auf dieser Seite
            found_terms = []
            original_found = []
            extended_found = []
            
            for term in all_search_terms:
                if term.lower() in text.lower():
                    found_terms.append(term)
                    # Klassifiziere: Original oder erweitert?
                    if any(orig_term.lower() == term.lower() or orig_term.lower() in term.lower() or term.lower() in orig_term.lower() 
                           for orig_term in original_query_terms):
                        original_found.append(term)
                    else:
                        extended_found.append(term)
            
            if found_terms:
                # 3. Berechne Relevanz basierend auf Strenge-Einstellung
                original_weight = strictness_threshold
                extended_weight = 1 - strictness_threshold
                
                # Score basierend auf gefundenen Original- und erweiterten Begriffen
                original_score = len(original_found) / max(len(original_query_terms), 1) * original_weight
                extended_score = len(extended_found) / max(len(all_search_terms) - len(original_query_terms), 1) * extended_weight
                
                relevance_score = original_score + extended_score
                
                print(f"DEBUG: Seite {page_num + 1}")
                print(f"  Original gefunden: {original_found} (Score: {original_score:.3f})")
                print(f"  Erweitert gefunden: {extended_found} (Score: {extended_score:.3f})")
                print(f"  Gesamt-Relevanz: {relevance_score:.3f}")
                
                # Extrahiere relevanten Kontext
                context_snippet = extract_context_around_terms(text, found_terms, max_lines=9)
                highlighted_snippet = highlight_terms_in_text(context_snippet, found_terms, original_query_terms)
                
                ergebnisse.append({
                    'seitenzahl': page_num + 1,
                    'textstelle': context_snippet,
                    'textstelle_highlighted': highlighted_snippet,
                    'relevance_score': relevance_score,
                    'found_terms': found_terms,
                    'original_found': original_found,
                    'extended_found': extended_found
                })
        
        doc.close()
        
        # 4. Sortiere nach Relevanz und wende Strenge-Filter an
        ergebnisse.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        print(f"DEBUG: {len(ergebnisse)} Gesamtergebnisse gefunden")
        if ergebnisse:
            print("DEBUG: Top Relevanz-Scores:", [round(r['relevance_score'], 3) for r in ergebnisse[:5]])
        
        # Wende Strenge-basierte Filterung an
        if ergebnisse:
            if strictness_threshold > 0.5:
                strict_results = [r for r in ergebnisse if r.get('original_found', [])]
                if strict_results:
                    print(f"DEBUG: Strenge Filterung: {len(strict_results)} von {len(ergebnisse)} Ergebnissen")
                    return strict_results
                else:
                    print(f"DEBUG: Strenge Filterung ergab keine Ergebnisse - zeige beste 3")
                    return ergebnisse[:3]
            else:
                print(f"DEBUG: Lockere Filterung: Zeige alle {len(ergebnisse)} gefundenen Ergebnisse")
                return ergebnisse
        else:
            print("DEBUG: Keine Ergebnisse gefunden")
            return []

    except Exception as e:
        print(f"FEHLER bei der semantischen Suche mit ausgewählten Begriffen: {e}")
        return []


def highlight_terms_in_text(text, search_terms, original_query_terms=None):
    """Hebt Suchbegriffe im Text farblich hervor."""
    import re
    highlighted_text = text
    
    # Bestimme welche Begriffe ursprünglich sind und welche KI-erweitert
    if original_query_terms is None:
        original_query_terms = []
    
    # Sortiere Suchbegriffe nach Länge (längste zuerst) um Überlappungen zu vermeiden
    sorted_terms = sorted(search_terms, key=len, reverse=True)
    
    for term in sorted_terms:
        if term and len(term.strip()) > 1:  # Nur nicht-leere Begriffe mit mehr als 1 Zeichen
            # Bestimme Farbe basierend darauf, ob es ein ursprünglicher Begriff ist
            is_original = any(orig_term.lower() in term.lower() or term.lower() in orig_term.lower() 
                            for orig_term in original_query_terms)
            
            if is_original:
                # Gelb für ursprüngliche Suchbegriffe
                color_style = 'background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px;'
            else:
                # Orange für KI-erweiterte Begriffe
                color_style = 'background-color: #ff9800; color: white; padding: 2px 4px; border-radius: 3px;'
            
            # Case-insensitive Ersetzung mit HTML-Markierung
            pattern = re.compile(re.escape(term.strip()), re.IGNORECASE)
            highlighted_text = pattern.sub(f'<mark style="{color_style}">{term.strip()}</mark>', highlighted_text)
    
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
        
        print(f"DEBUG: Einfache Suche nach Begriffen: {search_terms}")
        print(f"DEBUG: Seitenbereich: {start_page+1} bis {end_page}")
        
        for page_num in range(start_page, end_page):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            
            if not text.strip():
                continue
                
            # Suche nach jedem Begriff einzeln
            found_terms = []
            for term in search_terms:
                if term.strip() and term.lower() in text.lower():
                    found_terms.append(term)
            
            if found_terms:
                print(f"DEBUG: Seite {page_num + 1}, gefundene Begriffe: {found_terms}")
                
                # Extrahiere relevanten Kontext um die gefundenen Begriffe
                context_snippet = extract_context_around_terms(text, found_terms, max_lines=9)
                
                # Falls kein spezifischer Kontext gefunden, verwende Standard-Snippet
                if not context_snippet.strip():
                    first_term = found_terms[0]
                    pos = text.lower().find(first_term.lower())
                    start = max(0, pos - 100)
                    end = min(len(text), pos + len(first_term) + 400)
                    context_snippet = text[start:end]
                    if start > 0: 
                        context_snippet = "..." + context_snippet
                    if end < len(text): 
                        context_snippet = context_snippet + "..."
                
                # Hervorhebung der gefundenen Suchbegriffe (bei einfacher Suche sind alle ursprünglich)
                highlighted_snippet = highlight_terms_in_text(context_snippet, found_terms, found_terms)
                
                ergebnisse.append({
                    'seitenzahl': page_num + 1, 
                    'textstelle': context_snippet,
                    'textstelle_highlighted': highlighted_snippet,
                    'found_terms': found_terms
                })
        
        doc.close()
        print(f"DEBUG: Einfache Suche abgeschlossen. {len(ergebnisse)} Ergebnisse gefunden.")
        
    except Exception as e:
        print(f"Fehler bei der einfachen PDF-Suche: {e}")
        
    return ergebnisse


def pdf_suche(request):
    """Hauptansicht für die PDF-Suche."""
    if request.method == "POST":
        step = request.POST.get("step", "initial")
        search_type = request.POST.get("search_type")
        search_perspective = request.POST.get("search_perspective", "sales")
        suchanfrage = request.POST.get("suchanfrage")
        pdf_file = request.FILES.get("pdf_datei")
        seite_von_str = request.POST.get("seite_von")
        seite_bis_str = request.POST.get("seite_bis")

        # Schritt 1: Initiale Suche - Zeige erweiterte Begriffe für KI-Suche
        if step == "initial" and search_type == "ai":
            if not pdf_file:
                return render(request, "pdf_sucher/suche.html",
                              {"step": "initial", "error_message": "Bitte eine PDF-Datei hochladen."})
            
            # Speichere PDF temporär
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "pdfs"))
            filename = secure_filename(pdf_file.name)
            base, extension = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{base}_{timestamp}{extension}"
            pdf_filename = fs.save(unique_filename, pdf_file)
            
            # Validiere Seitenbereich
            try:
                doc = fitz.open(fs.path(pdf_filename))
                start_page = int(seite_von_str) - 1 if seite_von_str.isdigit() else 0
                end_page = int(seite_bis_str) if seite_bis_str.isdigit() else len(doc)
                doc.close()
            except Exception as e:
                return render(request, "pdf_sucher/suche.html",
                              {"step": "initial", "error_message": f"PDF konnte nicht verarbeitet werden: {e}"})
            
            # Generiere erweiterte Suchbegriffe
            expanded_terms = expand_search_terms_with_ai(suchanfrage, search_perspective)
            
            context = {
                'step': 'preview_terms',
                'pdf_filename': pdf_filename,
                'suchanfrage': suchanfrage,
                'search_type': search_type,
                'search_perspective': search_perspective,
                'seite_von': seite_von_str,
                'seite_bis': seite_bis_str,
                'expanded_terms': expanded_terms,
                'original_terms': [term.strip() for term in suchanfrage.split() if len(term.strip()) > 1]
            }
            return render(request, "pdf_sucher/suche.html", context)
        
        # Schritt 2: Führe die eigentliche Suche durch
        if step == "search" or search_type == "simple":
            # Für einfache Suche oder wenn erweiterte Begriffe bereits ausgewählt wurden
            pdf_filename = request.POST.get("pdf_filename")
            if not pdf_filename:
                if not pdf_file:
                    return render(request, "pdf_sucher/suche.html",
                                  {"step": "initial", "error_message": "Bitte eine PDF-Datei hochladen."})
                
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "pdfs"))
                filename = secure_filename(pdf_file.name)
                base, extension = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{base}_{timestamp}{extension}"
                pdf_filename = fs.save(unique_filename, pdf_file)
            
            pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", pdf_filename)

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

                # Umrechnung des Regler-Wertes (0-100) in einen Schwellenwert (0.1 - 0.8)
                # Niedrigere Werte = weniger streng, mehr Ergebnisse
                similarity_threshold = 0.1 + (strictness_value / 100.0) * 0.7
                print(f"DEBUG: Strenge-Wert: {strictness_value}, Schwellenwert: {similarity_threshold:.3f}")

                # Sammle ausgewählte erweiterte Begriffe
                selected_expanded_terms = []
                if step == "search":
                    # Hole alle ausgewählten erweiterten Begriffe aus den Checkboxes
                    for key, value in request.POST.items():
                        if key.startswith('expanded_term_'):
                            # Der Wert der Checkbox ist der Begriff selbst
                            selected_expanded_terms.append(value)
                    
                    print(f"DEBUG: Ausgewählte erweiterte Begriffe: {selected_expanded_terms}")

                ergebnisse = perform_semantic_search_with_selected_terms(
                    pdf_path, suchanfrage, page_range, similarity_threshold, 
                    search_perspective, selected_expanded_terms
                )

        elif search_type == 'simple':
            search_terms = [term.strip() for term in suchanfrage.split(",")]
            ergebnisse = search_text_in_pdf(pdf_path, search_terms, page_range)

        # Suchbegriffe für die Vorschau vorbereiten
        if search_type == 'simple':
            search_terms_for_preview = search_terms
        else:  # AI-Suche - Verwende die erweiterten Begriffe falls verfügbar
            search_terms_for_preview = []
            if ergebnisse:
                # Sammle alle gefundenen Begriffe aus den Ergebnissen
                for ergebnis in ergebnisse:
                    if 'found_terms' in ergebnis:
                        search_terms_for_preview.extend(ergebnis['found_terms'])
                # Entferne Duplikate
                search_terms_for_preview = list(set(search_terms_for_preview))
            
            # Fallback: Verwende ursprüngliche Query-Begriffe
            if not search_terms_for_preview:
                search_terms_for_preview = [term.strip() for term in suchanfrage.split() if len(term.strip()) > 2]
        
        # Generiere PDF mit Suchergebnissen
        results_pdf_filename = None
        if ergebnisse:
            results_pdf_filename = generate_search_results_pdf(
                pdf_path, ergebnisse, suchanfrage, search_type, search_perspective
            )
        
        # Sammle alle erweiterten Begriffe für die Anzeige
        expanded_terms_for_display = []
        if search_type == 'ai' and ergebnisse:
            # Versuche die erweiterten Begriffe aus dem ersten Ergebnis zu holen
            try:
                expanded_terms_for_display = expand_search_terms_with_ai(suchanfrage, search_perspective)
            except:
                expanded_terms_for_display = []
        
        context = {
            'step': 'results',
            'ergebnisse': ergebnisse,
            'pdf_filename': pdf_filename,
            'results_pdf_filename': results_pdf_filename,
            'search_terms': ','.join(search_terms_for_preview),
            'search_type': search_type,
            'search_perspective': search_perspective,
            'suchanfrage': suchanfrage,
            'expanded_terms': expanded_terms_for_display,
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


def generate_search_results_pdf(original_pdf_path, search_results, search_query, search_type, search_perspective=None):
    """Erstellt eine PDF mit den Suchergebnissen und Links zu den Fundstellen."""
    try:
        # Erstelle temporäre Datei für die Ergebnis-PDF
        temp_filename = f"suchergebnisse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_path = os.path.join(settings.MEDIA_ROOT, "pdfs", temp_filename)
        
        # Öffne das Original-PDF
        original_doc = fitz.open(original_pdf_path)
        
        # Erstelle eine Kopie des Original-PDFs
        result_doc = fitz.open()
        result_doc.insert_pdf(original_doc)
        
        # Erstelle eine neue Seite für die Suchergebnisse
        results_page = result_doc.new_page(width=595, height=842)  # A4 Format
        
        # Text-Inhalt für die Ergebnisseite
        y_position = 800
        
        # Titel
        results_page.insert_text((50, y_position), "Suchergebnisse", fontsize=20, color=(0, 0, 0))
        y_position -= 40
        
        # Suchdetails
        results_page.insert_text((50, y_position), f"Suchanfrage: {search_query}", fontsize=12, color=(0, 0, 0))
        y_position -= 20
        
        search_type_text = "KI-gestützte Kontextsuche" if search_type == "ai" else "Einfache Textsuche"
        results_page.insert_text((50, y_position), f"Suchmethode: {search_type_text}", fontsize=12, color=(0, 0, 0))
        y_position -= 20
        
        if search_type == "ai" and search_perspective:
            perspective_text = "Vertriebsmitarbeiter" if search_perspective == "sales" else "Entwickler/Techniker"
            results_page.insert_text((50, y_position), f"Perspektive: {perspective_text}", fontsize=12, color=(0, 0, 0))
            y_position -= 20
        
        results_page.insert_text((50, y_position), f"Gefundene Ergebnisse: {len(search_results)}", fontsize=12, color=(0, 0, 0))
        y_position -= 40
        
        # Ergebnisse auflisten
        for i, result in enumerate(search_results):  # Alle Ergebnisse
            if y_position < 150:  # Neue Seite wenn zu wenig Platz
                results_page = result_doc.new_page(width=595, height=842)
                y_position = 800
            
            # Ergebnis-Header mit Link
            page_num = result['seitenzahl']
            results_page.insert_text((50, y_position), f"Ergebnis {i+1}: Seite {page_num}", fontsize=14, color=(0, 0, 1))
            
            # Erstelle Link zur entsprechenden Seite
            link_rect = fitz.Rect(50, y_position-15, 200, y_position+5)
            link = results_page.insert_link({
                "kind": fitz.LINK_GOTO,
                "page": page_num - 1,  # 0-basiert
                "to": fitz.Point(0, 0)
            }, link_rect)
            
            y_position -= 25
            
            # Textausschnitt (ohne HTML-Tags)
            import re
            result_text = result.get('textstelle', '')
            if isinstance(result_text, str):
                clean_text = re.sub(r'<[^>]+>', '', result_text)
                clean_text = clean_text[:300] + "..." if len(clean_text) > 300 else clean_text
            else:
                clean_text = "Kein Text verfügbar"
            
            # Teile langen Text in mehrere Zeilen auf
            max_chars_per_line = 80
            words = clean_text.split()
            lines = []
            current_line = ""
            
            for word in words:
                if len(current_line + " " + word) <= max_chars_per_line:
                    current_line += " " + word if current_line else word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Zeige maximal 4 Zeilen pro Ergebnis
            for line in lines[:4]:
                if y_position < 50:
                    break
                results_page.insert_text((70, y_position), line, fontsize=10, color=(0.3, 0.3, 0.3))
                y_position -= 15
            
            y_position -= 10  # Extra Abstand zwischen Ergebnissen
        
        # Speichere die neue PDF
        result_doc.save(temp_path)
        result_doc.close()
        original_doc.close()
        
        return temp_filename
        
    except Exception as e:
        print(f"FEHLER bei der PDF-Generierung: {e}")
        return None


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