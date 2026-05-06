"""Parsed Naturmacher-Konfigurator-Properties aus Shopify-line-items in
LaserDesign-Felder.

Naturmacher's Designer-Topf-Konfigurator speichert die Personalisierung als
line_item.properties — typische Felder:
  - "Text 1", "Text 2", "Text 3", "Text 4"  (oder "Zeile 1" etc.)
  - "Schriftart" / "Font"
  - "Symbol" / "Icon"
  - "Vorschau-Bild" (URL)

Da das Naming je nach Customizer-Snippet variieren kann, mappen wir robust
mit Fuzzy-Match.
"""
from __future__ import annotations

import re

from ..models import FONT_CHOICES, ALIGN_H_CHOICES, ALIGN_V_CHOICES


VALID_FONTS = [c[0] for c in FONT_CHOICES]


def parse_design_from_properties(properties: dict, topf_model: str) -> tuple[dict, bool]:
    """Liefert (design-dict, complete-bool).

    complete=True wenn mindestens 1 Text + Schrift gefunden wurden.
    Fehlende Felder bleiben Default — Mitarbeiter muss dann im UI ergänzen.
    """
    keys_lc = {k.lower(): (k, v) for k, v in (properties or {}).items() if k}

    # ===== HOCHZEIT-Schema =====
    if topf_model == 'hochzeit':
        vornamen = _find_text(keys_lc, ['vornamen', 'namen', 'paar'])
        datum = _find_text(keys_lc, ['datum', 'hochzeitsdatum'])
        motiv = _find_text(keys_lc, ['motiv', 'icon', 'symbol'])
        motiv_id = _parse_icon_id(motiv)
        design = {
            'text_1': vornamen,
            'text_2': datum,
            'text_3': '',
            'text_4': '',
            'font': 'Allura',  # Lovely-Fallback
            'icon_id': motiv_id,
        }
        return design, bool(vornamen and datum)

    # Naturmacher nutzt 'Textzeile 1' usw. — diverse Fallbacks für andere Topf-Apps
    text_1 = _find_text(keys_lc, ['textzeile 1', 'textzeile1', 'text 1', 'text1', 'zeile 1', 'zeile1', 'gravurtext 1'])
    text_2 = _find_text(keys_lc, ['textzeile 2', 'textzeile2', 'text 2', 'text2', 'zeile 2', 'zeile2', 'gravurtext 2'])
    text_3 = _find_text(keys_lc, ['textzeile 3', 'textzeile3', 'text 3', 'text3', 'zeile 3', 'zeile3', 'gravurtext 3'])
    text_4 = _find_text(keys_lc, ['textzeile 4', 'textzeile4', 'text 4', 'text4', 'zeile 4', 'zeile4', 'gravurtext 4'])

    # Falls nur ein einziger "Text" oder "Gravur" Eintrag → text_1
    if not any([text_1, text_2, text_3, text_4]):
        single = _find_text(keys_lc, ['text', 'gravur', 'gravurtext', 'beschriftung'])
        if single:
            text_1 = single

    font_raw = _find_text(keys_lc, ['schriftart', 'schrift', 'font'])
    font = _normalize_font(font_raw) or 'Allura'

    icon_raw = _find_text(keys_lc, ['icon', 'symbol', 'motiv'])
    icon_id = _parse_icon_id(icon_raw)

    design = {
        'text_1': text_1 or '',
        'text_2': text_2 or '',
        'text_3': text_3 or '',
        'text_4': text_4 or '',
        'font': font,
        'icon_id': icon_id,
    }

    has_text = bool(text_1 or text_2 or text_3 or text_4)
    has_font = bool(font_raw)
    complete = has_text and has_font

    return design, complete


def _find_text(keys_lc: dict, candidates: list) -> str:
    """Erste Übereinstimmung (Fuzzy) liefert den Wert."""
    for cand in candidates:
        for key_lc, (orig_key, value) in keys_lc.items():
            if cand == key_lc or cand in key_lc:
                if value and str(value).strip():
                    return str(value).strip()
    return ''


def _normalize_font(font_raw: str) -> str:
    """Mappt Konfigurator-Font-Strings auf Naturmacher's 6 Standard-Fonts."""
    if not font_raw:
        return ''
    f = font_raw.lower().strip()
    for valid in VALID_FONTS:
        if valid.lower() in f or f in valid.lower():
            return valid
    return ''  # = Default Allura im Caller


def _parse_icon_id(icon_raw: str) -> int | None:
    """Aus 'Icon 42' / '42' / 'Symbol Nr 42' → 42."""
    if not icon_raw:
        return None
    m = re.search(r'\d+', str(icon_raw))
    if m:
        try:
            n = int(m.group(0))
            if 1 <= n <= 200:
                return n
        except Exception:
            pass
    return None
