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
from .glm_client import MagvisGLMClient

logger = logging.getLogger(__name__)


class MagvisProductPipeline:
    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user

        from ..models import MagvisSettings
        self.magvis_settings, _ = MagvisSettings.objects.get_or_create(user=self.user)
        self.glm = MagvisGLMClient(self.user, self.magvis_settings)

    def run(self) -> dict:
        """Erstellt 2 Produkte parallel."""
        from ploom.models import PLoomSettings

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
            f"  Platzhalter wie [Name] oder „Name". KEINE Daten/Jahreszahlen.\n"
            f"- Stattdessen: Rollen-/Beziehungsbezeichnungen aus dem Topic verwenden "
            f'  (z.B. "Lieblings-Erzieherin", "Beste Freundin", "Danke, Mama"), '
            f"  oder reine Botschaft ohne Anrede.\n"
            f"- Optional 2. Zeile mit Komma getrennt für eine kurze Botschaft "
            f"  (z.B. „Danke fürs Mit-Großziehen") — KEIN Name.\n\n"
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
        base_pot_path = self._generate_base_pot(image_service, engraving_text, session)
        if not base_pot_path:
            return {'success': False, 'error': 'Basis-Topf-Generierung fehlgeschlagen', 'session': session}

        # SEO-Content
        seo_content = ai_service.generate_all_seo_content(
            keyword=self.project.topic,
            context=f'Gravur: {engraving_text}',
        ) or {}

        # Produkt anlegen (vorerst ohne Shopify)
        ploom_settings_obj = ploom_settings
        product = PLoomProduct.objects.create(
            user=self.user,
            title=seo_content.get('title') or
                  f'Geschenk {self.project.topic} — Gravierter Blumentopf {engraving_text[:50]}',
            description=seo_content.get('description', '') or '',
            seo_title=(seo_content.get('seo_title') or '')[:60],
            seo_description=(seo_content.get('seo_description') or '')[:160],
            tags=seo_content.get('tags', '') or '',
            vendor=ploom_settings_obj.default_vendor if ploom_settings_obj else 'Naturmacher',
            product_type=ploom_settings_obj.default_product_type if ploom_settings_obj else 'Blumentopf',
            price=ploom_settings_obj.default_price_komplett or 19.90 if ploom_settings_obj else 19.90,
            inventory_quantity=100,
            shopify_store=ploom_settings_obj.default_store if ploom_settings_obj else None,
            status='active',  # active = direkt veroeffentlicht in Shopify (nicht 'draft')
        )

        # Phase 1: 3 KI-Bilder
        position = 1
        for variant in KI_VARIANTS_PHASE_1:
            self._add_ki_image(product, image_service, engraving_text, variant, base_pot_path, position)
            position += 1

        # Phase 2: 3 CDN-Bilder
        for url in (self.magvis_settings.fixed_cdn_image_urls or [])[:3]:
            self._add_cdn_image(product, url, position)
            position += 1

        # Phase 3: 1 KI-Bild (nahaufnahme)
        for variant in KI_VARIANTS_PHASE_3:
            self._add_ki_image(product, image_service, engraving_text, variant, base_pot_path, position)
            position += 1

        # Erstes KI-Bild als Featured markieren
        first_image = product.images.order_by('position').first()
        if first_image:
            first_image.is_featured = True
            first_image.save(update_fields=['is_featured'])

        # Shopify-Veröffentlichung
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

        ploom_img = PLoomProductImage.objects.create(
            product=product,
            source='gemini_workflow',
            position=position,
            alt_text=f'{product.title} — {variant}',
        )
        with open(abs_path, 'rb') as fh:
            ploom_img.image.save(filename, ContentFile(fh.read()), save=True)

        MagvisImageAsset.objects.create(
            project=self.project,
            source=MagvisImageAsset.SOURCE_PRODUCT_AI,
            source_ref=str(ploom_img.id),
            src_path=ploom_img.image.path if ploom_img.image else abs_path,
            title_de=f'{product.title} — {variant}',
        )

    def _add_cdn_image(self, product, url: str, position: int) -> None:
        from ploom.models import PLoomProductImage
        ploom_img = PLoomProductImage.objects.create(
            product=product,
            source='external_url',
            external_url=url,
            position=position,
            alt_text=f'{product.title} — CDN-Bild',
        )
        MagvisImageAsset.objects.create(
            project=self.project,
            source=MagvisImageAsset.SOURCE_PRODUCT_CDN,
            source_ref=str(ploom_img.id),
            src_path='',
            src_url=url,
            title_de=f'{product.title} — CDN',
        )
