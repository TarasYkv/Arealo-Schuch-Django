"""Magvis Blog-Assembler.

Baut den vollständigen Blog-HTML aus Sektions-Bausteinen:
TOC → Intro → YT-Embed → Diagramm → Quiz → Brainstorm → Mini-Spiel
→ Produkt-Card #1 (~50%) → Produkt-Card #2 (letztes Drittel) → 5 FAQs.

Texte: GLM-5.1. Bilder: Gemini.
"""
from __future__ import annotations

import json
import logging
import re
from html import escape
from urllib.parse import urlparse

from django.template.loader import render_to_string
from django.utils import timezone as django_timezone
from django.utils.text import slugify as django_slugify


def _now_isoformat() -> str:
    """ISO-Zeitstempel jetzt — für Shopify published_at, immer mit TZ."""
    return django_timezone.localtime().isoformat(timespec='seconds')

from ..models import MagvisBlog, MagvisImageAsset, MagvisProject
from ..prompts.blog_prompts import (
    NATURMACHER_VOICE,
    facts_prompt,
    faqs_prompt,
    headings_prompt,
    intro_prompt,
    search_intent_prompt,
    section_prompt,
    seo_prompt,
    statistics_extraction_prompt,
    tips_prompt,
    tldr_prompt,
    w_questions_prompt,
)
from .gemini_helper import MagvisGeminiHelper
from .internal_linking_service import MagvisInternalLinkingService
from .llm_client import MagvisLLMClient
from .minigame_generator import generate_minigame, minigame_html
from .quiz_generator import generate_quiz, quiz_html
from .research_service import MagvisResearchService
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
        self.glm = MagvisLLMClient(self.user, self.settings)
        self.gemini = MagvisGeminiHelper(self.user, self.settings)
        self.research = MagvisResearchService(user=self.user)
        self.linking = MagvisInternalLinkingService(self.user, llm_client=self.glm)
        self._shopify_product_cache = {}   # product_id → {handle, image_src}
        self._research_context = ''         # gefüllt vor Sektionen-Generierung
        self._internal_links_text = ''
        self._internal_links_data: dict = {}
        self._section_link_counter = 0       # Rotation der Blog-Vorschlaege pro Sektion
        self._competitor_analysis = ''       # Skyscraper-Map: Themen, Lücken, Differenzierung
        self._competitor_must_topics: list = []  # H2-Themen die fast alle abdecken
        self._search_intent: dict = {}       # informational/transactional + LSI-Keywords
        self._verified_facts: list = []      # Stat-Box-Stats fuer Inline-Verlinkung im Text

    # ------------------------------------------------------------------ public

    def assemble(self) -> MagvisBlog:
        blog, _ = MagvisBlog.objects.get_or_create(project=self.project)

        # Idempotenz: wenn der Blog bereits in Shopify veröffentlicht ist
        # (shopify_article_id gesetzt), Stage komplett überspringen.
        # Verhindert Doppel-Blog bei Worker-Crash + Celery-Retry.
        if blog.shopify_article_id and blog.shopify_published_url:
            self.project.log_stage(
                'blog',
                f'⏭️ Blog bereits veröffentlicht ({blog.shopify_published_url}) — übersprungen',
            )
            return blog

        topic = self.project.topic
        sections: list[dict] = []

        # 1. SEO-Titel + Meta-Description
        self.project.log_stage('blog', f'🎯 SEO + Mid-Volume-Keywords für "{topic}"')
        seo = self._generate_seo()
        blog.seo_title = seo.get('title', topic)[:255]
        blog.seo_description = seo.get('description', '')[:500]
        blog.slug = django_slugify(blog.seo_title)[:255]

        # 2. Headings (Struktur-Skelett)
        headings = self._generate_headings(topic)

        # 0a. RESEARCH + INTERNAL LINKS + INTENT (frueh — für Sektions-Prompts)
        self.project.log_stage('blog', '🔍 Web-Recherche (Brave Search) + interne Links')
        self._do_research_and_linking(topic)
        self.project.log_stage('blog', '🧠 Suchintention klassifizieren + LSI-Keywords')
        self._classify_intent(topic)

        # 0. TITELBILD (Hero, ganz oben) — mit Fallback auf Brainstorm/Diagramm
        self.project.log_stage('blog', '🖼️ Hero-Titelbild via Gemini generieren')
        title_url = self._generate_blog_image(
            kind='title',
            topic_summary=f'Hero image for "{topic}", elegant editorial photo.',
        )
        if title_url:
            sections.append({
                'type': 'title_image', 'id': 'hero',
                'src': title_url,
                'html': self._title_image_html(title_url, blog.seo_title or topic),
            })
        else:
            self.project.log_stage('blog', '⚠ Hero-Titelbild fehlgeschlagen — kommt spaeter via Brainstorm/Diagramm', level='warning')

        # 0a. AUTHOR-BIO-BOX direkt nach Hero — sichtbares E-E-A-T-Author-Signal
        # (Schema-Person ist da, aber Google + Leser brauchen sichtbaren Block).
        sections.append({
            'type': 'author_bio', 'id': 'author-bio',
            'html': self._author_bio_html(),
        })

        # 0b. TL;DR-BOX (vor Intro — Featured-Snippet- + LLM-Optimierung)
        self.project.log_stage('blog', '⚡️ TL;DR-Box generieren (Kernantwort)')
        tldr_data = self.glm.json_chat_with_retry(
            tldr_prompt(topic), expect='object', max_tokens=800, retries=4,
        ) or {}
        # Fallback wenn GLM ein 'summary' oder 'antwort' Key liefert
        if not tldr_data.get('core_answer'):
            for alt_key in ('summary', 'answer', 'antwort', 'kern', 'main'):
                if tldr_data.get(alt_key):
                    tldr_data['core_answer'] = tldr_data[alt_key]
                    break
        # Fallback: GLM-Direct-Call ohne Schema-Strenge
        if not tldr_data.get('core_answer'):
            try:
                fallback = self.glm.text(
                    f'Schreibe in einem Satz die wichtigste Aussage für einen '
                    f'Naturmacher-Blog zum Thema "{topic}". Max. 25 Wörter, '
                    f'antworte nur mit dem Satz, ohne Anführungszeichen.',
                    temperature=0.5,
                ).strip().strip('"').strip()
                if 10 < len(fallback) < 250:
                    tldr_data = {
                        'core_answer': fallback,
                        'bullets': tldr_data.get('bullets', []),
                        'recommendation': tldr_data.get('recommendation', ''),
                    }
            except Exception:
                pass
        if tldr_data.get('core_answer'):
            sections.append({
                'type': 'tldr_box', 'id': 'tldr',
                'html': self._tldr_box_html(tldr_data),
            })
            self.project.log_stage('blog', '✓ TL;DR-Box erstellt')
        else:
            self.project.log_stage('blog', '⚠ TL;DR-Box: GLM lieferte keine Kernantwort', level='warning')

        # 3. Intro
        self.project.log_stage('blog', '✍️ Einleitung (1. Person Naturmacher) schreiben')
        intro_html = self._call_glm(intro_prompt(topic))
        sections.append({'type': 'intro', 'id': 'intro', 'html': intro_html})

        # 3a. STATISTIK-Extraktion (verifizierte Quellen — fuer Inline-Verlinkung
        # in den Sektionen). Die Stat-BOX selbst wird erst AM ENDE des Beitrags
        # platziert (nach FAQs), damit der Lesefluss nicht unterbrochen wird.
        self.project.log_stage('blog', '📊 Statistiken aus Whitelist-Quellen extrahieren')
        verified_stats = self._extract_verified_statistics(topic)
        self._verified_facts = verified_stats or []
        if verified_stats:
            self.project.log_stage('blog', f'✓ {len(verified_stats)} Stats — fuer Inline-Verlinkung im Text + Stat-Box am Ende')

        # 3b. PRODUKT-EMBED #1 (statt Fakten-Box "Wusstest du schon" — User-Wunsch
        # 2026-04-30: Produkt soll Top-Position übernehmen, höhere CTR auf Sale-Funnel)
        if self.project.product_1:
            self.project.log_stage('blog', '🛒 Produkt-Embed #1 (oben, statt Fakten-Box)')
            sections.append({
                'type': 'product', 'id': 'product-1',
                'product_id': str(self.project.product_1.id),
                'html': self._product_card_html(self.project.product_1),
            })

        # 4. Inhaltsverzeichnis (TOC) zwischen Intro und Hauptteil
        toc_headings = [(2, h, slugify(h)) for h in headings]
        toc_html_str = render_toc(toc_headings, minutes=estimate_minutes(intro_html, wpm=220) + 4)
        blog.toc_html = toc_html_str

        self.project.log_stage('blog', '📖 Inhaltsverzeichnis aufbauen')
        # 5. Sektion 1 (1-2 Absätze)
        self.project.log_stage('blog', f'✍️ Sektion 1/6: {(headings[0] if headings else "")[:50]}')
        head1 = headings[0] if headings else 'Worum geht es?'
        slug1 = slugify(head1)
        para1 = self._call_glm(section_prompt(topic, head1))
        self._append_section_safe(sections, head1, slug1, para1, label='Sektion 1')

        # 6. YouTube-Short-Embed
        if self.project.youtube_video_id:
            sections.append({
                'type': 'youtube', 'id': 'yt-embed',
                'video_id': self.project.youtube_video_id,
                'html': embed_html(
                    self.project.youtube_video_id, is_short=True,
                    schema_name=blog.seo_title or self.project.topic,
                    schema_description=blog.seo_description or self.project.topic,
                ),
            })

        # 7. Sektion 2
        self.project.log_stage('blog', f'✍️ Sektion 2/6: {(headings[1] if len(headings) > 1 else "")[:50]}')
        head2 = headings[1] if len(headings) > 1 else 'Hintergrund'
        slug2 = slugify(head2)
        para2 = self._call_glm(section_prompt(topic, head2))
        self._append_section_safe(sections, head2, slug2, para2, label='Sektion 2')

        # 8. Diagramm (Gemini) — mit DB-Fallback bei Fehlschlag
        self.project.log_stage('blog', '🎨 Diagramm-Bild via Gemini + Shopify-CDN-Upload')
        prev_diagram = getattr(blog, 'diagram_image_path', '') or ''
        diagram_url = self._generate_blog_image(
            kind='diagram',
            topic_summary=f'Wichtigste Punkte zum Thema "{topic}" als Infografik'
        )
        if not diagram_url and prev_diagram and prev_diagram.startswith('http'):
            diagram_url = prev_diagram
            self.project.log_stage('blog', '✓ Diagramm-Bild aus DB-Fallback übernommen')
        if diagram_url:
            blog.diagram_image_path = diagram_url
            diagram_alt = (f'Infografik: Wichtigste Aspekte zum Thema "{topic}" '
                            f'mit Geschenkkategorien, Preisrahmen und Tipps — Naturmacher')
            sections.append({
                'type': 'image', 'id': 'diagram', 'src': diagram_url,
                'alt': diagram_alt,
                'html': self._image_html(diagram_url, diagram_alt),
            })

        # 9. Sektion 3
        self.project.log_stage('blog', f'✍️ Sektion 3/6: {(headings[2] if len(headings) > 2 else "")[:50]}')
        head3 = headings[2] if len(headings) > 2 else 'Was du beachten solltest'
        slug3 = slugify(head3)
        para3 = self._call_glm(section_prompt(topic, head3))
        self._append_section_safe(sections, head3, slug3, para3, label='Sektion 3')

        # 9b. W-FRAGEN-BLOCK (nach Sektion 3 — typische Google-Suchanfragen direkt beantwortet)
        self.project.log_stage('blog', '❓ W-Fragen-Block (5 Was/Wie/Wann/Warum/Wer)')
        wq = self.glm.json_chat_with_retry(
            w_questions_prompt(topic), expect='array', max_tokens=2000, retries=3,
        ) or []
        if wq and isinstance(wq, list):
            sections.append({
                'type': 'w_questions', 'id': 'w-questions',
                'html': self._w_questions_html(wq),
            })

        # 10. QUIZ
        self.project.log_stage('blog', '🧠 Quiz mit 4 Fragen via GLM')
        try:
            quiz_data = generate_quiz(topic, self.glm,
                                      num_questions=self.settings.default_quiz_questions or 4)
        except Exception as exc:
            logger.warning('Quiz failed: %s', exc)
            quiz_data = []
        blog.quiz_data = quiz_data
        sections.append({'type': 'quiz', 'id': 'quiz', 'html': quiz_html(quiz_data)})

        # 11. Sektion 4
        self.project.log_stage('blog', f'✍️ Sektion 4/6: {(headings[3] if len(headings) > 3 else "")[:50]}')
        head4 = headings[3] if len(headings) > 3 else 'Tipps & Ideen'
        slug4 = slugify(head4)
        para4 = self._call_glm(section_prompt(topic, head4))
        self._append_section_safe(sections, head4, slug4, para4, label='Sektion 4')

        # 12. PRODUKT-EMBED #2 (ca. Mitte des Beitrags — war früher Produkt 1,
        # ist jetzt Produkt 2, weil Produkt 1 nach oben gewandert ist statt Fakten-Box)
        if self.project.product_2:
            product_card_2_mid = self._product_card_html(self.project.product_2)
            sections.append({
                'type': 'product', 'id': 'product-2',
                'product_id': str(self.project.product_2.id), 'html': product_card_2_mid,
            })

        # 13. Brainstorming-Bild (Gemini) — mit DB-Fallback bei Fehlschlag
        self.project.log_stage('blog', '🌿 Brainstorming-Bild via Gemini + Shopify-CDN-Upload')
        brainstorm_url = self._generate_blog_image(kind='brainstorm', topic_summary='')
        # Fallback: wenn aktuelle Generation failed aber DB hat eine alte URL → nutze die
        if not brainstorm_url and blog.brainstorm_image_path and blog.brainstorm_image_path.startswith('http'):
            brainstorm_url = blog.brainstorm_image_path
            self.project.log_stage('blog', '✓ Brainstorm-Bild aus DB-Fallback übernommen')
        if brainstorm_url:
            blog.brainstorm_image_path = brainstorm_url
            brainstorm_alt = (f'Mind-Map: Brainstorming-Ideen zum Thema "{topic}" '
                               f'als Übersicht persönlicher Geschenkmöglichkeiten — Naturmacher')
            sections.append({
                'type': 'image', 'id': 'brainstorm', 'src': brainstorm_url,
                'alt': brainstorm_alt,
                'html': self._image_html(brainstorm_url, brainstorm_alt),
            })

        # KEIN Hero-Fallback mehr aus Brainstorm/Diagramm.
        # Wenn das echte Title-Image nicht erzeugt werden konnte, bleibt der Blog
        # ohne Hero — ein Mind-Map oder eine Infografik als Featured-Image waere
        # falsch und passt visuell nicht.
        has_hero = any(s.get('type') == 'title_image' for s in sections)
        if not has_hero:
            self.project.log_stage('blog',
                '⚠ Kein Hero — Title-Image-Generierung fehlgeschlagen, kein Fallback verwendet',
                level='warning')

        # 14. Sektion 5
        self.project.log_stage('blog', f'✍️ Sektion 5/6: {(headings[4] if len(headings) > 4 else "")[:50]}')
        head5 = headings[4] if len(headings) > 4 else 'Ein wenig zum Spielen'
        slug5 = slugify(head5)
        para5 = self._call_glm(section_prompt(topic, head5))
        self._append_section_safe(sections, head5, slug5, para5, label='Sektion 5')

        # 15. MINI-SPIEL
        self.project.log_stage('blog', '🎯 Mini-Spiel (5-Schritt-Sortier-Spiel)')
        try:
            game_data = generate_minigame(topic, self.glm)
        except Exception as exc:
            logger.warning('Minigame failed: %s', exc)
            game_data = {}
        blog.minigame_data = game_data
        sections.append({'type': 'minigame', 'id': 'minigame', 'html': minigame_html(game_data)})

        # 16. Sektion 6 (letztes Drittel)
        self.project.log_stage('blog', f'✍️ Sektion 6/6: {(headings[5] if len(headings) > 5 else "")[:50]}')
        head6 = headings[5] if len(headings) > 5 else 'Persönliche Geschenkideen'
        slug6 = slugify(head6)
        para6 = self._call_glm(section_prompt(topic, head6))
        self._append_section_safe(sections, head6, slug6, para6, label='Sektion 6')

        # 17. (entfernt) — Produkt 2 ist jetzt in der Mitte (Pos #12),
        # Produkt 1 ist oben (Pos #3b). 2 Cards reichen — sonst Sale-Spam.

        # 17b. TIPPS-BOX (vor FAQs, im letzten Drittel)
        self.project.log_stage('blog', '✨ Tipps-Box (4 praktische Tipps)')
        tips = self.glm.json_chat_with_retry(
            tips_prompt(topic, num_tips=4), expect='array',
            max_tokens=1500, retries=3,
        ) or _fallback_tips(topic)
        sections.append({
            'type': 'tips_box', 'id': 'tips',
            'html': self._tips_box_html(tips),
        })

        # 17c. DO'S AND DON'TS (User-Wunsch 2026-05-01: 2-Spalten-Tabelle vor FAQs)
        self.project.log_stage('blog', '✅❌ Do\'s and Don\'ts (5+5)')
        from ..prompts.blog_prompts import dos_donts_prompt
        dd = self.glm.json_chat_with_retry(
            dos_donts_prompt(topic), expect='object',
            max_tokens=1500, retries=3,
        ) or {}
        if isinstance(dd, dict) and (dd.get('dos') or dd.get('donts')):
            sections.append({
                'type': 'dos_donts', 'id': 'dos-donts',
                'html': self._dos_donts_html(dd.get('dos') or [], dd.get('donts') or []),
            })

        # 18. FAQs (mit Retry + robust JSON parsing)
        self.project.log_stage('blog', '❓ 5 FAQs + JSON-LD Schema')
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

        # Stat-Box GANZ AM ENDE — sammelnde Quellenangabe nach den FAQs
        if verified_stats:
            sections.append({
                'type': 'statistics_box', 'id': 'stats',
                'html': self._statistics_box_html(verified_stats),
            })

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
        self.project.log_stage('blog', '🚀 Shopify-Blog-Publish (PUT/POST)')
        try:
            self._publish_to_shopify(blog)
        except Exception as exc:
            logger.warning('Shopify-Blog-Publish fehlgeschlagen: %s', exc)

        return blog

    # ----------------------------------------------------------------- helper

    def _format_rotated_internal_links(self) -> str:
        """Liefert pro GLM-Aufruf 2 ROTIERTE Blog-Vorschläge + alle Produkte.

        Damit der GLM nicht in jeder Sektion den gleichen Blog wählt, geben wir
        pro Aufruf nur ein Fenster aus 2 Blogs (rotiert per Counter). Die
        Produkt-Liste bleibt komplett, weil nur 2 Produkte vorhanden sind.
        """
        if not self._internal_links_data:
            return ''
        blogs = self._internal_links_data.get('blogs') or []
        products = self._internal_links_data.get('products') or []
        if not blogs and not products:
            return ''

        parts = []
        if blogs:
            n = len(blogs)
            i1 = self._section_link_counter % n
            picked = [blogs[i1]]
            if n >= 2:
                i2 = (self._section_link_counter + 1) % n
                if i2 != i1:
                    picked.append(blogs[i2])
            self._section_link_counter += 1
            parts.append('VERWANDTE NATURMACHER-BLOG-ARTIKEL (zum Verlinken):')
            for b in picked:
                anchor = (b['anchors'][0] if b.get('anchors') else b.get('title', ''))[:60]
                parts.append(f'  - "{anchor}" → {b["url"]}')
        if products:
            parts.append('\nVERWANDTE NATURMACHER-PRODUKTE (zum Verlinken):')
            for p in products:
                anchor = (p['anchors'][0] if p.get('anchors') else p.get('title', ''))[:60]
                parts.append(f'  - "{anchor}" → {p["url"]}')
        return '\n'.join(parts)

    def _append_section_safe(self, sections: list, title: str, slug: str,
                              html: str, label: str = 'Sektion') -> None:
        """Haengt H2 + Paragraph an die Sektionen — nur wenn der Paragraph
        echten Inhalt hat. Bei leerem html (GLM-Failure nach 3 Retries) wird
        die ganze Sektion ausgelassen, damit kein Heading ohne Text uebrig
        bleibt.
        """
        clean = (html or '').strip()
        # Mindestens 80 Zeichen echten Text — sonst nicht renderbar
        text_only_len = len(re.sub(r'<[^>]+>', '', clean))
        if not clean or text_only_len < 80:
            self.project.log_stage(
                'blog',
                f'⚠ {label} ausgelassen ("{title[:40]}…") — '
                f'GLM lieferte keinen Text nach 3 Versuchen',
                level='warning',
            )
            return
        sections.append({'type': 'h2', 'id': slug, 'title': title})
        sections.append({'type': 'paragraph', 'id': f'{slug}-p', 'html': clean})

    def _call_glm(self, prompt: str) -> str:
        # Research + Links + Intent als System-Erweiterung anhaengen
        system = NATURMACHER_VOICE
        intent = self._search_intent.get('intent', 'informational') if self._search_intent else 'informational'
        lsi = self._search_intent.get('lsi_keywords', []) if self._search_intent else []
        if intent == 'transactional':
            system += '\n\nSUCHINTENTION: Transaktional — der Leser will (nach dem Lesen) entscheiden/kaufen. Sei konkret zu Vorteilen, Anwendungsfaellen.'
        else:
            system += '\n\nSUCHINTENTION: Informationell — der Leser will lernen. Liefere echten Mehrwert, keine Verkaufstexte.'
        if lsi:
            system += f'\n\nLSI-KEYWORDS (semantisch verwandt — natuerlich einbauen, nicht keyword-stuffing): {", ".join(lsi)}'
        if self._research_context:
            system += (
                '\n\nRECHERCHE-KONTEXT (verwende Fakten daraus, niemals 1:1 zitieren, '
                'sondern als Naturmacher in 1. Person mit eigener Stimme einbauen):\n'
                + self._research_context
            )
        if self._competitor_analysis:
            system += (
                '\n\n' + self._competitor_analysis + '\n\n'
                'WICHTIG: Decke alle Pflicht-Themen ab und fülle MINDESTENS eine Content-Lücke '
                'pro Beitrag. Hebe dich durch Naturmacher-Erfahrung (echte Kunden-Anekdoten, '
                'gravierte Töpfe, persönlicher Ton) ab — niemals abschreiben oder kopieren.'
            )
        # Rotation: pro Sektion ein anderes Set von 1-2 Blog-Vorschlaegen anbieten,
        # damit GLM nicht immer denselben Link nimmt.
        rotated_links_text = self._format_rotated_internal_links()
        if rotated_links_text:
            system += (
                '\n\n' + rotated_links_text + '\n\n'
                'INTERNE VERLINKUNGEN — Mittelweg:\n'
                '- Im ganzen Beitrag sollen am Ende ungefähr 2-3 Verweise auf '
                '  verwandte Naturmacher-Beiträge stehen (z.B. „weitere Geschenk-'
                '  Inspiration für andere Berufsgruppen"). Verteile die Links '
                '  über mehrere Sektionen — NICHT alle in dieselbe.\n'
                '- Wenn ein Vorschlag oben thematisch ungefähr zum Sektion-Inhalt '
                '  passt (gleicher Anlass, ähnliche Zielgruppe, verwandtes '
                '  Geschenk-Thema), baue EINEN Link ein. Format: '
                '  <a href="URL">natürlicher Ankertext im Satz</a>.\n'
                '- Bevorzugt am Schluss-Absatz einer Sektion mit einem Satz wie '
                '  „Du suchst weitere Inspiration? Schau auch bei [Anker]".\n'
                '- Anker frei und natürlich umformulieren — NIE 1:1 den '
                '  Vorschlags-Anker übernehmen.\n'
                '- Wenn dieses Thema gar nicht passt: KEINEN Link erzwingen — '
                '  andere Sektionen werden Links bringen.'
            )

        # Verifizierte Fakten fuer Inline-Quellenverlinkung
        if self._verified_facts:
            facts_block = ['\n\nVERIFIZIERTE FAKTEN — bitte im Fliesstext einbauen mit Quellenlink:']
            for f in self._verified_facts[:4]:
                value = f.get('value', '')
                label = f.get('label', '')
                url = f.get('source_url', '')
                source = f.get('source_name', 'Quelle')
                if value and url:
                    facts_block.append(f'  • "{value}" — {label}\n    Quelle: {source}, URL: {url}')
            facts_block.append(
                '\nWenn du eine dieser Aussagen in deinem Text einbaust, ZITIERE die '
                'Quelle als HTML-Link: <a href="URL" target="_blank" rel="noopener">{Quelle}</a>. '
                'Beispiel: "...wie das <a href=\\"https://destatis.de/...\\" target=\\"_blank\\" '
                'rel=\\"noopener\\">Statistische Bundesamt</a> berichtet, gab es 686.000..."\n'
                'WICHTIG: Zitiere NUR diese Fakten — erfinde KEINE eigenen Stats. '
                'Pro Sektion max. 1 Faktenzitat.'
            )
            system += '\n'.join(facts_block)
        # 3-faches Retry mit exponential backoff — schuetzt gegen Z.AI 500er,
        # Timeouts und voruebergehende Netzwerk-Probleme.
        import time as _time
        for attempt in range(3):
            try:
                result = self.glm.text(prompt, system=system, temperature=0.75).strip()
                if result and len(result) >= 80:
                    return result
                logger.warning('GLM-Call Versuch %d: leere/zu kurze Antwort (%d Zeichen)',
                               attempt + 1, len(result) if result else 0)
            except Exception as exc:
                logger.warning('GLM-Call Versuch %d fehlgeschlagen: %s',
                               attempt + 1, exc)
            if attempt < 2:
                _time.sleep(2 * (attempt + 1))
        # Alle 3 Versuche fehlgeschlagen — leerer String, Sektion wird ausgelassen.
        return ''

    def _extract_verified_statistics(self, topic: str) -> list[dict]:
        """Holt 1-4 verifizierte Statistiken/Aussagen aus Whitelist-Quellen.

        Pipeline:
        1. Topic-Transformation: 'geschenk X' → 'X' für Stat-Suche
        2. Stat-fokussierte Web-Suche (research_service.search_statistics)
        3. GLM extrahiert mit quote_excerpt-Pflichtfeld
        4. Live-Verifikation gegen Quell-URL
        """
        # Topic-Transformation: 'geschenk abiturientin' → 'abiturientin abitur'
        # Damit Stat-Suche thematische, nicht produktbezogene Quellen findet
        stat_topic = topic
        for prefix in ('geschenk ', 'geschenkidee ', 'idee '):
            if stat_topic.lower().startswith(prefix):
                stat_topic = stat_topic[len(prefix):].strip()
                break
        # Zusatz: GLM-generierte Schlagwörter für breitere Suche
        try:
            related = self.glm.text(
                f'Liefere 3 sachbezogene Schlagwörter für eine Statistik-Suche '
                f'zum Thema "{stat_topic}". Nur die Wörter, kommagetrennt, kein Präfix. '
                f'Beispiele: "abiturientin" → "abitur, hochschulreife, schulabschluss"; '
                f'"erzieherin" → "erzieher, kindergarten, paedagogik"',
                temperature=0.2,
            ).strip()
            if related and len(related) < 200:
                stat_topic = f'{stat_topic} {related.replace(",", " ")}'
        except Exception:
            pass
        logger.info('Stat-Topic transformiert: %r', stat_topic)

        try:
            stat_results = self.research.search_statistics(stat_topic, num_results=8)
        except Exception as exc:
            logger.warning('Stat-Search fehlgeschlagen: %s', exc)
            return []
        logger.info('Stat-Search Treffer: %d Whitelist-URLs', len(stat_results) if stat_results else 0)
        if not stat_results:
            logger.warning('Keine Stat-Quellen aus Whitelist gefunden')
            return []
        research_text = self.research.format_for_llm(stat_results)

        try:
            extracted = self.glm.json_chat_with_retry(
                statistics_extraction_prompt(topic, research_text),
                expect='array', max_tokens=3000, retries=3,
            ) or []
        except Exception as exc:
            logger.warning('Stat-Extraktion via GLM fehlgeschlagen: %s', exc)
            return []
        if not isinstance(extracted, list):
            return []
        logger.info('GLM extrahierte %d Stat-Kandidaten', len(extracted))

        # Verifikation MIT Recherche-Kontext (Snippet-First)
        verified = []
        for stat in extracted[:6]:
            if not isinstance(stat, dict):
                continue
            try:
                if self.research.verify_statistic(stat, search_results=stat_results):
                    verified.append(stat)
                    logger.info('✓ Stat verifiziert: %s = %s',
                                stat.get('label', '?'), stat.get('value', '?'))
                else:
                    logger.info('✗ Stat verworfen: %s = %s',
                                stat.get('label', '?'), stat.get('value', '?'))
            except Exception as exc:
                logger.warning('Stat-Verifikation Fehler: %s', exc)
        if verified:
            logger.info('%d Stats verifiziert — Box wird gerendert', len(verified))
            return verified[:4]

        # Keine echten Zahlen verifizierbar → Stat-Box komplett weglassen.
        # Eine Quellenliste ohne konkrete Werte ist keine Statistik-Box.
        logger.info('Keine verifizierten Zahlen — Stat-Box wird ausgelassen')
        return []

    def _statistics_box_html(self, stats: list[dict]) -> str:
        """Kompakte Quellenangabe am Ende des Beitrags — als Footnote-Liste."""
        if not stats:
            return ''
        items = ''
        for s in stats:
            value = str(s.get('value', '')).strip()
            label = escape(str(s.get('label', '')))
            url = escape(str(s.get('source_url', '')))
            source = escape(str(s.get('source_name', 'Quelle')))
            if not value or not url:
                continue
            # Kompakte Listen-Zeile: „Wert — Beschreibung. Quelle: X ↗"
            items += (
                '<li style="margin:4px 0;line-height:1.4;color:#5C5651;">'
                f'<strong style="color:#3D5A40;">{escape(value)}</strong> — '
                f'{label}. '
                f'<a href="{url}" target="_blank" rel="noopener" '
                f'style="color:#7D9C80;text-decoration:none;'
                f'border-bottom:1px dotted #7D9C80;">{source} ↗</a>'
                '</li>'
            )
        return (
            '<aside class="naturmacher-statistics" '
            'style="margin:32px auto 0;max-width:680px;'
            'border-top:1px solid rgba(125,156,128,0.3);'
            'padding:14px 4px 0;font-size:0.82rem;">'
            '<div style="color:#7A7264;font-weight:600;margin-bottom:4px;'
            'letter-spacing:0.02em;">📊 Belegbare Aussagen aus geprüften Quellen</div>'
            f'<ul style="margin:0;padding-left:1.2rem;list-style:disc;">{items}</ul>'
            '</aside>'
        )

    def _classify_intent(self, topic: str) -> None:
        """Klassifiziert Suchintention + ermittelt LSI-Keywords."""
        try:
            data = self.glm.json_chat_with_retry(
                search_intent_prompt(topic), expect='object',
                max_tokens=400, retries=2,
            ) or {}
            self._search_intent = data
            logger.info('Intent: %s, LSI: %s',
                        data.get('intent', '?'),
                        data.get('lsi_keywords', []))
        except Exception as exc:
            logger.warning('Intent-Klassifikation fehlgeschlagen: %s', exc)
            self._search_intent = {'intent': 'informational'}

    def _do_research_and_linking(self, topic: str) -> None:
        """Web-Research + interne Links — füllt self._research_context und _internal_links_text."""
        # Research (best effort, fail silent)
        try:
            search_q = f'{topic} Geschenk Idee'
            results = self.research.search(search_q, num_results=4)
            if results:
                self._research_context = self.research.format_for_llm(results)
                logger.info('Research: %d Quellen geladen', len(results))
        except Exception as exc:
            logger.warning('Research fehlgeschlagen: %s', exc)

        # Internal Links (Blogs + Produkte) — eigenen Beitrag ausschließen
        try:
            secondary = self.project.keywords or []
            current_article_id = (self.project.blog.shopify_article_id
                                   if hasattr(self.project, 'blog') else '')
            self._internal_links_data = self.linking.collect(
                topic, secondary, exclude_shopify_id=current_article_id,
            )
            self._internal_links_text = self.linking.format_for_llm(self._internal_links_data)
            n_blogs = len(self._internal_links_data.get('blogs', []))
            n_prods = len(self._internal_links_data.get('products', []))
            logger.info('Internal-Linking: %d Blogs + %d Produkte gefunden', n_blogs, n_prods)
        except Exception as exc:
            logger.warning('Internal-Linking fehlgeschlagen: %s', exc)

        # Skyscraper-Wettbewerbs-Analyse (Top-Treffer auslesen + Lücken finden)
        self._analyze_competitors(topic)

    def _analyze_competitors(self, topic: str) -> None:
        """Skyscraper-Methode: Top-Wettbewerber-Beiträge auslesen, GLM identifiziert
        verbreitete H2-Themen, Argumente und Content-Lücken.

        Füllt self._competitor_analysis (Text-Block für Sektion-Prompts) und
        self._competitor_must_topics (Liste der Pflicht-Themen).
        """
        self.project.log_stage('blog', '🔬 Wettbewerbs-Analyse: Top-Beiträge auslesen')
        try:
            competitors = self.research.analyze_top_competitors(topic, n=8)
        except Exception as exc:
            logger.warning('Wettbewerbs-Analyse fehlgeschlagen: %s', exc)
            return
        if not competitors:
            self.project.log_stage('blog', '⚠ Keine analysierbaren Wettbewerber-Beiträge gefunden', level='warning')
            return

        bodies = []
        for i, c in enumerate(competitors[:7], 1):
            body = (c.get('body_text') or '')[:1500]
            if not body:
                continue
            host = urlparse(c.get('url', '')).netloc.replace('www.', '')
            bodies.append(f'=== [{i}] {host} — {c.get("title", "")[:80]} ===\n{body}')
        if not bodies:
            return

        self.project.log_stage('blog', f'📥 {len(bodies)} Wettbewerber-Beiträge geladen — GLM analysiert')
        prompt = (
            f'Analysiere die folgenden {len(bodies)} TOP-Wettbewerber-Beiträge zum Thema '
            f'"{topic}". Wir wollen einen Beitrag schreiben, der besser ist als jeder einzelne — '
            f'alle wichtigen Themen abdeckt UND zusätzliche Aspekte einbringt, die keiner hat.\n\n'
            f'{chr(10).join(bodies)}\n\n'
            f'Liefere als JSON-Objekt:\n'
            f'{{\n'
            f'  "common_h2_topics": ["Thema 1", "Thema 2", ...],\n'
            f'    // 5-8 H2-Themen, die fast alle Beiträge abdecken (PFLICHT für unseren Beitrag)\n'
            f'  "key_arguments": ["Argument 1", ...],\n'
            f'    // 4-6 Kern-Argumente, die mehrfach vorkommen\n'
            f'  "concrete_examples": ["Beispiel 1", ...],\n'
            f'    // 4-6 konkrete Beispiele/Daten/Geschenkideen aus den Beiträgen\n'
            f'  "content_gaps": ["Lücke 1", ...],\n'
            f'    // 3-5 Aspekte, die FEHLEN — unsere SEO-Chance, dort zu glänzen\n'
            f'  "differentiation_ideas": ["Idee 1", ...]\n'
            f'    // 3-4 wie wir uns mit Naturmacher-Erfahrung (gravierte Töpfe, persönlich) abheben\n'
            f'}}\n\n'
            f'Antworte AUSSCHLIESSLICH mit dem JSON-Objekt. Korrektes Deutsch mit Umlauten.'
        )
        try:
            analysis = self.glm.json_chat_with_retry(
                prompt, expect='object', max_tokens=2500, retries=2,
            ) or {}
        except Exception as exc:
            logger.warning('GLM-Wettbewerbsanalyse fehlgeschlagen: %s', exc)
            return
        if not isinstance(analysis, dict) or not analysis:
            return

        self._competitor_must_topics = list(analysis.get('common_h2_topics', []))[:8]
        n_topics = len(self._competitor_must_topics)
        n_gaps = len(analysis.get('content_gaps', []))
        self.project.log_stage('blog',
            f'📐 Wettbewerber-Map: {n_topics} verbreitete H2-Themen, {n_gaps} Content-Lücken identifiziert')

        # Kompakter Text-Block fuer alle GLM-Sektion-Prompts
        parts = ['=== WETTBEWERBER-ANALYSE (Skyscraper-Map) ===']
        if analysis.get('common_h2_topics'):
            parts.append('Themen die fast alle TOP-Beiträge abdecken — bei uns auch:')
            for t in analysis['common_h2_topics'][:8]:
                parts.append(f'  • {t}')
        if analysis.get('key_arguments'):
            parts.append('\nKern-Argumente die in mehreren Beiträgen vorkommen:')
            for a in analysis['key_arguments'][:6]:
                parts.append(f'  • {a}')
        if analysis.get('concrete_examples'):
            parts.append('\nKonkrete Beispiele/Geschenkideen aus den TOP-Beiträgen:')
            for e in analysis['concrete_examples'][:6]:
                parts.append(f'  • {e}')
        if analysis.get('content_gaps'):
            parts.append('\n>>> CONTENT-LÜCKEN — UNSERE CHANCE (unbedingt mit reinnehmen):')
            for g in analysis['content_gaps'][:5]:
                parts.append(f'  • {g}')
        if analysis.get('differentiation_ideas'):
            parts.append('\n>>> DIFFERENZIERUNG mit Naturmacher-Erfahrung:')
            for d in analysis['differentiation_ideas'][:4]:
                parts.append(f'  • {d}')
        parts.append('=== ENDE Wettbewerber-Map ===')
        self._competitor_analysis = '\n'.join(parts)

    def _generate_seo(self) -> dict:
        try:
            data = self.glm.json_chat(seo_prompt(self.project.topic))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {'title': self.project.topic, 'description': self.project.topic}

    def _generate_headings(self, topic: str) -> list[str]:
        # Robuster: 3 Retries via json_chat_with_retry + max_tokens hoch.
        try:
            data = self.glm.json_chat_with_retry(
                headings_prompt(topic), expect='array',
                max_tokens=1500, retries=3,
            )
            if isinstance(data, list) and len(data) >= 4:
                cleaned = [str(h).strip() for h in data if h]
                if cleaned:
                    return cleaned
        except Exception as exc:
            logger.warning('Headings-Generation fehlgeschlagen: %s', exc)
        # Fallback: Topic Title-Case + sinnvollere Formulierungen, KEIN
        # "Was ist {topic} eigentlich?" (klingt wie eine Tautologie).
        topic_tc = topic.strip().title()
        return [
            f'Was {topic_tc} besonders macht',
            f'Worauf du bei einem Geschenk für {topic_tc} achten solltest',
            f'Persönliche Geschenkideen mit Bedeutung',
            f'Tipps für die richtige Auswahl',
            f'Häufige Anlässe und ideale Geschenke',
            f'Weitere Geschenkideen rund um {topic_tc}',
        ]

    def _generate_blog_image(self, kind: str, topic_summary: str = '') -> str:
        try:
            if kind == 'title':
                result = self.gemini.generate_title_image(self.project.topic, topic_summary)
            elif kind == 'diagram':
                result = self.gemini.generate_diagram(self.project.topic, topic_summary)
            elif kind == 'brainstorm':
                result = self.gemini.generate_brainstorm(self.project.topic)
            else:
                logger.warning('Unbekannter Bild-kind=%r — fallback Brainstorm', kind)
                result = self.gemini.generate_brainstorm(self.project.topic)
        except Exception as exc:
            logger.warning('Gemini-%s fehlgeschlagen: %s', kind, exc)
            return ''
        if not result.get('success'):
            return ''

        # SEO-freundlicher Filename + Alt-Text statt magvis_<kind>_<uuid>
        topic_slug = django_slugify(self.project.topic)[:60]
        kind_label = {
            'title': 'titelbild',
            'diagram': 'infografik',
            'brainstorm': 'mindmap',
        }.get(kind, kind)
        kind_alt = {
            'title': f'{self.project.topic} — persönliche Geschenkideen von Naturmacher',
            'diagram': f'Infografik: Wichtigste Punkte zu {self.project.topic}',
            'brainstorm': f'Mind-Map: Brainstorming zu {self.project.topic}',
        }.get(kind, f'{self.project.topic} — {kind}')
        # Kurzer Hash hinten dran, damit Shopify keine Konflikte hat
        short_id = self.project.id.hex[:6] if hasattr(self.project.id, 'hex') else str(self.project.id)[:6]
        seo_filename = f'{topic_slug}-{kind_label}-{short_id}'

        cdn_url = self._upload_to_shopify_files(
            result.get('abs_path', ''),
            seo_filename,
            alt_text=kind_alt,
        )
        return cdn_url or result.get('rel_path', '') or result.get('url', '')

    def _upload_to_shopify_files(self, abs_path: str, filename: str, alt_text: str = '') -> str:
        """Laedt ein Bild zu Shopify-Files hoch und liefert FINALE CDN-URL.

        Polling für cdn.shopify.com URL: blogprep.shopify_files liefert
        initial nur die temporaere staged-URL (1h gueltig). Wir pollen
        Shopify GraphQL bis die finale CDN-URL bereit ist (max. 30s).
        """
        import base64
        import os
        import time
        if not abs_path or not os.path.exists(abs_path):
            return ''
        try:
            from ploom.models import PLoomSettings
            from blogprep.shopify_files import ShopifyFilesService
            ploom_s = PLoomSettings.objects.filter(user=self.user).first()
            if not ploom_s or not ploom_s.default_store:
                return ''
            with open(abs_path, 'rb') as fh:
                b64 = base64.b64encode(fh.read()).decode('utf-8')
            svc = ShopifyFilesService(ploom_s.default_store)
            ok, url, file_id = svc.upload_image_from_base64(b64, filename, alt_text=alt_text)
            if not ok:
                return ''
            # Wenn URL schon CDN-URL: gut, fertig
            if 'cdn.shopify.com' in url:
                return url
            # Sonst: Polling auf finale CDN-URL (max. 30s, alle 3s)
            if file_id:
                cdn = self._poll_shopify_file_url(svc, file_id, max_attempts=10, delay=3)
                if cdn:
                    return cdn
            # Fallback: was wir haben (staged-URL — 1h gueltig)
            return url
        except Exception as exc:
            logger.warning('Shopify-Files-Upload fehlgeschlagen (%s): %s', filename, exc)
            return ''

    def _poll_shopify_file_url(self, svc, file_id: str, max_attempts: int = 10,
                                 delay: int = 3) -> str:
        """Pollt Shopify GraphQL bis die finale CDN-URL eines MediaImage bereit ist."""
        import requests as _requests
        import time as _time
        query = """
        query getFile($id: ID!) {
          node(id: $id) {
            ... on MediaImage {
              image { url }
              fileStatus
            }
          }
        }
        """
        for attempt in range(max_attempts):
            try:
                resp = _requests.post(
                    svc.graphql_url,
                    json={'query': query, 'variables': {'id': file_id}},
                    headers=svc.headers, timeout=15,
                )
                resp.raise_for_status()
                node = resp.json().get('data', {}).get('node') or {}
                status = node.get('fileStatus', '')
                image = node.get('image') or {}
                url = image.get('url', '')
                if url and 'cdn.shopify.com' in url:
                    logger.info('CDN-URL ready (attempt %d): %s', attempt + 1, url[:80])
                    return url
                if status in ('FAILED', 'ERROR'):
                    logger.warning('Shopify-File-Status: %s', status)
                    return ''
            except Exception as exc:
                logger.warning('Polling-Fehler (attempt %d): %s', attempt + 1, exc)
            _time.sleep(delay)
        logger.warning('CDN-URL nach %d Polls nicht bereit für %s', max_attempts, file_id)
        return ''

    def _shopify_product_info(self, product) -> dict:
        """Holt Live-Daten (handle, featured-image-src) eines Shopify-Produkts."""
        import requests
        if not product or not product.shopify_product_id:
            return {'handle': '', 'image_src': ''}
        if product.shopify_product_id in self._shopify_product_cache:
            return self._shopify_product_cache[product.shopify_product_id]
        store = product.shopify_store
        url = (f'https://{store.shop_domain}/admin/api/2023-10/products/'
               f'{product.shopify_product_id}.json?fields=handle,image,images')
        info = {'handle': '', 'image_src': ''}
        try:
            r = requests.get(url, headers={'X-Shopify-Access-Token': store.access_token}, timeout=15)
            r.raise_for_status()
            sd = r.json().get('product', {}) or {}
            info['handle'] = sd.get('handle', '')
            img = sd.get('image') or {}
            info['image_src'] = img.get('src', '') or (
                (sd.get('images') or [{}])[0].get('src', '')
            )
        except Exception as exc:
            logger.warning('Shopify-Produkt-Live-Abfrage fehlgeschlagen: %s', exc)
        self._shopify_product_cache[product.shopify_product_id] = info
        return info

    def _author_bio_html(self) -> str:
        """Kompakter Author-Bio-Block — mobile-optimiert via Media Query.

        Mobile (≤640px): klein (48px Foto, Bio-Lang ausgeblendet, nur Bio-Kurz).
        Desktop: volle Bio sichtbar. Schema.Person mit Foto + sameAs (IG).
        """
        return (
            '<style>'
            '.mb-auth{padding:0.3rem;margin:0.8rem 0;background:#FAF6EC;'
            'border-left:3px solid #5C8A6B;border-radius:6px;font-size:0.85rem;}'
            '.mb-auth-head{display:flex;align-items:center;gap:0.55rem;'
            'margin-bottom:0.15rem;}'
            '.mb-auth img{width:90px;height:90px;border-radius:50%;'
            'object-fit:cover;flex-shrink:0;}'
            '.mb-auth-name{font-weight:600;color:#2A2A2A;line-height:1.25;}'
            '.mb-auth-role{color:#7A7264;font-size:0.75rem;display:block;}'
            '.mb-auth-bio{margin:0;color:#5C5651;font-size:0.82rem;'
            'line-height:1.45;}'
            '.mb-auth-bio-long{display:none;}'
            '.mb-auth-links{margin-top:0.3rem;display:flex;flex-wrap:wrap;'
            'gap:0.2rem 0.9rem;align-items:center;}'
            '.mb-auth-links a{font-size:0.78rem;text-decoration:none;}'
            '.mb-auth-links a:first-child{color:#5C8A6B;font-weight:500;}'
            '.mb-auth-links a:last-child{color:#7A7264;}'
            '@media (min-width:641px){'
            '.mb-auth{padding:0.85rem 1rem;font-size:0.9rem;}'
            '.mb-auth img{width:110px;height:110px;}'
            '.mb-auth-head{gap:0.85rem;}'
            '.mb-auth-bio-short{display:none;}'
            '.mb-auth-bio-long{display:block;}'
            '.mb-auth-bio{font-size:0.88rem;line-height:1.55;margin-top:0.5rem;}'
            '}'
            '</style>'
            '<aside class="mb-auth" itemprop="author" itemscope '
            'itemtype="https://schema.org/Person">'
            '<div class="mb-auth-head">'
            '<img src="https://cdn.shopify.com/s/files/1/0696/9494/7595/files/'
            'lernrfi4k3sv47iojnea7iat9m._SX300_CR0_0_300_300.jpg?v=1734014095" '
            'alt="Lisa Yuzkiv — Autorin und Mitgründerin Naturmacher" itemprop="image" '
            'loading="lazy" width="52" height="52">'
            '<div>'
            '<span class="mb-auth-name" itemprop="name">Lisa Yuzkiv</span>'
            '<span class="mb-auth-role" itemprop="jobTitle">'
            'Autorin / Mitgründerin Naturmacher</span>'
            '</div>'
            '</div>'
            '<p class="mb-auth-bio" itemprop="description">'
            '<span class="mb-auth-bio-short">'
            'Geboren 1989 in Darmstadt, staatlich anerkannte Erzieherin und Mutter von '
            'zwei Söhnen. 2019 gründete sie mit ihrem Mann den Online-Shop Naturmacher '
            'für gravierte Blumentöpfe. Lebt mit Familie und Haustieren an der Bergstraße.'
            '</span>'
            '<span class="mb-auth-bio-long">'
            'Lisa Janina Yuzkiv, geboren 1989 in Darmstadt, ist staatlich anerkannte '
            'Erzieherin und Mutter von zwei Söhnen. 2019 gründete sie mit ihrem Mann den '
            'Online-Shop „Naturmacher", in welchem heute gravierte Blumentöpfe verkauft '
            'werden. Sie lebt mit ihrer Familie und Haustieren an der Bergstraße.'
            '</span>'
            '</p>'
            '<div class="mb-auth-links">'
            '<a href="https://naturmacher.de/pages/uber-uns" itemprop="url">'
            'Mehr über Lisa →</a>'
            '<a href="https://www.instagram.com/lisa_migraene_und_ernaehrung" '
            'itemprop="sameAs" target="_blank" rel="noopener" '
            'aria-label="Lisa auf Instagram folgen">'
            '📷 Instagram</a>'
            '</div>'
            '</aside>'
        )

    def _image_html(self, src_or_rel: str, alt: str) -> str:
        from django.conf import settings as django_settings
        # http(s) → CDN, sonst lokal /media/
        if src_or_rel.startswith(('http://', 'https://', '/')):
            url = src_or_rel
        else:
            url = django_settings.MEDIA_URL + src_or_rel
        return (
            f'<figure style="margin:2.5rem 0;text-align:center;">'
            f'<img src="{url}" alt="{escape(alt)}" '
            f'style="max-width:100%;height:auto;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,0.08);">'
            f'<figcaption style="margin-top:0.5rem;font-size:0.9rem;color:#7A7264;">{escape(alt)}</figcaption>'
            f'</figure>'
        )

    def _product_card_html(self, product) -> str:
        """Produkt-Embed-Card im Naturmacher-Stil (Bild links, Text+CTA rechts).

        Holt handle + Featured-Image-CDN-URL live aus Shopify (nicht aus DB,
        weil die Bilder dort als lokale /media-Pfade gespeichert sind).
        """
        store = getattr(product, 'shopify_store', None)
        info = self._shopify_product_info(product)
        handle = info.get('handle') or getattr(product, 'handle', '') or ''
        img_url = info.get('image_src', '')

        # Storefront-URL (nicht Admin!)
        if store and handle:
            domain = store.custom_domain or store.shop_domain
            url = f'https://{domain}/products/{handle}'
        else:
            url = '#'

        # Fallback: lokale Bilder aus PLoomProductImage
        if not img_url:
            featured = product.images.filter(is_featured=True).first() or product.images.first()
            if featured and featured.external_url:
                img_url = featured.external_url

        title = escape(product.title or 'Produkt')
        desc = escape((product.seo_description or product.description or '')[:140])

        return f'''<!-- NM-PRODUCT-CARD -->
<style>
.nm-pc{{background:#FAF6EC;border:1px solid #E8DFC9;border-radius:10px;padding:0.25rem;margin:1.4rem 0;box-shadow:0 2px 10px rgba(0,0,0,0.04);}}
.nm-pc-head{{display:flex;align-items:center;gap:0.5rem;margin-bottom:0.4rem;}}
.nm-pc-img{{flex:0 0 160px;display:block;border-radius:8px;overflow:hidden;}}
.nm-pc-img img{{width:100%;height:160px;object-fit:cover;display:block;}}
.nm-pc-label{{font-size:0.7rem;color:#7A7264;text-transform:uppercase;letter-spacing:0.05em;font-weight:500;}}
.nm-pc-title{{margin:0 0 0.35rem;font-size:0.95rem;color:#2A2A2A;line-height:1.3;font-weight:600;}}
.nm-pc-desc{{margin:0 0 0.55rem;font-size:0.82rem;color:#5C5651;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.nm-pc-cta{{display:inline-block;background:#D4AB32;color:#fff;padding:0.45rem 0.9rem;text-decoration:none;border-radius:5px;font-weight:600;font-size:0.78rem;}}
@media (min-width:641px){{
.nm-pc{{padding:1.1rem 1.25rem;border-radius:14px;margin:1.8rem 0;box-shadow:0 4px 18px rgba(0,0,0,0.05);}}
.nm-pc-head{{gap:0.85rem;margin-bottom:0.7rem;}}
.nm-pc-img{{flex:0 0 110px;}}
.nm-pc-img img{{height:110px;}}
.nm-pc-label{{font-size:0.78rem;}}
.nm-pc-title{{font-size:1.15rem;margin-bottom:0.5rem;}}
.nm-pc-desc{{font-size:0.92rem;line-height:1.5;-webkit-line-clamp:unset;margin-bottom:0.9rem;}}
.nm-pc-cta{{padding:0.65rem 1.4rem;font-size:0.9rem;border-radius:6px;}}
}}
</style>
<div class="nm-pc">
  <div class="nm-pc-head">
    <a href="{url}" class="nm-pc-img" aria-label="{title}">
      <img src="{img_url}" alt="{title}">
    </a>
    <div class="nm-pc-label">💡 Geschenkidee</div>
  </div>
  <h3 class="nm-pc-title">{title}</h3>
  <p class="nm-pc-desc">{desc}</p>
  <a href="{url}" class="nm-pc-cta">Mehr erfahren →</a>
</div>'''

    def _tldr_box_html(self, data: dict) -> str:
        """TL;DR-Box am Anfang des Blogs — für Featured Snippets + LLMs."""
        core = escape(str(data.get('core_answer', '')))
        bullets = data.get('bullets') or []
        recommendation = escape(str(data.get('recommendation', '')))
        if not core:
            return ''
        bullet_html = ''.join(
            f'<li style="margin:4px 0;color:#3D5A40;">{escape(str(b))}</li>'
            for b in bullets if b
        )
        rec_html = ''
        if recommendation:
            rec_html = (
                f'<div style="margin-top:12px;padding-top:10px;'
                f'border-top:1px dashed rgba(125,156,128,0.3);'
                f'font-size:0.92rem;color:#3D5A40;">'
                f'<strong>Naturmacher-Tipp:</strong> {recommendation}'
                f'</div>'
            )
        return (
            '<aside class="naturmacher-tldr" '
            'style="margin:24px auto 28px;max-width:680px;'
            'background:linear-gradient(135deg,#FFFCF4 0%,#F8F1DA 100%);'
            'border:1px solid rgba(212,171,50,0.4);border-radius:12px;'
            'padding:18px 22px;box-shadow:0 2px 14px rgba(212,171,50,0.08);">'
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
            '<span style="font-size:1.2rem;">⚡️</span>'
            '<strong style="color:#8A6F1F;font-size:0.85rem;letter-spacing:0.08em;text-transform:uppercase;">In 30 Sekunden</strong>'
            '</div>'
            f'<p style="margin:0 0 10px;font-size:1.05rem;color:#2A2A2A;line-height:1.5;font-weight:500;">{core}</p>'
            f'<ul style="margin:0;padding-left:18px;">{bullet_html}</ul>'
            f'{rec_html}'
            '</aside>'
        )

    def _w_questions_html(self, items: list) -> str:
        """W-Fragen-Block — typische Google-Suchanfragen direkt beantwortet."""
        if not items:
            return ''
        rows = ''
        for it in items[:5]:
            if not isinstance(it, dict):
                continue
            q = escape(str(it.get('question', '')))
            a = escape(str(it.get('answer', '')))
            if not q or not a:
                continue
            rows += (
                '<div style="padding:14px 0;border-bottom:1px solid #E8DFC9;">'
                f'<div style="font-weight:600;color:#3D5A40;font-size:1.02rem;margin-bottom:6px;">'
                f'<span style="color:#D4AB32;margin-right:6px;">?</span>{q}'
                '</div>'
                f'<div style="color:#5C5651;font-size:0.95rem;line-height:1.55;">{a}</div>'
                '</div>'
            )
        return (
            '<section class="naturmacher-w-questions" '
            'style="margin:36px auto;max-width:680px;background:#FAF6EC;'
            'border:1px solid #E8DFC9;border-radius:12px;padding:8px 24px 18px;">'
            '<h3 style="margin:18px 0 6px;color:#3D5A40;font-size:1.2rem;'
            'border-bottom:2px solid rgba(125,156,128,0.25);padding-bottom:8px;">'
            'Die häufigsten Fragen direkt beantwortet</h3>'
            f'{rows}'
            '</section>'
        )

    def _title_image_html(self, src: str, alt_title: str) -> str:
        """Hero-Titelbild im Blog (16:9, full-width)."""
        return (
            f'<figure style="margin:0 0 28px 0;border-radius:14px;overflow:hidden;'
            f'box-shadow:0 6px 24px rgba(0,0,0,0.08);">'
            f'<img src="{escape(src)}" alt="{escape(alt_title)}" '
            f'style="width:100%;height:auto;display:block;object-fit:cover;">'
            f'</figure>'
        )

    def _facts_box_html(self, facts: list) -> str:
        """Fakten-Box (kompakt, Grid 2x2)."""
        if not facts:
            return ''
        items = ''
        for f in facts:
            if not isinstance(f, dict):
                continue
            icon = escape(str(f.get('icon', '🌱')))
            title = escape(str(f.get('title', '')))
            text = escape(str(f.get('text', '')))
            if not text:
                continue
            items += (
                '<div style="display:flex;gap:8px;align-items:flex-start;padding:8px 10px;'
                'background:rgba(255,255,255,0.5);border-radius:6px;">'
                f'<span style="font-size:1.05rem;line-height:1.2;flex-shrink:0;">{icon}</span>'
                '<div style="font-size:0.85rem;line-height:1.4;">'
                f'<strong style="color:#3D5A40;">{title}:</strong> '
                f'<span style="color:#5C5651;">{text}</span>'
                '</div></div>'
            )
        return (
            '<aside class="naturmacher-facts-box" '
            'style="margin:24px auto;max-width:680px;'
            'background:linear-gradient(135deg,#F4F8F0 0%,#E8EDDF 100%);'
            'border-left:3px solid #7D9C80;border-radius:8px;padding:14px 16px;'
            'font-family:inherit;">'
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
            '<span style="font-size:1.05rem;">📚</span>'
            '<strong style="color:#3D5A40;font-size:0.95rem;letter-spacing:0.02em;text-transform:uppercase;">Wusstest du schon?</strong>'
            '</div>'
            f'<div style="display:flex;flex-direction:column;gap:8px;">{items}</div>'
            '</aside>'
        )

    def _tips_box_html(self, tips: list) -> str:
        """Tipps-Box mit HowTo-JSON-LD-Schema."""
        if not tips:
            return ''
        items = ''
        howto_steps = []
        for i, t in enumerate(tips, 1):
            if not isinstance(t, dict):
                continue
            icon = escape(str(t.get('icon', '💡')))
            title_t = escape(str(t.get('title', '')))
            text = escape(str(t.get('text', '')))
            if not text:
                continue
            items += (
                '<div style="display:flex;gap:8px;align-items:flex-start;padding:8px 10px;'
                'background:rgba(255,255,255,0.5);border-radius:6px;">'
                f'<span style="font-size:1.05rem;line-height:1.2;flex-shrink:0;">{icon}</span>'
                '<div style="font-size:0.85rem;line-height:1.4;">'
                f'<strong style="color:#8A6F1F;">{title_t}:</strong> '
                f'<span style="color:#5C5651;">{text}</span>'
                '</div></div>'
            )
            howto_steps.append({
                '@type': 'HowToStep',
                'position': i,
                'name': str(t.get('title', '')),
                'text': str(t.get('text', '')),
            })
        # HowTo JSON-LD
        howto_schema = ''
        if howto_steps:
            howto = {
                '@context': 'https://schema.org',
                '@type': 'HowTo',
                'name': f'Praktische Tipps zum Thema {self.project.topic}',
                'step': howto_steps,
            }
            howto_schema = (
                f'<script type="application/ld+json">{json.dumps(howto, ensure_ascii=False)}</script>'
            )
        return howto_schema + (
            '<aside class="naturmacher-tips-box" '
            'style="margin:24px auto;max-width:680px;'
            'background:linear-gradient(135deg,#FBF6E5 0%,#F5EDD0 100%);'
            'border-left:3px solid #D4AB32;border-radius:8px;padding:14px 16px;'
            'font-family:inherit;">'
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
            '<span style="font-size:1.05rem;">✨</span>'
            '<strong style="color:#8A6F1F;font-size:0.95rem;letter-spacing:0.02em;text-transform:uppercase;">Tipps & Tricks</strong>'
            '</div>'
            f'<div style="display:flex;flex-direction:column;gap:8px;">{items}</div>'
            '</aside>'
        )

    def _dos_donts_html(self, dos: list, donts: list) -> str:
        """2-Spalten-Tabelle mit Do's and Don'ts vor den FAQs."""
        if not dos and not donts:
            return ''
        max_rows = max(len(dos), len(donts))
        rows = ''
        for i in range(max_rows):
            do_text = escape(str(dos[i])) if i < len(dos) else ''
            dont_text = escape(str(donts[i])) if i < len(donts) else ''
            rows += (
                '<tr>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #DDE7DB;'
                f'color:#2A4A2A;line-height:1.5;font-size:0.95rem;">'
                f'{("✓ " + do_text) if do_text else ""}</td>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #F2DCD9;'
                f'color:#5A2A2A;line-height:1.5;font-size:0.95rem;">'
                f'{("✗ " + dont_text) if dont_text else ""}</td>'
                '</tr>'
            )
        return (
            '<aside style="margin:28px 0;background:#FAF6EC;border-radius:14px;'
            'padding:18px 14px;border:1px solid #E8DFC9;">'
            '<h3 style="margin:0 0 14px;color:#3D5A40;font-size:1.05rem;'
            'letter-spacing:0.02em;text-transform:uppercase;">Do\'s and Don\'ts</h3>'
            '<table style="width:100%;border-collapse:collapse;">'
            '<thead><tr>'
            '<th align="left" style="padding:10px 14px;background:#E8F2E0;'
            'color:#2A4A2A;border-radius:8px 0 0 0;font-size:0.9rem;'
            'letter-spacing:0.05em;">DO\'S</th>'
            '<th align="left" style="padding:10px 14px;background:#FBE4E0;'
            'color:#5A2A2A;border-radius:0 8px 0 0;font-size:0.9rem;'
            'letter-spacing:0.05em;">DON\'TS</th>'
            '</tr></thead>'
            f'<tbody>{rows}</tbody>'
            '</table>'
            '</aside>'
        )

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
        # Reihenfolge: BlogPosting-Schema → TOC → restliche Sektionen.
        # title_image NICHT in body_html — wird als Article-Featured-Image
        # an Shopify übergeben (Theme rendert es als Hero, vermeidet Duplikat).
        parts: list[str] = []
        # BlogPosting JSON-LD ganz am Anfang
        bp_schema = self._blogposting_schema(blog)
        if bp_schema:
            parts.append(bp_schema)
        if blog.toc_html:
            parts.append(blog.toc_html)
        for sec in blog.sections:
            t = sec.get('type')
            if t == 'title_image':
                continue  # geht als article.image an Shopify
            if t == 'h2':
                parts.append(
                    f'<h2 id="{sec["id"]}" '
                    f'style="margin:2.4rem 0 0.8rem 0;color:#3D5A40;'
                    f'font-weight:600;letter-spacing:-0.01em;'
                    f'border-bottom:2px solid rgba(125,156,128,0.25);padding-bottom:6px;">'
                    f'{escape(sec["title"])}</h2>'
                )
            else:
                parts.append(sec.get('html', ''))
        return '\n\n'.join(p for p in parts if p)

    def _blogposting_schema(self, blog: MagvisBlog) -> str:
        """BlogPosting JSON-LD — Pflicht-Schema fuer SERP-Rich-Snippets."""
        from datetime import datetime, timezone as _tz
        # Hero-Bild URL
        hero_section = next((s for s in blog.sections
                              if s.get('type') == 'title_image'), None)
        image_url = (hero_section.get('src') if hero_section else
                     blog.diagram_image_path or '')
        published_iso = (blog.created_at or datetime.now(_tz.utc)).isoformat()
        # dateModified = jetzt (jeder Re-Run aktualisiert den Artikel-Inhalt).
        # Google bevorzugt aktuell-gepflegte Inhalte; statisches dateModified =
        # datePublished signalisiert "wurde nie aktualisiert".
        modified_iso = datetime.now(_tz.utc).isoformat()
        canonical_url = blog.shopify_published_url or ''
        schema = {
            '@context': 'https://schema.org',
            '@type': 'BlogPosting',
            'headline': blog.seo_title or self.project.topic,
            'description': blog.seo_description or '',
            'author': {
                '@type': 'Person',
                'name': 'Lisa Yuzkiv',
                'url': 'https://naturmacher.de/pages/uber-uns',
                'jobTitle': 'Mitgründerin Naturmacher',
                'sameAs': [
                    'https://www.instagram.com/lisa_migraene_und_ernaehrung',
                ],
                'worksFor': {
                    '@type': 'Organization',
                    'name': 'Naturmacher',
                    'url': 'https://naturmacher.de',
                },
            },
            'publisher': {
                '@type': 'Organization',
                'name': 'Naturmacher',
                'logo': {
                    '@type': 'ImageObject',
                    'url': 'https://naturmacher.de/cdn/shop/files/Logo_Naturmacher.png',
                },
            },
            'datePublished': published_iso,
            'dateModified': modified_iso,
        }
        if image_url:
            schema['image'] = image_url
        if canonical_url:
            schema['mainEntityOfPage'] = {
                '@type': 'WebPage',
                '@id': canonical_url,
            }
        schema_json = json.dumps(schema, ensure_ascii=False)
        return f'<script type="application/ld+json">{schema_json}</script>'

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

        # Title-Bild als Article-Image (Featured-Image) setzen — Theme rendert
        # das automatisch als Hero. Aus body_html lassen wir es weg (sonst doppelt).
        title_url = ''
        for sec in blog.sections:
            if sec.get('type') == 'title_image' and sec.get('src', '').startswith('http'):
                title_url = sec['src']
                break

        # Author = "Lisa Yuzkiv" für Author-Box-App.
        # Markierung (zusätzlich zum standard 'author' Field):
        # - Tag 'author:lisa-yuzkiv' (gängiges Pattern für Shopify-Author-Apps)
        # - Tag 'magvis' (zur Identifikation aller Magvis-Posts)
        article_tags = [self.project.topic, 'author:lisa-yuzkiv', 'magvis']
        # Shopify-SEO-Felder als globale Metafields. Ohne diese baut Shopify die
        # Meta-Description automatisch aus dem body_html-Anfang (= aktuell der TOC,
        # was CTR in den SERPs zerstört).
        seo_desc = (blog.seo_description or '')[:320]
        seo_title = (blog.seo_title or self.project.topic or '')[:70]
        article_payload = {
            'article': {
                'title': blog.seo_title,
                'author': 'Lisa Yuzkiv',
                'body_html': blog.final_html,
                'tags': ', '.join(article_tags),
                'published': True,
                # published_at NUR beim ERSTEN Publish setzen — bei späteren PUTs
                # (Re-Run der Stage) den ursprünglichen Wert behalten, damit Shopify
                # 'updated_at' korrekt setzt und Google 'dateModified' erkennt.
                # (siehe Schema-Section: dateModified wird separat gepflegt)
                **({} if blog.shopify_article_id else {'published_at': _now_isoformat()}),
                'metafields': [
                    {
                        'namespace': 'custom',
                        'key': 'blog_tool',
                        'value': 'minisolo-gravurvorschau',
                        'type': 'single_line_text_field',
                    },
                    {
                        'namespace': 'global',
                        'key': 'description_tag',
                        'value': seo_desc,
                        'type': 'single_line_text_field',
                    },
                    {
                        'namespace': 'global',
                        'key': 'title_tag',
                        'value': seo_title,
                        'type': 'single_line_text_field',
                    },
                ],
            }
        }
        if title_url:
            article_payload['article']['image'] = {
                'src': title_url,
                'alt': blog.seo_title or self.project.topic,
            }
        else:
            # Kein echtes Title-Image — Featured-Image explizit entfernen,
            # damit bei PUT-Update kein altes Hero-Fallback (z.B. Brainstorm)
            # haengen bleibt.
            article_payload['article']['image'] = None
        headers = {
            'X-Shopify-Access-Token': store.access_token,
            'Content-Type': 'application/json',
        }

        # PUT wenn Article schon existiert, sonst POST
        if blog.shopify_article_id:
            url = (f'https://{store.shop_domain}/admin/api/2023-10/blogs/'
                   f'{target_blog_id}/articles/{blog.shopify_article_id}.json')
            method = 'PUT'
        else:
            url = f'https://{store.shop_domain}/admin/api/2023-10/blogs/{target_blog_id}/articles.json'
            method = 'POST'

        try:
            resp = requests.request(method, url, headers=headers, json=article_payload, timeout=60)
            resp.raise_for_status()
            data = resp.json().get('article', {})
            blog.shopify_blog_id = str(target_blog_id)
            blog.shopify_article_id = str(data.get('id', blog.shopify_article_id))
            handle = data.get('handle', '')
            if handle:
                blog.shopify_published_url = (
                    f'https://{store.custom_domain or store.shop_domain}'
                    f'/blogs/{target_blog_handle}/{handle}'
                )
            blog.save(update_fields=['shopify_blog_id', 'shopify_article_id', 'shopify_published_url'])
            logger.info(f'Shopify Article {method} OK: {blog.shopify_published_url}')
        except Exception as exc:
            logger.warning(f'Shopify Article-{method}: {exc}')


def _fallback_facts(topic: str) -> list:
    return [
        {'icon': '🌱', 'title': 'Lebenslang sichtbar',
         'text': 'Ein gravierter Topf bleibt jahrelang im Alltag — anders als Konsumgeschenke.'},
        {'icon': '🎁', 'title': 'Persönlich', 'text': 'Personalisierte Geschenke wirken nachweislich wertvoller als Standardprodukte.'},
        {'icon': '🌍', 'title': 'Made in Germany', 'text': 'Die Töpfe stammen aus deutscher Manufaktur und werden hier graviert.'},
        {'icon': '💚', 'title': 'Nachhaltig', 'text': 'Keramik ist langlebig, recycelbar und voellig kunststofffrei.'},
    ]


def _fallback_tips(topic: str) -> list:
    return [
        {'icon': '✏️', 'title': 'Kurz halten',
         'text': 'Wähle einen kurzen Spruch (max. 25 Zeichen) — er bleibt besser lesbar.'},
        {'icon': '🌸', 'title': 'Pflanze beilegen',
         'text': 'Verschenke den Topf bepflanzt mit einer pflegeleichten Pflanze für den Wow-Effekt.'},
        {'icon': '🎀', 'title': 'Liebevoll verpacken',
         'text': 'Eine Schleife und Geschenkpapier in Erdtoenen unterstreichen die natuerliche Optik.'},
        {'icon': '📅', 'title': 'Zeit einplanen',
         'text': 'Bestelle 1 Woche vor dem Anlass — dann reicht die Zeit für Gravur und Versand.'},
    ]
