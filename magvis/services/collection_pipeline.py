"""Magvis Collection-Pipeline: Stage zwischen Produkten und Blog.

Workflow:
1. Hole alle bestehenden Shopify-Custom-Collections.
2. GLM bewertet, ob bereits eine thematisch passende existiert (Schwelle 0.7+).
3a. Wenn Match: Magvis-Produkte zur bestehenden Kollektion hinzufügen, fertig.
3b. Wenn kein Match: Neue Custom-Collection erstellen mit:
   - GLM-Texten (Title, kurze_kategoriebeschreibung, body_html mit Cross-Links zu 2-3 verwandten Kollektionen, SEO-Felder)
   - Gemini-2.5-flash-image Bild im Naturmacher-Stil + alt-Text
   - Template `blumentopf_unterkategorie`
   - Magvis-Produkte zugewiesen
   - Auf allen Sales-Channels veröffentlicht
   - Metafelder gesetzt (custom.kurze_kategoriebeschreibung als Rich-Text-JSON)

Wiederverwendet:
- ploom.PLoomShopifyService für Auth/HTTP-Pattern (manche Endpoints sind aber neu).
- magvis.services.llm_client.MagvisLLMClient
- magvis.services.gemini_helper.MagvisGeminiHelper
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import uuid

from django.conf import settings as django_settings
from django.utils.text import slugify

from ..models import MagvisCollection, MagvisProject, MagvisSettings
from .gemini_helper import MagvisGeminiHelper
from .llm_client import MagvisLLMClient

logger = logging.getLogger(__name__)


class MagvisCollectionPipeline:
    """Erstellt oder findet eine Shopify-Kollektion für ein Magvis-Projekt."""

    DEFAULT_TEMPLATE = 'blumentopf_unterkategorie'
    MATCH_THRESHOLD = 0.7

    def __init__(self, project: MagvisProject, additional_product_ids: list | None = None):
        self.project = project
        self.user = project.user
        self.additional_product_ids = additional_product_ids or []
        self.magvis_settings, _ = MagvisSettings.objects.get_or_create(user=self.user)
        self.glm = MagvisLLMClient(self.user, self.magvis_settings)
        self.gemini = MagvisGeminiHelper(self.user, self.magvis_settings)

    # ---------------------------------------------------------------- public

    def run(self) -> dict:
        store = self._get_shopify_store()
        if not store:
            return {'success': False, 'error': 'Kein Shopify-Store konfiguriert'}

        # MagvisCollection-Eintrag holen oder anlegen
        coll, _ = MagvisCollection.objects.get_or_create(project=self.project)

        # Idempotent: wenn schon erfolgreich gelaufen
        if coll.shopify_collection_id:
            self.project.log_stage('collection', f'⏭️ Kollektion bereits gesetzt ({coll.shopify_collection_id})')
            return {'success': True, 'collection': coll, 'skipped': True}

        # Produktliste sammeln (2 Magvis-Produkte + manuelle Erweiterung)
        product_shopify_ids = self._collect_product_ids()
        if not product_shopify_ids:
            return {'success': False, 'error': 'Keine veröffentlichten Produkte für die Kollektion'}

        # 1) Bestehende Kollektionen holen
        all_collections = self._fetch_all_custom_collections(store)
        self.project.log_stage('collection', f'🔍 {len(all_collections)} bestehende Custom-Collections geladen')

        # 2) GLM-Match
        match_result = self._find_matching_collection(all_collections)

        if match_result and match_result.get('handle'):
            # 3a) Bestehende Kollektion erweitern
            matched = next(
                (c for c in all_collections if c['handle'] == match_result['handle']),
                None,
            )
            if matched:
                coll.was_existing = True
                coll.shopify_collection_id = str(matched['id'])
                coll.shopify_handle = matched['handle']
                coll.title = matched.get('title', '')
                coll.shopify_url = f'https://{store.shop_domain}/collections/{matched["handle"]}'
                coll.save()
                added = self._assign_products_to_collection(store, coll.shopify_collection_id, product_shopify_ids)
                coll.assigned_product_ids = added
                coll.save(update_fields=['assigned_product_ids', 'updated_at'])
                self.project.log_stage(
                    'collection',
                    f'🔗 Match auf bestehende Kollektion "{coll.title}" — {len(added)} Produkte zugewiesen',
                )
                return {'success': True, 'collection': coll}

        # 3b) Neue Kollektion erstellen
        return self._create_new_collection(store, coll, all_collections, product_shopify_ids)

    # --------------------------------------------------------------- helpers

    def _get_shopify_store(self):
        from ploom.models import PLoomSettings
        ps = PLoomSettings.objects.filter(user=self.user).first()
        return ps.default_store if ps else None

    def _collect_product_ids(self) -> list:
        """Sammelt Shopify-Product-IDs der Magvis-Produkte + Stamm-Sortiment + manuelle Ergänzungen.

        Quellen (in dieser Reihenfolge):
        1. self.project.product_1, product_2 (immer dabei)
        2. MagvisSettings.default_collection_extra_product_handles (Stamm)
        3. self.additional_product_ids (Wizard-Multi-Select)
        """
        ids = []
        for prod in (self.project.product_1, self.project.product_2):
            if prod and prod.shopify_product_id:
                ids.append(str(prod.shopify_product_id))

        # Stamm-Handles auflösen
        store = self._get_shopify_store()
        stamm_handles = list(self.magvis_settings.default_collection_extra_product_handles or [])
        for h in stamm_handles:
            sid = self._resolve_product_handle(store, h)
            if sid and str(sid) not in ids:
                ids.append(str(sid))

        # Manuelle Ergänzungen
        for pid in self.additional_product_ids:
            if pid and str(pid) not in ids:
                ids.append(str(pid))
        return ids

    def _resolve_product_handle(self, store, handle: str) -> str | None:
        """Auflösung Shopify-Handle → Product-ID via REST."""
        if not store or not handle:
            return None
        import requests
        h = {'X-Shopify-Access-Token': store.access_token}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        try:
            r = requests.get(f'{base}/products.json?handle={handle}&fields=id,handle',
                             headers=h, timeout=15)
            if r.status_code == 200:
                prods = r.json().get('products', [])
                if prods:
                    return str(prods[0]['id'])
        except Exception as exc:
            logger.warning('Handle-Resolver für %s: %s', handle, exc)
        return None

    def _fetch_all_custom_collections(self, store) -> list:
        """Paginierter Pull aller Custom-Collections (id, handle, title, body_html-snippet)."""
        import requests
        h = {'X-Shopify-Access-Token': store.access_token}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        out = []
        page_url = f'{base}/custom_collections.json?limit=250'
        for _ in range(15):  # Sicherheitsstop
            r = requests.get(page_url, headers=h, timeout=20)
            if r.status_code != 200:
                break
            data = r.json().get('custom_collections', [])
            for c in data:
                out.append({
                    'id': c['id'],
                    'handle': c['handle'],
                    'title': c['title'],
                    'body_snippet': re.sub(r'<[^>]+>', ' ', c.get('body_html', '') or '')[:300],
                })
            link = r.headers.get('Link', '')
            m = re.search(r'<([^>]+)>;\s*rel="next"', link)
            if not m:
                break
            page_url = m.group(1)
        return out

    def _find_matching_collection(self, collections: list) -> dict | None:
        """GLM bewertet, ob eine bestehende Kollektion zum Topic passt."""
        if not collections:
            return None
        # Kompakte Liste für GLM (handle + title)
        simple_list = [{'handle': c['handle'], 'title': c['title']} for c in collections]
        prompt = (
            f"Du bekommst eine Liste bestehender Shopify-Kollektionen eines deutschen "
            f"Geschenk-Shops und sollst entscheiden, ob eine davon thematisch zu einem "
            f"neuen Topic passt.\n\n"
            f'Topic: "{self.project.topic}"\n'
            f'Topic-Keywords: {self.project.keywords}\n\n'
            f"Bestehende Kollektionen:\n"
            f"{json.dumps(simple_list, ensure_ascii=False, indent=2)}\n\n"
            f"Entscheide:\n"
            f"- Gibt es eine bestehende Kollektion, deren Title/Handle das Topic GENAU "
            f"  abdeckt (Confidence ≥ 0.7)? Beispiel: Topic 'Geschenk Erzieherin' und "
            f"  bestehender Handle 'geschenk-erzieherin' = Match. Aber 'geschenk-lehrer' "
            f"  passt NICHT zu 'Geschenk Erzieherin' (zu unspezifisch).\n"
            f"- Wenn kein perfekter Match: gib `null` zurück.\n\n"
            f"Antwort als JSON:\n"
            f'{{"handle": "passender-handle" | null, "confidence": 0.0-1.0, '
            f'"reason": "kurze Begründung"}}'
        )
        try:
            data = self.glm.json_chat(prompt, temperature=0.2)
            if not isinstance(data, dict):
                return None
            handle = data.get('handle')
            confidence = float(data.get('confidence', 0))
            if handle and confidence >= self.MATCH_THRESHOLD:
                self.project.log_stage(
                    'collection',
                    f'✓ Match: "{handle}" (confidence {confidence:.2f}) — {data.get("reason","")[:80]}',
                )
                return {'handle': handle, 'confidence': confidence}
            self.project.log_stage(
                'collection',
                f'➡️ Kein Match (confidence {confidence:.2f}) — neue Kollektion wird erstellt',
            )
        except Exception as exc:
            logger.warning('Collection-Matching-GLM fehlgeschlagen: %s', exc)
        return None

    def _suggest_cross_links(self, all_collections: list, exclude_handle: str = '') -> list:
        """GLM wählt 2-3 thematisch passende Kollektionen für Cross-Links."""
        if not all_collections:
            return []
        simple = [{'handle': c['handle'], 'title': c['title']}
                  for c in all_collections if c['handle'] != exclude_handle]
        prompt = (
            f"Wähle aus dieser Liste GENAU 2-3 Kollektionen aus, die thematisch "
            f'zum Thema "{self.project.topic}" passen und für Cross-Linking aus '
            f"einer neuen Sub-Kategorie sinnvoll sind (z.B. übergeordnete Kategorien, "
            f"verwandte Anlässe, ähnliche Berufsgruppen).\n\n"
            f"Kollektionen:\n{json.dumps(simple, ensure_ascii=False, indent=2)}\n\n"
            f"Antwort als JSON-Array von Handles, max. 3:\n"
            f'["handle1", "handle2", "handle3"]'
        )
        try:
            data = self.glm.json_chat(prompt, temperature=0.3)
            if isinstance(data, list):
                return [str(h) for h in data[:3] if h]
        except Exception as exc:
            logger.warning('Cross-Link-Suggestion fehlgeschlagen: %s', exc)
        return []

    def _generate_collection_content(self, cross_links: list, all_collections: list) -> dict:
        """GLM generiert Title, body_html, kurze_beschreibung, SEO-Felder, Bild-Alt."""
        # Mappe Cross-Link-Handles zu Titles, damit GLM saubere Anchor-Texte schreiben kann
        handle_to_title = {c['handle']: c['title'] for c in all_collections}
        cross_link_pairs = [
            {'handle': h, 'title': handle_to_title.get(h, h.replace('-', ' ').title())}
            for h in cross_links
        ]
        prompt = (
            f"Erstelle eine SEO-optimierte Naturmacher-Sub-Kategorie für personalisierte "
            f"Blumentöpfe mit Gravur.\n\n"
            f'Topic: "{self.project.topic}"\n\n'
            f"Cross-Link-Kollektionen (für die 'Mehr Geschenke für ...'-Sektion am Ende "
            f"der body_html):\n{json.dumps(cross_link_pairs, ensure_ascii=False, indent=2)}\n\n"
            f"Erforderliche Felder:\n"
            f"1. **title**: max. 60 Zeichen, klar formuliert. Beispiel: "
            f"  'Geschenke für Erzieherinnen', 'Geschenke zum Ausbildungsabschluss'.\n"
            f"2. **handle**: URL-Slug aus title, kleinbuchstaben-bindestrich-getrennt, "
            f"  ohne Umlaute/Sonderzeichen. Beispiel: 'geschenke-fuer-erzieherinnen'.\n"
            f"3. **short_description** (für Metafeld custom.kurze_kategoriebeschreibung): "
            f"  1-2 Sätze, max. 200 Zeichen, SEO-optimiert mit Keyword-Topic. "
            f"  Beispiel: 'Dankeschön-Geschenke für Erzieherinnen mit persönlicher Gravur. "
            f"  Zeige Wertschätzung – mehr Kita & Schule Geschenke entdecken.'\n"
            f"4. **body_html**: vollständiger Naturmacher-Stil mit dieser Struktur:\n"
            f"   <p>Eingangs-Absatz (Frage + Antwort, emotional, 3-5 Sätze)</p>\n"
            f"   <h3>Warum ein personalisierter Blumentopf zum/zur ...?</h3><p>...</p>\n"
            f"   <h3>Unsere beliebtesten {{Topic}}-Geschenke</h3>\n"
            f"   <p><strong>Variante 1:</strong> Beschreibung.</p>\n"
            f"   <p><strong>Variante 2:</strong> Beschreibung mit eingebettetem Cross-Link "
            f'   <a href="/collections/{{andere-handle}}">Andere Kategorie</a>.</p>\n'
            f"   <h3>Perfekt für...</h3><ul><li>Anlass 1</li><li>Anlass 2</li>...</ul>\n"
            f"   <h3>Häufig gestellte Fragen</h3>\n"
            f"   <p><strong>Frage 1?</strong></p><p>Antwort 1.</p>\n"
            f"   <p><strong>Frage 2?</strong></p><p>Antwort 2.</p>\n"
            f"   <h3>Mehr Geschenke für ...</h3>\n"
            f"   <p>"
            f'→ <a href="/collections/HANDLE1">Title 1</a><br>'
            f'→ <a href="/collections/HANDLE2">Title 2</a></p>\n'
            f"   Verwende ALLE Cross-Link-Handles aus oben (HANDLE1, HANDLE2, ...).\n"
            f"5. **seo_title**: 50-65 Zeichen, Long-Tail mit Topic-Keyword.\n"
            f"6. **seo_description**: 140-160 Zeichen Meta-Tag.\n"
            f"7. **image_alt**: 1 Satz für das generierte Kollektions-Bild — beschreibt "
            f"  ein abstrakt-symbolisches Bild im Naturmacher-Stil (Aquarell/Pastell, "
            f"  einfaches Symbol/Icon zum Topic). Beispiel: "
            f"  'Glühbirne mit Strahlen auf einem bunten Aquarellhintergrund in Rosa und Blau, "
            f"  symbolisiert Ideen und Kreativität.'\n\n"
            f"Antworte als JSON-Objekt:\n"
            f'{{"title": "...", "handle": "...", "short_description": "...", '
            f'"body_html": "<p>...</p>...", "seo_title": "...", '
            f'"seo_description": "...", "image_alt": "..."}}\n\n'
            f"Wichtig: body_html ist gültiges HTML-String. Cross-Links nutzen handle aus "
            f"der Cross-Link-Liste oben. Keine ausgedachten URLs."
        )
        # max_tokens=4000 — Collection-Content ist umfangreich (body_html allein 1-2k Zeichen).
        # json_chat_with_retry ist robuster (3 Versuche + sauberere Parser-Fallbacks).
        data = self.glm.json_chat_with_retry(
            prompt, expect='object', max_tokens=4000, retries=3,
        )
        if not isinstance(data, dict) or not data.get('title'):
            # Fallback: minimaler Datensatz, damit Stage nicht komplett crasht.
            # Pipeline läuft weiter, Collection wird mit Basis-Texten erstellt.
            logger.warning('Collection-Content-GLM lieferte unvollständig — Fallback')
            data = data if isinstance(data, dict) else {}
            topic = self.project.topic
            data.setdefault('title', f'Geschenke für {topic[:50]}')
            data.setdefault('short_description',
                            f'Personalisierte Geschenke {topic} — entdecke unsere Auswahl.')
            data.setdefault('body_html',
                            f'<p>Du suchst ein Geschenk zum Thema „{topic}"? '
                            f'Bei Naturmacher findest du personalisierte Blumentöpfe '
                            f'mit Lasergravur — hochwertig, herzlich, ein Geschenk das bleibt.</p>')
            data.setdefault('seo_title', f'Personalisierte Geschenke {topic}'[:65])
            data.setdefault('seo_description',
                            f'Personalisierte Blumentöpfe mit Gravur als Geschenk: {topic}. Entdecke unsere Auswahl.'[:160])
            data.setdefault('image_alt',
                            f'Symbolisches Aquarell-Icon für {topic} auf cremefarbenem Hintergrund.')
        if not data.get('handle'):
            data['handle'] = slugify(data.get('title', '')) or f'magvis-{uuid.uuid4().hex[:8]}'
        return data

    def _generate_collection_image(self, image_alt: str) -> str | None:
        """Erzeugt Kollektions-Bild via Gemini im Naturmacher-Aquarell-Stil."""
        prompt = (
            f'Generate ONE square image (NOT TEXT). Style guideline: minimalist symbolic '
            f'illustration in the visual language of the Naturmacher.de brand: a single '
            f'clean symbol or icon centered on a SOFT WATERCOLOR BACKGROUND with pastel '
            f'wash (rose, sage, sky-blue, cream, terracotta blends). Hand-painted feel, '
            f'abstract, no realistic photo content.\n\n'
            f'Subject: an iconic symbol that represents the theme "{self.project.topic}". '
            f'{image_alt}\n\n'
            f'Composition: centered, lots of whitespace, square 1024x1024, watercolor '
            f'paper texture, slight bleeds.\n\n'
            f'STRICT NEGATIVES: no people, no photo-realism, no text, no letters, no logos, '
            f'no hands, no flower pots (this is a category icon — abstract, not product '
            f'photography).\n\n'
            f'OUTPUT MUST BE A SQUARE WATERCOLOR-STYLE ILLUSTRATION ONLY. NO TEXT IN RESPONSE.'
        )
        try:
            result = self.gemini._generate_and_save(prompt, prefix='collection')
            if result.get('success'):
                return result.get('absolute_path') or result.get('path')
        except Exception as exc:
            logger.exception('Collection-Bild-Generierung fehlgeschlagen: %s', exc)
        return None

    def _create_new_collection(self, store, coll: MagvisCollection,
                               all_collections: list, product_ids: list) -> dict:
        # Cross-Links auswählen
        cross_links = self._suggest_cross_links(all_collections)
        coll.cross_link_handles = cross_links
        coll.save(update_fields=['cross_link_handles', 'updated_at'])

        # GLM-Content
        try:
            content = self._generate_collection_content(cross_links, all_collections)
        except Exception as exc:
            return {'success': False, 'error': f'GLM-Content: {exc}'}

        coll.title = content['title'][:255]
        coll.handle = content.get('handle', '')[:255]
        coll.short_description = content.get('short_description', '')[:1000]
        coll.body_html = content.get('body_html', '')
        coll.seo_title = content.get('seo_title', '')[:255]
        coll.seo_description = content.get('seo_description', '')[:320]
        coll.image_alt = content.get('image_alt', '')[:255]
        coll.save()
        self.project.log_stage('collection', f'📝 Texte generiert: "{coll.title}"')

        # Bild generieren
        image_abs_path = self._generate_collection_image(coll.image_alt or coll.title)
        if image_abs_path and os.path.exists(image_abs_path):
            coll.image_path = image_abs_path
            coll.save(update_fields=['image_path', 'updated_at'])
            self.project.log_stage('collection', f'🎨 Bild erstellt: {os.path.basename(image_abs_path)}')

        # Shopify Custom-Collection POST
        try:
            shopify_id, shopify_handle = self._post_shopify_collection(store, coll)
        except Exception as exc:
            coll.error_message = f'Shopify-POST: {exc}'
            coll.save(update_fields=['error_message', 'updated_at'])
            return {'success': False, 'error': str(exc)}

        coll.shopify_collection_id = str(shopify_id)
        coll.shopify_handle = shopify_handle
        coll.shopify_url = f'https://{store.shop_domain}/collections/{shopify_handle}'
        coll.save(update_fields=['shopify_collection_id', 'shopify_handle', 'shopify_url', 'updated_at'])
        self.project.log_stage('collection', f'🛒 Shopify-Kollektion erstellt: {shopify_id}')

        # Metafelder setzen
        try:
            self._set_collection_metafields(store, shopify_id, coll)
            self.project.log_stage('collection', '🏷️ Metafelder gesetzt')
        except Exception as exc:
            logger.warning('Metafeld-Setzung: %s', exc)

        # Produkte zuweisen
        try:
            assigned = self._assign_products_to_collection(store, shopify_id, product_ids)
            coll.assigned_product_ids = assigned
            coll.save(update_fields=['assigned_product_ids', 'updated_at'])
            self.project.log_stage('collection', f'📦 {len(assigned)} Produkte zugewiesen')
        except Exception as exc:
            logger.warning('Produkt-Zuweisung: %s', exc)

        # Sales-Channels publizieren
        try:
            channels = self._publish_to_all_channels(store, shopify_id)
            coll.sales_channels_published = channels
            coll.save(update_fields=['sales_channels_published', 'updated_at'])
            self.project.log_stage('collection', f'📡 Auf {len(channels)} Kanälen publiziert')
        except Exception as exc:
            logger.warning('Sales-Channels: %s', exc)

        return {'success': True, 'collection': coll}

    def _post_shopify_collection(self, store, coll: MagvisCollection) -> tuple:
        import requests
        h = {'X-Shopify-Access-Token': store.access_token,
             'Content-Type': 'application/json'}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        payload = {
            'custom_collection': {
                'title': coll.title,
                'handle': coll.handle or None,
                'body_html': coll.body_html,
                'template_suffix': coll.template_suffix or self.DEFAULT_TEMPLATE,
                'published': True,
            },
        }
        # Bild als base64 anhängen wenn vorhanden
        if coll.image_path and os.path.exists(coll.image_path):
            with open(coll.image_path, 'rb') as fh:
                img_b64 = base64.b64encode(fh.read()).decode()
            payload['custom_collection']['image'] = {
                'attachment': img_b64,
                'alt': coll.image_alt or coll.title,
            }
        r = requests.post(f'{base}/custom_collections.json',
                          headers=h, json=payload, timeout=30)
        if r.status_code not in (200, 201):
            raise RuntimeError(f'HTTP {r.status_code}: {r.text[:300]}')
        cc = r.json().get('custom_collection', {})
        return cc.get('id'), cc.get('handle', coll.handle)

    def _set_collection_metafields(self, store, shopify_id: str, coll: MagvisCollection) -> None:
        """Setzt SEO-Title-Tag, SEO-Description-Tag, kurze_kategoriebeschreibung."""
        import requests
        h = {'X-Shopify-Access-Token': store.access_token,
             'Content-Type': 'application/json'}
        base = f'https://{store.shop_domain}/admin/api/2023-10'

        metafields = []
        if coll.seo_title:
            metafields.append({
                'namespace': 'global', 'key': 'title_tag',
                'type': 'single_line_text_field', 'value': coll.seo_title,
            })
        if coll.seo_description:
            metafields.append({
                'namespace': 'global', 'key': 'description_tag',
                'type': 'single_line_text_field', 'value': coll.seo_description,
            })
        if coll.short_description:
            # Shopify Rich-Text-Format JSON für Theme-Editor
            rich_value = json.dumps({
                'type': 'root',
                'children': [{
                    'type': 'paragraph',
                    'children': [{'type': 'text', 'value': coll.short_description}],
                }],
            }, ensure_ascii=False)
            metafields.append({
                'namespace': 'custom', 'key': 'kurze_kategoriebeschreibung',
                'type': 'rich_text_field', 'value': rich_value,
            })

        for mf in metafields:
            r = requests.post(
                f'{base}/collections/{shopify_id}/metafields.json',
                headers=h, json={'metafield': mf}, timeout=15,
            )
            if r.status_code not in (200, 201):
                logger.warning('Metafield %s.%s fehlgeschlagen: %s',
                               mf['namespace'], mf['key'], r.text[:200])

    def _assign_products_to_collection(self, store, collection_id, product_ids: list) -> list:
        """Erstellt Collects (collection_id ↔ product_id). Liefert Liste der erfolgreich zugewiesenen IDs."""
        import requests
        h = {'X-Shopify-Access-Token': store.access_token,
             'Content-Type': 'application/json'}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        ok = []
        for pid in product_ids:
            r = requests.post(
                f'{base}/collects.json',
                headers=h,
                json={'collect': {'collection_id': int(collection_id), 'product_id': int(pid)}},
                timeout=15,
            )
            if r.status_code in (200, 201):
                ok.append(str(pid))
            else:
                # 422 wenn schon Mitglied — auch als ok werten
                body = r.text[:200]
                if 'already exists' in body or r.status_code == 422:
                    ok.append(str(pid))
                else:
                    logger.warning('Collect prod %s: HTTP %s %s', pid, r.status_code, body)
        return ok

    def _publish_to_all_channels(self, store, collection_id) -> list:
        """Veröffentlicht Kollektion auf allen Sales-Channels (Publications)."""
        import requests
        h = {'X-Shopify-Access-Token': store.access_token,
             'Content-Type': 'application/json'}
        base = f'https://{store.shop_domain}/admin/api/2023-10'
        # Hole alle Publications
        r = requests.get(f'{base}/publications.json', headers=h, timeout=15)
        publications = r.json().get('publications', []) if r.status_code == 200 else []
        published_to = []
        for pub in publications:
            pub_id = pub.get('id')
            if not pub_id:
                continue
            # GraphQL publishablePublish — Custom-Collection
            graphql = f'https://{store.shop_domain}/admin/api/2023-10/graphql.json'
            mutation = (
                'mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {'
                ' publishablePublish(id: $id, input: $input) {'
                ' userErrors { field message } } }'
            )
            payload = {
                'query': mutation,
                'variables': {
                    'id': f'gid://shopify/Collection/{collection_id}',
                    'input': [{'publicationId': f'gid://shopify/Publication/{pub_id}'}],
                },
            }
            rg = requests.post(graphql, headers=h, json=payload, timeout=20).json()
            errs = (rg.get('data') or {}).get('publishablePublish', {}).get('userErrors') or []
            if not errs:
                published_to.append({'name': pub.get('name', ''), 'id': str(pub_id)})
            else:
                logger.warning('Publish to %s: %s', pub.get('name'), errs)
        return published_to
