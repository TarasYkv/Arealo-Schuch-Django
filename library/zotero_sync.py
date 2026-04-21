"""Zotero-API-Sync: holt Items aus zotero.org und schreibt sie in library.Reference."""
import urllib.request
import urllib.parse
import json
import re
from datetime import datetime
from django.utils import timezone

from .models import Reference, Collection, ZoteroAccount

BASE_URL = "https://api.zotero.org"


def _api_get(url: str, api_key: str):
    req = urllib.request.Request(url, headers={
        "Zotero-API-Key": api_key,
        "Zotero-API-Version": "3",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        total = r.headers.get("Total-Results")
        link = r.headers.get("Link", "")
    return json.loads(data), total, link


def _next_url(link_header: str):
    m = re.search(r'<([^>]+)>;\s*rel="next"', link_header or "")
    return m.group(1) if m else None


TYPE_MAP = {
    "journalArticle": "article",
    "book": "book",
    "bookSection": "misc",
    "conferencePaper": "inproceedings",
    "thesis": "thesis",
    "report": "report",
    "preprint": "report",
}


def zotero_item_to_defaults(item_data: dict, owner, collection):
    d = item_data
    authors = "; ".join(
        f"{a.get('lastName','')}, {a.get('firstName','')}".strip(", ")
        for a in d.get("creators", [])
        if a.get("creatorType") == "author" and (a.get("lastName") or a.get("firstName"))
    )

    date = d.get("date", "")
    year_match = re.search(r"\b(19|20)\d{2}\b", date)
    year = int(year_match.group(0)) if year_match else None

    return {
        "owner": owner,
        "collection": collection,
        "entry_type": TYPE_MAP.get(d.get("itemType"), "misc"),
        "title": (d.get("title") or "")[:500],
        "authors": authors[:500],
        "year": year,
        "journal": (d.get("publicationTitle") or d.get("bookTitle") or "")[:300],
        "publisher": (d.get("publisher") or "")[:300],
        "volume": (d.get("volume") or "")[:50],
        "issue": (d.get("issue") or "")[:50],
        "pages": (d.get("pages") or "")[:50],
        "doi": (d.get("DOI") or "").lower()[:200],
        "isbn": (d.get("ISBN") or "")[:50],
        "url": (d.get("url") or "")[:500],
        "abstract": (d.get("abstractNote") or "")[:2000],
        "tags": ", ".join(t.get("tag", "") for t in d.get("tags", []))[:500],
    }


def make_bibkey(item_data: dict, zotero_key: str) -> str:
    authors = item_data.get("creators", [])
    first = ""
    if authors:
        first = authors[0].get("lastName", "").lower()
        first = re.sub(r"[^a-z0-9]", "", first)
    date = item_data.get("date", "")
    m = re.search(r"\b(19|20)\d{2}\b", date)
    year = m.group(0) if m else "nd"
    title = item_data.get("title", "")
    words = re.findall(r"[A-Za-z]{4,}", title)
    slug = words[0].lower() if words else "ref"
    return (f"{first or 'ref'}{year}{slug}")[:60] or f"zot{zotero_key}"


def sync_account(account: ZoteroAccount, collection_name="Zotero-Sync") -> dict:
    """Synchronisiert eine Zotero-Bibliothek in Workloom-Library."""
    if account.library_type == "users":
        prefix = f"/users/{account.user_id}"
    else:
        prefix = f"/groups/{account.group_id or account.user_id}"

    coll, _ = Collection.objects.get_or_create(
        owner=account.owner, name=collection_name,
        defaults={"description": "Automatisch aus Zotero synchronisiert",
                  "color": "#cc2936"})

    url = f"{BASE_URL}{prefix}/items?format=json&limit=100&itemType=-attachment||note"
    created, updated, skipped = 0, 0, 0
    page = 0

    while url:
        page += 1
        items, _total, link = _api_get(url, account.api_key)
        for item in items:
            data = item.get("data", {})
            if data.get("itemType") in ("attachment", "note"):
                skipped += 1
                continue
            zotero_key = data.get("key", "")
            bibkey = make_bibkey(data, zotero_key)
            defaults = zotero_item_to_defaults(data, account.owner, coll)
            defaults["zotero_key"] = zotero_key
            defaults["last_synced"] = timezone.now()

            existing = Reference.objects.filter(
                owner=account.owner, zotero_key=zotero_key).first()
            if existing:
                for k, v in defaults.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
            else:
                defaults["bibtex_key"] = bibkey
                # Ggf. bestehender Eintrag mit gleichem bibkey → nutze zotero_key-Unterscheidung
                if Reference.objects.filter(
                        owner=account.owner, bibtex_key=bibkey).exists():
                    defaults["bibtex_key"] = f"{bibkey}_{zotero_key[:6]}"
                Reference.objects.create(**defaults)
                created += 1

        url = _next_url(link)

    account.last_sync = timezone.now()
    account.save(update_fields=["last_sync"])
    return {"created": created, "updated": updated, "skipped": skipped,
            "pages": page}
