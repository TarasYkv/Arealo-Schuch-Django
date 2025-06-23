# VOLLSTÄNDIGER CODE FÜR: pdf_sucher/views.py

import os
import io
import re
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

# OpenAI API wird jetzt über den neuen Client verwendet


def cosine_similarity(v1, v2):
    """Berechnet die Kosinus-Ähnlichkeit zwischen zwei Vektoren."""
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


def get_category_examples(category_name):
    """Gibt kategoriespezifische Beispiele für bessere KI-Prompts zurück."""
    examples = {
        "Feuchtraumleuchten": """
        feuchtraumleuchte, feuchtraumlampe, feuchtraumstrahler, feuchtraumarmatur, feuchtraumbeleuchtung,
        nassraumleuchte, nasszellenlicht, spritzwassergeschützt, wasserdicht, wasserfest,
        ip65, ip66, ip67, ip68, schutzart, schutzklasse,
        badleuchte, badlampe, badbeleuchtung, duschleuchte, saunaleuchte,
        kellerleuchte, garagenleuchte, außenleuchte, terrassenleuchte,
        wandleuchte feuchtraum, deckenleuchte feuchtraum, aufbauleuchte feuchtraum,
        led feuchtraum, t8 feuchtraum, wannenleuchte, feuchtraumwanne
        """,
        
        "Hallenleuchten": """
        hallenleuchte, hallenstrahler, hallenbeleuchtung, hallenlampe, industrieleuchte,
        highbay, high bay, tiefstrahler, flutlicht, hallenlicht,
        lagerbeleuchtung, fabrikbeleuchtung, produktionsbeleuchtung, werkstattbeleuchtung,
        linearleuchte, lichtband, rasterleuchte, pendelleuchte industrie,
        led hallenstrahler, hql ersatz, hqi ersatz, natriumdampflampe ersatz,
        hochregalbeleuchtung, güterhallenbeleuchtung, montagehalle, produktionshalle,
        deckenmontage, abgehängte montage, seilaufhängung, kettenaufhängung,
        arbeitsplatzbeleuchtung, maschinenbeleuchtung, bandbeleuchtung
        """,
        
        "Lichtmanagement": """
        lichtsteuerung, lichtregelung, lichtmanagement, beleuchtungssteuerung,
        bewegungsmelder, präsenzmelder, lichtsensor, helligkeitssensor, dämmerungsschalter,
        dali, dali-2, knx, eib, lcn, lichtbus, bussystem,
        dimmer, dimmen, dimmbar, stufendimmer, phasendimmer,
        tageslichtregelung, tageslichtabhängig, konstantlichtregelung,
        zeitschaltuhr, astroschaltuhr, wochenzeitschaltuhr,
        smart lighting, iot beleuchtung, vernetzte beleuchtung,
        szenensteuerung, lichtszenen, beleuchtungsszenarien,
        energiemanagement, energieeinsparung, standby, eco modus
        """,
        
        "EX-Leuchten": """
        ex-leuchte, explosionsgeschützte leuchte, explosionsschutz, ex-schutz,
        atex, iecex, ex-zone, explosionsgefahr, gasexplosion, staubexplosion,
        zone 1, zone 2, zone 21, zone 22, zone 0,
        ex d, ex e, ex i, ex m, ex n, ex p, ex t,
        druckfeste kapselung, erhöhte sicherheit, eigensicherheit,
        verguss, überdruckkapselung, sandkapselung,
        gasex, staubex, chemieanlage, raffinerie, petrochemie,
        lackiererei, siloanlage, mühle, getreidesilo,
        ex-zertifizierung, ex-kennzeichnung, ex-prüfung,
        temperaturklasse, zündgruppe, gießharz, robustes gehäuse
        """,
        
        "Straßenleuchten": """
        straßenleuchte, straßenlampe, straßenlaterne, mastleuchte, ausleuchte,
        led straßenleuchte, natriumdampflampe straße, quecksilberdampflampe straße,
        straßenbeleuchtung, außenbeleuchtung, verkehrswegebeleuchtung,
        lichtmast, beleuchtungsmast, lichtpunkt, mastaufsatz,
        parkplatzbeleuchtung, wegbeleuchtung, platzbeleuchtung,
        ansatzleuchte, aufsatzleuchte, mastansatz, mastaufsatz,
        lichtverteilung straße, lichtlenkung, asymmetrisch, symmetrisch,
        blendungsbegrenzung, lichtverschmutzung, upward light ratio,
        en 13201, straßenbeleuchtungsnorm, beleuchtungsklasse,
        fernsteuerung straße, dimmung straße, nachtabsenkung
        """,
        
        "Notleuchten": """
        notleuchte, notlicht, sicherheitsleuchte, sicherheitsbeleuchtung,
        rettungszeichenleuchte, rettungswegleuchte, fluchtwegleuchte, notausgangsleuchte,
        antipanikleuchte, sicherheitszeichenleuchte, hinweisleuchte,
        einzelbatterie, zentralbatterie, zentralbatterieanlage, gruppenbatterie,
        dauerlicht, bereitschaftslicht, kombinationslicht,
        selbsttest, funktionstestung, batteriemonitoring,
        din en 1838, din vde 0108, arbeitsstättenrichtlinie, bauordnung,
        wandmontage, deckenmontage, pendelleuchte, einbauleuchte,
        piktogramm, rettungszeichen, fluchtrichtung, sammelstelle,
        brandfall, stromausfall, evakuierung, fluchtweg,
        notbeleuchtung, ersatzbeleuchtung, reservebeleuchtung
        """
    }
    return examples.get(category_name, "")


def generate_category_keywords_with_ai(category_name):
    """Generiert verwandte Begriffe für eine Leuchtenkategorie mit OpenAI."""
    try:
        prompt = f"""
        Du bist ein Experte für Beleuchtungstechnik und Elektroinstallation. Generiere eine umfassende Liste von 25-30 verwandten Begriffen, Synonymen und Fachausdrücken für die Kategorie "{category_name}".

        WICHTIG: Finde möglichst viele verschiedene Begriffe, die in technischen Ausschreibungen verwendet werden können:
        
        Für "{category_name}" suche Begriffe in folgenden Kategorien:
        
        1. DIREKTE SYNONYME UND VARIANTEN:
        - Alternative Bezeichnungen und Schreibweisen
        - Umgangssprachliche und fachsprachliche Begriffe
        - Marken- und Produktbezeichnungen
        
        2. TECHNISCHE EIGENSCHAFTEN:
        - Schutzarten (IP-Klassen, Schutzklassen)
        - Materialien und Bauformen
        - Elektrische Parameter
        - Montagetechniken
        
        3. ANWENDUNGSBEREICHE:
        - Spezifische Einsatzorte und Räume
        - Industriezweige und Gebäudetypen
        - Besondere Anforderungen
        
        4. NORMEN UND STANDARDS:
        - DIN/EN Normen
        - Zertifizierungen
        - Prüfzeichen
        
        5. VERWANDTE KOMPONENTEN:
        - Zubehör und Ersatzteile
        - Steuerungs- und Regelungstechnik
        - Installationsmaterial
        
        Beispiele für "{category_name}":
        {get_category_examples(category_name)}
        
        Gib NUR eine kommaseparierte Liste zurück, keine Erklärungen oder zusätzlichen Text:
        """
        
        print(f"DEBUG: Generiere KI-Begriffe für Kategorie '{category_name}'")
        # Prüfe welche OpenAI Version verfügbar ist
        try:
            # Neue OpenAI Version (>= 1.0)
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
        except AttributeError:
            # Alte OpenAI Version (< 1.0)
            openai.api_key = settings.OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
        
        keywords_text = response.choices[0].message.content.strip()
        keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
        
        print(f"DEBUG: KI-generierte Begriffe für '{category_name}': {keywords}")
        return keywords
        
    except Exception as e:
        print(f"FEHLER bei KI-Begriffsgenerierung für '{category_name}': {e}")
        # Fallback: Verwende vordefinierte Begriffe
        fallback_keywords = {
            "Feuchtraumleuchten": ["feuchtraum", "ip65", "ip66", "wasserdicht", "spritzwasser", "bad", "keller", "schutzart"],
            "Hallenleuchten": ["halle", "industrie", "lager", "fabrik", "produktion", "hallenstrahler", "linearleuchte"],
            "Lichtmanagement": ["dali", "knx", "dimmer", "steuerung", "sensor", "bewegungsmelder", "automation", "smart"],
            "EX-Leuchten": ["ex", "explosion", "atex", "zone", "explosionsschutz", "gasex", "staubex"],
            "Straßenleuchten": ["straße", "außenbeleuchtung", "mast", "kandelaber", "parkplatz", "verkehr"],
            "Notleuchten": ["notlicht", "sicherheit", "fluchtweg", "rettungszeichen", "notbeleuchtung", "antipanik"]
        }
        fallback_keywords = {
            "Feuchtraumleuchten": [
                "feuchtraumleuchte", "feuchtraumlampe", "feuchtraumstrahler", "feuchtraumarmatur", 
                "nassraumleuchte", "spritzwassergeschützt", "wasserdicht", "wasserfest",
                "ip65", "ip66", "ip67", "ip68", "schutzart", "schutzklasse",
                "badleuchte", "badlampe", "duschleuchte", "kellerleuchte", "garagenleuchte",
                "wannenleuchte", "feuchtraumwanne", "aufbauleuchte", "feuchtraum"
            ],
            "Hallenleuchten": [
                "hallenleuchte", "hallenstrahler", "hallenbeleuchtung", "industrieleuchte",
                "highbay", "high bay", "tiefstrahler", "lagerbeleuchtung", "fabrikbeleuchtung",
                "linearleuchte", "lichtband", "rasterleuchte", "pendelleuchte",
                "led hallenstrahler", "hochregalbeleuchtung", "produktionshalle",
                "deckenmontage", "arbeitsplatzbeleuchtung", "halle", "industrie"
            ],
            "Lichtmanagement": [
                "lichtsteuerung", "lichtregelung", "lichtmanagement", "beleuchtungssteuerung",
                "bewegungsmelder", "präsenzmelder", "lichtsensor", "helligkeitssensor",
                "dali", "knx", "dimmer", "dimmen", "dimmbar", "tageslichtregelung",
                "zeitschaltuhr", "smart lighting", "szenensteuerung", "lichtszenen",
                "energiemanagement", "steuerung", "regelung", "automation"
            ],
            "EX-Leuchten": [
                "ex-leuchte", "explosionsgeschützte leuchte", "explosionsschutz", "ex-schutz",
                "atex", "iecex", "ex-zone", "zone 1", "zone 2", "zone 21", "zone 22",
                "gasexplosion", "staubexplosion", "druckfeste kapselung", "gasex", "staubex",
                "chemieanlage", "raffinerie", "ex-zertifizierung", "explosion", "ex"
            ],
            "Straßenleuchten": [
                "straßenleuchte", "straßenlampe", "straßenlaterne", "mastleuchte",
                "led straßenleuchte", "straßenbeleuchtung", "außenbeleuchtung",
                "lichtmast", "parkplatzbeleuchtung", "wegbeleuchtung", "ansatzleuchte",
                "lichtverteilung", "fernsteuerung", "straße", "mast", "aufsatz"
            ],
            "Notleuchten": [
                "notleuchte", "notlicht", "sicherheitsleuchte", "sicherheitsbeleuchtung",
                "rettungszeichenleuchte", "fluchtwegleuchte", "notausgangsleuchte",
                "antipanikleuchte", "einzelbatterie", "zentralbatterie", "dauerlicht",
                "bereitschaftslicht", "selbsttest", "piktogramm", "rettungszeichen",
                "notbeleuchtung", "fluchtweg", "brandfall", "stromausfall", "sicherheit"
            ]
        }
        return fallback_keywords.get(category_name, [])


def expand_user_keywords_with_ai(category_name, user_keywords):
    """Erweitert benutzerdefinierte Keywords um KI-generierte verwandte Begriffe."""
    try:
        # Kombiniere benutzer-keywords für besseren KI-Kontext
        keywords_context = ", ".join(user_keywords)
        
        prompt = f"""
        Du bist ein Experte für Beleuchtungstechnik. Erweitere die folgenden Suchbegriffe für die Kategorie "{category_name}" um verwandte Begriffe:
        
        Vorhandene Begriffe: {keywords_context}
        
        WICHTIG: 
        - Behalte alle ursprünglichen Begriffe bei
        - Füge 10-15 thematisch verwandte Begriffe hinzu
        - Verwende Synonyme, alternative Schreibweisen und Fachbegriffe
        - Orientiere dich am Stil und der Spezifität der vorhandenen Begriffe
        
        Gib eine kommaseparierte Liste zurück (ursprüngliche + neue Begriffe):
        """
        
        print(f"DEBUG: Erweitere benutzerdefinierte Keywords für '{category_name}' mit KI")
        
        # Prüfe welche OpenAI Version verfügbar ist
        try:
            # Neue OpenAI Version (>= 1.0)
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
        except AttributeError:
            # Alte OpenAI Version (< 1.0)
            openai.api_key = settings.OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
        
        expanded_keywords_text = response.choices[0].message.content.strip()
        expanded_keywords = [kw.strip().lower() for kw in expanded_keywords_text.split(',') if kw.strip()]
        
        print(f"DEBUG: KI-erweiterte Keywords für '{category_name}': {len(expanded_keywords)} Begriffe")
        return expanded_keywords
        
    except Exception as e:
        print(f"FEHLER bei KI-Erweiterung für '{category_name}': {e}")
        # Fallback: Nur ursprüngliche Keywords
        return user_keywords


def get_categories_and_keywords(user=None):
    """Gibt Kategorien und Keywords zurück - benutzerdefiniert oder Standard."""
    if user and user.is_authenticated and user.use_custom_categories:
        # Verwende benutzerdefinierte Kategorien
        from accounts.models import AmpelCategory
        custom_categories = AmpelCategory.objects.filter(user=user, is_active=True)
        categories_data = {}
        
        for category in custom_categories:
            user_keywords = [kw.keyword.lower() for kw in category.keywords.all()]
            
            # Prüfe ob KI-Erweiterung aktiviert ist
            if user.enable_ai_keyword_expansion and user_keywords:
                # Erweitere Keywords mit KI
                expanded_keywords = expand_user_keywords_with_ai(category.name, user_keywords)
                categories_data[category.name] = expanded_keywords
                print(f"DEBUG: '{category.name}' mit KI erweitert: {len(user_keywords)} -> {len(expanded_keywords)} Keywords")
            else:
                # Verwende nur benutzer-definierte Keywords
                categories_data[category.name] = user_keywords
                print(f"DEBUG: '{category.name}' nur Benutzer-Keywords: {len(user_keywords)} Keywords")
            
        print(f"DEBUG: Verwende benutzerdefinierte Kategorien für User {user.username}: {list(categories_data.keys())}")
        return categories_data
    else:
        # Verwende Standard-Kategorien mit KI-generierten Keywords
        standard_categories = ["Feuchtraumleuchten", "Hallenleuchten", "Lichtmanagement", "EX-Leuchten", "Straßenleuchten", "Notleuchten"]
        categories_data = {}
        
        for category in standard_categories:
            ai_keywords = generate_category_keywords_with_ai(category)
            categories_data[category] = ai_keywords
            
        print(f"DEBUG: Verwende Standard-Kategorien mit KI: {list(categories_data.keys())}")
        return categories_data


def analyze_entire_pdf_with_ampel(pdf_path, user=None):
    """Analysiert die gesamte PDF und gibt Ampel-Status für alle Kategorien zurück."""
    
    # Hole Kategorien und Keywords basierend auf Benutzer-Einstellungen
    categories_data = get_categories_and_keywords(user)
    
    try:
        # Extrahiere Text aus PDF mit Seitenverweise
        doc = fitz.open(pdf_path)
        page_texts = []
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            page_texts.append(page_text)
            full_text += page_text + " "
        # Dokument erst später schließen
        
        full_text_lower = full_text.lower()
        print(f"DEBUG: PDF-Text extrahiert, Länge: {len(full_text)} Zeichen")
        
        results = {}
        
        for category, keywords in categories_data.items():
            print(f"DEBUG: Analysiere Kategorie '{category}' mit {len(keywords)} Keywords")
            
            # Verwende die bereits vorhandenen Keywords (benutzerdefiniert oder KI-generiert)
            ai_keywords = keywords
            
            # Suche nach Schlüsselwörtern auf jeder Seite
            found_keywords = []
            keyword_positions = []
            page_locations = {}  # Neue Struktur für Seiten-Locations
            
            for keyword in ai_keywords:
                keyword_pages = []
                for page_num, page_text in enumerate(page_texts):
                    if keyword.lower() in page_text.lower():
                        try:
                            import re
                            # Finde alle Positionen dieses Keywords auf dieser Seite
                            # Verwende PyMuPDF für exakte Koordinaten
                            page_obj = doc.load_page(page_num)
                            text_instances = page_obj.search_for(keyword)
                            
                            if text_instances:
                                for i, rect in enumerate(text_instances):
                                    # Extrahiere Kontext um jede Fundstelle 
                                    matches = list(re.finditer(re.escape(keyword.lower()), page_text.lower()))
                                    if i < len(matches):
                                        match = matches[i]
                                        context_start = max(0, match.start() - 50)
                                        context_end = min(len(page_text), match.end() + 50)
                                        context = page_text[context_start:context_end].strip()
                                        
                                        keyword_pages.append({
                                            'page': page_num + 1,
                                            'context': f"...{context}...",
                                            'position': match.start(),
                                            'x0': float(rect.x0),
                                            'y0': float(rect.y0), 
                                            'x1': float(rect.x1),
                                            'y1': float(rect.y1)
                                        })
                                    else:
                                        # Fallback wenn regex nicht mit PyMuPDF übereinstimmt
                                        keyword_pages.append({
                                            'page': page_num + 1,
                                            'context': f"...{keyword} gefunden...",
                                            'position': 0,
                                            'x0': float(rect.x0),
                                            'y0': float(rect.y0),
                                            'x1': float(rect.x1), 
                                            'y1': float(rect.y1)
                                        })
                            else:
                                # Fallback: Nur Text-basiert, ohne Koordinaten
                                matches = list(re.finditer(re.escape(keyword.lower()), page_text.lower()))
                                for match in matches:
                                    context_start = max(0, match.start() - 50)
                                    context_end = min(len(page_text), match.end() + 50)
                                    context = page_text[context_start:context_end].strip()
                                    
                                    keyword_pages.append({
                                        'page': page_num + 1,
                                        'context': f"...{context}...",
                                        'position': match.start(),
                                        'x0': 0,
                                        'y0': 0,
                                        'x1': 0,
                                        'y1': 0
                                    })
                        except Exception as page_error:
                            print(f"DEBUG: Fehler bei Seite {page_num + 1} für Keyword '{keyword}': {page_error}")
                            # Fallback: Nur Text-basiert
                            import re
                            matches = list(re.finditer(re.escape(keyword.lower()), page_text.lower()))
                            for match in matches:
                                context_start = max(0, match.start() - 50)
                                context_end = min(len(page_text), match.end() + 50)
                                context = page_text[context_start:context_end].strip()
                                
                                keyword_pages.append({
                                    'page': page_num + 1,
                                    'context': f"...{context}...",
                                    'position': match.start(),
                                    'x0': 0,
                                    'y0': 0,
                                    'x1': 0,
                                    'y1': 0
                                })
                
                if keyword_pages:
                    found_keywords.append(keyword)
                    page_locations[keyword] = keyword_pages
                    
                    # Globale Positionen für Kompatibilität
                    for page_match in keyword_pages[:3]:  # Max 3 pro Keyword
                        keyword_positions.append((keyword, 0, 0))  # Dummy-Positionen
            
            # Extrahiere Kontext um gefundene Begriffe (für Kompatibilität)
            context_snippets = []
            for keyword in found_keywords[:3]:  # Max 3 Kontexte pro Kategorie
                if keyword in page_locations:
                    # Nimm ersten Kontext von jeder Fundstelle
                    context_snippets.append(page_locations[keyword][0]['context'])
            
            # Berechne Bewertung
            if found_keywords:
                confidence = min(1.0, len(found_keywords) / 5)  # Normalisiert auf max 5 Keywords
                status = "grün"
                print(f"DEBUG: Kategorie '{category}' -> GRÜN, {len(found_keywords)} Begriffe gefunden")
            else:
                confidence = 0.0
                status = "rot"
                print(f"DEBUG: Kategorie '{category}' -> ROT, keine Begriffe gefunden")
            
            results[category] = {
                "status": status,
                "found_keywords": found_keywords[:10],  # Limitiere Anzeige
                "confidence": confidence,
                "context_snippets": context_snippets,
                "ai_keywords_used": ai_keywords,
                "page_locations": page_locations  # Neue Struktur für Seiten-Locations
            }
        
        # Schließe das Dokument erst ganz am Ende
        doc.close()
        
        print(f"DEBUG: Ampel-Analyse abgeschlossen für {len(categories_data)} Kategorien")
        return results
        
    except Exception as e:
        print(f"FEHLER bei der PDF-Ampel-Analyse: {e}")
        # Versuche Dokument zu schließen falls noch offen
        try:
            if 'doc' in locals():
                doc.close()
        except:
            pass
        # Fallback: Alle Kategorien rot
        fallback_categories = list(categories_data.keys()) if 'categories_data' in locals() else ["Feuchtraumleuchten", "Hallenleuchten", "Lichtmanagement", "EX-Leuchten", "Straßenleuchten", "Notleuchten"]
        return {cat: {"status": "rot", "found_keywords": [], "confidence": 0.0, "context_snippets": [], "ai_keywords_used": [], "page_locations": {}} 
                for cat in fallback_categories}


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
        
        # Prüfe welche OpenAI Version verfügbar ist
        try:
            # Neue OpenAI Version (>= 1.0)
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": expansion_prompt}],
                max_tokens=200,
                temperature=0.3
            )
        except AttributeError:
            # Alte OpenAI Version (< 1.0)
            openai.api_key = settings.OPENAI_API_KEY
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
        fallback_terms = [term.strip() for term in query.split(",") if len(term.strip()) > 1]
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
        original_query_terms = [term.strip() for term in query.split(",") if len(term.strip()) > 1]
        
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
                if term.strip():
                    # Für mehrteilige Begriffe: exakte Suche nach dem ganzen Begriff
                    term_found = False
                    if ' ' in term.strip():
                        # Mehrteiliger Begriff: Suche nach exaktem Vorkommen
                        pattern = re.escape(term.strip().lower())
                        if re.search(pattern, text.lower()):
                            term_found = True
                    else:
                        # Einteiliger Begriff: Verwende Word Boundaries
                        pattern = r'\b' + re.escape(term.strip().lower()) + r'\b'
                        if re.search(pattern, text.lower()):
                            term_found = True
                    
                    if term_found:
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
                    
                    # Analysiere Thema/Produkt und Anzahl
                    analysis = analyze_product_and_quantity(context_snippet)
                    
                    ergebnisse.append({
                        'seitenzahl': page_num + 1,
                        'textstelle': context_snippet,
                        'textstelle_highlighted': highlighted_snippet,
                        'relevance_score': relevance_score,
                        'found_terms': found_terms,
                        'original_found': original_found,
                        'extended_found': extended_found,
                        'product_category': analysis['category'],
                        'quantity': analysis['quantity']
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
        original_query_terms = [term.strip() for term in query.split(",") if len(term.strip()) > 1]
        
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
                if term.strip():
                    # Für mehrteilige Begriffe: exakte Suche nach dem ganzen Begriff
                    term_found = False
                    if ' ' in term.strip():
                        # Mehrteiliger Begriff: Suche nach exaktem Vorkommen
                        pattern = re.escape(term.strip().lower())
                        if re.search(pattern, text.lower()):
                            term_found = True
                    else:
                        # Einteiliger Begriff: Verwende Word Boundaries
                        pattern = r'\b' + re.escape(term.strip().lower()) + r'\b'
                        if re.search(pattern, text.lower()):
                            term_found = True
                    
                    if term_found:
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
                
                # Analysiere Thema/Produkt und Anzahl
                analysis = analyze_product_and_quantity(context_snippet)
                
                ergebnisse.append({
                    'seitenzahl': page_num + 1,
                    'textstelle': context_snippet,
                    'textstelle_highlighted': highlighted_snippet,
                    'relevance_score': relevance_score,
                    'found_terms': found_terms,
                    'original_found': original_found,
                    'extended_found': extended_found,
                    'product_category': analysis['category'],
                    'quantity': analysis['quantity']
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


def analyze_product_and_quantity(text):
    """Analysiert Text auf Thema/Produkt und Anzahl."""
    import re
    
    # Kategorien definieren
    categories = {
        "Feuchtraumleuchten": ["feuchtraum", "ip65", "ip66", "ip67", "wasserdicht", "spritzwasser", "nassraum", "badleuchte"],
        "Hallenleuchten": ["halle", "industrial", "highbay", "high bay", "lagerhalle", "produktionshalle", "werkstatt"],
        "Straßenleuchten": ["straße", "straßen", "außenbeleuchtung", "mastleuchte", "verkehrsweg", "platz"],
        "Notleuchten": ["not", "sicherheit", "fluchtweg", "rettung", "notausgang", "antipanik"],
        "EX-Leuchten": ["ex", "explosion", "atex", "zone", "gasexplosion", "staubexplosion"],
        "Lichtmanagement": ["steuerung", "regelung", "sensor", "dali", "knx", "dimmer", "bewegungsmelder"]
    }
    
    # Thema/Kategorie erkennen
    found_category = "Sonstiges"
    for category, keywords in categories.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            found_category = category
            break
    
    # Falls keine Kategorie gefunden wurde, verwende KI für Kategorisierung
    if found_category == "Sonstiges" and text.strip():
        ai_category = extract_category_with_ai(text)
        if ai_category:
            found_category = ai_category
    
    # Anzahl extrahieren - erst mit Regex-Patterns
    quantity_patterns = [
        r'(\d+)\s*(?:stück|stk|st\.?|x|mal|einheiten?)',
        r'(\d+)\s*(?:leuchten?|lampen?|strahler?)',
        r'anzahl:?\s*(\d+)',
        r'(\d+)\s*(?:mal|x)'
    ]
    
    found_quantity = None
    for pattern in quantity_patterns:
        matches = re.findall(pattern, text.lower())
        if matches:
            found_quantity = matches[0]
            break
    
    # Falls keine Anzahl mit Regex gefunden, verwende KI
    if not found_quantity and text.strip():
        ai_quantity = extract_quantity_with_ai(text)
        if ai_quantity:
            found_quantity = ai_quantity
    
    # Letzter Fallback: Einzelne Zahlen suchen
    if not found_quantity:
        numbers = re.findall(r'\b(\d{1,3})\b', text)
        if numbers:
            # Nehme die erste sinnvolle Zahl (zwischen 1 und 999)
            for num in numbers:
                if 1 <= int(num) <= 999:
                    found_quantity = num
                    break
    
    return {
        'category': found_category,
        'quantity': found_quantity
    }


def extract_category_with_ai(text):
    """Extrahiert Produktkategorie aus Text mit KI."""
    try:
        from django.conf import settings
        import openai
        
        # OpenAI Client initialisieren
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        prompt = f"""
Analysiere den folgenden Text aus einer technischen Ausschreibung und bestimme die passende Produktkategorie in maximal 1-2 Wörtern.

Mögliche Kategorien:
- Innenleuchten
- Außenleuchten  
- Deckenleuchten
- Wandleuchten
- Strahler
- Downlights
- Pendelleuchten
- Einbauleuchten
- Scheinwerfer
- Flutlicht
- Mastleuchten
- Pollerleuchten
- Bodenleuchten
- Unterbauleuchten
- Lichtbänder
- Panels
- Spots
- Leuchtstoffröhren
- LED-Module
- Treiber
- Sensoren
- Schalter
- Kabel
- Befestigung

Text: "{text[:300]}"

Antworte nur mit der passendsten Kategorie in 1-2 Wörtern, ohne weitere Erklärung:
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.1
        )
        
        category = response.choices[0].message.content.strip()
        print(f"DEBUG: KI-Kategorie extrahiert: '{category}' für Text: '{text[:50]}...'")
        
        # Validiere die Antwort (nur 1-2 Wörter, keine Sonderzeichen)
        if category and len(category.split()) <= 2 and category.replace(' ', '').replace('-', '').isalpha():
            return category
        else:
            print(f"DEBUG: KI-Kategorie ungültig: '{category}'")
            return None
            
    except Exception as e:
        print(f"DEBUG: Fehler bei KI-Kategorisierung: {e}")
        return None


def extract_quantity_with_ai(text):
    """Extrahiert Anzahl/Menge aus Text mit KI."""
    try:
        from django.conf import settings
        import openai
        
        # OpenAI Client initialisieren
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        prompt = f"""
Analysiere den folgenden Text aus einer technischen Ausschreibung und extrahiere die benötigte Anzahl/Menge von Produkten.

Suche nach:
- Direkten Anzahlangaben (z.B. "12 Stück", "5 Leuchten", "10x")
- Indirekten Mengenangaben (z.B. "je Raum 3", "pro Bereich 8")
- Zahlen in Verbindung mit Produkten (z.B. "8 Downlights erforderlich")

Ignoriere:
- Technische Spezifikationen (Watt, Lumen, IP-Werte, Maße)
- Seitenzahlen, Artikelnummern, Preise
- Prozentangaben, Temperaturen

Text: "{text[:400]}"

Antworte nur mit der Zahl (ohne Einheit), oder "0" falls keine eindeutige Menge erkennbar ist:
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1
        )
        
        quantity = response.choices[0].message.content.strip()
        print(f"DEBUG: KI-Anzahl extrahiert: '{quantity}' für Text: '{text[:50]}...'")
        
        # Validiere die Antwort (muss eine Zahl zwischen 1 und 9999 sein)
        try:
            num = int(quantity)
            if 1 <= num <= 9999:
                return str(num)
            else:
                print(f"DEBUG: KI-Anzahl außerhalb des gültigen Bereichs: {num}")
                return None
        except ValueError:
            print(f"DEBUG: KI-Anzahl keine gültige Zahl: '{quantity}'")
            return None
            
    except Exception as e:
        print(f"DEBUG: Fehler bei KI-Anzahl-Extraktion: {e}")
        return None


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
                
            # Suche nach jedem Begriff einzeln (ganze Begriffe, auch mehrteilig)
            found_terms = []
            for term in search_terms:
                if term.strip():
                    # Für mehrteilige Begriffe: exakte Suche nach dem ganzen Begriff
                    # Erstelle Regex-Pattern für ganzen Begriff (Word Boundaries für einzelne Wörter)
                    if ' ' in term.strip():
                        # Mehrteiliger Begriff: Suche nach exaktem Vorkommen
                        pattern = re.escape(term.strip().lower())
                        if re.search(pattern, text.lower()):
                            found_terms.append(term.strip())
                    else:
                        # Einteiliger Begriff: Verwende Word Boundaries
                        pattern = r'\b' + re.escape(term.strip().lower()) + r'\b'
                        if re.search(pattern, text.lower()):
                            found_terms.append(term.strip())
            
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
                
                # Analysiere Thema/Produkt und Anzahl
                analysis = analyze_product_and_quantity(context_snippet)
                
                ergebnisse.append({
                    'seitenzahl': page_num + 1, 
                    'textstelle': context_snippet,
                    'textstelle_highlighted': highlighted_snippet,
                    'found_terms': found_terms,
                    'product_category': analysis['category'],
                    'quantity': analysis['quantity']
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
        
        # Debug-Ausgaben
        print(f"DEBUG: step={step}, pdf_file={pdf_file is not None}, search_type={search_type}")
        print(f"DEBUG: suchanfrage={suchanfrage}")
        
        # Schritt 0: Ampel-Analyse immer durchführen wenn PDF hochgeladen
        if step == "initial" and pdf_file and not search_type:
            print("DEBUG: Starte Ampel-Analyse")
            try:
                # Speichere PDF temporär für Ampel-Analyse
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "pdfs"))
                filename = secure_filename(pdf_file.name)
                base, extension = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{base}_{timestamp}{extension}"
                pdf_filename = fs.save(unique_filename, pdf_file)
                pdf_path = fs.path(pdf_filename)
                
                # Führe Ampel-Analyse für gesamte PDF durch
                ampel_results = analyze_entire_pdf_with_ampel(pdf_path, request.user)
                
                context = {
                    'step': 'ampel_and_search',
                    'pdf_filename': pdf_filename,
                    'ampel_results': ampel_results,
                    'pdf_original_name': pdf_file.name
                }
                print(f"DEBUG: Context für Template: {context}")
                return render(request, "pdf_sucher/suche.html", context)
                
            except Exception as e:
                print(f"FEHLER bei Ampel-Analyse: {e}")
                return render(request, "pdf_sucher/suche.html",
                              {"step": "initial", "error_message": f"PDF konnte nicht verarbeitet werden: {e}"})
        
        # Überprüfe ob PDF bereits hochgeladen (aus Ampel-Analyse)
        existing_pdf = request.POST.get("pdf_filename_existing") or request.POST.get("pdf_filename")
        
        # Schritt 1: Initiale Suche - Zeige erweiterte Begriffe für KI-Suche oder führe einfache Suche direkt aus
        if step == "initial" and search_type == "ai":
            if not pdf_file and not existing_pdf:
                return render(request, "pdf_sucher/suche.html",
                              {"step": "initial", "error_message": "Bitte eine PDF-Datei hochladen."})
            
            # Verwende existierende PDF oder speichere neue
            if existing_pdf:
                pdf_filename = existing_pdf
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "pdfs"))
            else:
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
                start_page = int(seite_von_str) - 1 if seite_von_str and seite_von_str.isdigit() else 0
                end_page = int(seite_bis_str) if seite_bis_str and seite_bis_str.isdigit() else len(doc)
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
                'original_terms': [term.strip() for term in suchanfrage.split(",") if len(term.strip()) > 1]
            }
            return render(request, "pdf_sucher/suche.html", context)
        
        # Schritt 1.5: Einfache Suche direkt ausführen
        if step == "initial" and search_type == "simple":
            if not pdf_file and not existing_pdf:
                return render(request, "pdf_sucher/suche.html",
                              {"step": "initial", "error_message": "Bitte eine PDF-Datei hochladen."})
            
            # Verwende existierende PDF oder speichere neue
            if existing_pdf:
                pdf_filename = existing_pdf
            else:
                # Speichere PDF temporär
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "pdfs"))
                filename = secure_filename(pdf_file.name)
                base, extension = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{base}_{timestamp}{extension}"
                pdf_filename = fs.save(unique_filename, pdf_file)
            
            # Führe einfache Suche direkt aus
            pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", pdf_filename)
            
            try:
                doc = fitz.open(pdf_path)
                start_page = int(seite_von_str) - 1 if seite_von_str and seite_von_str.isdigit() else 0
                end_page = int(seite_bis_str) if seite_bis_str and seite_bis_str.isdigit() else len(doc)
                page_range = (max(0, start_page), min(len(doc), end_page))
                doc.close()
            except Exception as e:
                return render(request, "pdf_sucher/suche.html",
                              {"step": "initial", "error_message": f"PDF konnte nicht verarbeitet werden: {e}"})

            # Führe einfache Textsuche durch
            search_terms = [term.strip() for term in suchanfrage.split(",")]
            ergebnisse = search_text_in_pdf(pdf_path, search_terms, page_range)
            
            # Generiere PDF mit Suchergebnissen
            results_pdf_filename = None
            if ergebnisse:
                results_pdf_filename = generate_search_results_pdf(
                    pdf_path, ergebnisse, suchanfrage, search_type, search_perspective
                )
            
            context = {
                'step': 'results',
                'ergebnisse': ergebnisse,
                'suchanfrage': suchanfrage,
                'search_type': search_type,
                'search_perspective': search_perspective,
                'pdf_filename': pdf_filename,
                'results_pdf_filename': results_pdf_filename,
                'search_terms_for_preview': search_terms
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
                start_page = int(seite_von_str) - 1 if seite_von_str and seite_von_str.isdigit() else 0
                end_page = int(seite_bis_str) if seite_bis_str and seite_bis_str.isdigit() else len(doc)
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
                    search_terms_for_preview = [term.strip() for term in suchanfrage.split(",") if len(term.strip()) > 2]
            
            # Generiere PDF mit Suchergebnissen
            results_pdf_filename = None
            if ergebnisse:
                print(f"DEBUG: Generiere PDF mit {len(ergebnisse)} Ergebnissen")
                results_pdf_filename = generate_search_results_pdf(
                    pdf_path, ergebnisse, suchanfrage, search_type, search_perspective
                )
                print(f"DEBUG: PDF erstellt: {results_pdf_filename}")
            else:
                print("DEBUG: Keine Ergebnisse für PDF-Generierung")
            
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
            print(f"DEBUG: Context für Template - results_pdf_filename: {results_pdf_filename}")
            print(f"DEBUG: Context für Template - ergebnisse: {len(ergebnisse) if ergebnisse else 0}")
            return render(request, "pdf_sucher/suche.html", context)

    return render(request, "pdf_sucher/suche.html", {"step": "initial"})


def view_pdf(request, filename):
    pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if os.path.exists(pdf_path):
        return FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    raise Http404("PDF nicht gefunden")


def get_ampel_locations(request):
    """AJAX-Endpunkt für Ampel-Kategorien-Details mit allen Seitenpositionen."""
    import json
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        pdf_filename = data.get('pdf_filename')
        category = data.get('category')
        
        if not pdf_filename or not category:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        # PDF-Pfad erstellen
        pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", pdf_filename)
        if not os.path.exists(pdf_path):
            return JsonResponse({'error': 'PDF not found'}, status=404)
        
        # Ampel-Analyse erneut durchführen für diese Kategorie
        ampel_results = analyze_entire_pdf_with_ampel(pdf_path, request.user)
        
        if category not in ampel_results:
            return JsonResponse({'error': 'Category not found'}, status=404)
        
        result_data = ampel_results[category]
        
        # Sammle und aggregiere Locations pro Keyword und Seite
        page_locations = result_data.get('page_locations', {})
        
        # Gruppiere nach Keyword und Seite
        grouped_locations = {}
        for keyword, locations in page_locations.items():
            if keyword not in grouped_locations:
                grouped_locations[keyword] = {}
            
            for location in locations:
                page = location['page']
                if page not in grouped_locations[keyword]:
                    grouped_locations[keyword][page] = {
                        'count': 0,
                        'contexts': [],
                        'coordinates': []
                    }
                
                grouped_locations[keyword][page]['count'] += 1
                grouped_locations[keyword][page]['contexts'].append(location['context'])
                grouped_locations[keyword][page]['coordinates'].append({
                    'x0': location.get('x0', 0),
                    'y0': location.get('y0', 0),
                    'x1': location.get('x1', 0),
                    'y1': location.get('y1', 0)
                })
        
        # Erstelle aggregierte Locations-Liste
        all_locations = []
        for keyword, pages in grouped_locations.items():
            for page, page_data in pages.items():
                # Verwende den ersten Kontext und die ersten Koordinaten
                first_context = page_data['contexts'][0] if page_data['contexts'] else f"{keyword} gefunden"
                first_coords = page_data['coordinates'][0] if page_data['coordinates'] else {'x0': 0, 'y0': 0, 'x1': 0, 'y1': 0}
                
                all_locations.append({
                    'keyword': keyword,
                    'page': page,
                    'context': first_context,
                    'count': page_data['count'],
                    'position': 0,
                    'x0': first_coords['x0'],
                    'y0': first_coords['y0'],
                    'x1': first_coords['x1'],
                    'y1': first_coords['y1']
                })
        
        # Sortiere nach Seite, dann nach Keyword
        all_locations.sort(key=lambda x: (x['page'], x['keyword']))
        
        return JsonResponse({
            'status': result_data['status'],
            'category': category,
            'found_keywords': result_data['found_keywords'],
            'ai_keywords_used': result_data['ai_keywords_used'],
            'locations': all_locations,
            'total_locations': len(all_locations)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"FEHLER in get_ampel_locations: {e}")
        return JsonResponse({'error': str(e)}, status=500)

def get_pdf_page_image(request, filename, page_num):
    """Erzeugt ein Bild der angegebenen PDF-Seite mit optionaler Hervorhebung und Zoom auf die Fundstelle."""
    import json
    from django.http import JsonResponse
    
    try:
        pdf_path = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
        if not os.path.exists(pdf_path):
            raise Http404("PDF nicht gefunden")
        
        # Hole optionale Suchbegriffe für Hervorhebung
        highlight_terms = request.GET.get('highlight', '').split(',') if request.GET.get('highlight') else []
        highlight_terms = [term.strip() for term in highlight_terms if term.strip()]
        
        # Hole optionale Koordinaten für gezielten Zoom
        focus_x0 = float(request.GET.get('x0', 0))
        focus_y0 = float(request.GET.get('y0', 0))
        focus_x1 = float(request.GET.get('x1', 0))
        focus_y1 = float(request.GET.get('y1', 0))
        
        doc = fitz.open(pdf_path)
        if page_num < 1 or page_num > len(doc):
            doc.close()
            raise Http404("Seite nicht gefunden")
        
        page = doc.load_page(page_num - 1)  # 0-basiert
        page_rect = page.rect
        
        # Finde die erste Fundstelle für Zoom-Bereich
        zoom_rect = None
        all_text_instances = []
        
        if highlight_terms:
            for term in highlight_terms:
                if term:
                    text_instances = page.search_for(term)
                    all_text_instances.extend(text_instances)
                    
                    # Hervorhebung hinzufügen
                    for inst in text_instances:
                        highlight = page.add_highlight_annot(inst)
                        highlight.set_colors({"stroke": [1, 1, 0]})  # Gelb
                        highlight.update()
        
        # Bestimme Zoom-Bereich basierend auf übergebenen Koordinaten oder gefundenen Textstellen
        if focus_x0 > 0 and focus_y0 > 0 and focus_x1 > focus_x0 and focus_y1 > focus_y0:
            # Verwende übergebene Koordinaten für präzisen Zoom
            zoom_margin = 80  # Kleinerer Rand für präziseren Zoom
            zoom_rect = fitz.Rect(
                max(0, focus_x0 - zoom_margin),
                max(0, focus_y0 - zoom_margin),
                min(page_rect.width, focus_x1 + zoom_margin),
                min(page_rect.height, focus_y1 + zoom_margin)
            )
        elif all_text_instances:
            # Fallback: Finde die erste (oberste) Fundstelle
            first_instance = min(all_text_instances, key=lambda r: r.y0)
            
            # Erweitere den Bereich um die Fundstelle für bessere Lesbarkeit
            zoom_margin = 100  # Rand in Punkten
            zoom_rect = fitz.Rect(
                max(0, first_instance.x0 - zoom_margin),
                max(0, first_instance.y0 - zoom_margin), 
                min(page_rect.width, first_instance.x1 + zoom_margin),
                min(page_rect.height, first_instance.y1 + zoom_margin)
            )
            
            # Stelle sicher, dass der Zoom-Bereich mindestens 300x200 Punkte groß ist
            min_width = 300
            min_height = 200
            
            if zoom_rect.width < min_width:
                diff = min_width - zoom_rect.width
                zoom_rect.x0 = max(0, zoom_rect.x0 - diff/2)
                zoom_rect.x1 = min(page_rect.width, zoom_rect.x1 + diff/2)
            
            if zoom_rect.height < min_height:
                diff = min_height - zoom_rect.height  
                zoom_rect.y0 = max(0, zoom_rect.y0 - diff/2)
                zoom_rect.y1 = min(page_rect.height, zoom_rect.y1 + diff/2)
        
        # Erzeuge Bild - entweder gezoomt oder ganze Seite
        if zoom_rect:
            # Begrenzter Zoom, der die ganze Seitenbreite zeigt
            # Berechne Zoom-Faktor basierend auf Seitenbreite statt Zoom-Bereich
            page_width = page_rect.width
            max_display_width = 600  # Maximale Anzeigebreite
            zoom_factor = max_display_width / page_width
            zoom_factor = max(1.2, min(zoom_factor, 2.5))  # Zwischen 1.2x und 2.5x Zoom
            
            # Zeige die ganze Seitenbreite, aber fokussiert auf den Fundbereich vertikal
            display_rect = fitz.Rect(
                0,  # Ganze Breite von links
                max(0, zoom_rect.y0 - 150),  # Etwas oberhalb der Fundstelle
                page_rect.width,  # Ganze Breite bis rechts
                min(page_rect.height, zoom_rect.y1 + 150)  # Etwas unterhalb der Fundstelle
            )
            
            mat = fitz.Matrix(zoom_factor, zoom_factor)
            pix = page.get_pixmap(matrix=mat, clip=display_rect)
        else:
            # Ganze Seite wenn keine Fundstelle
            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat)
        
        img_data = pix.tobytes("png")
        
        doc.close()
        
        # Gib Bild als HTTP-Response zurück
        response = HttpResponse(img_data, content_type="image/png")
        response['Cache-Control'] = 'max-age=3600'  # Cache für 1 Stunde
        return response
        
    except Exception as e:
        print(f"FEHLER in get_pdf_page_image: {e}")
        raise Http404("Fehler beim Erzeugen des Seitenbildes")


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


def categorize_search_results_by_terms(search_results, search_query, search_perspective="sales"):
    """Kategorisiert Suchergebnisse nach gefundenen Suchbegriffen statt nach Kategorien."""
    
    # Sammle alle einzigartigen gefundenen Suchbegriffe aus allen Ergebnissen
    all_found_terms = set()
    for result in search_results:
        found_terms = result.get('found_terms', [])
        for term in found_terms:
            all_found_terms.add(term.lower().strip())
    
    # Initialisiere Kategorien basierend auf gefundenen Begriffen
    categorized_results = {}
    for term in sorted(all_found_terms):
        categorized_results[term.title()] = []
    
    # Sonstige für Ergebnisse ohne spezifische Begriffe
    categorized_results["Sonstige"] = []
    
    # Kategorisiere jedes Ergebnis nach den darin gefundenen Begriffen
    for result in search_results:
        found_terms = [term.lower().strip() for term in result.get('found_terms', [])]
        
        # Weise das Ergebnis der ersten gefundenen Begriffskategorie zu
        assigned = False
        for term in found_terms:
            term_title = term.title()
            if term_title in categorized_results:
                categorized_results[term_title].append(result)
                assigned = True
                break  # Nur einer Kategorie zuweisen
        
        # Falls kein spezifischer Begriff gefunden, zu Sonstige
        if not assigned:
            categorized_results["Sonstige"].append(result)
    
    # Entferne leere Kategorien
    categorized_results = {k: v for k, v in categorized_results.items() if v}
    
    print(f"DEBUG: Ergebnisse nach Suchbegriffen kategorisiert:")
    for term, results in categorized_results.items():
        print(f"  {term}: {len(results)} Ergebnisse")
    
    return categorized_results


def generate_search_results_pdf(original_pdf_path, search_results, search_query, search_type, search_perspective=None):
    """Erstellt eine PDF mit den Suchergebnissen und Links zu den Fundstellen."""
    try:
        print(f"DEBUG: PDF-Generierung gestartet für {len(search_results)} Ergebnisse")
        
        # Kategorisiere Ergebnisse nach Suchbegriffen
        categorized_results = categorize_search_results_by_terms(search_results, search_query, search_perspective)
        
        # Erstelle temporäre Datei für die Ergebnis-PDF
        temp_filename = f"suchergebnisse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_path = os.path.join(settings.MEDIA_ROOT, "pdfs", temp_filename)
        
        # Öffne das Original-PDF
        original_doc = fitz.open(original_pdf_path)
        
        # Erstelle eine Kopie des Original-PDFs
        result_doc = fitz.open()
        result_doc.insert_pdf(original_doc)
        
        # Erstelle eine neue Seite für die Suchergebnisse am ENDE der PDF (keine Verschiebung!)
        results_page = result_doc.new_page(width=595, height=842)  # A4 Format am Ende
        print(f"DEBUG: Suchergebnisse-Seite am Ende eingefügt. Original-PDF hatte {len(original_doc)} Seiten, neue PDF hat {len(result_doc)} Seiten")
        
        # Text-Inhalt für die Ergebnisseite (Koordinaten von oben nach unten)
        y_position = 50  # Start von oben (50pt Abstand vom oberen Rand)
        
        # Titel
        results_page.insert_text((50, y_position), "Suchergebnisse", fontsize=20, color=(0, 0, 0))
        y_position += 40
        
        # Suchdetails
        results_page.insert_text((50, y_position), f"Suchanfrage: {search_query}", fontsize=12, color=(0, 0, 0))
        y_position += 20
        
        search_type_text = "KI-gestützte Kontextsuche" if search_type == "ai" else "Einfache Textsuche"
        results_page.insert_text((50, y_position), f"Suchmethode: {search_type_text}", fontsize=12, color=(0, 0, 0))
        y_position += 20
        
        if search_type == "ai" and search_perspective:
            perspective_text = "Vertriebsmitarbeiter" if search_perspective == "sales" else "Entwickler/Techniker"
            results_page.insert_text((50, y_position), f"Perspektive: {perspective_text}", fontsize=12, color=(0, 0, 0))
            y_position += 20
        
        results_page.insert_text((50, y_position), f"Gefundene Ergebnisse: {len(search_results)}", fontsize=12, color=(0, 0, 0))
        y_position += 20
        
        # Hinweis für Navigation
        results_page.insert_text((50, y_position), "Navigation: Nutzen Sie die Seitenzahlen in der Übersicht unten für manuelle Navigation", fontsize=10, color=(0.5, 0.5, 0.5))
        y_position += 30
        
        # Erstelle Übersicht nach Suchbegriffen
        results_page.insert_text((50, y_position), "Übersicht nach Suchbegriffen:", fontsize=14, color=(0, 0, 0))
        y_position += 25
        
        # Liste alle Suchbegriffe und deren Ergebnisse auf
        for search_term, results in categorized_results.items():
            if results:  # Nur Begriffe mit Ergebnissen
                results_page.insert_text((70, y_position), f"🔍 {search_term} ({len(results)} Ergebnisse)", fontsize=12, color=(0, 0, 0.8))
                y_position += 20
                
                # Liste ersten 5 Ergebnisse für diesen Suchbegriff
                for i, result in enumerate(results[:5]):
                    page_ref = result['seitenzahl']
                    results_page.insert_text((90, y_position), f"• Seite {page_ref}", fontsize=10, color=(0.3, 0.3, 0.3))
                    y_position += 15
                
                if len(results) > 5:
                    results_page.insert_text((90, y_position), f"... und {len(results)-5} weitere", fontsize=10, color=(0.5, 0.5, 0.5))
                    y_position += 15
                
                y_position += 10  # Extra Abstand zwischen Suchbegriffen
            
        y_position += 10
        
        # Ergebnisse nach Suchbegriffen auflisten
        print(f"DEBUG: Beginne mit der Erstellung von Ergebnissen nach Suchbegriffen")
        
        ergebnis_counter = 0
        for search_term, term_results in categorized_results.items():
            if not term_results:
                continue
                
            print(f"DEBUG: Erstelle Suchbegriff '{search_term}' mit {len(term_results)} Ergebnissen")
            
            # Prüfe ob genug Platz für Suchbegriff-Header
            if y_position > 720:
                results_page = result_doc.new_page(width=595, height=842)
                y_position = 50
                print(f"DEBUG: Neue Seite für Suchbegriff '{search_term}' erstellt")
            
            # Suchbegriff-Header
            results_page.insert_text((50, y_position), f"🔍 {search_term}", fontsize=16, color=(0, 0, 0.8))
            y_position += 30
            
            # Erstelle Suchbegriff-Lesezeichen
            try:
                term_bookmark = [1, f"{search_term} ({len(term_results)} Ergebnisse)", len(result_doc)]
                if not hasattr(result_doc, '_bookmarks'):
                    result_doc._bookmarks = []
                result_doc._bookmarks.append(term_bookmark)
                print(f"DEBUG: Suchbegriff-Lesezeichen für '{search_term}' erstellt")
            except Exception as bookmark_error:
                print(f"DEBUG: Suchbegriff-Lesezeichen fehlgeschlagen: {bookmark_error}")
            
            # Ergebnisse für diesen Suchbegriff
            for result in term_results:
                ergebnis_counter += 1
                print(f"DEBUG: Verarbeite Ergebnis {ergebnis_counter} für Suchbegriff '{search_term}', y_position: {y_position}")
                
                # Prüfe ob genug Platz für Ergebnis
                if y_position > 700:
                    results_page = result_doc.new_page(width=595, height=842)
                    y_position = 50
                    print(f"DEBUG: Neue Seite innerhalb Suchbegriff '{search_term}' erstellt")
                
                # Ergebnis-Header
                page_num = result['seitenzahl']
                results_page.insert_text((70, y_position), f"📄 Ergebnis {ergebnis_counter}: Seite {page_num}", fontsize=14, color=(0, 0, 1))
                
                # Lesezeichen für einzelnes Ergebnis
                try:
                    corrected_page = page_num
                    result_bookmark = [2, f"  → Seite {page_num}", corrected_page]
                    result_doc._bookmarks.append(result_bookmark)
                    print(f"DEBUG: Ergebnis-Lesezeichen für Seite {page_num} erstellt")
                except Exception as bookmark_error:
                    print(f"DEBUG: Ergebnis-Lesezeichen fehlgeschlagen: {bookmark_error}")
                
                # Visueller Hinweis
                header_rect = fitz.Rect(70, y_position-2, 300, y_position+16)
                results_page.draw_rect(header_rect, color=(0, 0, 1), width=1)
                results_page.insert_text((305, y_position), f"→ Seite {page_num}", fontsize=10, color=(0, 0, 1))
                
                y_position += 25
                
                # Textausschnitt
                import re
                result_text = result.get('textstelle', '')
                if isinstance(result_text, str):
                    clean_text = re.sub(r'<[^>]+>', '', result_text)
                    clean_text = clean_text[:350] + "..." if len(clean_text) > 350 else clean_text
                else:
                    clean_text = "Kein Text verfügbar"
                
                # Text in Zeilen aufteilen
                max_chars_per_line = 70
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
                
                # Text anzeigen
                for line in lines[:4]:  # Max 4 Zeilen pro Ergebnis
                    if y_position > 790:
                        break
                    results_page.insert_text((90, y_position), line, fontsize=10, color=(0.3, 0.3, 0.3))
                    y_position += 15
                
                # Ampel-Kategorien anzeigen
                ampel_data = result.get('ampel_categories', {})
                if ampel_data:
                    y_position += 10
                    results_page.insert_text((90, y_position), "🚦 Kategorien-Analyse:", fontsize=10, color=(0, 0, 0.5))
                    y_position += 15
                    
                    # Zeige grüne Kategorien
                    green_categories = [cat for cat, data in ampel_data.items() if data.get('status') == 'grün']
                    if green_categories:
                        green_text = f"🟢 {', '.join(green_categories[:3])}"
                        if len(green_categories) > 3:
                            green_text += f" (+{len(green_categories)-3} weitere)"
                        results_page.insert_text((90, y_position), green_text[:80], fontsize=9, color=(0, 0.6, 0))
                        y_position += 12
                    
                    # Zeige Anzahl roter Kategorien
                    red_count = len([cat for cat, data in ampel_data.items() if data.get('status') == 'rot'])
                    if red_count > 0:
                        red_text = f"🔴 {red_count} weitere Kategorien nicht erkannt"
                        results_page.insert_text((90, y_position), red_text, fontsize=9, color=(0.6, 0, 0))
                        y_position += 12
                
                y_position += 20  # Abstand zwischen Ergebnissen
            
            y_position += 20  # Extra Abstand zwischen Kategorien
        
        print(f"DEBUG: Alle {ergebnis_counter} Ergebnisse in {len(categorized_results)} Kategorien verarbeitet")
        
        # Füge thematische Lesezeichen zur PDF hinzu
        try:
            if hasattr(result_doc, '_bookmarks') and result_doc._bookmarks:
                result_doc.set_toc(result_doc._bookmarks)
                print(f"DEBUG: {len(result_doc._bookmarks)} thematische Lesezeichen zur PDF hinzugefügt")
                
                # Debug: Zeige Struktur der Lesezeichen
                category_count = len([b for b in result_doc._bookmarks if b[0] == 1])
                result_count = len([b for b in result_doc._bookmarks if b[0] == 2])
                print(f"DEBUG: Lesezeichen-Struktur: {category_count} Kategorien, {result_count} Ergebnisse")
                
        except Exception as toc_error:
            print(f"DEBUG: Lesezeichen konnten nicht hinzugefügt werden: {toc_error}")
        
        # Ermittle Seitenanzahl vor dem Schließen
        total_pages = len(result_doc)
        
        # Speichere die neue PDF mit optimierten Einstellungen
        try:
            result_doc.save(temp_path, 
                           garbage=4,     # Optimiert die PDF
                           clean=True,    # Bereinigt die PDF
                           deflate=True   # Komprimiert die PDF
                           )
            print(f"DEBUG: PDF erfolgreich gespeichert")
        except Exception as save_error:
            print(f"DEBUG: FEHLER beim Speichern: {save_error}")
            # Versuche einfaches Speichern
            try:
                result_doc.save(temp_path)
                print(f"DEBUG: PDF mit einfachen Einstellungen gespeichert")
            except Exception as simple_save_error:
                print(f"DEBUG: Auch einfaches Speichern fehlgeschlagen: {simple_save_error}")
                result_doc.close()
                original_doc.close()
                return None
        
        # Schließe Dokumente
        result_doc.close()
        original_doc.close()
        
        print(f"DEBUG: PDF erfolgreich erstellt: {temp_filename}")
        
        # Überprüfe ob die PDF-Datei tatsächlich erstellt wurde
        if os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            print(f"DEBUG: PDF-Datei existiert, Größe: {file_size} Bytes, Seiten: {total_pages}")
            print(f"DEBUG: PDF enthält {len(search_results)} Suchergebnisse auf {total_pages} Seiten")
            return temp_filename
        else:
            print(f"DEBUG: WARNUNG - PDF-Datei wurde nicht erstellt!")
            return None
        
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