"""Diversity-Anchors für Produkt-Bildgenerierung.

ploom.services.image_service.generate_pot_image() integriert bereits die
volle Topfgrößen-Klausel (14cm × 14cm). Wir liefern nur den
`scene_description`-Parameter mit klarer Negativ-Liste, damit die
4 KI-Bilder garantiert unterschiedlich aussehen.
"""

# Reihenfolge der 4 KI-Bilder (Phase 1: 3 KI, Phase 2: 3 CDN, Phase 3: 1 KI)
# Position 1 = Featured-Image (Hauptbild). Lifestyle (Mensch haelt Topf) zuerst,
# damit Shopify-Galerie mit Personen-Aufnahme oeffnet.
KI_VARIANTS_PHASE_1 = ['lifestyle', 'topf_gravur', 'geschenk_uebergabe']
KI_VARIANTS_PHASE_3 = ['nahaufnahme']
ALL_KI_VARIANTS = KI_VARIANTS_PHASE_1 + KI_VARIANTS_PHASE_3


SCENE_DESCRIPTIONS = {
    'topf_gravur': (
        "Studio-Aufnahme. Reiner weißer, nahtloser Hintergrund. "
        "Eye-Level-Perspektive. KEINE Hände, KEINE Person, KEIN Außenbereich, "
        "KEIN Geschenkpapier, KEIN Lifestyle-Setting. "
        "Klare professionelle Studio-Beleuchtung, die die Gravur scharf zeigt."
    ),
    'lifestyle': (
        "Echter Innenraum (Wohnzimmer, Küche oder Arbeitsplatz). "
        "Eine erwachsene Person seitlich im Bild, Gesicht teilweise sichtbar. "
        "Natürliches Tageslicht durch ein Fenster, warme Atmosphäre. "
        "KEIN reiner Studiohintergrund. KEIN Geschenkpapier. "
        "KEINE Makro-Detailaufnahme. Authentisch, wie ein Instagram-Foto."
    ),
    'geschenk_uebergabe': (
        "Zwei Hände bei der Geschenk-Übergabe. Festliche Stimmung "
        "(Geburtstag, Jahrestag oder Weihnachten). "
        "Geschenkpapier, Schleife oder Kranz im Bild. "
        "Warmes Bokeh-Hintergrundlicht. "
        "KEIN Studio-Setting. KEIN Einzel-Topf-Stillleben. KEIN Macro."
    ),
    'nahaufnahme': (
        "Extreme Makro-Detailaufnahme der Gravur. "
        "Sehr geringe Schärfentiefe — nur die eingravierten Buchstaben sind scharf, "
        "der Rest des Topfes verschwimmt. "
        "Sichtbare Keramik-Textur, kleine Lichtreflexe in den Vertiefungen. "
        "KEINE Person, KEINE Hände, KEIN Voll-Topf-Blick, KEIN Innenraum-Kontext."
    ),
}


def scene_for(variant_type: str) -> str:
    """Liefert die Diversity-Anchor-Scene-Description für einen IMAGE_TYPE."""
    return SCENE_DESCRIPTIONS.get(variant_type, '')
