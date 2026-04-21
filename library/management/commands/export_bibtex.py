"""Management command: Exportiert alle Referenzen eines Users als BibTeX."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from library.models import Reference

User = get_user_model()

ESC = str.maketrans({"{": "\\{", "}": "\\}"})


def clean(s):
    if s is None:
        return ""
    return str(s).replace("\n", " ").strip()


def to_bibtex(r: Reference) -> str:
    type_map = {
        "article": "article",
        "book": "book",
        "inproceedings": "inproceedings",
        "thesis": "phdthesis",
        "report": "techreport",
        "misc": "misc",
    }
    bt = type_map.get(r.entry_type, "misc")

    fields = []
    fields.append(("title", clean(r.title)))
    if r.authors:
        authors_bib = " and ".join(
            a.strip() for a in r.authors.split(";") if a.strip())
        fields.append(("author", authors_bib))
    if r.year:
        fields.append(("year", str(r.year)))
    if r.journal:
        fields.append(("journal", clean(r.journal)))
    if r.publisher:
        fields.append(("publisher", clean(r.publisher)))
    if r.volume:
        fields.append(("volume", clean(r.volume)))
    if r.issue:
        fields.append(("number", clean(r.issue)))
    if r.pages:
        fields.append(("pages", clean(r.pages)))
    if r.doi:
        fields.append(("doi", clean(r.doi)))
    if r.isbn:
        fields.append(("isbn", clean(r.isbn)))
    if r.url:
        fields.append(("url", clean(r.url)))
    if r.abstract:
        fields.append(("abstract", clean(r.abstract)[:1500]))
    if r.tag_list:
        fields.append(("keywords", ", ".join(r.tag_list)))
    if r.notes:
        fields.append(("note", clean(r.notes)[:500]))

    # Module-Tags
    modules = list(r.module_links.values_list("module_code", flat=True))
    if modules:
        fields.append(("module", ", ".join(modules)))

    body = ",\n".join(f"  {k:10s} = {{{v}}}" for k, v in fields)
    return f"@{bt}{{{r.bibtex_key},\n{body}\n}}\n"


class Command(BaseCommand):
    help = "Exportiere alle Referenzen eines Users als BibTeX."

    def add_arguments(self, p):
        p.add_argument("--user", required=True)
        p.add_argument("--out", default="/tmp/library_export.bib")

    def handle(self, *a, **o):
        u = User.objects.get(username=o["user"])
        refs = Reference.objects.filter(owner=u).order_by("year", "bibtex_key")
        with open(o["out"], "w", encoding="utf-8") as f:
            f.write("% =============================================\n")
            f.write(f"% BibTeX Export aus Workloom-Library\n")
            f.write(f"% User: {u.username}\n")
            f.write(f"% Anzahl: {refs.count()} Einträge\n")
            f.write("% Import in Zotero: File → Import → Auswahl dieser Datei\n")
            f.write("% =============================================\n\n")
            for r in refs:
                f.write(to_bibtex(r))
                f.write("\n")
        self.stdout.write(self.style.SUCCESS(
            f"✓ {refs.count()} Einträge exportiert nach {o['out']}"))
