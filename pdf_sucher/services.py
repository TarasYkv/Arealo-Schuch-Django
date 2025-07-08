"""
Services für PDF-Verarbeitung und KI-Analyse
"""
import fitz  # PyMuPDF
import json
import requests
import time
import os
import tempfile
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from .models import PDFDocument, PDFSummary, TenderPosition


class PDFTextExtractor:
    """Service zum Extrahieren von Text aus PDF-Dateien"""
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extrahiert den kompletten Text aus einer PDF-Datei"""
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                full_text += f"\n--- Seite {page_num + 1} ---\n{text}\n"
            
            doc.close()
            return full_text.strip()
        
        except Exception as e:
            raise Exception(f"Fehler beim Extrahieren des Textes: {str(e)}")


class TenderAnalysisService:
    """Service für die KI-basierte Analyse von Ausschreibungen"""
    
    def __init__(self, user):
        self.user = user
    
    def _get_requests_session_with_retry(self) -> requests.Session:
        """Erstellt eine Session mit automatischen Wiederholungen bei Netzwerkfehlern"""
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504),
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def _get_claude_model_name(self, model: str) -> str:
        """Gibt den API-Modellnamen für Claude zurück"""
        claude_models = {
            'anthropic_claude_opus': 'claude-3-opus-20240229',
            'anthropic_claude_sonnet': 'claude-3-5-sonnet-20241022',
            'anthropic_claude_haiku': 'claude-3-haiku-20240307'
        }
        return claude_models.get(model, 'claude-3-haiku-20240307')
    
    def _repair_truncated_json(self, content: str) -> str:
        """Versucht abgeschnittenes JSON zu reparieren"""
        try:
            print(f"DEBUG: Attempting to repair truncated JSON, length: {len(content)}")
            
            # Verschiedene JSON-Formate handhaben
            json_content = content
            is_markdown = False
            
            # Extrahiere JSON aus Markdown falls vorhanden
            import re
            json_start = content.find('```json')
            if json_start >= 0:
                json_content = content[json_start + 7:]  # Skip ```json
                is_markdown = True
                # Entferne trailing ``` falls vorhanden
                if json_content.endswith('```'):
                    json_content = json_content[:-3]
            elif content.strip().startswith('{'):
                # Direktes JSON ohne Markdown
                json_content = content.strip()
            
            # Finde den letzten vollständigen Eintrag
            lines = json_content.split('\n')
            repaired_lines = []
            brace_count = 0
            bracket_count = 0
            in_positions = False
            last_complete_position = -1
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Ignoriere leere Zeilen
                if not stripped:
                    repaired_lines.append(line)
                    continue
                
                # Zähle Klammern für Balance-Prüfung
                brace_count += line.count('{') - line.count('}')
                bracket_count += line.count('[') - line.count(']')
                
                # Prüfe ob wir im positions Array sind
                if '"positions":' in line:
                    in_positions = True
                
                # Prüfe ob eine Position vollständig abgeschlossen ist
                if in_positions and (stripped.endswith('},') or stripped.endswith('}')):
                    # Eine Position ist komplett, wenn die Klammern ausgeglichen sind
                    # (oder wir sind in einem guten Zustand)
                    if brace_count >= 1:  # Mindestens das Haupt-JSON-Objekt ist offen
                        last_complete_position = i
                        repaired_lines.append(line)
                    else:
                        break
                else:
                    repaired_lines.append(line)
                
                # Sicherheitscheck: Stoppe bei zu vielen schließenden Klammern
                if brace_count < 0 or bracket_count < 0:
                    break
            
            # Repariere das JSON wenn eine vollständige Position gefunden wurde
            if last_complete_position > 0:
                # Entferne das Komma der letzten Position falls vorhanden
                if repaired_lines[-1].strip().endswith(','):
                    repaired_lines[-1] = repaired_lines[-1].rstrip().rstrip(',')
                
                # Schließe das positions Array
                if in_positions and bracket_count > 0:
                    repaired_lines.append('  ]')
                
                # Schließe das Haupt-JSON-Objekt
                if brace_count > 0:
                    repaired_lines.append('}')
                
                # Erstelle die reparierte Antwort
                if is_markdown:
                    repaired_content = '```json\n' + '\n'.join(repaired_lines) + '\n```'
                else:
                    repaired_content = '\n'.join(repaired_lines)
                
                print(f"DEBUG: Successfully repaired JSON, new length: {len(repaired_content)}")
                print(f"DEBUG: Repaired JSON end: ...{repaired_content[-300:]}")
                return repaired_content
            
            print("DEBUG: Could not find repairable JSON structure")
            return content
            
        except Exception as e:
            print(f"DEBUG: Error repairing JSON: {e}")
            return content
    
    def _split_text_into_chunks(self, text: str, ai_model: str) -> List[str]:
        """Teilt Text in überlappende Chunks auf"""
        # Sehr konservative Chunk-Größen (50% der theoretischen Limits)
        chunk_sizes = {
            'openai_gpt4': 8000,         # Sehr klein wegen 8k Limit
            'openai_gpt35_turbo': 15000, # Sicher unter 16k
            'openai_gpt4o': 120000,      # 50% von 240k Limit
            'openai_gpt4o_mini': 120000,
            'openai_gpt4_turbo': 120000,
            'google_gemini_pro': 1200000,  # 50% von 2.5M
            'google_gemini_flash': 1200000,
            'anthropic_claude_opus': 240000,   # 50% von 480k
            'anthropic_claude_sonnet': 240000,
            'anthropic_claude_haiku': 240000
        }
        
        chunk_size = chunk_sizes.get(ai_model, 15000)
        overlap = chunk_size // 10  # 10% Überlappung
        
        print(f"DEBUG: Using chunk size {chunk_size} for model {ai_model}")
        print(f"DEBUG: Estimated tokens per chunk: {self._estimate_tokens(chunk_size)}")
        
        chunks = []
        start = 0
        max_chunks = 100  # Maximale Anzahl Chunks zur Sicherheit
        chunk_count = 0
        
        # Sicherheitscheck: Overlap darf nicht größer als chunk_size sein
        if overlap >= chunk_size:
            overlap = chunk_size // 10  # Fallback: 10% Überlappung
            print(f"DEBUG: Overlap zu groß, reduziert auf {overlap}")
        
        while start < len(text) and chunk_count < max_chunks:
            end = min(start + chunk_size, len(text))
            
            # Versuche an Paragraph- oder Satzgrenzen zu schneiden
            if end < len(text):
                # Suche rückwärts nach guter Trennstelle
                for i in range(end, max(start + chunk_size // 2, end - 1000), -1):
                    if text[i:i+2] in ['\n\n', '.\n', '. ']:
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                chunk_count += 1
            
            # Nächster Chunk mit Überlappung
            start = end - overlap
            
            # Sicherheitscheck: Stelle sicher, dass start fortschreitet
            if start <= end - overlap:
                print(f"DEBUG: Start nicht fortgeschritten, beende Chunking bei Position {start}")
                break
                
            if start >= len(text):
                break
        
        # Warnung wenn Chunk-Limit erreicht wurde
        if chunk_count >= max_chunks:
            print(f"Warnung: Maximale Chunk-Anzahl ({max_chunks}) erreicht. Text möglicherweise nicht vollständig verarbeitet.")
        
        print(f"DEBUG: Created {len(chunks)} chunks with average size {sum(len(c) for c in chunks) // len(chunks) if chunks else 0}")
        return chunks
    
    def _estimate_tokens(self, text_length: int) -> int:
        """Schätzt die Anzahl Tokens für eine gegebene Textlänge"""
        # Konservative Schätzung: 1 Token = 2.5 Zeichen (schlechter Fall für deutsche Texte)
        return int(text_length / 2.5)
    
    def _deduplicate_positions(self, positions: List[Dict]) -> List[Dict]:
        """Entfernt doppelte Positionen basierend auf Positionsnummer"""
        seen_positions = set()
        unique_positions = []
        
        for pos in positions:
            pos_key = pos.get('position_number', '')
            if pos_key and pos_key not in seen_positions:
                seen_positions.add(pos_key)
                unique_positions.append(pos)
            elif not pos_key:  # Positionen ohne Nummer behalten
                unique_positions.append(pos)
        
        # Sortiere nach Positionsnummer
        def sort_key(pos):
            pos_num = pos.get('position_number', 'zzz')
            # Versuche numerisch zu sortieren
            try:
                parts = pos_num.replace('.', ' ').split()
                return [int(p) if p.isdigit() else 999 for p in parts]
            except:
                return [999]
        
        unique_positions.sort(key=sort_key)
        return unique_positions
    
    def analyze_tender_document(self, text: str, ai_model: str) -> Dict:
        """Analysiert ein Ausschreibungsdokument mit dem gewählten KI-Modell"""
        try:
            # Prüfe ob das Dokument zu groß ist und Chunking benötigt
            if self._needs_chunking(text, ai_model):
                print(f"DEBUG: Document too large, using chunking strategy")
                return self._analyze_with_chunking(text, ai_model)
            else:
                print(f"DEBUG: Document size OK, using single-pass analysis")
                return self._analyze_single_pass(text, ai_model)
        
        except Exception as e:
            raise Exception(f"Fehler bei der KI-Analyse: {str(e)}")
    
    def _needs_chunking(self, text: str, ai_model: str) -> bool:
        """Prüft ob das Dokument Chunking benötigt"""
        # Sehr konservative Schätzung: 1 Token = 3 Zeichen (schlechter Fall)
        # Große Reserve für Prompt (ca. 1000 Token) und Antwort (8000 Token)
        limits = {
            'openai_gpt4o': 240000,      # 128k - 9k reserve = 119k * 2 chars (sehr sicher)
            'openai_gpt4o_mini': 240000, # Gleiche Limits
            'openai_gpt4_turbo': 240000, # Gleiche Limits  
            'openai_gpt4': 12000,        # 8k - 4k reserve = 4k * 3 chars
            'openai_gpt35_turbo': 24000, # 16k - 8k reserve = 8k * 3 chars
            'google_gemini_pro': 2500000,   # 1M - 50k reserve = 950k * 2.6 chars
            'google_gemini_flash': 2500000,
            'anthropic_claude_opus': 480000,    # 200k - 40k reserve = 160k * 3 chars
            'anthropic_claude_sonnet': 480000,
            'anthropic_claude_haiku': 480000
        }
        
        limit = limits.get(ai_model, 24000)
        needs_chunk = len(text) > limit
        print(f"DEBUG: Text length: {len(text)}, Limit: {limit}, Needs chunking: {needs_chunk}")
        return needs_chunk
    
    def _analyze_single_pass(self, text: str, ai_model: str) -> Dict:
        """Einmalige Analyse für kleinere Dokumente"""
        if ai_model.startswith('openai'):
            return self._analyze_with_openai(text, ai_model)
        elif ai_model.startswith('google_gemini'):
            return self._analyze_with_gemini(text, ai_model)
        elif ai_model.startswith('anthropic_claude'):
            return self._analyze_with_claude(text, ai_model)
        else:
            raise ValueError(f"Unbekanntes KI-Modell: {ai_model}")
    
    def _analyze_with_chunking(self, text: str, ai_model: str) -> Dict:
        """Multi-Pass Analyse für große Dokumente"""
        print(f"DEBUG: Starting chunked analysis for {len(text)} characters")
        
        # Teile das Dokument in überlappende Chunks
        chunks = self._split_text_into_chunks(text, ai_model)
        print(f"DEBUG: Split document into {len(chunks)} chunks")
        
        # Analysiere jeden Chunk
        all_positions = []
        project_info = None
        summary_parts = []
        
        failed_chunks = 0
        max_failed_chunks = 5  # Maximal 5 fehlgeschlagene Chunks tolerieren
        
        for i, chunk in enumerate(chunks):
            print(f"DEBUG: Analyzing chunk {i+1}/{len(chunks)}")
            
            # Timeout für einzelne Chunks
            start_time = time.time()
            max_chunk_time = 180  # 3 Minuten pro Chunk
            
            try:
                chunk_result = self._analyze_single_pass(chunk, ai_model)
                
                # Prüfe Verarbeitungszeit
                elapsed_time = time.time() - start_time
                if elapsed_time > max_chunk_time:
                    print(f"DEBUG: Chunk {i+1} took too long ({elapsed_time:.1f}s), skipping remaining chunks")
                    break
                
                # Sammle Projektinfo vom ersten Chunk
                if i == 0 and 'project_info' in chunk_result:
                    project_info = chunk_result['project_info']
                
                # Sammle Summary-Teile
                if 'summary' in chunk_result and chunk_result['summary']:
                    summary_parts.append(chunk_result['summary'])
                
                # Sammle alle Positionen
                if 'positions' in chunk_result and chunk_result['positions']:
                    all_positions.extend(chunk_result['positions'])
                    print(f"DEBUG: Found {len(chunk_result['positions'])} positions in chunk {i+1}")
                    
            except Exception as e:
                print(f"DEBUG: Error analyzing chunk {i+1}: {e}")
                failed_chunks += 1
                
                # Stoppe wenn zu viele Chunks fehlschlagen
                if failed_chunks >= max_failed_chunks:
                    print(f"DEBUG: Too many failed chunks ({failed_chunks}), stopping analysis")
                    break
                continue
        
        # Kombiniere Ergebnisse
        combined_result = {
            'summary': ' '.join(summary_parts) if summary_parts else 'Mehrteiliges Dokument analysiert',
            'project_info': project_info or {
                'title': 'Unbekanntes Projekt',
                'client': 'Nicht identifiziert', 
                'deadline': None,
                'location': 'Nicht angegeben'
            },
            'positions': self._deduplicate_positions(all_positions),
            'total_value': None,
            'currency': 'EUR'
        }
        
        print(f"DEBUG: Combined analysis found {len(combined_result['positions'])} total positions")
        return combined_result
    
    def _get_analysis_prompt(self) -> str:
        """Erstellt den Prompt für die Ausschreibungsanalyse"""
        return """
Analysiere dieses Ausschreibungsdokument und extrahiere strukturierte Informationen über alle Positionen.

Aufgabe:
1. Erstelle eine Zusammenfassung des Dokuments
2. Finde alle Ausschreibungspositionen mit:
   - Positionsnummer
   - Titel/Beschreibung
   - Menge/Anzahl (falls vorhanden)
   - Einheit (Stk, m², kg, etc.)
   - Einzelpreis (falls vorhanden)
   - Gesamtpreis (falls vorhanden)
   - Kategorie/Gewerk

WICHTIG - ANALYSIERE ALLE POSITIONEN: 
- Verwende ```json Code-Blöcke
- Erfasse ALLE Positionen aus dem Dokument (nicht nur die ersten)
- Beschreibungen: Kompakt aber informativ (max. 100 Zeichen)
- Verwende Abkürzungen für längere Begriffe
- Keine zusätzlichen Erklärungen außerhalb des JSON

Antworte im folgenden JSON-Format:
{
    "summary": "Kurze Zusammenfassung des Dokuments",
    "project_info": {
        "title": "Projekttitel",
        "client": "Auftraggeber",
        "deadline": "Abgabefrist",
        "location": "Ort"
    },
    "positions": [
        {
            "position_number": "1.1",
            "title": "Kurzer Titel",
            "description": "Kurze Beschreibung (max. 80 Zeichen)",
            "quantity": 10.5,
            "unit": "m²",
            "unit_price": 25.50,
            "total_price": 267.75,
            "category": "Kategorie",
            "page_reference": 5
        }
    ],
    "total_value": 50000.00,
    "currency": "EUR"
}

Wichtig: 
- Extrahiere nur tatsächlich vorhandene Positionen
- Achte auf korrekte Zahlenformate
- Gib alle Preise als Dezimalzahlen an
- Falls Informationen fehlen, verwende null
"""
    
    def _analyze_with_openai(self, text: str, model: str) -> Dict:
        """Analyse mit OpenAI GPT"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            api_key = get_user_api_key(self.user, 'openai')
            
            if not api_key:
                raise Exception("OpenAI API-Schlüssel nicht konfiguriert")
            
            # Text auf max. Zeichen begrenzen basierend auf Modell-Kontext
            # Konservative Schätzung: 1 Token = 4 Zeichen, Reserve für Prompt
            context_limits = {
                'openai_gpt4o': 400000,      # 128k tokens = ~500k chars
                'openai_gpt4o_mini': 400000, # 128k tokens
                'openai_gpt4_turbo': 400000, # 128k tokens
                'openai_gpt4': 24000,        # 8k tokens
                'openai_gpt35_turbo': 48000  # 16k tokens
            }
            max_chars = context_limits.get(model, 48000)
            if len(text) > max_chars:
                print(f"DEBUG: Text zu lang ({len(text)} Zeichen), kürze auf {max_chars} Zeichen")
                text = text[:max_chars] + "\n\n... (Text gekürzt)"
            
            # Modell-Mapping für OpenAI
            model_mapping = {
                'openai_gpt4o': 'gpt-4o',
                'openai_gpt4o_mini': 'gpt-4o-mini',
                'openai_gpt4_turbo': 'gpt-4-turbo',
                'openai_gpt4': 'gpt-4',
                'openai_gpt35_turbo': 'gpt-3.5-turbo'
            }
            model_name = model_mapping.get(model, 'gpt-4o-mini')
            print(f"DEBUG: Verwende Modell {model_name}, Textlänge: {len(text)} Zeichen")
            
            session = self._get_requests_session_with_retry()
            try:
                response = session.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': model_name,
                        'messages': [
                            {'role': 'system', 'content': self._get_analysis_prompt()},
                            {'role': 'user', 'content': f"Analysiere dieses Dokument:\n\n{text}"}
                        ],
                        'max_tokens': 8000,  # Erhöht für vollständige JSON-Antworten
                        'temperature': 0.1
                    },
                    timeout=120  # Erhöht von 60 auf 120 Sekunden
                )
            except requests.exceptions.ConnectionError as e:
                raise Exception("Netzwerkverbindung fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung.")
            except requests.exceptions.Timeout:
                raise Exception("Zeitüberschreitung bei der API-Anfrage. Bitte versuchen Sie es erneut.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Netzwerkfehler: {str(e)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG: OpenAI response: {result}")
                
                choice = result['choices'][0]
                content = choice['message']['content']
                
                # Prüfe finish_reason
                if 'finish_reason' in choice:
                    print(f"DEBUG: OpenAI finish reason: {choice['finish_reason']}")
                    if choice['finish_reason'] == 'length':
                        print("DEBUG: OpenAI response was truncated due to length limit")
                        content = self._repair_truncated_json(content)
                
                print(f"DEBUG: OpenAI content length: {len(content)}")
                print(f"DEBUG: OpenAI content preview: {content[:500]}...")
                return self._parse_analysis_result(content)
            elif response.status_code == 429:
                raise Exception("OpenAI API Rate Limit erreicht. Bitte warten Sie einen Moment und versuchen Sie es erneut.")
            elif response.status_code == 400:
                # Bei 400 Fehler Details aus der Response extrahieren
                try:
                    error_details = response.json()
                    error_message = error_details.get('error', {}).get('message', 'Unbekannter Fehler')
                    raise Exception(f"OpenAI API Anfragefehler: {error_message}")
                except:
                    raise Exception(f"OpenAI API Anfragefehler (400): {response.text}")
            elif response.status_code == 401:
                raise Exception("OpenAI API-Schlüssel ungültig oder abgelaufen.")
            elif response.status_code == 402:
                raise Exception("OpenAI API-Guthaben aufgebraucht. Bitte laden Sie Ihr Guthaben auf.")
            else:
                error_text = response.text[:500] if response.text else 'Keine Details verfügbar'
                raise Exception(f"OpenAI API Fehler {response.status_code}: {error_text}")
        
        except requests.exceptions.ConnectionError as e:
            if "Failed to resolve" in str(e) or "getaddrinfo failed" in str(e):
                raise Exception("DNS-Auflösung fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung und DNS-Einstellungen.")
            raise Exception(f"OpenAI Analyse fehlgeschlagen: Netzwerkverbindung nicht möglich")
        except Exception as e:
            if "Netzwerkverbindung fehlgeschlagen" in str(e) or "Zeitüberschreitung" in str(e) or "Netzwerkfehler" in str(e):
                raise e
            raise Exception(f"OpenAI Analyse fehlgeschlagen: {str(e)}")
    
    def _analyze_with_gemini(self, text: str, model: str = 'google_gemini_flash') -> Dict:
        """Analyse mit Google Gemini"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            api_key = get_user_api_key(self.user, 'google')
            
            if not api_key:
                raise Exception("Google API-Schlüssel nicht konfiguriert")
            
            prompt = f"{self._get_analysis_prompt()}\n\nAnalysiere dieses Dokument:\n\n{text}"
            
            # Modell-Mapping für Google
            gemini_models = {
                'google_gemini_pro': 'gemini-1.5-pro',
                'google_gemini_flash': 'gemini-1.5-flash'
            }
            gemini_model = gemini_models.get(model, 'gemini-1.5-flash')
            
            session = self._get_requests_session_with_retry()
            try:
                response = session.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}',
                    headers={'Content-Type': 'application/json'},
                    json={
                        'contents': [{
                            'parts': [{'text': prompt}]
                        }],
                        'generationConfig': {
                            'maxOutputTokens': 8000,  # Erhöht für vollständige JSON-Antworten
                            'temperature': 0.1
                        }
                    },
                    timeout=120  # Erhöht von 60 auf 120 Sekunden
                )
            except requests.exceptions.ConnectionError as e:
                raise Exception("Netzwerkverbindung fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung.")
            except requests.exceptions.Timeout:
                raise Exception("Zeitüberschreitung bei der API-Anfrage. Bitte versuchen Sie es erneut.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Netzwerkfehler: {str(e)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG: Gemini response: {result}")
                
                # Prüfe ob die Antwort die erwartete Struktur hat
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    print(f"DEBUG: Gemini candidate structure: {candidate}")
                    
                    if 'content' in candidate and 'parts' in candidate['content']:
                        if len(candidate['content']['parts']) > 0:
                            content = candidate['content']['parts'][0]['text']
                            print(f"DEBUG: Gemini full content length: {len(content)}")
                            print(f"DEBUG: Gemini content preview: {content[:1000]}")
                            print(f"DEBUG: Gemini content end: {content[-500:]}")
                            
                            # Prüfe auf Safety-Filter oder andere Probleme
                            if 'finishReason' in candidate:
                                print(f"DEBUG: Gemini finish reason: {candidate['finishReason']}")
                                if candidate['finishReason'] == 'MAX_TOKENS':
                                    print("DEBUG: Gemini response was truncated due to MAX_TOKENS")
                                    # Versuche das unvollständige JSON zu reparieren
                                    content = self._repair_truncated_json(content)
                            
                            result = self._parse_analysis_result(content)
                            print(f"DEBUG: Parsed result: {result}")
                            return result
                        else:
                            raise Exception("Gemini Antwort enthält keine Textteile")
                    else:
                        raise Exception(f"Gemini Antwort hat unerwartete Struktur: {candidate}")
                else:
                    raise Exception(f"Gemini Antwort enthält keine Kandidaten. Full response: {result}")
            elif response.status_code == 429:
                raise Exception("Google Gemini API Rate Limit erreicht. Bitte warten Sie einen Moment und versuchen Sie es erneut.")
            elif response.status_code == 401:
                raise Exception("Google API-Schlüssel ungültig oder abgelaufen.")
            elif response.status_code == 400:
                # Bei 400 Fehler Details aus der Response extrahieren
                try:
                    error_details = response.json()
                    error_message = error_details.get('error', {}).get('message', 'Unbekannter Fehler')
                    raise Exception(f"Gemini API Anfragefehler: {error_message}")
                except:
                    raise Exception(f"Gemini API Anfragefehler (400): {response.text[:500]}")
            elif response.status_code == 403:
                raise Exception("Google API-Zugriff verweigert oder Quota überschritten.")
            else:
                error_text = response.text[:500] if response.text else 'Keine Details verfügbar'
                raise Exception(f"Gemini API Fehler {response.status_code}: {error_text}")
        
        except requests.exceptions.ConnectionError as e:
            if "Failed to resolve" in str(e) or "getaddrinfo failed" in str(e):
                raise Exception("DNS-Auflösung fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung und DNS-Einstellungen.")
            raise Exception(f"Gemini Analyse fehlgeschlagen: Netzwerkverbindung nicht möglich")
        except Exception as e:
            if "Netzwerkverbindung fehlgeschlagen" in str(e) or "Zeitüberschreitung" in str(e) or "Netzwerkfehler" in str(e):
                raise e
            raise Exception(f"Gemini Analyse fehlgeschlagen: {str(e)}")
    
    def _analyze_with_claude(self, text: str, model: str = 'anthropic_claude_haiku') -> Dict:
        """Analyse mit Anthropic Claude"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            api_key = get_user_api_key(self.user, 'anthropic')
            
            if not api_key:
                raise Exception("Anthropic API-Schlüssel nicht konfiguriert")
            
            # Text auf max. Zeichen begrenzen (Claude hat 200k Context)
            max_chars = 150000
            if len(text) > max_chars:
                print(f"DEBUG: Text zu lang ({len(text)} Zeichen), kürze auf {max_chars} Zeichen")
                text = text[:max_chars] + "\n\n... (Text gekürzt)"
            
            session = self._get_requests_session_with_retry()
            try:
                response = session.post(
                    'https://api.anthropic.com/v1/messages',
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json',
                        'anthropic-version': '2023-06-01'
                    },
                    json={
                        'model': self._get_claude_model_name(model),
                        'max_tokens': 8000,  # Erhöht für vollständige JSON-Antworten
                        'temperature': 0.1,
                        'messages': [
                            {
                                'role': 'user',
                                'content': f"{self._get_analysis_prompt()}\n\nAnalysiere dieses Dokument:\n\n{text}"
                            }
                        ]
                    },
                    timeout=120  # Erhöht von 60 auf 120 Sekunden
                )
            except requests.exceptions.ConnectionError as e:
                raise Exception("Netzwerkverbindung fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung.")
            except requests.exceptions.Timeout:
                raise Exception("Zeitüberschreitung bei der API-Anfrage. Bitte versuchen Sie es erneut.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Netzwerkfehler: {str(e)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG: Claude response: {result}")
                
                if 'content' in result and len(result['content']) > 0:
                    content = result['content'][0]['text']
                    
                    # Prüfe stop_reason
                    if 'stop_reason' in result:
                        print(f"DEBUG: Claude stop reason: {result['stop_reason']}")
                        if result['stop_reason'] == 'max_tokens':
                            print("DEBUG: Claude response was truncated due to max_tokens")
                            content = self._repair_truncated_json(content)
                    
                    print(f"DEBUG: Claude content length: {len(content)}")
                    print(f"DEBUG: Claude content preview: {content[:500]}...")
                    return self._parse_analysis_result(content)
                else:
                    raise Exception("Claude Antwort enthält keinen Inhalt")
            elif response.status_code == 400:
                try:
                    error_details = response.json()
                    error_message = error_details.get('error', {}).get('message', 'Unbekannter Fehler')
                    raise Exception(f"Claude API Anfragefehler: {error_message}")
                except:
                    raise Exception(f"Claude API Anfragefehler (400): {response.text[:500]}")
            elif response.status_code == 401:
                raise Exception("Claude API-Schlüssel ungültig oder abgelaufen.")
            elif response.status_code == 429:
                raise Exception("Claude API Rate Limit erreicht. Bitte warten Sie einen Moment und versuchen Sie es erneut.")
            else:
                error_text = response.text[:500] if response.text else 'Keine Details verfügbar'
                raise Exception(f"Claude API Fehler {response.status_code}: {error_text}")
        
        except requests.exceptions.ConnectionError as e:
            if "Failed to resolve" in str(e) or "getaddrinfo failed" in str(e):
                raise Exception("DNS-Auflösung fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung und DNS-Einstellungen.")
            raise Exception(f"Claude Analyse fehlgeschlagen: Netzwerkverbindung nicht möglich")
        except Exception as e:
            if "Netzwerkverbindung fehlgeschlagen" in str(e) or "Zeitüberschreitung" in str(e) or "Netzwerkfehler" in str(e):
                raise e
            raise Exception(f"Claude Analyse fehlgeschlagen: {str(e)}")
    
    def _parse_analysis_result(self, content: str) -> Dict:
        """Parst das Analyseergebnis der KI"""
        try:
            print(f"DEBUG: Parsing content: {content[:1000]}...")
            
            # JSON aus dem Text extrahieren - versuche verschiedene Methoden
            # 1. Direktes JSON parsen falls der gesamte Content JSON ist
            content_stripped = content.strip()
            if content_stripped.startswith('{') and content_stripped.endswith('}'):
                try:
                    return json.loads(content_stripped)
                except json.JSONDecodeError:
                    pass
            
            # 2. JSON aus Markdown Code-Blöcken extrahieren (erweitert für Gemini)
            import re
            # Versuche verschiedene Markdown-Formate
            patterns = [
                r'```json\s*({.*?})\s*```',      # ```json { } ```
                r'```\s*({.*?})\s*```',          # ``` { } ```
                r'```json\s*([\s\S]*?)```',       # ```json ... ``` (mehrzeilig)
                r'```\s*([\s\S]*?)```'            # ``` ... ``` (mehrzeilig)
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    try:
                        # Bereinige den Match
                        cleaned = match.strip()
                        if not cleaned.startswith('{'):
                            # Versuche JSON aus dem Text zu extrahieren
                            start = cleaned.find('{')
                            end = cleaned.rfind('}') + 1
                            if start >= 0 and end > start:
                                cleaned = cleaned[start:end]
                        
                        print(f"DEBUG: Trying to parse JSON from markdown: {cleaned[:200]}...")
                        return json.loads(cleaned)
                    except json.JSONDecodeError as e:
                        print(f"DEBUG: JSON decode error for pattern {pattern}: {e}")
                        continue
            
            # 3. Erstes { bis letztes } finden
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Versuche JSON zu reparieren (häufige Probleme)
                    json_str = json_str.replace('\n', '\\n').replace('\"', '"')
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
            
            # Fallback wenn kein JSON gefunden wurde
            print(f"DEBUG: No valid JSON found, using fallback")
            return self._create_fallback_analysis(content)
        
        except Exception as e:
            print(f"DEBUG: Parse error: {e}")
            return self._create_fallback_analysis(content)
    
    def _create_fallback_analysis(self, text: str) -> Dict:
        """Erstellt eine Fallback-Analyse wenn die KI-Analyse fehlschlägt"""
        return {
            "summary": "Automatische Analyse nicht möglich. Bitte manuell überprüfen.",
            "project_info": {
                "title": "Unbekanntes Projekt",
                "client": "Nicht identifiziert",
                "deadline": None,
                "location": "Nicht angegeben"
            },
            "positions": [],
            "total_value": None,
            "currency": "EUR"
        }


class PDFSummaryGenerator:
    """Service zum Generieren von Zusammenfassungs-PDFs"""
    
    def generate_summary_pdf(self, summary: PDFSummary) -> str:
        """Generiert eine PDF-Zusammenfassung"""
        # Dynamische Prüfung von ReportLab-Verfügbarkeit
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.units import cm
        except ImportError:
            raise Exception("ReportLab ist nicht installiert. Bitte installieren Sie es mit: pip install reportlab")
        
        try:
            # Temporäre Datei erstellen
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_filename = tmp_file.name
            
            # PDF erstellen
            doc = SimpleDocTemplate(tmp_filename, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Titel
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                textColor=colors.darkblue
            )
            story.append(Paragraph(f"Ausschreibungsanalyse: {summary.document.title}", title_style))
            story.append(Spacer(1, 20))
            
            # Dokumentinfo
            doc_info = [
                ['Dokument:', summary.document.title],
                ['Analysiert mit:', summary.get_ai_model_display()],
                ['Analysiert am:', summary.created_at.strftime('%d.%m.%Y %H:%M')],
                ['Status:', summary.get_status_display()],
            ]
            
            doc_table = Table(doc_info, colWidths=[4*cm, 12*cm])
            doc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(doc_table)
            story.append(Spacer(1, 20))
            
            # Zusammenfassung
            if summary.summary_text:
                story.append(Paragraph("Zusammenfassung", styles['Heading2']))
                story.append(Paragraph(summary.summary_text, styles['Normal']))
                story.append(Spacer(1, 20))
            
            # Positionen
            positions = summary.positions.all()
            if positions:
                story.append(Paragraph("Ausschreibungspositionen", styles['Heading2']))
                story.append(Spacer(1, 10))
                
                # Tabellendaten vorbereiten
                table_data = [
                    ['Pos.', 'Titel', 'Menge', 'Einheit', 'Einzelpreis', 'Gesamtpreis']
                ]
                
                total_sum = Decimal('0.00')
                
                for pos in positions:
                    row = [
                        pos.position_number or '-',
                        pos.title[:50] + '...' if len(pos.title) > 50 else pos.title,
                        str(pos.quantity) if pos.quantity else '-',
                        pos.unit or '-',
                        f"{pos.unit_price:.2f} €" if pos.unit_price else '-',
                        f"{pos.total_price:.2f} €" if pos.total_price else '-'
                    ]
                    table_data.append(row)
                    
                    if pos.total_price:
                        total_sum += pos.total_price
                
                # Gesamtsumme hinzufügen
                if total_sum > 0:
                    table_data.append(['', '', '', '', 'Gesamt:', f"{total_sum:.2f} €"])
                
                # Tabelle erstellen
                pos_table = Table(table_data, colWidths=[2*cm, 6*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm])
                pos_table.setStyle(TableStyle([
                    # Header
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Data rows
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                    ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Zahlen rechtsbündig
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    
                    # Gesamtsumme (letzte Zeile)
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    
                    # Grid
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                
                story.append(pos_table)
            
            # PDF bauen
            doc.build(story)
            
            return tmp_filename
        
        except Exception as e:
            raise Exception(f"Fehler bei der PDF-Generierung: {str(e)}")


class PDFSummaryService:
    """Hauptservice für die PDF-Zusammenfassungsfunktionalität"""
    
    def __init__(self):
        self.text_extractor = PDFTextExtractor()
        self.pdf_generator = PDFSummaryGenerator()
    
    def create_summary(self, document: PDFDocument, ai_model: str, user) -> PDFSummary:
        """Erstellt eine neue Zusammenfassung für ein Dokument"""
        # Summary-Objekt erstellen
        summary = PDFSummary.objects.create(
            document=document,
            user=user,
            ai_model=ai_model,
            status='processing'
        )
        
        try:
            start_time = time.time()
            
            # Text extrahieren
            extracted_text = self.text_extractor.extract_text_from_pdf(document.file.path)
            summary.extracted_text = extracted_text
            summary.save()
            
            # KI-Analyse durchführen
            analyzer = TenderAnalysisService(user)
            analysis_result = analyzer.analyze_tender_document(extracted_text, ai_model)
            
            # Ergebnisse speichern
            summary.summary_text = analysis_result.get('summary', '')
            summary.structured_data = analysis_result
            summary.save()
            
            # Positionen erstellen
            self._create_positions_from_analysis(summary, analysis_result)
            
            # Zusammenfassungs-PDF generieren
            pdf_path = self.pdf_generator.generate_summary_pdf(summary)
            
            # PDF-Datei im Model speichern
            with open(pdf_path, 'rb') as pdf_file:
                filename = f"zusammenfassung_{document.title}_{summary.id}.pdf"
                summary.summary_pdf.save(filename, ContentFile(pdf_file.read()))
            
            # Temporäre Datei löschen
            os.unlink(pdf_path)
            
            # Abschluss
            processing_time = time.time() - start_time
            summary.processing_time = processing_time
            summary.completed_at = timezone.now()
            summary.status = 'completed'
            summary.save()
            
            return summary
        
        except Exception as e:
            summary.status = 'error'
            summary.error_message = str(e)
            summary.save()
            raise
    
    def _create_positions_from_analysis(self, summary: PDFSummary, analysis_result: Dict):
        """Erstellt TenderPosition-Objekte aus den Analyseergebnissen"""
        positions_data = analysis_result.get('positions', [])
        
        for pos_data in positions_data:
            try:
                TenderPosition.objects.create(
                    summary=summary,
                    position_number=pos_data.get('position_number', ''),
                    title=pos_data.get('title', ''),
                    description=pos_data.get('description', ''),
                    quantity=Decimal(str(pos_data.get('quantity'))) if pos_data.get('quantity') else None,
                    unit=pos_data.get('unit', ''),
                    unit_price=Decimal(str(pos_data.get('unit_price'))) if pos_data.get('unit_price') else None,
                    total_price=Decimal(str(pos_data.get('total_price'))) if pos_data.get('total_price') else None,
                    category=pos_data.get('category', ''),
                    page_reference=pos_data.get('page_reference')
                )
            except (ValueError, TypeError) as e:
                # Position überspringen bei Fehlern in den Daten
                continue