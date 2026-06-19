"""
GLM-5.2-Client für den Radiosender (Z.AI Coding Plan, Abo — keine Token-Kosten).

Folgt exakt dem Muster aus research/services/council.py und
backloom/services/bot_runner.py:
- Endpoint: https://api.z.ai/api/coding/paas/v4 (OpenAI-kompatibel)
- Key: CustomUser.zhipu_api_key (verschlüsselt), bevorzugt User 'taras'
- Modell: glm-5.2 (Fallback glm-4.6)

Wird für ALLE KI-Agenten-Aufgaben des Senders genutzt: MusicGen-Prompts,
News-Zusammenfassungen, Gute-Nacht-Geschichten, Programmplanung.
"""
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

ZAI_BASE_URL = 'https://api.z.ai/api/coding/paas/v4'
GLM_MODEL_PRIMARY = 'glm-5.2'
GLM_MODEL_FALLBACK = 'glm-4.6'

DEFAULT_MUSIC_SYSTEM = (
    'You are the music director of a modern online radio station for the '
    'German brand Naturmacher (nature, crafting, family). You program '
    'CONTEMPORARY music across a wide range of modern genres — e.g. modern '
    'pop instrumentals, electronic, house, chillhop, lo-fi hip hop, '
    'future bass, synthwave, indie, cinematic, ambient — fitting the given '
    'mood. This is a general modern station, NOT only children songs. '
    'You write concise English prompts for the MusicGen model. Each prompt '
    'describes genre, instrumentation, mood and tempo, is INSTRUMENTAL '
    '(no vocals, since MusicGen cannot sing real lyrics) and contains NO '
    'copyrighted artist or song names. Keep prompts under 30 words.'
)


def _rubrik(key):
    """Lädt eine aktive Rubrik aus der DB (None, falls keine/Fehler)."""
    try:
        from .models import Rubrik
        return Rubrik.objects.filter(key=key, is_active=True).first()
    except Exception:
        return None


def _rubrik_system(key, fallback):
    r = _rubrik(key)
    return r.system_prompt if (r and r.system_prompt) else fallback


def _rubrik_prompts(key, fb_system, fb_task):
    r = _rubrik(key)
    if r:
        return (r.system_prompt or fb_system), (r.task_prompt or fb_task)
    return fb_system, fb_task


def get_glm_key():
    """Lädt den GLM/Zhipu-Key aus den Workloom-API-Einstellungen (CustomUser)."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Bevorzugt 'taras' (siehe Memory: Keys liegen an diesem User)
    user = User.objects.filter(username='taras').first()
    if user and user.zhipu_api_key:
        return user.zhipu_api_key

    # Fallback: irgendein User mit gesetztem Key
    user = User.objects.exclude(zhipu_api_key__isnull=True).exclude(zhipu_api_key='').first()
    if user and user.zhipu_api_key:
        return user.zhipu_api_key

    raise RuntimeError('Kein zhipu_api_key in den API-Einstellungen gefunden (GLM 5.2).')


# Rubriken OHNE Eingangs-Ankündigung (Jingle ist selbst eine Kennung; ein Spot
# soll sich nicht als "Marken-Spot" ankündigen; Musik/Effekt sind keine Sprache)
ANNOUNCE_EXCLUDE = {'jingle', 'ad', 'music', 'song', 'effekt'}


def announce_instruction(kind):
    """GLM-Anweisung: Beitrag mit kurzer Rubrik-Ankündigung beginnen ('' wenn unpassend).
    So weiß der Hörer sofort, welche Rubrik gerade läuft."""
    if kind in ANNOUNCE_EXCLUDE:
        return ''
    r = _rubrik(kind)
    label = (r.label if r else '') or ''
    if not label:
        return ''
    return (f'Beginne den Beitrag mit einer kurzen, freundlichen Ankündigung der Rubrik '
            f'„{label}" in einem einzigen kurzen Satz, damit die Hörer sofort wissen, was läuft '
            f'(variiere die Formulierung, z. B. „Und jetzt: {label}!" oder „Zeit für {label}."). '
            f'Falls der Beitrag ein Dialog-Format mit Sprecherzeilen hat, übernimmt der erste '
            f'Sprecher diese Ankündigung in seiner ersten Zeile.')


TOPIC_MEMORY_MAX = 120  # maximal gemerkte Themen je Rubrik (FIFO)


def avoid_topics_instruction(kind, limit=40):
    """Themen-Gedächtnis: bereits vergebene Themen dieser Rubrik (editierbares
    Feld Rubrik.topic_memory, eine Zeile = ein Thema) als GLM-Anweisung, ein
    DEUTLICH anderes Thema zu wählen ('' wenn leer)."""
    r = _rubrik(kind)
    if not r:
        return ''
    lines = [ln.strip() for ln in (r.topic_memory or '').splitlines() if ln.strip()]
    if not lines:
        return ''
    recent = lines[-limit:]
    return ('Diese Themen gab es in der Rubrik BEREITS – wähle ein DEUTLICH anderes, '
            'neues Thema (keine inhaltliche Wiederholung, auch nicht umformuliert): '
            + '; '.join(t[:60] for t in recent) + '.')


def remember_topic(kind, title):
    """Trägt ein vergebenes Thema ins editierbare Themen-Gedächtnis der Rubrik ein
    (Duplikate werden ignoriert, älteste Einträge fallen bei Überlauf heraus)."""
    title = (title or '').strip()
    if not title:
        return
    try:
        from .models import Rubrik
        r = Rubrik.objects.filter(key=kind).first()
        if not r:
            return
        lines = [ln.strip() for ln in (r.topic_memory or '').splitlines() if ln.strip()]
        if title.lower() in {ln.lower() for ln in lines}:
            return
        lines.append(title)
        r.topic_memory = '\n'.join(lines[-TOPIC_MEMORY_MAX:])
        r.save(update_fields=['topic_memory'])
    except Exception:
        pass


def make_title(text, max_words=7):
    """Kurzer, prägnanter deutscher Titel aus einem Text/Liedtext (GLM 5.2).
    Gibt '' zurück, wenn kein Text oder bei Fehler."""
    snippet = (text or '').strip()
    if not snippet:
        return ''
    snippet = snippet[:1500]
    try:
        t = glm_chat(
            f'Erstelle einen kurzen, prägnanten deutschen Titel (höchstens {max_words} Wörter) '
            f'für den folgenden Radio-Beitrag. Antworte AUSSCHLIESSLICH mit dem Titel – ohne '
            f'Anführungszeichen, ohne Punkt am Ende, ohne Vorrede:\n\n"""\n{snippet}\n"""',
            system='Du bist ein Radio-Redakteur und vergibst knappe, treffende Titel.',
            max_tokens=40)
        t = (t or '').strip().strip('"„“”').splitlines()[0].strip()
        # evtl. Marker-Zeilen ([verse] etc.) meiden
        if t[:1] in '[(':
            return ''
        return t[:80]
    except Exception:
        return ''


def _strip_cjk(text):
    """Entfernt versehentlich eingestreute CJK-Zeichen (Chinesisch/Japanisch/
    Koreanisch) aus dem GLM-Text — GLM ist ein chinesisches Modell und mischt
    sporadisch CJK-Zeichen in deutschen Text, was beim Vorlesen stört."""
    if not text:
        return text
    import re
    cleaned = re.sub(
        r'[　-〿぀-ヿㇰ-ㇿ㐀-䶿一-鿿가-힯＀-￯]',
        '', text)
    cleaned = re.sub(r'\s+([,.!?;:])', r'\1', cleaned)   # Leerzeichen vor Satzzeichen weg
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)          # doppelte Leerzeichen glätten
    return cleaned.strip()


def glm_chat(prompt, system=None, max_tokens=4000, timeout=120, json_mode=False):
    """
    Einzelner GLM-5.2-Call. Gibt den Antworttext (str) zurück.
    Bei json_mode=True wird das Modell angewiesen, reines JSON zu liefern.
    """
    api_key = get_glm_key()
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})

    payload = {
        'model': GLM_MODEL_PRIMARY,
        'messages': messages,
        'max_tokens': max_tokens,
        'thinking': {'type': 'disabled'},  # GLM 5.2: kein Reasoning in den Antworttext
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}

    last_err = None
    for model in (GLM_MODEL_PRIMARY, GLM_MODEL_FALLBACK):
        payload['model'] = model
        try:
            req = urllib.request.Request(
                f'{ZAI_BASE_URL}/chat/completions',
                method='POST',
                data=json.dumps(payload).encode(),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}',
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read())
            choices = body.get('choices') or []
            if not choices:
                raise RuntimeError(f'GLM-Antwort ohne choices: {str(body)[:200]}')
            msg = choices[0].get('message', {}) or {}
            text = (msg.get('content') or '').strip()
            if not text:
                text = (msg.get('reasoning_content') or msg.get('reasoning') or '').strip()
            return _strip_cjk(text)
        except Exception as e:
            last_err = e
            logger.warning(f'GLM-Call mit {model} fehlgeschlagen: {e}')
            continue
    raise RuntimeError(f'GLM 5.2 nicht erreichbar: {last_err}')


def generate_music_prompts(mood, count=10):
    """
    Lässt GLM 5.2 eine Liste kreativer MusicGen-Prompts (englisch) erzeugen.
    Gibt eine Liste von dicts zurück: [{'title': ..., 'prompt': ...}, ...].
    """
    system = _rubrik_system('music', DEFAULT_MUSIC_SYSTEM)
    user = (
        f'Create {count} distinct instrumental music prompts for the mood: '
        f'"{mood}". Return ONLY a JSON object of the form '
        '{"tracks": [{"title": "<short German title>", "prompt": "<English MusicGen prompt>"}, ...]}.'
    )
    raw = glm_chat(user, system=system, json_mode=True, max_tokens=2000)
    data = _parse_json(raw)
    tracks = data.get('tracks') if isinstance(data, dict) else None
    if not isinstance(tracks, list):
        raise RuntimeError(f'Unerwartetes GLM-Format für Musik-Prompts: {raw[:200]}')
    # Säubern
    out = []
    for t in tracks[:count]:
        if isinstance(t, dict) and t.get('prompt'):
            out.append({
                'title': (t.get('title') or 'Ohne Titel').strip()[:200],
                'prompt': t['prompt'].strip(),
            })
    return out


# Spezifikation je Wort-Inhalt: System-Prompt + Aufgabe + Ziel-Wortzahl.
# Bewusst warmer, einfacher Radio-Ton — NICHT der akademische Promotions-Stil.
SPOKEN_SPECS = {
    'story': {
        'system': (
            'Du bist Geschichtenerzähler eines liebevollen Familien-Radiosenders '
            'der Marke Naturmacher (Natur, Garten, Basteln, Familie). Du schreibst '
            'ruhige, warmherzige Gute-Nacht-Geschichten für Kinder (ca. 4–9 Jahre). '
            'Einfache Sprache, kurze Sätze, positive und beruhigende Stimmung, ein '
            'sanftes, gutes Ende zum Einschlafen. Keine Angst, keine Gewalt, keine '
            'Werbung, keine Markennamen. Themen: Natur, Pflanzen, Tiere, Jahreszeiten, '
            'Freundschaft, Basteln.'
        ),
        'task': 'Schreibe EINE Gute-Nacht-Geschichte zum Vorlesen (ca. 5 Minuten, etwa 650–800 Wörter).',
        'words': 750,
    },
    'wissen': {
        'system': (
            'Du moderierst die Rubrik „Wusstest du schon?" eines Naturmacher-'
            'Radiosenders. Du erklärst eine faszinierende, wahre Tatsache aus Natur, '
            'Pflanzenwelt, Garten oder Nachhaltigkeit — verständlich, lebendig, '
            'familienfreundlich. Keine erfundenen Zahlen oder Daten; bleib bei '
            'gesichertem Allgemeinwissen. Warmer, neugieriger Ton.'
        ),
        'task': 'Schreibe einen kurzen Wissens-Beitrag zum Vorlesen (ca. 1 Minute, etwa 130–170 Wörter).',
        'words': 150,
    },
    'tip': {
        'system': (
            'Du gibst den „Tipp des Tages" auf einem Naturmacher-Radiosender — '
            'eine praktische, leicht umsetzbare Idee rund um Garten, Basteln mit '
            'Kindern, Pflanzenpflege oder Nachhaltigkeit im Familienalltag. '
            'Konkret, freundlich, ermutigend. Keine Markennamen, keine Werbung.'
        ),
        'task': 'Schreibe einen kurzen Tipp zum Vorlesen (ca. 1 Minute, etwa 130–170 Wörter).',
        'words': 150,
    },
    'news': {
        'system': (
            'Du sprichst die Rubrik „Saisonales rund um Natur & Garten" auf einem '
            'Naturmacher-Radiosender. Du gibst eine kurze, zeitlose saisonale '
            'Orientierung (was in dieser Jahreszeit in Garten/Natur ansteht). '
            'KEINE tagesaktuellen Nachrichten oder konkreten Ereignisse/Daten '
            'erfinden — nur allgemeine, saisonale Hinweise. Freundlich und knapp.'
        ),
        'task': 'Schreibe einen kurzen saisonalen Beitrag zum Vorlesen (ca. 1 Minute, etwa 130–170 Wörter).',
        'words': 150,
    },
    'kreativ': {
        'system': (
            'Du bist kreativer Autor eines modernen Naturmacher-Radiosenders '
            '(Natur, Garten, Basteln, Familie). Du schreibst freie, fantasievolle '
            'Kurzbeiträge zum vorgegebenen Thema – z. B. eine kleine Glosse, ein '
            'Gedicht, eine Miniatur-Episode, einen poetischen Gedanken oder eine '
            'Alltagsbeobachtung. Lebendig, stimmungsvoll, zur Marke passend, '
            'familienfreundlich. Form frei wählbar, gut vorlesbar.'
        ),
        'task': 'Schreibe einen kreativen Beitrag zum Vorlesen (ca. 1–2 Minuten, etwa 180–280 Wörter).',
        'words': 230,
    },
    'jingle': {
        'system': (
            'Du textest Senderkennungen (Jingles) für „Naturmacher Radio" — '
            'den Radiosender der Marke Naturmacher (Natur, Garten, Basteln, '
            'Familie). Sehr kurz, eingängig, freundlich, zum Sprechen. Nennt den '
            'Sendernamen „Naturmacher Radio". Keine Musiknoten, keine Regie.'
        ),
        'task': 'Schreibe eine sehr kurze Senderkennung (ein bis zwei Sätze, ca. 8–12 Sekunden gesprochen).',
        'words': 22,
    },
    'ad': {
        'system': (
            'Du textest kurze, dezente Marken-Spots / Mitmach-Aufrufe für die '
            'Marke Naturmacher (personalisierte Blumentöpfe, Basteln mit Kindern, '
            'Naturerlebnisse für Familien). Freundlich, ehrlich, nicht aufdringlich, '
            'mit einer sanften Handlungsaufforderung (z. B. auf naturmacher.de '
            'vorbeischauen oder eine Bastelidee einsenden). KEINE konkreten Preise '
            'oder Rabatte erfinden.'
        ),
        'task': 'Schreibe einen kurzen Spot/Mitmach-Aufruf zum Vorlesen (ca. 25–35 Sekunden, etwa 60–80 Wörter).',
        'words': 70,
    },
}


def generate_spoken_text(kind, topic=None, season=None, target_words=None):
    """
    Lässt GLM 5.2 einen Vorlese-Text schreiben. Gibt dict {'title','text'} zurück.
    kind: 'story' | 'wissen' | 'tip' | 'news'
    target_words: optionale Längen-Zielvorgabe (überschreibt die Rubrik-Standardlänge).
    """
    spec = SPOKEN_SPECS.get(kind, SPOKEN_SPECS['wissen'])
    system, task = _rubrik_prompts(kind, spec['system'], spec['task'])
    words = int(target_words) if target_words else spec.get('words', 200)
    extra = ''
    if target_words:
        secs = round(words / 2.3)
        extra += (f' Ziel-Länge: etwa {words} Wörter (rund {secs} Sekunden gesprochen) – '
                  f'halte dich möglichst an diese Länge.')
    if topic:
        extra += f' Thema/Schwerpunkt: {topic}.'
    else:
        # Kein explizites Thema -> Themen-Gedächtnis: bisherige Titel meiden
        avoid = avoid_topics_instruction(kind)
        if avoid:
            extra += ' ' + avoid
    if season:
        extra += f' Jahreszeit/Anlass: {season}.'
    ann = announce_instruction(kind)
    if ann:
        extra += ' ' + ann
    user = (
        f'{task}{extra} '
        'Gib deine Antwort in genau diesem Format: In der ERSTEN Zeile "TITEL: " gefolgt von '
        'einem kurzen, konkreten deutschen Titel (kein Platzhalter, keine spitzen Klammern). '
        'Danach eine Leerzeile, dann der vollständige, fertig ausformulierte Vorlesetext als '
        'Fließtext (ohne Überschriften, ohne Markdown/Sternchen). Schreibe den Text '
        'zusammenhängend und vollständig bis zum Schluss zu Ende.'
    )
    import re as _re_t
    def _truncated(txt):
        # Text gilt als abgeschnitten, wenn er (nach evtl. SFX-Marker) nicht
        # mit einem Satzzeichen endet -> GLM-Truncation, neu generieren.
        t = _re_t.sub(r'\[[^\]]*\]\s*$', '', (txt or '').strip()).strip()
        t = t.rstrip('"\u201c\u201d\u201e\u00bb\u00ab' + chr(39)).strip()
        return bool(t) and t[-1] not in '.!?\u2026'
    # WICHTIG: KEIN json_mode. Im JSON-Modus beendet ein Anführungszeichen aus der
    # wörtlichen Rede das "text"-Feld vorzeitig -> die Geschichte bricht mitten im
    # Dialog ab. Reines Textformat (TITEL-Zeile + Fließtext) ist dagegen robust.
    title, body, raw = '', '', ''
    for _att in range(3):
        raw = glm_chat(user, system=system, max_tokens=max(2400, words * 6)).strip()
        title, body = _split_title_text(raw, kind)
        if body and not _truncated(body):
            break
    if not body:
        raise RuntimeError(f'Leerer GLM-Wort-Inhalt: {raw[:200]}')
    body = body.replace('*', '').replace('#', '').strip()  # Markdown-Reste raus
    return {'title': (title or kind.title())[:200], 'text': body}


def _split_title_text(raw, kind='wissen'):
    """Trennt 'TITEL: ...' (erste Zeile) vom Vorlesetext; robust gegen fehlenden Marker."""
    import re as _re
    s = (raw or '').strip()
    if s.startswith('```'):
        s = s.strip('`').strip()
        if s[:4].lower() == 'json':
            s = s[4:].strip()
    lines = s.splitlines()
    title, start = '', 0
    for i, ln in enumerate(lines[:3]):
        m = _re.match(r'\s*(?:TITEL|Titel|TITLE|Title)\s*[:\-]\s*(.+)', ln)
        if m:
            title = m.group(1).strip().strip('"“”„*#').strip()
            start = i + 1
            break
    body = '\n'.join(lines[start:]).strip()
    if not title and body:  # kein Marker -> Titel aus erstem Satz ableiten
        title = _re.split(r'(?<=[.!?])\s', body, 1)[0][:60]
    return title[:200], body


def _parse_json(raw):
    """Robustes JSON-Parsing (entfernt evtl. Markdown-Codefences)."""
    s = raw.strip()
    if s.startswith('```'):
        s = s.split('```', 2)[1]
        if s.lstrip().lower().startswith('json'):
            s = s.lstrip()[4:]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Versuch: erstes { ... } herausschneiden
        start, end = s.find('{'), s.rfind('}')
        if start != -1 and end != -1:
            return json.loads(s[start:end + 1])
        raise


# --- Built-in-Rubriken seeden (idempotent) ----------------------------------
_RUBRIK_LABELS = {
    'story': 'Gute-Nacht-Geschichte', 'wissen': 'Wissenswertes', 'tip': 'Tipp',
    'news': 'Saisonales / News', 'kreativ': 'Kreativ-Beitrag',
    'jingle': 'Jingle / Senderkennung', 'ad': 'Marken-Spot / Mitmach',
}
_RUBRIK_VOICES = {
    'story': 'piper-thorsten-sleepy', 'wissen': 'piper-thorsten-medium',
    'tip': 'piper-ramona', 'news': 'piper-thorsten-medium',
    'kreativ': 'piper-thorsten-amused', 'jingle': 'piper-thorsten-medium', 'ad': 'piper-ramona',
}
_RUBRIK_NIGHTLY = {'music', 'story', 'wissen', 'tip'}


def ensure_default_rubriken():
    """Legt die Built-in-Rubriken an, falls noch nicht vorhanden (überschreibt nichts)."""
    from .models import Rubrik
    Rubrik.objects.get_or_create(key='music', defaults=dict(
        label='Musik', rtype='music', system_prompt=DEFAULT_MUSIC_SYSTEM, task_prompt='',
        voice='', in_nightly=True, order=10, builtin=True))
    order = 20
    for key in ['story', 'wissen', 'tip', 'news', 'kreativ', 'jingle', 'ad']:
        spec = SPOKEN_SPECS.get(key)
        if not spec:
            continue
        Rubrik.objects.get_or_create(key=key, defaults=dict(
            label=_RUBRIK_LABELS.get(key, key.title()), rtype='speech',
            system_prompt=spec['system'], task_prompt=spec['task'],
            voice=_RUBRIK_VOICES.get(key, 'piper-thorsten-medium'),
            in_nightly=(key in _RUBRIK_NIGHTLY), order=order, builtin=True))
        order += 10
