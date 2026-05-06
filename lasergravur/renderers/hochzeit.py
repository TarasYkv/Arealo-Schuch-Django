"""Renderer für Hochzeitstopf — anderes Schema als Designer.

Layout-Daten aus hochzeit-preview.js:
- baseImage = vorschaubild.png (gleicher Topf wie Designer)
- vornamen-Text bei (400, 580), fontSize 72, Font 'Lovely'
- datum-Text bei (400, 670), fontSize 42, Font 'Poppins Black'
- motiv-Bild (Trauring/Herz/etc.) bei (400, 425), max 200×200

Properties aus Shopify-Order:
- 'Vornamen': 'Kim & Max'
- 'Datum': '16.05.2026'
- 'Motiv': 'Motiv 20'  → mappt auf motivUrls[20]
"""
from __future__ import annotations

import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .asset_loader import ensure_assets
from .designer import (
    _draw_text_with_fallback,
    _hex_to_rgba,
    _to_black_silhouette,
    _first_value,
)

logger = logging.getLogger(__name__)


def render_hochzeit(order, design, store, *,
                     with_background: bool = True,
                     output_size_px: int = 800,
                     export_padding_mm: float = 5.0,
                     topf_model: str = 'hochzeit') -> bytes:
    """Rendert Hochzeit/Hochzeit-Glossy/Glossy-Geburt-Design als PNG.

    Mapping Design-Felder → Hochzeits-Layout:
    - design.text_1 = Vornamen (z.B. „Kim & Max")
    - design.text_2 = Datum (z.B. „16.05.2026")
    - design.icon_id = Motiv-Nummer (1-27)
    """
    config = ensure_assets(store, topf_model)
    canvas_w = config.get('canvasWidth', 800)
    canvas_h = config.get('canvasHeight', 800)
    scale = output_size_px / canvas_w

    if with_background:
        base_path = config.get('baseImagePath', '')
        if base_path and os.path.exists(base_path):
            img = Image.open(base_path).convert('RGBA')
            img = img.resize((output_size_px, int(canvas_h * scale)), Image.LANCZOS)
        else:
            img = Image.new('RGBA', (output_size_px, int(canvas_h * scale)),
                             (255, 255, 255, 255))
    else:
        img = Image.new('RGBA',
                        (max(3000, int(canvas_w * 4)), max(3000, int(canvas_h * 4))),
                        (0, 0, 0, 0))
        scale = img.size[0] / canvas_w

    draw = ImageDraw.Draw(img)
    font_paths = config.get('fontPaths') or {}
    # Hochzeits-Schemas referenzieren Schriften wie Lovely, Poppins Black, Halimun,
    # Yanone Kaffeesatz — die meisten sind im Topf-spezifischen JS nicht als
    # Datei-URL hinterlegt. Fallback-Kette: lokale Topf-Schrift → Designer-Schrift
    # → erste verfügbare. Map = bekannte Style-Approximationen.
    designer_config = ensure_assets(store, 'designer')
    designer_fonts = designer_config.get('fontPaths') or {}
    style_fallbacks = {
        'Lovely':           ['Sacramento', 'Allura', 'Dreaming Outloud'],
        'Halimun':          ['Sacramento', 'Allura', 'Dreaming Outloud'],
        'Poppins Black':    ['Poppins Black', 'Bebas Neue', 'Montserrat'],
        'Yanone Kaffeesatz':['Yanone Kaffeesatz', 'Bebas Neue', 'Amatic SC'],
    }

    def _resolve(family: str) -> str:
        if not family:
            return _first_value(designer_fonts) or ''
        if family in font_paths:
            return font_paths[family]
        for fb in style_fallbacks.get(family, []):
            if fb in designer_fonts:
                return designer_fonts[fb]
        return _first_value(designer_fonts) or ''

    # ---------- 1. Motiv (oben) ----------
    motiv_id = design.icon_id
    icon_paths = config.get('iconPaths') or {}
    motiv_path = icon_paths.get(motiv_id) or icon_paths.get(str(motiv_id)) if motiv_id else None
    if motiv_path and os.path.exists(motiv_path):
        icon_cfg = config.get('iconConfig', {})
        icon_x = int(icon_cfg.get('x', 400) * scale)
        icon_y = int(icon_cfg.get('y', 425) * scale)
        max_w = int(icon_cfg.get('maxWidth', 200) * scale)
        max_h = int(icon_cfg.get('maxHeight', 200) * scale)

        motiv_img = Image.open(motiv_path).convert('RGBA')
        if not with_background:
            motiv_img = _to_black_silhouette(motiv_img)
        motiv_img.thumbnail((max_w, max_h), Image.LANCZOS)
        iw, ih = motiv_img.size
        img.paste(motiv_img, (icon_x - iw // 2, icon_y - ih // 2), motiv_img)

    # ---------- 2. Vornamen (+ optional Datum) ----------
    hz_text = config.get('hochzeitText') or {}
    vor_cfg = hz_text.get('vornamen', {'x': 400, 'y': 580, 'fontSize': 72})
    dat_cfg = hz_text.get('datum')  # kann None sein (z.B. Mini Palm hat nur 1 Text)

    color = _hex_to_rgba('#000000' if not with_background else '#4a4a4a')

    if design.text_1:
        font_path = _resolve(vor_cfg.get('fontFamily', ''))
        x = int(vor_cfg['x'] * scale); y = int(vor_cfg['y'] * scale)
        size = int(vor_cfg['fontSize'] * scale)
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        _draw_text_with_fallback(draw, (x, y), design.text_1, font, font_path, color, anchor='mm')

    if design.text_2 and dat_cfg:
        font_path = _resolve(dat_cfg.get('fontFamily', ''))
        x = int(dat_cfg['x'] * scale); y = int(dat_cfg['y'] * scale)
        size = int(dat_cfg['fontSize'] * scale)
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        _draw_text_with_fallback(draw, (x, y), design.text_2, font, font_path, color, anchor='mm')

    # Export-Mode: Bounding-Box-Crop + Padding
    if not with_background:
        bbox = img.getbbox()
        if bbox:
            cropped = img.crop(bbox)
            cw, ch = cropped.size
            padding_px = int(export_padding_mm / 100 * output_size_px)
            max_inner = output_size_px - 2 * padding_px
            longest = max(cw, ch)
            sf = max_inner / longest if longest > 0 else 1
            new_w, new_h = max(1, int(cw * sf)), max(1, int(ch * sf))
            cropped = cropped.resize((new_w, new_h), Image.LANCZOS)
            final = Image.new('RGBA', (new_w + 2 * padding_px, new_h + 2 * padding_px),
                               (0, 0, 0, 0))
            final.paste(cropped, (padding_px, padding_px), cropped)
            img = final

    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
