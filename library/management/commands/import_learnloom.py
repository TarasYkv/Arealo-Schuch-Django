"""Management command: importiert learnloom-PDFs + CrossRef-Metadaten in library."""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from library.models import Reference, Collection, ModuleLink

User = get_user_model()

MODULE_KEYWORDS = {
    "M02": ["photosensitiz", "chromophor", "absorption spectr", "quantum yield",
            "jablonski", "singlet excited", "triplet state"],
    "M03": ["reflectance", "ndvi", "near-infrared spectros", "hyperspectral",
            "kubelka", "diffuse reflect"],
    "M06": ["phytochrome", "far-red", "far red", "pif3", "pif4", "pif5", "red:far",
            "phyb", "phya"],
    "M07": ["cryptochrome", "phototropin", "blue light photo", "cry1", "cry2"],
    "M09": ["singlet oxygen", "reactive oxygen species", " ros ", "photodynamic",
            "oxidative stress", "lipid peroxidation"],
    "M12": ["ethylene", "climacteric", "ripening", "acc oxidase", "acc synthase"],
    "M13": ["respiration rate", "respiratory quotient", "atmung"],
    "M14": ["membrane integrity", "lipid peroxid", "malondialdehyde", " mda "],
    "M15": ["senescence", "chlorophyllase", "stay-green", "leaf senescence", "sag"],
    "M17": ["phenylpropanoid", "flavonoid", "anthocyan", "pal induc", "phenolic"],
    "M19": ["photooxidation", "photo-oxidation", "lipid oxidation",
            "photosensitiz", "malondialdehyde"],
    "M20": ["photoinhibition", "photosystem ii", "d1 protein", "psii"],
    "M22": ["lettuce", "spinach", "lamb's lettuce", "baby leaf", "salad", "romaine"],
    "M23": ["strawberry", "strawberri", "blueberry", "blueberri", "bayberry",
            "anthocyan"],
    "M24": ["mushroom", "agaricus", "champignon", "fungi", "fungal", "fungus"],
    "M25": ["broccoli", "brassica", "sprouting broccoli", "brussels sprout",
            "chinese kale"],
    "M26": ["banana", "musa", "plantain"],
    "M29": [" dali ", "digital addressable lighting", "dt6", "dt8"],
    "M30": ["sensor fusion", "time-of-flight", "vl53", "tof sensor", "multispectral",
            "hyperspectral imaging"],
    "M32": [" hplc ", "gc-ms", "gc/ms", "mass spectrometry", "chromatography"],
    "M46": ["iec 62471", "photobiological safety", "lm-79", "lm-80",
            "photoelectric safety"],
    "M49": ["botrytis", "penicillium", "listeria", "salmonella", "escherichia coli",
            "saccharomyces", "inactivation", "pathogen", "ochratoxin"],
    "M52": ["oxidative stress", "antioxidant enzyme", "ascorbate", "glutathione",
            "apx", "sod ", "catalase"],
    "M53": ["cost-benefit", "energy-efficient lighting", "lcc", "roi"],
    "M13-26-BANANA-RIPENING-CHAMBER": ["green banana", "banana ripening chamber",
                                        "degreening"],
    "M1X-OVERVIEW": ["review", "overview", "a review", "comprehensive review"],
    "POTATO": ["potato", "solanum tuberosum", "solanine", "glycoalkaloid", "chaconine"],
    "TOMATO": ["tomato", "solanum lycopersicum", "lycopene"],
    "PEPPER": ["sweet pepper", "capsicum", "paprika", "bell pepper"],
    "CITRUS": ["citrus", "orange", "lemon", "mandarin", "grapefruit"],
    "APPLE": ["apple", "malus domestica"],
    "CARROT": ["carrot", "daucus carota"],
    "OILS": ["olive oil", "edible oil", "edible oils", "fats"],
    "MILK": [" milk ", "milk products"],
}

MODULE_TITLES = {
    "M02": "Absorption & Molekulare Anregung",
    "M03": "Reflexion, Streuung, Lambert-Beer",
    "M06": "Phytochrom-System",
    "M07": "Cryptochrom, Phototropin, Blaulicht-Signale",
    "M09": "Reaktive Sauerstoffspezies (ROS)",
    "M12": "Ethylen als Regie-Hormon",
    "M13": "Atmungsrate & Respirationsquotient",
    "M14": "Membran-Integrität & Lipidperoxidation",
    "M15": "Seneszenz-assoziierte Gene",
    "M17": "Cryptochrom & Flavonoid-Abwehr",
    "M19": "Photooxidation & ROS-Schäden",
    "M20": "Photoinhibition PSII",
    "M22": "Blattsalat",
    "M23": "Erdbeeren",
    "M24": "Pilze/Champignons",
    "M25": "Brokkoli",
    "M26": "Bananen",
    "M29": "DALI-2 Steuerung",
    "M30": "Sensorik-Stack",
    "M32": "Chemische Analytik HPLC/GC-MS",
    "M46": "LED-Normen IEC 62471",
    "M49": "Mikrobiologie (Botrytis, Penicillium, Listeria)",
    "M52": "Oxidative Stress-Biochemie",
    "M53": "LCC/ROI-Wirtschaftlichkeit",
    "POTATO": "Kartoffeln (Sonderthema)",
    "TOMATO": "Tomaten (Sonderthema)",
    "PEPPER": "Paprika (Sonderthema)",
    "CITRUS": "Zitrusfrüchte (Sonderthema)",
    "APPLE": "Äpfel (Sonderthema)",
    "CARROT": "Karotten (Sonderthema)",
    "OILS": "Speiseöle (außerhalb Scope)",
    "MILK": "Milchprodukte (außerhalb Scope)",
    "M1X-OVERVIEW": "Review/Übersicht (allgemein)",
    "M13-26-BANANA-RIPENING-CHAMBER": "Bananen-Reifekammer (Spezial)",
}


def make_key(rec):
    """Erzeugt einen sprechenden BibTeX-Citation-Key."""
    authors = rec.get("authors", "")
    year = rec.get("year") or "n.d."
    first = authors.split(";")[0].split(",")[0].strip().lower() if authors else ""
    first = re.sub(r"[^a-z0-9]", "", first)
    title = rec.get("crossref_title") or rec.get("title", "")
    w = re.findall(r"[A-Za-z]{4,}", title)
    slug = (w[0] if w else "ref").lower()
    return f"{first or 'ref'}{year}{slug}"[:60]


def classify_modules(rec):
    """Ordne einen Eintrag per Keyword-Match allen passenden Modulen zu."""
    blob = " ".join([
        rec.get("title", ""),
        rec.get("crossref_title") or "",
        rec.get("abstract") or "",
        rec.get("filename", ""),
    ]).lower()
    hits = []
    for code, kws in MODULE_KEYWORDS.items():
        if any(k in blob for k in kws):
            hits.append(code)
    return hits


class Command(BaseCommand):
    help = "Importiere learnloom-PDFs (angereichert mit CrossRef-Metadaten) in library."

    def add_arguments(self, parser):
        parser.add_argument("--json", required=True,
                            help="Pfad zu enriched JSON aus /tmp/pdfs_enriched.json")
        parser.add_argument("--user", required=True,
                            help="Username (z.B. 'taras')")
        parser.add_argument("--collection", default="Promotion – Learnloom Import",
                            help="Collection-Name")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        u = User.objects.get(username=opts["user"])
        coll_name = opts["collection"]
        coll, _ = Collection.objects.get_or_create(
            owner=u, name=coll_name,
            defaults={"description": "Automatisch importiert aus learnloom "
                      "(152 PDFs, CrossRef-Metadaten), "
                      "Modul-Zuordnung via Keyword-Matching.",
                      "color": "#0b3d60"})

        data = json.loads(Path(opts["json"]).read_text())
        created, updated, links_new = 0, 0, 0

        for rec in data:
            key = make_key(rec)
            title = rec.get("crossref_title") or rec.get("title") or rec.get("filename", "unnamed")

            entry_type_map = {
                "journal-article": "article",
                "book-chapter": "misc",
                "book": "book",
                "proceedings-article": "inproceedings",
                "report": "report",
            }
            et = entry_type_map.get(rec.get("type", ""), "article")

            defaults = {
                "owner": u,
                "collection": coll,
                "entry_type": et,
                "title": title[:500],
                "authors": (rec.get("authors") or "")[:500],
                "year": rec.get("year") or None,
                "journal": (rec.get("journal") or "")[:300],
                "publisher": (rec.get("publisher") or "")[:300],
                "volume": (rec.get("volume") or "")[:50],
                "issue": (rec.get("issue") or "")[:50],
                "pages": (rec.get("pages") or "").replace("--", "–")[:50],
                "doi": (rec.get("crossref_doi") or "")[:200],
                "url": (rec.get("url") or "")[:500],
                "abstract": rec.get("abstract", ""),
                "notes": f"Learnloom-ID: {rec['id']}\nLearnloom-Datei: {rec['filename']}\nPfad: {rec.get('file_path','')}",
                "tags": "learnloom-import, promotion",
                "status": "unread",
                "relevance": 3,
            }

            if opts["dry_run"]:
                self.stdout.write(f"DRY: {key} → {title[:80]}")
                continue

            obj, was_new = Reference.objects.update_or_create(
                owner=u, bibtex_key=key, defaults=defaults)
            if was_new:
                created += 1
            else:
                updated += 1

            # Modul-Verknüpfungen
            modules = classify_modules(rec)
            for m in modules:
                ModuleLink.objects.get_or_create(
                    reference=obj, module_code=m,
                    defaults={"module_title": MODULE_TITLES.get(m, "")})
                links_new += 1

            self.stdout.write(
                f"{'[NEU]' if was_new else '[UPD]'} {key} → {title[:60]}  "
                f"(Module: {', '.join(modules) if modules else 'keine'})")

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Neu: {created}, aktualisiert: {updated}, "
            f"Modul-Links: {links_new}"))
