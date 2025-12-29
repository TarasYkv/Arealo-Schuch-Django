"""
Internal Linking Service für BlogPrep

Verantwortlich für:
- Laden aller veröffentlichten Blog-Artikel des Users
- Vorfilterung nach Keywords (Performance)
- KI-basierte Relevanzanalyse
- Generierung von Ankertext-Vorschlägen
"""

import logging
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from .content_service import ContentService

logger = logging.getLogger(__name__)


class InternalLinkingService:
    """Service für interne Verlinkung"""

    def __init__(self, user, settings=None):
        """
        Args:
            user: Django User Objekt
            settings: BlogPrepSettings (optional, für KI-Modell)
        """
        self.user = user
        self.settings = settings
        self.content_service = ContentService(user, settings)

    def get_user_blog_posts(self, exclude_draft: bool = True) -> List[Dict]:
        """
        Lädt alle veröffentlichten Blog-Artikel des Users aus allen Stores.

        Returns:
            Liste von Artikel-Dicts mit id, title, url, summary, content_preview
        """
        from shopify_manager.models import ShopifyBlogPost

        filters = {
            'blog__store__user': self.user,
            'blog__store__is_active': True,
        }

        if exclude_draft:
            filters['status'] = 'published'
            filters['published_at__isnull'] = False  # Muss veröffentlicht worden sein

        posts = ShopifyBlogPost.objects.filter(
            **filters
        ).exclude(
            shopify_id=''  # Nur Artikel die tatsächlich in Shopify existieren
        ).exclude(
            shopify_id__isnull=True
        ).select_related('blog', 'blog__store')

        return [
            {
                'id': post.id,
                'title': post.title,
                'url': post.get_storefront_url(),
                'summary': post.summary or '',
                'content_preview': self._extract_text_preview(post.content, 500),
                'store_name': post.blog.store.name,
                'blog_title': post.blog.title,
            }
            for post in posts
        ]

    def _extract_text_preview(self, html_content: str, max_length: int = 500) -> str:
        """Extrahiert Text aus HTML für Vorschau"""
        if not html_content:
            return ''

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)

            if len(text) > max_length:
                return text[:max_length] + '...'
            return text
        except Exception as e:
            logger.warning(f"Fehler beim Extrahieren von Text aus HTML: {e}")
            return ''

    def prefilter_articles(self, articles: List[Dict], keyword: str,
                          secondary_keywords: List[str] = None) -> List[Dict]:
        """
        Schnelle Vorfilterung nach Keywords (ohne KI).
        Reduziert die Anzahl der Artikel für die KI-Analyse.

        Args:
            articles: Liste aller Artikel
            keyword: Hauptkeyword
            secondary_keywords: Optionale sekundäre Keywords

        Returns:
            Gefilterte Liste (max. 20 Artikel)
        """
        keywords = [keyword.lower()]
        if secondary_keywords:
            keywords.extend([k.lower() for k in secondary_keywords])

        # Thematisch verwandte Wörter aus dem Keyword extrahieren
        keyword_parts = keyword.lower().split()

        scored_articles = []
        for article in articles:
            score = 0
            searchable = (
                article['title'].lower() + ' ' +
                article['summary'].lower() + ' ' +
                article['content_preview'].lower()
            )

            # Keyword-Matching
            for kw in keywords:
                if kw in searchable:
                    # Hauptkeyword gibt mehr Punkte
                    score += 3 if kw == keyword.lower() else 1

                # Teilwort-Matching (z.B. "Matratze" in "Matratzenratgeber")
                for part in kw.split():
                    if len(part) >= 4 and part in searchable:
                        score += 0.5

            # Keyword-Teile matchen
            for part in keyword_parts:
                if len(part) >= 4 and part in searchable:
                    score += 1

            if score > 0:
                scored_articles.append((score, article))

        # Sortiere nach Score, nimm max. 20
        scored_articles.sort(key=lambda x: x[0], reverse=True)
        return [article for _, article in scored_articles[:20]]

    def analyze_relevance(self, keyword: str, articles: List[Dict]) -> Dict:
        """
        KI-basierte Relevanzanalyse der vorgefilterten Artikel.

        Args:
            keyword: Hauptkeyword des neuen Blogs
            articles: Vorgefilterte Artikel-Liste

        Returns:
            Dict mit relevanten Artikeln und Scores
        """
        if not articles:
            return {
                'success': True,
                'relevant_articles': [],
                'analyzed_count': 0
            }

        # Formatiere Artikel für Prompt
        articles_text = "\n".join([
            f"[ID:{a['id']}] {a['title']}\n"
            f"   Zusammenfassung: {a['summary'][:200] if a['summary'] else 'Keine'}\n"
            f"   Inhalt: {a['content_preview'][:300]}\n"
            for a in articles
        ])

        system_prompt = """Du bist ein SEO-Experte für interne Verlinkung.
Analysiere die bestehenden Blog-Artikel und bewerte ihre Relevanz für einen neuen Blog zum angegebenen Keyword.
Nur Artikel verlinken die WIRKLICH thematisch passen - keine erzwungenen Links!"""

        user_prompt = f"""Neuer Blog zum Keyword: "{keyword}"

BESTEHENDE ARTIKEL ZUM ANALYSIEREN:
{articles_text}

AUFGABE:
1. Bewerte die Relevanz jedes Artikels (0.0 = irrelevant, 1.0 = sehr relevant)
2. Nur Artikel mit Relevanz >= 0.6 aufnehmen
3. Schlage 2-3 natürliche Ankertexte vor (kurz, beschreibend, KEIN "hier klicken")

Erstelle als JSON:
{{
    "relevant_articles": [
        {{
            "id": 123,
            "relevance_score": 0.85,
            "relevance_reason": "Kurze Begründung warum relevant",
            "suggested_anchor_texts": ["Ankertext 1", "Ankertext 2"]
        }}
    ]
}}

Antworte NUR mit dem JSON-Objekt. Wenn KEIN Artikel relevant ist, gib ein leeres Array zurück."""

        result = self.content_service._call_llm(
            system_prompt, user_prompt,
            max_tokens=2000, temperature=0.3
        )

        if not result['success']:
            return result

        parsed = self.content_service._parse_json_response(result['content'])
        if not parsed:
            logger.warning(f"Konnte Relevanz-Analyse nicht parsen: {result['content'][:500]}")
            return {
                'success': False,
                'error': 'Konnte Relevanz-Analyse nicht parsen'
            }

        # Merge KI-Ergebnisse mit Artikel-Daten
        relevant_articles = []
        for ai_article in parsed.get('relevant_articles', []):
            article_id = ai_article.get('id')
            original = next((a for a in articles if a['id'] == article_id), None)

            if original and ai_article.get('relevance_score', 0) >= 0.6:
                relevant_articles.append({
                    **original,
                    'relevance_score': ai_article.get('relevance_score'),
                    'relevance_reason': ai_article.get('relevance_reason', ''),
                    'suggested_anchor_texts': ai_article.get('suggested_anchor_texts', [])
                })

        # Sortiere nach Relevanz
        relevant_articles.sort(key=lambda x: x['relevance_score'], reverse=True)

        return {
            'success': True,
            'relevant_articles': relevant_articles,
            'analyzed_count': len(articles),
            'tokens_input': result.get('tokens_input', 0),
            'tokens_output': result.get('tokens_output', 0),
            'duration': result.get('duration', 0)
        }

    def analyze_internal_articles(self, keyword: str,
                                  secondary_keywords: List[str] = None) -> Dict:
        """
        Hauptmethode: Lädt, filtert und analysiert interne Artikel.

        Args:
            keyword: Hauptkeyword
            secondary_keywords: Sekundäre Keywords

        Returns:
            Dict mit relevanten Artikeln für research_data
        """
        # 1. Alle Artikel laden
        all_articles = self.get_user_blog_posts()

        if not all_articles:
            return {
                'success': True,
                'internal_articles': [],
                'internal_articles_analyzed': 0,
                'internal_articles_relevant': 0,
                'message': 'Keine veröffentlichten Blog-Artikel gefunden'
            }

        # 2. Vorfiltern (Performance)
        filtered = self.prefilter_articles(all_articles, keyword, secondary_keywords)

        if not filtered:
            return {
                'success': True,
                'internal_articles': [],
                'internal_articles_analyzed': len(all_articles),
                'internal_articles_relevant': 0,
                'message': 'Keine thematisch passenden Artikel gefunden'
            }

        # 3. KI-Analyse
        result = self.analyze_relevance(keyword, filtered)

        if not result['success']:
            return result

        return {
            'success': True,
            'internal_articles': result['relevant_articles'],
            'internal_articles_analyzed': len(all_articles),
            'internal_articles_relevant': len(result['relevant_articles']),
            'tokens_input': result.get('tokens_input', 0),
            'tokens_output': result.get('tokens_output', 0),
            'duration': result.get('duration', 0)
        }
