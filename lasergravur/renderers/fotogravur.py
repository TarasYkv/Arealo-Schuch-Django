"""Renderer für Fotogravur-Topf — Kunden-Bild + optional Text-Untertitel.

Property-Schema (Annahme, da keine echte Bestellung als Referenz):
- 'Bild' / 'Foto' / 'Vorschau-Bild' / 'image_url' / '_image_url' → URL des Kunden-Fotos
- 'Text' / 'Textzeile' / 'Untertitel' → optionaler Text unter dem Bild

JS-Layout aus fotogravur-preview.js:
- imageConfig: x=400, y=445, maxWidth=350, maxHeight=350
- textConfig:  x=400, y=680, fontSize=48
"""
from __future__ import annotations

import logging
import os
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

from .asset_loader import ensure_assets
from .designer import (
    _draw_text_with_fallback,
    _hex_to_rgba,
    _to_black_silhouette,
    _first_value,
)

logger = logging.getLogger(__name__)

IMAGE_PROPERTY_KEYS = ['bild', 'foto', 'vorschau-bild', 'vorschaubild',
                        'image', 'image_url', '_image_url',
                        'kundenbild', 'kunden-bild', 'photo', 'upload']
TEXT_PROPERTY_KEYS = ['text', 'textzeile', 'untertitel', 'spruch']


def _find_image_url(properties: dict) -> str:
    """Sucht eine Bild-URL in den Order-Properties."""
    keys_lc = {k.lower(): v for k, v in (properties or {}).items() if k}
    for cand in IMAGE_PROPERTY_KEYS:
        for key_lc, value in keys_lc.items():
            if cand in key_lc and value and 'http' in str(value):
                return str(value).strip()
    return ''


def render_fotogravur(order, design, store, *,
                       with_background: bool = True,
                       output_size_px: int = 800,
                       export_padding_mm: float = 5.0,
                       topf_model: str = 'fotogravur') -> bytes:
    """Rendert Fotogravur-Topf mit Kunden-Bild aus Shopify-Properties."""
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

    # ---------- 1. Kunden-Bild (aus Properties) ----------
    # Naturmacher-Konfigurator wandelt das Foto via Bayer-Ordered-Dithering in
    # reines S/W (1 Bit) für die Lasergravur. Wir nutzen Pillows Floyd-Steinberg
    # (visuell sehr nah dran und viel schneller).
    img_url = _find_image_url(order.raw_properties or {})
    icon_cfg = config.get('iconConfig', {'x': 400, 'y': 445, 'maxWidth': 350, 'maxHeight': 350})
    threshold = int(_first_value({'_': 128}) or 128)  # default Threshold
    # Falls Order-Property einen Threshold-Override hat, nutze den
    for k, v in (order.raw_properties or {}).items():
        if 'threshold' in str(k).lower():
            try: threshold = max(0, min(255, int(v)))
            except Exception: pass

    if img_url:
        try:
            r = requests.get(img_url, timeout=30)
            r.raise_for_status()
            src = Image.open(BytesIO(r.content)).convert('RGBA')
            # Auf weißen Untergrund komponieren (PNG-Transparenz → weiß)
            bg = Image.new('RGB', src.size, (255, 255, 255))
            bg.paste(src, mask=src.split()[3] if src.mode == 'RGBA' else None)
            gray = bg.convert('L')
            # Threshold-Override: shift Helligkeit so dass Default-Threshold (128) wirkt
            if threshold != 128:
                shift = 128 - threshold
                gray = gray.point(lambda p: max(0, min(255, p + shift)))
            # Floyd-Steinberg Dithering → 1-Bit, dann zurück zu RGBA
            bw = gray.convert('1', dither=Image.FLOYDSTEINBERG)
            engraved = Image.new('RGBA', bw.size, (0, 0, 0, 0))
            black_pixels = bw.point(lambda p: 255 if p == 0 else 0).convert('L')
            engraved.putalpha(black_pixels)  # nur schwarze Pixel sichtbar

            ix = int(icon_cfg.get('x', 400) * scale)
            iy = int(icon_cfg.get('y', 445) * scale)
            mw = int(icon_cfg.get('maxWidth', 350) * scale)
            mh = int(icon_cfg.get('maxHeight', 350) * scale)
            engraved.thumbnail((mw, mh), Image.LANCZOS)
            iw, ih = engraved.size
            img.paste(engraved, (ix - iw // 2, iy - ih // 2), engraved)
        except Exception as exc:
            logger.warning('Kunden-Bild laden/dithern: %s', exc)

    # ---------- 2. Optional Text unter dem Bild ----------
    text = design.text_1 or ''
    if text:
        text_cfg = config.get('textConfig', {})
        font_paths = config.get('fontPaths') or {}
        designer_fonts = ensure_assets(store, 'designer').get('fontPaths') or {}
        all_fonts = {**designer_fonts, **font_paths}
        font_path = all_fonts.get(design.font) or _first_value(all_fonts) or ''
        x = int(text_cfg.get('line1', {}).get('x', 400) * scale)
        y = int(text_cfg.get('line1', {}).get('y', 680) * scale)
        size = int(text_cfg.get('line1', {}).get('fontSize', 48) * scale)
        color = _hex_to_rgba('#000000' if not with_background else '#4a4a4a')
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        _draw_text_with_fallback(draw, (x, y), text, font, font_path, color, anchor='mm')

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
