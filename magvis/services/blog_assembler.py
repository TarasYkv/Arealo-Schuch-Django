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
        self._research_context = ''         # gefuellt vor Sektionen-Generierung
        self._internal_links_text = ''
        self._internal_links_data: dict = {}
        self._search_intent: dict = {}       # informational/transactional + LSI-Keywords

    # ------------------------------------------------------------------ public

    def assemble(self) -> MagvisBlog:
        blog, _ = MagvisBlog.objects.get_or_create(project=self.project)

        topic = self.project.topic
        sections: list[dict] = []

        # 1. SEO-Titel + Meta-Description
        self.project.log_stage('blog', f'🎯 SEO + Mid-Volume-Keywords fuer "{topic}"')
        seo = self._generate_seo()
        blog.seo_title = seo.get('title', topic)[:255]
        blog.seo_description = seo.get('description', '')[:500]
        blog.slug = django_slugify(blog.seo_title)[:255]

        # 2. Headings (Struktur-Skelett)
        headings = self._generate_headings(topic)

        # 0a. RESEARCH + INTERNAL LINKS + INTENT (frueh — fuer Sektions-Prompts)
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
                    f'Schreibe in einem Satz die wichtigste Aussage fuer einen '
                    f'Naturmacher-Blog zum Thema "{topic}". Max. 25 Woerter, '
                    f'antworte nur mit dem Satz, ohne Anfuehrungszeichen.',
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

        # 3a. STATISTIK-BOX (nach TL;DR, vor Fakten — verifizierte Quellen)
        self.project.log_stage('blog', '📊 Statistiken aus Whitelist-Quellen extrahieren')
        verified_stats = self._extract_verified_statistics(topic)
        if verified_stats:
            self.project.log_stage('blog', f'✓ {len(verified_stats)} Statistiken verifiziert')
            sections.append({
                'type': 'statistics_box', 'id': 'stats',
                'html': self._statistics_box_html(verified_stats),
            })

        # 3b. FAKTEN-BOX (nach Intro, vor TOC)
        self.project.log_stage('blog', '📚 Fakten-Box (4 Wusstest-du-schon)')
        facts = self.glm.json_chat_with_retry(
            facts_prompt(topic, num_facts=4), expect='array',
            max_tokens=1500, retries=3,
        ) or _fallback_facts(topic)
        sections.append({
            'type': 'facts_box', 'id': 'facts',
            'html': self._facts_box_html(facts),
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
        self.project.log_stage('blog', f'✍️ Sektion 2/6: {(headings[1] if len(headings) > 1 else "")[:50]}')
        head2 = headings[1] if len(headings) > 1 else 'Hintergrund'
        slug2 = slugify(head2)
        para2 = self._call_glm(section_prompt(topic, head2))
        sections.append({'type': 'h2', 'id': slug2, 'title': head2})
        sections.append({'type': 'paragraph', 'id': f'{slug2}-p', 'html': para2})

        # 8. Diagramm (Gemini) — wird bei Bedarf zum Title-Bild-Fallback
        self.project.log_stage('blog', '🎨 Diagramm-Bild via Gemini + Shopify-CDN-Upload')
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
        self.project.log_stage('blog', f'✍️ Sektion 3/6: {(headings[2] if len(headings) > 2 else "")[:50]}')
        head3 = headings[2] if len(headings) > 2 else 'Was du beachten solltest'
        slug3 = slugify(head3)
        para3 = self._call_glm(section_prompt(topic, head3))
        sections.append({'type': 'h2', 'id': slug3, 'title': head3})
        sections.append({'type': 'paragraph', 'id': f'{slug3}-p', 'html': para3})

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
        self.project.log_stage('blog', '🌿 Brainstorming-Bild via Gemini + Shopify-CDN-Upload')
        brainstorm_url = self._generate_blog_image(kind='brainstorm', topic_summary='')
        if brainstorm_url:
            blog.brainstorm_image_path = brainstorm_url
            sections.append({
                'type': 'image', 'id': 'brainstorm', 'src': brainstorm_url,
                'alt': f'Brainstorming: {topic}',
                'html': self._image_html(brainstorm_url, f'Brainstorming zum Thema {topic}'),
            })

        # 13b. Fallback fuer Hero-Titelbild: wenn keins generiert wurde,
        # nutze brainstorm_url (oder diagram_url) als Hero ganz oben
        has_hero = any(s.get('type') == 'title_image' for s in sections)
        if not has_hero:
            fallback = brainstorm_url or diagram_url
            if fallback:
                hero_section = {
                    'type': 'title_image', 'id': 'hero', 'src': fallback,
                    'html': self._title_image_html(fallback, blog.seo_title or topic),
                }
                # An Position 0 einsetzen (vor TL;DR)
                sections.insert(0, hero_section)
                self.project.log_stage('blog', '✓ Hero-Bild aus Brainstorm/Diagramm-Fallback übernommen')

        # 14. Sektion 5
        self.project.log_stage('blog', f'✍️ Sektion 5/6: {(headings[4] if len(headings) > 4 else "")[:50]}')
        head5 = headings[4] if len(headings) > 4 else 'Ein wenig zum Spielen'
        slug5 = slugify(head5)
        para5 = self._call_glm(section_prompt(topic, head5))
        sections.append({'type': 'h2', 'id': slug5, 'title': head5})
        sections.append({'type': 'paragraph', 'id': f'{slug5}-p', 'html': para5})

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
        sections.append({'type': 'h2', 'id': slug6, 'title': head6})
        sections.append({'type': 'paragraph', 'id': f'{slug6}-p', 'html': para6})

        # 17. PRODUKT-EMBED #2 (letztes Drittel)
        if self.project.product_2:
            product_card_2 = self._product_card_html(self.project.product_2)
            sections.append({
                'type': 'product', 'id': 'product-2',
                'product_id': str(self.project.product_2.id), 'html': product_card_2,
            })

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
        if self._internal_links_text:
            system += (
                '\n\n' + self._internal_links_text + '\n'
                'WICHTIG: Wenn ein Anker thematisch passt, baue ihn als HTML-Link '
                '<a href="URL">Ankertext</a> NATUERLICH in den Text ein. Erzwinge '
                'KEINE Links — pro Absatz max 1 Link, im ganzen Beitrag max 5.'
            )
        try:
            return self.glm.text(prompt, system=system, temperature=0.75).strip()
        except Exception as exc:
            logger.warning('GLM-Call fehlgeschlagen: %s', exc)
            return f'<p><em>(Hinweis: Sektion konnte nicht generiert werden.)</em></p>'

    def _extract_verified_statistics(self, topic: str) -> list[dict]:
        """Holt 1-3 verifizierte Statistiken aus Whitelist-Quellen.

        Pipeline:
        1. Stat-fokussierte Web-Suche (research_service.search_statistics)
        2. GLM extrahiert mit quote_excerpt-Pflichtfeld
        3. Live-Verifikation gegen Quell-URL
        4. Filtert auf Whitelist-Domains
        """
        try:
            stat_results = self.research.search_statistics(topic, num_results=6)
        except Exception as exc:
            logger.warning('Stat-Search fehlgeschlagen: %s', exc)
            return []
        if not stat_results:
            return []
        research_text = self.research.format_for_llm(stat_results)

        try:
            extracted = self.glm.json_chat_with_retry(
                statistics_extraction_prompt(topic, research_text),
                expect='array', max_tokens=2000, retries=2,
            ) or []
        except Exception as exc:
            logger.warning('Stat-Extraktion via GLM fehlgeschlagen: %s', exc)
            return []
        if not isinstance(extracted, list):
            return []

        # Verifikation
        verified = []
        for stat in extracted[:5]:
            if not isinstance(stat, dict):
                continue
            try:
                if self.research.verify_statistic(stat):
                    verified.append(stat)
                    logger.info('✓ Stat verifiziert: %s = %s',
                                stat.get('label', '?'), stat.get('value', '?'))
                else:
                    logger.info('✗ Stat verworfen (nicht verifizierbar): %s',
                                stat.get('label', '?'))
            except Exception as exc:
                logger.warning('Stat-Verifikation Fehler: %s', exc)
        # Mind. 1 Stat — Box wird auch bei nur einer angezeigt (besser als nix)
        if not verified:
            logger.info('0 verifizierte Stats — Stat-Box wird ausgelassen')
            return []
        logger.info('%d Stats verifiziert — Box wird gerendert', len(verified))
        return verified[:3]

    def _statistics_box_html(self, stats: list[dict]) -> str:
        """Sichtbare 'Belastbare Zahlen'-Box mit Quell-Links."""
        if not stats:
            return ''
        items = ''
        for s in stats:
            value = escape(str(s.get('value', '')))
            label = escape(str(s.get('label', '')))
            url = escape(str(s.get('source_url', '')))
            source = escape(str(s.get('source_name', 'Quelle')))
            if not value or not url:
                continue
            items += (
                '<div style="padding:12px 0;border-bottom:1px solid rgba(125,156,128,0.2);'
                'display:flex;gap:14px;align-items:flex-start;">'
                f'<div style="font-size:1.4rem;font-weight:700;color:#3D5A40;'
                f'min-width:90px;letter-spacing:-0.02em;">{value}</div>'
                '<div style="flex:1;">'
                f'<div style="color:#2A2A2A;font-size:0.95rem;line-height:1.4;'
                f'margin-bottom:4px;">{label}</div>'
                f'<a href="{url}" target="_blank" rel="noopener" '
                f'style="font-size:0.82rem;color:#7D9C80;text-decoration:none;'
                f'border-bottom:1px dotted #7D9C80;">→ {source} ↗</a>'
                '</div></div>'
            )
        return (
            '<aside class="naturmacher-statistics" '
            'style="margin:36px auto;max-width:680px;background:#fff;'
            'border:1px solid rgba(125,156,128,0.3);border-left:4px solid #7D9C80;'
            'border-radius:12px;padding:18px 24px 8px;'
            'box-shadow:0 2px 14px rgba(0,0,0,0.04);">'
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
            '<span style="font-size:1.2rem;">📊</span>'
            '<strong style="color:#3D5A40;font-size:0.92rem;letter-spacing:0.04em;'
            'text-transform:uppercase;">Belastbare Zahlen zum Thema</strong>'
            '</div>'
            '<div style="font-size:0.78rem;color:#7A7264;margin-bottom:8px;">'
            'Geprüfte Quellen, die wir bei unserer Recherche verwendet haben:</div>'
            f'<div>{items}</div>'
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
        """Web-Research + interne Links — fuellt self._research_context und _internal_links_text."""
        # Research (best effort, fail silent)
        try:
            search_q = f'{topic} Geschenk Idee'
            results = self.research.search(search_q, num_results=4)
            if results:
                self._research_context = self.research.format_for_llm(results)
                logger.info('Research: %d Quellen geladen', len(results))
        except Exception as exc:
            logger.warning('Research fehlgeschlagen: %s', exc)

        # Internal Links (Blogs + Produkte)
        try:
            secondary = self.project.keywords or []
            self._internal_links_data = self.linking.collect(topic, secondary)
            self._internal_links_text = self.linking.format_for_llm(self._internal_links_data)
            n_blogs = len(self._internal_links_data.get('blogs', []))
            n_prods = len(self._internal_links_data.get('products', []))
            logger.info('Internal-Linking: %d Blogs + %d Produkte gefunden', n_blogs, n_prods)
        except Exception as exc:
            logger.warning('Internal-Linking fehlgeschlagen: %s', exc)

    def _generate_seo(self) -> dict:
        try:
            data = self.glm.json_chat(seo_prompt(self.project.topic))
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

        # Bild zu Shopify-Files hochladen (CDN-URL fuer den Blog-Embed)
        cdn_url = self._upload_to_shopify_files(
            result.get('abs_path', ''),
            f'magvis_{kind}_{self.project.id}',
            alt_text=f'{kind} - {self.project.topic}',
        )
        return cdn_url or result.get('rel_path', '') or result.get('url', '')

    def _upload_to_shopify_files(self, abs_path: str, filename: str, alt_text: str = '') -> str:
        """Laedt ein Bild zu Shopify-Files hoch und liefert FINALE CDN-URL.

        Polling fuer cdn.shopify.com URL: blogprep.shopify_files liefert
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
        logger.warning('CDN-URL nach %d Polls nicht bereit fuer %s', max_attempts, file_id)
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

    def _tldr_box_html(self, data: dict) -> str:
        """TL;DR-Box am Anfang des Blogs — fuer Featured Snippets + LLMs."""
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
            f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;">{items}</div>'
            '</aside>'
        )

    def _tips_box_html(self, tips: list) -> str:
        """Tipps-Box (kompakt, Grid 2x2)."""
        if not tips:
            return ''
        items = ''
        for t in tips:
            if not isinstance(t, dict):
                continue
            icon = escape(str(t.get('icon', '💡')))
            title = escape(str(t.get('title', '')))
            text = escape(str(t.get('text', '')))
            if not text:
                continue
            items += (
                '<div style="display:flex;gap:8px;align-items:flex-start;padding:8px 10px;'
                'background:rgba(255,255,255,0.5);border-radius:6px;">'
                f'<span style="font-size:1.05rem;line-height:1.2;flex-shrink:0;">{icon}</span>'
                '<div style="font-size:0.85rem;line-height:1.4;">'
                f'<strong style="color:#8A6F1F;">{title}:</strong> '
                f'<span style="color:#5C5651;">{text}</span>'
                '</div></div>'
            )
        return (
            '<aside class="naturmacher-tips-box" '
            'style="margin:24px auto;max-width:680px;'
            'background:linear-gradient(135deg,#FBF6E5 0%,#F5EDD0 100%);'
            'border-left:3px solid #D4AB32;border-radius:8px;padding:14px 16px;'
            'font-family:inherit;">'
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
            '<span style="font-size:1.05rem;">✨</span>'
            '<strong style="color:#8A6F1F;font-size:0.95rem;letter-spacing:0.02em;text-transform:uppercase;">Tipps & Tricks</strong>'
            '</div>'
            f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;">{items}</div>'
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
        # Reihenfolge: title_image (ganz oben) → TOC → restliche Sektionen.
        # H2 in Naturmacher-Salbeigruen, elegant unterstrichen.
        parts: list[str] = []
        title_html = ''
        for sec in blog.sections:
            if sec.get('type') == 'title_image':
                title_html = sec.get('html', '')
                break
        if title_html:
            parts.append(title_html)
        if blog.toc_html:
            parts.append(blog.toc_html)
        for sec in blog.sections:
            t = sec.get('type')
            if t == 'title_image':
                continue  # bereits oben
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

        article_payload = {
            'article': {
                'title': blog.seo_title,
                'author': 'Naturmacher',
                'body_html': blog.final_html,
                'tags': self.project.topic,
                'published': True,
                'metafields': [
                    {
                        'namespace': 'custom',
                        'key': 'blog_tool',
                        'value': 'minisolo-gravurvorschau',
                        'type': 'single_line_text_field',
                    },
                ],
            }
        }
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
        {'icon': '🎁', 'title': 'Persoenlich', 'text': 'Personalisierte Geschenke wirken nachweislich wertvoller als Standardprodukte.'},
        {'icon': '🌍', 'title': 'Made in Germany', 'text': 'Die Toepfe stammen aus deutscher Manufaktur und werden hier graviert.'},
        {'icon': '💚', 'title': 'Nachhaltig', 'text': 'Keramik ist langlebig, recycelbar und voellig kunststofffrei.'},
    ]


def _fallback_tips(topic: str) -> list:
    return [
        {'icon': '✏️', 'title': 'Kurz halten',
         'text': 'Waehle einen kurzen Spruch (max. 25 Zeichen) — er bleibt besser lesbar.'},
        {'icon': '🌸', 'title': 'Pflanze beilegen',
         'text': 'Verschenke den Topf bepflanzt mit einer pflegeleichten Pflanze fuer den Wow-Effekt.'},
        {'icon': '🎀', 'title': 'Liebevoll verpacken',
         'text': 'Eine Schleife und Geschenkpapier in Erdtoenen unterstreichen die natuerliche Optik.'},
        {'icon': '📅', 'title': 'Zeit einplanen',
         'text': 'Bestelle 1 Woche vor dem Anlass — dann reicht die Zeit fuer Gravur und Versand.'},
    ]
