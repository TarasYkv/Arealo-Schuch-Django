"""
VSkript Service

Generiert Videoskripte basierend auf Keywords/Beschreibungen
mit erweiterten Optionen für Ton, Zielgruppe und Plattform.
"""

import logging
import re
import time
from typing import Dict, Optional

# Optionale Imports - werden nur bei Bedarf geladen
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class VSkriptService:
    """Service für Videoskript-Generierung"""

    # Durchschnittliche Wörter pro Minute beim Sprechen
    WORDS_PER_MINUTE = 130

    # === SCRIPT TYPE PROMPTS ===
    SCRIPT_TYPE_PROMPTS = {
        'fun_facts': {
            'name': 'Witzige Fakten',
            'instructions': """Erstelle witzige, überraschende Fakten zum Thema.
- Beginne mit "Wusstest du, dass..."
- Verwende humorvolle, unterhaltsame Fakten
- Überrasche mit unerwarteten Zusammenhängen
- Halte den Ton locker und lustig
- Die Fakten sollen zum Schmunzeln bringen"""
        },
        'interesting_facts': {
            'name': 'Interessante Fakten',
            'instructions': """Präsentiere faszinierende, wissenswerte Fakten zum Thema.
- Starte mit dem interessantesten Fakt als Hook
- Verwende konkrete Zahlen und Beispiele
- Verknüpfe Fakten miteinander
- Schließe mit einem "Wow-Moment" ab"""
        },
        'how_to': {
            'name': 'Schritt-für-Schritt Anleitung',
            'instructions': """Erstelle eine klare Schritt-für-Schritt Anleitung.
- Beginne mit dem Ziel: "In diesem Video zeige ich dir, wie..."
- Nummeriere die Schritte klar durch
- Erkläre jeden Schritt verständlich
- Gib praktische Tipps bei jedem Schritt
- Fasse am Ende zusammen"""
        },
        'tips': {
            'name': 'Tipps & Tricks',
            'instructions': """Präsentiere die besten Tipps und Tricks kompakt.
- Starte mit "Hier sind meine Top-Tipps für..."
- Nummeriere jeden Tipp
- Halte jeden Tipp kurz und prägnant
- Erkläre warum jeder Tipp funktioniert
- Füge einen Bonus-Tipp am Ende hinzu"""
        },
        'story': {
            'name': 'Spannende Geschichte',
            'instructions': """Erzähle eine spannende, fesselnde Geschichte zum Thema.
- Beginne mit einem packenden Einstieg
- Baue Spannung auf
- Schaffe eine emotionale Verbindung
- Die Geschichte soll unterhalten und fesseln
- Schließe mit einem überraschenden oder berührenden Ende"""
        },
        'true_false': {
            'name': 'Wahr/Falsch Spiel',
            'instructions': """Erstelle eine "Wahr oder Falsch" Geschichte.
- Erzähle eine unglaubliche aber wahre Geschichte ODER eine erfundene Geschichte
- Baue die Geschichte spannend auf
- Halte den Zuschauer in Spannung
- Am Ende auflösen ob es wahr oder falsch ist
- Erkläre kurz warum"""
        },
        'qa': {
            'name': 'Frage & Antwort',
            'instructions': """Stelle eine spannende Frage und beantworte sie überraschend.
- Beginne mit einer fesselnden Frage
- Baue Spannung auf ("Hast du dich das auch schon gefragt?")
- Gib eine überraschende oder interessante Antwort
- Erkläre den Hintergrund kurz
- Schließe mit einer Erkenntnis ab"""
        },
        'riddle': {
            'name': 'Rätsel',
            'instructions': """Erstelle ein Rätsel zum Thema.
- Formuliere ein kniffliges Rätsel
- Gib dem Zuschauer Zeit zum Nachdenken (z.B. "Denk mal kurz nach...")
- Die Lösung soll überraschend aber logisch sein
- Löse das Rätsel am Ende auf
- Erkläre kurz warum die Lösung stimmt"""
        },
        'expectation_reality': {
            'name': 'Erwartung vs. Realität',
            'instructions': """Zeige den lustigen Unterschied zwischen Erwartung und Realität.
- Beschreibe zuerst die typische Erwartung
- Dann die (oft lustige) Realität
- Verwende Kontraste für Humor
- Das Format: "Erwartung: ... Realität: ..."
- Halte es relatable und witzig"""
        },
        'myth_busting': {
            'name': 'Mythen aufdecken',
            'instructions': """Decke populäre Mythen und Irrtümer zum Thema auf.
- Starte mit einem weit verbreiteten Mythos
- Erkläre warum viele Menschen das glauben
- Enthülle dann die überraschende Wahrheit
- Belege mit Fakten oder Beispielen
- Schließe mit einer Lektion ab"""
        },
        'comparison': {
            'name': 'Vergleich A vs B',
            'instructions': """Vergleiche zwei Dinge, Methoden oder Ansätze miteinander.
- Stelle beide Optionen kurz vor
- Nenne Vorteile und Nachteile beider
- Verwende konkrete Beispiele
- Gib am Ende eine klare Empfehlung
- Erkläre für wen was besser geeignet ist"""
        },
        'top_list': {
            'name': 'Top 5/10 Liste',
            'instructions': """Erstelle eine Top-Liste zum Thema.
- Starte mit "Hier sind meine Top X..."
- Beginne mit dem schwächsten Punkt
- Steigere dich zum Highlight
- Erkläre jeden Punkt kurz
- Das Beste kommt am Schluss"""
        },
        'behind_scenes': {
            'name': 'Hinter den Kulissen',
            'instructions': """Gib einen exklusiven Blick hinter die Kulissen.
- Erzähle was normalerweise verborgen bleibt
- Teile Insider-Wissen
- Mache es persönlich und authentisch
- Verrate Geheimnisse oder überraschende Details
- Schaffe Nähe und Vertrauen"""
        },
        'challenge': {
            'name': 'Challenge-Format',
            'instructions': """Erstelle ein unterhaltsames Challenge-Format.
- Stelle die Challenge klar vor
- Erkläre die Regeln
- Beschreibe den Ablauf spannend
- Baue Spannung auf
- Fordere die Zuschauer zur Teilnahme auf"""
        },
        'controversial': {
            'name': 'Kontroverse Meinung',
            'instructions': """Präsentiere eine kontroverse, unerwartete Meinung zum Thema.
- Starte mit einer provokanten Aussage
- Erkläre deine ungewöhnliche Perspektive
- Begründe mit guten Argumenten
- Zeige warum die Mainstream-Meinung falsch sein könnte
- Fordere die Zuschauer zum Nachdenken auf"""
        },

        # ═══════════════════════════════════════════════════════════════
        # NEUE SKRIPTARTEN - KURZ BIS MITTEL
        # ═══════════════════════════════════════════════════════════════

        'pov': {
            'name': 'POV (Point of View)',
            'instructions': """Erstelle ein POV-Format (Point of View).
- Starte mit "POV: Du bist..." oder "POV: Du hast gerade..."
- Der Zuschauer IST die Hauptperson
- Beschreibe die Situation aus Ich-Perspektive des Zuschauers
- Schaffe eine immersive Erfahrung
- Kann lustig, relatable oder dramatisch sein"""
        },
        'unpopular_opinion': {
            'name': 'Unpopuläre Meinung',
            'instructions': """Teile eine unpopuläre aber begründete Meinung.
- Starte mit "Unpopuläre Meinung:" oder "Das wird nicht jedem gefallen, aber..."
- Präsentiere eine Meinung gegen den Mainstream
- Begründe sachlich und überzeugend
- Sei respektvoll aber direkt
- Fordere zur Diskussion auf"""
        },
        'mistakes': {
            'name': 'Häufige Fehler',
            'instructions': """Zeige die häufigsten Fehler die Menschen machen.
- Starte mit "Diese Fehler macht fast jeder bei..."
- Liste 3-5 konkrete Fehler auf
- Erkläre warum es ein Fehler ist
- Gib die richtige Alternative
- Schließe mit dem größten/wichtigsten Fehler"""
        },
        'secrets': {
            'name': 'Geheimtipps & Insider',
            'instructions': """Enthülle Insider-Wissen und Geheimtipps.
- Starte mit "Was dir niemand über X verrät..." oder "Insider-Wissen:"
- Teile exklusives, wenig bekanntes Wissen
- Erkläre warum das nicht jeder weiß
- Gib praktische Anwendungstipps
- Mache den Zuschauer zum "Insider" """
        },
        'reaction': {
            'name': 'Reaktions-Format',
            'instructions': """Erstelle ein Reaktions-Skript zu einem Thema.
- Starte mit deiner ersten spontanen Reaktion
- Kommentiere verschiedene Aspekte
- Zeige echte Emotionen (Überraschung, Begeisterung, Skepsis)
- Teile deine persönliche Meinung
- Schließe mit einem Fazit"""
        },
        'what_if': {
            'name': 'Was wäre wenn...',
            'instructions': """Erkunde ein hypothetisches Szenario.
- Starte mit "Was wäre, wenn..."
- Beschreibe das Szenario detailliert
- Gehe verschiedene Konsequenzen durch
- Nutze Fakten um die Theorie zu untermauern
- Schließe mit einer überraschenden Erkenntnis"""
        },
        'before_after': {
            'name': 'Vorher/Nachher',
            'instructions': """Zeige eine Transformation oder Veränderung.
- Beschreibe den Ausgangszustand ("Vorher war es so...")
- Erkläre was sich geändert hat
- Zeige den neuen Zustand ("Jetzt ist es so...")
- Betone den Unterschied dramatisch
- Teile die Lektion oder das Learning"""
        },
        'review': {
            'name': 'Ehrliche Bewertung',
            'instructions': """Erstelle eine ehrliche, ausgewogene Bewertung.
- Starte mit dem ersten Eindruck
- Nenne konkrete Vorteile
- Nenne ehrlich die Nachteile
- Vergleiche mit Alternativen
- Gib eine klare Empfehlung (für wen geeignet/nicht geeignet)"""
        },
        'prediction': {
            'name': 'Zukunfts-Prognose',
            'instructions': """Mache Vorhersagen für die Zukunft.
- Starte mit "In X Jahren wird..."
- Basiere auf aktuellen Trends
- Erkläre die Logik hinter der Prognose
- Zeige mögliche Szenarien auf
- Schließe mit einer konkreten Vorhersage"""
        },
        'rant': {
            'name': 'Meinungs-Rant',
            'instructions': """Lass Dampf ab zu einem Thema (konstruktiv).
- Starte energisch mit dem Problem
- Zeige echte Emotion und Leidenschaft
- Erkläre was dich stört und warum
- Bringe konkrete Beispiele
- Schließe mit einem Lösungsvorschlag oder Appell"""
        },
        'hot_take': {
            'name': 'Hot Take',
            'instructions': """Präsentiere einen heißen, spontanen Take.
- Starte direkt mit der provokanten Aussage
- Sei mutig und direkt
- Begründe kurz aber überzeugend
- Keine langen Erklärungen - auf den Punkt
- Fordere Reaktionen heraus"""
        },
        'this_or_that': {
            'name': 'Dies oder Das',
            'instructions': """Stelle zwei Optionen gegenüber und wähle.
- Präsentiere zwei Alternativen
- Gehe kurz auf beide ein
- Triff eine klare Entscheidung
- Begründe deine Wahl
- Frage die Zuschauer nach ihrer Meinung"""
        },
        'day_in_life': {
            'name': 'Ein Tag als...',
            'instructions': """Beschreibe einen typischen Tag aus einer bestimmten Perspektive.
- Starte mit dem Morgen/Beginn
- Gehe chronologisch durch den Tag
- Zeige interessante/überraschende Momente
- Teile Einblicke die man sonst nicht bekommt
- Schließe mit einem Fazit zum Tag"""
        },

        # ═══════════════════════════════════════════════════════════════
        # LÄNGERE FORMATE (5+ Minuten empfohlen)
        # ═══════════════════════════════════════════════════════════════

        'deep_dive': {
            'name': '🕐 Deep Dive (5+ Min)',
            'instructions': """Tauche tief in ein Thema ein - für längere Videos.
- Beginne mit einem spannenden Hook
- Gib einen Überblick was kommt
- Behandle das Thema von allen Seiten
- Nutze Beispiele, Daten, Geschichten
- Beantworte alle wichtigen Fragen
- Strukturiere in klare Abschnitte
- Schließe mit einem starken Fazit und Call-to-Action
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'documentary': {
            'name': '🕐 Mini-Dokumentation (5+ Min)',
            'instructions': """Erstelle ein dokumentarisches Skript - für längere Videos.
- Beginne mit einem fesselnden Einstieg
- Stelle das Thema/die Person/das Ereignis vor
- Erzähle die Geschichte chronologisch oder thematisch
- Nutze Fakten, Zitate und Hintergründe
- Baue dramatische Wendepunkte ein
- Zeige verschiedene Perspektiven
- Schließe mit der Bedeutung/dem Vermächtnis
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'storytime_long': {
            'name': '🕐 Ausführliche Storytime (5+ Min)',
            'instructions': """Erzähle eine ausführliche, persönliche Geschichte - für längere Videos.
- Setze die Szene: Wann, wo, wer war dabei?
- Baue die Charaktere auf
- Entwickle die Handlung mit Höhen und Tiefen
- Nutze Dialoge und Details
- Schaffe emotionale Momente
- Baue zu einem Höhepunkt auf
- Schließe mit der Lektion/dem Takeaway
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'case_study': {
            'name': '🕐 Fallstudie (5+ Min)',
            'instructions': """Analysiere einen konkreten Fall ausführlich - für längere Videos.
- Stelle den Fall/das Beispiel vor
- Erkläre den Hintergrund und Kontext
- Analysiere was passiert ist und warum
- Zeige die Ergebnisse/Konsequenzen
- Ziehe übertragbare Lehren daraus
- Gib konkrete Handlungsempfehlungen
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'complete_guide': {
            'name': '🕐 Kompletter Guide (7+ Min)',
            'instructions': """Erstelle einen umfassenden Leitfaden - für längere Videos.
- Beginne mit dem Nutzen: "Nach diesem Video wirst du..."
- Gib einen Überblick über die Themen
- Erkläre Grundlagen für Anfänger
- Gehe in fortgeschrittene Details
- Gib praktische Beispiele bei jedem Punkt
- Teile Pro-Tipps und Fallstricke
- Fasse die wichtigsten Punkte zusammen
- Gib nächste Schritte/Ressourcen
HINWEIS: Dieses Format ist für Videos ab 7 Minuten gedacht."""
        },
        'history': {
            'name': '🕐 Geschichte & Ursprung (5+ Min)',
            'instructions': """Erzähle die Geschichte/Historie eines Themas - für längere Videos.
- Starte mit einem interessanten Fakt aus der Geschichte
- Gehe chronologisch vor: Ursprung → Entwicklung → Heute
- Erzähle von wichtigen Personen und Ereignissen
- Zeige Wendepunkte und deren Auswirkungen
- Verbinde Vergangenheit mit der Gegenwart
- Schließe mit einem Ausblick in die Zukunft
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'interview_style': {
            'name': '🕐 Interview-Format (5+ Min)',
            'instructions': """Simuliere ein Interview mit Fragen und Antworten - für längere Videos.
- Beginne mit einer kurzen Vorstellung des Themas
- Stelle interessante, tiefgehende Fragen
- Beantworte sie ausführlich und persönlich
- Variiere zwischen einfachen und komplexen Fragen
- Baue auch kontroverse Fragen ein
- Schließe mit einer überraschenden letzten Frage
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'debate': {
            'name': '🕐 Pro & Contra Debatte (5+ Min)',
            'instructions': """Führe eine ausgewogene Debatte mit dir selbst - für längere Videos.
- Stelle das kontroverse Thema vor
- Präsentiere die Pro-Seite mit starken Argumenten
- Präsentiere die Contra-Seite mit starken Argumenten
- Gehe auf Gegenargumente ein
- Zeige Nuancen und Grauzonen
- Gib am Ende deine persönliche Einschätzung
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },
        'masterclass': {
            'name': '🕐 Masterclass (10+ Min)',
            'instructions': """Erstelle eine ausführliche Lehr-Session - für lange Videos.
- Beginne mit dem Lernziel und warum es wichtig ist
- Gib einen Überblick über den Inhalt
- Erkläre Konzepte von einfach zu komplex
- Nutze viele praktische Beispiele
- Gib Übungen oder Aufgaben
- Teile Experten-Tipps und häufige Fehler
- Wiederhole wichtige Punkte
- Schließe mit nächsten Schritten und Ressourcen
HINWEIS: Dieses Format ist für Videos ab 10 Minuten gedacht."""
        },
        'analysis': {
            'name': '🕐 Tiefgehende Analyse (7+ Min)',
            'instructions': """Analysiere ein Thema von allen Seiten - für längere Videos.
- Starte mit der zentralen Frage oder These
- Zerlege das Thema in Komponenten
- Analysiere jeden Aspekt systematisch
- Nutze Daten, Fakten und Beispiele
- Zeige Zusammenhänge und Muster
- Diskutiere verschiedene Interpretationen
- Schließe mit einer fundierten Schlussfolgerung
HINWEIS: Dieses Format ist für Videos ab 7 Minuten gedacht."""
        },
        'ultimate_list': {
            'name': '🕐 Ultimate Liste (7+ Min)',
            'instructions': """Erstelle eine umfangreiche, definitive Liste - für längere Videos.
- Kündige die Anzahl an: "Die X besten/wichtigsten..."
- Beginne mit den soliden Einträgen
- Steigere dich zu den Top-Einträgen
- Erkläre jeden Punkt ausführlich
- Gib Kontext und Beispiele
- Füge einen Bonus oder Geheimtipp hinzu
- Die Nummer 1 soll beeindrucken
HINWEIS: Dieses Format ist für Videos ab 7 Minuten gedacht."""
        },
        'journey': {
            'name': '🕐 Meine Reise/Entwicklung (5+ Min)',
            'instructions': """Erzähle von einer persönlichen Entwicklung - für längere Videos.
- Starte mit dem Ausgangspunkt: "Wo ich angefangen habe..."
- Zeige die ersten Schritte und Herausforderungen
- Beschreibe wichtige Wendepunkte
- Teile Fehler und was du daraus gelernt hast
- Zeige den aktuellen Stand
- Gib Tipps für andere auf dem gleichen Weg
HINWEIS: Dieses Format ist für Videos ab 5 Minuten gedacht."""
        },

        # ═══════════════════════════════════════════════════════════════
        # NEUE TREND-FORMATE (2025)
        # ═══════════════════════════════════════════════════════════════

        'storytime_short': {
            'name': 'Mini Storytime',
            'instructions': """Erzähle eine kurze, packende persönliche Geschichte.
- Starte direkt mitten in der Action ("Also, da war ich...")
- Halte es kurz aber fesselnd (30-90 Sekunden)
- Eine klare Pointe oder Überraschung am Ende
- Persönlich und relatable
- Emotionen zeigen - Aufregung, Schock, Freude"""
        },
        'get_ready_with_me': {
            'name': 'GRWM (Get Ready With Me)',
            'instructions': """Erstelle ein "Get Ready With Me" Format mit Themen-Fokus.
- Starte mit "Komm, mach dich mit mir fertig für..." oder "GRWM während ich dir erzähle..."
- Verbinde Routine-Beschreibung mit interessantem Content
- Teile Gedanken, Tipps oder eine Geschichte nebenbei
- Halte es locker und gesprächig
- Schaffe eine intime, persönliche Atmosphäre"""
        },
        'explain_like_5': {
            'name': 'Erkläre wie für 5-Jährige',
            'instructions': """Erkläre ein komplexes Thema super einfach.
- Starte mit "Stell dir vor..." oder "Okay, also..."
- Verwende einfache Analogien und Vergleiche
- Keine Fachbegriffe - nur Alltagssprache
- Mache es bildhaft und vorstellbar
- Am Ende: "Siehst du? So einfach ist das!" """
        },
        'red_flags': {
            'name': 'Red Flags / Warnsignale',
            'instructions': """Zeige Warnsignale und Red Flags auf.
- Starte mit "Red Flags bei..." oder "Wenn das passiert, RENN!"
- Liste klare, konkrete Warnsignale auf
- Erkläre kurz warum es ein Problem ist
- Gib praktische Tipps zum Erkennen
- Schließe mit dem wichtigsten Red Flag"""
        },
        'green_flags': {
            'name': 'Green Flags / Positive Zeichen',
            'instructions': """Zeige positive Zeichen und Green Flags.
- Starte mit "Green Flags die du nicht ignorieren solltest..."
- Liste positive Signale und gute Zeichen auf
- Erkläre warum diese Dinge gut sind
- Mache es ermutigend und positiv
- Schließe mit dem besten Green Flag"""
        },
        'things_i_learned': {
            'name': 'X Dinge die ich gelernt habe',
            'instructions': """Teile wichtige Lektionen die du gelernt hast.
- Starte mit "X Dinge die ich gelernt habe über/bei..."
- Nummeriere jede Lektion klar durch
- Teile persönliche Erfahrungen dazu
- Mache es praktisch und umsetzbar
- Die wichtigste Lektion kommt am Ende"""
        },
        'hack': {
            'name': 'Life Hack / Cleverer Trick',
            'instructions': """Präsentiere einen cleveren Hack oder Trick.
- Starte mit "Dieser Hack wird alles verändern..." oder "Warum weiß das nicht jeder?"
- Erkläre das Problem kurz
- Zeige die clevere Lösung
- Betone wie einfach es ist
- "Du kannst mir später danken!" """
        },
        'ranking': {
            'name': 'Bewertungs-Ranking',
            'instructions': """Ranke und bewerte verschiedene Optionen.
- Starte mit "Ich ranke heute..." oder "Von schlecht bis genial..."
- Gehe durch jede Option mit Bewertung
- Begründe deine Einschätzung kurz
- Sei ehrlich und unterhaltsam
- Die beste/schlechteste Option dramatisch präsentieren"""
        },
        'nostalgia': {
            'name': 'Nostalgie-Trip',
            'instructions': """Nimm die Zuschauer auf eine Nostalgie-Reise mit.
- Starte mit "Erinnert sich noch jemand an..." oder "Nur echte OGs kennen..."
- Wecke Erinnerungen an früher
- Beschreibe Details die Emotionen auslösen
- Verbinde Vergangenheit mit Gegenwart
- Schaffe ein Gefühl von "die guten alten Zeiten" """
        },
        'recap': {
            'name': 'Schnelles Recap',
            'instructions': """Fasse etwas schnell und unterhaltsam zusammen.
- Starte mit "Hier ist alles was du wissen musst über..."
- Halte es extrem kompakt
- Nur die wichtigsten Punkte
- Schnelles Tempo, keine Umschweife
- "Das war's - jetzt weißt du Bescheid!" """
        },
        'things_nobody_tells': {
            'name': 'Dinge die dir niemand sagt',
            'instructions': """Enthülle Wahrheiten die normalerweise verschwiegen werden.
- Starte mit "Was dir niemand über X sagt..." oder "Die unbequeme Wahrheit..."
- Teile ehrliche, ungeschönte Einsichten
- Erkläre warum das normalerweise verschwiegen wird
- Sei authentisch und direkt
- Schließe mit der wichtigsten Erkenntnis"""
        },
        'motivation_quote': {
            'name': 'Motivations-Zitat',
            'instructions': """Präsentiere ein kraftvolles Zitat mit Geschichte.
- Starte mit dem Zitat oder der Kernaussage
- Erzähle die Geschichte dahinter
- Erkläre was es für dich bedeutet
- Verbinde es mit dem Leben der Zuschauer
- Schließe mit einem Call-to-Action"""
        },
        'trend_check': {
            'name': 'Trend-Check',
            'instructions': """Analysiere und erkläre einen aktuellen Trend.
- Starte mit "Alle reden gerade über..." oder "Dieser Trend ist überall..."
- Erkläre was der Trend ist
- Zeige woher er kommt
- Gib deine Meinung dazu
- "Ist der Hype berechtigt?" - Fazit geben"""
        },
        'asmr_style': {
            'name': 'ASMR-Style (Ruhig & Entspannt)',
            'instructions': """Erstelle einen ruhigen, entspannenden Text.
- Sprich langsam und sanft
- Verwende beruhigende, weiche Sprache
- Mache Pausen (im Text angedeutet mit "...")
- Schaffe eine meditative Atmosphäre
- Der Content soll entspannen und beruhigen"""
        },
        'celebrity_bio': {
            'name': 'Promi-/Personen-Biografie',
            'instructions': """Erzähle die Geschichte einer bekannten Person.
- Starte mit einem überraschenden Fakt über die Person
- Erzähle den Werdegang kompakt aber fesselnd
- Hebe Wendepunkte und Besonderheiten hervor
- Zeige was die Person besonders macht
- Schließe mit ihrem Vermächtnis oder aktuellen Status"""
        },
        'science_explained': {
            'name': 'Wissenschaft einfach erklärt',
            'instructions': """Erkläre ein wissenschaftliches Thema verständlich.
- Starte mit einer faszinierenden Frage
- Erkläre die Wissenschaft dahinter einfach
- Verwende Analogien und Beispiele
- Mache es spannend, nicht trocken
- "Mind = Blown" Momente einbauen"""
        },
        'money_tip': {
            'name': 'Finanz-/Geld-Tipp',
            'instructions': """Teile einen wertvollen Finanztipp.
- Starte mit dem Nutzen: "So sparst du..." oder "Dieser Trick hat mir X€ gespart..."
- Erkläre den Tipp klar und praktisch
- Zeige konkrete Zahlen oder Beispiele
- Warne vor häufigen Fehlern
- Mache es sofort umsetzbar"""
        },
        'satisfying': {
            'name': 'Satisfying Content',
            'instructions': """Erstelle einen befriedigenden, entspannenden Text.
- Beschreibe befriedigende Prozesse oder Ergebnisse
- Verwende beschreibende, sensorische Sprache
- Schaffe ein Gefühl von Ordnung und Perfektion
- Baue auf zum befriedigenden Moment
- "Ahh, das ist so gut!" - Momente erzeugen"""
        },
        'tutorial_quick': {
            'name': 'Schnelles Mini-Tutorial',
            'instructions': """Erkläre etwas schnell und praktisch.
- Starte direkt: "So machst du..." oder "In 60 Sekunden lernst du..."
- Halte jeden Schritt ultra-kurz
- Fokus auf das Wesentliche
- Keine Abschweifungen
- "Fertig! So einfach ist das." """
        },
        'conspiracy_debunk': {
            'name': 'Verschwörungstheorie hinterfragen',
            'instructions': """Hinterfrage eine Verschwörungstheorie kritisch.
- Starte mit der Theorie: "Viele glauben, dass..."
- Erkläre warum Menschen das glauben
- Zeige die Fakten und Gegenbeweise
- Bleibe respektvoll aber klar
- Schließe mit der wahrscheinlichsten Erklärung"""
        }
    }

    # === TONE PROMPTS ===
    TONE_PROMPTS = {
        'professional': {
            'name': 'Professionell & seriös',
            'instructions': """Der Ton ist professionell und seriös.
- Verwende klare, präzise Sprache
- Bleibe sachlich und fundiert
- Wirke kompetent und vertrauenswürdig
- Keine Slang-Ausdrücke oder Umgangssprache
- Halte einen respektvollen, geschäftsmäßigen Ton"""
        },
        'casual': {
            'name': 'Locker & entspannt',
            'instructions': """Der Ton ist locker und entspannt.
- Sprich wie mit einem guten Freund
- Verwende Umgangssprache
- Sei authentisch und nahbar
- Nutze lockere Ausdrücke und Phrasen
- Halte es natürlich und ungezwungen"""
        },
        'humorous': {
            'name': 'Humorvoll & witzig',
            'instructions': """Der Ton ist humorvoll und witzig.
- Baue Witze und lustige Bemerkungen ein
- Verwende Ironie und Übertreibungen
- Halte es unterhaltsam und leicht
- Sei nicht zu ernst
- Bringe den Zuschauer zum Lachen oder Schmunzeln"""
        },
        'inspiring': {
            'name': 'Inspirierend & motivierend',
            'instructions': """Der Ton ist inspirierend und erhebend.
- Motiviere und ermutige den Zuschauer
- Teile positive Botschaften
- Zeige Möglichkeiten und Potenzial auf
- Verwende kraftvolle, aufbauende Sprache
- Hinterlasse ein Gefühl der Hoffnung und Motivation"""
        },
        'neutral': {
            'name': 'Sachlich & informativ',
            'instructions': """Der Ton ist neutral und informativ.
- Bleibe objektiv und faktisch
- Präsentiere Informationen ohne Wertung
- Vermeide emotionale Sprache
- Sei klar und verständlich
- Fokussiere auf die Fakten"""
        },
        'motivating': {
            'name': 'Motivierend & aufbauend',
            'instructions': """Der Ton ist stark motivierend und aufbauend.
- Pushe den Zuschauer zu Aktionen
- Verwende energische, dynamische Sprache
- Schaffe ein "Du kannst das!"-Gefühl
- Betone Stärken und Potenzial
- Rufe zu mutigen Entscheidungen auf"""
        },
        'provocative': {
            'name': 'Provokant & herausfordernd',
            'instructions': """Der Ton ist provokant und herausfordernd.
- Stelle unbequeme Fragen
- Hinterfrage den Status Quo
- Sei direkt und konfrontativ (aber respektvoll)
- Rege zum Nachdenken an
- Fordere etablierte Meinungen heraus"""
        },
        'emotional': {
            'name': 'Emotional & berührend',
            'instructions': """Der Ton ist emotional und berührend.
- Schaffe emotionale Verbindung
- Sprich Gefühle direkt an
- Erzähle mit Herz und Seele
- Sei verletzlich und authentisch
- Berühre die Zuschauer auf einer tiefen Ebene"""
        },
        'dramatic': {
            'name': 'Dramatisch & spannungsgeladen',
            'instructions': """Der Ton ist dramatisch und spannungsgeladen.
- Baue Spannung und Drama auf
- Verwende dramatische Pausen (in der Sprache angedeutet)
- Schaffe Cliffhanger-Momente
- Steigere die Intensität
- Halte die Zuschauer am Rand ihres Sitzes"""
        }
    }

    # === TARGET AUDIENCE PROMPTS ===
    TARGET_AUDIENCE_PROMPTS = {
        'beginner': {
            'name': 'Anfänger',
            'instructions': """Die Zielgruppe sind absolute Anfänger.
- Erkläre alles von Grund auf
- Verwende einfache, verständliche Sprache
- Vermeide Fachbegriffe oder erkläre sie
- Gehe Schritt für Schritt vor
- Mache keine Annahmen über Vorwissen"""
        },
        'intermediate': {
            'name': 'Fortgeschrittene',
            'instructions': """Die Zielgruppe sind Fortgeschrittene.
- Setze Grundwissen voraus
- Gehe auf tiefere Details ein
- Teile fortgeschrittene Tipps
- Verwende Fachbegriffe wo angebracht
- Biete Mehrwert über Basics hinaus"""
        },
        'expert': {
            'name': 'Experten',
            'instructions': """Die Zielgruppe sind Experten.
- Setze umfangreiches Vorwissen voraus
- Fokussiere auf Nuancen und Feinheiten
- Diskutiere Kontroversen und Edge Cases
- Verwende Fachsprache selbstverständlich
- Biete tiefe Einblicke und neue Perspektiven"""
        },
        'general': {
            'name': 'Allgemein',
            'instructions': """Die Zielgruppe ist gemischt/allgemein.
- Finde eine Balance zwischen einfach und fundiert
- Erkläre Fachbegriffe kurz bei Bedarf
- Sprich ein breites Publikum an
- Halte es zugänglich aber nicht zu oberflächlich
- Biete für jeden etwas Interessantes"""
        },
        'young': {
            'name': 'Kinder/Jugendliche',
            'instructions': """Die Zielgruppe sind jüngere Menschen (Kinder/Jugendliche).
- Verwende einfache, lebhafte Sprache
- Sei besonders unterhaltsam und dynamisch
- Nutze Trends und Referenzen die Jüngere kennen
- Halte es kurz und abwechslungsreich
- Vermeide komplizierte Konzepte"""
        }
    }

    # === PLATFORM PROMPTS ===
    PLATFORM_PROMPTS = {
        'youtube': {
            'name': 'YouTube',
            'instructions': """Optimiert für YouTube.
- Beginne mit einem starken Hook in den ersten 5 Sekunden
- Struktur: Hook → Inhalt → Call-to-Action
- Nutze "Wenn du mehr erfahren willst, bleib dran..."
- Ermutige zu Likes, Kommentaren, Abos (am Ende)
- Längere, ausführlichere Formate sind okay"""
        },
        'tiktok': {
            'name': 'TikTok',
            'instructions': """Optimiert für TikTok.
- SOFORT mit dem Interessantesten starten (Hook in 1 Sekunde!)
- Sehr schnelles Tempo, keine langen Pausen
- Trend-Sprache und aktuelle Phrasen verwenden
- Kurz, knackig, auf den Punkt
- Überraschende Wendungen einbauen
- Mit einem CTA enden ("Folg mir für mehr!")"""
        },
        'instagram': {
            'name': 'Instagram Reels',
            'instructions': """Optimiert für Instagram Reels.
- Visuell ansprechend beschreiben
- Trendy und ästhetisch im Stil
- Emotionale Hooks die zum Teilen animieren
- Lifestyle-orientiert wo möglich
- "Save this for later" oder "Share with a friend" CTAs"""
        },
        'linkedin': {
            'name': 'LinkedIn',
            'instructions': """Optimiert für LinkedIn.
- Professioneller, Business-fokussierter Ton
- Expertise und Thought Leadership zeigen
- Learnings und Insights teilen
- Berufliche Relevanz hervorheben
- Mit einer Frage oder Diskussionsaufforderung enden"""
        },
        'facebook': {
            'name': 'Facebook',
            'instructions': """Optimiert für Facebook.
- Storytelling-fokussiert
- Breites, diverses Publikum ansprechen
- Emotional und relatable sein
- Community-Gefühl schaffen
- Zum Teilen und Kommentieren animieren"""
        }
    }

    def __init__(self, user, settings=None):
        """
        Initialisiert den VSkript Service.

        Args:
            user: Django User Objekt mit API-Keys
            settings: Optional Settings Objekt (z.B. BlogPrepSettings)
        """
        self.user = user
        self.settings = settings

        # VSkript verwendet ausschließlich OpenAI-Modelle
        self.provider = 'openai'
        self.model = getattr(settings, 'ai_model', 'gpt-4o') if settings else 'gpt-4o'

        # Clients initialisieren
        self._init_clients()

    def _init_clients(self):
        """Initialisiert die API-Clients basierend auf Provider"""
        self.openai_client = None
        self.gemini_model = None
        self.anthropic_client = None

        if self.provider == 'openai' and OPENAI_AVAILABLE:
            api_key = getattr(self.user, 'openai_api_key', None)
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        elif self.provider == 'gemini' and GENAI_AVAILABLE:
            api_key = getattr(self.user, 'gemini_api_key', None)
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel(self.model)
        elif self.provider == 'anthropic' and ANTHROPIC_AVAILABLE:
            api_key = getattr(self.user, 'anthropic_api_key', None)
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 3000, temperature: float = 0.8) -> Dict:
        """Ruft das LLM auf basierend auf dem konfigurierten Provider."""
        start_time = time.time()

        try:
            if self.provider == 'openai' and self.openai_client:
                # O-Modelle (o1, o3, o4) und Thinking-Varianten sind Reasoning-Modelle
                is_reasoning_model = (
                    self.model.startswith('o1') or
                    self.model.startswith('o3') or
                    self.model.startswith('o4') or
                    'thinking' in self.model.lower()
                )

                # GPT-5 Serie verwendet max_completion_tokens
                is_gpt5_model = self.model.startswith('gpt-5')

                if is_reasoning_model:
                    # Reasoning-Modelle: max_completion_tokens, keine temperature, kein system prompt
                    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                    response = self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "user", "content": combined_prompt}
                        ],
                        max_completion_tokens=max_tokens
                    )
                elif is_gpt5_model:
                    # GPT-5 Serie: max_completion_tokens mit temperature und system prompt
                    response = self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_completion_tokens=max_tokens,
                        temperature=temperature
                    )
                else:
                    # Legacy-Modelle (GPT-4o, GPT-4.1, etc.): max_tokens
                    response = self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                content = response.choices[0].message.content.strip()
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0

            elif self.provider == 'gemini' and self.gemini_model:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                response = self.gemini_model.generate_content(
                    full_prompt,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature
                    )
                )
                content = response.text.strip()
                tokens_in = 0
                tokens_out = 0

            elif self.provider == 'anthropic' and self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = response.content[0].text.strip()
                tokens_in = response.usage.input_tokens if response.usage else 0
                tokens_out = response.usage.output_tokens if response.usage else 0

            else:
                return {
                    'success': False,
                    'error': f'API-Key für {self.provider} nicht konfiguriert'
                }

            duration = time.time() - start_time

            return {
                'success': True,
                'content': content,
                'tokens_input': tokens_in,
                'tokens_output': tokens_out,
                'duration': duration,
                'provider': self.provider,
                'model': self.model
            }

        except Exception as e:
            logger.error(f"LLM call error ({self.provider}): {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _clean_script(self, script: str) -> str:
        """Bereinigt das Skript von unerwünschten Elementen"""
        # Entferne Regieanweisungen
        script = re.sub(r'\[.*?\]', '', script)  # [Anweisungen]
        script = re.sub(r'\(.*?\)', '', script)  # (Anweisungen)
        script = re.sub(r'^[A-Z]+:', '', script, flags=re.MULTILINE)  # ROLLE:
        script = re.sub(r'^\*.*?\*$', '', script, flags=re.MULTILINE)  # *Anweisungen*

        # Bereinige Formatierung
        script = re.sub(r'\n{3,}', '\n\n', script)  # Max 2 Zeilenumbrüche
        script = script.strip()

        return script

    def generate_script(
        self,
        keyword: str,
        description: str = '',
        script_type: str = 'interesting_facts',
        tone: str = 'casual',
        target_audience: str = 'general',
        platform: str = 'youtube',
        duration_minutes: float = 1.0,
        ai_model: str = None
    ) -> Dict:
        """
        Generiert ein Videoskript basierend auf allen Parametern.

        Args:
            keyword: Das Thema/Keyword
            description: Optionale zusätzliche Beschreibung
            script_type: Art des Skripts
            tone: Tonalität
            target_audience: Zielgruppe
            platform: Video-Plattform
            duration_minutes: Gewünschte Länge in Minuten
            ai_model: OpenAI Modell (optional, überschreibt Default)

        Returns:
            Dict mit success, script, word_count, etc.
        """
        # Modell überschreiben falls angegeben
        if ai_model:
            self.model = ai_model
        target_words = int(duration_minutes * self.WORDS_PER_MINUTE)

        # Hole alle Konfigurationen
        script_config = self.SCRIPT_TYPE_PROMPTS.get(script_type, self.SCRIPT_TYPE_PROMPTS['interesting_facts'])
        tone_config = self.TONE_PROMPTS.get(tone, self.TONE_PROMPTS['casual'])
        audience_config = self.TARGET_AUDIENCE_PROMPTS.get(target_audience, self.TARGET_AUDIENCE_PROMPTS['general'])
        platform_config = self.PLATFORM_PROMPTS.get(platform, self.PLATFORM_PROMPTS['youtube'])

        # Baue System-Prompt
        system_prompt = f"""Du bist ein erfahrener Video-Skript-Autor für Social Media und Online-Videos.
Du schreibst NUR den gesprochenen Text für Videos - KEINE Regieanweisungen, KEINE Rollenbezeichnungen, KEINE Szenenanweisungen.
Der Text soll natürlich klingen, als würde jemand frei und authentisch sprechen.

WICHTIG: Verwende IMMER die Du-Form (informell).

═══════════════════════════════════════════════════════════════════
SKRIPT-ART: {script_config['name']}
═══════════════════════════════════════════════════════════════════
{script_config['instructions']}

═══════════════════════════════════════════════════════════════════
TONALITÄT: {tone_config['name']}
═══════════════════════════════════════════════════════════════════
{tone_config['instructions']}

═══════════════════════════════════════════════════════════════════
ZIELGRUPPE: {audience_config['name']}
═══════════════════════════════════════════════════════════════════
{audience_config['instructions']}

═══════════════════════════════════════════════════════════════════
PLATTFORM: {platform_config['name']}
═══════════════════════════════════════════════════════════════════
{platform_config['instructions']}

═══════════════════════════════════════════════════════════════════
FORMATIERUNG (SEHR WICHTIG!):
═══════════════════════════════════════════════════════════════════
- Strukturiere den Text mit VIELEN Absätzen (Leerzeilen zwischen Abschnitten)
- Jeder Gedanke/Punkt sollte ein eigener Absatz sein (2-4 Sätze max)
- Bei Aufzählungen: Jeder Punkt in einer neuen Zeile
- Nach jedem Hook, Übergang oder Themenwechsel: Neuer Absatz
- Der Text muss optisch gut lesbar und übersichtlich sein
- KEINE langen Textblöcke - lieber mehr kürzere Absätze
- Verwende Zeilenumbrüche großzügig für bessere Lesbarkeit"""

        # Baue User-Prompt
        description_part = f"\n\nZusätzliche Details:\n{description}" if description else ""

        user_prompt = f"""Erstelle ein "{script_config['name']}" Video-Skript zum Thema:

THEMA/KEYWORD: {keyword}{description_part}

═══════════════════════════════════════════════════════════════════
ANFORDERUNGEN:
═══════════════════════════════════════════════════════════════════
- Länge: ca. {duration_minutes} Minuten ({target_words} Wörter)
- NUR gesprochener Text
- KEINE Regieanweisungen wie "[Sprecher]", "(Pause)", "[Schnitt]", etc.
- KEINE Rollenbezeichnungen
- IMMER "du"-Form verwenden
- Natürlicher, fließender Sprachstil

═══════════════════════════════════════════════════════════════════
FORMATIERUNG (ZWINGEND EINHALTEN!):
═══════════════════════════════════════════════════════════════════
- Nach JEDEM Gedanken/Punkt: Leerzeile einfügen
- Maximal 2-3 Sätze pro Absatz
- Bei Listen/Aufzählungen: Jeder Punkt in eigener Zeile
- Text muss gut strukturiert und übersichtlich sein
- VIELE kurze Absätze statt wenige lange

Das Skript beginnt DIREKT mit dem gesprochenen Text.
Schreibe ca. {target_words} Wörter mit guter Absatzstruktur."""

        # Generiere Skript
        result = self._call_llm(system_prompt, user_prompt, max_tokens=4000, temperature=0.85)

        if result['success']:
            script = self._clean_script(result['content'])
            word_count = len(script.split())
            estimated_duration = round(word_count / self.WORDS_PER_MINUTE, 1)

            return {
                'success': True,
                'script': script,
                'word_count': word_count,
                'estimated_duration_minutes': estimated_duration,
                'tokens_input': result.get('tokens_input', 0),
                'tokens_output': result.get('tokens_output', 0),
                'duration': result.get('duration', 0),
                'provider': result.get('provider', self.provider),
                'model': result.get('model', self.model)
            }

        return result

    def get_available_options(self) -> Dict:
        """Gibt alle verfügbaren Optionen zurück"""
        return {
            'script_types': [
                {'value': key, 'label': val['name']}
                for key, val in self.SCRIPT_TYPE_PROMPTS.items()
            ],
            'tones': [
                {'value': key, 'label': val['name']}
                for key, val in self.TONE_PROMPTS.items()
            ],
            'target_audiences': [
                {'value': key, 'label': val['name']}
                for key, val in self.TARGET_AUDIENCE_PROMPTS.items()
            ],
            'platforms': [
                {'value': key, 'label': val['name']}
                for key, val in self.PLATFORM_PROMPTS.items()
            ],
            'durations': [
                {'value': 0.25, 'label': '15 Sekunden'},
                {'value': 0.5, 'label': '30 Sekunden'},
                {'value': 1.0, 'label': '1 Minute'},
                {'value': 2.0, 'label': '2 Minuten'},
                {'value': 3.0, 'label': '3 Minuten'},
                {'value': 5.0, 'label': '5 Minuten'},
                {'value': 7.0, 'label': '7 Minuten'},
                {'value': 10.0, 'label': '10 Minuten'},
            ]
        }
