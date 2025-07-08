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
    
    def analyze_tender_document(self, text: str, ai_model: str) -> Dict:
        """Analysiert ein Ausschreibungsdokument mit dem gewählten KI-Modell"""
        try:
            if ai_model.startswith('openai'):
                return self._analyze_with_openai(text, ai_model)
            elif ai_model == 'google_gemini':
                return self._analyze_with_gemini(text)
            elif ai_model == 'anthropic_claude':
                return self._analyze_with_claude(text)
            else:
                raise ValueError(f"Unbekanntes KI-Modell: {ai_model}")
        
        except Exception as e:
            raise Exception(f"Fehler bei der KI-Analyse: {str(e)}")
    
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
            "title": "Beschreibung der Position",
            "description": "Detaillierte Beschreibung",
            "quantity": 10.5,
            "unit": "m²",
            "unit_price": 25.50,
            "total_price": 267.75,
            "category": "Mauerwerk",
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
            
            model_name = 'gpt-4' if model == 'openai_gpt4' else 'gpt-3.5-turbo'
            
            response = requests.post(
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
                    'max_tokens': 4000,
                    'temperature': 0.1
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return self._parse_analysis_result(content)
            else:
                raise Exception(f"OpenAI API Fehler: {response.status_code}")
        
        except Exception as e:
            raise Exception(f"OpenAI Analyse fehlgeschlagen: {str(e)}")
    
    def _analyze_with_gemini(self, text: str) -> Dict:
        """Analyse mit Google Gemini"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            api_key = get_user_api_key(self.user, 'google')
            
            if not api_key:
                raise Exception("Google API-Schlüssel nicht konfiguriert")
            
            prompt = f"{self._get_analysis_prompt()}\n\nAnalysiere dieses Dokument:\n\n{text}"
            
            response = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}',
                headers={'Content-Type': 'application/json'},
                json={
                    'contents': [{
                        'parts': [{'text': prompt}]
                    }],
                    'generationConfig': {
                        'maxOutputTokens': 4000,
                        'temperature': 0.1
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['candidates'][0]['content']['parts'][0]['text']
                return self._parse_analysis_result(content)
            else:
                raise Exception(f"Gemini API Fehler: {response.status_code}")
        
        except Exception as e:
            raise Exception(f"Gemini Analyse fehlgeschlagen: {str(e)}")
    
    def _analyze_with_claude(self, text: str) -> Dict:
        """Analyse mit Anthropic Claude"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            api_key = get_user_api_key(self.user, 'anthropic')
            
            if not api_key:
                raise Exception("Anthropic API-Schlüssel nicht konfiguriert")
            
            # Vereinfachte Implementierung - Claude API würde hier integriert werden
            # Für jetzt verwenden wir einen Fallback
            return self._create_fallback_analysis(text)
        
        except Exception as e:
            raise Exception(f"Claude Analyse fehlgeschlagen: {str(e)}")
    
    def _parse_analysis_result(self, content: str) -> Dict:
        """Parst das Analyseergebnis der KI"""
        try:
            # JSON aus dem Text extrahieren
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback wenn kein JSON gefunden wurde
                return self._create_fallback_analysis(content)
        
        except json.JSONDecodeError:
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
        if not REPORTLAB_AVAILABLE:
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