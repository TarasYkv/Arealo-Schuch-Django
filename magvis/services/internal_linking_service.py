"""Magvis Internal-Linking-Service.

Findet thematisch passende Naturmacher-Blog-Artikel UND -Produkte
in der Workloom-Shopify-DB, schlaegt natuerliche Ankertexte vor und
liefert eine Liste, die GLM in den Blogtext eingebaut werden kann.

Erweiterung gegenueber blogprep: Linkt zusaetzlich Produkte
(blogprep linkt nur Artikel).
"""
from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    s = (s or '').lower()
    return re.sub(r'[^a-zäöüß0-9 ]+', ' ', s)


def _score(text: str, keywords: list[str]) -> float:
    t = _normalize(text)
    score = 0.0
    for kw in keywords:
        kw_n = _normalize(kw)
        if not kw_n:
            continue
        # Exact match
        if kw_n in t:
            score += 3.0
        # Wort-fuer-Wort + Substring-Match (faengt z.B. 'abitur' in 'abiturientin')
        for word in kw_n.split():
            if len(word) >= 4 and word in t:
                score += 0.5
            elif len(word) >= 5:
                # Stamm-Match: 'abiturientin' -> 'abitur' wuerde matchen
                stem = word[:5]
                if stem in t:
                    score += 0.25
    return score


class MagvisInternalLinkingService:
    def __init__(self, user, llm_client=None, max_blog_results: int = 5,
                 max_product_results: int = 4):
        self.user = user
        self.llm = llm_client
        self.max_blog_results = max_blog_results
        self.max_product_results = max_product_results

    # ---------- BLOG-ARTIKEL ----------

    def find_relevant_blog_posts(self, keyword: str,
                                  secondary: list[str] | None = None,
                                  exclude_shopify_id: str = '') -> list[dict]:
        from shopify_manager.models import ShopifyBlogPost

        keywords = [keyword] + (secondary or [])
        posts = (ShopifyBlogPost.objects
                 .filter(blog__store__user=self.user,
                         blog__store__is_active=True,
                         status='published',
                         published_at__isnull=False)
                 .exclude(shopify_id='').exclude(shopify_id__isnull=True)
                 .select_related('blog', 'blog__store'))
        if exclude_shopify_id:
            posts = posts.exclude(shopify_id=str(exclude_shopify_id))

        scored = []
        for post in posts:
            haystack = ' '.join([
                post.title or '',
                post.summary or '',
                self._text_preview(post.content, 600),
            ])
            s = _score(haystack, keywords)
            # Schwelle gesenkt: 1.5 → 0.6 (greift, wenn auch nur 2 Schluesselworte
            # je 0.5 Punkte matchen). Sortierung & Top-N bleiben — Spam gibt's nicht.
            if s >= 0.5:
                scored.append((s, post))

        # Sortierung: erst Score (hoch), dann published_at (neuesten zuerst)
        # → bei gleichem Score gewinnt der frischere Beitrag.
        from datetime import datetime, timezone as _tz
        scored.sort(key=lambda x: (
            x[0],
            (x[1].published_at or datetime(1970, 1, 1, tzinfo=_tz.utc)).timestamp(),
        ), reverse=True)
        out = []
        for s, post in scored[:self.max_blog_results]:
            try:
                url = post.get_storefront_url()
            except Exception:
                url = f'https://{post.blog.store.custom_domain or post.blog.store.shop_domain}/blogs/{post.blog.handle or "news"}/{post.handle}'
            out.append({
                'kind': 'blog',
                'title': post.title,
                'url': url,
                'score': round(s, 2),
                'summary': (post.summary or '')[:200],
                'anchors': self._suggest_anchors(post.title, keyword),
            })
        return out

    # ---------- PRODUKTE ----------

    def find_relevant_products(self, keyword: str,
                                secondary: list[str] | None = None) -> list[dict]:
        from shopify_manager.models import ShopifyProduct

        keywords = [keyword] + (secondary or [])
        # Nur AKTIVE/veroeffentlichte Produkte (kein 'draft' / 'archived')
        products = (ShopifyProduct.objects
                    .filter(store__user=self.user, store__is_active=True,
                            status='active')
                    .exclude(shopify_id='')
                    .exclude(handle=''))

        scored = []
        for prod in products:
            haystack = ' '.join([prod.title or '', prod.tags or '',
                                 self._text_preview(prod.body_html or '', 400)])
            s = _score(haystack, keywords)
            if s >= 1.5:
                scored.append((s, prod))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, prod in scored[:self.max_product_results]:
            try:
                url = prod.get_storefront_url()
            except Exception:
                url = f'https://{prod.store.custom_domain or prod.store.shop_domain}/products/{prod.handle}'
            out.append({
                'kind': 'product',
                'title': prod.title,
                'url': url,
                'score': round(s, 2),
                'summary': self._text_preview(prod.body_html or '', 200),
                'anchors': self._suggest_anchors(prod.title, keyword),
            })
        return out

    # ---------- COLLECTIONS ----------

    def find_relevant_collections(self, keyword: str,
                                   secondary: list[str] | None = None,
                                   exclude_handle: str = '') -> list[dict]:
        """Sucht thematisch passende ShopifyCollections (z.B. fuer Cross-Linking
        zwischen Beitraegen verschiedener Berufsgruppen)."""
        from shopify_manager.models import ShopifyCollection

        keywords = [keyword] + (secondary or [])
        colls = (ShopifyCollection.objects
                 .filter(store__user=self.user, store__is_active=True,
                         status='active', published=True)
                 .exclude(handle=''))
        if exclude_handle:
            colls = colls.exclude(handle=exclude_handle)

        scored = []
        for c in colls:
            haystack = ' '.join([c.title or '', c.seo_title or '',
                                 c.seo_description or '',
                                 self._text_preview(c.description or '', 400)])
            s = _score(haystack, keywords)
            if s >= 0.5:
                scored.append((s, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, c in scored[:3]:
            try:
                domain = (getattr(c.store, 'custom_domain', None)
                          or {'naturkind-de.myshopify.com': 'naturmacher.de'}.get(
                              c.store.shop_domain, c.store.shop_domain))
                url = f'https://{domain}/collections/{c.handle}'
            except Exception:
                url = ''
            if not url:
                continue
            out.append({
                'kind': 'collection',
                'title': c.title,
                'url': url,
                'score': round(s, 2),
                'summary': (c.seo_description or self._text_preview(c.description, 200))[:200],
                'anchors': self._suggest_anchors(c.title, keyword),
            })
        return out

    def collection_link_from_project(self, project_collection) -> dict | None:
        """Baut den Pflicht-Link auf die im selben Magvis-Projekt erstellte
        Collection. Liefert None wenn keine Collection vorhanden ist."""
        if not project_collection or not project_collection.shopify_handle:
            return None
        try:
            from ploom.models import PLoomSettings
            ps = PLoomSettings.objects.filter(user=self.user).first()
            if ps and ps.default_store:
                domain = (getattr(ps.default_store, 'custom_domain', None)
                          or {'naturkind-de.myshopify.com': 'naturmacher.de'}.get(
                              ps.default_store.shop_domain, ps.default_store.shop_domain))
            else:
                domain = 'naturmacher.de'
        except Exception:
            domain = 'naturmacher.de'
        url = f'https://{domain}/collections/{project_collection.shopify_handle}'
        title = project_collection.title or 'unsere Sammlung'
        return {
            'kind': 'collection',
            'title': title,
            'url': url,
            'score': 999.0,  # Pflicht
            'summary': (project_collection.short_description or '')[:200],
            'anchors': [title, f'Geschenke fuer {title.split()[-1] if title else ""}'.strip()],
            'is_required': True,
        }

    # ---------- KOMBINIERT ----------

    def collect(self, keyword: str, secondary: list[str] | None = None,
                 exclude_shopify_id: str = '',
                 project_collection=None) -> dict:
        """Liefert dict mit blogs + products + collections.

        project_collection: Die im selben Magvis-Projekt erstellte Collection
        (PFLICHT-Link an erste Stelle). Andere thematisch passende Collections
        werden danach angefuegt — fuer Cross-Linking zwischen Berufsgruppen."""
        result = {
            'blogs': self.find_relevant_blog_posts(keyword, secondary, exclude_shopify_id),
            'products': self.find_relevant_products(keyword, secondary),
            'collections': [],
        }
        # Pflicht-Collection vorne anstellen (falls vorhanden)
        required = self.collection_link_from_project(project_collection)
        if required:
            result['collections'].append(required)
            exclude_handle = project_collection.shopify_handle if project_collection else ''
        else:
            exclude_handle = ''
        # Andere thematisch passende Collections dazu (max 2 weitere)
        related = self.find_relevant_collections(keyword, secondary, exclude_handle)
        for c in related[:2]:
            result['collections'].append(c)
        return result

    def format_for_llm(self, links: dict) -> str:
        """Formatiert Links fuer LLM-Prompt-Injection."""
        parts = []
        if links.get('collections'):
            parts.append('VERWANDTE NATURMACHER-COLLECTIONS (zum Verlinken):')
            for c in links['collections']:
                anchor = (c['anchors'][0] if c['anchors'] else c['title'])[:60]
                marker = '  [PFLICHT-LINK] ' if c.get('is_required') else '  - '
                parts.append(f'{marker}"{anchor}" → {c["url"]}')
        if links.get('blogs'):
            parts.append('\nVERWANDTE NATURMACHER-BLOG-ARTIKEL (zum Verlinken):')
            for b in links['blogs']:
                anchor = (b['anchors'][0] if b['anchors'] else b['title'])[:60]
                parts.append(f'  - "{anchor}" → {b["url"]}')
        if links.get('products'):
            parts.append('\nVERWANDTE NATURMACHER-PRODUKTE (zum Verlinken):')
            for p in links['products']:
                anchor = (p['anchors'][0] if p['anchors'] else p['title'])[:60]
                parts.append(f'  - "{anchor}" → {p["url"]}')
        return '\n'.join(parts)

    # ---------- helpers ----------

    @staticmethod
    def _text_preview(html: str, max_len: int = 500) -> str:
        if not html:
            return ''
        try:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True)
        except Exception:
            text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text[:max_len]

    @staticmethod
    def _suggest_anchors(title: str, keyword: str) -> list[str]:
        """Schlaegt 1-2 natuerliche Ankertexte vor."""
        out = []
        # 1. Erstes Substantiv-Pair aus Title
        clean = re.sub(r'[:|–\-,]', ' ', title)
        words = [w for w in clean.split() if len(w) >= 3]
        if len(words) >= 2:
            out.append(' '.join(words[:3]))
        if title:
            out.append(title)
        return out[:2]
