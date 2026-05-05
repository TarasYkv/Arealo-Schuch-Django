"""GLM-Prompts für Blog-Sektionen (Naturmacher-Stil)."""

NATURMACHER_VOICE = (
    "Du schreibst einen umfassenden Geschenk-Ratgeber. Naturmacher ist eine "
    "von vielen möglichen Quellen — KEIN reiner Werbe-Text.\n\n"
    "PERSPEKTIVE & MISCHUNG (wichtig):\n"
    "- ~70% der Sektion: ALLGEMEINE Geschenkideen, Tipps, Hintergründe, "
    "  Inspiration — was generell zum Thema passt, mehrere Optionen, "
    "  verschiedene Preisklassen, unterschiedliche Anlässe und Empfängertypen.\n"
    "- ~30% der Sektion: Naturmacher-Erfahrung in 1. Person ('wir', 'uns'), "
    "  aber NUR wo sie wirklich Mehrwert bringt — als zusätzliche Stimme, "
    "  nicht als Hauptstoff.\n"
    "- Spreche den Leser mit 'du' / 'dich' / 'dein' an.\n"
    "- KEINE 'Sie'-Form, KEINE leeren Floskeln.\n\n"
    "EIGENE ERFAHRUNG sparsam einstreuen (E-E-A-T):\n"
    "- Pro BEITRAG insgesamt MAX. 2-3 konkrete Anekdoten, NICHT pro Sektion.\n"
    "- Anekdoten plausibel, kurz, zum Thema des Abschnitts. Beispiele:\n"
    "  • 'Eine Kundin schrieb uns, ihre Tochter habe...'\n"
    "  • 'Aus hunderten Gravuren wissen wir, dass...'\n"
    "- In den meisten Sektionen reichen ALLGEMEINE Tipps, ohne 'wir bei Naturmacher'.\n\n"
    "STIL:\n"
    "- Warm, sachlich, kompetent — wie ein guter Ratgeber-Artikel.\n"
    "- Korrektes Deutsch, flüssige Sätze, max. 25 Wörter pro Satz.\n"
    "- KEINE hohlen Marketing-Phrasen ('zeitlose Eleganz', 'erstklassige Qualität').\n"
    "- Konkrete Beispiele, Preisrahmen, Alternativen, Pro/Contra."
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
        f"Schreibe 2-3 Absätze (insgesamt 180-280 Wörter) für die Blog-Sektion "
        f"\"{heading}\" innerhalb eines Beitrags zum Thema \"{topic}\". "
        f"{position_hint}\n\n"
        f"INVERTED PYRAMID (kritisch für SEO + LLM-Snippet-Ranking):\n"
        f"- Die ersten 1-2 Sätze beantworten die Sektions-Frage DIREKT und "
        f"  prägnant (definitive Antwort). Erst DANACH kommen Details, Beispiele.\n"
        f"- Wenn möglich: 1-2 H3-Unterüberschriften (<h3 style=\"color:#3D5A40;"
        f"margin:1.4rem 0 0.6rem;font-size:1.1rem;\">) zur Strukturierung.\n"
        f"- Mehrere konkrete Geschenkideen, Preisrahmen, Alternativen für "
        f"  unterschiedliche Empfänger-Typen und Anlässe.\n"
        f"- Eine Naturmacher-Anekdote NUR wenn sie wirklich passt — nicht in "
        f"  jeder Sektion (max. 2-3 im ganzen Beitrag).\n\n"
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
        f"- Listen-Items dürfen <strong>fettgedruckte Schlüsselworte</strong> haben.\n\n"
        f"Antworte NUR mit reinem HTML (Absätze in <p>...</p>, plus die "
        f"strukturellen Elemente). KEIN <h2>, kein Markdown."
    )


def intro_prompt(topic: str) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Schreibe eine Blog-Einleitung von 2-3 Absätzen (130-180 Wörter) "
        f'zum Thema "{topic}".\n'
        f"- Hook im 1. Satz (Frage, Statement oder Mini-Anekdote).\n"
        f"- 'Wir bei Naturmacher haben...' Erfahrungsbezug einbauen.\n"
        f"- Versprechen, was der Leser hier lernt/findet.\n"
        f"- Kein <h1>, kein <h2>. Reines HTML in <p>-Tags."
    )


def tldr_prompt(topic: str) -> str:
    """Kompakte TL;DR-Box am Anfang — Featured-Snippet- + LLM-Goldgrube."""
    return (
        f'Erstelle eine ultra-kurze Zusammenfassung für einen Naturmacher-Blog '
        f'zum Thema "{topic}".\n\n'
        f"FORMAT (genau einhalten):\n"
        f"- core_answer: 1 Satz, max. 25 Wörter — die Hauptaussage des Beitrags.\n"
        f"- bullets: Liste mit GENAU 3 Highlights (je 4-10 Wörter, aktives Verb).\n"
        f"- recommendation: 1 Naturmacher-Empfehlung, max. 15 Wörter.\n\n"
        f"Beispiel:\n"
        f'{{"core_answer": "Ein gravierter Blumentopf ist das ideale Geschenk für Erzieherinnen — '
        f'persönlich und langlebig.", "bullets": ["Pflegeleicht und frostfest", '
        f'"Gravur frei wählbar", "Lieferung in 5 Tagen"], "recommendation": '
        f'"Mit einer pflegeleichten Pflanze bepflanzen für Wow-Effekt."}}\n\n'
        f'Antworte AUSSCHLIESSLICH als JSON-Objekt mit GENAU diesen 3 Keys: '
        f'core_answer (string), bullets (array of 3 strings), recommendation (string).'
    )


def w_questions_prompt(topic: str) -> str:
    """W-Fragen-Block — beantwortet die typischen Suchanfragen direkt."""
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f'Erstelle GENAU 5 W-Fragen + direkte Antworten zum Thema "{topic}".\n'
        f"Jede Frage beginnt mit Was, Wie, Wann, Warum, oder Wer. Die Antwort "
        f"beantwortet die Frage in den ersten 10-15 Wörtern direkt — danach "
        f"folgt 1 Satz mit Kontext / Naturmacher-Erfahrung.\n\n"
        f"Diese Fragen entsprechen typischen Google-Suchanfragen (W-Fragen-Box).\n\n"
        f"Antworte als JSON-Array:\n"
        f'[{{"question": "Was ist...?", "answer": "Direkte Antwort. Ergänzender '
        f'Kontext-Satz mit Naturmacher-Erfahrung."}}, ...]'
    )


def search_intent_prompt(topic: str) -> str:
    """Klassifiziert die Suchintention, damit Überschriften/Sprache passen."""
    return (
        f'Klassifiziere die Suchintention für das Keyword "{topic}":\n\n'
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
        f"Erstelle GENAU {num_facts} interessante, überraschende Fakten zum Thema "
        f'"{topic}". Jeder Fakt: 1 Satz (max. 25 Wörter), faktisch wahr, '
        f"nicht-trivial. Keine Werbetexte, kein Marketing.\n\n"
        f"Antworte AUSSCHLIESSLICH als JSON-Array:\n"
        f'[{{"icon": "🌱", "title": "Kurzer Fakten-Titel", "text": "Der Fakt-Satz."}}, ...]\n'
        f"icon: 1 passendes Emoji (Pflanze, Stern, Geschenk, Gluehbirne, Herz, ...). "
        f"title: 2-4 Wörter."
    )


def tips_prompt(topic: str, num_tips: int = 4) -> str:
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle GENAU {num_tips} praktische, sofort umsetzbare Tipps zum Thema "
        f'"{topic}". Jeder Tipp: 1 Anweisung (max. 30 Wörter), aktiver Imperativ '
        f'("Schreibe...", "Verpacke...", "Nutze..."), du-Form.\n\n'
        f"Antworte AUSSCHLIESSLICH als JSON-Array:\n"
        f'[{{"icon": "💡", "title": "Kurzer Tipp-Titel", "text": "Der Tipp-Satz."}}, ...]\n'
        f"icon: 1 passendes Emoji. title: 2-4 Wörter."
    )


def seo_prompt(topic: str) -> str:
    """SEO-Titel + Meta-Description, optimiert auf MID-VOLUME-Long-Tail-Keywords.

    Title-Stil-Rotation (gegen Listicle-Monotonie): GLM soll EINEN von 7 Stilen
    zufällig wählen, NICHT immer Zahlen-Listicle.
    """
    import random
    title_styles = [
        # 1. Ratgeber-Frage
        '"Was schenken Erzieherinnen wirklich Freude bereitet" (Frage-Form, ohne Zahl, neugierig)',
        # 2. How-to / Anleitung
        '"So findest du das perfekte Geschenk für Anlagenmechaniker" (How-to, du-Anrede)',
        # 3. Emotion / Bedeutung (ohne Produkt-Wort wie "Topf")
        '"Warum manche Geschenke Erzieherinnen ein Leben lang begleiten" (Emotion, ohne Produkt-Wort, ohne Zahl)',
        # 4. Vergleich / Negation
        '"Schluss mit lieblosen Standardgeschenken — Ideen für Antiquare" (Negation + Lösung)',
        # 5. Benefit-Fokus
        '"Kleines Geschenk, große Wirkung: Persönliche Ideen für Anwälte" (Benefit-Versprechen)',
        # 6. Listicle (klassisch — nur 1 von 7 Optionen, nicht Standard!)
        '"7 ungewöhnliche Geschenkideen für Animateurinnen" (Zahl-Liste, OK aber NICHT Default)',
        # 7. Insider/Tipp (ohne Jahresangabe)
        '"Das Abschiedsgeschenk, das Altenpflegerinnen wirklich rührt" (Insider + Empfehlung, KEINE Jahreszahl)',
    ]
    chosen_style = random.choice(title_styles)
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f"Erstelle SEO-Titel und Meta-Description für einen Blogbeitrag zum Thema "
        f'"{topic}" (Naturmacher.de — gravierte Blumentöpfe).\n\n'
        f"WICHTIG — Mid-Volume-Strategie (nicht super-kompetitive Keywords, "
        f"sondern realistisch rankbare Long-Tails):\n"
        f"- Title 50-65 Zeichen, mit 3-4 Wort-Long-Tail.\n"
        f"- Modifier zur Eingrenzung verwenden: 'persönlich', 'individuell', 'kreativ', "
        f"  'mit Gravur', 'zum Abschied', 'für den Geburtstag', 'günstig'.\n\n"
        f"=== TITLE-STIL FÜR DIESEN BEITRAG ===\n"
        f"Verwende DIESEN Stil: {chosen_style}\n"
        f"NICHT immer Zahlen-Listicle ('5 Ideen', '7 Geschenke')! "
        f"Halte dich an den vorgegebenen Stil oben — bringt Variation in die "
        f"Blog-Liste.\n\n"
        f"=== HARTE REGELN (verboten im Title) ===\n"
        f"- KEINE Produktbezeichnung im Title (verboten: 'Blumentopf', 'Topf', "
        f"  'Pflanzgefäß', 'Keramik') — der Topf wird im Inhalt erwähnt, im Title "
        f"  aber soll der Anlass/die Person Fokus sein, nicht das Produkt.\n"
        f"- KEINE Jahreszahl im Title (verboten: '2026', '2025', '2027', "
        f"  'in diesem Jahr') — Titel sollen zeitlos bleiben, sonst wirken sie "
        f"  in 6 Monaten veraltet.\n"
        f"- KEIN '__' oder '|' als Trenner — nur ':' oder '—' oder Komma.\n\n"
        f"=== DESCRIPTION ===\n"
        f"- Description 140-160 Zeichen, Long-Tail-Keyword + Vorteil + Call-to-Action "
        f"  ('jetzt entdecken', 'mit Gravur', 'in 5 Tagen').\n"
        f"- Description darf 1-2 Long-Tail-Keywords enthalten (nicht stuffing).\n"
        f"- Zielsuchvolumen: 100-2000/Monat (mid-tail), KEINE generischen Top-Keywords.\n\n"
        f'Antwort als JSON: {{"title": "...", "description": "...", '
        f'"target_keyword": "das Long-Tail-Keyword auf das du optimiert hast"}}'
    )


def dos_donts_prompt(topic: str) -> str:
    """Generiert Do's and Don'ts für eine 2-Spalten-Tabelle vor den FAQs."""
    return (
        f"{NATURMACHER_VOICE}\n\n"
        f'Erstelle Do\'s and Don\'ts für ein Geschenk zum Thema "{topic}". '
        f"Genau 5 Do\'s und 5 Don\'ts, die thematisch zum Topic passen.\n\n"
        f"Do's = was sollte man beim Geschenk tun (positive Tipps).\n"
        f"Don'ts = was sollte man vermeiden (negative Pitfalls).\n\n"
        f"Stil:\n"
        f"- Jede Zeile max 60 Zeichen, klar + actionable.\n"
        f"- Keine generischen Sprüche, immer Topic-spezifisch.\n"
        f'- Beispiele für "Geschenk Erzieherin Abschied":\n'
        f'  Do: "Karte mit allen Kindernamen unterschreiben lassen"\n'
        f'  Don\'t: "Standard-Pralinen ohne persönliche Note"\n\n'
        f'Antwort als JSON: {{"dos": ["...", "...", ...], "donts": ["...", "...", ...]}}'
    )


def statistics_extraction_prompt(topic: str, research_text: str) -> str:
    """Prompt für Stat- + Aussagen-Extraktion (Halluzinations-sicher aber optimistisch)."""
    return (
        f'Extrahiere 3-5 belegbare Aussagen zum Thema "{topic}" aus dem '
        f"RECHERCHE-TEXT. Mix aus Zahlen-Statistiken UND qualitativen Aussagen — "
        f"BEVORZUGE Aussagen, wenn die Zahl sich nicht 1:1 im Snippet wiederfindet.\n\n"
        f"=== REGELN ===\n"
        f"1. Nutze NUR Aussagen, die im Recherche-Text vorkommen (wortwoertlich oder "
        f"   sinngemaess paraphrasiert). KEIN frei erfinden.\n"
        f"2. quote_excerpt: PASSAGE aus dem Recherche-Text (>= 30 Zeichen), "
        f"   die die Aussage stützt — moeglichst WORTWOERTLICH aus dem Snippet.\n"
        f"3. Liefere mindestens 2-3 brauchbare Aussagen — KEINE leere Liste. "
        f"   Im Recherche-Text gibt es fast immer Aussagen, die wir stuetzen koennen.\n"
        f"4. value-PRIORITAET in dieser Reihenfolge:\n"
        f"   a) Praegnante 3-7-Wort-AUSSAGE (robust, leicht zu verifizieren) — "
        f"      'Studienberechtigte sinken seit 2022', "
        f"      'Pflanzen halten Jahre laenger als Schnittblumen', "
        f"      'Personalisierte Geschenke werden bevorzugt'\n"
        f"   b) Konkrete Zahl mit Einheit — nur wenn sie EXAKT im Snippet steht: "
        f"      '686.000', '38%', '2024'\n"
        f"5. Bei Zahlen: schreibe sie EXAKT wie im Snippet "
        f"   (also '373.000' wenn da '373.000' steht — nicht 'rund 373 000').\n"
        f"6. Bei Vagheit ('viele', 'oft'): nur extrahieren, wenn der Recherche-Text "
        f"   eine konkrete Beleg-Phrase liefert ('die Mehrheit der Befragten').\n\n"
        f"=== RECHERCHE-TEXT ===\n"
        f"{research_text}\n"
        f"=== ENDE RECHERCHE-TEXT ===\n\n"
        f"Antworte als JSON-Array (max. 5 Eintraege oder leer):\n"
        f"BEISPIELE (gemischt — Zahlen + Aussagen):\n"
        f'[{{"value": "686.000", "label": "Erzieher in Deutschland (2023)", '
        f'"source_url": "https://...", "source_name": "Statistisches Bundesamt", '
        f'"quote_excerpt": "Im Jahr 2023 waren in Deutschland rund 686.000 Personen als Erzieher beschäftigt..."}},\n'
        f' {{"value": "Persönliches wirkt länger", "label": "Forschung zur Geschenkpsychologie", '
        f'"source_url": "https://...", "source_name": "Max-Planck-Institut", '
        f'"quote_excerpt": "Studien zeigen: Persönlich gestaltete Geschenke wirken nachhaltig emotionaler als..."}}]\n\n'
        f"value: konkrete Zahl mit Einheit ODER 3-7-Wort-Aussage.\n"
        f"label: 4-8 Wörter Kurzbeschreibung.\n"
        f"source_url: VOLLSTÄNDIGE URL aus den Q-Blöcken.\n"
        f"source_name: kurzer Quellname.\n"
        f"quote_excerpt: WORTWOERTLICHER Auszug aus dem Recherche-Text."
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
