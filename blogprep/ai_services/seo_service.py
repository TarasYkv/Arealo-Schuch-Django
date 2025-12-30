"""
SEO Analysis Service für BlogPrep

Verantwortlich für:
- Keyword-Density-Check
- Bild-SEO Analyse (Alt-Text mit Keyword)
- Outbound-Links Vorschläge
- Content-Gap-Analyse
- Duplicate Content Check
- Keyword-Kannibalisierung Warnung
- Update-Reminder für alte Artikel
"""

import logging
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SEOAnalysisService:
    """Service für SEO-Analyse von Blog-Content"""

    def __init__(self, user, settings=None):
        """
        Initialisiert den SEO Analysis Service.

        Args:
            user: Django User Objekt
            settings: Optional BlogPrepSettings Objekt
        """
        self.user = user
        self.settings = settings

        # Content Service für KI-Aufrufe (lazy loading)
        self._content_service = None

    @property
    def content_service(self):
        """Lazy loading des Content Service"""
        if self._content_service is None:
            from .content_service import ContentService
            self._content_service = ContentService(self.user, self.settings)
        return self._content_service

    def check_keyword_density(self, content: str, main_keyword: str, secondary_keywords: List[str] = None) -> Dict:
        """
        Prüft die Keyword-Dichte im Content.

        Zielwerte:
        - Hauptkeyword: 1-2% (optimal)
        - Unter 0.5%: zu niedrig
        - Über 3%: zu hoch (Keyword Stuffing)

        Args:
            content: HTML oder Text Content
            main_keyword: Das Hauptkeyword
            secondary_keywords: Liste der Sekundär-Keywords

        Returns:
            Dict mit Analyse-Ergebnissen und Score
        """
        try:
            # HTML entfernen
            text = BeautifulSoup(content, 'html.parser').get_text()
            text_lower = text.lower()

            # Wörter zählen
            words = re.findall(r'\b\w+\b', text_lower)
            total_words = len(words)

            if total_words == 0:
                return {
                    'score': 0,
                    'status': 'error',
                    'message': 'Kein Text vorhanden',
                    'total_words': 0
                }

            # Hauptkeyword analysieren
            main_kw_lower = main_keyword.lower()
            main_count = text_lower.count(main_kw_lower)

            # Wörter im Keyword zählen für Prozentberechnung
            main_kw_words = len(main_kw_lower.split())
            main_percentage = (main_count * main_kw_words / total_words) * 100 if total_words > 0 else 0

            # Status bestimmen
            if main_percentage < 0.5:
                main_status = 'zu_niedrig'
                main_score = max(30, 100 - (0.5 - main_percentage) * 100)
            elif main_percentage > 3:
                main_status = 'zu_hoch'
                main_score = max(30, 100 - (main_percentage - 3) * 20)
            else:
                main_status = 'optimal'
                # Je näher an 1.5%, desto besser
                deviation = abs(main_percentage - 1.5)
                main_score = 100 - (deviation * 15)

            # Sekundäre Keywords analysieren
            secondary_results = []
            if secondary_keywords:
                for kw in secondary_keywords[:5]:  # Max 5 analysieren
                    kw_lower = kw.lower().strip()
                    if not kw_lower:
                        continue
                    kw_count = text_lower.count(kw_lower)
                    kw_words = len(kw_lower.split())
                    kw_percentage = (kw_count * kw_words / total_words) * 100
                    secondary_results.append({
                        'keyword': kw,
                        'count': kw_count,
                        'percentage': round(kw_percentage, 2),
                        'status': 'vorhanden' if kw_count > 0 else 'fehlt'
                    })

            # Gesamt-Score berechnen
            secondary_score = 100
            if secondary_results:
                missing = sum(1 for s in secondary_results if s['status'] == 'fehlt')
                secondary_score = 100 - (missing / len(secondary_results)) * 40

            overall_score = int((main_score * 0.7) + (secondary_score * 0.3))

            # Empfehlungen generieren
            recommendations = []
            if main_status == 'zu_niedrig':
                recommendations.append(f"Verwende '{main_keyword}' häufiger im Text (aktuell: {main_count}x)")
            elif main_status == 'zu_hoch':
                recommendations.append(f"Reduziere die Verwendung von '{main_keyword}' (aktuell: {main_count}x)")

            for sec in secondary_results:
                if sec['status'] == 'fehlt':
                    recommendations.append(f"Integriere das Keyword '{sec['keyword']}' im Text")

            return {
                'score': overall_score,
                'status': main_status,
                'total_words': total_words,
                'main_keyword': {
                    'keyword': main_keyword,
                    'count': main_count,
                    'percentage': round(main_percentage, 2),
                    'status': main_status
                },
                'secondary_keywords': secondary_results,
                'recommendations': recommendations
            }

        except Exception as e:
            logger.error(f"Keyword density check error: {e}")
            return {
                'score': 0,
                'status': 'error',
                'message': str(e)
            }

    def check_image_seo(self, section_images: Dict, main_keyword: str) -> Dict:
        """
        Prüft Bilder auf SEO-Optimierung (Alt-Text mit Keyword).

        Args:
            section_images: Dict mit Abschnitts-Bildern
            main_keyword: Das Hauptkeyword

        Returns:
            Dict mit Bild-SEO-Analyse
        """
        try:
            images = []
            main_kw_lower = main_keyword.lower()

            if not section_images:
                return {
                    'score': 100,
                    'status': 'keine_bilder',
                    'message': 'Keine Bilder vorhanden',
                    'images': [],
                    'recommendations': []
                }

            total_images = 0
            with_keyword = 0
            without_alt = 0

            for section_key, image_data in section_images.items():
                if not image_data:
                    continue

                total_images += 1

                # Alt-Text prüfen
                alt_text = image_data.get('alt_text', '') or ''
                has_alt = bool(alt_text.strip())
                has_keyword = main_kw_lower in alt_text.lower() if has_alt else False

                if not has_alt:
                    without_alt += 1
                elif has_keyword:
                    with_keyword += 1

                images.append({
                    'section': section_key,
                    'has_alt': has_alt,
                    'has_keyword': has_keyword,
                    'current_alt': alt_text[:100] if alt_text else '',
                    'status': 'optimal' if has_keyword else ('kein_keyword' if has_alt else 'kein_alt')
                })

            if total_images == 0:
                return {
                    'score': 100,
                    'status': 'keine_bilder',
                    'message': 'Keine Bilder vorhanden',
                    'images': [],
                    'recommendations': []
                }

            # Score berechnen
            # 50% für Alt-Text vorhanden, 50% für Keyword im Alt-Text
            alt_score = ((total_images - without_alt) / total_images) * 50
            keyword_score = (with_keyword / total_images) * 50
            overall_score = int(alt_score + keyword_score)

            # Status bestimmen
            if without_alt > 0:
                status = 'fehlt_alt'
            elif with_keyword < total_images:
                status = 'fehlt_keyword'
            else:
                status = 'optimal'

            # Empfehlungen
            recommendations = []
            if without_alt > 0:
                recommendations.append(f"{without_alt} Bild(er) haben keinen Alt-Text")
            if with_keyword < total_images:
                missing = total_images - with_keyword
                recommendations.append(f"Bei {missing} Bild(ern) fehlt das Keyword im Alt-Text")

            for img in images:
                if img['status'] == 'kein_alt':
                    recommendations.append(f"Füge Alt-Text für '{img['section']}' hinzu mit Keyword '{main_keyword}'")
                elif img['status'] == 'kein_keyword':
                    recommendations.append(f"Integriere '{main_keyword}' in den Alt-Text von '{img['section']}'")

            return {
                'score': overall_score,
                'status': status,
                'total_images': total_images,
                'with_keyword': with_keyword,
                'without_alt': without_alt,
                'images': images,
                'recommendations': recommendations[:5]  # Max 5 Empfehlungen
            }

        except Exception as e:
            logger.error(f"Image SEO check error: {e}")
            return {
                'score': 0,
                'status': 'error',
                'message': str(e)
            }

    def suggest_outbound_links(self, content: str, main_keyword: str, research_data: Dict = None) -> Dict:
        """
        Schlägt relevante externe Links zu Autoritätsquellen vor.

        Args:
            content: Der Blog-Content
            main_keyword: Das Hauptkeyword
            research_data: Recherche-Daten (optional)

        Returns:
            Dict mit Link-Vorschlägen
        """
        try:
            # Aktuelle externe Links zählen
            soup = BeautifulSoup(content, 'html.parser')
            external_links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if href.startswith('http') and 'workloom.de' not in href and 'arealo' not in href.lower():
                    external_links.append(href)

            current_count = len(external_links)

            # KI-Vorschläge generieren
            system_prompt = """Du bist ein SEO-Experte für deutsche Blogs.
Analysiere den Content und schlage 3-5 externe Links zu Autoritätsquellen vor.

Fokussiere auf:
- Offizielle Statistiken (Statista, Bundesamt, etc.)
- Studien und Forschung
- Bekannte Marken/Experten im Themenbereich
- Wikipedia für Definitionen

Antworte NUR als valides JSON ohne Markdown-Formatierung."""

            user_prompt = f"""
Thema/Keyword: {main_keyword}

Content (Auszug):
{content[:2000]}

Schlage 3-5 externe Links vor als JSON:
{{
    "suggestions": [
        {{
            "topic": "Thema für den Link",
            "reason": "Warum dieser Link wertvoll ist",
            "search_query": "Suchbegriff um die Quelle zu finden",
            "anchor_text": "Vorgeschlagener Ankertext"
        }}
    ]
}}"""

            result = self.content_service._call_llm(system_prompt, user_prompt, max_tokens=800)

            suggestions = []
            if result.get('success'):
                parsed = self.content_service._parse_json_response(result['content'])
                if parsed and 'suggestions' in parsed:
                    suggestions = parsed['suggestions']

            # Score berechnen (Ziel: 3-5 externe Links)
            if current_count >= 5:
                score = 100
            elif current_count >= 3:
                score = 85
            elif current_count >= 1:
                score = 60
            else:
                score = 40

            recommendations = []
            if current_count < 3:
                recommendations.append(f"Füge {3 - current_count} externe Links zu Autoritätsquellen hinzu")

            return {
                'score': score,
                'status': 'optimal' if current_count >= 3 else 'verbesserbar',
                'current_count': current_count,
                'current_links': external_links[:5],
                'suggestions': suggestions,
                'recommendations': recommendations
            }

        except Exception as e:
            logger.error(f"Outbound links check error: {e}")
            return {
                'score': 50,
                'status': 'error',
                'message': str(e),
                'current_count': 0,
                'suggestions': []
            }

    def analyze_content_gaps(self, content: str, main_keyword: str, research_data: Dict = None) -> Dict:
        """
        Analysiert ob wichtige Themen im Content fehlen.

        Args:
            content: Der Blog-Content
            main_keyword: Das Hauptkeyword
            research_data: Recherche-Daten mit Konkurrenzanalyse

        Returns:
            Dict mit Content-Gap-Analyse
        """
        try:
            # Bereits vorhandene Gaps aus Research nutzen
            existing_gaps = []
            if research_data and 'content_gaps' in research_data:
                existing_gaps = research_data.get('content_gaps', [])

            # KI-Analyse für zusätzliche Gaps
            system_prompt = """Du bist ein SEO Content-Stratege.
Analysiere den Content und identifiziere fehlende Themen, die typischerweise zu diesem Keyword behandelt werden.

Antworte NUR als valides JSON ohne Markdown-Formatierung."""

            user_prompt = f"""
Keyword: {main_keyword}

Content:
{content[:3000]}

Bereits bekannte Content-Gaps aus Konkurrenzanalyse:
{json.dumps(existing_gaps[:5], ensure_ascii=False) if existing_gaps else 'Keine'}

Analysiere und antworte als JSON:
{{
    "missing_topics": [
        {{
            "topic": "Fehlendes Thema",
            "importance": "hoch/mittel/niedrig",
            "reason": "Warum dieses Thema wichtig ist"
        }}
    ],
    "unanswered_questions": [
        "Unbeantwortete Frage die Nutzer haben könnten"
    ],
    "competitor_advantage": "Was Konkurrenten besser machen (1 Satz)"
}}"""

            result = self.content_service._call_llm(system_prompt, user_prompt, max_tokens=800)

            missing_topics = []
            unanswered_questions = []
            competitor_info = ""

            if result.get('success'):
                parsed = self.content_service._parse_json_response(result['content'])
                if parsed:
                    missing_topics = parsed.get('missing_topics', [])
                    unanswered_questions = parsed.get('unanswered_questions', [])
                    competitor_info = parsed.get('competitor_advantage', '')

            # Score berechnen
            high_priority_missing = sum(1 for t in missing_topics if t.get('importance') == 'hoch')
            if high_priority_missing == 0 and len(missing_topics) <= 1:
                score = 95
            elif high_priority_missing == 0:
                score = 80
            elif high_priority_missing <= 2:
                score = 60
            else:
                score = 40

            recommendations = []
            for topic in missing_topics[:3]:
                if topic.get('importance') == 'hoch':
                    recommendations.append(f"Wichtig: Ergänze Abschnitt über '{topic.get('topic', '')}'")

            for question in unanswered_questions[:2]:
                recommendations.append(f"Beantworte: {question}")

            return {
                'score': score,
                'status': 'vollständig' if score >= 80 else 'lückenhaft',
                'missing_topics': missing_topics,
                'unanswered_questions': unanswered_questions,
                'competitor_advantage': competitor_info,
                'existing_gaps': existing_gaps[:5],
                'recommendations': recommendations[:5]
            }

        except Exception as e:
            logger.error(f"Content gaps analysis error: {e}")
            return {
                'score': 70,
                'status': 'error',
                'message': str(e)
            }

    def check_duplicate_content(self, content: str, project_id: str = None) -> Dict:
        """
        Prüft auf Duplicate Content gegen eigene veröffentlichte Artikel.

        Args:
            content: Der zu prüfende Content
            project_id: ID des aktuellen Projekts (zum Ausschließen)

        Returns:
            Dict mit Duplicate-Check-Ergebnissen
        """
        try:
            from shopify_manager.models import ShopifyBlogPost

            # Text extrahieren und normalisieren
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()
            text = ' '.join(text.split())[:2000]  # Normalisieren und begrenzen

            if len(text) < 100:
                return {
                    'score': 100,
                    'status': 'ok',
                    'message': 'Zu wenig Text für Vergleich',
                    'similar_articles': []
                }

            # Eigene veröffentlichte Artikel laden
            articles = ShopifyBlogPost.objects.filter(
                blog__store__user=self.user,
                status='published'
            ).exclude(
                content__isnull=True
            ).exclude(
                content=''
            )[:100]  # Limit für Performance

            similar_articles = []
            for article in articles:
                try:
                    article_soup = BeautifulSoup(article.content or '', 'html.parser')
                    article_text = article_soup.get_text()
                    article_text = ' '.join(article_text.split())[:2000]

                    if len(article_text) < 100:
                        continue

                    # Ähnlichkeit berechnen
                    ratio = SequenceMatcher(None, text, article_text).ratio()

                    if ratio > 0.25:  # 25% Ähnlichkeit
                        similar_articles.append({
                            'title': article.title,
                            'similarity': round(ratio * 100, 1),
                            'shopify_id': article.shopify_id,
                            'published_at': article.published_at.strftime('%d.%m.%Y') if article.published_at else 'Unbekannt'
                        })
                except Exception as e:
                    logger.warning(f"Error comparing article {article.id}: {e}")
                    continue

            # Sortieren nach Ähnlichkeit
            similar_articles.sort(key=lambda x: x['similarity'], reverse=True)
            similar_articles = similar_articles[:5]  # Top 5

            # Score berechnen
            if not similar_articles:
                score = 100
                status = 'einzigartig'
            else:
                max_similarity = similar_articles[0]['similarity']
                if max_similarity > 70:
                    score = 20
                    status = 'duplikat'
                elif max_similarity > 50:
                    score = 50
                    status = 'sehr_ähnlich'
                elif max_similarity > 35:
                    score = 75
                    status = 'ähnlich'
                else:
                    score = 90
                    status = 'leicht_ähnlich'

            recommendations = []
            if similar_articles and similar_articles[0]['similarity'] > 40:
                recommendations.append(f"Hohe Ähnlichkeit mit '{similar_articles[0]['title']}' ({similar_articles[0]['similarity']}%)")
                recommendations.append("Überarbeite den Content um ihn einzigartiger zu machen")

            return {
                'score': score,
                'status': status,
                'is_duplicate': score < 50,
                'similar_articles': similar_articles,
                'total_compared': len(articles),
                'recommendations': recommendations
            }

        except Exception as e:
            logger.error(f"Duplicate content check error: {e}")
            return {
                'score': 80,
                'status': 'error',
                'message': str(e),
                'similar_articles': []
            }

    def check_keyword_cannibalization(self, main_keyword: str, project_id: str = None) -> Dict:
        """
        Prüft auf Keyword-Kannibalisierung mit anderen Projekten.

        Args:
            main_keyword: Das Hauptkeyword
            project_id: ID des aktuellen Projekts (zum Ausschließen)

        Returns:
            Dict mit Kannibalisierungs-Analyse
        """
        try:
            from blogprep.models import BlogPrepProject

            main_kw_lower = main_keyword.lower().strip()

            # Andere Projekte mit ähnlichem Keyword finden
            projects = BlogPrepProject.objects.filter(
                user=self.user,
                main_keyword__isnull=False
            )

            if project_id:
                projects = projects.exclude(id=project_id)

            conflicts = []
            for project in projects:
                project_kw = (project.main_keyword or '').lower().strip()

                if not project_kw:
                    continue

                # Exakte Übereinstimmung
                if project_kw == main_kw_lower:
                    similarity = 100
                # Teilweise Übereinstimmung
                elif main_kw_lower in project_kw or project_kw in main_kw_lower:
                    similarity = 80
                # Wort-Übereinstimmung
                else:
                    main_words = set(main_kw_lower.split())
                    project_words = set(project_kw.split())
                    common_words = main_words & project_words
                    if len(common_words) >= 2:
                        similarity = 60
                    elif len(common_words) == 1 and len(main_words) <= 3:
                        similarity = 40
                    else:
                        similarity = 0

                if similarity >= 40:
                    conflicts.append({
                        'project_id': str(project.id),
                        'keyword': project.main_keyword,
                        'title': project.seo_title or project.main_keyword,
                        'similarity': similarity,
                        'created_at': project.created_at.strftime('%d.%m.%Y'),
                        'status': project.status
                    })

            # Sortieren nach Ähnlichkeit
            conflicts.sort(key=lambda x: x['similarity'], reverse=True)
            conflicts = conflicts[:5]

            # Score berechnen
            if not conflicts:
                score = 100
                severity = 'keine'
            else:
                max_similarity = conflicts[0]['similarity']
                if max_similarity == 100:
                    score = 30
                    severity = 'kritisch'
                elif max_similarity >= 80:
                    score = 50
                    severity = 'hoch'
                elif max_similarity >= 60:
                    score = 70
                    severity = 'mittel'
                else:
                    score = 85
                    severity = 'niedrig'

            recommendations = []
            if conflicts:
                if conflicts[0]['similarity'] == 100:
                    recommendations.append(f"Exaktes Keyword bereits verwendet in '{conflicts[0]['title']}'")
                    recommendations.append("Wähle ein spezifischeres Long-Tail-Keyword")
                elif conflicts[0]['similarity'] >= 80:
                    recommendations.append(f"Sehr ähnliches Keyword in '{conflicts[0]['title']}'")
                    recommendations.append("Differenziere die Keywords deutlicher")

            return {
                'score': score,
                'status': severity,
                'conflicts': conflicts,
                'total_projects_checked': projects.count(),
                'recommendations': recommendations
            }

        except Exception as e:
            logger.error(f"Keyword cannibalization check error: {e}")
            return {
                'score': 80,
                'status': 'error',
                'message': str(e),
                'conflicts': []
            }

    def check_update_reminders(self, main_keyword: str) -> Dict:
        """
        Findet alte Artikel zu ähnlichen Themen, die aktualisiert werden sollten.

        Args:
            main_keyword: Das Hauptkeyword

        Returns:
            Dict mit Update-Empfehlungen
        """
        try:
            from shopify_manager.models import ShopifyBlogPost

            # Artikel älter als 6 Monate mit ähnlichem Thema
            six_months_ago = datetime.now() - timedelta(days=180)

            articles = ShopifyBlogPost.objects.filter(
                blog__store__user=self.user,
                status='published',
                published_at__lt=six_months_ago
            ).order_by('-published_at')[:50]

            main_kw_lower = main_keyword.lower()
            main_words = set(main_kw_lower.split())

            outdated_articles = []
            for article in articles:
                title_lower = (article.title or '').lower()
                title_words = set(title_lower.split())

                # Thematische Übereinstimmung prüfen
                common_words = main_words & title_words
                relevance = len(common_words) / max(len(main_words), 1)

                # Auch im Content suchen
                if relevance < 0.3 and article.content:
                    content_lower = BeautifulSoup(article.content, 'html.parser').get_text().lower()
                    if main_kw_lower in content_lower:
                        relevance = 0.5

                if relevance >= 0.3:
                    age_days = (datetime.now() - article.published_at.replace(tzinfo=None)).days if article.published_at else 365

                    # Dringlichkeit bestimmen
                    if age_days > 365:
                        urgency = 'hoch'
                    elif age_days > 270:
                        urgency = 'mittel'
                    else:
                        urgency = 'niedrig'

                    outdated_articles.append({
                        'title': article.title,
                        'age_days': age_days,
                        'published_at': article.published_at.strftime('%d.%m.%Y') if article.published_at else 'Unbekannt',
                        'shopify_id': article.shopify_id,
                        'urgency': urgency,
                        'relevance': round(relevance * 100)
                    })

            # Sortieren nach Dringlichkeit und Alter
            outdated_articles.sort(key=lambda x: (-x['age_days'], -x['relevance']))
            outdated_articles = outdated_articles[:5]

            # Score berechnen
            if not outdated_articles:
                score = 100
            else:
                high_urgency = sum(1 for a in outdated_articles if a['urgency'] == 'hoch')
                if high_urgency >= 2:
                    score = 50
                elif high_urgency == 1:
                    score = 70
                else:
                    score = 85

            recommendations = []
            for article in outdated_articles[:3]:
                if article['urgency'] == 'hoch':
                    recommendations.append(f"Dringend aktualisieren: '{article['title']}' ({article['age_days']} Tage alt)")
                elif article['urgency'] == 'mittel':
                    recommendations.append(f"Aktualisierung empfohlen: '{article['title']}'")

            return {
                'score': score,
                'status': 'aktuell' if score >= 85 else 'aktualisierung_nötig',
                'outdated_articles': outdated_articles,
                'recommendations': recommendations
            }

        except Exception as e:
            logger.error(f"Update reminders check error: {e}")
            return {
                'score': 100,
                'status': 'error',
                'message': str(e),
                'outdated_articles': []
            }

    def run_full_analysis(self, project) -> Dict:
        """
        Führt alle SEO-Checks für ein Projekt durch.

        Args:
            project: BlogPrepProject Objekt

        Returns:
            Dict mit allen Analyse-Ergebnissen und Gesamt-Score
        """
        try:
            # Content zusammenbauen
            content_parts = []
            if project.intro_content:
                content_parts.append(project.intro_content)
            if project.main_content:
                content_parts.append(project.main_content)
            if project.tips_content:
                content_parts.append(project.tips_content)

            full_content = '\n\n'.join(content_parts)

            if not full_content:
                return {
                    'success': False,
                    'error': 'Kein Content vorhanden für SEO-Analyse'
                }

            # Alle Checks durchführen
            results = {}

            # 1. Keyword Density
            results['keyword_density'] = self.check_keyword_density(
                full_content,
                project.main_keyword,
                project.secondary_keywords or []
            )

            # 2. Bild-SEO
            results['image_seo'] = self.check_image_seo(
                project.section_images or {},
                project.main_keyword
            )

            # 3. Outbound Links
            results['outbound_links'] = self.suggest_outbound_links(
                full_content,
                project.main_keyword,
                project.research_data or {}
            )

            # 4. Content Gaps
            results['content_gaps'] = self.analyze_content_gaps(
                full_content,
                project.main_keyword,
                project.research_data or {}
            )

            # 5. Duplicate Check
            results['duplicate_check'] = self.check_duplicate_content(
                full_content,
                str(project.id)
            )

            # 6. Keyword Kannibalisierung
            results['cannibalization'] = self.check_keyword_cannibalization(
                project.main_keyword,
                str(project.id)
            )

            # 7. Update Reminders
            results['update_reminders'] = self.check_update_reminders(
                project.main_keyword
            )

            # Gesamt-Score berechnen (gewichtet)
            weights = {
                'keyword_density': 0.20,
                'image_seo': 0.10,
                'outbound_links': 0.10,
                'content_gaps': 0.20,
                'duplicate_check': 0.20,
                'cannibalization': 0.15,
                'update_reminders': 0.05
            }

            total_score = 0
            for key, weight in weights.items():
                if key in results and 'score' in results[key]:
                    total_score += results[key]['score'] * weight

            overall_score = int(total_score)

            # Alle Empfehlungen sammeln
            all_recommendations = []
            priority_order = ['duplicate_check', 'cannibalization', 'keyword_density', 'content_gaps', 'outbound_links', 'image_seo', 'update_reminders']
            for key in priority_order:
                if key in results and 'recommendations' in results[key]:
                    all_recommendations.extend(results[key]['recommendations'][:2])

            return {
                'success': True,
                'overall_score': overall_score,
                'results': results,
                'top_recommendations': all_recommendations[:7],
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Full SEO analysis error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
