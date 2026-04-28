"""GLM-Prompts für Blog-Sektionen (Naturmacher-Stil)."""

NATURMACHER_VOICE = (
    "Du schreibst für Naturmacher.de — einen deutschen Familienbetrieb, der "
    "personalisierte Blumentöpfe mit Gravur als Geschenke verkauft. "
    "Stil: warm, herzlich, du-Form, persönliche Anrede des Lesers. "
    "Sprache: korrektes Deutsch, fließende Sätze, max. 25 Wörter pro Satz. "
    "Vermeide hohle Marketing-Phrasen. Nutze Bilder und Beispiele."
)


def headings_prompt(topic: str, num_headings: int = 6) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle für einen Blogbeitrag zum Thema \"{topic}\" GENAU "
        f"{num_headings} prägnante H2-Überschriften. Reihenfolge: "
        f"vom Hook über Hauptthemen bis zum Abschluss. "
        f"Antworte AUSSCHLIESSLICH als JSON-Array mit Strings: "
        f"[\"Überschrift 1\", \"Überschrift 2\", ...]"
    )


def section_prompt(topic: str, heading: str, position_hint: str = '') -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Schreibe 1-2 Absätze (insgesamt 80-180 Wörter) für die Blog-Sektion "
        f"\"{heading}\" innerhalb eines Beitrags zum Thema \"{topic}\". "
        f"{position_hint}\n\n"
        f"WICHTIG — Strukturierte Inhalte: Wenn dieser Abschnitt thematisch passt, "
        f"baue UNBEDINGT eines der folgenden Strukturelemente ein:\n"
        f"- Eine Aufzählung mit 4-6 Stichpunkten als <ul><li>...</li></ul> "
        f"  (z.B. wenn du Vorteile, Eigenschaften, Tipps, oder Eigenschaften "
        f"  einer Personengruppe aufzählen kannst — DAS IST DER NORMALFALL).\n"
        f"- Eine Vergleichstabelle mit 3-5 Zeilen + 2-3 Spalten als "
        f"  <table><thead><tr><th>...</th></tr></thead><tbody><tr><td>...</td></tr></tbody></table> "
        f"  (z.B. Vorher vs. Nachher, Standard-Geschenk vs. Personalisiert, "
        f"  Optionen mit Eigenschaften).\n"
        f"- Eine nummerierte Liste <ol><li>...</li></ol> wenn Reihenfolge wichtig.\n\n"
        f"Style-Inline (nutze Naturmacher-Farben):\n"
        f"- Tabellen: <table style=\"width:100%;border-collapse:collapse;margin:1.4rem 0;\">, "
        f"  Zellen mit <td style=\"padding:10px 14px;border-bottom:1px solid #E8DFC9;\"> "
        f"  und Header mit <th style=\"padding:10px 14px;background:#F4F8F0;color:#3D5A40;"
        f"text-align:left;border-bottom:2px solid #7D9C80;\">\n"
        f"- Listen: <ul style=\"margin:1rem 0;padding-left:1.4rem;line-height:1.7;\"> "
        f"  oder <ol style=\"margin:1rem 0;padding-left:1.4rem;line-height:1.7;\">\n"
        f"- Listen-Items dürfen <strong>fettgedruckte Schluesselworte</strong> haben.\n\n"
        f"Antworte NUR mit reinem HTML (Absätze in <p>...</p>, plus die "
        f"strukturellen Elemente). KEIN <h2>, kein Markdown."
    )


def intro_prompt(topic: str) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Schreibe eine Blog-Einleitung von genau 2 Absätzen (zusammen 100-150 Wörter) "
        f"zum Thema \"{topic}\". Ein starker Hook, eine emotionale Verbindung zum Leser, "
        f"ein Versprechen, was im Beitrag kommt. Kein <h1>, kein <h2>. "
        f"Antworte als reines HTML in <p>-Tags."
    )


def facts_prompt(topic: str, num_facts: int = 4) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle GENAU {num_facts} interessante, ueberraschende Fakten zum Thema "
        f'"{topic}". Jeder Fakt: 1 Satz (max. 25 Woerter), faktisch wahr, '
        f"nicht-trivial. Keine Werbetexte, kein Marketing.\n\n"
        f"Antworte AUSSCHLIESSLICH als JSON-Array:\n"
        f'[{{"icon": "🌱", "title": "Kurzer Fakten-Titel", "text": "Der Fakt-Satz."}}, ...]\n'
        f"icon: 1 passendes Emoji (Pflanze, Stern, Geschenk, Gluehbirne, Herz, ...). "
        f"title: 2-4 Woerter."
    )


def tips_prompt(topic: str, num_tips: int = 4) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle GENAU {num_tips} praktische, sofort umsetzbare Tipps zum Thema "
        f'"{topic}". Jeder Tipp: 1 Anweisung (max. 30 Woerter), aktiver Imperativ '
        f'("Schreibe...", "Verpacke...", "Nutze..."), du-Form.\n\n'
        f"Antworte AUSSCHLIESSLICH als JSON-Array:\n"
        f'[{{"icon": "💡", "title": "Kurzer Tipp-Titel", "text": "Der Tipp-Satz."}}, ...]\n'
        f"icon: 1 passendes Emoji. title: 2-4 Woerter."
    )


def seo_prompt(topic: str) -> str:
    """SEO-Titel + Meta-Description, optimiert auf MID-VOLUME-Long-Tail-Keywords."""
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle SEO-Titel und Meta-Description fuer einen Blogbeitrag zum Thema "
        f'"{topic}" (Naturmacher.de — gravierte Blumentoepfe).\n\n'
        f"WICHTIG — Mid-Volume-Strategie (nicht super-kompetitive Keywords, "
        f"sondern realistisch rankbare Long-Tails):\n"
        f"- Title 50-60 Zeichen, mit 3-4 Wort-Long-Tail (z.B. statt 'Geschenk Erzieherin' "
        f"  besser 'Geschenk Erzieherin Kindergarten Abschied' oder 'Persoenliches "
        f"  Abschiedsgeschenk Erzieherin').\n"
        f"- Modifier zur Eingrenzung verwenden: 'persoenlich', 'individuell', 'kreativ', "
        f"  'mit Gravur', 'zum Abschied', 'fuer den Geburtstag', 'guenstig'.\n"
        f"- Im Title gerne Zahlen oder Frage-Form ('5 Ideen fuer...', 'Was schenken...?').\n"
        f"- Description 140-160 Zeichen, Long-Tail-Keyword + Vorteil + Call-to-Action "
        f"  ('jetzt entdecken', 'mit Gravur', 'in 5 Tagen').\n"
        f"- Description darf 1-2 Long-Tail-Keywords enthalten (nicht stuffing).\n"
        f"- Zielsuchvolumen: 100-2000/Monat (mid-tail), KEINE generischen Top-Keywords.\n\n"
        f'Antwort als JSON: {{"title": "...", "description": "...", '
        f'"target_keyword": "das Long-Tail-Keyword auf das du optimiert hast"}}'
    )


def faqs_prompt(topic: str, num_faqs: int = 5) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle GENAU {num_faqs} häufig gestellte Fragen (FAQ) zum Thema "
        f"\"{topic}\" für einen Naturmacher-Blogbeitrag. "
        f"Mische allgemeine Fragen zum Thema mit konkreten Fragen zu personalisierten "
        f"Geschenken (Blumentopf mit Gravur).\n\n"
        f"Antworte AUSSCHLIESSLICH als JSON-Array:\n"
        f'[{{"question": "...?", "answer": "..."}}, ...]\n'
        f"Antworten 30-80 Wörter, sachlich-warm formuliert, keine Marketing-Floskeln."
    )
