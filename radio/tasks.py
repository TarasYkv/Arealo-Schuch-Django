"""
Celery-Tasks des Radiosenders.

generate_music_batch: der nächtliche KI-Musik-Lauf.
  GLM 5.1 (Programmdirektor) schreibt die MusicGen-Prompts ->
  MusicGen auf RunPod erzeugt die Tracks -> Track-Datensätze + MP3.

Gestartet z.B. via Celery-Beat (nachts) oder manuell über
  python manage.py generate_music_batch --mood "ruhig, naturnah" --count 10
"""
import logging
import os

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)


# Standard-Stimme je Wort-Inhalt — natürliche Gemini-Stimmen (Cloud, keine GPU nötig)
VOICE_BY_KIND = {
    'story': 'gemini-Enceladus',   # ruhig/behaucht — sanft zum Einschlafen
    'klanggeschichte': 'gemini-Enceladus',  # Hörgeschichte mit Soundeffekten
    'wissen': 'gemini-Charon',     # ruhig, sachlich
    'tip': 'gemini-Kore',          # freundlich, weiblich
    'news': 'gemini-Rasalgethi',   # informativ, klar
    'kreativ': 'gemini-Puck',      # lebendig
    'jingle': 'gemini-Aoede',      # frisch, locker
    'ad': 'gemini-Kore',           # einladend, freundlich
}

# Wiederverwendbare, tagesunabhängige Inhalte (kein air_date)
EVERGREEN_KINDS = {'jingle', 'ad'}


def _synthesize(text, voice, kind=None, gemini_model=None, eleven_model=None):
    """
    Vertont Text. Reihenfolge:
      'gemini-*' -> Gemini Cloud-TTS (natürlich, keine GPU) — Standard
      'xtts*'    -> XTTS-v2 (GPU, klonbar)
      sonst      -> Piper (CPU, schnell)
    """
    from . import gemini_tts
    # Klanggeschichte: Erzählung + eingebettete Soundeffekte/Klangteppich mischen.
    if kind == 'klanggeschichte':
        from . import soundscape
        return soundscape.synth_story(text, voice=voice)
    # fal.ai-Stimme (kodiert als 'fal:<model-id>')
    if voice and str(voice).startswith('fal:'):
        from . import fal
        return fal.tts(voice.split(':', 1)[1], text)
    # Edge-TTS (Microsoft) — gratis, natürliche deutsche Stimmen, KEINE lokale Last.
    # Stimme kodiert als 'edge-<VoiceName>', z. B. 'edge-de-DE-ConradNeural'.
    if voice and str(voice).startswith('edge-'):
        from . import edgetts
        return edgetts.synth(text, voice=voice)
    # ElevenLabs-Stimme (Feintuning aus StationConfig)
    from . import elevenlabs as el
    if el.is_eleven_voice(voice):
        from .models import StationConfig
        cfg = StationConfig.get()
        return el.text_to_speech(
            text, el.voice_id_of(voice), model_id=(eleven_model or cfg.eleven_model_id),
            stability=cfg.eleven_stability, similarity=cfg.eleven_similarity,
            style=cfg.eleven_style, speaker_boost=cfg.eleven_speaker_boost)
    if gemini_tts.is_gemini_voice(voice):
        from .models import StationConfig
        model = gemini_model or StationConfig.get().gemini_tts_model
        return gemini_tts.synth(text, voice=voice, kind=kind, model=model)
    from . import xtts as radio_xtts
    from video import tts
    if radio_xtts.is_xtts_voice(voice):
        clone = None
        if voice == 'xtts-clone':
            from .models import StationConfig
            c = StationConfig.get()
            try:
                clone = c.clone_voice.path if c.clone_voice else None
            except ValueError:
                clone = None
        return radio_xtts.generate_xtts(text, voice=voice, clone_wav_local=clone)
    return tts.generate_piper(text, audio_model=voice)


def _prepend_news_intro(news_bytes):
    """Stellt das feste News-Intro (media/radio/news_intro.mp3) vor die Bytes.
    Robust per ffmpeg-Resample+Concat; gibt Original zurück, wenn kein Intro da ist."""
    import os
    import subprocess
    import tempfile
    from django.conf import settings as _dj
    from .models import StationConfig
    if not StationConfig.get().news_intro_enabled:
        return news_bytes
    intro = os.path.join(_dj.MEDIA_ROOT, 'radio', 'news_intro.mp3')
    if not news_bytes or not os.path.exists(intro):
        return news_bytes
    try:
        with tempfile.TemporaryDirectory() as td:
            npath = os.path.join(td, 'news.mp3')
            out = os.path.join(td, 'out.mp3')
            with open(npath, 'wb') as fh:
                fh.write(news_bytes)
            cmd = ['ffmpeg', '-y', '-i', intro, '-i', npath, '-filter_complex',
                   '[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a0];'
                   '[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a1];'
                   '[a0][a1]concat=n=2:v=0:a=1[a]',
                   '-map', '[a]', '-c:a', 'libmp3lame', '-b:a', '192k', out]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                with open(out, 'rb') as fh:
                    return fh.read()
    except Exception as e:
        logger.warning('News-Intro voranstellen fehlgeschlagen: %s', e)
    return news_bytes


@shared_task
def generate_spoken_content(kind='wissen', topic=None, season=None, air_date=None, voice=None):
    """
    Erzeugt EINEN Wort-Inhalt: GLM 5.1 schreibt den Text, Piper liest ihn,
    Ergebnis wird als SpokenContent (status='generated') gespeichert.
    Gibt die SpokenContent-pk zurück.
    """
    from datetime import date as _date
    from .models import SpokenContent, Rubrik
    from . import glm
    from video import tts

    # Rubrik-Einstellungen heranziehen (Stimme, Länge, TTS-Modell) – mit Fallbacks
    r = Rubrik.objects.filter(key=kind).first()
    rvoice = (r.voice if (r and r.voice) else '') or ''
    if rvoice.startswith('piper'):  # Piper ist auf diesem Server NICHT installiert -> Gemini-Standard
        rvoice = ''
    voice = voice or rvoice or VOICE_BY_KIND.get(kind, 'gemini-Charon')
    target_words = max(8, round(r.target_sec * 2.3)) if (r and r.target_sec) else None
    tts_model = (r.tts_model.strip() if (r and r.tts_model) else '') or None

    # Saisonsensible Rubriken bekommen automatisch die aktuelle Jahreszeit,
    # sonst erfindet das Modell beliebige (z. B. Herbst-Themen im Juni).
    if not season and kind in ('news', 'tip', 'spaziergang', 'bastelidee', 'blitzrezept', 'wissen'):
        from datetime import date as _d2
        _m = _d2.today().month
        _MON = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli',
                'August', 'September', 'Oktober', 'November', 'Dezember']
        _SAI = ('Frühling' if _m in (3, 4, 5) else 'Sommer' if _m in (6, 7, 8)
                else 'Herbst' if _m in (9, 10, 11) else 'Winter')
        season = f'aktuell ist {_MON[_m - 1]} ({_SAI})'

    logger.info(f'GLM 5.1: schreibe Wort-Inhalt ({kind})...')
    written = glm.generate_spoken_text(kind, topic=topic, season=season, target_words=target_words)

    # Harte Dublettenprüfung: GLM ignoriert das Themen-Gedächtnis gelegentlich.
    # Steht der neue Titel (normalisiert) schon im Gedächtnis, einmal mit
    # verschärfter Anweisung neu schreiben lassen.
    if not topic:
        def _norm(t):
            return ''.join(ch for ch in (t or '').lower() if ch.isalnum())
        from .models import Rubrik as _Rb2
        _r2 = _Rb2.objects.filter(key=kind).first()
        _known = {_norm(ln) for ln in ((_r2.topic_memory or '').splitlines() if _r2 else []) if ln.strip()}
        if _norm(written.get('title')) in _known:
            logger.info(f'Thema "{written.get("title")}" existiert bereits – schreibe neu...')
            written = glm.generate_spoken_text(
                kind, topic=None, season=season, target_words=target_words)
            if _norm(written.get('title')) in _known:
                raise RuntimeError(f'Themen-Dublette trotz Retry: {written.get("title")}')

    # Jingles/Spots sind evergreen (tagesunabhängig, wiederverwendbar)
    if kind not in EVERGREEN_KINDS:
        air_date = air_date or _date.today()
    sc = SpokenContent(
        kind=kind,
        title=written['title'],
        text=written['text'],
        voice=voice,
        air_date=air_date,
        status='draft',
    )
    sc.save()

    # TTS-Modell-Detail nur an die passende Engine weiterreichen
    gem_model = elev_model = None
    if tts_model:
        if str(voice).startswith('gemini-'):
            gem_model = tts_model
        else:
            try:
                from . import elevenlabs as _el
                if _el.is_eleven_voice(voice):
                    elev_model = tts_model
            except Exception:
                pass
    logger.info(f'TTS ({voice}): vertone "{sc.title}" ({len(written["text"].split())} Wörter)...')
    if '+' in (voice or ''):
        # Dialog-Rubrik: Stimme als "stimmeA+stimmeB"; Sprecher-Namen aus den
        # Zeilen-Präfixen des Textes ("Anna: ...", "Theo: ...") ableiten.
        import re as _re
        from . import gemini_tts as _gt
        va, vb = (voice.split('+', 1) + [''])[:2]
        names = []
        for line in written['text'].splitlines():
            m = _re.match(r'\s*([^:\n]{2,24}):\s', line)
            if m:
                n = m.group(1).strip()
                if n and n not in names:
                    names.append(n)
            if len(names) >= 2:
                break
        speakers = [(names[0] if names else 'A', va.strip()),
                    (names[1] if len(names) > 1 else 'B', vb.strip())]
        mp3 = _gt.synth_dialog(written['text'], speakers=speakers, model=gem_model)
    else:
        mp3 = _synthesize(written['text'], voice, kind=kind, gemini_model=gem_model, eleven_model=elev_model)
    if kind in MUSIC_BEDS:
        bed_pk, bed_gain = MUSIC_BEDS[kind]
        mp3 = _mix_music_bed(mp3, bed_pk, gain=bed_gain)
    sc.audio_file.save(f'spoken_{kind}_{sc.pk}.mp3', ContentFile(mp3), save=False)
    sc.duration_sec = _probe_duration(sc.audio_file.path)
    sc.status = 'generated'
    try:  # verwendetes KI-Modell festhalten (fuer Bibliotheks-Anzeige)
        from .models import StationConfig as _SC
        if '+' in (voice or '') or str(voice).startswith('gemini-'):
            sc.gen_model = gem_model or _SC.get().gemini_tts_model or ''
        else:
            from . import elevenlabs as _el2
            if _el2.is_eleven_voice(voice):
                sc.gen_model = elev_model or _SC.get().eleven_model_id or ''
    except Exception:
        pass
    sc.save(update_fields=['audio_file', 'duration_sec', 'status', 'gen_model'])
    glm.remember_topic(kind, sc.title)   # Themen-Gedächtnis der Rubrik pflegen
    logger.info(f'   ✓ SpokenContent #{sc.pk} fertig vertont ({sc.duration_sec}s).')
    return sc.pk


# Rubriken mit automatischem Musikbett: Rubrik-Key -> (Track-PK, Lautstärke)
MUSIC_BEDS = {'garten-meditation': (114, 0.14)}


def _mix_music_bed(mp3_bytes, track_pk, gain=0.14, pre=2.5, tail=6.0):
    """Legt ein leises, weichgefiltertes Musikbett unter eine Sprachaufnahme.
    Musik startet pre Sekunden vor der Stimme und klingt tail Sekunden aus."""
    import subprocess, tempfile, os as _os
    from .models import Track
    t = Track.objects.filter(pk=track_pk).exclude(audio_file='').first()
    if not t:
        return mp3_bytes
    vp = out = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(mp3_bytes); vp = f.name
        out = vp + '.mix.mp3'
        dur = _probe_duration(vp)
        if not dur:
            return mp3_bytes
        total = dur + pre + tail
        fade_st = max(0.0, total - 5)
        flt = (f'[0:a]adelay={int(pre*1000)}|{int(pre*1000)}[v];'
               f'[1:a]atrim=0:{total},volume={gain},lowpass=f=4500,'
               f'afade=t=in:d=3,afade=t=out:st={fade_st}:d=5[m];'
               f'[v][m]amix=inputs=2:duration=longest:normalize=0[mix]')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', vp,
                        '-stream_loop', '-1', '-i', t.audio_file.path,
                        '-filter_complex', flt, '-map', '[mix]',
                        '-c:a', 'libmp3lame', '-b:a', '160k', out],
                       check=True, timeout=180)
        return open(out, 'rb').read()
    except Exception as e:
        logger.warning(f'Musikbett-Mischung fehlgeschlagen (Track {track_pk}): {e}')
        return mp3_bytes
    finally:
        for q in (vp, out):
            if q and _os.path.exists(q):
                _os.unlink(q)


def _probe_duration(path):
    """Audiolänge in Sekunden via ffprobe (0 bei Fehler)."""
    import subprocess
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return int(float(out)) if out else 0
    except Exception:
        return 0


@shared_task
def generate_spoken_batch(plan=None, air_date=None):
    """
    Erzeugt mehrere Wort-Inhalte gemäß `plan` (Liste von dicts mit kind/topic/season)
    oder einem sinnvollen Default-Tagespaket. Gibt Liste der pks zurück.
    """
    if not plan:
        plan = [
            {'kind': 'story'},
            {'kind': 'wissen'},
            {'kind': 'tip'},
        ]
    pks = []
    for item in plan:
        try:
            pk = generate_spoken_content(
                kind=item.get('kind', 'wissen'),
                topic=item.get('topic'),
                season=item.get('season'),
                air_date=air_date,
                voice=item.get('voice'),
            )
            pks.append(pk)
        except Exception as e:
            logger.exception(f'Wort-Inhalt ({item}) fehlgeschlagen: {e}')
    return pks


@shared_task
def generate_music_batch(mood=None, count=10, batch_job_id=None, duration_sec=300):
    """Erzeugt `count` KI-Musik-Tracks zur Stimmung `mood` (Default 5 Min/Track)."""
    from .models import StationConfig, Track, MusicBatchJob
    from . import glm, musicgen

    config = StationConfig.get()
    mood = mood or config.default_mood

    if batch_job_id:
        job = MusicBatchJob.objects.get(pk=batch_job_id)
    else:
        job = MusicBatchJob.objects.create(mood=mood, count_requested=count)
    job.status = 'running'
    job.save(update_fields=['status'])

    def _log(line):
        logger.info(line)
        job.log = (job.log + line + '\n')[-8000:]
        job.save(update_fields=['log'])

    try:
        _log(f'GLM 5.1: erzeuge {count} Musik-Prompts für Stimmung "{mood}"...')
        prompts = glm.generate_music_prompts(mood, count=count)
        _log(f'GLM lieferte {len(prompts)} Prompts.')

        for i, item in enumerate(prompts, 1):
            try:
                _log(f'[{i}/{len(prompts)}] MusicGen: {item["title"]} — "{item["prompt"][:60]}..."')
                mp3_path = musicgen.generate_track(item['prompt'], duration_sec=duration_sec)
                with open(mp3_path, 'rb') as f:
                    data = f.read()
                os.remove(mp3_path)

                track = Track(
                    title=item['title'],
                    mood=mood,
                    source='musicgen',
                    prompt=item['prompt'],
                    duration_sec=duration_sec,
                )
                filename = f'musicgen_{job.pk}_{i}.mp3'
                track.audio_file.save(filename, ContentFile(data), save=True)
                job.count_done += 1
                job.save(update_fields=['count_done'])
                _log(f'   ✓ gespeichert als Track #{track.pk}')
            except Exception as e:
                _log(f'   ✗ Fehler bei Track {i}: {e}')

        job.status = 'done'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'finished_at'])
        _log(f'Batch fertig: {job.count_done}/{job.count_requested} Tracks erzeugt.')
        return {'job_id': job.pk, 'done': job.count_done}

    except Exception as e:
        job.status = 'failed'
        job.finished_at = timezone.now()
        job.log = (job.log + f'ABBRUCH: {e}\n')[-8000:]
        job.save(update_fields=['status', 'finished_at', 'log'])
        logger.exception('Musik-Batch fehlgeschlagen')
        raise


@shared_task
def cleanup_old_media(track_keep=150, spoken_days=7, played_hours=24):
    """
    Räumt NUR gespielte/übersprungene Sendeplan-Zeilen (älter als played_hours)
    samt heruntergeladener Videos auf — Tracks und Wort-Inhalte bleiben dauerhaft
    erhalten (sie bilden die Bibliothek, sortiert nach Rubriken).

    Hinweis: track_keep/spoken_days bleiben aus Kompatibilität in der Signatur,
    werden aber nicht mehr zum Löschen von Bibliotheks-Inhalten genutzt.
    """
    from datetime import timedelta
    from .models import PlaylistEntry
    removed = {'entries': 0}
    now = timezone.now()

    for e in PlaylistEntry.objects.filter(status__in=['played', 'skipped'],
                                          created_at__lt=now - timedelta(hours=played_hours)):
        try:
            if e.video_file:
                e.video_file.delete(save=False)
        except Exception:
            pass
        e.delete()
        removed['entries'] += 1

    logger.info(f'cleanup_old_media (Bibliothek bleibt): {removed}')
    return removed


def _track_kind(t):
    """Rubrik eines Tracks: manuelle Kategorie hat Vorrang, sonst aus Quelle abgeleitet."""
    if getattr(t, 'category', '') in ('music', 'song', 'effekt', 'ad'):
        return t.category
    if t.source == 'elevenlabs':
        return 'effekt'
    if t.lyrics or t.source in ('acestep',):
        return 'song'
    return 'music'


def _library_candidates(limit=120):
    """Sammelt AUTOMATISCH einplanbare Bibliotheks-Inhalte (Tracks + Wort-Inhalte).

    Ausgeschlossene (Track.is_active=False / SpokenContent.auto_include=False) und
    saisonal gesperrte Inhalte (siehe scheduler._seasonal_ok) werden NICHT geliefert.
    """
    from .models import Track, SpokenContent
    from . import scheduler
    from django.utils import timezone
    today = timezone.localdate()
    smap = scheduler._season_map()
    cands = []
    for t in (Track.objects.filter(is_active=True).exclude(audio_file='')
              .order_by('play_count', '-created_at')[:limit]):
        if not scheduler._seasonal_ok(t.tags, today, smap):
            continue
        item = {'type': 'track', 'pk': t.pk, 'kind': _track_kind(t),
                'title': t.title, 'dur': t.duration_sec or 120,
                'desc': (t.description or t.mood or '')[:80]}
        # Saison-Boost: aktive Saison-Inhalte mehrfach in den Pool legen
        cands.extend([item] * scheduler._season_boost(t.tags, today, smap))
    # Werbe-/Spot-Tracks (z.B. gesungene Spots) IMMER aufnehmen – sie dürfen nicht
    # durch das Pool-Limit der (vielen) Musiktitel verdrängt werden
    have = {(c['type'], c['pk']) for c in cands}
    for t in Track.objects.filter(is_active=True, category='ad').exclude(audio_file=''):
        if ('track', t.pk) not in have and scheduler._seasonal_ok(t.tags, today, smap):
            cands.append({'type': 'track', 'pk': t.pk, 'kind': 'ad',
                          'title': t.title, 'dur': t.duration_sec or 60,
                          'desc': (t.description or t.mood or '')[:80]})
    from django.db.models import F as _F
    for s in (SpokenContent.objects.filter(status='generated', auto_include=True).exclude(audio_file='').exclude(kind='news')
              .order_by(_F('last_played_at').asc(nulls_first=True), '-created_at')[:limit]):
        if not scheduler._seasonal_ok(s.tags, today, smap):
            continue
        item = {'type': 'spoken', 'pk': s.pk, 'kind': s.kind,
                'title': s.title, 'dur': s.duration_sec or 60,
                'desc': (s.description or s.text[:80])}
        cands.extend([item] * scheduler._season_boost(s.tags, today, smap))
    return cands


def _fallback_mix(cands, target_sec):
    """Standard-Mix nach den globalen Misch-Regeln (StationConfig):
    alle N Musiktitel ein Wortbeitrag, Jingle alle K Titel, Werbung alle M Minuten.
    Füllt zyklisch bis zur Zielzeit (faire Rotation, keine direkte Wiederholung)."""
    import random
    from .models import StationConfig, Rubrik
    cfg = StationConfig.get()
    mpt = cfg.std_music_per_talk or 0      # 0 = nie automatisch Wortbeitrag
    jev = cfg.std_jingle_every or 0        # 0 = keine Jingles
    ade = cfg.std_ad_every_min or 0        # 0 = keine Werbung

    # Pro-Rubrik konfigurierte Kategorie (Einstellungen → Rubriken); leer = automatisch
    catmap = {r.key: r.category for r in Rubrik.objects.all() if r.category}

    def _bucket(c):
        # explizite Rubrik-Kategorie hat Vorrang
        cat = catmap.get(c['kind'])
        if cat:
            return cat
        # Fallback: Heuristik nach Art-Name
        if c['kind'] in ('music', 'song'):
            return 'music'
        if c['kind'] in ('jingle', 'effekt'):
            return 'jingle'
        if c['kind'] == 'ad':
            return 'ad'
        return 'talk'

    music_all = [c for c in cands if _bucket(c) == 'music']
    talk = [c for c in cands if _bucket(c) == 'talk']
    jings = [c for c in cands if _bucket(c) == 'jingle']
    ads = [c for c in cands if _bucket(c) == 'ad']
    # Instrumental vs. Gesang nach eingestelltem Anteil (StationConfig.song_share) mischen
    instr = [c for c in music_all if c['kind'] != 'song']
    vocal = [c for c in music_all if c['kind'] == 'song']
    random.shuffle(instr); random.shuffle(vocal)
    share = max(0, min(100, getattr(cfg, 'song_share', 35) or 0)) / 100.0
    music = []
    acc, ii, vi = 0.0, 0, 0
    for _ in range(len(music_all)):
        acc += share
        if (acc >= 1.0 and vocal) or not instr:
            if not vocal:
                break
            music.append(vocal[vi % len(vocal)]); vi += 1; acc -= 1.0
        else:
            music.append(instr[ii % len(instr)]); ii += 1
    random.shuffle(talk); random.shuffle(jings); random.shuffle(ads)
    if not music and not talk:
        return []
    order = []; total = 0; mi = ti = ji = ai = since = mcount = 0; last_ad = 0; guard = 0
    while total < target_sec and guard < 5000:
        guard += 1
        if music:
            c = music[mi % len(music)]; mi += 1
            if order and (order[-1]['type'], order[-1]['pk']) == (c['type'], c['pk']) and len(music) > 1:
                continue
            order.append(c); total += c['dur'] or 60; mcount += 1; since += 1
        elif talk:
            c = talk[ti % len(talk)]; ti += 1; order.append(c); total += c['dur'] or 60
        else:
            break
        if jev and jings and mcount > 0 and mcount % jev == 0:
            order.append(jings[ji % len(jings)]); ji += 1; total += order[-1]['dur'] or 5
        if mpt and since >= mpt and talk:
            c = talk[ti % len(talk)]; ti += 1; since = 0; order.append(c); total += c['dur'] or 60
        if ade and ads and (total - last_ad) >= ade * 60:
            order.append(ads[ai % len(ads)]); ai += 1; last_ad = total; total += order[-1]['dur'] or 10
    return order


@shared_task
def auto_program(target_minutes=120):
    """
    Stellt mit GLM 5.1 aus der BIBLIOTHEK ein ~target_minutes langes Programm
    zusammen (Musik mit/ohne Gesang + Wortbeiträge + Jingles, sinnvoll gemischt)
    und hängt es HINTEN an den Sendeplan an. Läuft alle 2 Std. via Celery-Beat.
    """
    from .models import Track, SpokenContent, PlaylistEntry
    from . import glm, scheduler
    import json as _json

    cands = _library_candidates()
    if not cands:
        return 'auto_program: Bibliothek leer'

    target_sec = int(target_minutes) * 60
    # Standardprogramm nach den globalen Misch-Regeln (StationConfig):
    # vorhersehbare Intervalle für Wortbeiträge/Jingles/Werbung.
    order = _fallback_mix(cands, target_sec)
    if not order:
        return 'auto_program: nichts auswählbar'

    # Direkte Wiederholungen entzerren (nicht zweimal dasselbe hintereinander)
    def _key(c):
        return (c['type'], c['pk'])
    for i in range(1, len(order)):
        if _key(order[i]) == _key(order[i - 1]):
            for j in range(i + 1, len(order)):
                if _key(order[j]) != _key(order[i - 1]):
                    order[i], order[j] = order[j], order[i]
                    break

    last = (PlaylistEntry.objects.order_by('-position').values_list('position', flat=True).first()) or 0
    pos = last
    created = 0
    for c in order:
        pos += 1
        entry = PlaylistEntry(status='queued', manual=False, position=pos, kind=c['kind'])
        if c['type'] == 'track':
            entry.track = Track.objects.filter(pk=c['pk']).first()
        else:
            entry.spoken = SpokenContent.objects.filter(pk=c['pk']).first()
        if entry.content:
            entry.save(); created += 1
    scheduler.renumber()
    logger.info(f'auto_program: {created} Einträge angehängt (~{target_minutes} Min)')
    return f'auto_program: {created} Einträge angehängt'


def _build_slot_order(slot):
    """Baut die Beitragsreihenfolge für einen Slot nach dessen Mischregeln aus der Bibliothek."""
    import random
    kinds = [k.strip() for k in (slot.kinds or '').split(',') if k.strip()] or ['music']
    cands = [c for c in _library_candidates() if c['kind'] in kinds]
    music = [c for c in cands if c['kind'] in ('music', 'song')]
    talk = [c for c in cands if c['kind'] in ('news', 'tip', 'wissen', 'story', 'dialog', 'kreativ', 'jingle', 'effekt')]
    ads = [c for c in cands if c['kind'] == 'ad']
    random.shuffle(music); random.shuffle(talk); random.shuffle(ads)
    if not (music or talk or ads):
        return []
    target = (slot.duration_min or 60) * 60
    order, total, mi, ti, ai, mcount, last_ad, guard = [], 0, 0, 0, 0, 0, 0, 0
    while total < target and guard < 4000:
        guard += 1
        if ads and slot.ad_every_min and (total - last_ad) >= slot.ad_every_min * 60:
            c = ads[ai % len(ads)]; ai += 1; last_ad = total
        elif slot.music_per_talk and mcount >= slot.music_per_talk and talk:
            c = talk[ti % len(talk)]; ti += 1; mcount = 0
        elif music:
            c = music[mi % len(music)]; mi += 1; mcount += 1
        elif talk:
            c = talk[ti % len(talk)]; ti += 1
        elif ads:
            c = ads[ai % len(ads)]; ai += 1
        else:
            break
        if order and (order[-1]['type'], order[-1]['pk']) == (c['type'], c['pk']):
            continue
        order.append(c); total += (c.get('dur') or 60)
    return order


@shared_task
def fill_slot(slot_id, append=True):
    """Füllt EINEN Slot aus der Bibliothek (nach seinen Mischregeln) und hängt ihn an den Sendeplan."""
    from .models import ProgramSlot, Track, SpokenContent, PlaylistEntry
    from . import scheduler
    slot = ProgramSlot.objects.filter(pk=slot_id).first()
    if not slot:
        return 'fill_slot: Slot nicht gefunden'
    order = _build_slot_order(slot)
    if not order:
        return f'fill_slot: keine passenden Inhalte für „{slot.name}"'
    pos = (PlaylistEntry.objects.order_by('-position').values_list('position', flat=True).first()) or 0
    created = 0
    for c in order:
        pos += 1
        e = PlaylistEntry(status='queued', manual=False, position=pos, kind=c['kind'])
        if c['type'] == 'track':
            e.track = Track.objects.filter(pk=c['pk']).first()
        else:
            e.spoken = SpokenContent.objects.filter(pk=c['pk']).first()
        if e.content:
            e.save(); created += 1
    scheduler.renumber()
    return f'fill_slot „{slot.name}": {created} Einträge angehängt'


@shared_task
def plan_day(replace=True):
    """Plant den ganzen Tag: füllt ALLE aktiven Slots in Zeit-Reihenfolge aus der Bibliothek."""
    from .models import ProgramSlot, PlaylistEntry
    if replace:
        PlaylistEntry.objects.filter(status='queued').delete()
    slots = list(ProgramSlot.objects.filter(is_active=True).order_by('start_time', 'order'))
    if not slots:
        return 'plan_day: keine aktiven Slots'
    total = 0
    for s in slots:
        r = fill_slot(s.pk, append=True)
        try:
            total += int(r.split(':')[1].split()[0])
        except Exception:
            pass
    return f'plan_day: {len(slots)} Slots gefüllt, ~{total} Einträge'


ALERT_EMAIL = 'kontakt@naturmacher.de'
ALERT_THROTTLE_H = 6  # pro Problemtyp höchstens alle 6 Stunden mailen


def _radio_alert(key, subject, body):
    """Schickt eine Problem-Mail an den Betreiber (gedrosselt je Problemtyp)."""
    import json as _json
    import time as _time
    from django.conf import settings as _st
    path = os.path.join(_st.MEDIA_ROOT, 'radio', 'alerts.json')
    try:
        data = _json.load(open(path)) if os.path.exists(path) else {}
    except Exception:
        data = {}
    now = _time.time()
    if now - data.get(key, 0) < ALERT_THROTTLE_H * 3600:
        return False
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f'[Naturmacher Radio] {subject}',
            message=(body + '\n\n— Automatische Meldung vom Radio-Wächter '
                     '(https://workloom.de/radio/). Nächste Mail zu diesem Problem '
                     f'frühestens in {ALERT_THROTTLE_H} Stunden.'),
            from_email=None, recipient_list=[ALERT_EMAIL], fail_silently=False)
        data[key] = now
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _json.dump(data, open(path, 'w'))
        logger.warning(f'Radio-Alarm gemailt: {subject}')
        return True
    except Exception as e:
        logger.error(f'Radio-Alarm-Mail fehlgeschlagen: {e}')
        return False


@shared_task
def radio_healthcheck():
    """Wächter: prüft Stream, Sendeplan und Tages-Journal; mailt bei Problemen."""
    from datetime import date as _date
    from django.utils import timezone as _tz
    from zoneinfo import ZoneInfo as _ZI
    from .models import PlaylistEntry, SpokenContent, StationConfig
    problems = []

    # 1) Liquidsoap-Prozess
    import subprocess
    try:
        r = subprocess.run(['pgrep', '-f', 'liquidsoap.*radio.liq'], capture_output=True, timeout=10)
        if r.returncode != 0:
            problems.append(('liquidsoap', 'Stream-Mischer (Liquidsoap) läuft NICHT',
                             'Der Liquidsoap-Prozess ist nicht aktiv — der Sender ist vermutlich stumm.'))
    except Exception:
        pass

    # 2) Icecast-Stream liefert Audio
    try:
        import urllib.request
        req = urllib.request.Request('http://127.0.0.1:8000/radio.mp3', headers={'Range': 'bytes=0-512'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if not resp.read(64):
                raise RuntimeError('leer')
    except Exception as e:
        problems.append(('stream', 'Radio-Stream nicht erreichbar',
                         f'http://127.0.0.1:8000/radio.mp3 liefert kein Audio ({e}).'))

    # 3) Sendeplan fast leer (Sender on air)
    if StationConfig.get().on_air:
        n = PlaylistEntry.objects.filter(status='queued').count()
        if n < 5:
            problems.append(('queue', 'Sendeplan fast leer',
                             f'Nur noch {n} Einträge in der Warteschlange — Auto-Planung prüfen.'))

    # 4) Tages-Journal fehlt deutlich nach Slot-Zeit
    h = _tz.now().astimezone(_ZI('Europe/Berlin')).hour
    ed = None
    if 10 <= h < 14:
        ed = 'Morgenausgabe'
    elif 15 <= h < 20:
        ed = 'Mittagsausgabe'
    elif h >= 21:
        ed = 'Abendausgabe'
    if ed and not SpokenContent.objects.filter(
            kind='news', air_date=_date.today(), status='generated',
            title__contains=ed).exists():
        problems.append(('journal', f'Journal-{ed} fehlt',
                         f'Die heutige {ed} des Naturmacher-Journals wurde nicht erstellt — '
                         'die News-Slots nutzen den Saisonales-Fallback. Bitte Logs prüfen.'))

    for key, subject, body in problems:
        _radio_alert(key, subject, body)
    return f'healthcheck: {len(problems)} Problem(e)' if problems else 'healthcheck: alles ok'


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_news(self, only_if_missing=False):
    """
    Recherchiert aktuelle News zu den konfigurierten Themen (Gemini-Grounding),
    fasst sie per GLM 5.1 zu einem vertonten Tages-Journal zusammen (3 Ausgaben/Tag).
    only_if_missing=True: läuft nur, wenn die aktuelle Tages-Ausgabe noch fehlt
    (Nachzügler-Check). Bei Fehlern: automatisch bis zu 3 Wiederholungen.
    """
    from datetime import date as _date
    from .models import StationConfig, SpokenContent

    if only_if_missing:
        from django.utils import timezone as _tzg
        from zoneinfo import ZoneInfo as _ZIg
        _hg = _tzg.now().astimezone(_ZIg('Europe/Berlin')).hour
        _edg = 'Morgenausgabe' if _hg < 11 else ('Mittagsausgabe' if _hg < 17 else 'Abendausgabe')
        if SpokenContent.objects.filter(
                kind='news', air_date=_date.today(), status='generated',
                title__contains=_edg).exists():
            return f'fetch_news: {_edg} existiert bereits — kein Nachzügler nötig'
    from . import glm, news

    topics = [t.strip() for t in (StationConfig.get().news_topics or '').splitlines() if t.strip()]
    if not topics:
        return 'fetch_news: keine Themen konfiguriert'

    SpokenContent.objects.filter(kind='news', status='draft').delete()  # nur die aktuellsten behalten
    created = 0
    for topic in topics[:8]:
        raw = news.search_topic(topic)
        if not raw:
            continue
        try:
            text = glm.glm_chat(
                f'Fasse die folgenden aktuellen Meldungen zum Thema "{topic}" zu einem kurzen, '
                f'radiotauglichen Nachrichtenblock auf Deutsch zusammen (3–5 Sätze, sachlich, zum '
                f'Vorlesen, ohne Quellenangaben oder URLs):\n\n{raw}\n\nGib nur den fertigen Vorlesetext zurück.',
                system='Du bist Nachrichtenredakteur eines Radiosenders.', max_tokens=600).strip()
        except Exception as e:
            logger.warning(f'fetch_news: GLM-Zusammenfassung fehlgeschlagen ({e}), nutze Rohtext')
            text = raw
        sc = SpokenContent(kind='news', title=f'News: {topic}'[:200], description=topic[:300],
                           text=(text or raw).strip(), voice='', air_date=_date.today(), status='draft')
        sc.save()
        created += 1
    # --- Tages-Journal: alle Themen zu EINEM vertonten Beitrag bündeln ------
    journal = ''
    try:
        drafts = list(SpokenContent.objects.filter(kind='news', status='draft').order_by('pk'))
        today = _date.today()
        if drafts:
            from .models import Rubrik as _Rb
            combined = '\n\n'.join(f'[{d.description}]\n{d.text}' for d in drafts)
            jt = glm.glm_chat(
                'Forme aus den folgenden Themenblöcken ein zusammenhängendes, radiotaugliches '
                '"Naturmacher-Journal" (ca. 90 Sekunden Vorlesezeit, etwa 200 bis 230 Wörter): '
                'freundlicher Einstieg ("Willkommen zum Naturmacher-Journal"), die wichtigsten '
                '3 bis 5 Meldungen fließend verbunden, kurzer warmer Abschluss. Sachlich und '
                'freundlich, zum Vorlesen, keine URLs oder Quellenangaben:\n\n' + combined,
                system='Du bist Nachrichtenredakteur eines familienfreundlichen Radiosenders.',
                max_tokens=900).strip()
            # Tagesnews/Journal hat eine EIGENE Rubrik 'journal' (getrennt von der
            # saisonalen/zeitlosen 'news'-Rubrik). Fallback auf 'news' für Altbestand.
            r = _Rb.objects.filter(key='journal').first() or _Rb.objects.filter(key='news').first()
            voice = (r.voice if (r and r.voice and not r.voice.startswith('piper')) else '') or 'edge-de-DE-ConradNeural'
            _gm = (r.tts_model.strip() if (r and r.tts_model) else '') or None
            mp3 = _synthesize(jt, voice, kind='news', gemini_model=_gm)
            mp3 = _prepend_news_intro(mp3)  # festes Intro (Jingle) voranstellen
            from django.utils import timezone as _tz2
            from zoneinfo import ZoneInfo as _ZI
            _h = _tz2.now().astimezone(_ZI('Europe/Berlin')).hour
            _ed = 'Morgenausgabe' if _h < 11 else ('Mittagsausgabe' if _h < 17 else 'Abendausgabe')
            sc = SpokenContent(kind='news',
                               title=f'Naturmacher-Journal vom {today.strftime("%d.%m.%Y")} – {_ed}',
                               description='Tagesaktuelle Meldungen (automatisch recherchiert)',
                               text=jt, voice=voice, air_date=today, status='draft')
            sc.save()
            sc.audio_file.save(f'spoken_news_{sc.pk}.mp3', ContentFile(mp3), save=False)
            sc.duration_sec = _probe_duration(sc.audio_file.path)
            sc.status = 'generated'
            try:
                from .models import StationConfig as _SC2
                sc.gen_model = ('edge' if str(voice).startswith('edge-')
                                else (_gm or (_SC2.get().gemini_tts_model or '')))
            except Exception:
                pass
            sc.save(update_fields=['audio_file', 'duration_sec', 'status', 'gen_model'])
            # ältere Journal-Ausgaben aus der Rotation nehmen (nur das frische läuft)
            SpokenContent.objects.filter(kind='news', title__startswith='Naturmacher-Journal') \
                .exclude(pk=sc.pk).update(auto_include=False)
            # bereits eingeplante (noch nicht gespielte) Journal-Einträge auf die frische Ausgabe umbiegen
            try:
                from .models import PlaylistEntry as _PE
                swapped = _PE.objects.filter(
                    status='queued', spoken__kind='news',
                    spoken__title__startswith='Naturmacher-Journal').exclude(spoken=sc).update(spoken=sc)
                if swapped:
                    logger.info(f'fetch_news: {swapped} eingeplante Journal-Slots auf neue Ausgabe getauscht')
            except Exception as _e:
                logger.warning(f'fetch_news: Journal-Tausch fehlgeschlagen: {_e}')
            journal = f' + Journal #{sc.pk} ({sc.duration_sec}s)'
            logger.info(f'fetch_news: Journal #{sc.pk} vertont ({sc.duration_sec}s)')
    except Exception as e:
        logger.warning(f'fetch_news: Journal fehlgeschlagen: {e} — Retry geplant')
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error('fetch_news: Journal endgültig fehlgeschlagen — Evergreen-Fallback greift')
            _radio_alert('journal_fail', 'Journal-Erstellung mehrfach fehlgeschlagen',
                         f'Die Journal-Produktion ist trotz 3 Wiederholungen gescheitert: {e}')

    logger.info(f'fetch_news: {created} News-Entwürfe erstellt' + journal)
    return f'fetch_news: {created} News-Entwürfe erstellt' + journal



@shared_task
def download_entry_video(entry_id, url):
    """Lädt ein gewähltes Pexels-Video herunter und hängt es an den Sendeplan-Eintrag."""
    import requests
    from django.core.files.base import ContentFile
    from .models import PlaylistEntry
    try:
        e = PlaylistEntry.objects.get(pk=entry_id)
    except PlaylistEntry.DoesNotExist:
        return 'entry weg'
    try:
        r = requests.get(url, timeout=120, stream=True)
        data = r.content
        e.video_file.save(f'entry_{entry_id}.mp4', ContentFile(data), save=True)
        logger.info(f'Beitrags-Video gespeichert für Entry #{entry_id} ({len(data)} bytes)')
        return 'ok'
    except Exception as ex:
        logger.warning(f'Video-Download fehlgeschlagen: {ex}')
        return 'fehler'


@shared_task
def gpu_idle_terminate(idle_minutes=5):
    """
    Beendet den Radio-GPU-Pod automatisch, wenn er seit `idle_minutes` nicht
    mehr genutzt wurde (spart Kosten). Network-Volume + Modelle bleiben erhalten;
    der nächste Bedarf erstellt den Pod neu. Überspringt, wenn gpu_busy=True.
    """
    from .models import StationConfig
    from . import musicgen
    from video import tasks as vt
    import runpod

    cfg = StationConfig.get()
    if not cfg.gpu_pod_id or cfg.gpu_busy:
        return 'skip (kein Pod / busy)'
    if cfg.gpu_last_used and (timezone.now() - cfg.gpu_last_used).total_seconds() < idle_minutes * 60:
        return 'skip (kürzlich genutzt)'
    runpod.api_key = vt.RUNPOD_API_KEY
    try:
        p = runpod.get_pod(cfg.gpu_pod_id)
    except Exception:
        p = None
    if p and p.get('desiredStatus') == 'RUNNING':
        musicgen.terminate_pod()
        logger.info('GPU-Pod wegen Leerlauf automatisch beendet.')
        return 'terminated'
    return 'skip (läuft nicht)'


@shared_task
def nightly_production(music_count=8):
    """
    Nächtlicher Komplettlauf für den Sender:
      1. KI-Musik-Batch (frische Tracks) auf RunPod
      2. Pod stoppen (Kosten sparen)
      3. Wort-Tagespaket (Geschichte + Wissenswertes + Tipp) via GLM+Piper
      4. Sendeplan für den Tag neu bauen

    Läuft als EIN Celery-Beat-Job nachts. Robust: jeder Schritt einzeln
    abgesichert, ein Fehler kippt nicht den ganzen Lauf.
    """
    from . import musicgen, scheduler
    result = {'music': 0, 'spoken': [], 'schedule': 0}

    # 1) Musik
    try:
        r = generate_music_batch(count=music_count)
        result['music'] = (r or {}).get('done', 0)
    except Exception:
        logger.exception('nightly: Musik-Batch fehlgeschlagen')
    # 2) Pod stoppen
    try:
        musicgen.stop_pod()
    except Exception:
        logger.exception('nightly: Pod-Stop fehlgeschlagen')
    # 3) Wort-Tagespaket
    try:
        result['spoken'] = generate_spoken_batch()
    except Exception:
        logger.exception('nightly: Wort-Tagespaket fehlgeschlagen')
    # 4) Sendeplan
    try:
        result['schedule'] = scheduler.build_schedule()
    except Exception:
        logger.exception('nightly: Sendeplan-Bau fehlgeschlagen')
    # 5) Aufräumen (alte Audio/Video-Dateien)
    try:
        result['cleanup'] = cleanup_old_media()
    except Exception:
        logger.exception('nightly: Cleanup fehlgeschlagen')

    logger.info(f'nightly_production fertig: {result}')
    return result


def _cost_note(kind, voice=None, engine=None, model=None, duration_sec=0):
    """Grobe Kostenschätzung des erzeugten Audios als kurzer Text (für die Vorschau)."""
    from . import elevenlabs as el
    eng = (engine or 'lyria').lower()
    if kind in ('music', 'song'):
        if eng == 'minimax':
            ct = {'music-2.6': 15, 'music-2.5+': 10, 'music-2.5': 8, 'music-2.0': 6}.get(model, 12)
            return f'ca. {ct} ct (MiniMax {model or "2.6"})'
        if eng == 'fal':
            from . import fal
            ct = (fal.MUSIC_BY_ID.get(model) or {}).get('price_ct', 3)
            return f'ca. {ct} ct (fal.ai {(model or "").split("/")[-1]})'
        if eng == 'elevenlabs':
            mins = max((duration_sec or 0) / 60.0, 0.5)
            return f'ca. {round(mins * 37)} ct (ElevenLabs Music, ~37 ct/Min – teuerste Option)'
        ct = 4 if (model or '').endswith('clip-preview') else 8
        return f'ca. {ct} ct (Lyria {"Clip" if ct == 4 else "Pro"})'
    if kind in ('effekt', 'jingle'):
        # ElevenLabs Sound-Effekte ~ wenige Cent (dauerabhängig), zählen aufs Guthaben
        ct = max(1, round((duration_sec or 4) * 0.8))
        return f'ca. {ct} ct (ElevenLabs-Effekt, zählt aufs Guthaben)'
    # Sprache
    if voice and str(voice).startswith('fal:'):
        from . import fal
        mid = voice.split(':', 1)[1]
        rate = (fal.SPEECH_BY_ID.get(mid) or {}).get('price_min', 6)
        mins = (duration_sec or 0) / 60.0
        return f'ca. {round(mins * rate, 1)} ct (fal.ai {mid.split("/")[-1]}, {round(mins, 1)} Min)'
    if el.is_eleven_voice(voice):
        return 'ElevenLabs (zählt aufs Guthaben – siehe Anzeige)'
    mins = (duration_sec or 0) / 60.0
    rate = 3.0 if model == 'pro' else 1.5
    return f'ca. {round(mins * rate, 1)} ct (Gemini {"Pro" if model == "pro" else "Flash"}, {round(mins, 1)} Min)'


def _background_bed_mp3(bg_track_id=None):
    """Wählt eine Melodie aus der Bibliothek als Hintergrund (MP3-Bytes) oder None.
    Mit bg_track_id ein bestimmtes Stück, sonst bevorzugt ein zufälliges Instrumental."""
    qs = Track.objects.filter(is_active=True).exclude(audio_file='').exclude(source='elevenlabs')
    t = qs.filter(pk=bg_track_id).first() if bg_track_id else None
    if t is None:
        t = qs.filter(lyrics='').order_by('?').first() or qs.order_by('?').first()
    if not t:
        return None
    try:
        with t.audio_file.open('rb') as fh:
            return fh.read()
    except Exception as e:
        logger.warning(f'Hintergrund-Track nicht lesbar: {e}')
        return None


def _apply_background(mp3, bg_music, bg_volume, bg_track_id):
    """Mischt – falls gewünscht – eine leise Hintergrundmelodie unter die Sprache."""
    if not bg_music:
        return mp3
    try:
        bed = _background_bed_mp3(bg_track_id)
        if not bed:
            logger.info('Hintergrundmusik gewünscht, aber keine passende Melodie in der Bibliothek.')
            return mp3
        from . import soundscape
        return soundscape.mix_background(mp3, bed, volume=bg_volume or 0.12)
    except Exception as e:
        logger.warning(f'Hintergrundmusik übersprungen: {e}')
        return mp3


@shared_task
def compose_generate_task(kind='wissen', text='', voice=None, title=None, duration_sec=300,
                          voice2=None, speaker_a=None, speaker_b=None, style=None, seconds=None,
                          engine=None, bg_music=False, bg_volume=0.12, bg_track_id=None,
                          mm_model=None, lyria_model=None, gemini_model=None, eleven_model=None,
                          fal_model=None, tags='', auto=True):
    """
    Studio-Erzeugung EINES Beitrags:
      - kind 'music': GLM macht aus der Beschreibung einen MusicGen-Prompt,
        MusicGen erzeugt den Track.
      - sonst (Sprache): der gelieferte Text wird direkt von Piper vertont.
    Gibt dict {type, pk, kind, title, audio_url} zurück (für Vorschau + Übernehmen).
    """
    import uuid
    from datetime import date as _date
    from .models import Track, SpokenContent, Rubrik
    from . import glm, musicgen
    from video import tts

    # Wird eine Musik-Rubrik erzeugt und ist kein Engine explizit gewählt,
    # so greift die in der Rubrik hinterlegte Musik-Engine (tts_model).
    if not engine:
        _rb = Rubrik.objects.filter(key=kind).first()
        if _rb and _rb.rtype == 'music' and _rb.tts_model in ('lyria', 'minimax', 'elevenlabs', 'fal'):
            engine = _rb.tts_model
        if _rb and _rb.rtype == 'music' and _rb.target_sec and (not duration_sec or duration_sec == 300):
            duration_sec = _rb.target_sec
    # Leerer Prompt bei Rubrik-Erzeugung (z.B. Musik-Pin ohne Text) -> aus Rubrik/Default ableiten
    if not (text or '').strip():
        _rbt = Rubrik.objects.filter(key=kind).first()
        derived = ((_rbt.task_prompt or _rbt.label) if _rbt else '') or ''
        if kind in ('music', 'song') and not derived.strip():
            from .models import StationConfig as _SC
            derived = _SC.get().default_mood
        text = derived or text

    if kind == 'effekt':
        # Engine wählbar: ElevenLabs (kurzer Sound-Effekt) oder Lyria 3 Clip (30s-Musik-Jingle)
        eng = (engine or 'elevenlabs').lower()
        if eng == 'lyria':
            from . import lyria
            dur = 30
            data = lyria.generate(prompt=text, instrumental=True, duration_sec=dur,
                                  model='lyria-3-clip-preview')
            src = 'lyria'
            cost = _cost_note('music', engine='lyria', model='lyria-3-clip-preview')
        else:
            from . import elevenlabs as el
            dur = max(1, min(int(seconds or 4), el.MAX_SECONDS))
            data = el.generate_sfx(text, duration_sec=dur)
            src = 'elevenlabs'
            cost = _cost_note('effekt', duration_sec=dur)
        # mood='jingle' markiert den Eintrag als Effekt/Jingle (engine-unabhängig für die Bibliothek)
        track = Track(title=(title or text.strip()[:60] or 'Sound-Effekt'),
                      mood='jingle', source=src, prompt=text[:500],
                      description=text[:300], duration_sec=dur,
                      gen_model=('lyria-3-clip-preview' if eng == 'lyria' else ''),
                      is_active=auto, tags=(tags or ''))
        track.audio_file.save(f'sfx_{uuid.uuid4().hex[:8]}.mp3', ContentFile(data), save=True)
        return {'type': 'track', 'pk': track.pk, 'kind': 'effekt', 'title': track.title,
                'audio_url': track.audio_file.url, 'cost': cost}

    if kind == 'music':
        # Instrumental (ohne Stimme) — Engine wählbar: MiniMax (günstig) oder Lyria.
        dur = max(20, min(int(duration_sec or 180), 300))
        eng = (engine or 'lyria').lower()
        if eng == 'minimax':
            from . import minimax
            data = minimax.generate(prompt=text, instrumental=True, model=mm_model)
            src = 'minimax'
        elif eng == 'elevenlabs':
            from . import elevenlabs as el
            data = el.generate_music(prompt=text, instrumental=True, duration_sec=dur)
            src = 'elevenmusic'
        elif eng == 'fal':
            from . import fal
            data = fal.music(fal_model, prompt=text, instrumental=True, duration_sec=dur)
            src = 'fal'
        else:
            from . import lyria
            data = lyria.generate(prompt=text, instrumental=True, duration_sec=dur, model=lyria_model)
            src = 'lyria'
        _mm = mm_model if eng == 'minimax' else (fal_model if eng == 'fal' else (lyria_model if eng == 'lyria' else ''))
        track = Track(title=(title or glm.make_title(text) or text.strip().split('.')[0][:60] or 'Instrumental'),
                      mood=text[:120], source=src, prompt=text[:500],
                      description=text[:300], duration_sec=dur, gen_model=(_mm or ''),
                      is_active=auto, tags=(tags or ''))
        track.audio_file.save(f'music_{uuid.uuid4().hex[:8]}.mp3', ContentFile(data), save=True)
        _cm = mm_model if eng == 'minimax' else (fal_model if eng == 'fal' else lyria_model)
        return {'type': 'track', 'pk': track.pk, 'kind': 'music', 'title': track.title,
                'audio_url': track.audio_file.url,
                'cost': _cost_note('music', engine=eng, model=_cm, duration_sec=dur)}

    if kind == 'song':
        # Musik MIT Gesang — Engine wählbar: Google Lyria 3 Pro oder MiniMax.
        import re as _re
        def _clean_song_title(lyr, fb='Lied'):
            """Titel aus dem Liedtext – überspringt Struktur-Marker wie [verse]/(chorus)."""
            for line in (lyr or '').splitlines():
                s = line.strip()
                if not s:
                    continue
                if _re.fullmatch(r'[\[\(].*[\]\)]', s):   # reine Marker-Zeile
                    continue
                s = _re.sub(r'^[\[\(][^\]\)]*[\]\)]\s*', '', s).strip()  # führenden Marker entfernen
                if s:
                    return s[:60]
            return fb
        prompt = (style or '').strip() or 'warm upbeat german pop, clear female vocals, acoustic guitar'
        lyrics = text
        dur = max(20, min(int(duration_sec or 150), 180))
        eng = (engine or 'lyria').lower()
        if eng == 'minimax':
            from . import minimax
            data = minimax.generate(prompt=prompt, lyrics=lyrics, instrumental=False, model=mm_model)
            src = 'minimax'
        elif eng == 'elevenlabs':
            from . import elevenlabs as el
            data = el.generate_music(prompt=f'{prompt}. Lyrics:\n{lyrics}', instrumental=False, duration_sec=dur)
            src = 'elevenmusic'
        elif eng == 'fal':
            from . import fal
            data = fal.music(fal_model, prompt=prompt, lyrics=lyrics, instrumental=False, duration_sec=dur)
            src = 'fal'
        else:
            from . import lyria
            data = lyria.generate(prompt=prompt, lyrics=lyrics, instrumental=False, duration_sec=dur, model=lyria_model)
            src = 'lyria'
        _sm = mm_model if eng == 'minimax' else (fal_model if eng == 'fal' else (lyria_model if eng == 'lyria' else ''))
        track = Track(title=(title or _clean_song_title(lyrics, 'Lied')),
                      mood=prompt[:120], source=src, prompt=f'{prompt} || {lyrics[:500]}',
                      description=prompt[:300], lyrics=lyrics, duration_sec=dur, gen_model=(_sm or ''),
                      is_active=auto, tags=(tags or ''))
        track.audio_file.save(f'song_{uuid.uuid4().hex[:8]}.mp3', ContentFile(data), save=True)
        _cs = mm_model if eng == 'minimax' else (fal_model if eng == 'fal' else lyria_model)
        return {'type': 'track', 'pk': track.pk, 'kind': 'song', 'title': track.title,
                'audio_url': track.audio_file.url,
                'cost': _cost_note('song', engine=eng, model=_cs, duration_sec=dur)}

    if kind == 'dialog':
        from . import gemini_tts
        a_name = (speaker_a or 'Anna').strip()[:30]
        b_name = (speaker_b or 'Tom').strip()[:30]
        va = voice if gemini_tts.is_gemini_voice(voice) else 'gemini-Kore'
        vb = voice2 if gemini_tts.is_gemini_voice(voice2) else 'gemini-Puck'
        air = _date.today()
        title = (title or glm.make_title(text) or text.strip().split(':')[-1].split('.')[0][:60] or 'Dialog')
        sc = SpokenContent(kind='dialog', title=title, text=text,
                           voice=f'{va}+{vb}', air_date=air, status='draft',
                           auto_include=auto, tags=(tags or ''))
        sc.save()
        mp3 = gemini_tts.synth_dialog(text, speakers=[(a_name, va), (b_name, vb)], model=gemini_model)
        mp3 = _apply_background(mp3, bg_music, bg_volume, bg_track_id)
        sc.audio_file.save(f'manual_dialog_{sc.pk}.mp3', ContentFile(mp3), save=False)
        sc.duration_sec = _probe_duration(sc.audio_file.path)
        sc.status = 'generated'
        sc.save(update_fields=['audio_file', 'duration_sec', 'status'])
        glm.remember_topic('dialog', sc.title)
        return {'type': 'spoken', 'pk': sc.pk, 'kind': 'dialog', 'title': sc.title,
                'audio_url': sc.audio_file.url,
                'cost': _cost_note('dialog', voice=va, model=gemini_model, duration_sec=sc.duration_sec)}

    voice = voice or VOICE_BY_KIND.get(kind, 'gemini-Charon')
    air = None if kind in EVERGREEN_KINDS else _date.today()
    title = (title or glm.make_title(text) or text.strip().split('.')[0][:60] or kind.title())
    sc = SpokenContent(kind=kind, title=title, text=text, voice=voice, air_date=air, status='draft',
                       auto_include=auto, tags=(tags or ''))
    sc.save()
    mp3 = _synthesize(text, voice, kind=kind, gemini_model=gemini_model, eleven_model=eleven_model)
    mp3 = _apply_background(mp3, bg_music, bg_volume, bg_track_id)
    sc.audio_file.save(f'manual_{kind}_{sc.pk}.mp3', ContentFile(mp3), save=False)
    sc.duration_sec = _probe_duration(sc.audio_file.path)
    sc.status = 'generated'
    sc.save(update_fields=['audio_file', 'duration_sec', 'status'])
    glm.remember_topic(kind, sc.title)
    return {'type': 'spoken', 'pk': sc.pk, 'kind': kind, 'title': sc.title,
            'audio_url': sc.audio_file.url,
            'cost': _cost_note(kind, voice=voice, model=gemini_model, duration_sec=sc.duration_sec)}


@shared_task
def generate_pin_content(pin_id):
    """Erzeugt den selbst-definierten Beitrag eines compose-Pins (Spec wie im Studio)
    und hängt ihn als festen Beitrag an den Pin. Danach läuft der Pin wie ein
    fester Track/Wort-Beitrag zu seiner Zeit."""
    from .models import ScheduledItem
    pin = ScheduledItem.objects.filter(pk=pin_id).first()
    if not pin:
        return 'pin weg'
    spec = dict(pin.gen_spec or {})
    pin.gen_status = 'generating'
    pin.save(update_fields=['gen_status'])
    try:
        res = compose_generate_task(**spec)
    except Exception as e:
        logger.warning(f'generate_pin_content #{pin_id} fehlgeschlagen: {e}')
        pin.gen_status = 'failed'
        pin.save(update_fields=['gen_status'])
        return f'fehler: {e}'
    if res and res.get('type') == 'track':
        pin.track_id = res['pk']; pin.spoken = None; pin.mode = 'pinned_track'
    elif res and res.get('type') == 'spoken':
        pin.spoken_id = res['pk']; pin.track = None; pin.mode = 'pinned_spoken'
    else:
        pin.gen_status = 'failed'
        pin.save(update_fields=['gen_status'])
        return 'kein ergebnis'
    pin.gen_status = 'done'
    pin.save()
    return res.get('pk')


@shared_task
def materialize_day_task(target_date_iso=None, replace=False, generate=True, next_day=False):
    """Materialisiert den Tagesplan (Pins + Slots) asynchron in die Queue.
    next_day=True (nächtlicher Beat): plant den FOLGETAG inkl. Nachtprogramm voraus."""
    from datetime import date as _date, timedelta as _td
    from . import scheduler
    if next_day and not target_date_iso:
        target_date_iso = (_date.today() + _td(days=1)).isoformat()
    d = _date.fromisoformat(target_date_iso) if target_date_iso else None
    made = scheduler.materialize_day(d, replace=replace, generate=generate)
    return f'materialize_day_task: {made} Einträge für {target_date_iso or "heute"}' 


@shared_task
def enforce_pins():
    """Wendet FÄLLIGE Timeline-Pins automatisch an (läuft jede Minute):
      - anchor: sanft – der Beitrag wird als NÄCHSTES gespielt (kein Abschneiden)
      - exact:  sofort – schiebt den Beitrag nach vorn UND überspringt den
                laufenden Track (Liquidsoap-Telnet sendeplan.flush_and_skip)
    rubrik_gen ohne vorhandenen Beitrag: im Hintergrund erzeugen (für nächste Runde).
    So laufen Grundprogramm (auto_program) + Pins komplett hands-off."""
    import socket
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    from django.db.models import F
    from .models import ScheduledItem, PlaylistEntry
    from . import scheduler
    # Übergangs-/Crossfade-Einstellungen an Liquidsoap re-synchronisieren
    # (damit sie auch nach einem Liquidsoap-Neustart wieder gesetzt sind)
    try:
        scheduler.apply_mix_settings()
    except Exception:
        pass
    now = _dt.now(ZoneInfo('Europe/Berlin'))
    today = now.date()
    fired = 0
    for pin in ScheduledItem.objects.filter(is_active=True):
        if not pin.applies_on(today):
            continue
        if pin.start_time.hour != now.hour or pin.start_time.minute != now.minute:
            continue
        res = scheduler._resolve_pin(pin, today, generate=False)
        if not res:
            # „erzeugen"-Pin ohne Inhalt: im Hintergrund anstoßen (für nächstes Mal)
            if pin.mode == 'rubrik_gen' and pin.rubrik_key:
                try:
                    if pin.rubrik_key in ('story', 'wissen', 'tip', 'news', 'kreativ'):
                        generate_spoken_content.delay(kind=pin.rubrik_key, topic=(pin.topic or None), air_date=today)
                    else:
                        compose_generate_task.delay(kind=pin.rubrik_key, text=(pin.topic or ''))
                except Exception:
                    pass
            continue
        # ANKER-Pins (sanft) werden seit der 24/7-Tagesplanung bereits von
        # materialize_day in die Warteschlange eingeplant. Der Wächter darf sie
        # daher NICHT zusätzlich einschieben — sonst läuft der Beitrag doppelt
        # (einmal aus dem Plan, einmal vom Wächter). Nur 'exact'-Pins drängeln.
        if pin.enforce != 'exact':
            continue
        kind, track, spoken, dur = res
        # bereits laufend oder schon ganz vorne? -> nicht doppelt einfügen
        cur = PlaylistEntry.objects.filter(status='playing').first()
        head = PlaylistEntry.objects.filter(status='queued').order_by('position').first()
        def _same(e):
            return e and ((track and e.track_id == track.pk) or (spoken and e.spoken_id == spoken.pk))
        if _same(cur) or _same(head):
            continue
        PlaylistEntry.objects.filter(status='queued').update(position=F('position') + 1)
        PlaylistEntry.objects.create(position=0, kind=kind, track=track, spoken=spoken,
                                     status='queued', manual=True, scheduled_time=_dt.now(ZoneInfo('UTC')))
        if pin.enforce == 'exact':
            # flush_and_skip: bricht den laufenden Titel ab UND verwirft den von
            # Liquidsoap bereits vorgepufferten nächsten Request -> der nächste
            # Abruf von /radio/next/ liefert direkt unseren Pin (Position 0).
            # (Achtung: 'sendeplan.skip' existiert NICHT - war der Bug, weshalb
            # „exakt" nie unterbrochen hat.)
            try:
                s = socket.create_connection(('127.0.0.1', 1234), timeout=4)
                s.sendall(b'sendeplan.flush_and_skip\nquit\n')
                s.settimeout(2)
                try:
                    while s.recv(256):
                        pass
                except Exception:
                    pass
                s.close()
            except Exception:
                pass
        fired += 1
    return fired


@shared_task
def assistant_answer_task(message, history):
    """Erzeugt die Antwort des schwebenden Radio-Assistenten im Hintergrund.
    Ausgelagert in Celery, damit die Antwort einen Seiten-Reload übersteht."""
    from . import views
    return views.assistant_answer(message, history)


@shared_task
def topup_queue():
    """Auffüllung (alle 15 Min): hält >= 10 Stunden Vorlauf in der Warteschlange.
    Idempotent über scheduler.ensure_queue_filled -> nie leer, nie doppelt."""
    from .models import StationConfig
    from . import scheduler
    if not StationConfig.get().on_air:
        return "topup: nicht on air"
    made = scheduler.ensure_queue_filled(min_hours=10, max_days=3)
    return f"topup: +{made} angehängt" if made else "topup: Vorlauf ausreichend"


@shared_task
def plan_ahead():
    """Nächtlich: garantiert den Folgetag komplett vorausgeplant (>= 28 h Vorlauf)."""
    from . import scheduler
    return f"plan_ahead: +{scheduler.ensure_queue_filled(min_hours=28, max_days=3)}"
    # Reicht bis zum Tagesende, aber Mitternacht naht? -> Folgetag dranhängen
    made_next = 0
    if t.astimezone(B).hour >= 21 or rest_h < 1:
        made_next = scheduler.materialize_day(now.astimezone(B).date() + timedelta(days=1), replace=False, generate=False)
    return f"topup: +{made_today} heute, +{made_next} morgen (war {rest_h:.1f}h)"
