"""Generischer Renderer für alle Naturmacher-Topf-Modelle.

Rendert das Personalisierungs-Design EXAKT wie die Shop-Live-Vorschau:
- Topf-Hintergrund + Icon (an Position aus iconConfig) + 4 Textzeilen (Positionen aus textConfig)
- Schriftarten + Icon + Layout-Positionen werden pro Topf-Modell aus dem
  jeweiligen `<modell>-preview.js` im Theme geladen (Asset-Loader)

Funktioniert für alle Topf-Modelle, deren Preview-JS Standard-Schema hat:
designer, glossy, glossywhite (= alle mit textConfig + iconConfig + fontConfig).
Spezialmodelle (Birthtree mit Datum-Picker, Hochzeit mit 2 Namen, Fotogravur
mit Bild-Upload) bekommen perspektivisch eigene Renderer.

Zwei Modi:
- with_background=True: Topf-Bild + Design overlayed = WYSIWYG
- with_background=False: NUR Design auf transparent (für Lasergravur)
"""
from __future__ import annotations

import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .asset_loader import ensure_assets

logger = logging.getLogger(__name__)


# Fallback-Font für Glyphs die in den 6 Naturmacher-Schriften nicht da sind
# (z.B. Herz ♥, Stern ★, andere Symbole). DejaVu Sans ist auf den meisten
# Linux-Systemen vorhanden und enthält praktisch alle Unicode-Symbole.
FALLBACK_FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]


def _draw_text_with_fallback(draw, xy, text, font, font_path, fill, anchor='mm'):
    """Zeichnet Text — pro Zeichen prüfen ob die Schriftart das Glyph hat,
    sonst Fallback-Font (DejaVu) für dieses eine Zeichen.

    Vor dem Render werden Emoji-Hearts/Sterne auf monochrome Unicode-Symbole
    gemappt die DejaVu Sans rendern kann.
    """
    text = _normalize_emoji_to_symbol(text)
    try:
        font_obj = font  # primärer Font
        # Zeichen klassifizieren: hat primärer Font ein Glyph?
        runs = []  # Liste von (text, font_to_use) Tupeln
        cur_text = ''
        cur_use_primary = None
        # Bestimme Fallback-Font (gleiche Pixelgröße)
        fallback_font = _get_fallback_font(font.size if hasattr(font, 'size') else 32)
        for ch in text:
            has_glyph = _font_has_glyph(font_obj, ch)
            use_primary = has_glyph
            if cur_use_primary is None:
                cur_use_primary = use_primary
            if use_primary != cur_use_primary:
                runs.append((cur_text, font_obj if cur_use_primary else fallback_font))
                cur_text = ch
                cur_use_primary = use_primary
            else:
                cur_text += ch
        if cur_text:
            runs.append((cur_text, font_obj if cur_use_primary else fallback_font))

        # Wenn nur 1 Run + primärer Font: einfach zeichnen
        if len(runs) == 1 and runs[0][1] is font_obj:
            draw.text(xy, text, font=font_obj, fill=fill, anchor=anchor)
            return

        # Mehrere Runs: Gesamt-Breite berechnen, dann von links zentriert zeichnen
        total_w = 0
        run_widths = []
        for run_text, run_font in runs:
            try:
                bbox = draw.textbbox((0, 0), run_text, font=run_font)
                w = bbox[2] - bbox[0]
            except Exception:
                w = run_font.getlength(run_text) if hasattr(run_font, 'getlength') else len(run_text) * 20
            run_widths.append(w)
            total_w += w

        # Start-X = xy[0] - total_w/2 (für anchor=mm/mt zentriert)
        cx, cy = xy
        x_cursor = cx - total_w // 2
        for (run_text, run_font), rw in zip(runs, run_widths):
            try:
                draw.text((x_cursor, cy), run_text, font=run_font, fill=fill,
                           anchor='lm' if anchor == 'mm' else 'lt')
            except Exception:
                draw.text((x_cursor, cy), run_text, font=run_font, fill=fill)
            x_cursor += rw
    except Exception as exc:
        logger.warning('Text-Fallback-Render: %s — fallback einfaches draw.text', exc)
        draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _font_has_glyph(font, char: str) -> bool:
    """Prüft ob die TTF-Schriftart ein Glyph für das Zeichen enthält.

    Pillow's getmask() gibt das Tofu-Glyph (X im Kasten) als Pseudo-Glyph zurück,
    daher liefert die Pixel-Heuristik falsch True. Wir nutzen den Font selbst
    via freetype/fontTools wenn verfügbar — sonst Whitelist-Heuristik:
    - ASCII (Codepoint 32-126): Naturmacher-Schriften haben das alle ✓
    - Latin-1 Extended (Umlaute äöü, ß, etc.): meist ja ✓
    - Spezielle deutsche Anführungszeichen: meist ja
    - Alles andere (Symbole, Emojis): konservativ NEIN → DejaVu fallback
    """
    if not char:
        return True
    cp = ord(char)
    # ASCII (inkl. Whitespace): immer ja
    if 32 <= cp <= 126:
        return True
    # Latin-1 Supplement (umlaute, etc.): meist ja
    if 0x00A0 <= cp <= 0x00FF:
        return True
    # Latin Extended-A (z.B. Sonderbuchstaben für andere Sprachen): meist ja
    if 0x0100 <= cp <= 0x017F:
        return True
    # Allgemeine Interpunktion (typografisch — em-dash, „"  etc.): meist ja
    if 0x2010 <= cp <= 0x206F:
        return True
    # Alles andere = Symbole/Emojis: nutze Fallback-Font
    return False


def _normalize_emoji_to_symbol(text: str) -> str:
    """Mappt populäre Emoji-Codepoints auf monochrome Unicode-Symbole, die
    Standard-Schriftarten (DejaVu Sans) rendern können.

    Hintergrund: Kunden tippen oft ❤️ (U+2764 + U+FE0F = Emoji-Heart) oder
    🌟 (Star). Diese sind in den meisten Schriftarten nicht enthalten —
    das wäre dann ein Tofu □. Wir ersetzen sie mit ihren monochromen
    Pendants ♥ (U+2665) bzw. ★ (U+2605).
    """
    if not text:
        return text
    # Variation Selector entfernen (FE0F macht aus ♥ ein Emoji-❤️)
    text = text.replace('️', '')
    # Emoji → monochromes Symbol
    mapping = {
        '❤': '♥',  # ❤ → ♥
        '\U0001F496': '♥',  # 💖 → ♥
        '\U0001F497': '♥',  # 💗 → ♥
        '\U0001F49E': '♥',  # 💞 → ♥
        '\U0001F49B': '♥',  # 💛 → ♥
        '\U0001F49A': '♥',  # 💚 → ♥
        '\U0001F499': '♥',  # 💙 → ♥
        '\U0001F49C': '♥',  # 💜 → ♥
        '\U0001F49D': '♥',  # 💝 → ♥
        '\U0001F31F': '★',  # 🌟 → ★
        '⭐': '★',       # ⭐ → ★
        '\U0001F4AB': '★',  # 💫 → ★
        '\U0001F338': '⚘',  # 🌸 → ⚘
        '\U0001F33C': '⚘',  # 🌼 → ⚘
        '\U0001F339': '⚘',  # 🌹 → ⚘
        '\U0001F381': '■',  # 🎁 → ■
    }
    for emoji, symbol in mapping.items():
        text = text.replace(emoji, symbol)
    return text


def _get_fallback_font(size: int):
    """Liefert ein Pillow-Font-Objekt mit Fallback (DejaVu Sans) in der gewünschten Größe."""
    for fp in FALLBACK_FONT_PATHS:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def render_designer(order, design, store, *,
                     with_background: bool = True,
                     output_size_px: int = 800,
                     export_padding_mm: float = 5.0,
                     topf_model: str = 'designer') -> bytes:
    """Rendert das Design als PNG. Liefert die Bytes.

    Layout-Positionen (Icon, Text) werden IMMER 1:1 vom Shop-Konfigurator
    übernommen. Mitarbeiter sieht in Workloom dasselbe wie der Kunde im Shop.

    - with_background=True (UI-Preview): Topf-Hintergrund + Design overlayed
    - with_background=False (Lasergravur-Export): NUR Design (transparent)
      Output: output_size_px (z.B. 1181 = 10×10cm @ 300 DPI)
    - topf_model: 'designer', 'glossy', 'glossywhite', etc. — bestimmt welche
      preview-JS-Konfig geladen wird (Asset-Loader)
    """
    config = ensure_assets(store, topf_model)
    canvas_w = config.get('canvasWidth', 800)
    canvas_h = config.get('canvasHeight', 800)
    scale = output_size_px / canvas_w

    if with_background:
        # UI-Mode: Topf-Hintergrund laden, Design overlayen
        base_path = config.get('baseImagePath', '')
        if base_path and os.path.exists(base_path):
            img = Image.open(base_path).convert('RGBA')
            img = img.resize((output_size_px, int(canvas_h * scale)),
                              Image.LANCZOS)
        else:
            img = Image.new('RGBA',
                            (output_size_px, int(canvas_h * scale)),
                            (255, 255, 255, 255))
    else:
        # Export-Mode: groß rendern, danach Bounding-Box-Crop + Padding.
        # Wir rendern auf einer GROSSEN Canvas (3000×3000) damit nichts
        # abgeschnitten wird, dann croppen wir auf den tatsächlichen Inhalt
        # und skalieren auf output_size_px abzüglich Padding.
        canvas_size = max(3000, int(canvas_w * scale * 4))
        img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        # Skala so anpassen, dass die Shop-Positionen relativ zur großen
        # Canvas korrekt landen — wir rendern mit großem Faktor
        scale = canvas_size / canvas_w

    draw = ImageDraw.Draw(img)

    # ---------- 1. Icon ----------
    icon_id = design.icon_id
    icon_paths = config.get('iconPaths') or {}
    # JSON-Cache hat string-keys (int wurde zu str beim json.dump)
    icon_path = icon_paths.get(icon_id) or icon_paths.get(str(icon_id))
    if icon_id and icon_path:
        if os.path.exists(icon_path):
            icon_cfg = config.get('iconConfig', {})
            icon_x = int(icon_cfg.get('x', 520) * scale)
            icon_y = int(icon_cfg.get('y', 365) * scale)
            max_w = int(icon_cfg.get('maxWidth', 120) * scale)
            max_h = int(icon_cfg.get('maxHeight', 120) * scale)

            icon_img = Image.open(icon_path).convert('RGBA')
            if not with_background:
                # Im Export schwarz für Lasergravur
                icon_img = _to_black_silhouette(icon_img)
            icon_img.thumbnail((max_w, max_h), Image.LANCZOS)
            iw, ih = icon_img.size

            paste_x = icon_x - iw // 2
            paste_y = icon_y - ih // 2
            img.paste(icon_img, (paste_x, paste_y), icon_img)

    # ---------- 2. Textzeilen ----------
    text_cfg = config.get('textConfig', {})
    color_hex = text_cfg.get('color', '#4a4a4a')
    if not with_background:
        color_hex = '#000000'  # Reines Schwarz für Lasergravur
    color = _hex_to_rgba(color_hex)
    font_paths = config.get('fontPaths') or {}
    # Topf-spezifische Schriften (Bebas Neue, Halimun, etc.) sind oft nicht im
    # eigenen Theme-JS verlinkt. Designer-Topf hat 6 Standard-Schriften lokal —
    # wir nutzen die als Fallback-Pool für alle anderen Töpfe.
    designer_fonts = {}
    if topf_model != 'designer':
        try:
            designer_fonts = (ensure_assets(store, 'designer').get('fontPaths') or {})
        except Exception:
            pass
    all_fonts = {**designer_fonts, **font_paths}  # topf-eigene Schriften gewinnen
    default_font_path = all_fonts.get(design.font) or _first_value(all_fonts) or ''
    style_fallbacks = {
        'Bebas Neue':            ['Bebas Neue', 'Montserrat'],
        'Glacial Indifference':  ['Glacial Indifference', 'Montserrat', 'Bebas Neue'],
        'Halimun':               ['Halimun', 'Sacramento', 'Allura', 'Dreaming Outloud'],
        'Lovely':                ['Lovely', 'Sacramento', 'Allura', 'Dreaming Outloud'],
        'Yanone Kaffeesatz':     ['Yanone Kaffeesatz', 'Bebas Neue', 'Amatic SC'],
        'Poppins Black':         ['Poppins Black', 'Bebas Neue', 'Montserrat'],
    }

    def _resolve_font(family: str) -> str:
        if not family:
            return default_font_path
        if family in all_fonts:
            return all_fonts[family]
        for fb in style_fallbacks.get(family, []):
            if fb in all_fonts:
                return all_fonts[fb]
        return default_font_path

    # Apply offset (in mm → px), Konvertierung: 10 cm = canvas_w px → 1 mm = canvas_w/100 px
    offset_x_px = int(design.offset_x_mm * canvas_w / 100 * scale)
    offset_y_px = int(design.offset_y_mm * canvas_h / 100 * scale)

    lines = [
        ('line1', design.text_1),
        ('line2', design.text_2),
        ('line3', design.text_3),
        ('line4', design.text_4),
    ]

    for line_key, text in lines:
        if not text or not text.strip():
            continue
        line_cfg = text_cfg.get(line_key, {})
        x = int(line_cfg.get('x', canvas_w / 2) * scale) + offset_x_px
        y = int(line_cfg.get('y', canvas_h / 2) * scale) + offset_y_px
        font_size = int(line_cfg.get('fontSize', 48) * scale)

        # Topf-Vorgabe pro Zeile (Glossywhite: Bebas Neue für Zahl, Glacial für Text).
        # Wenn keine Vorgabe → User-Auswahl design.font.
        line_font_path = _resolve_font(line_cfg.get('fontFamily', '')) or default_font_path

        try:
            font = ImageFont.truetype(line_font_path, font_size) if line_font_path else ImageFont.load_default()
        except Exception as exc:
            logger.warning('Font %s nicht ladbar: %s', line_font_path, exc)
            font = ImageFont.load_default()

        _draw_text_with_fallback(draw, (x, y), text, font, line_font_path, color, anchor='mm')

    # ----- Export-Mode: Bounding-Box-Crop + symmetrisches Padding -----
    # Output ist NICHT mehr quadratisch fix, sondern Design-Aspect-Ratio +
    # gleichmäßiges Padding zu ALLEN 4 Seiten. Längste Dimension wird auf
    # output_size_px - 2*padding skaliert, kürzere Dimension proportional.
    # Lasergravur passt das beliebig auf den Tisch — ist nicht auf 10×10cm
    # quadratisch fixiert.
    if not with_background:
        bbox = img.getbbox()
        if bbox:
            cropped = img.crop(bbox)
            cw, ch = cropped.size

            # Längste Seite skaliert auf output_size_px - 2*padding
            padding_px = int(export_padding_mm / 100 * output_size_px)
            max_inner = output_size_px - 2 * padding_px
            longest = max(cw, ch)
            scale_factor = max_inner / longest if longest > 0 else 1
            new_w = max(1, int(cw * scale_factor))
            new_h = max(1, int(ch * scale_factor))
            cropped = cropped.resize((new_w, new_h), Image.LANCZOS)

            # Final-Canvas: Design-Größe + Padding rundum (NICHT mehr quadratisch fix)
            final_w = new_w + 2 * padding_px
            final_h = new_h + 2 * padding_px
            final = Image.new('RGBA', (final_w, final_h), (0, 0, 0, 0))
            final.paste(cropped, (padding_px, padding_px), cropped)
            img = final

    # PNG-Bytes ausgeben
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    s = hex_color.lstrip('#')
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), alpha)
    return (0, 0, 0, alpha)


def _first_value(d: dict):
    for v in d.values():
        return v
    return None


def _to_black_silhouette(rgba_img: Image.Image) -> Image.Image:
    """Wandelt ein RGBA-Bild in eine reine Schwarz-Silhouette um — Alpha bleibt erhalten.
    Für Lasergravur-Export: alle Pixel mit Alpha > 50 werden Schwarz, Rest transparent.
    """
    pixels = rgba_img.load()
    w, h = rgba_img.size
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out_pixels = out.load()
    for y in range(h):
        for x in range(w):
            _, _, _, a = pixels[x, y]
            if a > 50:
                out_pixels[x, y] = (0, 0, 0, a)
    return out
