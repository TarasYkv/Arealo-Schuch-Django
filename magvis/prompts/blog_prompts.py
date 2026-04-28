"""GLM-Prompts für Blog-Sektionen (Naturmacher-Stil)."""

NATURMACHER_VOICE = (
    "Du schreibst aus erster Person fuer Naturmacher.de — wir sind ein "
    "deutscher Familienbetrieb (graviert seit 2019 Blumentoepfe als "
    "personalisierte Geschenke).\n\n"
    "PERSPEKTIVE — STRENG:\n"
    "- Schreibe in 'wir' / 'uns' / 'bei Naturmacher': "
    "  'Wir bei Naturmacher gravieren...', 'Bei uns hat sich gezeigt...', "
    "  'Aus unserer Werkstatt-Erfahrung...'\n"
    "- Spreche den Leser mit 'du' / 'dich' / 'dein' an.\n"
    "- KEINE neutralen Sachtexte ohne Stimme, KEINE 'Sie'-Form, KEINE "
    "  generischen Floskeln wie 'Es ist allgemein bekannt...'\n\n"
    "EIGENE ERFAHRUNG einstreuen (E-E-A-T):\n"
    "- Mindestens 2-3 konkrete Praxis-Mini-Anekdoten pro Beitrag, z.B.:\n"
    "  • 'Letztens hat uns eine Kundin geschrieben, sie habe ihren...'\n"
    "  • 'In unserer Werkstatt sehen wir oft, dass...'\n"
    "  • 'Wir haben schon hunderte Toepfe graviert und wissen daher...'\n"
    "  • 'Eine Mama erzaehlte uns, ihre Tochter habe...'\n"
    "- Die Anekdoten muessen plausibel sein und zum Thema des Abschnitts passen.\n\n"
    "STIL:\n"
    "- Warm, herzlich, ehrlich, naturverbunden.\n"
    "- Korrektes Deutsch, fluessige Saetze, max. 25 Woerter pro Satz.\n"
    "- KEINE hohlen Marketing-Phrasen ('zeitlose Eleganz', 'erstklassige Qualitaet').\n"
    "- Konkrete Bilder, sinnliche Sprache, kleine Beispiele aus dem Alltag."
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
        f"Schreibe 2-3 Absaetze (insgesamt 180-280 Woerter) fuer die Blog-Sektion "
        f"\"{heading}\" innerhalb eines Beitrags zum Thema \"{topic}\". "
        f"{position_hint}\n\n"
        f"INVERTED PYRAMID (kritisch fuer SEO + LLM-Snippet-Ranking):\n"
        f"- Die ersten 1-2 Saetze beantworten die Sektions-Frage DIREKT und "
        f"  prägnant (definitive Antwort). Erst DANACH kommen Details, Beispiele "
        f"  und Praxis-Anekdoten.\n"
        f"- Wenn moeglich: 1-2 H3-Unterueberschriften (<h3 style=\"color:#3D5A40;"
        f"margin:1.4rem 0 0.6rem;font-size:1.1rem;\">) zur Strukturierung.\n"
        f"- Mindestens 1 Praxis-Mini-Anekdote in 1. Person ('Letztens hat uns...').\n\n"
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
        f"Schreibe eine Blog-Einleitung von 2-3 Absaetzen (130-180 Woerter) "
        f'zum Thema "{topic}".\n'
        f"- Hook im 1. Satz (Frage, Statement oder Mini-Anekdote).\n"
        f"- 'Wir bei Naturmacher haben...' Erfahrungsbezug einbauen.\n"
        f"- Versprechen, was der Leser hier lernt/findet.\n"
        f"- Kein <h1>, kein <h2>. Reines HTML in <p>-Tags."
    )


def tldr_prompt(topic: str) -> str:
    """Kompakte TL;DR-Box am Anfang — Featured-Snippet- + LLM-Goldgrube."""
    return (
        f'Erstelle eine ultra-kurze Zusammenfassung fuer einen Naturmacher-Blog '
        f'zum Thema "{topic}".\n\n'
        f"FORMAT (genau einhalten):\n"
        f"- core_answer: 1 Satz, max. 25 Woerter — die Hauptaussage des Beitrags.\n"
        f"- bullets: Liste mit GENAU 3 Highlights (je 4-10 Woerter, aktives Verb).\n"
        f"- recommendation: 1 Naturmacher-Empfehlung, max. 15 Woerter.\n\n"
        f"Beispiel:\n"
        f'{{"core_answer": "Ein gravierter Blumentopf ist das ideale Geschenk fuer Erzieherinnen — '
        f'persoenlich und langlebig.", "bullets": ["Pflegeleicht und frostfest", '
        f'"Gravur frei waehlbar", "Lieferung in 5 Tagen"], "recommendation": '
        f'"Mit einer pflegeleichten Pflanze bepflanzen fuer Wow-Effekt."}}\n\n'
        f'Antworte AUSSCHLIESSLICH als JSON-Objekt mit GENAU diesen 3 Keys: '
        f'core_answer (string), bullets (array of 3 strings), recommendation (string).'
    )


def w_questions_prompt(topic: str) -> str:
    """W-Fragen-Block — beantwortet die typischen Suchanfragen direkt."""
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f'Erstelle GENAU 5 W-Fragen + direkte Antworten zum Thema "{topic}".\n'
        f"Jede Frage beginnt mit Was, Wie, Wann, Warum, oder Wer. Die Antwort "
        f"beantwortet die Frage in den ersten 10-15 Woertern direkt — danach "
        f"folgt 1 Satz mit Kontext / Naturmacher-Erfahrung.\n\n"
        f"Diese Fragen entsprechen typischen Google-Suchanfragen (W-Fragen-Box).\n\n"
        f"Antworte als JSON-Array:\n"
        f'[{{"question": "Was ist...?", "answer": "Direkte Antwort. Ergaenzender '
        f'Kontext-Satz mit Naturmacher-Erfahrung."}}, ...]'
    )


def search_intent_prompt(topic: str) -> str:
    """Klassifiziert die Suchintention, damit Ueberschriften/Sprache passen."""
    return (
        f'Klassifiziere die Suchintention fuer das Keyword "{topic}":\n\n'
        f'- "informational" — User will lernen / sich informieren '
        f'(Was, Wie, Warum, Tipps, Ideen)\n'
        f'- "transactional" — User will kaufen / direkte Aktion '
        f'(kaufen, bestellen, vergleichen)\n'
        f'- "navigational" — User sucht eine bestimmte Marke/Site\n\n'
        f"Liefere zudem 3-5 LSI-Keywords (semantisch verwandt).\n\n"
        f'Antworte als JSON: {{"intent": "informational|transactional|navigational", '
        f'"reasoning": "1 Satz", "lsi_keywords": ["...", "..."]}}'
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


def statistics_extraction_prompt(topic: str, research_text: str) -> str:
    """STRICT-Prompt fuer Halluzinations-sichere Stat-Extraktion."""
    return (
        f'Extrahiere 2-5 belastbare Statistiken zum Thema "{topic}" '
        f"aus dem unten stehenden RECHERCHE-TEXT. Liefere so viele wie moeglich.\n\n"
        f"=== ABSOLUT WICHTIGE REGELN — HALLUZINATIONS-SCHUTZ ===\n"
        f"1. ERFINDE NICHTS. Nutze AUSSCHLIESSLICH Zahlen, die WORTWOERTLICH im "
        f"   Recherche-Text stehen. Wenn keine passende Zahl da ist — liefere ein leeres Array.\n"
        f"2. quote_excerpt MUSS exakt eine Passage aus dem Recherche-Text sein, "
        f"   die die Zahl enthaelt (mindestens 50 Zeichen).\n"
        f"3. Lieber 0 statt 3 Stats, wenn du nicht 100% sicher bist.\n"
        f"4. Bevorzuge konkrete Zahlen ('686.000', '38%', '1,8 Mio.'), nicht 'viele' oder 'einige'.\n\n"
        f"=== RECHERCHE-TEXT ===\n"
        f"{research_text}\n"
        f"=== ENDE RECHERCHE-TEXT ===\n\n"
        f"Antworte AUSSCHLIESSLICH als JSON-Array (max. 3 Eintraege, oder leeres Array):\n"
        f'[{{"value": "686.000", "label": "Erzieher in Deutschland (2023)", '
        f'"source_url": "https://...", "source_name": "Statistisches Bundesamt", '
        f'"quote_excerpt": "Im Jahr 2023 waren in Deutschland rund 686.000 Personen als Erzieher beschäftigt..."}}, ...]\n\n'
        f"value: nur die Zahl mit Einheit (z.B. '38%', '1,8 Mio.', '686.000').\n"
        f"label: 4-8 Woerter Kurzbeschreibung (Was beschreibt die Zahl?).\n"
        f"source_url: VOLLSTAENDIGE URL aus den Q-Bloecken oben.\n"
        f"source_name: kurzer Quellname (z.B. 'Statistisches Bundesamt', 'BMFSFJ', 'Eurostat').\n"
        f"quote_excerpt: WORTWOERTLICHER Auszug aus dem Recherche-Text mit der Zahl drin."
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
