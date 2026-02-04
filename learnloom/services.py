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
