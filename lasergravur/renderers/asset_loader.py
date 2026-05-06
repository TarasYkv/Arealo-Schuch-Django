"""Asset-Loader: holt Schriftarten + Icons + Topf-Vorschau-Bilder aus dem
Shopify-Theme & CDN, cached lokal in MEDIA_ROOT/lasergravur/assets/<modell>/.

Wird beim ersten Render eines Topf-Modells aufgerufen — danach Cache.
Lädt die JS-Datei (z.B. designer-preview.js), extrahiert URLs per Regex und
downloaded alles parallel.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import requests
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)


ASSETS_BASE = os.path.join(django_settings.MEDIA_ROOT, 'lasergravur', 'assets')

# Mapping: topf_model → preview-JS-asset-key im Theme
JS_ASSETS = {
    'designer': 'assets/designer-preview.js',
    'glossy': 'assets/designer-preview-glossy.js',
    'glossywhite': 'assets/glossywhite-preview.js',
    'birthtree': 'assets/birthtree-preview.js',
    'fotogravur': 'assets/fotogravur-preview.js',
    'hochzeit': 'assets/hochzeit-preview.js',
    'hochzeit_glossy': 'assets/hochzeit-preview-glossy.js',
    'glossy_geburt': 'assets/birthtree-preview-glossy.js',
    'minipalm': 'assets/minipalm-preview.js',
    'minisolo': 'assets/minisolo-preview.js',
}

# Standard Naturmacher-Theme-ID — kann perspektivisch in LaserSettings.
DEFAULT_THEME_ID = 179765248267


def assets_dir(topf_model: str) -> str:
    """Lokaler Cache-Ordner für ein Topf-Modell."""
    p = os.path.join(ASSETS_BASE, topf_model)
    os.makedirs(p, exist_ok=True)
    os.makedirs(os.path.join(p, 'fonts'), exist_ok=True)
    os.makedirs(os.path.join(p, 'icons'), exist_ok=True)
    return p


def _fetch_theme_asset(store, asset_key: str, theme_id: int = DEFAULT_THEME_ID) -> str:
    """Lädt eine Theme-Asset-Datei aus Shopify."""
    h = {'X-Shopify-Access-Token': store.access_token}
    base = f'https://{store.shop_domain}/admin/api/2023-10'
    url = f'{base}/themes/{theme_id}/assets.json?asset[key]={asset_key}'
    r = requests.get(url, headers=h, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'Theme-Asset {asset_key}: HTTP {r.status_code}')
    return r.json().get('asset', {}).get('value', '')


def _extract_config_from_js(js_text: str) -> dict:
    """Extrahiert relevante Konfig-Blöcke aus dem preview-JS.

    Wir können nicht den ganzen JS-Code parsen — aber wir können die JSON-artigen
    Block-Definitionen (iconUrls, fontConfig, textConfig, iconConfig, baseImage)
    via Regex herausziehen.
    """
    out = {}
    # baseImage (Designer/Glossy) | defaultImage (Mini Solo) | baseImages (Mini Palm: Multi-Color)
    m = re.search(r"baseImage:\s*'([^']+)'", js_text)
    if not m:
        m = re.search(r"defaultImage:\s*'([^']+)'", js_text)
    if m:
        out['baseImage'] = m.group(1)
    else:
        # baseImages: { 'Türkis': '...', 'Rosa': '...' } — nimm erstes als Default,
        # speichere alle als baseImageVariants für späteres User-Switching
        block = re.search(r'baseImages:\s*\{([^}]+)\}', js_text, flags=re.DOTALL)
        if block:
            variants = {}
            for vm in re.finditer(r"'([^']+)'\s*:\s*'(https?://[^']+)'", block.group(1)):
                variants[vm.group(1)] = vm.group(2)
            if variants:
                out['baseImageVariants'] = variants
                out['baseImage'] = next(iter(variants.values()))
    # canvasWidth/Height
    m = re.search(r'canvasWidth:\s*(\d+)', js_text)
    if m:
        out['canvasWidth'] = int(m.group(1))
    m = re.search(r'canvasHeight:\s*(\d+)', js_text)
    if m:
        out['canvasHeight'] = int(m.group(1))

    # iconUrls (designer-Schema) ODER motivUrls (hochzeit-Schema) —
    # extrahiere {nummer: url} Paare aus dem ersten gefundenen Block
    icon_urls = {}
    for m in re.finditer(r'(\d+):\s*\'(https://cdn\.shopify[^\']+\.png[^\']*)\'', js_text):
        icon_urls[int(m.group(1))] = m.group(2)
    out['iconUrls'] = icon_urls

    # fontConfig — extrahiere Font-Name, URL
    fonts = {}
    # Match Block: 'Pixie Ring': { url: '...', previewImage: '...', name: '...' }
    for m in re.finditer(
        r"'([^']+)':\s*\{\s*url:\s*'([^']+\.ttf[^']*)'.*?name:\s*'([^']+)'\s*\}",
        js_text, flags=re.DOTALL,
    ):
        fonts[m.group(1)] = {'url': m.group(2), 'name': m.group(3)}
    out['fontConfig'] = fonts

    # textConfig — Position pro Zeile. Akzeptiert line1-4 (Designer/Mini Solo) und
    # zahl/textzeile1/textzeile2 (Glossywhite). Letztere mappen wir auf line1-3,
    # damit Designer-Renderer 1:1 funktioniert.
    text_cfg = {}
    line_aliases = [
        ('line1', ['line1', 'zahl']),
        ('line2', ['line2', 'textzeile1']),
        ('line3', ['line3', 'textzeile2']),
        ('line4', ['line4', 'textzeile3']),
    ]
    for canonical, aliases in line_aliases:
        for field in aliases:
            block_m = re.search(rf'\b{field}:\s*\{{([^}}]+)\}}', js_text)
            if not block_m:
                continue
            block = block_m.group(1)
            cfg = {}
            for key in ('x', 'y', 'fontSize'):
                mm = re.search(rf'{key}:\s*(\d+)', block)
                if mm:
                    cfg[key] = int(mm.group(1))
            ff = re.search(r"fontFamily:\s*'([^']+)'", block)
            if ff:
                cfg['fontFamily'] = ff.group(1)
            if cfg:
                text_cfg[canonical] = cfg
                break
    # color
    m = re.search(r"color:\s*'(#[0-9a-fA-F]+)'", js_text)
    if m:
        text_cfg['color'] = m.group(1)
    out['textConfig'] = text_cfg

    # iconConfig (designer) | motivConfig (hochzeit) | imageConfig (fotogravur:
    # Kunden-Bild-Position) — alle gleiche Struktur (x/y/maxWidth/maxHeight)
    icon_block = (re.search(r'iconConfig:\s*\{([^}]+)\}', js_text)
                  or re.search(r'motivConfig:\s*\{([^}]+)\}', js_text)
                  or re.search(r'imageConfig:\s*\{([^}]+)\}', js_text))
    if icon_block:
        block = icon_block.group(1)
        ic = {}
        for key in ('x', 'y', 'maxWidth', 'maxHeight'):
            mm = re.search(rf'{key}:\s*(\d+)', block)
            if mm:
                ic[key] = int(mm.group(1))
        if ic:
            out['iconConfig'] = ic

    # Hochzeit-Schema (1-2 Textfelder + Motiv) — nutzen Hochzeit, Hochzeit Glossy,
    # Glossy Geburt, Mini Palm. Aliase: 'vornamen'|'vorname'|'name' → vornamen,
    # 'datum' → datum. Erstes gefundenes Match pro Slot gewinnt.
    out['hochzeitText'] = {}
    for canonical, aliases in [('vornamen', ['vornamen', 'vorname', 'name']),
                                ('datum', ['datum'])]:
        for field in aliases:
            m = re.search(rf'\b{field}:\s*\{{([^}}]+)\}}', js_text)
            if not m:
                continue
            block = m.group(1)
            cfg = {}
            for key in ('x', 'y', 'fontSize'):
                mm = re.search(rf'{key}:\s*(\d+)', block)
                if mm:
                    cfg[key] = int(mm.group(1))
            ff = re.search(r"fontFamily:\s*'([^']+)'", block)
            if ff:
                cfg['fontFamily'] = ff.group(1)
            if cfg:
                out['hochzeitText'][canonical] = cfg
                break

    return out


def _download_to(url: str, target_path: str) -> bool:
    """Downloaded eine Datei wenn sie noch nicht existiert. True wenn vorhanden."""
    if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
        return True
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(target_path, 'wb') as f:
            f.write(r.content)
        return True
    except Exception as exc:
        logger.warning('Download %s: %s', url, exc)
        return False


def ensure_assets(store, topf_model: str) -> dict:
    """Stellt sicher dass alle Assets für ein Topf-Modell lokal vorhanden sind.

    Liefert die Konfig-dict (mit Icon+Font lokalen Pfaden statt URLs) zurück.
    Diese wird vom Renderer verwendet.
    """
    base_dir = assets_dir(topf_model)
    config_path = os.path.join(base_dir, 'config.json')

    # Wenn config.json existiert + alle Files lokal: Cache verwenden
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            if _all_local_files_present(config, base_dir):
                return config
        except Exception:
            pass

    # Sonst: JS holen, parsen, downloaden
    js_key = JS_ASSETS.get(topf_model)
    if not js_key:
        raise RuntimeError(f'Kein preview-JS für topf_model={topf_model}')
    js_text = _fetch_theme_asset(store, js_key)
    config = _extract_config_from_js(js_text)

    # Base-Image (Topf-Hintergrund)
    if config.get('baseImage'):
        target = os.path.join(base_dir, 'base.png')
        if _download_to(config['baseImage'], target):
            config['baseImagePath'] = target

    # Icons
    icon_paths = {}
    for num, url in (config.get('iconUrls') or {}).items():
        target = os.path.join(base_dir, 'icons', f'{num}.png')
        if _download_to(url, target):
            icon_paths[int(num)] = target
    config['iconPaths'] = icon_paths

    # Schriftarten
    font_paths = {}
    for font_name, font_data in (config.get('fontConfig') or {}).items():
        url = font_data.get('url', '')
        if not url:
            continue
        ext = '.ttf' if '.ttf' in url else '.otf'
        target = os.path.join(base_dir, 'fonts', f'{font_name.replace(" ", "_")}{ext}')
        if _download_to(url, target):
            font_paths[font_name] = target
    config['fontPaths'] = font_paths

    # Cache-Datei schreiben
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    logger.info('Assets für %s geladen: %d icons, %d fonts',
                topf_model, len(icon_paths), len(font_paths))
    return config


def _all_local_files_present(config: dict, base_dir: str) -> bool:
    """Quick check ob die wichtigsten Files noch da sind (Cache-Validation)."""
    base_img = config.get('baseImagePath')
    if base_img and not os.path.exists(base_img):
        return False
    # mind. 50% der Icons müssen da sein
    icon_paths = config.get('iconPaths') or {}
    if not icon_paths:
        return False
    present = sum(1 for p in icon_paths.values() if os.path.exists(p))
    if present < len(icon_paths) * 0.5:
        return False
    # mind. 1 Font muss da sein
    font_paths = config.get('fontPaths') or {}
    if not any(os.path.exists(p) for p in font_paths.values()):
        return False
    return True
