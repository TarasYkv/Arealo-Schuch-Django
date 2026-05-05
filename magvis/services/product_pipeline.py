"""Magvis Product-Pipeline: 2 Produkte parallel über ploom-Services.

Pro Produkt:
- Phase 1: 3 KI-Bilder (topf_gravur, lifestyle, geschenk_uebergabe)
- Phase 2: 3 fixe CDN-Bilder aus MagvisSettings.fixed_cdn_image_urls
- Phase 3: 1 KI-Bild (nahaufnahme)
- SEO-Texte via PLoomAIService
- Shopify-Veröffentlichung via PLoomShopifyService

Die 4 KI-Prompts kombinieren Naturmacher Topfgrößen-Klausel (kommt aus ploom)
mit unseren Diversity-Anchors (magvis.prompts.product_prompts).
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from django.conf import settings as django_settings
from django.core.files.base import ContentFile

from ..models import MagvisImageAsset, MagvisProject
from ..prompts.product_prompts import (
    ALL_KI_VARIANTS,
    KI_VARIANTS_PHASE_1,
    KI_VARIANTS_PHASE_3,
    scene_for,
)
from .llm_client import MagvisLLMClient

logger = logging.getLogger(__name__)


# Menschenlesbare Alt-Text-Beschreibungen pro KI-Variant.
# Frueher: "{title} — lifestyle" (technischer Suffix, Google-sichtbar, schlecht).
# Jetzt:  beschreibender deutscher Suffix, gut fuer Bildersuche + Accessibility.
VARIANT_ALT_SUFFIX = {
    'topf_gravur': 'Detailansicht der Lasergravur',
    'lifestyle': 'im Wohnambiente',
    'geschenk_uebergabe': 'als persoenliche Geschenk-Uebergabe',
    'nahaufnahme': 'Detailaufnahme',
}


def _alt_for_variant(title: str, variant: str) -> str:
    """Sauberer Alt-Text: '{title} — {beschreibender Suffix}', max 125 char."""
    suffix = VARIANT_ALT_SUFFIX.get(variant, '')
    base = (title or '').strip()
    if not suffix:
        return base[:125]
    full = f'{base} — {suffix}'
    # Wenn zu lang, lieber Suffix kuerzen statt Title.
    if len(full) > 125:
        return f'{base[:125 - len(suffix) - 5]}... — {suffix}'
    return full


# Statisches Naturmacher-Hersteller-HTML (Pflichtangabe Produktbundle).
HERSTELLER_INFO_HTML = (
    '<p><span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>Bei diesem Artikel handelt es sich um ein Produktbundle.</span>'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    '<span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>Die Bundlebestandteile sind&nbsp;</span>'
    '<span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 12px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>'
    '<a href="https://cdn.shopify.com/s/files/1/0696/9494/7595/files/produktsicherheit.pdf?v=1736755197" target="_blank" rel="noopener noreferrer">hier</a></span>'
    '<span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>aufgeführt.</span>'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    '<span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>Verantwortlich für die Zusammenstellung des Produktbundles ist:</span>'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    'Naturmacher, Taras Yuzkiv'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    '<span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>Schillerstraße 6 64625 Bensheim</span>'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    '<span style=\'text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, ";\'>E-Mail: kontakt@naturmacher.de</span>'
    '<br style="text-align: start;color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);font-size: 15px;font-family: Proximanova, -apple-system, BlinkMacSystemFont, &quot;;">'
    '<br></p>'
)
WARN_HINWEISE = 'kein Spielzeug'


class MagvisProductPipeline:
    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user

        from ..models import MagvisSettings
        self.magvis_settings, _ = MagvisSettings.objects.get_or_create(user=self.user)
        self.glm = MagvisLLMClient(self.user, self.magvis_settings)

    def run(self) -> dict:
        """Erstellt 2 Produkte parallel — idempotent gegen Re-Trigger.

        Wenn beide Magvis-Produkte bereits Shopify-IDs haben, wird der Stage
        komplett übersprungen (verhindert Doppel-Erstellung bei Worker-Crash
        + Celery-Retry).
        """
        from ploom.models import PLoomSettings

        if (self.project.product_1 and self.project.product_1.shopify_product_id
                and self.project.product_2 and self.project.product_2.shopify_product_id):
            self.project.log_stage(
                'products',
                f'⏭️ Beide Produkte bereits in Shopify '
                f'({self.project.product_1.shopify_product_id}, '
                f'{self.project.product_2.shopify_product_id}) — Stage übersprungen',
            )
            return {'success': True, 'skipped': True}

        if not self.magvis_settings.default_ploom_settings:
            self.magvis_settings.default_ploom_settings = PLoomSettings.objects.filter(
                user=self.user
            ).first()
            if self.magvis_settings.default_ploom_settings:
                self.magvis_settings.save(update_fields=['default_ploom_settings'])
            else:
                raise RuntimeError(
                    'Keine PLoomSettings für diesen User gefunden. '
                    'Bitte unter /ploom/einstellungen/ konfigurieren (inkl. Referenz-Topf-Foto + Shopify-Store).'
                )

        engraving_texts = self._generate_engraving_texts()
        if len(engraving_texts) < 2:
            raise RuntimeError(f'GLM lieferte nur {len(engraving_texts)} Gravur-Texte (erwartet: 2)')

        results = []
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {
                ex.submit(self._build_one_product, idx, text): idx
                for idx, text in enumerate(engraving_texts[:2], start=1)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results.append((idx, fut.result()))
                except Exception as exc:
                    logger.exception('Produkt %s failed', idx)
                    results.append((idx, {'success': False, 'error': str(exc)}))

        results.sort(key=lambda t: t[0])
        for idx, result in results:
            if result.get('success'):
                product = result['product']
                if idx == 1:
                    self.project.product_1 = product
                    self.project.ploom_session_1 = result.get('session')
                else:
                    self.project.product_2 = product
                    self.project.ploom_session_2 = result.get('session')
        self.project.save(update_fields=['product_1', 'product_2',
                                         'ploom_session_1', 'ploom_session_2',
                                         'updated_at'])

        return {'success': all(r[1].get('success') for r in results), 'results': results}

    def _generate_kurzbeschreibung_eigene(self, engraving_text: str) -> list[str]:
        """3 knackige Bullet-Highlights als List-Field (Shopify-Metafeld)."""
        prompt = (
            f'Erstelle 3 sehr knappe, emotionale Highlight-Punkte für einen '
            f'personalisierten Blumentopf mit Gravur "{engraving_text}" '
            f'zum Thema "{self.project.topic}".\n\n'
            f"Format-Regeln:\n"
            f"- Jeder Punkt 2-5 Wörter, AKTIV formuliert.\n"
            f"- KEIN Punkt am Ende, KEIN Substantiv-Marketing-Floskel "
            f'  ("hochwertig", "premium" verboten).\n'
            f'- Beispiele: "Bereit zum Verschenken", "Geschenk das im Gedächtnis bleibt", '
            f'  "Persönlich graviert", "Mit Liebe gefertigt", "Sofort einsatzbereit".\n\n'
            f'Antwort als JSON-Array mit 3 Strings: ["...", "...", "..."]'
        )
        try:
            data = self.glm.json_chat(prompt, temperature=0.6)
            if isinstance(data, list) and len(data) >= 1:
                return [str(s).strip() for s in data[:3] if s]
        except Exception as exc:
            logger.warning('Kurzbeschreibung-Generation: %s', exc)
        # Fallback
        return [
            'Bereit zum Verschenken',
            'Geschenk, das im Gedächtnis bleibt',
            'Persönlich für dich graviert',
        ]

    def _override_seo_mid_volume(self, base_seo: dict, engraving_text: str) -> dict | None:
        """Erstellt SEO-Inhalte im Naturmacher-Stil: strukturierte HTML-Beschreibung
        mit Intro + Highlights + Material + Anlässen + CTA, plus Mid-Volume-Long-Tail-Title.

        Format orientiert sich an mein-blumentopf-designer-geschenk-blumentopf-graviert.
        """
        prompt = (
            f"Erstelle vollständigen Produktinhalt für einen personalisierten Blumentopf "
            f"mit Lasergravur auf Naturmacher.de.\n\n"
            f'Thema/Anlass: "{self.project.topic}"\n'
            f'Gravur auf dem Topf: "{engraving_text}"\n\n'
            f"=== TITLE ===\n"
            f"60-80 Zeichen, Long-Tail-Kombi (Produkt + Anlass + Zielgruppe). "
            f"Beispiel: 'Personalisierter Blumentopf — Geschenk Erzieherin Abschied'.\n"
            f"KEIN generisches 'Geschenk' allein, immer mit Spezifität zum Topic.\n\n"
            f"=== DESCRIPTION (HTML, Naturmacher-Stil) ===\n"
            f"Strukturiert mit Absätzen, Listen, sub-headings — KEIN Fließtext-Block.\n"
            f"Pflicht-Sektionen, in dieser Reihenfolge:\n"
            f"1. <p>Eingangs-Absatz (2-3 Sätze, emotional, Anlass aufgreifen).</p>\n"
            f"2. <h3>Das macht diesen Topf besonders</h3><ul><li>4-5 Bullets mit USPs/Highlights</li></ul>\n"
            f"   Beispiel-Bullets: 'Persönliche Lasergravur — kratzfest und langlebig', "
            f"   'Hochwertige Keramik aus deutscher Manufaktur', 'Maße: ca. 14 cm Höhe & Durchmesser', "
            f"   'Liebevoll handverpackt mit Pflegeanleitung', 'Sofort verschenkbar — Karte & Geschenknotiz inklusive'.\n"
            f"3. <h3>Perfekt als Geschenk für</h3><ul><li>3-5 spezifische Anlässe rund um Topic</li></ul>\n"
            f"4. <h3>Material & Fertigung</h3><p>Kurzer Absatz: Cremefarbene Keramik, "
            f"   Lasergravur in unserer Manufaktur in Bensheim, witterungsbeständig.</p>\n"
            f"5. <p>Abschluss-CTA mit Wertgefühl (1-2 Sätze, ohne 'Jetzt kaufen!'-Plattheit).</p>\n\n"
            f"Kein Marketing-Geschwafel ('hochwertig', 'premium' nur in Material-Block ok). "
            f"Keine Emojis im HTML. Saubere Tags: <p>, <h3>, <ul>, <li>, <strong>.\n\n"
            f"=== SEO-TITLE ===\n"
            f"50-65 Zeichen, Long-Tail wie title aber kürzer, Keyword vorne.\n\n"
            f"=== SEO-DESCRIPTION ===\n"
            f"140-160 Zeichen Meta-Tag: Long-Tail + USP + CTA in einem Satz.\n\n"
            f"=== TAGS ===\n"
            f"6-9 Mid-Tail-Tags Komma-separiert. Mix: '{self.project.topic} Geschenk', "
            f"'Blumentopf mit Gravur', 'personalisiertes Geschenk', '{self.project.topic} Abschied', "
            f"'Lasergravur Topf', etc.\n\n"
            f"=== AUSGABE ===\n"
            f"Antwort als JSON-Objekt:\n"
            f'{{"title": "...", "description": "<p>...</p><h3>...</h3>...", '
            f'"seo_title": "...", "seo_description": "...", "tags": "..."}}\n'
            f"Wichtig: description-Wert ist gültiges HTML als String (Tags escaped wo nötig).\n"
        )
        try:
            data = self.glm.json_chat(prompt, temperature=0.55)
            if not isinstance(data, dict):
                return None
            desc = data.get('description') or base_seo.get('description', '')
            # Sicherstellen dass HTML-Struktur drin ist (Fallback wenn LLM Plain-Text liefert)
            if desc and '<' not in desc and '>' not in desc:
                paras = [p.strip() for p in desc.split('\n\n') if p.strip()]
                desc = ''.join(f'<p>{p}</p>' for p in paras) if paras else f'<p>{desc}</p>'
            return {
                'title': data.get('title') or base_seo.get('title'),
                'description': desc,
                'seo_title': (data.get('seo_title') or base_seo.get('seo_title') or '')[:70],
                'seo_description': (data.get('seo_description') or base_seo.get('seo_description') or '')[:160],
                'tags': data.get('tags') or base_seo.get('tags', ''),
            }
        except Exception as exc:
            logger.warning('Mid-Volume-SEO-Override fehlgeschlagen: %s', exc)
            return None

    def _generate_engraving_texts(self) -> list[str]:
        """Lässt GLM 2 unterschiedliche Gravur-Vorschläge zum Topic generieren."""
        prompt = (
            f"Gib mir GENAU 2 unterschiedliche, kurze deutsche Geschenk-Gravur-Texte "
            f"(je max. 25 Zeichen, je 1-2 Zeilen) für einen personalisierten "
            f"Blumentopf zum Thema \"{self.project.topic}\".\n\n"
            f"Anforderungen:\n"
            f"- Persönlich, herzlich, NICHT kitschig.\n"
            f"- Beide Texte deutlich verschieden im Stil.\n"
            f"- VERBOTEN: Konkrete Eigennamen (Anna, Max, Lisa, Tom, ...). Auch keine "
            f"  Platzhalter wie [Name] oder Name-Variablen. KEINE Daten/Jahreszahlen.\n"
            f"- Stattdessen: Rollen-/Beziehungsbezeichnungen aus dem Topic verwenden "
            f"  (z.B. 'Lieblings-Erzieherin', 'Beste Freundin', 'Danke, Mama'), "
            f"  oder reine Botschaft ohne Anrede.\n"
            f"- Optional 2. Zeile mit Komma getrennt für eine kurze Botschaft "
            f"  (z.B. 'Danke fürs Mit-Großziehen') — KEIN Name.\n\n"
            f'Antworte nur als JSON-Array mit 2 Strings: ["Text 1", "Text 2"]'
        )
        try:
            data = self.glm.json_chat(prompt, temperature=0.85)
            if isinstance(data, list):
                return [str(t).strip() for t in data if t]
        except Exception as exc:
            logger.warning('Engraving-text-generation fehlgeschlagen: %s — Fallback', exc)
        # Fallback
        return [
            f'Für meine\nLieblings-{self.project.topic}',
            f'Danke,\n{self.project.topic}',
        ]

    def _build_one_product(self, index: int, engraving_text: str) -> dict:
        """Baut ein einzelnes Produkt mit 4 KI- + 3 CDN-Bildern."""
        from ploom.models import PLoomProduct, PLoomProductImage, PLoomWorkflowSession
        from ploom.services.ai_service import PLoomAIService
        from ploom.services.image_service import PLoomImageService

        ploom_settings = self.magvis_settings.default_ploom_settings
        image_service = PLoomImageService(self.user)
        ai_service = PLoomAIService(self.user)

        # Gravur-Workflow-Session anlegen (für ploom-Konsistenz)
        session = PLoomWorkflowSession.objects.create(
            user=self.user,
            keyword=self.project.topic[:200],
            selected_text=engraving_text,
        )

        # Schritt 1: Basis-Topf
        self.project.log_stage('products', f'🪴 Produkt {index}: Basis-Topf via Gemini')
        base_pot_path = self._generate_base_pot(image_service, engraving_text, session)
        if not base_pot_path:
            return {'success': False, 'error': 'Basis-Topf-Generierung fehlgeschlagen', 'session': session}

        # SEO-Content — wie OpenClaw mit product_description_context als Hint
        ploom_settings_obj = ploom_settings
        ctx = (ploom_settings_obj.product_description_context if ploom_settings_obj else '') or ''
        keyword_ctx = f'{self.project.topic} - Gravur: {engraving_text}'
        seo_content = ai_service.generate_all_seo_content(
            keyword=keyword_ctx, language='de', context=ctx,
        ) or {}
        seo_content = self._override_seo_mid_volume(seo_content, engraving_text) or seo_content

        # 3 Kurzbeschreibung-Highlights via GLM (List-Field)
        kurzbeschreibung = self._generate_kurzbeschreibung_eigene(engraving_text)

        # Produkt anlegen — alle OpenClaw-Defaults aus PLoomSettings übernehmen
        product = PLoomProduct.objects.create(
            user=self.user,
            title=(seo_content.get('title') or
                   f'Geschenk {self.project.topic} — Gravierter Blumentopf {engraving_text[:50]}')[:255],
            description=seo_content.get('description', '') or '',
            seo_title=(seo_content.get('seo_title') or seo_content.get('title') or '')[:70],
            seo_description=(seo_content.get('seo_description') or '')[:160],
            tags=seo_content.get('tags', '') or 'personaliserbar,Name(n)',
            vendor=ploom_settings_obj.default_vendor if ploom_settings_obj else 'Naturmacher',
            product_type=ploom_settings_obj.default_product_type if ploom_settings_obj else '',
            collection_id=ploom_settings_obj.default_collection_id if ploom_settings_obj else '',
            collection_name=ploom_settings_obj.default_collection_name if ploom_settings_obj else '',
            weight=ploom_settings_obj.default_weight if ploom_settings_obj else 0.95,
            weight_unit=ploom_settings_obj.default_weight_unit if ploom_settings_obj else 'kg',
            # 'creative_design' — Magvis-Topf ist NICHT personalisierbar
            # (hat bereits fixe Gravur), daher KEIN designer-mit-assistent.
            template_suffix=ploom_settings_obj.default_template_suffix or 'creative_design',
            inventory_quantity=100,
            shopify_store=ploom_settings_obj.default_store if ploom_settings_obj else None,
            status='active',
            product_metafields={
                'custom.herstellerinformationen_': HERSTELLER_INFO_HTML,
                'custom._warn_hinweise': WARN_HINWEISE,
                'custom.kurzbeschreibung_eigene': kurzbeschreibung,
            },
        )

        # Varianten erstellen — wie OpenClaw 'Nur Topf' + 'Komplettset'
        from ploom.models import PLoomProductVariant
        uid_hex = str(product.id).replace('-', '')[:8].upper()
        price_topf = float(ploom_settings_obj.default_price_topf) if (
            ploom_settings_obj and ploom_settings_obj.default_price_topf) else 24.99
        price_komplett = float(ploom_settings_obj.default_price_komplett) if (
            ploom_settings_obj and ploom_settings_obj.default_price_komplett) else 34.99
        variant_specs = [
            {'title': 'Nur Topf', 'price': price_topf, 'image_ref': 'ki:lifestyle'},
            {'title': 'Komplettset', 'price': price_komplett, 'image_ref': 'cdn:0'},
        ]
        variant_uuid_by_idx = []
        for v_idx, v_spec in enumerate(variant_specs):
            sku_suffix = chr(ord('A') + v_idx)
            v_obj = PLoomProductVariant.objects.create(
                product=product,
                title=v_spec['title'],
                price=v_spec['price'],
                sku=f'NM{uid_hex}{sku_suffix}',
                option1_name='Ausführung',
                option1_value=v_spec['title'],
                position=v_idx + 1,
            )
            variant_uuid_by_idx.append(str(v_obj.id))
        # Bild→Variant-Mapping
        self._ki_to_variant = {}
        self._cdn_to_variant = {}
        for v_idx, v_spec in enumerate(variant_specs):
            ref = v_spec.get('image_ref', '')
            if not ref:
                continue
            if ref.startswith('ki:'):
                self._ki_to_variant[ref[3:]] = variant_uuid_by_idx[v_idx]
            elif ref.startswith('cdn:'):
                try:
                    self._cdn_to_variant[int(ref[4:])] = variant_uuid_by_idx[v_idx]
                except ValueError:
                    pass

        # Phase 1: 3 KI-Bilder
        position = 1
        for i, variant in enumerate(KI_VARIANTS_PHASE_1, start=1):
            self.project.log_stage('products', f'🖼️ Produkt {index}: KI-Bild Phase 1 ({i}/3): {variant}')
            self._add_ki_image(product, image_service, engraving_text, variant, base_pot_path, position)
            position += 1

        # Phase 2: 3 CDN-Bilder
        self.project.log_stage('products', f'🪧 Produkt {index}: 3 fixe CDN-Bilder anhaengen')
        for cdn_idx, url in enumerate((self.magvis_settings.fixed_cdn_image_urls or [])[:3]):
            self._add_cdn_image(product, url, position, cdn_idx=cdn_idx)
            position += 1

        # Phase 3: 1 KI-Bild (nahaufnahme)
        for variant in KI_VARIANTS_PHASE_3:
            self.project.log_stage('products', f'🔍 Produkt {index}: Detail-Macro ({variant})')
            self._add_ki_image(product, image_service, engraving_text, variant, base_pot_path, position)
            position += 1

        # Erstes KI-Bild als Featured markieren
        first_image = product.images.order_by('position').first()
        if first_image:
            first_image.is_featured = True
            first_image.save(update_fields=['is_featured'])

        # Shopify-Veröffentlichung
        self.project.log_stage('products', f'🛒 Produkt {index}: Shopify-Veröffentlichung')
        shopify_url = ''
        try:
            from ploom.services.shopify_service import PLoomShopifyService
            if product.shopify_store:
                shopify = PLoomShopifyService(product.shopify_store)
                ok, shopify_id, msg = shopify.create_draft_product(product)
                if ok:
                    product.shopify_product_id = shopify_id
                    # status bleibt 'active' (so wurde Shopify-Produkt erstellt)
                    product.save(update_fields=['shopify_product_id'])
                    # Sales-Channels publizieren
                    ok2, pubs, _ = shopify.get_publications()
                    if ok2 and pubs:
                        publication_ids = [p['id'] for p in pubs]
                        try:
                            shopify.publish_to_channels(shopify_id, publication_ids)
                        except Exception as exc:
                            logger.warning('publish_to_channels: %s', exc)
                    # Variant-Bilder explizit setzen (image.variant_ids reicht in Shopify nicht)
                    try:
                        self._set_variant_images_on_shopify(product, shopify_id)
                    except Exception as exc:
                        logger.warning('Variant-Image-Setzung: %s', exc)
                    # Video als letztes Media-Item anhängen
                    try:
                        self._attach_video_to_shopify_product(product, shopify_id)
                    except Exception as exc:
                        logger.warning('Video-Anhang: %s', exc)
                    shopify_url = (
                        f'https://{product.shopify_store.shop_domain}/products/{product.handle}'
                        if hasattr(product, 'handle') and product.handle
                        else f'https://{product.shopify_store.shop_domain}/admin/products/{shopify_id}'
                    )
                else:
                    logger.warning('Shopify-Upload fehlgeschlagen: %s', msg)
        except Exception as exc:
            logger.exception('Shopify-Publish fehlgeschlagen')

        # Session aktualisieren
        session.product = product
        session.current_step = 'completed'
        session.base_pot_image_path = base_pot_path
        session.save(update_fields=['product', 'current_step', 'base_pot_image_path'])

        return {
            'success': True,
            'product': product,
            'session': session,
            'shopify_url': shopify_url,
        }

    # ----------------------------------------------------------------- helpers

    def _generate_base_pot(self, image_service, engraving_text: str, session) -> Optional[str]:
        """Generiert das Basis-Topf-Bild und speichert es nach MEDIA_ROOT."""
        result = image_service.generate_base_pot(engraving_text)
        if not result.get('success') or not result.get('image_data'):
            logger.error('Base-Pot fehlgeschlagen: %s', result.get('error'))
            return None
        rel_dir = os.path.join('magvis', 'product_images', str(self.project.id))
        abs_dir = os.path.join(django_settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        filename = f'base_pot_{uuid.uuid4().hex[:10]}.png'
        rel_path = os.path.join(rel_dir, filename).replace('\\', '/')
        abs_path = os.path.join(django_settings.MEDIA_ROOT, rel_path)
        with open(abs_path, 'wb') as fh:
            fh.write(base64.b64decode(result['image_data']))
        return rel_path

    def _add_ki_image(self, product, image_service, engraving_text: str,
                      variant: str, base_pot_path: str, position: int) -> None:
        from ploom.models import PLoomProductImage

        scene = scene_for(variant)
        result = image_service.generate_pot_image(
            engraving_text=engraving_text,
            scene_description=scene,
            variant_type=variant,
            base_pot_image_path=base_pot_path,
        )
        if not result.get('success') or not result.get('image_data'):
            logger.warning('KI-Bild %s fehlgeschlagen: %s', variant, result.get('error'))
            return

        # Speichern
        rel_dir = os.path.join('magvis', 'product_images', str(self.project.id))
        abs_dir = os.path.join(django_settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        filename = f'{variant}_{uuid.uuid4().hex[:10]}.png'
        rel_path = os.path.join(rel_dir, filename).replace('\\', '/')
        abs_path = os.path.join(django_settings.MEDIA_ROOT, rel_path)
        with open(abs_path, 'wb') as fh:
            fh.write(base64.b64decode(result['image_data']))

        # Variant-Mapping: KI-Bild dieses Typs → variant_id
        variant_id = (self._ki_to_variant.get(variant, '')
                      if hasattr(self, '_ki_to_variant') else '')
        clean_alt = _alt_for_variant(product.title, variant)
        ploom_img = PLoomProductImage.objects.create(
            product=product,
            source='gemini_workflow',
            position=position,
            alt_text=clean_alt,
            variant_id=variant_id,
        )
        with open(abs_path, 'rb') as fh:
            ploom_img.image.save(filename, ContentFile(fh.read()), save=True)

        MagvisImageAsset.objects.create(
            project=self.project,
            source=MagvisImageAsset.SOURCE_PRODUCT_AI,
            source_ref=str(ploom_img.id),
            src_path=ploom_img.image.path if ploom_img.image else abs_path,
            title_de=clean_alt,
        )

    def _add_cdn_image(self, product, url: str, position: int, cdn_idx: int = 0) -> None:
        from ploom.models import PLoomProductImage
        variant_id = (self._cdn_to_variant.get(cdn_idx, '')
                      if hasattr(self, '_cdn_to_variant') else '')
        # CDN-Bilder bekommen den reinen Produkttitel als Alt — der technische
        # 'CDN-Bild'-Suffix ist Google-sichtbar gewesen und brachte keine SEO-Info.
        clean_alt = (product.title or '').strip()[:125]
        ploom_img = PLoomProductImage.objects.create(
            product=product,
            source='external_url',
            external_url=url,
            position=position,
            alt_text=clean_alt,
            variant_id=variant_id,
        )
        MagvisImageAsset.objects.create(
            project=self.project,
            source=MagvisImageAsset.SOURCE_PRODUCT_CDN,
            source_ref=str(ploom_img.id),
            src_path='',
            src_url=url,
            title_de=clean_alt,
        )

    # ---- Shopify-Post-Process: Variant-Bilder + Video --------------------

    NATURMACHER_VIDEO_URL = (
        'https://cdn.shopify.com/videos/c/o/v/4255d323970f47b9924c98fb0829768e.mp4'
    )

    def _set_variant_images_on_shopify(self, product, shopify_id: str) -> None:
        """Setzt variant.image_id direkt auf Shopify, da der image.variant_ids-Pfad
        in der ploom-Pipeline nicht zuverlässig ankommt.

        Map: 'Nur Topf' -> erstes KI-Lifestyle-Bild, 'Komplettset' -> erstes CDN-Bild.
        """
        import requests as _rq
        store = product.shopify_store
        if not store:
            return
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        h = {'X-Shopify-Access-Token': store.access_token,
             'Content-Type': 'application/json'}
        r = _rq.get(f'{base}/products/{shopify_id}.json', headers=h, timeout=20)
        sp = r.json().get('product', {})
        sp_imgs = sorted(sp.get('images', []), key=lambda x: x.get('position', 99))
        sp_variants = sp.get('variants', [])
        local_imgs = list(product.images.all().order_by('position'))
        if not sp_imgs or not local_imgs or len(sp_imgs) != len(local_imgs):
            return
        pos_to_shopify = {i + 1: sp['id'] for i, sp in enumerate(sp_imgs)}
        topf_img = komplett_img = None
        for li in local_imgs:
            name = (li.image.name if li.image else '') + (li.external_url or '')
            if 'lifestyle' in name and not topf_img:
                topf_img = pos_to_shopify.get(li.position)
            elif li.source == 'external_url' and not komplett_img:
                komplett_img = pos_to_shopify.get(li.position)
        if not topf_img and local_imgs:
            for li in local_imgs:
                if li.source == 'gemini_workflow':
                    topf_img = pos_to_shopify.get(li.position)
                    break
        for sv in sp_variants:
            target = topf_img if sv['title'] == 'Nur Topf' else (
                komplett_img if sv['title'] == 'Komplettset' else None)
            if not target:
                continue
            _rq.put(
                f'{base}/variants/{sv["id"]}.json',
                headers=h,
                json={'variant': {'id': sv['id'], 'image_id': target}},
                timeout=20,
            )

    def _attach_video_to_shopify_product(self, product, shopify_id: str) -> None:
        """Hängt das Naturmacher-Video als letztes Media-Item ans Produkt.

        Nutzt stagedUploadsCreate (Shopify lehnt direkte cdn.shopify.com-URLs
        bei productCreateMedia ab) + productCreateMedia mit resourceUrl.
        Video wird nur einmal pro Pipeline-Run heruntergeladen (Klassen-Cache).
        """
        import requests as _rq
        store = product.shopify_store
        if not store:
            return
        # Video lokal cachen (Klassen-Attribut, einmal pro Run)
        cache_path = getattr(self, '_video_cache_path', None)
        if not cache_path or not os.path.exists(cache_path):
            cache_path = '/tmp/naturmacher_product_video.mp4'
            if not os.path.exists(cache_path):
                vr = _rq.get(self.NATURMACHER_VIDEO_URL, timeout=180, stream=True)
                with open(cache_path, 'wb') as fh:
                    for chunk in vr.iter_content(8192):
                        fh.write(chunk)
            self._video_cache_path = cache_path
        video_size = os.path.getsize(cache_path)
        with open(cache_path, 'rb') as fh:
            video_bytes = fh.read()

        graphql_url = f'https://{store.shop_domain}/admin/api/2023-10/graphql.json'
        h = {'X-Shopify-Access-Token': store.access_token,
             'Content-Type': 'application/json'}

        stage_q = (
            'mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {'
            ' stagedUploadsCreate(input: $input) {'
            ' stagedTargets { url resourceUrl parameters { name value } }'
            ' userErrors { field message } } }'
        )
        sp = _rq.post(graphql_url, headers=h, json={
            'query': stage_q,
            'variables': {'input': [{
                'filename': 'naturmacher_video.mp4',
                'mimeType': 'video/mp4',
                'resource': 'VIDEO',
                'fileSize': str(video_size),
                'httpMethod': 'POST',
            }]},
        }, timeout=30).json()
        targets = (sp.get('data') or {}).get('stagedUploadsCreate', {}).get('stagedTargets') or []
        if not targets:
            return
        t = targets[0]
        files_data = {p['name']: (None, p['value']) for p in t.get('parameters') or []}
        files_data['file'] = ('naturmacher_video.mp4', video_bytes, 'video/mp4')
        up = _rq.post(t['url'], files=files_data, timeout=180)
        if up.status_code not in (200, 201, 204):
            return
        create_q = (
            'mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {'
            ' productCreateMedia(productId: $productId, media: $media) {'
            ' media { ... on Video { id status } } mediaUserErrors { field message } } }'
        )
        _rq.post(graphql_url, headers=h, json={
            'query': create_q,
            'variables': {
                'productId': f'gid://shopify/Product/{shopify_id}',
                'media': [{
                    'originalSource': t['resourceUrl'],
                    'mediaContentType': 'VIDEO',
                    'alt': 'Naturmacher-Produktvideo',
                }],
            },
        }, timeout=30)
