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
2. Seitenzahlen aus [Seite X] Markierungen entnehmen
3. 5-10 Abschnitte erstellen je nach Dokumentstruktur
4. Wissenschaftlich korrekt aber verständlich zusammenfassen
5. Wichtige Details, Zahlen und Erkenntnisse einbeziehen
6. Bei Studien: Methodik, Stichprobe, Ergebnisse und Limitationen erwähnen"""

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
