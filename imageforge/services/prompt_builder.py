"""
PromptBuilder für ImageForge

Baut optimierte Prompts aus den Benutzer-Einstellungen für verschiedene
Bildgenerierungs-Modi und KI-Modelle.
"""

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT-VORLAGEN
# =============================================================================

LIGHTING_PROMPTS = {
    'studio': 'professional studio lighting with clean shadows',
    'natural': 'soft natural daylight, organic ambient light',
    'dramatic': 'dramatic lighting with strong contrasts and spotlight effect',
    'soft': 'soft diffused lighting with no harsh shadows',
    'golden_hour': 'warm golden hour lighting, atmospheric sunset tones',
    'high_key': 'bright high-key lighting, overexposed look',
}

PERSPECTIVE_PROMPTS = {
    'frontal': 'straight-on frontal view',
    'angle_45': 'slight 45-degree angle view, adds depth',
    'flat_lay': 'flat lay top-down view from above',
    'floating': 'product floating in space, levitating',
    'hero': 'dramatic hero shot from below, powerful angle',
    'macro': 'macro close-up view showing fine details',
}

STYLE_PROMPTS = {
    'ecommerce': 'clean e-commerce style, white or neutral background, professional product photography',
    'lifestyle': 'lifestyle photography, product in real-world setting, contextual scene',
    'minimal': 'minimalist design, lots of white space, simple clean aesthetic',
    'luxury': 'luxury premium style, dark tones, reflections, high-end feel',
    'nature': 'organic natural setting, plants and natural materials, earthy tones',
    'tech': 'modern tech style, geometric shapes, clean lines, futuristic',
}

SHADOW_PROMPTS = {
    'none': 'no shadows',
    'soft': 'soft diffused shadow',
    'hard': 'sharp defined hard shadow',
    'reflection': 'glossy surface reflection below',
}

COLOR_MOOD_PROMPTS = {
    'warm': 'warm color tones, cozy atmosphere',
    'neutral': 'neutral balanced colors',
    'cool': 'cool blue-tinted color palette',
    'vibrant': 'vibrant saturated colors, bold and eye-catching',
}


# =============================================================================
# TEXT-EMBEDDING PROMPTS
# =============================================================================

TEXT_EMBEDDING_BASE = """
IMPORTANT TEXT OVERLAY INSTRUCTIONS:
- Include the following text prominently in the image: "{text}"
- The text must be clearly readable, with high contrast against the background
- Use professional typography with clean, legible fonts
- Text should be large enough to be easily readable
- Ensure the text is properly integrated into the composition
"""

TEXT_BACKGROUND_PROMPT = """
- Place the text on a solid or semi-transparent background shape
- The background shape should have a color that contrasts well with the text
- The shape should complement the overall design
"""

TEXT_CREATIVE_SHAPES_PROMPT = """
- Use CREATIVE shapes for the text background: banner, ribbon, splash, brush stroke, torn paper, badge, stamp, explosion shape, speech bubble, or similar dynamic elements
- The shape should add visual interest and energy to the design
- Make the text background shape eye-catching but not overwhelming
"""


class PromptBuilder:
    """
    Baut optimierte Prompts für verschiedene Generierungs-Modi.

    Modi:
    - background: Nur Hintergrund generieren
    - product: Produkt auf KI-Hintergrund platzieren
    - character: Charakter in neuer Szene
    - character_product: Charakter mit Produkt in Szene
    """

    def build_prompt(
        self,
        mode: str,
        background_description: str,
        lighting: str = 'natural',
        perspective: str = 'frontal',
        style: str = 'lifestyle',
        shadow: str = 'soft',
        color_mood: str = 'neutral',
        character_description: str = '',
        product_description: str = '',
        aspect_ratio: str = '1:1',
        overlay_text: str = '',
        text_background_enabled: bool = False,
        text_background_creative: bool = False
    ) -> str:
        """
        Baut einen vollständigen Prompt basierend auf Modus und Einstellungen.

        Args:
            mode: Generierungs-Modus (background, product, character, character_product)
            background_description: Beschreibung der Szene/Hintergrund
            lighting: Lichtstil
            perspective: Perspektive
            style: Stil-Preset
            shadow: Schatten-Typ
            color_mood: Farbstimmung
            character_description: Beschreibung des Charakters (für character-Modi)
            product_description: Beschreibung des Produkts
            aspect_ratio: Bildformat
            overlay_text: Optionaler Text der ins Bild eingebettet wird
            text_background_enabled: Text auf Hintergrund-Element platzieren
            text_background_creative: Kreative Formen für Text-Hintergrund erlauben

        Returns:
            Vollständiger, optimierter Prompt
        """
        if mode == 'background':
            base_prompt = self._build_background_prompt(
                background_description, lighting, perspective, style,
                shadow, color_mood, aspect_ratio
            )
        elif mode == 'product':
            base_prompt = self._build_product_prompt(
                background_description, product_description, lighting,
                perspective, style, shadow, color_mood, aspect_ratio
            )
        elif mode == 'character':
            base_prompt = self._build_character_prompt(
                background_description, character_description, lighting,
                perspective, style, color_mood, aspect_ratio
            )
        elif mode == 'character_product':
            base_prompt = self._build_character_product_prompt(
                background_description, character_description, product_description,
                lighting, perspective, style, color_mood, aspect_ratio
            )
        else:
            logger.warning(f"Unknown mode: {mode}, falling back to background")
            base_prompt = self._build_background_prompt(
                background_description, lighting, perspective, style,
                shadow, color_mood, aspect_ratio
            )

        # Text-Embedding hinzufügen falls aktiviert
        if overlay_text and overlay_text.strip():
            text_instructions = self._build_text_embedding_prompt(
                overlay_text.strip(),
                text_background_enabled,
                text_background_creative
            )
            base_prompt = base_prompt + "\n\n" + text_instructions

        return base_prompt

    def _build_background_prompt(
        self, description: str, lighting: str, perspective: str,
        style: str, shadow: str, color_mood: str, aspect_ratio: str
    ) -> str:
        """Baut Prompt für Nur-Hintergrund-Modus"""
        parts = []

        # Hauptbeschreibung
        parts.append(f"Create a high-quality background image: {description.strip()}")

        # Stil-Einstellungen
        style_settings = self._get_style_settings(lighting, perspective, style, shadow, color_mood)
        parts.append(style_settings)

        # Bildformat
        format_instruction = self._get_format_instruction(aspect_ratio)
        parts.append(format_instruction)

        # Qualität
        parts.append(
            "Professional quality, high resolution, suitable for commercial use. "
            "Clean composition with visual interest."
        )

        prompt = " ".join(parts)
        logger.info(f"Built background prompt: {prompt[:200]}...")
        return prompt

    def _build_product_prompt(
        self, background_desc: str, product_desc: str, lighting: str,
        perspective: str, style: str, shadow: str, color_mood: str, aspect_ratio: str
    ) -> str:
        """Baut Prompt für Produkt-auf-Hintergrund-Modus"""
        parts = []

        # Produktintegration
        parts.append(
            "Create a product photography image. "
            "Extract the product from the provided reference image and place it prominently. "
            "Keep the product exactly as it appears - do not modify, distort, or reimagine the product itself."
        )

        # Produktbeschreibung falls vorhanden
        if product_desc:
            parts.append(f"The product is: {product_desc.strip()}")

        # Hintergrund
        if background_desc:
            parts.append(f"Place the product in this setting: {background_desc.strip()}")

        # Stil-Einstellungen
        style_settings = self._get_style_settings(lighting, perspective, style, shadow, color_mood)
        parts.append(style_settings)

        # Bildformat
        format_instruction = self._get_format_instruction(aspect_ratio)
        parts.append(format_instruction)

        # Qualität
        parts.append(
            "Professional product photography quality, high resolution. "
            "The product should be the clear focal point of the image."
        )

        prompt = " ".join(parts)
        logger.info(f"Built product prompt: {prompt[:200]}...")
        return prompt

    def _build_character_prompt(
        self, background_desc: str, character_desc: str, lighting: str,
        perspective: str, style: str, color_mood: str, aspect_ratio: str
    ) -> str:
        """Baut Prompt für Charakter-in-Szene-Modus"""
        parts = []

        # Charakter-Integration
        parts.append(
            "Create an image featuring the person/character from the provided reference images. "
            "Maintain the exact likeness, facial features, and identity of the character. "
            "The character should look natural and believable in the new setting."
        )

        # Charakterbeschreibung falls vorhanden
        if character_desc:
            parts.append(f"Character details: {character_desc.strip()}")

        # Szene
        if background_desc:
            parts.append(f"Place the character in this scene: {background_desc.strip()}")

        # Stil-Einstellungen (ohne shadow für Charaktere)
        style_parts = []
        if lighting in LIGHTING_PROMPTS:
            style_parts.append(LIGHTING_PROMPTS[lighting])
        if perspective in PERSPECTIVE_PROMPTS:
            style_parts.append(PERSPECTIVE_PROMPTS[perspective])
        if style in STYLE_PROMPTS:
            style_parts.append(STYLE_PROMPTS[style])
        if color_mood in COLOR_MOOD_PROMPTS:
            style_parts.append(COLOR_MOOD_PROMPTS[color_mood])

        if style_parts:
            parts.append("Style: " + ", ".join(style_parts) + ".")

        # Bildformat
        format_instruction = self._get_format_instruction(aspect_ratio)
        parts.append(format_instruction)

        # Qualität
        parts.append(
            "Professional quality, realistic rendering, natural pose and expression. "
            "The character should be seamlessly integrated into the scene."
        )

        prompt = " ".join(parts)
        logger.info(f"Built character prompt: {prompt[:200]}...")
        return prompt

    def _build_character_product_prompt(
        self, background_desc: str, character_desc: str, product_desc: str,
        lighting: str, perspective: str, style: str, color_mood: str, aspect_ratio: str
    ) -> str:
        """Baut Prompt für Charakter-mit-Produkt-Modus"""
        parts = []

        # Charakter + Produkt Integration
        parts.append(
            "Create an image featuring the person/character from the provided reference images "
            "holding or presenting a product. "
            "Maintain the exact likeness of the character. "
            "Keep the product exactly as it appears in its reference image."
        )

        # Charakterbeschreibung
        if character_desc:
            parts.append(f"Character details: {character_desc.strip()}")

        # Produktbeschreibung
        if product_desc:
            parts.append(f"The product they are holding/presenting: {product_desc.strip()}")

        # Interaktion
        parts.append(
            "The character should naturally interact with the product - "
            "holding it, showing it, or demonstrating it in a believable way."
        )

        # Szene
        if background_desc:
            parts.append(f"Set the scene in: {background_desc.strip()}")

        # Stil-Einstellungen
        style_parts = []
        if lighting in LIGHTING_PROMPTS:
            style_parts.append(LIGHTING_PROMPTS[lighting])
        if perspective in PERSPECTIVE_PROMPTS:
            style_parts.append(PERSPECTIVE_PROMPTS[perspective])
        if style in STYLE_PROMPTS:
            style_parts.append(STYLE_PROMPTS[style])
        if color_mood in COLOR_MOOD_PROMPTS:
            style_parts.append(COLOR_MOOD_PROMPTS[color_mood])

        if style_parts:
            parts.append("Style: " + ", ".join(style_parts) + ".")

        # Bildformat
        format_instruction = self._get_format_instruction(aspect_ratio)
        parts.append(format_instruction)

        # Qualität
        parts.append(
            "Professional advertising quality, suitable for marketing materials. "
            "Natural interaction between character and product. High resolution."
        )

        prompt = " ".join(parts)
        logger.info(f"Built character+product prompt: {prompt[:200]}...")
        return prompt

    def _get_style_settings(
        self, lighting: str, perspective: str, style: str,
        shadow: str, color_mood: str
    ) -> str:
        """Kombiniert alle Stil-Einstellungen zu einem String"""
        parts = []

        if lighting in LIGHTING_PROMPTS:
            parts.append(LIGHTING_PROMPTS[lighting])
        if perspective in PERSPECTIVE_PROMPTS:
            parts.append(PERSPECTIVE_PROMPTS[perspective])
        if style in STYLE_PROMPTS:
            parts.append(STYLE_PROMPTS[style])
        if shadow in SHADOW_PROMPTS:
            parts.append(SHADOW_PROMPTS[shadow])
        if color_mood in COLOR_MOOD_PROMPTS:
            parts.append(COLOR_MOOD_PROMPTS[color_mood])

        if parts:
            return "Style: " + ", ".join(parts) + "."
        return ""

    def _get_format_instruction(self, aspect_ratio: str) -> str:
        """Gibt Formatanweisung basierend auf Aspect Ratio zurück"""
        format_map = {
            '1:1': 'Square format (1:1 aspect ratio).',
            '4:3': 'Standard format (4:3 aspect ratio).',
            '16:9': 'Widescreen format (16:9 aspect ratio), horizontal composition.',
            '9:16': 'Vertical portrait format (9:16 aspect ratio), ideal for stories/mobile.',
            '3:4': 'Portrait format (3:4 aspect ratio), vertical composition.',
        }
        return format_map.get(aspect_ratio, 'Square format (1:1 aspect ratio).')

    def _build_text_embedding_prompt(
        self,
        text: str,
        text_background_enabled: bool = False,
        text_background_creative: bool = False
    ) -> str:
        """
        Baut Prompt-Anweisungen für Text-Einbettung im Bild.

        Args:
            text: Der einzubettende Text
            text_background_enabled: Text auf Hintergrund-Element platzieren
            text_background_creative: Kreative Formen erlauben

        Returns:
            Prompt-String für Text-Einbettung
        """
        parts = []

        # Basis-Text-Anweisungen
        parts.append(TEXT_EMBEDDING_BASE.format(text=text).strip())

        # Text-Hintergrund Optionen
        if text_background_enabled:
            parts.append(TEXT_BACKGROUND_PROMPT.strip())

            if text_background_creative:
                parts.append(TEXT_CREATIVE_SHAPES_PROMPT.strip())

        result = "\n".join(parts)
        logger.info(f"Built text embedding prompt for: '{text[:50]}...'")
        return result
