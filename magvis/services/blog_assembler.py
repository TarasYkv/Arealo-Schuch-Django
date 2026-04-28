"""Magvis Blog-Assembler.

Baut den vollständigen Blog-HTML aus Sektions-Bausteinen:
TOC → Intro → YT-Embed → Diagramm → Quiz → Brainstorm → Mini-Spiel
→ Produkt-Card #1 (~50%) → Produkt-Card #2 (letztes Drittel) → 5 FAQs.

Texte: GLM-5.1. Bilder: Gemini.
"""
from __future__ import annotations

import json
import logging
from html import escape

from django.template.loader import render_to_string
from django.utils.text import slugify as django_slugify

from ..models import MagvisBlog, MagvisImageAsset, MagvisProject
from ..prompts.blog_prompts import (
    NATURMACHER_VOICE,
    faqs_prompt,
    headings_prompt,
    intro_prompt,
    section_prompt,
)
from .gemini_helper import MagvisGeminiHelper
from .glm_client import MagvisGLMClient
from .minigame_generator import generate_minigame, minigame_html
from .quiz_generator import generate_quiz, quiz_html
from .toc_generator import estimate_minutes, render_toc, slugify
from .youtube_embed import embed_html

logger = logging.getLogger(__name__)


class MagvisBlogAssembler:
    """Hauptklasse — assemble(project) liefert MagvisBlog mit final_html."""

    def __init__(self, project: MagvisProject):
        self.project = project
        self.user = project.user

        from ..models import MagvisSettings
        self.settings, _ = MagvisSettings.objects.get_or_create(user=self.user)
        self.glm = MagvisGLMClient(self.user, self.settings)
        self.gemini = MagvisGeminiHelper(self.user, self.settings)

    # ------------------------------------------------------------------ public

    def assemble(self) -> MagvisBlog:
        blog, _ = MagvisBlog.objects.get_or_create(project=self.project)

        topic = self.project.topic
        sections: list[dict] = []

        # 1. SEO-Titel + Meta-Description
        seo = self._generate_seo()
        blog.seo_title = seo.get('title', topic)[:255]
        blog.seo_description = seo.get('description', '')[:500]
        blog.slug = django_slugify(blog.seo_title)[:255]

        # 2. Headings (Struktur-Skelett)
        headings = self._generate_headings(topic)

        # 3. Intro
        intro_html = self._call_glm(intro_prompt(topic))
        sections.append({'type': 'intro', 'id': 'intro', 'html': intro_html})

        # 4. Inhaltsverzeichnis (TOC) zwischen Intro und Hauptteil
        toc_headings = [(2, h, slugify(h)) for h in headings]
        toc_html_str = render_toc(toc_headings, minutes=estimate_minutes(intro_html, wpm=220) + 4)
        blog.toc_html = toc_html_str

        # 5. Sektion 1 (1-2 Absätze)
        head1 = headings[0] if headings else 'Worum geht es?'
        slug1 = slugify(head1)
        para1 = self._call_glm(section_prompt(topic, head1))
        sections.append({'type': 'h2', 'id': slug1, 'title': head1})
        sections.append({'type': 'paragraph', 'id': f'{slug1}-p', 'html': para1})

        # 6. YouTube-Short-Embed
        if self.project.youtube_video_id:
            sections.append({
                'type': 'youtube', 'id': 'yt-embed',
                'video_id': self.project.youtube_video_id,
                'html': embed_html(self.project.youtube_video_id, is_short=True),
            })

        # 7. Sektion 2
        head2 = headings[1] if len(headings) > 1 else 'Hintergrund'
        slug2 = slugify(head2)
        para2 = self._call_glm(section_prompt(topic, head2))
        sections.append({'type': 'h2', 'id': slug2, 'title': head2})
        sections.append({'type': 'paragraph', 'id': f'{slug2}-p', 'html': para2})

        # 8. Diagramm (Gemini)
        diagram_url = self._generate_blog_image(
            kind='diagram',
            topic_summary=f'Wichtigste Punkte zum Thema "{topic}" als Infografik'
        )
        if diagram_url:
            blog.diagram_image_path = diagram_url
            sections.append({
                'type': 'image', 'id': 'diagram', 'src': diagram_url,
                'alt': f'Infografik: {topic}',
                'html': self._image_html(diagram_url, f'Infografik zum Thema {topic}'),
            })

        # 9. Sektion 3
        head3 = headings[2] if len(headings) > 2 else 'Was du beachten solltest'
        slug3 = slugify(head3)
        para3 = self._call_glm(section_prompt(topic, head3))
        sections.append({'type': 'h2', 'id': slug3, 'title': head3})
        sections.append({'type': 'paragraph', 'id': f'{slug3}-p', 'html': para3})

        # 10. QUIZ
        try:
            quiz_data = generate_quiz(topic, self.glm,
                                      num_questions=self.settings.default_quiz_questions or 4)
        except Exception as exc:
            logger.warning('Quiz failed: %s', exc)
            quiz_data = []
        blog.quiz_data = quiz_data
        sections.append({'type': 'quiz', 'id': 'quiz', 'html': quiz_html(quiz_data)})

        # 11. Sektion 4
        head4 = headings[3] if len(headings) > 3 else 'Tipps & Ideen'
        slug4 = slugify(head4)
        para4 = self._call_glm(section_prompt(topic, head4))
        sections.append({'type': 'h2', 'id': slug4, 'title': head4})
        sections.append({'type': 'paragraph', 'id': f'{slug4}-p', 'html': para4})

        # 12. PRODUKT-EMBED #1 (ca. Mitte des Beitrags)
        if self.project.product_1:
            product_card_1 = self._product_card_html(self.project.product_1)
            sections.append({
                'type': 'product', 'id': 'product-1',
                'product_id': str(self.project.product_1.id), 'html': product_card_1,
            })

        # 13. Brainstorming-Bild (Gemini)
        brainstorm_url = self._generate_blog_image(kind='brainstorm', topic_summary='')
        if brainstorm_url:
            blog.brainstorm_image_path = brainstorm_url
            sections.append({
                'type': 'image', 'id': 'brainstorm', 'src': brainstorm_url,
                'alt': f'Brainstorming: {topic}',
                'html': self._image_html(brainstorm_url, f'Brainstorming zum Thema {topic}'),
            })

        # 14. Sektion 5
        head5 = headings[4] if len(headings) > 4 else 'Ein wenig zum Spielen'
        slug5 = slugify(head5)
        para5 = self._call_glm(section_prompt(topic, head5))
        sections.append({'type': 'h2', 'id': slug5, 'title': head5})
        sections.append({'type': 'paragraph', 'id': f'{slug5}-p', 'html': para5})

        # 15. MINI-SPIEL
        try:
            game_data = generate_minigame(topic, self.glm)
        except Exception as exc:
            logger.warning('Minigame failed: %s', exc)
            game_data = {}
        blog.minigame_data = game_data
        sections.append({'type': 'minigame', 'id': 'minigame', 'html': minigame_html(game_data)})

        # 16. Sektion 6 (letztes Drittel)
        head6 = headings[5] if len(headings) > 5 else 'Persönliche Geschenkideen'
        slug6 = slugify(head6)
        para6 = self._call_glm(section_prompt(topic, head6))
        sections.append({'type': 'h2', 'id': slug6, 'title': head6})
        sections.append({'type': 'paragraph', 'id': f'{slug6}-p', 'html': para6})

        # 17. PRODUKT-EMBED #2 (letztes Drittel)
        if self.project.product_2:
            product_card_2 = self._product_card_html(self.project.product_2)
            sections.append({
                'type': 'product', 'id': 'product-2',
                'product_id': str(self.project.product_2.id), 'html': product_card_2,
            })

        # 18. FAQs (mit Retry + robust JSON parsing)
        faqs = self.glm.json_chat_with_retry(
            faqs_prompt(topic, num_faqs=self.settings.default_faq_count or 5),
            expect='array', max_tokens=3000, retries=3,
        ) or []
        if not isinstance(faqs, list):
            faqs = []
        # Validierung: nur dicts mit question+answer
        faqs = [f for f in faqs if isinstance(f, dict)
                and f.get('question') and f.get('answer')]
        if not faqs:
            logger.warning('FAQs leer geliefert — verwende Naturmacher-Standard-Fallback')
            faqs = [
                {'question': f'Warum eignet sich ein personalisierter Blumentopf zum Thema "{topic}"?',
                 'answer': 'Ein gravierter Blumentopf ist langlebig, naturverbunden und individuell — er bleibt jahrelang sichtbar im Alltag.'},
                {'question': 'Wie lange dauert die Lieferung?',
                 'answer': 'In der Regel 5-7 Werktage innerhalb Deutschlands.'},
                {'question': 'Kann ich die Gravur frei wählen?',
                 'answer': 'Ja, jeder Topf wird individuell graviert — du gibst Text und Schriftart vor.'},
                {'question': 'Sind die Töpfe für draußen geeignet?',
                 'answer': 'Ja, sie sind frostbeständig und für den Außenbereich geeignet.'},
                {'question': 'Welche Größe haben die Töpfe?',
                 'answer': 'Etwa 14 cm Durchmesser und 12 cm Höhe — kompakt und vielseitig einsetzbar.'},
            ]
        blog.faqs = faqs
        sections.append({'type': 'faqs', 'id': 'faqs', 'html': self._faqs_html(faqs)})

        blog.sections = sections
        blog.final_html = self._compose_html(blog)
        blog.save()

        # Diagramm + Brainstorming als MagvisImageAsset für Schritt 5 (Posten)
        if blog.diagram_image_path:
            MagvisImageAsset.objects.get_or_create(
                project=self.project,
                source=MagvisImageAsset.SOURCE_BLOG_DIAGRAM,
                defaults={'src_path': blog.diagram_image_path,
                          'title_de': f'Diagramm: {topic}'},
            )
        if blog.brainstorm_image_path:
            MagvisImageAsset.objects.get_or_create(
                project=self.project,
                source=MagvisImageAsset.SOURCE_BLOG_BRAINSTORM,
                defaults={'src_path': blog.brainstorm_image_path,
                          'title_de': f'Brainstorming: {topic}'},
            )

        # Shopify-Veröffentlichung (Blog-Artikel) — best effort
        try:
            self._publish_to_shopify(blog)
        except Exception as exc:
            logger.warning('Shopify-Blog-Publish fehlgeschlagen: %s', exc)

        return blog

    # ----------------------------------------------------------------- helper

    def _call_glm(self, prompt: str) -> str:
        try:
            return self.glm.text(prompt, system=NATURMACHER_VOICE, temperature=0.75).strip()
        except Exception as exc:
            logger.warning('GLM-Call fehlgeschlagen: %s', exc)
            return f'<p><em>(Hinweis: GLM-Sektion konnte nicht generiert werden — bitte Eintrag manuell ergänzen.)</em></p>'

    def _generate_seo(self) -> dict:
        prompt = (
            f"{NATURMACHER_VOICE}\n\n"
            f"Erstelle SEO-Titel (max. 60 Zeichen) und Meta-Description (max. 160 Zeichen) "
            f"für einen Blogbeitrag zum Thema \"{self.project.topic}\".\n"
            f'Antwort als JSON: {{"title": "...", "description": "..."}}'
        )
        try:
            data = self.glm.json_chat(prompt)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {'title': self.project.topic, 'description': self.project.topic}

    def _generate_headings(self, topic: str) -> list[str]:
        try:
            data = self.glm.json_chat(headings_prompt(topic))
            if isinstance(data, list):
                return [str(h).strip() for h in data if h]
        except Exception as exc:
            logger.warning('Headings-Generation fehlgeschlagen: %s', exc)
        return [
            f'Was ist {topic} eigentlich?',
            f'Warum ist {topic} so besonders?',
            'Worauf solltest du beim Geschenk achten?',
            'Tipps für die persönliche Note',
            'Mit Spaß lernen',
            'Mehr Geschenkideen',
        ]

    def _generate_blog_image(self, kind: str, topic_summary: str = '') -> str:
        try:
            if kind == 'diagram':
                result = self.gemini.generate_diagram(self.project.topic, topic_summary)
            else:
                result = self.gemini.generate_brainstorm(self.project.topic)
        except Exception as exc:
            logger.warning('Gemini-%s fehlgeschlagen: %s', kind, exc)
            return ''
        if not result.get('success'):
            return ''
        return result.get('rel_path', '') or result.get('url', '')

    def _image_html(self, rel_path: str, alt: str) -> str:
        from django.conf import settings as django_settings
        url = django_settings.MEDIA_URL + rel_path if not rel_path.startswith(('/', 'http')) else rel_path
        return (
            f'<figure style="margin:2.5rem 0;text-align:center;">'
            f'<img src="{url}" alt="{escape(alt)}" '
            f'style="max-width:100%;height:auto;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,0.08);">'
            f'<figcaption style="margin-top:0.5rem;font-size:0.9rem;color:#7A7264;">{escape(alt)}</figcaption>'
            f'</figure>'
        )

    def _product_card_html(self, product) -> str:
        """Produkt-Embed-Card im Naturmacher-Stil (Bild links, Text+CTA rechts)."""
        store = getattr(product, 'shopify_store', None)
        handle = getattr(product, 'handle', '') or ''
        if store and handle:
            url = f'https://{store.shop_domain}/products/{handle}'
        elif store and getattr(product, 'shopify_product_id', ''):
            url = f'https://{store.shop_domain}/admin/products/{product.shopify_product_id}'
        else:
            url = '#'

        featured = product.images.filter(is_featured=True).first() or product.images.first()
        if featured and featured.image:
            img_url = featured.image.url
        elif featured and featured.external_url:
            img_url = featured.external_url
        else:
            img_url = ''

        title = escape(product.title or 'Produkt')
        desc = escape((product.seo_description or product.description or '')[:140])

        return f'''<!-- NM-PRODUCT-CARD -->
<div class="naturmacher-product-card" style="display:flex;gap:18px;align-items:stretch;background:#FAF6EC;border:1px solid #E8DFC9;border-radius:14px;padding:20px;margin:32px 0;flex-wrap:wrap;box-shadow:0 4px 18px rgba(0,0,0,0.05);">
  <a href="{url}" style="flex:0 0 200px;display:block;border-radius:10px;overflow:hidden;">
    <img src="{img_url}" alt="{title}" style="width:100%;height:200px;object-fit:cover;display:block;">
  </a>
  <div style="flex:1;min-width:240px;display:flex;flex-direction:column;justify-content:space-between;">
    <div>
      <div style="font-size:0.85rem;color:#7A7264;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">💡 Geschenkidee</div>
      <h3 style="margin:0 0 10px 0;font-size:1.2rem;color:#2A2A2A;line-height:1.3;">{title}</h3>
      <p style="margin:0 0 16px 0;font-size:0.95rem;color:#5C5651;line-height:1.5;">{desc}</p>
    </div>
    <div>
      <a href="{url}" style="display:inline-block;background:#D4AB32;color:#fff;padding:12px 28px;text-decoration:none;border-radius:6px;font-weight:600;font-size:0.95rem;">Mehr erfahren →</a>
    </div>
  </div>
</div>'''

    def _faqs_html(self, faqs: list) -> str:
        if not faqs:
            return ''
        items = []
        for i, f in enumerate(faqs, start=1):
            q = escape(str(f.get('question', '')))
            a = escape(str(f.get('answer', '')))
            if not q or not a:
                continue
            items.append(
                f'<details style="margin:8px 0;background:#FAF6EC;border:1px solid #E8DFC9;border-radius:8px;padding:16px 20px;">'
                f'<summary style="font-weight:600;color:#2A2A2A;cursor:pointer;font-size:1rem;">{q}</summary>'
                f'<div style="margin-top:10px;color:#5C5651;line-height:1.6;">{a}</div>'
                f'</details>'
            )
        # JSON-LD Schema
        schema = {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            'mainEntity': [
                {'@type': 'Question', 'name': str(f.get('question', '')),
                 'acceptedAnswer': {'@type': 'Answer', 'text': str(f.get('answer', ''))}}
                for f in faqs if f.get('question') and f.get('answer')
            ],
        }
        schema_json = json.dumps(schema, ensure_ascii=False)
        return (
            f'<section class="naturmacher-faqs" style="margin:48px 0;">'
            f'<h2 style="font-size:1.4rem;margin-bottom:18px;color:#2A2A2A;">❓ Häufige Fragen</h2>'
            + ''.join(items)
            + f'<script type="application/ld+json">{schema_json}</script>'
            f'</section>'
        )

    def _compose_html(self, blog: MagvisBlog) -> str:
        parts: list[str] = [blog.toc_html or '']
        for sec in blog.sections:
            t = sec.get('type')
            if t == 'h2':
                parts.append(f'<h2 id="{sec["id"]}" style="margin-top:2rem;color:#2A2A2A;">{escape(sec["title"])}</h2>')
            else:
                parts.append(sec.get('html', ''))
        return '\n\n'.join(p for p in parts if p)

    def _publish_to_shopify(self, blog: MagvisBlog) -> None:
        """Veröffentlicht den Blog-Artikel über shopify_manager (best effort)."""
        import requests
        from ploom.models import PLoomSettings
        ploom_settings = PLoomSettings.objects.filter(user=self.user).first()
        if not ploom_settings or not ploom_settings.default_store:
            logger.info('Kein Shopify-Store konfiguriert — überspringe Blog-Publish')
            return

        store = ploom_settings.default_store

        # Nur Live-Shopify-Blogs verwenden (Workloom-DB kann veraltete Eintraege haben)
        try:
            r = requests.get(
                f'https://{store.shop_domain}/admin/api/2023-10/blogs.json',
                headers={'X-Shopify-Access-Token': store.access_token}, timeout=15,
            )
            r.raise_for_status()
            live_blogs = r.json().get('blogs', [])
        except Exception as exc:
            logger.warning('Shopify-Blog-Liste nicht abrufbar: %s', exc)
            return

        if not live_blogs:
            logger.info('Kein Live-ShopifyBlog — überspringe Publish')
            return

        # Bevorzugt 'news', sonst der erste vorhandene Blog
        live = next((b for b in live_blogs if b.get('handle') == 'news'), live_blogs[0])
        target_blog_id = live['id']
        target_blog_handle = live.get('handle', 'news')

        url = f'https://{store.shop_domain}/admin/api/2023-10/blogs/{target_blog_id}/articles.json'
        payload = {
            'article': {
                'title': blog.seo_title,
                'author': 'Naturmacher',
                'body_html': blog.final_html,
                'tags': self.project.topic,
                'published': True,
            }
        }
        headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json',
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json().get('article', {})
            blog.shopify_blog_id = str(target_blog_id)
            blog.shopify_article_id = str(data.get('id', ''))
            handle = data.get('handle', '')
            if handle:
                blog.shopify_published_url = (
                    f'https://{store.custom_domain or store.shop_domain}'
                    f'/blogs/{target_blog_handle}/{handle}'
                )
            blog.save(update_fields=['shopify_blog_id', 'shopify_article_id', 'shopify_published_url'])
        except Exception as exc:
            logger.warning('Shopify Article-Erstellung: %s', exc)
