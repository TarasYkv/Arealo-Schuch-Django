"""
Parser für strukturierte Szenen-Skripte (v2).

Unterstützt das erweiterte Format mit:
- BILDPROMPT (Frame-Prompt)
- VIDEO-PROMPT (Kamera/Bewegung/Atmosphäre)
- NEGATIVE PROMPT
- VOICE-OVER (nur zitierter Text)
- TEXT-OVERLAY
- MUSIK (Genre, Prompt, Lautstärke)
"""
import re


def _clean_quotes(text):
    text = text.strip()
    for pair in [('\u201e', '\u201c'), ('\u00bb', '\u00ab'), ('\u201c', '\u201d'), ('"', '"'), ("'", "'")]:
        if text.startswith(pair[0]) and text.endswith(pair[1]):
            text = text[len(pair[0]):-len(pair[1])].strip()
    return text


def _is_empty_value(val):
    v = val.strip().lower()
    return v in ('', 'keiner', 'keins', 'keine', 'kein', '-', 'n/a') or v.startswith('keiner') or v.startswith('keins')


def _extract_between(block, start_markers, end_markers):
    """Extract text between start_markers (any) and end_markers (any/end)."""
    for sm in start_markers:
        pattern = re.compile(
            re.escape(sm) + r'[^\n]*\n(.*?)(?=' + '|'.join(re.escape(e) for e in end_markers) + r'|\Z)',
            re.DOTALL | re.IGNORECASE
        )
        m = pattern.search(block)
        if m:
            return m.group(1).strip()
    return ''


def parse_script(text):
    if not text or not text.strip():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    scene_pattern = re.compile(r"(?=^SZENE\s+\d+\s*[—–\-])", re.MULTILINE)
    parts = scene_pattern.split(text)
    scene_blocks = [p for p in parts if re.match(r"^SZENE\s+\d+", p)]

    section_markers = ['📸', 'BILDPROMPT', '🎬', 'VIDEO-PROMPT', '❌', 'NEGATIVE',
                       '🎙️', 'VOICE-OVER', '📝', 'TEXT-OVERLAY', 'TEXT OVERLAY',
                       '🎵', 'MUSIK', '━', 'SZENE']

    scenes = []
    for idx, block in enumerate(scene_blocks):
        scene = {
            'order': idx,
            'duration': 5,
            'start_frame_prompt': '',
            'prompt': '',
            'voiceover_text': '',
            'text_overlay': '',
            'negative_prompt': '',
            'music_prompt': '',
            'music_genre': '',
            'music_volume': 0.3,
        }

        # Duration
        m_dur = re.search(r'\|\s*(\d+(?:\.\d+)?)\s*Sek', block)
        if m_dur:
            try:
                scene['duration'] = int(float(m_dur.group(1)))
            except ValueError:
                pass

        # BILDPROMPT
        m_bild = re.search(
            r'(?:📸\s*)?BILDPROMPT[^\n]*\n(.*?)(?=🎬|VIDEO-PROMPT|❌|NEGATIVE|🎙️|VOICE-OVER|📝|TEXT.?OVERLAY|🎵|MUSIK|━|\Z)',
            block, re.DOTALL | re.IGNORECASE)
        if m_bild:
            raw = m_bild.group(1).strip()
            lines = [l.strip() for l in raw.split('\n') if l.strip() and not l.strip().startswith('—')]
            scene['start_frame_prompt'] = '\n'.join(lines).strip()

        # VIDEO-PROMPT → combine labeled lines
        m_vid = re.search(
            r'(?:🎬\s*)?VIDEO-PROMPT[^\n]*\n(.*?)(?=❌|NEGATIVE|🎙️|VOICE-OVER|📝|TEXT.?OVERLAY|🎵|MUSIK|━|\Z)',
            block, re.DOTALL | re.IGNORECASE)
        if m_vid:
            raw = m_vid.group(1).strip()
            parts_vp = []
            for line in raw.split('\n'):
                line = line.strip().lstrip('—').strip()
                if not line:
                    continue
                if ':' in line:
                    label, val = line.split(':', 1)
                    val = val.strip()
                    lab = label.strip().lower()
                    if _is_empty_value(val):
                        continue
                    if 'kamera' in lab:
                        parts_vp.append(f'Camera: {val}')
                    elif 'subjekt' in lab or 'bewegung' in lab:
                        parts_vp.append(f'Motion: {val}')
                    elif 'atmosph' in lab:
                        parts_vp.append(f'Atmosphere: {val}')
                    elif 'tempo' in lab:
                        parts_vp.append(f'Pace: {val.split("|")[0].strip()}')
                    else:
                        parts_vp.append(val)
                else:
                    parts_vp.append(line)
            scene['prompt'] = '. '.join(parts_vp)

        # NEGATIVE PROMPT
        m_neg = re.search(
            r'(?:❌\s*)?NEGATIVE\s*PROMPT\s*:?\s*([^\n]+)',
            block, re.IGNORECASE)
        if m_neg:
            val = m_neg.group(1).strip()
            if not _is_empty_value(val):
                scene['negative_prompt'] = val

        # VOICE-OVER — only extract quoted text, skip annotations (→ Typ:, → Rhythmus:)
        m_vo = re.search(
            r'(?:🎙️\s*)?VOICE-OVER\s*:?\s*\n?(.*?)(?=📸|BILDPROMPT|📝|TEXT.?OVERLAY|🎵|MUSIK|❌|NEGATIVE|━|\Z)',
            block, re.DOTALL | re.IGNORECASE)
        if m_vo:
            vo_raw = m_vo.group(1).strip()
            first_line = vo_raw.split('\n')[0].strip() if vo_raw else ''
            if not _is_empty_value(first_line):
                # Filter out annotation lines FIRST, then extract quotes
                content_lines = []
                for line in vo_raw.split('\n'):
                    stripped = line.strip()
                    if stripped.startswith('\u2192') or stripped.startswith('->'):
                        continue
                    if any(stripped.lower().startswith(x) for x in ['typ:', 'rhythmus:']):
                        continue
                    content_lines.append(stripped)
                vo_cleaned = '\n'.join(content_lines)
                # ONLY extract text inside quotes. Everything else is ignored.
                all_quotes = re.findall(
                    r'[\u201e\u201c"\u00ab\u00bb\u201d](.+?)[\u201c\u201d"\u00ab\u00bb\u201e]',
                    vo_cleaned)
                if all_quotes:
                    scene['voiceover_text'] = ' '.join(q.strip() for q in all_quotes).strip()
                else:
                    # Fallback: first non-annotation non-empty line
                    for line in vo_raw.split('\n'):
                        line = line.strip()
                        if not line or line.startswith('\u2192') or line.startswith('->'):
                            continue
                        if any(line.lower().startswith(x) for x in ['typ:', 'rhythmus:', 'keiner', 'kein ']):
                            continue
                        cleaned = _clean_quotes(line)
                        if cleaned and not _is_empty_value(cleaned):
                            scene['voiceover_text'] = cleaned
                            break

        # TEXT-OVERLAY
        m_tov = re.search(r'(?:📝\s*)?TEXT-?OVERLAY\s*:?\s*([^\n]+)', block, re.IGNORECASE)
        if m_tov:
            val = m_tov.group(1).strip()
            if not _is_empty_value(val):
                scene['text_overlay'] = _clean_quotes(val).strip('\u201e\u201c"\'')

        # MUSIK section
        m_mus = re.search(
            r'(?:🎵\s*)?MUSIK\s*:?\s*\n(.*?)(?=━|\Z)',
            block, re.DOTALL | re.IGNORECASE)
        if m_mus:
            mus_raw = m_mus.group(1).strip()
            for line in mus_raw.split('\n'):
                line = line.strip().lstrip('→').strip()
                if ':' not in line:
                    continue
                label, val = line.split(':', 1)
                label = label.strip().lower()
                val = val.strip()
                if 'genre' in label:
                    genre_map = {
                        'piano': 'piano', 'klavier': 'piano',
                        'akustisch': 'acoustic', 'acoustic': 'acoustic', 'gitarre': 'acoustic',
                        'cinematic': 'cinematic', 'filmmusik': 'cinematic',
                        'lo-fi': 'lofi', 'lofi': 'lofi', 'chill': 'lofi',
                        'corporate': 'corporate', 'business': 'corporate',
                        'epic': 'epic', 'trailer': 'epic',
                        'ambient': 'ambient',
                        'happy': 'happy',
                        'sad': 'sad', 'melancholisch': 'sad',
                        'dramatisch': 'dramatic', 'dramatic': 'dramatic',
                        'romantisch': 'romantic', 'romantic': 'romantic',
                        'electronic': 'electronic', 'synth': 'electronic',
                    }
                    val_lower = val.lower().strip()
                    for key, mapped in genre_map.items():
                        if key in val_lower:
                            scene['music_genre'] = mapped
                            break
                elif 'prompt' in label:
                    val = _clean_quotes(val).strip('\u201e\u201c"\'')
                    if not _is_empty_value(val):
                        scene['music_prompt'] = val
                elif 'laut' in label or 'volume' in label:
                    m_pct = re.search(r'(\d+)\s*%', val)
                    if m_pct:
                        scene['music_volume'] = int(m_pct.group(1)) / 100.0

        scenes.append(scene)

    return scenes


def extract_project_metadata(text):
    metadata = {}
    m = re.search(r'TITEL\s*[:：]?\s*(.+?)$', text, re.MULTILINE | re.IGNORECASE)
    if m:
        metadata['title'] = m.group(1).strip().strip('\u201e\u201c"')
    m = re.search(r'PLATTFORM\s*[:：]?\s*(.+?)$', text, re.MULTILINE | re.IGNORECASE)
    if m:
        metadata['platform'] = m.group(1).strip()
    m = re.search(r'SEITENVERH[ÄA]LTNIS\s*[:：]?\s*(.+?)$', text, re.MULTILINE | re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if '9:16' in val:
            metadata['aspect_ratio'] = '9:16'
        elif '16:9' in val:
            metadata['aspect_ratio'] = '16:9'
        elif '1:1' in val:
            metadata['aspect_ratio'] = '1:1'

    # Project-level music from header (before first SZENE)
    preamble = text.split('SZENE')[0] if 'SZENE' in text else text
    m_mus = re.search(r'(?:🎵\s*)?MUSIK[^\n]*\n(.*?)(?=━|SZENE|\Z)', preamble, re.DOTALL | re.IGNORECASE)
    if m_mus:
        genre_map = {
            'piano': 'piano', 'klavier': 'piano',
            'akustisch': 'acoustic', 'acoustic': 'acoustic',
            'cinematic': 'cinematic', 'filmmusik': 'cinematic',
            'lo-fi': 'lofi', 'lofi': 'lofi', 'chill': 'lofi',
            'corporate': 'corporate', 'epic': 'epic', 'trailer': 'epic',
            'ambient': 'ambient', 'happy': 'happy',
            'sad': 'sad', 'melancholisch': 'sad',
            'dramatisch': 'dramatic', 'dramatic': 'dramatic',
            'romantisch': 'romantic', 'romantic': 'romantic',
            'electronic': 'electronic', 'synth': 'electronic',
        }
        for line in m_mus.group(1).split('\n'):
            line = line.strip().lstrip('\u2192').strip()
            if ':' not in line:
                continue
            label, val = line.split(':', 1)
            label = label.strip().lower()
            val = val.strip()
            if 'genre' in label:
                for key, mapped in genre_map.items():
                    if key in val.lower():
                        metadata['music_genre'] = mapped
                        break
            elif 'prompt' in label:
                metadata['music_prompt'] = _clean_quotes(val).strip('\u201e\u201c"\'')
            elif 'laut' in label or 'volume' in label:
                m_pct = re.search(r'(\d+)\s*%', val)
                if m_pct:
                    metadata['music_volume'] = int(m_pct.group(1)) / 100.0
    return metadata
