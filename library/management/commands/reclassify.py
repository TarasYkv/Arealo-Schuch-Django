"""Management command: Ordnet noch unklassifizierte Referenzen via erweitertem Keyword-Set neu zu."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from library.models import Reference, ModuleLink

User = get_user_model()

EXTRA_KEYWORDS = {
    "M02": ["porphyrin", "excit state", "chromophor", "singlet excited"],
    "M03": ["spectrosc", "near-infrared", " nir ", "diffuse reflect", "reflectance index"],
    "M06": ["light quality", "r:fr", "red to far-red", "pfr", "phytochrom"],
    "M07": ["blue light", "uv-a", "uva radiation", "cry ", "crypto"],
    "M09": ["reactive oxygen", "roc generation", "oxidative damage"],
    "M15": ["senesce", "shelf-life", "shelf life", "shelf-l"],
    "M17": ["phenolic", "antioxidant", "flavonoid", "anthocyan"],
    "M19": ["photo-oxidation", "photooxidation", "light-induced oxidation",
            "lipid oxidation"],
    "M22": ["lettuce", "lamb's lettuce", "spinach", "pak choi", "bok choy"],
    "M25": ["broccoli", "brussels sprout", "chinese kale", "cruciferous"],
    "M26": ["banana"],
    "M32": ["hplc", "high performance liquid", "gc-ms"],
    "M49": ["listeria", "salmonella", "escherichia", "e. coli",
            "staphylococcus", "pathogen inactivation", "bacterial inactivation",
            "fungal pathogen", "botrytis", "penicillium", "bacillus"],
    "M52": ["ascorbate", "ascorbic acid", "vitamin c", "antioxidant",
            "apx", "sod ", "catalase"],
    "M53": ["cost-benefit", "energy saving", "roi", "economic analysis"],
    "POTATO": ["potato", "solanum tuberosum"],
    "TOMATO": ["tomato", "lycopene"],
    "PEPPER": ["bell pepper", "sweet pepper", "capsicum"],
    "CITRUS": ["citrus", "orange", "mandarin"],
    "M1X-OVERVIEW": ["review", "overview"],
}

MODULE_TITLES = {
    "M02": "Absorption & Molekulare Anregung",
    "M03": "Reflexion, Streuung, Lambert-Beer",
    "M06": "Phytochrom-System",
    "M07": "Cryptochrom, Phototropin, Blaulicht",
    "M09": "Reaktive Sauerstoffspezies (ROS)",
    "M15": "Seneszenz-Gene & Shelf-Life",
    "M17": "Flavonoid-Abwehr",
    "M19": "Photooxidation",
    "M22": "Blattsalat",
    "M25": "Brokkoli/Brassicaceae",
    "M26": "Bananen",
    "M32": "Chemische Analytik",
    "M49": "Mikrobiologie / Pathogene",
    "M52": "Oxidative Stress-Biochemie",
    "M53": "Wirtschaftlichkeit",
    "POTATO": "Kartoffeln",
    "TOMATO": "Tomaten",
    "PEPPER": "Paprika",
    "CITRUS": "Zitrus",
    "M1X-OVERVIEW": "Reviews",
}


class Command(BaseCommand):
    help = "Klassifiziere noch nicht zugeordnete Referenzen nach."

    def add_arguments(self, p):
        p.add_argument("--user", required=True)
        p.add_argument("--force", action="store_true",
                       help="Auch bereits klassifizierte neu durchlaufen")

    def handle(self, *a, **o):
        u = User.objects.get(username=o["user"])
        qs = Reference.objects.filter(owner=u)
        if not o["force"]:
            qs = qs.filter(module_links__isnull=True)
        count_new = 0
        for r in qs:
            blob = " ".join([r.title, r.authors, r.abstract, r.journal, r.notes]).lower()
            for code, kws in EXTRA_KEYWORDS.items():
                if any(k in blob for k in kws):
                    _, created = ModuleLink.objects.get_or_create(
                        reference=r, module_code=code,
                        defaults={"module_title": MODULE_TITLES.get(code, "")})
                    if created:
                        count_new += 1
                        self.stdout.write(f"[+] {r.bibtex_key} → {code}")
        self.stdout.write(self.style.SUCCESS(f"\n✓ {count_new} neue Modul-Links erstellt"))
