"""Magvis Orchestrator — Stage-Dispatch.

Ruft den passenden Sub-Service je nach Stage des Projekts auf.
Wird von den Celery-Tasks und der DRF-API genutzt.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from ..models import MagvisProject

logger = logging.getLogger(__name__)


class MagvisOrchestrator:
    """Orchestriert die Stages eines MagvisProject."""

    STAGE_SLUGS = ['preflight', 'video', 'post_video', 'products', 'collection', 'blog', 'image_posts', 'sync', 'report']

    def __init__(self, project: MagvisProject):
        self.project = project

    # ------------------------------------------------------------------ public

    def run_stage(self, slug: str, **kwargs) -> dict:
        """Synchron einen Stage ausführen."""
        if slug not in self.STAGE_SLUGS:
            raise ValueError(f'Unbekannter Stage-Slug: {slug}')

        method = getattr(self, f'_stage_{slug}')
        try:
            self._set_stage_running(slug)
            result = method(**kwargs)
            self._set_stage_done(slug, result)
            return result
        except Exception as exc:
            logger.exception('Stage %s fehlgeschlagen', slug)
            self.project.stage = MagvisProject.STAGE_FAILED
            self.project.error_message = str(exc)[:2000]
            self.project.save(update_fields=['stage', 'error_message', 'updated_at'])
            raise

    def advance(self) -> dict | None:
        """Führt den nächsten passenden Stage aus, basierend auf project.stage."""
        slug = self.project.next_stage_slug()
        if not slug:
            return None
        return self.run_stage(slug)

    # Mapping: aus welchem Stage-Status soll bei welchem Slug fortgesetzt werden?
    # Wird genutzt damit run_full_chain bei einem Re-Trigger nicht von vorne
    # anfaengt und z.B. das Video doppelt rendert / postet.
    DONE_STAGE_FOR_SLUG = {
        'preflight': MagvisProject.STAGE_PREFLIGHT_DONE,
        'video': MagvisProject.STAGE_VIDEO_DONE,
        'post_video': MagvisProject.STAGE_POST_VIDEO_DONE,
        'products': MagvisProject.STAGE_PRODUCTS_DONE,
        'collection': MagvisProject.STAGE_COLLECTION_DONE,
        'blog': MagvisProject.STAGE_BLOG_DONE,
        'image_posts': MagvisProject.STAGE_IMAGE_POSTS_DONE,
        'sync': MagvisProject.STAGE_SYNC_DONE,
    }

    def run_full_chain(self) -> None:
        """Komplette Pipeline ohne Pause. Idempotent: ueberspringt Stages, die
        bereits abgeschlossen sind (verhindert Doppel-Render/Doppel-Posting bei
        Re-Triggern nach Worker-Crash oder Manual-Restart)."""
        # Aktuellen Stage-Status auslesen
        self.project.refresh_from_db()
        completed = self._completed_stages()
        for slug in self.STAGE_SLUGS:
            if slug in completed:
                logger.info('Stage %s bereits done — wird uebersprungen', slug)
                continue
            try:
                self.run_stage(slug)
            except Exception:
                # Stage-Fehler unterbricht die Chain (Project ist auf 'failed' gesetzt
                # via run_stage's except-Block). Report-Stage läuft trotzdem mit
                # Fehler-Notiz ABER darf den Failed-Status nicht überschreiben.
                # _set_stage_done(report) würde sonst stage=COMPLETED setzen.
                if slug != 'report':
                    failed_msg = self.project.error_message
                    try:
                        self.run_stage('report')
                    except Exception:
                        pass
                    # Status zurück auf FAILED setzen (run_stage('report') hat
                    # ihn bei success auf COMPLETED ueberschrieben)
                    self.project.refresh_from_db()
                    if self.project.stage in (MagvisProject.STAGE_COMPLETED,
                                               MagvisProject.STAGE_REPORT_SENT):
                        self.project.stage = MagvisProject.STAGE_FAILED
                        self.project.error_message = (failed_msg
                            or f'Stage {slug} fehlgeschlagen')[:2000]
                        self.project.save(update_fields=['stage', 'error_message', 'updated_at'])
                raise

    def _completed_stages(self) -> set:
        """Liefert die Slugs der bereits abgeschlossenen Stages — basierend auf
        project.stage. Reihenfolge: video → post_video → products → collection →
        blog → image_posts → report."""
        order = ['preflight', 'video', 'post_video', 'products', 'collection', 'blog', 'image_posts', 'sync', 'report']
        done_states = {
            MagvisProject.STAGE_PREFLIGHT_DONE: 0,
            MagvisProject.STAGE_VIDEO_RUNNING: 0,
            MagvisProject.STAGE_VIDEO_DONE: 1,
            MagvisProject.STAGE_POST_VIDEO_RUNNING: 1,
            MagvisProject.STAGE_POST_VIDEO_DONE: 2,
            MagvisProject.STAGE_PRODUCTS_RUNNING: 2,
            MagvisProject.STAGE_PRODUCTS_DONE: 3,
            MagvisProject.STAGE_COLLECTION_RUNNING: 3,
            MagvisProject.STAGE_COLLECTION_DONE: 4,
            MagvisProject.STAGE_BLOG_RUNNING: 4,
            MagvisProject.STAGE_BLOG_DONE: 5,
            MagvisProject.STAGE_IMAGE_POSTS_RUNNING: 5,
            MagvisProject.STAGE_IMAGE_POSTS_DONE: 6,
            MagvisProject.STAGE_SYNC_RUNNING: 6,
            MagvisProject.STAGE_SYNC_DONE: 7,
            MagvisProject.STAGE_REPORT_SENT: 8,
            MagvisProject.STAGE_COMPLETED: 9,
        }
        idx = done_states.get(self.project.stage, -1)
        if idx < 0:
            return set()
        return set(order[:idx + 1])

    # ----------------------------------------------------------------- stages

    def _stage_preflight(self, **kwargs) -> dict:
        """Pre-Flight: alle externen Services + System-Resourcen prüfen,
        bevor wir 18 Min Video rendern. Bei Fehler wird zusätzlich eine
        Alert-Email an MagvisReportConfig.report_email gesendet, damit
        der User sofort weiß was kaputt ist."""
        from .preflight_check import MagvisPreflightCheck
        check = MagvisPreflightCheck(self.project)
        try:
            return check.run()
        except RuntimeError:
            # Alert-Mail bevor wir die Exception weiterwerfen
            try:
                from .report_mailer import send_preflight_failure_alert
                send_preflight_failure_alert(self.project, check.results)
            except Exception as alert_exc:
                logger.warning('Preflight-Alert-Mail-Versand: %s', alert_exc)
            raise

    def _stage_video(self, **kwargs) -> dict:
        """Video-Stage: vidgen synchron im selben Worker.

        Der pool=solo Celery-Worker kann den vidgen-Task nicht parallel
        abarbeiten, deshalb kein .delay() + Polling-Deadlock — sondern
        direkter Aufruf von vidgen.tasks.generate_video.run().
        """
        from .video_pipeline import MagvisVideoPipeline
        pipe = MagvisVideoPipeline(self.project)
        pipe.create_video_project()
        result = pipe.trigger_render(sync=True)
        # vidgen markiert sein VideoProject am Ende auf status='done' oder 'failed'
        done, err = pipe.is_done()
        if not done:
            raise RuntimeError('Video-Pipeline lief, aber VideoProject ist nicht done/failed')
        if err:
            raise RuntimeError(f'Video-Generierung fehlgeschlagen: {err}')
        pipe.attach_video_record()
        return {'success': True, 'video_result': result}

    def _stage_post_video(self, **kwargs) -> dict:
        from .social_pipeline import MagvisSocialPipeline
        pipe = MagvisSocialPipeline(self.project)
        # Hardcoded: YouTube + Instagram + TikTok (User-Wunsch).
        # YouTube ist zwingend fuer den Blog-Embed in Stage 4.
        result = pipe.post_video(platforms=['youtube', 'instagram', 'tiktok'])
        if not result.get('success'):
            raise RuntimeError(f'Video-Posten fehlgeschlagen: {result.get("error")}')
        # Auf YouTube-URL warten
        poll = pipe.poll_youtube_url(max_wait_s=600)
        if not poll.get('success'):
            # Trotzdem als done markieren — Blog kann ohne YT-Embed gebaut werden
            logger.warning('YouTube-URL nicht verfügbar: %s', poll.get('error'))
        return {'success': True, **poll}

    def _stage_products(self, **kwargs) -> dict:
        from .product_pipeline import MagvisProductPipeline
        return MagvisProductPipeline(self.project).run()

    def _stage_collection(self, **kwargs) -> dict:
        """Erstellt oder findet eine Shopify-Kollektion und weist die 2 Magvis-Produkte
        + das Stamm-Sortiment (default_collection_extra_product_handles) zu.

        Optional kann der Wizard zusätzliche Shopify-Product-IDs via
        kwargs['additional_product_ids'] (Liste) durchreichen.
        """
        from .collection_pipeline import MagvisCollectionPipeline
        extra = kwargs.get('additional_product_ids') or []
        result = MagvisCollectionPipeline(self.project, additional_product_ids=extra).run()
        if not result.get('success'):
            raise RuntimeError(f'Collection-Stage: {result.get("error","unbekannt")}')
        coll = result.get('collection')
        return {
            'success': True,
            'shopify_url': getattr(coll, 'shopify_url', '') or '',
            'was_existing': getattr(coll, 'was_existing', False),
        }

    def _stage_blog(self, **kwargs) -> dict:
        from .blog_assembler import MagvisBlogAssembler
        blog = MagvisBlogAssembler(self.project).assemble()
        return {'success': True, 'blog_id': blog.id, 'shopify_url': blog.shopify_published_url}

    def _stage_image_posts(self, **kwargs) -> dict:
        """Selektives Posten ausgewählter KI-Bilder auf mehreren Plattformen.

        Strategie (User-Vorgabe vom 2026-04-30):
        - Blog-Brainstorm  → pinterest, instagram, facebook, threads
        - Blog-Diagramm    → pinterest, facebook, threads
        - Produkt-KI (NUR variant=geschenk_uebergabe, eines pro Produkt)
                           → pinterest, facebook, threads
        - andere Bilder    → werden NICHT gepostet (verhindert Pinterest-Spam)

        Title/Description werden via GLM SEO-optimiert + jeweils mit dem
        Blog-Link am Ende verlinkt (über alle Plattformen, die Links unterstützen).

        Wizard-Override: explizite asset.target_platforms gewinnt.
        """
        from .image_post_pipeline import MagvisImagePostPipeline
        from ..models import MagvisImageAsset
        from .llm_client import MagvisLLMClient
        from ..models import MagvisSettings

        ms, _ = MagvisSettings.objects.get_or_create(user=self.project.user)
        glm = MagvisLLMClient(self.project.user, ms)
        topic = self.project.topic
        blog_url = (getattr(self.project, 'blog', None)
                    and self.project.blog.shopify_published_url) or ''

        results = []
        skipped = 0
        for asset in self.project.image_assets.all():
            # Plattform-Wahl: explizite Wizard-Vorgabe gewinnt, sonst Magvis-Strategie
            platforms = asset.target_platforms or self._select_platforms_for_asset(asset)
            if not platforms:
                continue

            # IDEMPOTENZ: pro Plattform überspringen, wenn schon erfolgreich gepostet.
            # Verhindert Doppel-Posts bei Worker-Crash + Celery-Retry.
            already = asset.posted_status or {}
            todo_platforms = []
            for plat in platforms:
                ps_entry = already.get(plat) or {}
                # Erfolgreich heißt: success=True ODER eine URL/social_url ODER request_id
                is_done = bool(
                    ps_entry.get('success') or ps_entry.get('url')
                    or ps_entry.get('social_url') or ps_entry.get('request_id')
                )
                if not is_done:
                    todo_platforms.append(plat)
            if not todo_platforms:
                skipped += 1
                continue
            platforms = todo_platforms

            # GLM erzeugt SEO-optimierten Title + Description universell
            # (Pinterest, IG, FB, Threads). Blog-URL wird nur dort eingefügt,
            # wo Links in der Description sinnvoll/klickbar sind.
            post_title, post_description = self._generate_post_caption(
                glm, topic, asset, platforms, blog_url,
            )
            post_title = post_title or asset.title_de
            post_description = post_description or asset.description_de
            try:
                r = MagvisImagePostPipeline(asset).post(
                    platforms=platforms,
                    use_overlay=asset.use_overlay,
                    overlay_text=asset.overlay_text,
                    overlay_method=asset.overlay_method,
                    title=post_title,
                    description=post_description,
                )
                results.append({'asset_id': asset.id, 'platforms': platforms, 'result': r})
            except Exception as exc:
                logger.exception('ImagePost asset=%s', asset.id)
                results.append({'asset_id': asset.id, 'error': str(exc)})
        self.project.log_stage(
            'image_posts',
            f'📤 {len(results)} KI-Bilder gepostet, {skipped} bereits erledigt (Idempotenz-Skip)',
        )
        return {'success': True, 'count': len(results), 'skipped': skipped, 'results': results}

    def _select_platforms_for_asset(self, asset) -> list:
        """Magvis-Posting-Strategie pro Asset (User-Vorgabe 2026-04-30):

        - Blog-Brainstorm  → pinterest, instagram
        - Blog-Diagramm    → pinterest
        - Produkt-KI variant=geschenk_uebergabe (eines pro Produkt)
                           → pinterest
        - sonst leer (= nicht posten)

        Facebook + Threads sind im Upload-Post-Account NICHT korrekt verknüpft:
        - FB ist auf Taras' privatem Profil (nicht Naturmacher-Page)
        - Threads hat keinen Account konfiguriert
        Sobald in Upload-Post Settings die Naturmacher-FB-Page + Threads
        verknüpft sind, hier Plattformen wieder ergänzen.

        Heuristik für 'geschenk'-Variante: title_de enthält 'geschenk_uebergabe'.
        """
        from ..models import MagvisImageAsset
        if asset.source == MagvisImageAsset.SOURCE_BLOG_BRAINSTORM:
            return ['pinterest', 'instagram']
        if asset.source == MagvisImageAsset.SOURCE_BLOG_DIAGRAM:
            return ['pinterest']
        if asset.source == MagvisImageAsset.SOURCE_PRODUCT_AI:
            tag = (asset.title_de or '').lower()
            if 'geschenk_uebergabe' in tag or 'geschenk' in tag.split('—')[-1].strip():
                return ['pinterest']
        return []

    def _generate_post_caption(self, glm, topic: str, asset,
                               platforms: list, blog_url: str) -> tuple[str, str]:
        """SEO-optimierter Title + Description via GLM, plattform-aware.

        Title: max 100 Zeichen (Pinterest-Limit ist striktest).
        Description: max 500 Zeichen, mit Mid-Tail-Long-Keywords + 5-7 Hashtags
        + Blog-URL am Ende, falls 'pinterest', 'facebook' oder 'threads' (dort
        sind Links nützlich/klickbar; Instagram-Captions verlinken nicht klickbar
        — Blog-URL trotzdem als Text, weil sie kontextuell sinnvoll bleibt).
        """
        from ..models import MagvisImageAsset
        kind_hint = {
            MagvisImageAsset.SOURCE_PRODUCT_AI: 'Personalisierter Naturmacher-Blumentopf mit Gravur — Geschenk-Übergabe-Szene',
            MagvisImageAsset.SOURCE_BLOG_DIAGRAM: 'Infografik mit Kernpunkten zum Thema',
            MagvisImageAsset.SOURCE_BLOG_BRAINSTORM: 'Brainstorming-Mind-Map zum Thema',
        }.get(asset.source, 'Bild zum Thema')
        platform_hint = ', '.join(platforms)
        link_clause = (f'\n- Verlinke den Blogbeitrag am Ende der Description: "{blog_url}"'
                       if blog_url else '')
        prompt = (
            f'Erstelle einen Title und eine Description für einen Social-Media-Post '
            f'auf den Plattformen: {platform_hint}.\n\n'
            f'Thema: "{topic}"\n'
            f'Bild-Typ: {kind_hint}\n'
            f'Marke: Naturmacher.de — personalisierte Blumentöpfe mit Lasergravur, '
            f'herzlich, persönlich, du-Form, deutscher Familienbetrieb.\n\n'
            f'Anforderungen:\n'
            f'- **Title**: max 100 Zeichen, hookig, deutsch, suchfreundlich '
            f'  (Long-Tail-Keyword zum Topic), kein Marketing-Geschwurbel.\n'
            f'- **Description**: max 500 Zeichen GESAMT (inkl. Blog-URL & Hashtags). '
            f'  SEO-optimiert mit Mid-Tail-Keywords zum Topic, beschreibt was das '
            f'  Bild zeigt + warum es relevant ist + Call-to-Action zum Mehr-Lesen. '
            f'  Endet mit 5-7 passenden deutschen Hashtags '
            f'  (#Geschenkidee #PersonalisiertesGeschenk #Naturmacher etc).'
            f'{link_clause}\n\n'
            f'Antworte AUSSCHLIESSLICH mit diesem JSON:\n'
            f'{{"title": "...", "description": "..."}}'
        )
        try:
            data = glm.json_chat_with_retry(
                prompt, expect='object', max_tokens=700, retries=2,
            ) or {}
        except Exception as exc:
            logger.warning('Post-Caption-Generation fehlgeschlagen: %s', exc)
            data = {}
        title = (data.get('title') or '').strip()[:100]
        description = (data.get('description') or '').strip()
        # Failsafe: wenn GLM die Blog-URL nicht eingebaut hat, hänge sie an
        if blog_url and blog_url not in description:
            tail = f'\n→ {blog_url}'
            if len(description) + len(tail) <= 500:
                description = description + tail
            else:
                description = (description[:500 - len(tail)].rstrip() + tail)
        return title, description[:500]

    def _stage_sync(self, **kwargs) -> dict:
        """Synchronisiert die im Run erstellten Items in die shopify_manager-DB."""
        from .sync_pipeline import MagvisSyncPipeline
        result = MagvisSyncPipeline(self.project).run()
        # Sync-Fehler sind nicht fatal — wir loggen, aber lassen die Pipeline laufen
        if not result.get('success'):
            logger.warning('Sync-Stage mit Fehlern: %s', result.get('results'))
        return {'success': True, **result}

    def _stage_report(self, **kwargs) -> dict:
        from .report_mailer import send_project_report
        ok = send_project_report(self.project)
        return {'success': ok}

    # --------------------------------------------------------------- internals

    STAGE_RUNNING_MAP = {
        'preflight': MagvisProject.STAGE_PREFLIGHT_RUNNING,
        'video': MagvisProject.STAGE_VIDEO_RUNNING,
        'post_video': MagvisProject.STAGE_POST_VIDEO_RUNNING,
        'products': MagvisProject.STAGE_PRODUCTS_RUNNING,
        'collection': MagvisProject.STAGE_COLLECTION_RUNNING,
        'blog': MagvisProject.STAGE_BLOG_RUNNING,
        'image_posts': MagvisProject.STAGE_IMAGE_POSTS_RUNNING,
        'sync': MagvisProject.STAGE_SYNC_RUNNING,
        'report': MagvisProject.STAGE_REPORT_SENT,
    }
    STAGE_DONE_MAP = {
        'preflight': MagvisProject.STAGE_PREFLIGHT_DONE,
        'video': MagvisProject.STAGE_VIDEO_DONE,
        'post_video': MagvisProject.STAGE_POST_VIDEO_DONE,
        'products': MagvisProject.STAGE_PRODUCTS_DONE,
        'collection': MagvisProject.STAGE_COLLECTION_DONE,
        'blog': MagvisProject.STAGE_BLOG_DONE,
        'image_posts': MagvisProject.STAGE_IMAGE_POSTS_DONE,
        'sync': MagvisProject.STAGE_SYNC_DONE,
        'report': MagvisProject.STAGE_COMPLETED,
    }
    STAGE_PCT = {
        'preflight': 5, 'video': 20, 'post_video': 35, 'products': 55,
        'collection': 65, 'blog': 80, 'image_posts': 90, 'sync': 95, 'report': 100,
    }

    def _set_stage_running(self, slug: str) -> None:
        self.project.stage = self.STAGE_RUNNING_MAP[slug]
        self.project.error_message = ''
        self.project.log_stage(slug, f'Stage "{slug}" gestartet', level='info')
        self.project.save(update_fields=['stage', 'error_message', 'updated_at'])

    def _set_stage_done(self, slug: str, result: dict | None = None) -> None:
        self.project.stage = self.STAGE_DONE_MAP[slug]
        self.project.progress_pct = self.STAGE_PCT[slug]
        msg = f'Stage "{slug}" erfolgreich abgeschlossen'
        if result and result.get('shopify_url'):
            msg += f' — {result["shopify_url"]}'
        self.project.log_stage(slug, msg, level='success')
        self.project.save(update_fields=['stage', 'progress_pct', 'updated_at'])

        # Bei letztem Stage: Wenn source_queue_item existiert → Status setzen
        if slug == 'report' and self.project.source_queue_item:
            self.project.source_queue_item.refresh_from_db()
            self.project.source_queue_item.used_by_project = self.project
            self.project.source_queue_item.save(update_fields=['used_by_project'])
