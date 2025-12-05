import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class PinAIService:
    """Service für KI-gesteuerte Pin-Generierung mit OpenAI GPT"""

    def __init__(self, user):
        self.user = user
        self.api_key = user.openai_api_key
        self.model = user.preferred_openai_model or 'gpt-4o-mini'

        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def generate_realistic_background_description(self, user_input: str, project_keywords: str = '') -> dict:
        """
        Generiert eine fotorealistische Hintergrund-Beschreibung aus Stichwörtern.

        Fokus auf:
        - Fotorealismus (echte Fotos, keine Illustrationen)
        - Natürliche Farben und Beleuchtung
        - Realistische Schatten und Tiefenschärfe
        - Echte Menschen und authentische Szenarien
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            prompt = f"""Du bist ein Experte für fotorealistische Bildgenerierung.
Erstelle aus den folgenden Stichwörtern eine detaillierte Beschreibung für ein FOTOREALISTISCHES Bild.

STICHWÖRTER VOM NUTZER: {user_input}
THEMA/KEYWORDS DES PINS: {project_keywords or 'Nicht angegeben'}

═══════════════════════════════════════════════════════════════

ERSTELLE EINE BESCHREIBUNG DIE FOLGENDES GARANTIERT:

1. FOTOREALISMUS (WICHTIGSTE REGEL!):
   - Das Bild soll wie ein echtes Foto aussehen
   - KEINE Illustrationen, Cartoons oder künstlerische Stile
   - Schreibe explizit: "photorealistic", "real photograph", "DSLR quality"

2. NATÜRLICHE BELEUCHTUNG:
   - Beschreibe die Lichtquelle (Tageslicht, goldene Stunde, Studioblitz)
   - Natürliche, weiche Schatten
   - Realistische Lichtreflexionen

3. ECHTE FARBEN:
   - Keine übersättigten oder künstlichen Farben
   - Natürliche Hauttöne bei Menschen
   - Authentische Materialfarben

4. TIEFENSCHÄRFE & FOKUS:
   - Beschreibe Vordergrund, Mittelgrund, Hintergrund
   - Bokeh-Effekt im Hintergrund wenn sinnvoll
   - Klarer Fokuspunkt

5. AUTHENTIZITÄT:
   - Echte Menschen (keine perfekten Models, authentische Posen)
   - Realistische Szenarien aus dem Alltag
   - Glaubwürdige Umgebungen

═══════════════════════════════════════════════════════════════

FORMAT DER BESCHREIBUNG:
- Maximal 3-4 Sätze
- Englisch (für beste Bildgenerierung)
- Beginne mit "Photorealistic photograph of..."
- Inkludiere Kamera-Details wenn passend (z.B. "shot with 85mm lens, f/1.8")

Antworte NUR mit der Beschreibung, ohne Erklärungen."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Experte für fotorealistische Bildgenerierung. Du schreibst Prompts die zu echten, authentischen Fotos führen."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )

            description = response.choices[0].message.content.strip()

            return {
                'success': True,
                'description': description
            }

        except Exception as e:
            logger.error(f"Error generating background description: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_overlay_text(self, keywords: str) -> dict:
        """Generiert einen catchy, kurzen Pin-Text aus Keywords via GPT"""
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            prompt = f"""Du bist ein Experte für Pinterest Marketing. Erstelle einen kurzen, catchy Text für ein Pinterest Pin-Bild.

Keywords: {keywords}

Anforderungen:
- Maximal 6-8 Wörter
- Aufmerksamkeitsstark und klickfördernd
- Gut lesbar als Overlay auf einem Bild
- Nutze Action-Wörter oder Fragen
- Keine Hashtags, nur der reine Text

Antworte NUR mit dem Text, ohne Anführungszeichen oder Erklärungen."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest Marketing Experte."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.8
            )

            text = response.choices[0].message.content.strip()
            # Remove quotes if present
            text = text.strip('"\'')

            return {
                'success': True,
                'text': text
            }

        except Exception as e:
            logger.error(f"Error generating overlay text: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_seo_description(self, keywords: str, image_description: str, image_base64: str = None, overlay_text: str = None) -> dict:
        """
        Generiert die PERFEKTE Pinterest Pin-Beschreibung via GPT.

        Strategie:
        1. Haupt-Keyword aus der Keyword-Liste extrahieren und priorisieren
        2. Optional: Bild mit OpenAI Vision analysieren
        3. Motivierende, leicht lesbare Beschreibung erstellen
        4. Passende Hashtags hinzufügen
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            # Extrahiere das Haupt-Keyword (erstes Keyword ist am wichtigsten)
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
            main_keyword = keyword_list[0] if keyword_list else keywords
            secondary_keywords = keyword_list[1:5] if len(keyword_list) > 1 else []

            # Bild-Analyse wenn Bild vorhanden
            image_analysis = None
            if image_base64:
                image_analysis = self._analyze_image_for_seo(image_base64)
                logger.info(f"Image analysis result: {image_analysis[:100] if image_analysis else 'None'}...")

            prompt = f"""Du bist ein Pinterest Marketing-Experte. Erstelle die PERFEKTE Pin-Beschreibung.

🎯 HAUPT-KEYWORD (WICHTIGSTER BEGRIFF - muss prominent vorkommen):
"{main_keyword}"

📝 Weitere Keywords: {', '.join(secondary_keywords) if secondary_keywords else 'keine'}

🖼️ Bild-Inhalt: {image_analysis or image_description or 'Nicht angegeben'}

📌 Text auf dem Pin: {overlay_text or 'Nicht angegeben'}

═══════════════════════════════════════════════════════════════

ERSTELLE EINE PINTEREST-BESCHREIBUNG MIT FOLGENDER STRUKTUR:

1. HOOK (erste 100 Zeichen - KRITISCH für SEO!):
   - Beginne DIREKT mit dem Haupt-Keyword "{main_keyword}"
   - Emotionaler Einstieg der neugierig macht
   - Nutze Power-Wörter wie: Entdecke, Perfekt, Geheim, Einfach, Schnell

2. MITTELTEIL (motivierend & leicht lesbar):
   - Kurze, knackige Sätze (max. 10-15 Wörter pro Satz)
   - Nutzen/Benefit für den Leser hervorheben
   - Weitere Keywords natürlich einbauen
   - Emotionen wecken (Freude, Neugier, Inspiration)

3. CALL-TO-ACTION:
   - Motiviere zum Klicken: "Jetzt entdecken", "Mehr erfahren", "Lass dich inspirieren"
   - Oder Frage stellen: "Bereit für...?", "Willst du...?"

4. HASHTAGS (am Ende, 4-6 Stück):
   - #{{Haupt-Keyword}} MUSS dabei sein
   - Mix aus populären und spezifischen Tags
   - Deutsch und Englisch mischen für mehr Reichweite

═══════════════════════════════════════════════════════════════

REGELN:
✓ Maximal 480 Zeichen (inkl. Hashtags)
✓ Keine Emojis im Fließtext (nur bei Hashtags optional)
✓ Kein Werbe-Sprech, authentisch und hilfreich
✓ Leicht lesbar, als würdest du einem Freund erzählen

Antworte NUR mit der fertigen Beschreibung, ohne Erklärungen."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest SEO-Experte. Du schreibst Beschreibungen, die Menschen zum Klicken motivieren."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )

            description = response.choices[0].message.content.strip()

            # Ensure max 500 chars
            if len(description) > 500:
                description = description[:497] + '...'

            return {
                'success': True,
                'description': description,
                'main_keyword': main_keyword
            }

        except Exception as e:
            logger.error(f"Error generating SEO description: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _analyze_image_for_seo(self, image_base64: str) -> str:
        """Analysiert ein Bild mit OpenAI Vision für SEO-Beschreibung"""
        try:
            # Prüfe ob das Modell Vision unterstützt
            vision_models = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-vision-preview', 'gpt-4-turbo']
            model_to_use = self.model if any(v in self.model for v in vision_models) else 'gpt-4o-mini'

            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Beschreibe dieses Pinterest-Pin-Bild in 2-3 kurzen Sätzen auf Deutsch. Fokussiere auf: Was ist zu sehen? Welche Stimmung vermittelt es? Was macht es ansprechend? Keine Hashtags, nur Beschreibung."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "low"  # Schneller und günstiger
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Image analysis failed (will continue without): {e}")
            return None

    def generate_text_styling(self, keywords: str, overlay_text: str, pin_format: str = '1000x1500') -> dict:
        """
        Generiert optimales Text-Styling basierend auf Keywords und Overlay-Text.

        Berücksichtigt:
        - Textlänge für optimale Schriftgröße
        - Stimmung/Thema für Farbwahl
        - Pinterest Best-Practices
        - Kontrast und Lesbarkeit
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            # Berechne Bildmaße
            width, height = map(int, pin_format.split('x'))
            text_length = len(overlay_text)

            prompt = f"""Du bist ein Pinterest Design-Experte. Erstelle ein optimales Text-Styling für einen Pinterest Pin.

Overlay-Text: "{overlay_text}"
Textlänge: {text_length} Zeichen
Keywords/Thema: {keywords}
Bildformat: {width}x{height}px

Analysiere das Thema und erstelle ein passendes, kontrastreiches Styling.

Antworte NUR im folgenden JSON-Format (keine Erklärungen):
{{
    "style_preset": "<siehe Liste unten>",
    "text_font": "<siehe Liste unten>",
    "text_size": <optimale Schriftgröße 24-96 basierend auf Textlänge>,
    "text_color": "<Hex-Farbe für Text>",
    "text_secondary_color": "<Hex-Farbe für Outline/Schatten>",
    "text_background_color": "<Hex-Farbe für Hintergrund oder leer>",
    "text_background_opacity": <0.0-1.0>,
    "text_effect": "<siehe Liste unten>",
    "text_position": "top|center|bottom",
    "text_padding": <15-40>,
    "reasoning": "<kurze Begründung für die Wahl>"
}}

Style-Presets (wähle das passendste):
- modern_bold, minimal_clean, tech_futuristic, geometric (Modern)
- elegant_serif, luxury_gold, wedding_romantic, art_deco (Elegant)
- playful_color, neon_glow, pastel_soft, gradient_vibrant, rainbow (Bunt)
- dark_contrast, midnight_blue, noir_dramatic (Dunkel)
- bright_fresh, summer_beach, spring_floral (Hell)
- vintage_retro, retro_70s, polaroid (Retro)
- professional, corporate_blue, startup (Business)
- food_warm, nature_organic, fitness_energy, kids_playful, christmas, halloween (Themen)

Schriftarten:
- Sans-Serif: Arial, Helvetica, Verdana, Roboto, Open Sans, Montserrat, Lato, Poppins
- Serif: Times New Roman, Georgia, Palatino, Garamond, Playfair Display, Merriweather
- Display: Impact, Anton, Bebas Neue, Oswald, Raleway
- Script: Brush Script MT, Pacifico, Dancing Script, Great Vibes

Text-Effekte:
- Schatten: shadow, shadow_soft, shadow_hard, shadow_long, shadow_3d
- Kontur: outline, outline_thin, outline_thick, outline_double
- Glow: glow, glow_neon, glow_soft
- Hintergrund: highlight, box, rounded_box, pill
- Spezial: frame, banner, badge, stamp, gradient_text
- none (kein Effekt)

Regeln:
- Kurze Texte (< 30 Zeichen): große Schrift (60-96px)
- Mittlere Texte (30-60 Zeichen): mittlere Schrift (42-60px)
- Lange Texte (> 60 Zeichen): kleinere Schrift (24-42px)
- Immer hohen Kontrast zwischen Text und Hintergrund
- Für Pinterest: Bold, auffällig, leicht lesbar
- Wähle Preset/Font/Effekt passend zum Thema"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest Design-Experte. Antworte nur mit validem JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON
            import json
            # Handle markdown code blocks
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            styling = json.loads(result_text)

            # Validierung und Defaults - erweiterte Listen
            valid_presets = [
                'custom', 'modern_bold', 'minimal_clean', 'tech_futuristic', 'geometric',
                'elegant_serif', 'luxury_gold', 'wedding_romantic', 'art_deco',
                'playful_color', 'neon_glow', 'pastel_soft', 'gradient_vibrant', 'rainbow',
                'dark_contrast', 'midnight_blue', 'noir_dramatic',
                'bright_fresh', 'summer_beach', 'spring_floral',
                'vintage_retro', 'retro_70s', 'polaroid',
                'professional', 'corporate_blue', 'startup',
                'food_warm', 'nature_organic', 'fitness_energy', 'kids_playful', 'christmas', 'halloween'
            ]
            valid_effects = [
                'none', 'shadow', 'shadow_soft', 'shadow_hard', 'shadow_long', 'shadow_3d',
                'outline', 'outline_thin', 'outline_thick', 'outline_double',
                'glow', 'glow_neon', 'glow_soft',
                'highlight', 'underline', 'box', 'rounded_box', 'pill',
                'frame', 'banner', 'badge', 'stamp', 'torn_paper', 'gradient_text'
            ]
            valid_positions = ['top', 'center', 'bottom']
            valid_fonts = [
                'Arial', 'Helvetica', 'Verdana', 'Tahoma', 'Trebuchet MS',
                'Roboto', 'Open Sans', 'Montserrat', 'Lato', 'Poppins',
                'Times New Roman', 'Georgia', 'Palatino', 'Garamond', 'Playfair Display', 'Merriweather',
                'Impact', 'Anton', 'Bebas Neue', 'Oswald', 'Raleway',
                'Brush Script MT', 'Comic Sans MS', 'Pacifico', 'Dancing Script', 'Great Vibes',
                'Courier New', 'Consolas'
            ]

            styling['style_preset'] = styling.get('style_preset', 'modern_bold')
            if styling['style_preset'] not in valid_presets:
                styling['style_preset'] = 'modern_bold'

            styling['text_effect'] = styling.get('text_effect', 'shadow')
            if styling['text_effect'] not in valid_effects:
                styling['text_effect'] = 'shadow'

            styling['text_position'] = styling.get('text_position', 'center')
            if styling['text_position'] not in valid_positions:
                styling['text_position'] = 'center'

            styling['text_font'] = styling.get('text_font', 'Arial')
            if styling['text_font'] not in valid_fonts:
                styling['text_font'] = 'Arial'

            # Numerische Werte validieren
            styling['text_size'] = max(24, min(96, int(styling.get('text_size', 48))))
            styling['text_padding'] = max(10, min(50, int(styling.get('text_padding', 20))))
            styling['text_background_opacity'] = max(0.0, min(1.0, float(styling.get('text_background_opacity', 0.7))))

            # Hex-Farben validieren
            for color_field in ['text_color', 'text_secondary_color', 'text_background_color']:
                color = styling.get(color_field, '')
                if color and not color.startswith('#'):
                    color = '#' + color
                if color and len(color) != 7:
                    color = '#FFFFFF' if color_field == 'text_color' else '#000000'
                styling[color_field] = color

            return {
                'success': True,
                'styling': styling,
                'reasoning': styling.get('reasoning', '')
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in styling generation: {e}")
            # Fallback: Return safe defaults
            return self._get_fallback_styling(overlay_text)
        except Exception as e:
            logger.error(f"Error generating text styling: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_related_keywords(self, seed_keyword: str) -> dict:
        """
        Generiert verwandte Keywords mit hohem Suchvolumen für Pinterest.

        Args:
            seed_keyword: Das Ausgangs-Keyword

        Returns:
            Dict mit success, keywords (Liste) und optional error
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI API-Key nicht konfiguriert'
            }

        try:
            prompt = f"""Du bist ein Pinterest SEO-Experte und Keyword-Researcher.

Ausgangs-Keyword: "{seed_keyword}"

Generiere 8-12 verwandte Keywords, die:
1. Zum Thema passen und auf Pinterest relevant sind
2. Ein hohes Suchvolumen haben (beliebte Suchbegriffe)
3. Für Pinterest Pin-Erstellung geeignet sind
4. Long-Tail Keywords und Variationen enthalten
5. Sowohl deutsche als auch englische Keywords (je nach Thema)

Antworte NUR mit einer kommagetrennten Liste der Keywords, ohne Nummerierung oder Erklärungen.
Beispiel-Format: keyword1, keyword2, keyword3, keyword4

Fokussiere auf:
- Trending Topics im Bereich
- Saisonale Begriffe falls relevant
- Action-Keywords (DIY, Tipps, Ideen, Anleitung)
- Spezifische Nischen-Keywords"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein Pinterest SEO-Experte. Antworte nur mit Keywords."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )

            result_text = response.choices[0].message.content.strip()

            # Keywords parsen (kommagetrennt)
            keywords = [kw.strip() for kw in result_text.split(',') if kw.strip()]

            # Original-Keyword am Anfang behalten falls nicht vorhanden
            if seed_keyword.lower() not in [kw.lower() for kw in keywords]:
                keywords.insert(0, seed_keyword)

            return {
                'success': True,
                'keywords': keywords
            }

        except Exception as e:
            logger.error(f"Error generating related keywords: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_fallback_styling(self, overlay_text: str) -> dict:
        """Fallback-Styling wenn KI-Generierung fehlschlägt"""
        text_length = len(overlay_text)

        # Schriftgröße basierend auf Textlänge
        if text_length < 30:
            text_size = 72
        elif text_length < 60:
            text_size = 54
        else:
            text_size = 36

        return {
            'success': True,
            'styling': {
                'style_preset': 'modern_bold',
                'text_font': 'Arial',
                'text_size': text_size,
                'text_color': '#FFFFFF',
                'text_secondary_color': '#000000',
                'text_background_color': '#000000',
                'text_background_opacity': 0.6,
                'text_effect': 'shadow',
                'text_position': 'center',
                'text_padding': 25,
            },
            'reasoning': 'Fallback-Styling (kontrastreiche Standard-Einstellungen)',
            'is_fallback': True
        }
