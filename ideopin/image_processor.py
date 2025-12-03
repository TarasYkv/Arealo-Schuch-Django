import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

logger = logging.getLogger(__name__)


class PinImageProcessor:
    """Bildverarbeitung für Pinterest Pins mit Text-Overlay"""

    # Standard fonts to try (cross-platform)
    FONT_PATHS = {
        'Arial': [
            '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'C:/Windows/Fonts/arial.ttf',
        ],
        'Helvetica': [
            '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            'C:/Windows/Fonts/arial.ttf',
        ],
        'Times New Roman': [
            '/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
            'C:/Windows/Fonts/times.ttf',
        ],
        'Georgia': [
            '/usr/share/fonts/truetype/msttcorefonts/Georgia.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
            'C:/Windows/Fonts/georgia.ttf',
        ],
        'Verdana': [
            '/usr/share/fonts/truetype/msttcorefonts/Verdana.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'C:/Windows/Fonts/verdana.ttf',
        ],
        'Impact': [
            '/usr/share/fonts/truetype/msttcorefonts/Impact.ttf',
            'C:/Windows/Fonts/impact.ttf',
        ],
    }

    def __init__(self, image_path_or_object):
        """
        Initialisiert den Processor mit einem Bild.

        Args:
            image_path_or_object: Pfad zum Bild oder PIL Image Objekt
        """
        if isinstance(image_path_or_object, Image.Image):
            self.image = image_path_or_object.copy()
        else:
            self.image = Image.open(image_path_or_object)

        # Convert to RGBA for transparency support
        if self.image.mode != 'RGBA':
            self.image = self.image.convert('RGBA')

    def _get_font(self, font_name: str, size: int) -> ImageFont.FreeTypeFont:
        """Lädt eine Schriftart"""
        font_paths = self.FONT_PATHS.get(font_name, self.FONT_PATHS['Arial'])

        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue

        # Fallback to default font
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Konvertiert Hex-Farbe zu RGB-Tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        """Bricht Text in mehrere Zeilen um"""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]

            if line_width > max_width:
                if len(current_line) == 1:
                    # Word is too long, add it anyway
                    lines.append(test_line)
                    current_line = []
                else:
                    # Remove last word and add line
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def add_text_overlay(
        self,
        text: str,
        font: str = 'Arial',
        size: int = 48,
        color: str = '#FFFFFF',
        position: str = 'center',
        background_color: str = None,
        background_opacity: float = 0.7
    ) -> Image.Image:
        """
        Fügt Text-Overlay zum Bild hinzu.

        Args:
            text: Der anzuzeigende Text
            font: Schriftart-Name
            size: Schriftgröße
            color: Textfarbe als Hex
            position: 'top', 'center', oder 'bottom'
            background_color: Hintergrundfarbe für Textbox (None für transparent)
            background_opacity: Transparenz des Hintergrunds (0-1)

        Returns:
            PIL Image mit Text-Overlay
        """
        if not text:
            return self.image

        # Create a copy to work on
        result = self.image.copy()
        draw = ImageDraw.Draw(result)

        # Load font
        pil_font = self._get_font(font, size)

        # Calculate text dimensions
        img_width, img_height = result.size
        max_text_width = int(img_width * 0.9)  # 90% of image width

        # Wrap text
        lines = self._wrap_text(text, pil_font, max_text_width)

        # Calculate total text height
        line_heights = []
        for line in lines:
            bbox = pil_font.getbbox(line)
            line_heights.append(bbox[3] - bbox[1])

        total_text_height = sum(line_heights) + (len(lines) - 1) * 10  # 10px line spacing

        # Calculate position
        padding = 20

        if position == 'top':
            start_y = padding + 50
        elif position == 'bottom':
            start_y = img_height - total_text_height - padding - 50
        else:  # center
            start_y = (img_height - total_text_height) // 2

        # Draw background box if specified
        if background_color:
            bg_rgb = self._hex_to_rgb(background_color)
            bg_alpha = int(background_opacity * 255)

            # Calculate box dimensions
            max_line_width = 0
            for line in lines:
                bbox = pil_font.getbbox(line)
                max_line_width = max(max_line_width, bbox[2] - bbox[0])

            box_left = (img_width - max_line_width) // 2 - padding
            box_top = start_y - padding
            box_right = (img_width + max_line_width) // 2 + padding
            box_bottom = start_y + total_text_height + padding

            # Create semi-transparent overlay
            overlay = Image.new('RGBA', result.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [box_left, box_top, box_right, box_bottom],
                fill=(*bg_rgb, bg_alpha)
            )
            result = Image.alpha_composite(result, overlay)
            draw = ImageDraw.Draw(result)

        # Draw text
        text_rgb = self._hex_to_rgb(color)
        current_y = start_y

        for i, line in enumerate(lines):
            bbox = pil_font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            x = (img_width - line_width) // 2

            # Draw shadow for better readability
            shadow_offset = max(2, size // 20)
            draw.text((x + shadow_offset, current_y + shadow_offset), line, font=pil_font, fill=(0, 0, 0, 128))

            # Draw main text
            draw.text((x, current_y), line, font=pil_font, fill=(*text_rgb, 255))

            current_y += line_heights[i] + 10

        return result

    def resize_for_pinterest(self, format_size: str) -> Image.Image:
        """
        Passt das Bild an ein Pinterest-Format an.

        Args:
            format_size: '1000x1500', '1000x1000', etc.

        Returns:
            Resized PIL Image
        """
        dimensions = {
            '1000x1500': (1000, 1500),
            '1000x1000': (1000, 1000),
            '1080x1920': (1080, 1920),
            '600x900': (600, 900),
        }

        target_size = dimensions.get(format_size, (1000, 1500))
        return self.image.resize(target_size, Image.Resampling.LANCZOS)

    def save(self, output_path: str, quality: int = 95) -> str:
        """Speichert das Bild"""
        # Convert to RGB for JPEG compatibility
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            rgb_image = self.image.convert('RGB')
            rgb_image.save(output_path, quality=quality)
        else:
            self.image.save(output_path)
        return output_path
