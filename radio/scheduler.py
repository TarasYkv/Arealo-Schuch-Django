"""
Sendeplan-Builder: füllt die rollierende Warteschlange (PlaylistEntry).

Erste Ausbaustufe: musik-dominanter Plan aus den vorhandenen Tracks
(am wenigsten gespielte zuerst → faire Rotation), angereichert um bereits
erzeugte Vorlese-Inhalte (News/Geschichte/Tipp), die für heute geplant sind.
Jingles/Spots werden eingehängt, sobald solche Assets existieren.

Die geschätzte Sendezeit ergibt sich kumulativ aus Reihenfolge + Dauer ab
'jetzt'. Der Superuser kann danach in der Timeline-App umsortieren/ersetzen.
"""
from datetime import timedelta, datetime, time as _time
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import Track, SpokenContent, PlaylistEntry, ContentTag, StationConfig

BERLIN = ZoneInfo('Europe/Berlin')
UTC = ZoneInfo('UTC')


def _season_map():
    """Aktive, exklusive Tags mit Saison-Fenster: {name: ContentTag}."""
    return {t.name: t for t in ContentTag.objects.filter(is_active=True, exclusive=True)
            if t.start_md and t.end_md}


def _seasonal_ok(tags_csv, on_date, smap=None):
    """False, wenn ein exklusiver Saison-Tag des Inhalts außerhalb seines Fensters liegt."""
    if not (tags_csv or '').strip():
        return True
    if smap is None:
        smap = _season_map()
    if not smap:
        return True
    for name in [x.strip().lower() for x in tags_csv.split(',') if x.strip()]:
        tag = smap.get(name)
        if tag and not tag.is_in_season(on_date):
            return False
    return True


def _season_boost(tags_csv, on_date, smap=None):
    """Gewichtung eines Inhalts im Automatik-Pool: höchster Boost seiner Tags,
    deren Saison GERADE aktiv ist (1 = normal, max 10). Pro Tag einstellbar."""
    if not (tags_csv or '').strip():
        return 1
    if smap is None:
        smap = _season_map()
    w = 1
    for name in [x.strip().lower() for x in tags_csv.split(',') if x.strip()]:
        tag = smap.get(name)
        if tag and tag.is_in_season(on_date):
            b = getattr(tag, 'boost', 1) or 1
            if b > w:
                w = b
    return min(int(w), 10)


def _auto_eligible(obj, on_date, smap=None):
    """Darf obj (Track/SpokenContent) automatisch eingeplant werden (Ausschluss + Saison)?"""
    if isinstance(obj, Track):
        if not obj.is_active:
            return False
    else:  # SpokenContent
        if not getattr(obj, 'auto_include', True):
            return False
        if obj.status != 'generated' or not obj.audio_file:
            return False
    return _seasonal_ok(getattr(obj, 'tags', ''), on_date, smap)


# Kadenzen: nach wie vielen Musiktiteln ein Element eingestreut wird
SPOKEN_EVERY = 4    # verbrauchbarer Tages-Wortbeitrag (News/Geschichte/Tipp/Wissen)
JINGLE_EVERY = 6    # Senderkennung (rotierend, wiederverwendet)
AD_EVERY = 12       # Marken-Spot / Mitmach (rotierend, wiederverwendet)


@transaction.atomic
def build_schedule(target_count=40):
    """
    Baut den Sendeplan neu auf (ersetzt alle noch nicht gespielten Einträge).

    Musik ist der Teppich; darüber werden eingestreut:
    - verbrauchbare Tages-Wortbeiträge (kind story/wissen/tip/news, air_date=heute)
    - rotierende Jingles und Marken-Spots (evergreen, wiederverwendet)
    Gibt die Anzahl erzeugter Einträge zurück.
    """
    PlaylistEntry.objects.filter(status='queued').delete()

    tracks = list(
        Track.objects.filter(is_active=True)
        .exclude(source='elevenlabs').exclude(mood='jingle')  # keine Sound-Effekte/Jingles als Musik
        .order_by('play_count', 'created_at')
    )
    if not tracks:
        return 0

    today = timezone.localdate()
    smap = _season_map()
    tracks = [t for t in tracks if _seasonal_ok(t.tags, today, smap)]
    if not tracks:
        return 0
    spoken_pool = list(
        SpokenContent.objects.filter(status='generated', air_date=today, auto_include=True)
        .exclude(audio_file='').exclude(kind__in=['jingle', 'ad', 'news'])  # news NUR über die festen Slots
        .order_by('created_at')
    )
    jingles = list(
        SpokenContent.objects.filter(kind='jingle', status='generated', auto_include=True)
        .exclude(audio_file='').order_by('created_at')
    )
    ads = list(
        SpokenContent.objects.filter(kind='ad', status='generated', auto_include=True)
        .exclude(audio_file='').order_by('created_at')
    )
    spoken_pool = [s for s in spoken_pool if _seasonal_ok(s.tags, today, smap)]
    jingles = [j for j in jingles if _seasonal_ok(j.tags, today, smap)]
    ads = [a for a in ads if _seasonal_ok(a.tags, today, smap)]

    entries = []
    _base = PlaylistEntry.objects.aggregate(m=Max('position'))['m']
    state = {'pos': (_base + 1) if _base is not None else 0, 't': timezone.now()}

    def add(kind, track=None, spoken=None, dur=60):
        entries.append(PlaylistEntry(
            position=state['pos'], kind=kind, track=track, spoken=spoken,
            scheduled_time=state['t'], status='queued',
        ))
        state['pos'] += 1
        state['t'] += timedelta(seconds=dur or 60)

    cfg = StationConfig.get()
    spoken_every = cfg.std_music_per_talk or SPOKEN_EVERY
    jingle_every = cfg.std_jingle_every or 0
    ad_every = max(1, cfg.std_ad_every_min // 3) if cfg.std_ad_every_min else 0

    ti = ji = ai = music_count = 0
    while len(entries) < target_count:
        track = tracks[ti % len(tracks)]
        ti += 1
        add('music', track=track, dur=track.duration_sec or 120)
        music_count += 1
        if len(entries) >= target_count:
            break

        if jingles and jingle_every and music_count % jingle_every == 0:
            j = jingles[ji % len(jingles)]
            ji += 1
            add('jingle', spoken=j, dur=max(j.duration_sec, 5))
            if len(entries) >= target_count:
                break

        if spoken_pool and spoken_every and music_count % spoken_every == 0:
            sp = spoken_pool.pop(0)
            kind = sp.kind if sp.kind in dict(PlaylistEntry.KIND) else 'tip'
            add(kind, spoken=sp, dur=max(sp.duration_sec, 30))
            if len(entries) >= target_count:
                break

        if ads and ad_every and music_count % ad_every == 0:
            a = ads[ai % len(ads)]
            ai += 1
            add('ad', spoken=a, dur=max(a.duration_sec, 15))

    PlaylistEntry.objects.bulk_create(entries)
    return len(entries)


@transaction.atomic
def renumber():
    """Positions-Lücken nach Umsortieren/Löschen schließen (0..n)."""
    for i, e in enumerate(PlaylistEntry.objects.filter(status='queued').order_by('position')):
        if e.position != i:
            PlaylistEntry.objects.filter(pk=e.pk).update(position=i)


def _rubrik_is_music(rubrik_key):
    """Ist die Rubrik musik-basiert (Track) oder sprach-basiert (SpokenContent)?"""
    from .models import Rubrik
    r = Rubrik.objects.filter(key=rubrik_key).first()
    if r:
        return r.rtype == 'music'
    return rubrik_key in ('music', 'song', 'effekt', 'jingle')


def _pin_resolvable(pin, on_date, smap=None):
    """Trocken-Prüfung: gibt es für diesen Pin am Tag einen abspielbaren Beitrag?"""
    if pin.mode == 'compose':
        return pin.gen_status == 'done'
    if pin.mode == 'pinned_track':
        return bool(pin.track and pin.track.audio_file)
    if pin.mode == 'pinned_spoken':
        return bool(pin.spoken and pin.spoken.audio_file)
    if pin.mode == 'rubrik_gen':
        return True  # zur Not wird erzeugt
    if smap is None:
        smap = _season_map()
    if _rubrik_is_music(pin.rubrik_key):
        for t in Track.objects.filter(is_active=True).exclude(audio_file=''):
            if _auto_eligible(t, on_date, smap):
                return True
        return False
    for s in (SpokenContent.objects.filter(kind=pin.rubrik_key, status='generated', auto_include=True)
              .exclude(audio_file='')):
        if _seasonal_ok(s.tags, on_date, smap):
            return True
    return False


def projected_timeline(target_date, now=None):
    """
    Voraussichtliche Timeline eines Tages: gemischt aus
    - REAL: bereits in der Queue stehende Einträge (kumuliert ab jetzt)
    - THEORETISCH: noch nicht materialisierte Pins + Auto-Blöcke des Tages
      (nur NACH dem letzten realen Eintrag, um Doppelung zu vermeiden).
    Liefert nach Zeit sortierte dicts.
    """
    from .models import ScheduledItem, ProgramSlot
    now = now or timezone.now()
    smap = _season_map()
    rows = []

    current = (PlaylistEntry.objects.filter(status='playing')
               .select_related('track', 'spoken').order_by('-started_at').first())
    queued = list(PlaylistEntry.objects.filter(status='queued')
                  .select_related('track', 'spoken').order_by('position'))
    t = now
    if current and current.started_at:
        rest = (current.duration_sec or 0) - (now - current.started_at).total_seconds()
        if rest > 0:
            t = now + timedelta(seconds=rest)
    last_real = None
    real_marks = []   # (Zeit, Rubrik-Key, track_id, spoken_id) für Pin-Dubletten-Abgleich
    for e in queued:
        pe = t.astimezone(BERLIN)
        real_marks.append((pe, (e.spoken.kind if e.spoken_id and e.spoken else ('music' if e.track_id else e.kind)),
                           e.track_id, e.spoken_id))
        if pe.date() == target_date:
            try:
                au = e.audio_url or ''
            except Exception:
                au = ''
            rows.append({'time': pe.isoformat(), 'time_str': pe.strftime('%H:%M'),
                         'kind': e.kind, 'title': e.title or '—', 'source': 'real',
                         'pk': e.pk, 'resolved': True, 'enforce': '', 'tags': '',
                         'audio_url': au})
        last_real = t
        t += timedelta(seconds=e.duration_sec or 120)

    cutoff = (last_real or now).astimezone(BERLIN)
    now_b = now.astimezone(BERLIN)

    for pin in ScheduledItem.objects.filter(is_active=True):
        if not pin.applies_on(target_date):
            continue
        pt = datetime.combine(target_date, pin.start_time, tzinfo=BERLIN)
        # Geplante Pins werden ZUSÄTZLICH zur Auto-Queue angezeigt (sie liegen wie
        # eine Ebene darüber). Nur bereits vergangene Pins des heutigen Tages
        # ausblenden – NICHT anhand der projizierten Queue-Länge (sonst verschwinden
        # z.B. „exakt"-Pins, die ja ohnehin unterbrechen).
        if pt <= now_b:
            continue
        # Bereits materialisiert? Realer Eintrag derselben Rubrik (bzw. desselben
        # Inhalts bei festen Pins) im ±12-Minuten-Fenster -> Pin nicht doppelt zeigen.
        rkey = pin.rubrik_key or 'music'
        materialized = False
        for (mt, mkind, mtrack, mspoken) in real_marks:
            if abs((mt - pt).total_seconds()) > 720:
                continue
            if pin.mode == 'pinned_track' and pin.track_id and mtrack == pin.track_id:
                materialized = True; break
            if pin.mode == 'pinned_spoken' and pin.spoken_id and mspoken == pin.spoken_id:
                materialized = True; break
            if pin.mode not in ('pinned_track', 'pinned_spoken') and mkind == rkey:
                materialized = True; break
        if materialized:
            continue
        title, kind = pin.name, (pin.rubrik_key or 'music')
        if pin.mode == 'pinned_track' and pin.track:
            title, kind = title or pin.track.title, 'music'
        elif pin.mode == 'pinned_spoken' and pin.spoken:
            title, kind = title or pin.spoken.title, pin.spoken.kind
        else:
            title = title or ('Rubrik: ' + (pin.rubrik_key or '?'))
        pau = ''
        try:
            if pin.mode == 'pinned_track' and pin.track and pin.track.audio_file:
                pau = pin.track.audio_file.url
            elif pin.mode == 'pinned_spoken' and pin.spoken and pin.spoken.audio_file:
                pau = pin.spoken.audio_file.url
        except Exception:
            pau = ''
        rows.append({'time': pt.isoformat(), 'time_str': pt.strftime('%H:%M'),
                     'kind': kind, 'title': title, 'source': 'theoretical', 'is_pin': True,
                     'mode': pin.mode, 'pk': pin.pk, 'enforce': pin.enforce,
                     'gen_status': pin.gen_status,
                     'resolved': _pin_resolvable(pin, target_date, smap), 'tags': '',
                     'audio_url': pau})

    wd = target_date.weekday()
    for slot in ProgramSlot.objects.filter(is_active=True):
        if wd not in slot.active_weekdays():
            continue
        st = datetime.combine(target_date, slot.start_time, tzinfo=UTC).astimezone(BERLIN)
        if st <= cutoff:
            continue
        rows.append({'time': st.isoformat(), 'time_str': st.strftime('%H:%M'),
                     'kind': 'auto', 'title': 'Auto-Block: ' + (slot.kinds or 'music'),
                     'source': 'theoretical', 'is_slot': True, 'pk': slot.pk,
                     'resolved': True, 'enforce': '', 'tags': ''})

    rows.sort(key=lambda r: r['time'])
    return rows


def _spoken_kind(s):
    """SpokenContent.kind auf eine gültige PlaylistEntry.kind abbilden."""
    valid = dict(PlaylistEntry.KIND)
    if s.kind in valid:
        return s.kind
    return 'story' if s.kind == 'klanggeschichte' else 'tip'


def _resolve_pin(pin, on_date, smap=None, generate=False):
    """Löst einen Pin zu (kind, track, spoken, dur) auf – oder None, wenn nichts spielbar.

    rubrik_gen + generate=True: fehlt ein Beitrag, wird er erzeugt (Sprach-Specs
    synchron via generate_spoken_content; sonst – z.B. klanggeschichte – im
    Hintergrund via compose_generate_task; dieser Lauf bleibt dann offen).
    """
    import random
    if smap is None:
        smap = _season_map()
    if pin.mode == 'compose':
        return None  # Beitrag wird separat erzeugt; bis dahin nicht spielbar
    if pin.mode == 'pinned_track':
        t = pin.track
        return ('music', t, None, t.duration_sec or 120) if (t and t.audio_file) else None
    if pin.mode == 'pinned_spoken':
        s = pin.spoken
        return (_spoken_kind(s), None, s, s.duration_sec or 60) if (s and s.audio_file) else None

    def _lru_pick(objs):
        """Fairness: bevorzugt das am längsten nicht Gespielte (nie Gespieltes zuerst);
        leichte Zufallsstreuung unter den 3 ältesten, Saison-Boost gewichtet."""
        if not objs:
            return None
        epoch = datetime.min.replace(tzinfo=UTC)
        objs.sort(key=lambda o: o.last_played_at or epoch)
        top = objs[:3]
        pool = [o for o in top for _ in range(_season_boost(o.tags, on_date, smap))]
        return random.choice(pool)

    key = pin.rubrik_key
    if _rubrik_is_music(key):
        t = _lru_pick([t for t in Track.objects.filter(is_active=True).exclude(audio_file='')
                       if _auto_eligible(t, on_date, smap)])
        if t is not None:
            return ('music', t, None, t.duration_sec or 120)
    else:
        if key == 'news':
            # Jeder News-Slot spielt die frischeste heutige Journal-Ausgabe
            # (Morgen/Mittag/Abend); ohne Journal laufen Saisonales-Beiträge.
            fresh = (SpokenContent.objects.filter(
                kind='news', status='generated', auto_include=True, air_date=on_date,
                title__startswith='Naturmacher-Journal').exclude(audio_file='')
                .order_by('-created_at').first())
            if fresh is not None:
                return (_spoken_kind(fresh), None, fresh, fresh.duration_sec or 90)
        s = _lru_pick([s for s in SpokenContent.objects.filter(kind=key, status='generated', auto_include=True)
                       .exclude(audio_file='') if _seasonal_ok(s.tags, on_date, smap)])
        if s is not None:
            return (_spoken_kind(s), None, s, s.duration_sec or 60)

    if pin.mode == 'rubrik_gen' and generate:
        from . import tasks
        try:
            if key in ('story', 'wissen', 'tip', 'news', 'kreativ'):
                pk = tasks.generate_spoken_content(kind=key, topic=(pin.topic or None), air_date=on_date)
                s = SpokenContent.objects.filter(pk=pk).first()
                if s and s.audio_file:
                    return (_spoken_kind(s), None, s, s.duration_sec or 60)
            else:
                # klanggeschichte/dialog/effekt/… im Hintergrund erzeugen
                tasks.compose_generate_task.delay(kind=key)
        except Exception:
            pass
    return None


@transaction.atomic
def ensure_queue_filled(min_hours=10, max_days=3):
    """Sorgt dafür, dass die Warteschlange immer mindestens `min_hours` Stunden
    Audio im Voraus enthält. Plant – falls nötig – ganze Folgetage hinzu, IMMER
    lückenlos hinter dem letzten Eintrag (idempotent: ein bereits geplanter Tag
    wird nie erneut geplant -> keine Doppel-Einträge). Gibt die Anzahl neu
    erzeugter Einträge zurück.
    """
    now = timezone.now()
    total_made = 0
    for _ in range(max_days + 2):
        qs = list(PlaylistEntry.objects.filter(status='queued')
                  .select_related('track', 'spoken'))
        secs = sum((e.duration_sec or 120) for e in qs)          # Zeit bis leer
        through = max((e.scheduled_time for e in qs if e.scheduled_time),
                      default=None)                               # letzter Plan-Tag
        if qs and secs >= min_hours * 3600:
            break
        today = now.astimezone(BERLIN).date()
        if through is None:
            target = today
        else:
            target = through.astimezone(BERLIN).date() + timedelta(days=1)
        if (target - today).days > max_days:
            break
        made = materialize_day(target, replace=False, generate=False)
        total_made += made
        if made == 0:
            break  # nichts (mehr) planbar -> keine Endlosschleife
    return total_made


def materialize_day(target_date=None, replace=False, generate=False):
    """
    Übersetzt den Tagesplan (Pins + Slots) in konkrete PlaylistEntry-Zeilen.
    Pins landen nahe ihrer Berlin-Uhrzeit; dazwischen füllt der Slot-Plan
    bzw. – falls keine Slots – ein Musik-Teppich aus eligiblen Tracks.
    generate=False (z.B. aus next_track): erzeugt NICHTS inline (schnell).
    Gibt die Anzahl erzeugter Zeilen zurück.
    """
    from .models import ScheduledItem, ProgramSlot
    from . import tasks
    now = timezone.now()
    target_date = target_date or now.astimezone(BERLIN).date()
    smap = _season_map()
    if replace:
        PlaylistEntry.objects.filter(status='queued').delete()

    # Startpunkt bestimmen: Beim Anhängen (replace=False) wird LÜCKENLOS an das
    # Ende der bestehenden Warteschlange angeschlossen — so kann derselbe
    # Zeitabschnitt NIE doppelt geplant werden (früherer Überlappungs-Bug).
    today = now.astimezone(BERLIN).date()
    if replace:
        start_floor = now
    else:
        last = (PlaylistEntry.objects.filter(status='queued')
                .order_by('-position').first())
        cont = None
        if last is not None and last.scheduled_time:
            cont = last.scheduled_time + timedelta(seconds=(last.duration_sec or 120))
        if target_date == today:
            start_floor = max(now, cont) if cont else now
        else:
            day_mid = datetime.combine(target_date, _time(0, 0), tzinfo=BERLIN)
            start_floor = max(day_mid, cont) if cont else day_mid

    pins = []
    for pin in ScheduledItem.objects.filter(is_active=True).order_by('start_time', 'order'):
        if not pin.applies_on(target_date):
            continue
        pt = datetime.combine(target_date, pin.start_time, tzinfo=BERLIN)
        if pt < start_floor - timedelta(minutes=2):
            continue  # liegt vor dem Anschlusspunkt — nicht (nach)holen
        if pin.enforce == 'exact':
            continue  # exact-Pins schiebt der Waechter (enforce_pins) live punktgenau ein
                       # -> NICHT vorab materialisieren (sonst Doppelung + Drift im Plan)
        res = _resolve_pin(pin, target_date, smap, generate=generate)
        if res:
            pins.append([pt, res])
    pins.sort(key=lambda x: x[0])

    wd = target_date.weekday()
    filler = []
    for slot in ProgramSlot.objects.filter(is_active=True).order_by('start_time', 'order'):
        if wd in slot.active_weekdays():
            try:
                filler.extend(tasks._build_slot_order(slot))
            except Exception:
                pass
    if not filler:
        # Instrumental- und Gesangs-Pool getrennt sammeln und nach dem
        # eingestellten Gesangs-Anteil (StationConfig.song_share) verzahnen
        instr, vocal = [], []
        for t in (Track.objects.filter(is_active=True).exclude(audio_file='')
                  .exclude(source='elevenlabs').exclude(mood='jingle')
                  .exclude(category='ad')
                  .order_by('play_count', 'created_at')):
            if not _auto_eligible(t, target_date, smap):
                continue
            item = {'type': 'track', 'pk': t.pk, 'kind': 'music',
                    'title': t.title, 'dur': t.duration_sec or 120}
            is_song = (getattr(t, 'category', '') == 'song') or bool(getattr(t, 'lyrics', ''))
            (vocal if is_song else instr).append(item)
        share = max(0, min(100, getattr(StationConfig.get(), 'song_share', 35) or 0)) / 100.0
        acc, ii, vi = 0.0, 0, 0
        for _ in range(len(instr) + len(vocal)):
            acc += share
            if (acc >= 1.0 and vocal) or not instr:
                if not vocal:
                    break
                filler.append(vocal[vi % len(vocal)]); vi += 1; acc -= 1.0
            else:
                filler.append(instr[ii % len(instr)]); ii += 1

    start = start_floor
    horizon = (pins[-1][0] + timedelta(minutes=30)) if pins else (start + timedelta(hours=2))

    # Werbe-Rotation: Pool (gesprochene + gesungene Spots), Abstand aus den Einstellungen
    cfg = StationConfig.get()
    ad_gap = (cfg.std_ad_every_min or 0) * 60
    adpool = []
    for sp in SpokenContent.objects.filter(kind='ad', status='generated', auto_include=True).exclude(audio_file='').order_by('?'):
        adpool.append(('ad', None, sp, sp.duration_sec or 30))
    for tr in Track.objects.filter(is_active=True, category='ad').exclude(audio_file='').order_by('?'):
        adpool.append(('ad', tr, None, tr.duration_sec or 30))

    seq, t, fi, pi, guard = [], start, 0, 0, 0
    ai, last_ad = 0, start
    while (t < horizon or pi < len(pins)) and guard < 1500:
        guard += 1
        if pi < len(pins) and pins[pi][0] <= t:
            kind, track, spoken, dur = pins[pi][1]
            seq.append((kind, track, spoken, dur)); t += timedelta(seconds=dur or 60); pi += 1
            continue
        if ad_gap and adpool and (t - last_ad).total_seconds() >= ad_gap:
            kind, track, spoken, dur = adpool[ai % len(adpool)]; ai += 1
            seq.append((kind, track, spoken, dur)); t += timedelta(seconds=dur or 30)
            last_ad = t
            continue
        if filler:
            it = filler[fi % len(filler)]; fi += 1
            tr = Track.objects.filter(pk=it['pk']).first() if it['type'] == 'track' else None
            sp = SpokenContent.objects.filter(pk=it['pk']).first() if it['type'] == 'spoken' else None
            if tr or sp:
                seq.append((it.get('kind', 'music'), tr, sp, it.get('dur', 120)))
            t += timedelta(seconds=(it.get('dur') or 120))
        elif pi < len(pins):
            kind, track, spoken, dur = pins[pi][1]
            seq.append((kind, track, spoken, dur)); t += timedelta(seconds=dur or 60); pi += 1
        else:
            break

    # GLOBAL über alle Einträge (auch gespielte): verhindert Positions-Kollisionen,
    # wenn mehrere Planungsläufe/Anhänger parallel arbeiten.
    base = PlaylistEntry.objects.aggregate(m=Max('position'))['m']
    pos = (base + 1) if base is not None else 0
    rows, tt = [], start
    for (kind, track, spoken, dur) in seq:
        rows.append(PlaylistEntry(position=pos, kind=kind, track=track, spoken=spoken,
                                  scheduled_time=tt, status='queued', manual=True))
        pos += 1; tt += timedelta(seconds=dur or 60)
    PlaylistEntry.objects.bulk_create(rows)
    return len(rows)


def apply_mix_settings():
    """Schickt die Crossfade-/Übergangs-Einstellungen aus StationConfig LIVE an
    Liquidsoap (Telnet-Interaktivvariablen). Wird beim Speichern der Einstellungen
    UND minütlich (enforce_pins) aufgerufen, damit die Werte auch einen Liquidsoap-
    Neustart überdauern. Gibt True bei Erfolg zurück."""
    import socket
    from .models import StationConfig
    c = StationConfig.get()
    try:
        sec = max(0.0, min(3.8, float(c.mix_xfade_sec or 0)))
    except (TypeError, ValueError):
        sec = 1.5
    cmds = (
        'var.set xfade_on = %s\n' % ('true' if c.mix_crossfade else 'false')
        + 'var.set xfade_sec = %.2f\n' % sec
        + 'var.set xfade_songs = %s\n' % ('true' if c.mix_xfade_songs else 'false')
        + 'quit\n'
    )
    try:
        s = socket.create_connection(('127.0.0.1', 1234), timeout=4)
        s.sendall(cmds.encode())
        s.settimeout(2)
        # bis zum Verbindungsende lesen, damit ALLE Befehle verarbeitet werden,
        # bevor geschlossen wird (sonst geht der letzte var.set verloren)
        try:
            while s.recv(512):
                pass
        except Exception:
            pass
        s.close()
        return True
    except Exception:
        return False
