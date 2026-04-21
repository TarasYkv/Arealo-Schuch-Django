"""Management command: Markiert Referenzen mit vermutlich falschen CrossRef-Matches."""
import re
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from library.models import Reference

User = get_user_model()

SUSPICIOUS_PATTERNS = [
    (r"^\s*introduction\s*$", "Nur 'Introduction'"),
    (r"^\s*references?\s*$", "Nur 'References'"),
    (r"^\s*no job name\s*$", "Word-Platzhalter"),
    (r"^[a-z0-9+/=]{20,}$", "Base64-artiger String"),
    (r"^\s*doi:", "Roher DOI als Titel"),
    (r"^[A-Z]{1,3}-\d+\s*$", "Nur Dokument-ID"),
    (r"^\s*\w+\s*\d+\.\.\d+\s*$", "Seitenbereich ohne Titel"),
    (r"^\s*\w+-\d+-\d+.*indd", "Indesign-Filename"),
    (r"microsoft word", "Word-Filename-Relikt"),
    (r"^Ostraka\b", "Antiker Text, vermutlich Fehlmatch"),
    (r"^SEG\b|Supplementum Epigraphicum", "Archäologischer Fehlmatch"),
]


class Command(BaseCommand):
    help = "Markiere verdächtige Referenzen (vermutlich falsch zugeordnete CrossRef-Matches)."

    def add_arguments(self, p):
        p.add_argument("--user", required=True)
        p.add_argument("--fix", action="store_true",
                       help="Setze 'status=unread' und tag='qc-review' bei Verdachtsfällen")

    def handle(self, *a, **o):
        u = User.objects.get(username=o["user"])
        refs = Reference.objects.filter(owner=u)
        flagged = []

        for r in refs:
            title = r.title.strip()
            journal = r.journal.strip()
            reasons = []

            for pat, reason in SUSPICIOUS_PATTERNS:
                if re.search(pat, title, re.IGNORECASE):
                    reasons.append(f"Titel: {reason}")

            # Heuristik: Titel sehr kurz und generisch
            if len(title) < 10 and not re.search(r"[A-Z]{2,}", title):
                reasons.append(f"Titel zu kurz ({len(title)} Zeichen)")

            # Heuristik: Journal aus historischer/archäologischer Domain
            if re.search(r"epigraph|springerreference", journal, re.IGNORECASE):
                reasons.append(f"Journal verdächtig: {journal}")

            # Heuristik: Filename vs. Title weit auseinander
            fn = (r.notes or "").lower()
            fn_keywords = re.findall(r"[a-z]{5,}", fn)
            title_keywords = re.findall(r"[a-z]{5,}", title.lower())
            if fn_keywords and title_keywords:
                overlap = set(fn_keywords) & set(title_keywords)
                if len(overlap) == 0 and len(title_keywords) > 1:
                    reasons.append("Keine Keyword-Übereinstimmung Filename↔Titel")

            if reasons:
                flagged.append((r, reasons))

        self.stdout.write(f"\n⚠️ {len(flagged)} verdächtige Einträge:\n")
        for r, reasons in flagged:
            self.stdout.write(f"  [{r.bibtex_key}]  {r.title[:55]}")
            for reason in reasons:
                self.stdout.write(f"     → {reason}")
            if o["fix"]:
                tags = r.tags + ", qc-review" if r.tags else "qc-review"
                r.tags = tags
                r.save(update_fields=["tags"])

        if o["fix"]:
            self.stdout.write(self.style.WARNING(
                f"\n{len(flagged)} Einträge mit 'qc-review' getaggt"))
