import fitz  # PyMuPDF
import io
import requests
from PIL import Image
from django.core.files.base import ContentFile


class PDFService:
    """Service für PDF-Verarbeitung mit PyMuPDF"""

    @staticmethod
    def generate_thumbnail(pdf_file, size=(300, 400)):
        """
        Generiert ein Thumbnail aus der ersten PDF-Seite.

        Args:
            pdf_file: Django UploadedFile oder File-ähnliches Objekt
            size: Tuple (width, height) für maximale Größe

        Returns:
            ContentFile mit dem Thumbnail als PNG, oder None bei Fehler
        """
        try:
            # PDF als Bytes lesen
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            if len(doc) == 0:
                doc.close()
                return None

            # Erste Seite als Bild rendern
            page = doc[0]
            mat = fitz.Matrix(2, 2)  # 2x Zoom für bessere Qualität
            pix = page.get_pixmap(matrix=mat)

            # In PIL Image konvertieren
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Auf gewünschte Größe skalieren (Aspect Ratio beibehalten)
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Als PNG in BytesIO speichern
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)

            doc.close()
            return ContentFile(buffer.read(), name='thumbnail.png')

        except Exception as e:
            print(f"Fehler beim Thumbnail-Generieren: {e}")
            return None

    @staticmethod
    def get_page_count(pdf_file):
        """
        Gibt die Seitenanzahl des PDFs zurück.

        Args:
            pdf_file: Django UploadedFile oder File-ähnliches Objekt

        Returns:
            int: Anzahl der Seiten
        """
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            print(f"Fehler beim Seitenzählen: {e}")
            return 0

    @staticmethod
    def extract_title(pdf_file):
        """
        Extrahiert den Titel aus PDF-Metadaten oder der ersten Seite.

        Args:
            pdf_file: Django UploadedFile oder File-ähnliches Objekt

        Returns:
            str: Extrahierter Titel oder leerer String
        """
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 1. Versuche Titel aus Metadaten zu lesen
            metadata = doc.metadata
            if metadata and metadata.get('title'):
                title = metadata['title'].strip()
                if title and len(title) > 3:  # Ignoriere zu kurze Titel
                    doc.close()
                    return title
            
            # 2. Versuche Titel aus erster Seite zu extrahieren
            if len(doc) > 0:
                page = doc[0]
                text = page.get_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                # Suche nach der ersten nicht-leeren Zeile mit min. 10 Zeichen
                # die nicht wie eine Seitenzahl oder DOI aussieht
                for line in lines[:10]:  # Nur erste 10 Zeilen prüfen
                    if len(line) >= 10 and not line.isdigit():
                        # Ignoriere Zeilen die wie DOI, URLs, etc. aussehen
                        if not any(x in line.lower() for x in ['doi:', 'http', 'www.', '@', 'issn', 'isbn']):
                            doc.close()
                            return line[:200]  # Max 200 Zeichen
            
            doc.close()
            return ""
        except Exception as e:
            print(f"Fehler beim Titel-Extrahieren: {e}")
            return ""

    @staticmethod
    def extract_text_from_page(pdf_file, page_number):
        """
        Extrahiert Text von einer bestimmten Seite.

        Args:
            pdf_file: Django UploadedFile oder File-ähnliches Objekt
            page_number: Seitennummer (1-basiert)

        Returns:
            str: Extrahierter Text
        """
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            if page_number < 1 or page_number > len(doc):
                doc.close()
                return ""

            page = doc[page_number - 1]  # 0-basierter Index
            text = page.get_text()

            doc.close()
            return text
        except Exception as e:
            print(f"Fehler bei Textextraktion: {e}")
            return ""


class TranslationService:
    """Service für Übersetzungen via OpenAI/Anthropic"""

    def __init__(self, user):
        self.user = user

    def translate(self, text, source_lang='en', target_lang='de', provider='openai'):
        """
        Übersetzt Text mit dem gewählten Provider.

        Args:
            text: Zu übersetzender Text
            source_lang: Quellsprache (z.B. 'en')
            target_lang: Zielsprache (z.B. 'de')
            provider: 'openai' oder 'anthropic'

        Returns:
            str: Übersetzter Text

        Raises:
            ValueError: Wenn kein API-Key konfiguriert ist
            Exception: Bei API-Fehlern
        """
        from naturmacher.utils.api_helpers import get_user_api_key

        api_key = get_user_api_key(self.user, provider)
        if not api_key:
            raise ValueError(f"Kein API-Key für {provider} konfiguriert. "
                           "Bitte in den Account-Einstellungen hinterlegen.")

        if provider == 'openai':
            return self._translate_openai(text, source_lang, target_lang, api_key)
        elif provider == 'anthropic':
            return self._translate_anthropic(text, source_lang, target_lang, api_key)
        else:
            raise ValueError(f"Unbekannter Provider: {provider}")

    def _get_language_name(self, lang_code):
        """Konvertiert Sprachcode zu vollem Namen"""
        names = {
            'en': 'Englisch',
            'de': 'Deutsch',
            'fr': 'Französisch',
            'es': 'Spanisch',
            'it': 'Italienisch',
            'pt': 'Portugiesisch',
            'nl': 'Niederländisch',
            'pl': 'Polnisch',
            'ru': 'Russisch',
            'zh': 'Chinesisch',
            'ja': 'Japanisch',
            'ko': 'Koreanisch',
        }
        return names.get(lang_code, lang_code)

    def _translate_openai(self, text, source_lang, target_lang, api_key):
        """Übersetzung mit OpenAI API"""
        source_name = self._get_language_name(source_lang)
        target_name = self._get_language_name(target_lang)

        # Bevorzugtes Model des Users nutzen
        model = getattr(self.user, 'preferred_openai_model', None) or 'gpt-4o-mini'

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [
                    {
                        'role': 'system',
                        'content': f'Du bist ein präziser Übersetzer. Übersetze den folgenden Text '
                                   f'von {source_name} nach {target_name}. '
                                   f'Antworte NUR mit der Übersetzung, ohne zusätzliche Erklärungen '
                                   f'oder Anführungszeichen.'
                    },
                    {'role': 'user', 'content': text}
                ],
                'temperature': 0.3,
                'max_tokens': 1000
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI API Fehler ({response.status_code}): {error_msg}")

    def _translate_anthropic(self, text, source_lang, target_lang, api_key):
        """Übersetzung mit Anthropic Claude API"""
        source_name = self._get_language_name(source_lang)
        target_name = self._get_language_name(target_lang)

        # Bevorzugtes Model des Users nutzen
        model = getattr(self.user, 'preferred_anthropic_model', None) or 'claude-3-5-sonnet-20241022'

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'messages': [
                    {
                        'role': 'user',
                        'content': f'Übersetze den folgenden Text von {source_name} nach {target_name}. '
                                   f'Antworte NUR mit der Übersetzung, ohne Anführungszeichen oder Erklärungen:\n\n'
                                   f'{text}'
                    }
                ]
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"Anthropic API Fehler ({response.status_code}): {error_msg}")


class ImageExplanationService:
    """Service für Bild-Erklärungen via OpenAI Vision"""

    def __init__(self, user):
        self.user = user

    def explain_image(self, image_base64, context='', provider='openai'):
        """
        Erklärt ein Bild (z.B. ein Diagramm, Grafik oder Formel aus einer PDF).

        Args:
            image_base64: Base64-kodiertes Bild (PNG/JPEG)
            context: Optionaler Kontext (z.B. PDF-Titel, Thema)
            provider: 'openai' (aktuell nur OpenAI Vision unterstützt)

        Returns:
            str: Erklärung des Bildinhalts

        Raises:
            ValueError: Wenn kein API-Key konfiguriert ist
            Exception: Bei API-Fehlern
        """
        from naturmacher.utils.api_helpers import get_user_api_key

        api_key = get_user_api_key(self.user, 'openai')
        if not api_key:
            raise ValueError("Kein OpenAI API-Key konfiguriert. "
                           "Bitte in den Account-Einstellungen hinterlegen.")

        return self._explain_image_openai(image_base64, context, api_key)

    def _explain_image_openai(self, image_base64, context, api_key):
        """Bild-Erklärung mit OpenAI Vision API"""
        # gpt-4o und gpt-4o-mini unterstützen Vision
        model = 'gpt-4o-mini'  # Kostengünstig und gut für Bilder
        
        # Sicherstellen, dass das Bild das richtige Format hat
        if not image_base64.startswith('data:'):
            # Annahme: PNG wenn kein MIME-Typ angegeben
            image_base64 = f"data:image/png;base64,{image_base64}"

        context_text = ""
        if context:
            context_text = f"\n\nKontext: {context}"

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'Du bist ein Experte für die Analyse von Bildern aus wissenschaftlichen '
                                   'Dokumenten und PDFs. Erkläre den Bildinhalt auf Deutsch, klar und verständlich. '
                                   'Beschreibe Diagramme, Grafiken, Formeln, Tabellen oder andere visuelle Elemente. '
                                   'Erkläre die Bedeutung und den Zusammenhang. Halte die Erklärung informativ aber verständlich.'
                    },
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'text',
                                'text': f'Erkläre bitte dieses Bild/Diagramm aus einem PDF-Dokument.{context_text}'
                            },
                            {
                                'type': 'image_url',
                                'image_url': {
                                    'url': image_base64,
                                    'detail': 'high'
                                }
                            }
                        ]
                    }
                ],
                'max_tokens': 1000
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI Vision Fehler ({response.status_code}): {error_msg}")


class FollowupService:
    """Service für Follow-up-Fragen zu Erklärungen"""

    def __init__(self, user):
        self.user = user

    def answer_followup(self, question, conversation_history, original_context='', provider='openai'):
        """
        Beantwortet eine Follow-up-Frage basierend auf der vorherigen Konversation.

        Args:
            question: Die Follow-up-Frage
            conversation_history: Liste von vorherigen Nachrichten
            original_context: Ursprünglicher Kontext (Text oder Bildbeschreibung)
            provider: 'openai' oder 'anthropic'

        Returns:
            str: Antwort auf die Frage
        """
        from naturmacher.utils.api_helpers import get_user_api_key

        api_key = get_user_api_key(self.user, provider)
        if not api_key:
            raise ValueError(f"Kein API-Key für {provider} konfiguriert.")

        if provider == 'openai':
            return self._answer_openai(question, conversation_history, original_context, api_key)
        else:
            return self._answer_anthropic(question, conversation_history, original_context, api_key)

    def _answer_openai(self, question, conversation_history, original_context, api_key):
        """Antwort mit OpenAI API"""
        model = getattr(self.user, 'preferred_openai_model', None) or 'gpt-4o-mini'

        system_prompt = f"""Du bist ein hilfreicher Assistent, der Fragen zu einem zuvor erklärten Thema beantwortet.
Du hast vorher etwas erklärt (Text, Bild, Diagramm aus einem PDF). Der Nutzer stellt jetzt eine Follow-up-Frage dazu.
Beantworte die Frage direkt und hilfreich auf Deutsch. Beziehe dich auf die vorherige Erklärung.

Ursprünglicher Kontext: {original_context}"""

        messages = [{'role': 'system', 'content': system_prompt}]
        
        # Vorherige Konversation hinzufügen
        for msg in conversation_history[-10:]:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })
        
        messages.append({'role': 'user', 'content': question})

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': messages,
                'temperature': 0.5,
                'max_tokens': 1000
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI Fehler: {error_msg}")

    def _answer_anthropic(self, question, conversation_history, original_context, api_key):
        """Antwort mit Anthropic Claude API"""
        model = getattr(self.user, 'preferred_anthropic_model', None) or 'claude-3-5-sonnet-20241022'

        system_prompt = f"""Du bist ein hilfreicher Assistent, der Fragen zu einem zuvor erklärten Thema beantwortet.
Du hast vorher etwas erklärt (Text, Bild, Diagramm aus einem PDF). Der Nutzer stellt jetzt eine Follow-up-Frage dazu.
Beantworte die Frage direkt und hilfreich auf Deutsch. Beziehe dich auf die vorherige Erklärung.

Ursprünglicher Kontext: {original_context}"""

        messages = []
        for msg in conversation_history[-10:]:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })
        messages.append({'role': 'user', 'content': question})

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'system': system_prompt,
                'messages': messages
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Fehler')
            raise Exception(f"Anthropic Fehler: {error_msg}")


class ExplanationService:
    """Service für Texterklärungen via OpenAI/Anthropic"""

    def __init__(self, user):
        self.user = user

    def explain(self, selected_text, context_before='', context_after='', provider='openai'):
        """
        Erklärt einen Textabschnitt im Kontext.

        Args:
            selected_text: Der ausgewählte Text, der erklärt werden soll
            context_before: Text vor der Auswahl (für Kontext)
            context_after: Text nach der Auswahl (für Kontext)
            provider: 'openai' oder 'anthropic'

        Returns:
            str: Erklärung des Textes

        Raises:
            ValueError: Wenn kein API-Key konfiguriert ist
            Exception: Bei API-Fehlern
        """
        from naturmacher.utils.api_helpers import get_user_api_key

        api_key = get_user_api_key(self.user, provider)
        if not api_key:
            raise ValueError(f"Kein API-Key für {provider} konfiguriert. "
                           "Bitte in den Account-Einstellungen hinterlegen.")

        if provider == 'openai':
            return self._explain_openai(selected_text, context_before, context_after, api_key)
        elif provider == 'anthropic':
            return self._explain_anthropic(selected_text, context_before, context_after, api_key)
        else:
            raise ValueError(f"Unbekannter Provider: {provider}")

    def _explain_openai(self, selected_text, context_before, context_after, api_key):
        """Erklärung mit OpenAI API"""
        model = getattr(self.user, 'preferred_openai_model', None) or 'gpt-4o-mini'

        # Kontext zusammenbauen
        context_prompt = ""
        if context_before or context_after:
            context_prompt = "\n\nKontext:\n"
            if context_before:
                context_prompt += f"Text davor: ...{context_before[-300:]}\n"
            context_prompt += f"[AUSGEWÄHLTER TEXT: {selected_text}]\n"
            if context_after:
                context_prompt += f"Text danach: {context_after[:300]}..."

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'Du bist ein hilfreicher Erklärer. Erkläre den ausgewählten Textabschnitt '
                                   'auf Deutsch, klar und verständlich. Beachte dabei den umgebenden Kontext, '
                                   'falls vorhanden. Erkläre Fachbegriffe, Konzepte und den Zusammenhang. '
                                   'Halte die Erklärung prägnant aber informativ (max. 3-4 Sätze).'
                    },
                    {
                        'role': 'user',
                        'content': f'Erkläre diesen Text: "{selected_text}"{context_prompt}'
                    }
                ],
                'temperature': 0.5,
                'max_tokens': 500
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI API Fehler ({response.status_code}): {error_msg}")

    def _explain_anthropic(self, selected_text, context_before, context_after, api_key):
        """Erklärung mit Anthropic Claude API"""
        model = getattr(self.user, 'preferred_anthropic_model', None) or 'claude-3-5-sonnet-20241022'

        # Kontext zusammenbauen
        context_prompt = ""
        if context_before or context_after:
            context_prompt = "\n\nKontext:\n"
            if context_before:
                context_prompt += f"Text davor: ...{context_before[-300:]}\n"
            context_prompt += f"[AUSGEWÄHLTER TEXT]\n"
            if context_after:
                context_prompt += f"Text danach: {context_after[:300]}..."

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 500,
                'messages': [
                    {
                        'role': 'user',
                        'content': f'Erkläre den folgenden Textabschnitt auf Deutsch, klar und verständlich. '
                                   f'Beachte den Kontext und erkläre Fachbegriffe und Konzepte. '
                                   f'Halte die Erklärung prägnant (max. 3-4 Sätze).\n\n'
                                   f'Text: "{selected_text}"{context_prompt}'
                    }
                ]
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"Anthropic API Fehler ({response.status_code}): {error_msg}")


class SummaryService:
    """Service für KI-generierte PDF-Zusammenfassungen"""

    def __init__(self, user):
        self.user = user

    def extract_full_text(self, pdf_file):
        """
        Extrahiert den gesamten Text aus einem PDF mit Seitenzuordnung.
        
        Returns:
            list: [{"page": 1, "text": "..."}, ...]
        """
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                if text:
                    pages.append({
                        "page": i + 1,
                        "text": text
                    })
            
            doc.close()
            return pages
        except Exception as e:
            print(f"Fehler bei Textextraktion: {e}")
            return []

    def generate_summary(self, book, provider='openai', language='de'):
        """
        Generiert eine strukturierte Zusammenfassung eines PDFs.
        """
        from naturmacher.utils.api_helpers import get_user_api_key
        import json
        
        # Gemini API-Key direkt aus User-Modell holen (Feld heißt gemini_api_key)
        if provider == 'gemini':
            api_key = getattr(self.user, 'gemini_api_key', None)
            if api_key:
                api_key = api_key.strip()
        else:
            api_key = get_user_api_key(self.user, provider)
        
        if not api_key:
            raise ValueError(f"Kein API-Key für {provider} konfiguriert.")
        
        # PDF-Text extrahieren
        book.file.seek(0)
        pages = self.extract_full_text(book.file)
        
        if not pages:
            raise ValueError("Konnte keinen Text aus dem PDF extrahieren.")
        
        # Text zusammenfügen mit Seitenmarkierungen
        full_text = ""
        for p in pages:
            full_text += f"\n\n[Seite {p['page']}]\n{p['text']}"
        
        # Text kürzen wenn zu lang
        if len(full_text) > 50000:
            full_text = full_text[:50000] + "\n\n[... Text gekürzt ...]"
        
        lang_name = "Deutsch" if language == 'de' else "English"
        
        system_prompt = f"""Du bist ein Experte für wissenschaftliche Texte. Erstelle eine ausführliche, strukturierte Zusammenfassung auf {lang_name}.

Antworte NUR mit diesem JSON-Format:
{{
    "short_summary": "Sehr kurze Zusammenfassung in 2-3 Sätzen (max. 50 Wörter). Worum geht es im Kern?",
    "full_summary": "Sehr ausführliche Zusammenfassung des gesamten Dokuments (800-1500 Wörter). Erkläre die wichtigsten Konzepte, Methoden, Ergebnisse und Schlussfolgerungen detailliert.",
    "sections": [
        {{
            "title": "Abschnittstitel",
            "text": "Detaillierte Zusammenfassung dieses Abschnitts (150-300 Wörter)",
            "start_page": 1,
            "end_page": 2
        }}
    ]
}}

Regeln:
1. NUR valides JSON ausgeben
2. short_summary: Kernaussage in 2-3 Sätzen für schnellen Überblick
3. full_summary: Ausführliche Zusammenfassung mit allen Details
4. Seitenzahlen aus [Seite X] Markierungen entnehmen
5. 5-10 Abschnitte erstellen je nach Dokumentstruktur
6. Wissenschaftlich korrekt aber verständlich zusammenfassen"""

        if provider == 'openai':
            return self._generate_summary_openai(full_text, system_prompt, api_key)
        elif provider == 'gemini':
            return self._generate_summary_gemini(full_text, system_prompt, api_key)
        else:
            return self._generate_summary_anthropic(full_text, system_prompt, api_key)

    def _generate_summary_openai(self, text, system_prompt, api_key):
        import json
        model = getattr(self.user, 'preferred_openai_model', None) or 'gpt-4o-mini'
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f'Dokument:\n\n{text}'}
                ],
                'temperature': 0.3,
                'max_tokens': 8000,
                'response_format': {'type': 'json_object'}
            },
            timeout=120
        )
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            return json.loads(content)
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI Fehler: {error_msg}")

    def _generate_summary_anthropic(self, text, system_prompt, api_key):
        import json
        import re
        model = getattr(self.user, 'preferred_anthropic_model', None) or 'claude-3-5-sonnet-20241022'
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 8000,
                'system': system_prompt,
                'messages': [
                    {'role': 'user', 'content': f'Dokument:\n\n{text}'}
                ]
            },
            timeout=180
        )
        
        if response.status_code == 200:
            content = response.json()['content'][0]['text']
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    return json.loads(json_match.group())
                raise ValueError("Kein gültiges JSON in Antwort")
        else:
            error_msg = response.json().get('error', {}).get('message', 'Fehler')
            raise Exception(f"Anthropic Fehler: {error_msg}")

    def _generate_summary_gemini(self, text, system_prompt, api_key):
        """Zusammenfassung mit Google Gemini generieren"""
        import json
        import re
        
        model = getattr(self.user, 'preferred_gemini_model', None) or 'gemini-2.0-flash'
        
        # Gemini API URL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        # Kombiniere System-Prompt und User-Prompt
        full_prompt = f"{system_prompt}\n\nDokument:\n\n{text}"
        
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': full_prompt}]}],
                'generationConfig': {
                    'temperature': 0.3,
                    'maxOutputTokens': 8000,
                }
            },
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['candidates'][0]['content']['parts'][0]['text']
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Versuche JSON aus der Antwort zu extrahieren
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    return json.loads(json_match.group())
                raise ValueError("Kein gültiges JSON in Gemini-Antwort")
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"Gemini Fehler: {error_msg}")

    def summarize_section(self, book, start_page, end_page, section_title, provider='openai', language='de'):
        """
        Generiert eine Zusammenfassung für einen bestimmten Abschnitt (Seitenbereich).
        """
        from naturmacher.utils.api_helpers import get_user_api_key
        import json
        
        # API-Key holen
        if provider == 'gemini':
            api_key = getattr(self.user, 'gemini_api_key', None)
            if api_key:
                api_key = api_key.strip()
        else:
            api_key = get_user_api_key(self.user, provider)
        
        if not api_key:
            raise ValueError(f"Kein API-Key für {provider} konfiguriert.")
        
        # Text nur von den relevanten Seiten extrahieren
        book.file.seek(0)
        pdf_bytes = book.file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        section_text = ""
        for page_num in range(start_page - 1, min(end_page, len(doc))):
            page = doc[page_num]
            text = page.get_text().strip()
            if text:
                section_text += f"\n\n[Seite {page_num + 1}]\n{text}"
        
        doc.close()
        
        if not section_text.strip():
            raise ValueError("Konnte keinen Text aus diesem Abschnitt extrahieren.")
        
        # Text kürzen wenn zu lang
        if len(section_text) > 15000:
            section_text = section_text[:15000] + "\n\n[... Text gekürzt ...]"
        
        lang_name = "Deutsch" if language == 'de' else "English"
        
        prompt = f"""Fasse den folgenden Abschnitt "{section_title}" auf {lang_name} zusammen.

Erstelle eine prägnante Zusammenfassung (100-200 Wörter) die die wichtigsten Punkte erklärt.
Antworte NUR mit dem Zusammenfassungstext, ohne JSON oder Formatierung.

Abschnitt:
{section_text}"""

        if provider == 'openai':
            return self._summarize_section_openai(prompt, api_key)
        elif provider == 'gemini':
            return self._summarize_section_gemini(prompt, api_key)
        else:
            return self._summarize_section_anthropic(prompt, api_key)

    def _summarize_section_openai(self, prompt, api_key):
        model = getattr(self.user, 'preferred_openai_model', None) or 'gpt-4o-mini'
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 1000
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI Fehler: {error_msg}")

    def _summarize_section_anthropic(self, prompt, api_key):
        model = getattr(self.user, 'preferred_anthropic_model', None) or 'claude-3-5-sonnet-20241022'
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Fehler')
            raise Exception(f"Anthropic Fehler: {error_msg}")

    def _summarize_section_gemini(self, prompt, api_key):
        model = getattr(self.user, 'preferred_gemini_model', None) or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {
                    'temperature': 0.3,
                    'maxOutputTokens': 1000,
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"Gemini Fehler: {error_msg}")


class PDFChatService:
    """Service für Chat mit PDF-Dokumenten"""

    def __init__(self, user):
        self.user = user

    def get_pdf_context(self, book, max_chars=30000):
        """
        Extrahiert Text aus dem PDF für Chat-Kontext.
        
        Args:
            book: PDFBook-Instanz
            max_chars: Maximale Zeichen für Kontext
            
        Returns:
            str: Extrahierter PDF-Text
        """
        try:
            book.file.seek(0)
            pdf_bytes = book.file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            full_text = ""
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                if text:
                    full_text += f"\n\n[Seite {i + 1}]\n{text}"
                
                # Abbrechen wenn max_chars erreicht
                if len(full_text) > max_chars:
                    full_text = full_text[:max_chars] + "\n\n[... Text gekürzt ...]"
                    break
            
            doc.close()
            return full_text
        except Exception as e:
            print(f"Fehler bei PDF-Textextraktion: {e}")
            return ""

    def chat(self, book, question, conversation_history=None, provider='openai'):
        """
        Beantwortet eine Frage zum PDF-Dokument.
        
        Args:
            book: PDFBook-Instanz
            question: Die Frage des Benutzers
            conversation_history: Liste von vorherigen Nachrichten [{"role": "user/assistant", "content": "..."}]
            provider: 'openai', 'anthropic' oder 'gemini'
            
        Returns:
            str: Antwort auf die Frage
        """
        from naturmacher.utils.api_helpers import get_user_api_key
        
        # API-Key holen
        if provider == 'gemini':
            api_key = getattr(self.user, 'gemini_api_key', None)
            if api_key:
                api_key = api_key.strip()
        else:
            api_key = get_user_api_key(self.user, provider)
        
        if not api_key:
            raise ValueError(f"Kein API-Key für {provider} konfiguriert.")
        
        # PDF-Text extrahieren
        pdf_context = self.get_pdf_context(book)
        
        if not pdf_context:
            raise ValueError("Konnte keinen Text aus dem PDF extrahieren.")
        
        # Zusammenfassung einbeziehen wenn vorhanden
        summary_context = ""
        try:
            if hasattr(book, 'summary') and book.summary:
                summary = book.summary
                if summary.full_summary:
                    summary_context = f"\n\nZusammenfassung des Dokuments:\n{summary.full_summary}"
        except Exception:
            pass
        
        if provider == 'openai':
            return self._chat_openai(pdf_context, summary_context, question, conversation_history, api_key)
        elif provider == 'gemini':
            return self._chat_gemini(pdf_context, summary_context, question, conversation_history, api_key)
        else:
            return self._chat_anthropic(pdf_context, summary_context, question, conversation_history, api_key)

    def _chat_openai(self, pdf_context, summary_context, question, conversation_history, api_key):
        """Chat mit OpenAI API"""
        model = getattr(self.user, 'preferred_openai_model', None) or 'gpt-4o-mini'
        
        system_prompt = f"""Du bist ein hilfreicher Assistent, der Fragen zu einem PDF-Dokument beantwortet.
Beantworte die Fragen basierend auf dem Dokumentinhalt. Wenn die Antwort nicht im Dokument steht, sage das ehrlich.
Antworte auf Deutsch, klar und präzise.
{summary_context}

Dokumentinhalt:
{pdf_context}"""

        messages = [{'role': 'system', 'content': system_prompt}]
        
        # Vorherige Konversation hinzufügen (max. letzte 10 Nachrichten)
        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({
                    'role': msg.get('role', 'user'),
                    'content': msg.get('content', '')
                })
        
        messages.append({'role': 'user', 'content': question})
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': messages,
                'temperature': 0.5,
                'max_tokens': 1500
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"OpenAI Fehler: {error_msg}")

    def _chat_anthropic(self, pdf_context, summary_context, question, conversation_history, api_key):
        """Chat mit Anthropic Claude API"""
        model = getattr(self.user, 'preferred_anthropic_model', None) or 'claude-3-5-sonnet-20241022'
        
        system_prompt = f"""Du bist ein hilfreicher Assistent, der Fragen zu einem PDF-Dokument beantwortet.
Beantworte die Fragen basierend auf dem Dokumentinhalt. Wenn die Antwort nicht im Dokument steht, sage das ehrlich.
Antworte auf Deutsch, klar und präzise.
{summary_context}

Dokumentinhalt:
{pdf_context}"""

        messages = []
        
        # Vorherige Konversation hinzufügen
        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({
                    'role': msg.get('role', 'user'),
                    'content': msg.get('content', '')
                })
        
        messages.append({'role': 'user', 'content': question})
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 1500,
                'system': system_prompt,
                'messages': messages
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Fehler')
            raise Exception(f"Anthropic Fehler: {error_msg}")

    def _chat_gemini(self, pdf_context, summary_context, question, conversation_history, api_key):
        """Chat mit Google Gemini API"""
        model = getattr(self.user, 'preferred_gemini_model', None) or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        # Kontext und Konversation zusammenbauen
        context_text = f"""Du bist ein hilfreicher Assistent, der Fragen zu einem PDF-Dokument beantwortet.
Beantworte die Fragen basierend auf dem Dokumentinhalt. Wenn die Antwort nicht im Dokument steht, sage das ehrlich.
Antworte auf Deutsch, klar und präzise.
{summary_context}

Dokumentinhalt:
{pdf_context}"""
        
        # Vorherige Konversation als Text
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = "Nutzer" if msg.get('role') == 'user' else "Assistent"
                history_text += f"\n{role}: {msg.get('content', '')}"
        
        full_prompt = f"{context_text}\n\nBisherige Konversation:{history_text}\n\nNutzer: {question}\n\nAssistent:"
        
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': full_prompt}]}],
                'generationConfig': {
                    'temperature': 0.5,
                    'maxOutputTokens': 1500,
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            error_msg = response.json().get('error', {}).get('message', 'Unbekannter Fehler')
            raise Exception(f"Gemini Fehler: {error_msg}")
