"""
Image Service für BlogPrep

Verantwortlich für:
- Titelbild generieren
- Abschnittsbilder generieren
- Diagramme als Bilder generieren
"""

import logging
import base64
import requests
import time
from typing import Dict, Optional, Any
from io import BytesIO
from django.core.files.base import ContentFile

# Optionale Imports
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Import der gemeinsamen Fehlerbehandlung
from .content_service import _get_user_friendly_error


class ImageService:
    """Service für KI-gestützte Bildgenerierung"""

    # Google API Base URL
    GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Verfügbare Modelle pro Provider (Stand: Dezember 2025)
    # Nano Banana = Gemini 2.5 Flash, Nano Banana Pro = Gemini 3 Pro
    PROVIDER_MODELS = {
        'gemini': {
            'gemini-3-pro-image-preview': 'Nano Banana Pro (Beste Qualität)',
            'gemini-2.5-flash-image': 'Nano Banana (Schnell & Günstig)',
            'gemini-2.0-flash-exp-image-generation': 'Gemini 2.0 Flash (Fallback)',
        },
        'dalle': {
            'gpt-image-1': 'GPT Image 1 (Beste Qualität)',
            'dall-e-3': 'DALL-E 3',
        },
    }

    def __init__(self, user, settings=None):
        """
        Initialisiert den Image Service.

        Args:
            user: Django User Objekt mit API-Keys
            settings: Optional BlogPrepSettings Objekt
        """
        self.user = user
        self.settings = settings

        # Provider und Modell aus Settings oder Defaults
        if settings:
            self.provider = settings.image_provider
            self.model = settings.image_model
            # Fallback für alte/ungültige Imagen-Modelle
            if 'imagen' in self.model.lower():
                logger.warning(f"Imagen model {self.model} nicht verfügbar, verwende Nano Banana stattdessen")
                self.model = 'gemini-2.5-flash-image'
        else:
            self.provider = 'gemini'
            self.model = 'gemini-2.5-flash-image'  # Nano Banana als Standard

        # Clients initialisieren
        self._init_clients()

    def _init_clients(self):
        """Initialisiert die API-Clients basierend auf Provider"""
        self.openai_client = None
        self.google_api_key = None
        self.ideogram_api_key = None

        if self.provider == 'dalle' and OPENAI_AVAILABLE and self.user.openai_api_key:
            self.openai_client = OpenAI(api_key=self.user.openai_api_key)
        elif self.provider == 'gemini' and self.user.gemini_api_key:
            self.google_api_key = self.user.gemini_api_key
        elif self.provider == 'ideogram' and hasattr(self.user, 'ideogram_api_key'):
            self.ideogram_api_key = self.user.ideogram_api_key

    def generate_title_image(self, keyword: str, blog_summary: str = '') -> Dict:
        """
        Generiert ein Titelbild für den Blogbeitrag.

        Args:
            keyword: Das Hauptkeyword
            blog_summary: Kurze Zusammenfassung des Blog-Inhalts

        Returns:
            Dict mit success, image_data (base64), prompt
        """
        prompt = self._create_blog_image_prompt(keyword, blog_summary, is_title=True)

        return self._generate_image(prompt, width=1200, height=630)

    def generate_section_image(self, section_text: str, keyword: str) -> Dict:
        """
        Generiert ein Bild für einen Blog-Abschnitt.

        Args:
            section_text: Der Text des Abschnitts (gekürzt)
            keyword: Das Hauptkeyword

        Returns:
            Dict mit success, image_data (base64), prompt
        """
        prompt = self._create_blog_image_prompt(keyword, section_text[:500], is_title=False)

        return self._generate_image(prompt, width=800, height=600)

    def generate_diagram_image(self, diagram_type: str, diagram_data: Dict, keyword: str) -> Dict:
        """
        Generiert ein Diagramm als Bild.

        Args:
            diagram_type: Art des Diagramms (bar, pie, flow, etc.)
            diagram_data: Daten für das Diagramm
            keyword: Kontext-Keyword

        Returns:
            Dict mit success, image_data (base64), prompt
        """
        prompt = self._create_diagram_prompt(diagram_type, diagram_data, keyword)

        return self._generate_image(prompt, width=1000, height=700)

    def _create_blog_image_prompt(self, keyword: str, context: str, is_title: bool = False) -> str:
        """Erstellt einen optimierten Prompt für Blog-Bilder"""
        image_type = "Titelbild" if is_title else "illustrierendes Bild"

        prompt = f"""Erstelle ein professionelles {image_type} für einen Blogbeitrag zum Thema "{keyword}".

KONTEXT: {context[:300] if context else 'Informativer Blogbeitrag'}

STIL-ANFORDERUNGEN:
- Professionelles, modernes Design
- Klare, ansprechende Komposition
- Helle, freundliche Farbpalette
- Keine Textüberlagerungen
- Hochwertige, stock-photo-artige Qualität
- Passend für ein Business-Blog

Das Bild soll informativ und einladend wirken, ohne aufdringlich zu sein."""

        return prompt

    def _create_diagram_prompt(self, diagram_type: str, diagram_data: Dict, keyword: str) -> str:
        """Erstellt einen spezifischen Prompt für jeden Diagrammtyp"""
        title = diagram_data.get('title', f'Diagramm zu {keyword}')
        subtitle = diagram_data.get('subtitle', '')
        labels = diagram_data.get('labels', [])
        values = diagram_data.get('values', [])
        value_labels = diagram_data.get('value_labels', [])
        steps = diagram_data.get('steps', [])
        center_value = diagram_data.get('center_value', '')
        key_insight = diagram_data.get('key_insight', '')
        colors = diagram_data.get('colors', [])

        # Basis-Stil für alle Diagramme
        base_style = """
DESIGN-REGELN:
- Modernes, cleanes Flat-Design
- Gut lesbare Schriften (min. 14pt)
- Professionelle Farbpalette
- Weißer/heller Hintergrund
- Kein 3D, keine Schatten
- Hoher Kontrast für Lesbarkeit"""

        # Spezifische Prompts für jeden Diagrammtyp
        if diagram_type in ['bar_vertical', 'bar']:
            data_str = ', '.join([f'"{l}": {v}' for l, v in zip(labels[:6], values[:6])]) if labels and values else ''
            prompt = f"""Erstelle ein VERTIKALES BALKENDIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

DATEN (Balken von links nach rechts):
{data_str if data_str else ', '.join(labels[:6])}

LAYOUT:
- Vertikale Balken nebeneinander
- Y-Achse mit Werten beschriftet
- X-Achse mit Kategorien beschriftet
- Jeder Balken hat eine eigene Farbe
- Werte über oder in den Balken anzeigen
{base_style}"""

        elif diagram_type == 'bar_horizontal':
            data_str = ', '.join([f'"{l}": {v}' for l, v in zip(labels[:6], values[:6])]) if labels and values else ''
            prompt = f"""Erstelle ein HORIZONTALES BALKENDIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

DATEN (Balken von oben nach unten):
{data_str if data_str else ', '.join(labels[:6])}

LAYOUT:
- Horizontale Balken untereinander
- Kategorien links vom Balken
- Werte rechts vom Balken oder am Balkenende
- Längster Balken oben (Ranking-Stil)
- Unterschiedliche Farben oder Farbverlauf
{base_style}"""

        elif diagram_type == 'pie':
            data_str = ', '.join([f'{l}: {v}%' for l, v in zip(labels[:5], values[:5])]) if labels and values else ''
            prompt = f"""Erstelle ein KREISDIAGRAMM (Pie Chart) für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

SEGMENTE:
{data_str if data_str else ', '.join(labels[:5])}

LAYOUT:
- Klar unterscheidbare Segmente
- Prozentangaben IN oder NEBEN den Segmenten
- Legende mit Kategorien und Farben
- Größtes Segment beginnt bei 12 Uhr
- Maximal 5-6 Segmente für Übersichtlichkeit
{base_style}"""

        elif diagram_type == 'donut':
            prompt = f"""Erstelle ein RINGDIAGRAMM (Donut Chart) für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

{f'ZENTRALER WERT IN DER MITTE: {center_value}' if center_value else ''}

SEGMENTE:
{', '.join([f'{l}: {v}%' for l, v in zip(labels[:5], values[:5])]) if labels and values else ', '.join(labels[:5])}

LAYOUT:
- Ring mit großem Loch in der Mitte
- Hauptkennzahl groß in der Mitte
- Prozentangaben bei den Segmenten
- Legende unterhalb oder rechts
- Kontrastreiche Farben für Segmente
{base_style}"""

        elif diagram_type in ['line', 'area']:
            chart_type = "LINIENDIAGRAMM" if diagram_type == 'line' else "FLÄCHENDIAGRAMM"
            prompt = f"""Erstelle ein {chart_type} für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

DATENPUNKTE (X-Achse): {', '.join(str(l) for l in labels[:8])}
WERTE (Y-Achse): {', '.join(str(v) for v in values[:8]) if values else 'Aufsteigender Trend'}

LAYOUT:
- Klare Linie{'n' if diagram_type == 'line' else ' mit gefüllter Fläche darunter'}
- X-Achse: Zeitpunkte/Kategorien
- Y-Achse: Werte mit Skalierung
- Datenpunkte als kleine Kreise markiert
- {'Mehrere Linien in verschiedenen Farben' if diagram_type == 'line' else 'Transparente Füllung unter der Linie'}
- Grid-Linien zur Orientierung
{base_style}"""

        elif diagram_type == 'timeline':
            events = steps if steps else labels
            prompt = f"""Erstelle einen ZEITSTRAHL (Timeline) für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

EREIGNISSE/MEILENSTEINE:
{chr(10).join([f'{i+1}. {e}' for i, e in enumerate(events[:7])])}

LAYOUT:
- Horizontale oder vertikale Zeitachse
- Punkte/Marker für jedes Ereignis
- Ereignisbeschreibungen neben den Markern
- Verbindungslinie zwischen Ereignissen
- Optionale Jahreszahlen/Daten
- Abwechselnde Positionen (oben/unten oder links/rechts)
{base_style}"""

        elif diagram_type == 'flow':
            flow_steps = steps if steps else labels
            prompt = f"""Erstelle ein FLUSSDIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

PROZESS-SCHRITTE:
{chr(10).join([f'{i+1}. {s}' for i, s in enumerate(flow_steps[:6])])}

LAYOUT:
- Rechteckige Boxen für jeden Schritt
- Pfeile zeigen den Fluss/die Richtung
- Klare Beschriftung in jeder Box
- Von oben nach unten ODER links nach rechts
- Optionale Entscheidungsrauten (Ja/Nein)
- Einheitliche Box-Größen
{base_style}"""

        elif diagram_type == 'funnel':
            funnel_stages = steps if steps else labels
            prompt = f"""Erstelle ein TRICHTERDIAGRAMM (Funnel) für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

STUFEN (von oben/breit nach unten/schmal):
{chr(10).join([f'{i+1}. {s}' + (f' ({values[i]}%)' if i < len(values) else '') for i, s in enumerate(funnel_stages[:5])])}

LAYOUT:
- Trapezförmige Segmente
- Oberstes Segment am breitesten
- Unterstes Segment am schmalsten
- Jedes Segment beschriftet
- Prozent/Zahlen in den Segmenten
- Unterschiedliche Farben pro Stufe
{base_style}"""

        elif diagram_type == 'steps':
            process_steps = steps if steps else labels
            prompt = f"""Erstelle ein SCHRITTE-DIAGRAMM (Step-by-Step) für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

SCHRITTE:
{chr(10).join([f'Schritt {i+1}: {s}' for i, s in enumerate(process_steps[:6])])}

LAYOUT:
- Nummerierte Schritte in Kreisen oder Badges
- Verbindungslinien oder Pfeile zwischen Schritten
- Kurze Beschreibung unter/neben jedem Schritt
- Horizontal oder vertikal angeordnet
- Fortschritts-Stil (1→2→3→4)
- Icons optional in den Schritt-Markern
{base_style}"""

        elif diagram_type == 'gauge':
            prompt = f"""Erstelle ein TACHO/GAUGE-DIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

HAUPTWERT: {center_value if center_value else values[0] if values else '75%'}
SKALA: {', '.join(str(l) for l in labels[:5]) if labels else '0-100'}

LAYOUT:
- Halbkreis-Tacho oder Vollkreis-Gauge
- Zeiger/Nadel auf dem aktuellen Wert
- Farbzonen (rot/gelb/grün)
- Großer Wert in der Mitte
- Skala-Markierungen am Rand
- Klare Beschriftung der Bereiche
{base_style}"""

        elif diagram_type == 'radar':
            prompt = f"""Erstelle ein RADAR/SPINNENDIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

KRITERIEN (Achsen): {', '.join(labels[:6])}
WERTE: {', '.join([str(v) for v in values[:6]]) if values else 'Verschiedene Ausprägungen'}

LAYOUT:
- Sternförmiges Netz mit 5-6 Achsen
- Jede Achse = ein Kriterium
- Datenpunkte verbunden zu Polygon
- Skala von Mitte (0) nach außen (max)
- Beschriftung an jeder Achsenspitze
- Optional: mehrere Datensätze überlagert
{base_style}"""

        elif diagram_type == 'comparison_table':
            prompt = f"""Erstelle eine VISUELLE VERGLEICHSTABELLE für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

KATEGORIEN ZUM VERGLEICH: {', '.join(labels[:4])}
{f'KRITERIEN: {", ".join(steps[:5])}' if steps else ''}

LAYOUT:
- Tabellenformat mit klaren Spalten
- Header-Zeile hervorgehoben
- Checkmarks/X für Ja/Nein Kriterien
- Alternierend eingefärbte Zeilen
- Icons statt Text wo möglich
- Gewinnermarkierung optional
{base_style}"""

        elif diagram_type == 'checklist':
            items = steps if steps else labels
            prompt = f"""Erstelle eine VISUELLE CHECKLISTE für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

CHECKLISTEN-PUNKTE:
{chr(10).join([f'☑ {item}' for item in items[:8]])}

LAYOUT:
- Aufgelistete Items mit Checkboxen
- Grüne Häkchen für erledigte Punkte
- Klare, gut lesbare Beschriftungen
- Nummerierung optional
- Gruppierung nach Kategorien möglich
- Kompaktes, scanningfreundliches Design
{base_style}"""

        elif diagram_type == 'matrix':
            prompt = f"""Erstelle eine 2x2 MATRIX für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

QUADRANTEN: {', '.join(labels[:4]) if labels else 'Vier Kategorien'}
X-ACHSE: {diagram_data.get('axis_label_x', 'Niedrig → Hoch')}
Y-ACHSE: {diagram_data.get('axis_label_y', 'Niedrig → Hoch')}

LAYOUT:
- 2x2 Raster mit 4 Quadranten
- Achsenbeschriftungen
- Jeder Quadrant farblich unterschieden
- Titel/Label in jedem Quadranten
- Beispiele/Items in den Quadranten
- Klare Trennlinien
{base_style}"""

        elif diagram_type == 'icons_grid':
            items = steps if steps else labels
            prompt = f"""Erstelle ein ICON-RASTER für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

FEATURES/VORTEILE:
{chr(10).join([f'• {item}' for item in items[:6]])}

LAYOUT:
- Raster mit Icons und Beschriftungen
- 2-3 Spalten, 2-3 Zeilen
- Großes Icon pro Feature
- Kurzer Text unter jedem Icon
- Einheitliche Icon-Größe
- Klare visuelle Hierarchie
{base_style}"""

        elif diagram_type == 'stacked_bar':
            prompt = f"""Erstelle ein GESTAPELTES BALKENDIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

KATEGORIEN: {', '.join(labels[:4])}
SEGMENTE PRO BALKEN: {', '.join(steps[:4]) if steps else 'Teil A, Teil B, Teil C'}

LAYOUT:
- Horizontale oder vertikale gestapelte Balken
- Jeder Balken zeigt Zusammensetzung
- Farbcodierte Segmente
- Legende für Segment-Farben
- Summe = 100% pro Balken
- Beschriftung der Segmente
{base_style}"""

        else:
            # Fallback für unbekannte Typen
            prompt = f"""Erstelle ein informatives DIAGRAMM für einen Business-Blog.

TITEL: {title}
{f'UNTERTITEL: {subtitle}' if subtitle else ''}

DATENPUNKTE: {', '.join(str(l) for l in labels[:6]) if labels else 'Verschiedene Kategorien'}

LAYOUT:
- Klares, übersichtliches Design
- Gut lesbare Beschriftungen
- Professionelle Darstellung
{base_style}"""

        # Füge key_insight hinzu wenn vorhanden
        if key_insight:
            prompt += f"\n\nHAUPTAUSSAGE: {key_insight}"

        return prompt

    def _generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> Dict:
        """
        Generiert ein Bild mit dem konfigurierten Provider.

        Returns:
            Dict mit success, image_data (base64), prompt, error
        """
        start_time = time.time()

        try:
            if self.provider == 'dalle' and self.openai_client:
                result = self._generate_with_dalle(prompt, width, height)
            elif self.provider == 'gemini' and self.google_api_key:
                result = self._generate_with_google(prompt, width, height)
            elif self.provider == 'ideogram' and self.ideogram_api_key:
                result = self._generate_with_ideogram(prompt, width, height)
            else:
                return {
                    'success': False,
                    'error': f'API-Key für {self.provider} nicht konfiguriert',
                    'prompt': prompt
                }

            result['prompt'] = prompt
            result['duration'] = time.time() - start_time
            return result

        except Exception as e:
            logger.error(f"Image generation error ({self.provider}): {e}")
            user_friendly_error = _get_user_friendly_error(e, self.provider)
            return {
                'success': False,
                'error': user_friendly_error,
                'prompt': prompt
            }

    def _generate_with_dalle(self, prompt: str, width: int, height: int) -> Dict:
        """Generiert Bild mit OpenAI DALL-E oder GPT Image 1"""
        # Größen bestimmen
        if width >= 1792 or height >= 1792:
            size = "1792x1024" if width > height else "1024x1792"
        else:
            size = "1024x1024"

        # GPT Image 1 vs DALL-E 3 haben unterschiedliche Parameter
        if self.model == 'gpt-image-1':
            # GPT Image 1: kein response_format, gibt URL zurück
            response = self.openai_client.images.generate(
                model=self.model,
                prompt=prompt,
                size=size,
                n=1
            )

            # Prüfe ob Daten vorhanden
            if not response.data or len(response.data) == 0:
                return {
                    'success': False,
                    'error': 'Keine Bilddaten von OpenAI erhalten',
                    'model_used': self.model
                }

            # URL abrufen und zu Base64 konvertieren
            image_url = response.data[0].url

            if not image_url:
                # Falls URL None ist, versuche b64_json
                if hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
                    image_data = response.data[0].b64_json
                else:
                    return {
                        'success': False,
                        'error': 'Keine Bild-URL von OpenAI erhalten. Möglicherweise ist das Modell für Ihren Account nicht verfügbar.',
                        'model_used': self.model
                    }
            else:
                img_response = requests.get(image_url, timeout=60)

                if img_response.status_code == 200:
                    image_data = base64.b64encode(img_response.content).decode('utf-8')
                else:
                    return {
                        'success': False,
                        'error': f'Fehler beim Herunterladen des Bildes: {img_response.status_code}',
                        'model_used': self.model
                    }
        else:
            # DALL-E 3: unterstützt b64_json
            response = self.openai_client.images.generate(
                model=self.model,
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
                response_format="b64_json"
            )

            if not response.data or len(response.data) == 0:
                return {
                    'success': False,
                    'error': 'Keine Bilddaten von OpenAI erhalten',
                    'model_used': self.model
                }

            image_data = response.data[0].b64_json

        return {
            'success': True,
            'image_data': image_data,
            'model_used': self.model
        }

    def _generate_with_google(self, prompt: str, width: int, height: int) -> Dict:
        """Generiert Bild mit Google Gemini/Imagen"""
        # Aspect Ratio bestimmen
        ratio = width / height
        if ratio > 1.3:
            aspect_ratio = "16:9"
        elif ratio < 0.77:
            aspect_ratio = "9:16"
        elif ratio > 1.1:
            aspect_ratio = "4:3"
        elif ratio < 0.9:
            aspect_ratio = "3:4"
        else:
            aspect_ratio = "1:1"

        # Routing basierend auf Modelltyp
        if 'imagen' in self.model:
            return self._generate_with_imagen(prompt, aspect_ratio)
        elif 'gemini' in self.model:
            # Gemini 2.5 Flash Image oder andere Gemini-Modelle
            return self._generate_with_gemini_native(prompt, aspect_ratio)
        else:
            # Fallback zu Gemini Native
            return self._generate_with_gemini_native(prompt, aspect_ratio)

    def _generate_with_imagen(self, prompt: str, aspect_ratio: str) -> Dict:
        """Generiert Bild mit Google Imagen über die Gemini API"""
        # Imagen 3 verwendet generateImages Endpunkt
        url = f"{self.GOOGLE_BASE_URL}/models/{self.model}:generateImages"

        payload = {
            "prompt": prompt,
            "config": {
                "numberOfImages": 1,
                "aspectRatio": aspect_ratio,
                "personGeneration": "ALLOW_ADULT",
                "outputOptions": {
                    "mimeType": "image/png"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.google_api_key
        }

        response = requests.post(url, json=payload, headers=headers, timeout=180)

        if response.status_code != 200:
            try:
                error_detail = response.json().get('error', {}).get('message', response.text)
            except:
                error_detail = response.text
            return {
                'success': False,
                'error': f"Imagen API Error: {error_detail}",
                'model_used': self.model
            }

        data = response.json()

        # Imagen 3 Response Format
        generated_images = data.get('generatedImages', [])
        if generated_images and 'image' in generated_images[0]:
            image_data = generated_images[0]['image'].get('imageBytes')
            if image_data:
                return {
                    'success': True,
                    'image_data': image_data,
                    'model_used': self.model
                }

        # Fallback für altes Format
        predictions = data.get('predictions', [])
        if predictions and 'bytesBase64Encoded' in predictions[0]:
            return {
                'success': True,
                'image_data': predictions[0]['bytesBase64Encoded'],
                'model_used': self.model
            }

        return {
            'success': False,
            'error': f'Keine Bilddaten in der Antwort: {str(data)[:200]}',
            'model_used': self.model
        }

    def _generate_with_gemini_native(self, prompt: str, aspect_ratio: str) -> Dict:
        """Generiert Bild mit Gemini 2.0 Flash Image Generation"""
        url = f"{self.GOOGLE_BASE_URL}/models/{self.model}:generateContent"

        # Bild-Prompt optimieren
        image_prompt = f"""Generate a professional, high-quality image for a blog post.

Topic: {prompt}

Style requirements:
- Professional, modern design
- Clear, appealing composition
- Bright, friendly color palette
- No text overlays
- High-quality, stock-photo-like quality
- Suitable for a business blog

Create the image now."""

        payload = {
            "contents": [{
                "parts": [{"text": image_prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.google_api_key
        }

        logger.info(f"Calling Gemini Image API: {url}")
        logger.info(f"Model: {self.model}")

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=180)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            user_friendly_error = _get_user_friendly_error(e, 'gemini')
            return {
                'success': False,
                'error': user_friendly_error,
                'model_used': self.model
            }

        logger.info(f"Response status: {response.status_code}")

        if response.status_code != 200:
            try:
                error_data = response.json()
                error_detail = error_data.get('error', {}).get('message', response.text)
            except:
                error_detail = response.text[:500]
            logger.error(f"Gemini API Error: {error_detail}")
            return {
                'success': False,
                'error': f"Gemini API Error ({response.status_code}): {error_detail}",
                'model_used': self.model
            }

        try:
            data = response.json()
        except Exception as e:
            logger.error(f"JSON parse error: {e}")
            return {
                'success': False,
                'error': f"JSON parse error: {str(e)}",
                'model_used': self.model
            }

        # Suche nach Bilddaten in der Antwort
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'inlineData' in part:
                    image_data = part['inlineData'].get('data')
                    if image_data:
                        logger.info("Image generated successfully")
                        return {
                            'success': True,
                            'image_data': image_data,
                            'model_used': self.model
                        }

        logger.error(f"No image in response: {str(data)[:300]}")
        return {
            'success': False,
            'error': f'Keine Bilddaten in der Gemini-Antwort. Response: {str(data)[:200]}',
            'model_used': self.model
        }

    def _generate_with_ideogram(self, prompt: str, width: int, height: int) -> Dict:
        """Generiert Bild mit Ideogram"""
        # Aspect Ratio mapping
        ratio = width / height
        if ratio > 1.3:
            aspect_ratio = "ASPECT_16_9"
        elif ratio < 0.77:
            aspect_ratio = "ASPECT_9_16"
        elif ratio > 1.1:
            aspect_ratio = "ASPECT_4_3"
        elif ratio < 0.9:
            aspect_ratio = "ASPECT_3_4"
        else:
            aspect_ratio = "ASPECT_1_1"

        url = "https://api.ideogram.ai/generate"

        payload = {
            "image_request": {
                "prompt": prompt,
                "model": self.model,
                "aspect_ratio": aspect_ratio,
                "style_type": "REALISTIC"
            }
        }

        headers = {
            "Api-Key": self.ideogram_api_key,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=180)

        if response.status_code != 200:
            return {
                'success': False,
                'error': f"Ideogram API Error: {response.text}",
                'model_used': self.model
            }

        data = response.json()
        images = data.get('data', [])

        if images and 'url' in images[0]:
            # Lade Bild herunter und konvertiere zu base64
            img_response = requests.get(images[0]['url'], timeout=30)
            if img_response.status_code == 200:
                image_data = base64.b64encode(img_response.content).decode('utf-8')
                return {
                    'success': True,
                    'image_data': image_data,
                    'model_used': self.model
                }

        return {
            'success': False,
            'error': 'Keine Bilddaten von Ideogram erhalten',
            'model_used': self.model
        }

    def save_image_to_field(self, image_data: str, field, filename: str) -> bool:
        """
        Speichert Base64-Bilddaten in ein Django ImageField.

        Args:
            image_data: Base64-kodierte Bilddaten
            field: Django ImageField
            filename: Dateiname ohne Extension

        Returns:
            bool: Erfolg
        """
        try:
            # Dekodiere Base64
            image_bytes = base64.b64decode(image_data)

            # Öffne mit PIL um Format zu bestimmen (falls verfügbar)
            if PIL_AVAILABLE:
                img = Image.open(BytesIO(image_bytes))
                img_format = img.format or 'PNG'
                extension = img_format.lower()
            else:
                extension = 'png'

            # Speichere in Field
            full_filename = f"{filename}.{extension}"

            field.save(full_filename, ContentFile(image_bytes), save=False)
            return True

        except Exception as e:
            logger.error(f"Error saving image to field: {e}")
            return False

    def save_image_to_media(self, image_data: str, filename: str) -> str:
        """
        Speichert Base64-Bilddaten als Datei im Media-Verzeichnis.

        Args:
            image_data: Base64-kodierte Bilddaten
            filename: Dateiname ohne Extension

        Returns:
            str: Relativer URL-Pfad zur Datei oder leerer String bei Fehler
        """
        from django.core.files.storage import default_storage
        import os

        try:
            # Dekodiere Base64
            image_bytes = base64.b64decode(image_data)

            # Bestimme Extension
            if PIL_AVAILABLE:
                img = Image.open(BytesIO(image_bytes))
                img_format = img.format or 'PNG'
                extension = img_format.lower()
            else:
                extension = 'png'

            # Erstelle Dateipfad
            full_filename = f"blogprep/section_images/{filename}.{extension}"

            # Speichere Datei
            saved_path = default_storage.save(full_filename, ContentFile(image_bytes))

            # Gib URL zurück
            return default_storage.url(saved_path)

        except Exception as e:
            logger.error(f"Error saving image to media: {e}")
            return ''
