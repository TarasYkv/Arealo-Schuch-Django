"""Management Command: Berufs-Keywords aus Naturmacher-Liste in MagvisTopicQueue importieren.

Filtert bereits gepostete Topics raus (aus statischer batch_done.txt + Live-Abfrage
der Naturmacher-Shopify-Blog-Artikel + bestehende MagvisTopicQueue-Eintraege).

Usage:
    python manage.py magvis_import_topics --user=taras
    python manage.py magvis_import_topics --user=taras --priority=50 --dry-run
    python manage.py magvis_import_topics --user=taras --skip-shopify --keywords-file=/pfad/datei.txt
"""
from __future__ import annotations

import re

import requests
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


def _normalize(s: str) -> str:
    """Bringt Topic-Strings auf einen vergleichbaren Stand."""
    s = (s or '').lower().strip()
    s = (s.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss'))
    # alles non-alphanumerisch entfernen
    s = re.sub(r'[^a-z0-9]+', '', s)
    return s


def _read_keywords_file(path: str) -> list[str]:
    keywords = []
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                keywords.append(line)
    except FileNotFoundError:
        raise CommandError(f'Keywords-Datei nicht gefunden: {path}')
    return keywords


def _read_done_file(path: str) -> set[str]:
    """Liest batch_done.txt-Format: Zeilen wie '✅ geschenk lehrerin'."""
    done = set()
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip().lstrip('✅✓').strip()
                if line:
                    done.add(_normalize(line))
    except FileNotFoundError:
        pass
    return done


def _fetch_shopify_blog_titles(user) -> set[str]:
    """Holt Live-Artikeltitel aus dem Naturmacher-Shopify-Blog des Users."""
    titles = set()
    try:
        from ploom.models import PLoomSettings
        from shopify_manager.models import ShopifyBlog
    except ImportError:
        return titles
    ploom_s = PLoomSettings.objects.filter(user=user).first()
    if not ploom_s or not ploom_s.default_store:
        return titles
    store = ploom_s.default_store
    blogs = list(ShopifyBlog.objects.filter(store=store))
    for blog in blogs:
        url = (f'https://{store.shop_domain}/admin/api/2023-10/blogs/'
               f'{blog.shopify_id}/articles.json?limit=250&fields=title,handle')
        headers = {'X-Shopify-Access-Token': store.access_token}
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            for article in resp.json().get('articles', []):
                t = (article.get('title') or '').strip()
                h = (article.get('handle') or '').strip()
                if t:
                    titles.add(t)
                if h:
                    titles.add(h)
        except Exception:
            continue
    return titles


def _extract_topic_keywords_from_titles(titles: set[str]) -> set[str]:
    """Aus 'Geschenk Erzieherin: 12 schoene Ideen' wird 'geschenk erzieherin'."""
    out = set()
    for t in titles:
        # Zerlegen am ersten Satzzeichen
        m = re.split(r'[:–—\-,!?]', t, maxsplit=1)
        head = m[0].strip()
        out.add(_normalize(head))
        out.add(_normalize(t))  # Vollst. Vergleich auch zulassen
    return out


class Command(BaseCommand):
    help = 'Importiert Berufs-Keywords als MagvisTopicQueue-Eintraege, ' \
           'filtert bereits gepostete Topics raus.'

    DEFAULT_KEYWORDS = '/home/optimus/clawd/agents/naturmacher/keywords-berufe-final.txt'
    DEFAULT_DONE = '/home/optimus/clawd/agents/bloggy/batch_done.txt'

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True,
                            help='Username, dem die Topics zugeordnet werden')
        parser.add_argument('--keywords-file', default=self.DEFAULT_KEYWORDS,
                            help='Quelle der Keywords (eine pro Zeile)')
        parser.add_argument('--done-file', default=self.DEFAULT_DONE,
                            help='Statische Liste bereits geposteter Themen')
        parser.add_argument('--skip-shopify', action='store_true',
                            help='Naturmacher-Shopify-Blog NICHT abfragen')
        parser.add_argument('--priority', type=int, default=100,
                            help='Default-Priority fuer neue Topics')
        parser.add_argument('--dry-run', action='store_true',
                            help='Nur anzeigen, nichts speichern')

    def handle(self, *args, **opts):
        from magvis.models import MagvisTopicQueue

        try:
            user = User.objects.get(username=opts['user'])
        except User.DoesNotExist:
            raise CommandError(f'User "{opts["user"]}" nicht gefunden')

        # Keyword-Quelle
        keywords = _read_keywords_file(opts['keywords_file'])
        self.stdout.write(self.style.SUCCESS(
            f'{len(keywords)} Keywords geladen aus {opts["keywords_file"]}'
        ))

        # Bereits gepostet — Quellen sammeln
        done = _read_done_file(opts['done_file'])
        self.stdout.write(f'{len(done)} aus statischer batch_done.txt')

        if not opts['skip_shopify']:
            titles = _fetch_shopify_blog_titles(user)
            shop_topics = _extract_topic_keywords_from_titles(titles)
            done |= shop_topics
            self.stdout.write(
                f'{len(shop_topics)} aus Naturmacher-Shopify-Blog '
                f'(insgesamt {len(titles)} Artikel-Titel)'
            )

        # Bereits in MagvisTopicQueue
        existing = set(
            _normalize(t.topic) for t in MagvisTopicQueue.objects.filter(user=user)
        )
        done |= existing
        self.stdout.write(f'{len(existing)} bereits in MagvisTopicQueue')

        # Filter
        new_topics = []
        skipped = 0
        for kw in keywords:
            if _normalize(kw) in done:
                skipped += 1
                continue
            new_topics.append(kw)

        self.stdout.write(self.style.SUCCESS(
            f'\nNeu zu importieren: {len(new_topics)} Topics '
            f'(uebersprungen: {skipped})'
        ))

        if opts['dry_run']:
            self.stdout.write('\n--- DRY-RUN: erste 20 ---')
            for kw in new_topics[:20]:
                self.stdout.write(f'  + {kw}')
            if len(new_topics) > 20:
                self.stdout.write(f'  ... +{len(new_topics) - 20} weitere')
            return

        # Import
        objs = [
            MagvisTopicQueue(
                user=user, topic=kw,
                priority=opts['priority'],
                notes='Auto-Import aus keywords-berufe-final.txt',
            )
            for kw in new_topics
        ]
        MagvisTopicQueue.objects.bulk_create(objs, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ {len(new_topics)} Topics importiert in MagvisTopicQueue '
            f'fuer User {user.username}'
        ))
