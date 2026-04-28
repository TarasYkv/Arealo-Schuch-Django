"""Inhaltsverzeichnis-Generator (portiert aus blog-product-autopilot/steps/s12_toc.py).

Liefert TOC-HTML mit Lesezeit-Schätzung im Naturmacher-Stil.
"""
import re
from typing import List, Tuple


TOC_TEMPLATE = """<!-- NM-TOC-START -->
<div class="autopilot-toc" style="background:{color};border-radius:8px;padding:18px 24px;margin:28px 0;font-family:inherit;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;border-bottom:2px solid {accent};padding-bottom:6px;">
    <h3 style="margin:0;font-size:18px;color:#2a2a2a;font-weight:600;">📖 Inhaltsverzeichnis</h3>
    <span style="font-size:13px;color:#555;background:#fff;border-radius:20px;padding:4px 12px;white-space:nowrap;">ca. {minutes} Min Lesezeit</span>
  </div>
  <ol style="margin:10px 0 0 0;padding-left:22px;line-height:1.8;font-size:15px;">
{items}
  </ol>
</div>
<!-- NM-TOC-END -->
"""

ITEM_TEMPLATE = '    <li><a href="#{slug}" style="color:#2a2a2a;text-decoration:none;border-bottom:1px dotted #ccc;">{title}</a></li>'


def slugify(title: str) -> str:
    """Einfacher Slug für Anchor-IDs (Umlaute → ae/oe/ue)."""
    s = title.lower()
    s = (s.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss'))
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'abschnitt'


def estimate_minutes(text: str, wpm: int = 220) -> int:
    """Lesezeit grob schätzen (Wörter ÷ Lese-Geschwindigkeit)."""
    word_count = len(re.findall(r'\w+', text or ''))
    return max(1, round(word_count / wpm))


def render_toc(headings: List[Tuple[int, str, str]], minutes: int,
               color: str = "#F3ECDE", accent: str = "#D4AB32") -> str:
    """headings = [(level, title, slug), ...]"""
    items = "\n".join(ITEM_TEMPLATE.format(slug=slug, title=title) for _, title, slug in headings)
    return TOC_TEMPLATE.format(color=color, accent=accent, minutes=minutes, items=items)
