import json
import os
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db import models, transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from .models import StationConfig, Track, ProgramSlot, SpokenContent, PlaylistEntry, ScheduledItem
from . import scheduler, glm

BERLIN = ZoneInfo('Europe/Berlin')


def _superuser_only(view):
    """Zugriff strikt nur für Superuser (nicht nur Staff)."""
    return user_passes_test(lambda u: u.is_active and u.is_superuser)(view)


# ============================================================================
#  Dashboard
# ============================================================================
def _queue_reach():
    """(Anzahl wartender Einträge, Text 'bis wann vorgeplant')."""
    from datetime import timedelta as _td
    qs = PlaylistEntry.objects.filter(status='queued').only('id')
    # Dauer separat summieren (duration_sec ist Property -> volle Objekte nötig)
    qfull = PlaylistEntry.objects.filter(status='queued').select_related('track', 'spoken')
    now = timezone.now()
    t = now
    n = 0
    for e in qfull:
        t += _td(seconds=(e.duration_sec or 120))
        n += 1
    if n == 0:
        return 0, 'leer'
    tl = t.astimezone(BERLIN)
    nl = now.astimezone(BERLIN)
    WD = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    if tl.date() == nl.date():
        txt = 'heute ' + tl.strftime('%H:%M')
    elif tl.date() == (nl.date() + timedelta(days=1)):
        txt = 'morgen ' + tl.strftime('%H:%M')
    else:
        txt = WD[tl.weekday()] + ' ' + tl.strftime('%d.%m. %H:%M')
    return n, txt


def _projected_days():
    """(days, queued, current, nxt): anstehende Einträge mit projizierten Berliner
    Sendezeiten (vorwärts ab jetzt kumuliert), nach Tagen gruppiert."""
    current = (
        PlaylistEntry.objects.filter(status='playing')
        .select_related('track', 'spoken').order_by('-started_at').first()
    )
    queued = list(
        PlaylistEntry.objects.filter(status='queued')
        .select_related('track', 'spoken').order_by('position')
    )
    now = timezone.now()
    t = now
    # Restzeit des laufenden Beitrags grob berücksichtigen
    if current and current.started_at:
        rest = (current.duration_sec or 0) - (now - current.started_at).total_seconds()
        if rest > 0:
            t = now + timedelta(seconds=rest)
    WD = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    for e in queued:
        pe = t.astimezone(BERLIN)
        e.proj = pe
        e.proj_str = pe.strftime('%H:%M')  # bereits Berlin — KEIN Template-|time-Filter
        e.engine_label, e.gen_prompt = _entry_meta(e)
        t += timedelta(seconds=e.duration_sec or 120)
    days = []
    for e in queued:
        label = f'{WD[e.proj.weekday()]}, {e.proj.strftime("%d.%m.")}'
        if not days or days[-1]['label'] != label:
            days.append({'label': label, 'date': e.proj.date(), 'entries': []})
        days[-1]['entries'].append(e)
    nxt = queued[0] if queued else None
    return days, queued, current, nxt


def _entry_meta(e):
    """(Engine/Modell-Label, Erstellungs-Prompt) eines Sendeplan-Eintrags."""
    if e.track_id and e.track:
        t = e.track
        eng = _engine_label_track(t)
        pr = (t.prompt or '').strip()
        if t.lyrics:
            pr = (pr + '\n\n[Gesungener Text]\n' + t.lyrics).strip()
        return eng, pr
    if e.spoken_id and e.spoken:
        sp = e.spoken
        eng = _engine_label_voice(sp.voice) + ((' · ' + _GEN_MODEL_LABELS.get(sp.gen_model, sp.gen_model)) if getattr(sp, 'gen_model', '') else '')
        return eng, (sp.text or '').strip()
    return '', ''


@_superuser_only
def schedule_fragment(request):
    """Sendeplan-Liste als HTML-Fragment + Anzahl (für AJAX-Refresh ohne Reload)."""
    days, queued, current, nxt = _projected_days()
    html = render(request, 'radio/_schedlist.html', {'days': days}).content.decode('utf-8')
    _n, _reach = _queue_reach()
    return JsonResponse({'html': html, 'count': len(queued), 'reach': _reach})


def _upcoming_pins(days=8, limit=40):
    """Nächste geplante Beiträge (Pins + Wochenprogramm): je Pin das nächste
    Vorkommen ab jetzt innerhalb der nächsten `days` Tage, zeitlich sortiert."""
    from datetime import datetime as _dt
    from .models import ScheduledItem, SpokenContent
    kindmap = dict(SpokenContent.KIND)
    WD = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    now_b = timezone.now().astimezone(BERLIN)
    out = []
    for pin in ScheduledItem.objects.filter(is_active=True).select_related('track', 'spoken'):
        nxt_dt = None
        for off in range(days):
            d = (now_b + timedelta(days=off)).date()
            if not pin.applies_on(d):
                continue
            cand = _dt.combine(d, pin.start_time, tzinfo=BERLIN)
            if cand < now_b:
                continue
            nxt_dt = cand
            break
        if not nxt_dt:
            continue
        if pin.mode == 'pinned_track' and pin.track:
            content = '🎵 ' + pin.track.title
        elif pin.mode == 'pinned_spoken' and pin.spoken:
            content = '🎙️ ' + pin.spoken.title
        else:
            content = '🎲 ' + (kindmap.get(pin.rubrik_key) or pin.rubrik_key or 'Rubrik')
        out.append({'dt': nxt_dt,
                    'when': '%s %s' % (WD[nxt_dt.weekday()], nxt_dt.strftime('%d.%m.')),
                    'time': nxt_dt.strftime('%H:%M'),
                    'content': content, 'exact': pin.enforce == 'exact',
                    'recurring': bool(pin.days) or not pin.on_date,
                    '_rk': pin.rubrik_key or '', '_track': pin.track_id, '_spoken': pin.spoken_id})

    # Bereits materialisierte Pins ausblenden: existiert in der Queue ein realer
    # Eintrag derselben Rubrik (bzw. desselben Inhalts) im ±12-Minuten-Fenster,
    # würde der Pin sonst doppelt erscheinen (z. B. 11:00 geplant + 11:05 real).
    try:
        _days, _queued, _cur, _nxt = _projected_days()
        marks = [(e.proj, (e.spoken.kind if e.spoken_id and e.spoken else ('music' if e.track_id else e.kind)),
                  e.track_id, e.spoken_id) for e in _queued]
        def _is_materialized(it):
            for (mt, mkind, mtrack, mspoken) in marks:
                if abs((mt - it['dt']).total_seconds()) > 720:
                    continue
                if it['_track'] and mtrack == it['_track']:
                    return True
                if it['_spoken'] and mspoken == it['_spoken']:
                    return True
                if not it['_track'] and not it['_spoken'] and mkind == (it['_rk'] or 'music'):
                    return True
            return False
        out = [it for it in out if not _is_materialized(it)]
    except Exception:
        pass
    for it in out:
        it.pop('_rk', None); it.pop('_track', None); it.pop('_spoken', None)
    out.sort(key=lambda x: x['dt'])
    return out[:limit]


@_superuser_only
def dashboard(request):
    """Cockpit: Uhr, läuft gerade / als Nächstes, Timeline nach Tagen/Stunden."""
    config = StationConfig.get()
    days, queued, current, nxt = _projected_days()
    now = timezone.now()
    now_b = now.astimezone(BERLIN)
    WD = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    try:
        with open(os.path.join(settings.MEDIA_ROOT, 'radio', 'stream_enabled')) as f:
            stream_live = f.read().strip() != '0'
    except OSError:
        stream_live = True
    ctx = {
        'stream_live': stream_live,
        'config': config,
        'now_berlin': now_b,
        'now_date_str': f'{WD[now_b.weekday()]}, {now_b.strftime("%d.%m.%Y")}',
        'next_proj_str': nxt.proj_str if nxt else '',
        'current': current,
        'next_entry': nxt,
        'days': days,
        'queued_count': len(queued),
        'queue_reach': _queue_reach()[1],
        'upcoming_pins': _upcoming_pins(),
        'track_count': Track.objects.filter(is_active=True).count(),
        'stream_token': getattr(settings, 'RADIO_STREAM_TOKEN', None) or os.environ.get('RADIO_STREAM_TOKEN', ''),
        'visual_ts': int(now.timestamp()),
        'visual_mode_now': (open(os.path.join(settings.MEDIA_ROOT, 'radio', 'visual_mode')).read().strip()
                            if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'radio', 'visual_mode')) else 'image'),
        'viz_preview_ts': (int(os.path.getmtime(os.path.join(settings.MEDIA_ROOT, 'radio', 'viz_preview.mp4')))
                           if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'radio', 'viz_preview.mp4')) else 0),
    }
    resp = render(request, 'radio/dashboard.html', ctx)
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


# ============================================================================
#  Sendeplan-Bedienung
# ============================================================================
@_superuser_only
@require_POST
def toggle_onair(request):
    """ON AIR an/aus. Aus = Sender pausiert (Stille), Queue bleibt stehen."""
    c = StationConfig.get()
    c.on_air = not c.on_air
    c.save(update_fields=['on_air'])
    return redirect('radio:dashboard')


@_superuser_only
@require_POST
def stream_power(request):
    """Beendet/startet die YouTube-Sendung (ffmpeg-Push) komplett – ohne Root, via Flag."""
    on = request.POST.get('on') == '1'
    media_dir = os.path.join(settings.MEDIA_ROOT, 'radio')
    os.makedirs(media_dir, exist_ok=True)
    with open(os.path.join(media_dir, 'stream_enabled'), 'w') as f:
        f.write('1' if on else '0')
    if not on:
        _kill_stream_ffmpeg()  # sofort stoppen; Loop startet nicht neu, solange Flag=0
    return redirect('radio:dashboard')


@_superuser_only
@require_POST
def live_duck(request):
    """Setzt die Musik-Lautstärke während Live-Sprechens (Liquidsoap interactive var)."""
    import socket
    try:
        val = float(json.loads(request.body or '{}').get('value', 0.18))
    except (ValueError, TypeError):
        val = 0.18
    val = max(0.0, min(1.0, val))
    try:
        s = socket.create_connection(('127.0.0.1', 1234), timeout=5)
        s.sendall(f'var.set music_duck = {val}\nquit\n'.encode())
        resp = s.recv(256).decode('utf-8', 'ignore')
        s.close()
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)
    return JsonResponse({'ok': True, 'value': val, 'resp': resp[:120]})


@_superuser_only
@require_POST
def set_background(request):
    """Wechselt das Stream-Visual (Bild oder Video, Loop/einmalig) und startet ffmpeg neu."""
    import signal
    media_dir = os.path.join(settings.MEDIA_ROOT, 'radio')
    os.makedirs(media_dir, exist_ok=True)
    mode = request.POST.get('mode', 'image')
    f = request.FILES.get('file')

    if f:
        if mode == 'image':
            from PIL import Image
            img = Image.open(f).convert('RGB')
            # Cover auf 1280x720
            tw, th = 1280, 720
            scale = max(tw / img.width, th / img.height)
            img = img.resize((int(img.width * scale), int(img.height * scale)))
            left = (img.width - tw) // 2
            top = (img.height - th) // 2
            img.crop((left, top, left + tw, top + th)).save(os.path.join(media_dir, 'standbild.png'))
            mode = 'image'
        else:
            with open(os.path.join(media_dir, 'background.mp4'), 'wb') as out:
                for chunk in f.chunks():
                    out.write(chunk)

    if mode not in dict(StationConfig.VISUAL_MODES):
        mode = 'image'
    with open(os.path.join(media_dir, 'visual_mode'), 'w') as vm:
        vm.write(mode)
    c = StationConfig.get()
    c.visual_mode = mode
    c.save(update_fields=['visual_mode'])

    # laufenden ffmpeg gezielt beenden -> stream.sh startet mit neuem Visual neu
    try:
        with open(os.path.join(media_dir, 'stream_ffmpeg.pid')) as pf:
            os.kill(int(pf.read().strip()), signal.SIGTERM)
    except Exception:
        pass
    return redirect('radio:dashboard')


@_superuser_only
@require_POST
def build_schedule(request):
    count = scheduler.build_schedule(target_count=int(request.POST.get('count', 40)))
    return redirect(reverse('radio:dashboard') + f'?built={count}')


@_superuser_only
@require_POST
def entry_move(request, pk):
    direction = request.POST.get('dir')
    with transaction.atomic():
        try:
            entry = PlaylistEntry.objects.get(pk=pk, status='queued')
        except PlaylistEntry.DoesNotExist:
            return redirect('radio:dashboard')
        qs = PlaylistEntry.objects.filter(status='queued')
        neighbor = (
            qs.filter(position__lt=entry.position).order_by('-position').first()
            if direction == 'up'
            else qs.filter(position__gt=entry.position).order_by('position').first()
        )
        if neighbor:
            entry.position, neighbor.position = neighbor.position, entry.position
            PlaylistEntry.objects.filter(pk=entry.pk).update(position=entry.position)
            PlaylistEntry.objects.filter(pk=neighbor.pk).update(position=neighbor.position)
    return redirect('radio:dashboard')


@_superuser_only
@require_POST
def entry_remove(request, pk):
    PlaylistEntry.objects.filter(pk=pk, status='queued').delete()
    scheduler.renumber()
    return redirect('radio:dashboard')


# ============================================================================
#  Compose-Studio (manuelle Beiträge)
# ============================================================================
@_superuser_only
def settings_view(request):
    """Einstellungen: Rubriken (GLM-Prompts), News-Themen, allgemeine Optionen."""
    config = StationConfig.get()
    from .models import Rubrik
    gemini_voices = [(v, l) for (v, l) in STUDIO_VOICES if v.startswith('gemini-')]
    # Intro-Auswahl: Bibliotheks-Audios, Jingles/Effekte zuerst (typische Intros)
    jingles, music = [], []
    for t in Track.objects.exclude(audio_file='').order_by('title'):
        try:
            _url = t.audio_file.url
        except ValueError:
            _url = ''
        item = {'pk': t.pk, 'title': t.title, 'dur': _fmt_dur(t.duration_sec), 'url': _url}
        if t.category == 'effekt' or (not t.category and (t.source == 'elevenlabs' or t.mood == 'jingle')):
            jingles.append(item)
        else:
            music.append(item)
    intro_groups = [('🔔 Jingles & Effekte', jingles), ('🎵 Musik', music)]
    return render(request, 'radio/settings.html', {
        'config': config,
        # 'journal' (Tagesnews) ist ein Sonderfall mit eigener News-Seite -> hier ausblenden.
        # Die saisonale/zeitlose 'news'-Rubrik bleibt regulär in der Liste.
        'rubriken': Rubrik.objects.exclude(key='journal'),
        'voices': gemini_voices,
        'intro_groups': intro_groups,
    })


@_superuser_only
@require_POST
def rubrik_save(request):
    """Legt eine Rubrik an oder aktualisiert sie (editierbare GLM-Prompts)."""
    from django.utils.text import slugify
    from .models import Rubrik
    pk = request.POST.get('pk')
    if pk:
        r = Rubrik.objects.filter(pk=pk).first()
        if not r:
            return redirect('radio:settings')
    else:
        r = Rubrik()
        base = slugify(request.POST.get('key') or request.POST.get('label') or 'rubrik')[:36] or 'rubrik'
        key, i = base, 2
        while Rubrik.objects.filter(key=key).exists():
            key = f'{base}-{i}'
            i += 1
        r.key = key
    r.label = (request.POST.get('label') or r.key).strip()[:80]
    r.rtype = request.POST.get('rtype', 'speech')
    r.system_prompt = request.POST.get('system_prompt', '').strip()
    r.task_prompt = request.POST.get('task_prompt', '').strip()
    r.voice = (request.POST.get('voice') or '').strip()
    r.tts_model = (request.POST.get('tts_model') or '').strip()[:40]
    if 'intro' in request.POST:
        iv = (request.POST.get('intro') or '').strip()
        r.intro = Track.objects.filter(pk=iv).first() if iv.isdigit() else None
    if 'outro' in request.POST:
        ov = (request.POST.get('outro') or '').strip()
        r.outro = Track.objects.filter(pk=ov).first() if ov.isdigit() else None
    if 'topic_memory' in request.POST:
        # Themen-Gedächtnis: Zeilen säubern, Limit einhalten
        lines = [ln.strip() for ln in (request.POST.get('topic_memory') or '').splitlines() if ln.strip()]
        from . import glm as _glm
        r.topic_memory = '\n'.join(lines[-_glm.TOPIC_MEMORY_MAX:])
    # Kategorie wird zentral im Standardprogramm gepflegt – hier nur, falls explizit mitgesendet
    if 'category' in request.POST:
        cat = (request.POST.get('category') or '').strip()
        r.category = cat if cat in ('talk', 'jingle', 'ad', 'music') else ''
    try:
        r.target_sec = max(0, min(3600, int(request.POST.get('target_sec') or 0)))
    except (TypeError, ValueError):
        r.target_sec = 0
    r.in_nightly = bool(request.POST.get('in_nightly'))
    r.is_active = bool(request.POST.get('is_active'))
    r.save()
    return redirect(reverse('radio:settings') + '?rubrik=1#rubriken')


@_superuser_only
@require_POST
def rubrik_delete(request, pk):
    from .models import Rubrik
    Rubrik.objects.filter(pk=pk).delete()
    return redirect(reverse('radio:settings') + '?rubrik_del=1#rubriken')


def _get_journal_rubrik():
    """Liefert (und erstellt bei Bedarf) die Sonderrubrik 'journal' = Tagesnews."""
    from .models import Rubrik
    j, _ = Rubrik.objects.get_or_create(
        key='journal',
        defaults={'label': 'Tagesnews / Journal', 'rtype': 'speech',
                  'voice': 'edge-de-DE-ConradNeural', 'in_nightly': True,
                  'is_active': True})
    return j


@_superuser_only
def news_settings(request):
    """Eigene Seite für die TAGESNEWS (Journal) — getrennt von der saisonalen
    'news'-Rubrik. Bündelt: Themen, Stimme, TTS-Modell, Zeitplan, Intro."""
    config = StationConfig.get()
    journal = _get_journal_rubrik()
    intro_path = os.path.join(settings.MEDIA_ROOT, 'radio', 'news_intro.mp3')
    intro_exists = os.path.exists(intro_path)
    intro_mtime = int(os.path.getmtime(intro_path)) if intro_exists else 0
    from .models import ScheduledItem
    news_pins = ScheduledItem.objects.filter(
        rubrik_key='news', on_date__isnull=True).order_by('start_time')
    return render(request, 'radio/news_settings.html', {
        'config': config,
        'journal': journal,
        'voices': list(STUDIO_VOICES),  # Gemini + Edge (gratis)
        'intro_exists': intro_exists,
        'intro_mtime': intro_mtime,
        'news_pins': news_pins,
    })


def _regenerate_news_pins(c):
    """Erzeugt die wiederkehrenden News-Pins (ScheduledItem) neu gemäß Zeitplan.
    Spielt je Pin die frischeste Tagesnews (rubrik_key='news')."""
    import datetime as _dt
    from .models import ScheduledItem
    # vorhandene Termin-Themen + Stimme/Modell pro Stunde merken (beim Neuaufbau erhalten)
    old = {p.start_time.hour: (p.topic, p.gen_spec or {}) for p in
           ScheduledItem.objects.filter(rubrik_key='news', on_date__isnull=True)}
    # nur die WIEDERKEHRENDEN News-Pins ersetzen (on_date leer); datums-spezifische bleiben
    ScheduledItem.objects.filter(rubrik_key='news', on_date__isnull=True).delete()
    if not c.news_enabled:
        return 0
    minute = max(0, min(59, c.news_minute or 0))
    step = max(1, c.news_interval_h or 1)
    frm = max(0, min(23, c.news_from_hour or 0))
    to = max(0, min(23, c.news_to_hour if c.news_to_hour is not None else 23))
    made, hh = 0, frm
    while hh <= to:
        _topic, _spec = old.get(hh, ('', {}))
        ScheduledItem.objects.create(
            name=f'News {hh:02d}:{minute:02d}', mode='rubrik_auto', rubrik_key='news',
            start_time=_dt.time(hh, minute), days='', enforce='anchor', is_active=True, order=0,
            topic=_topic, gen_spec=_spec)
        made += 1
        hh += step
    return made


@_superuser_only
@require_POST
def news_settings_save(request):
    c = StationConfig.get()
    c.news_topics = (request.POST.get('news_topics') or '').strip()[:2000]

    def _ival(key, cur, lo, hi):
        try:
            return max(lo, min(hi, int(request.POST.get(key))))
        except (TypeError, ValueError):
            return cur
    c.news_enabled = bool(request.POST.get('news_enabled'))
    c.news_minute = _ival('news_minute', c.news_minute, 0, 59)
    c.news_from_hour = _ival('news_from_hour', c.news_from_hour, 0, 23)
    c.news_to_hour = _ival('news_to_hour', c.news_to_hour, 0, 23)
    c.news_interval_h = _ival('news_interval_h', c.news_interval_h, 1, 24)
    c.news_intro_enabled = bool(request.POST.get('news_intro_enabled'))
    c.save()
    # Optionaler Intro-Upload: ersetzt media/radio/news_intro.mp3
    f = request.FILES.get('intro_file')
    if f:
        dest_dir = os.path.join(settings.MEDIA_ROOT, 'radio')
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, 'news_intro.mp3'), 'wb') as out:
            for chunk in f.chunks():
                out.write(chunk)
    journal = _get_journal_rubrik()
    journal.voice = (request.POST.get('voice') or '').strip()
    journal.tts_model = (request.POST.get('tts_model') or '').strip()[:40]
    journal.is_active = c.news_enabled
    try:
        journal.target_sec = max(0, min(600, int(request.POST.get('news_length_sec'))))
    except (TypeError, ValueError):
        pass
    journal.save()
    # Per-Termin-Themen speichern (Felder topic_<pin_id>) – vor dem Neuaufbau,
    # damit _regenerate_news_pins sie pro Stunde übernimmt.
    from .models import ScheduledItem
    for p in ScheduledItem.objects.filter(rubrik_key='news', on_date__isnull=True):
        changed = False
        if f'topic_{p.pk}' in request.POST:
            p.topic = (request.POST.get(f'topic_{p.pk}') or '').strip()[:1000]
            changed = True
        # Stimme/Modell pro Termin in gen_spec ablegen (leer = globale Journal-Stimme)
        if f'voice_{p.pk}' in request.POST:
            spec = dict(p.gen_spec or {})
            v = (request.POST.get(f'voice_{p.pk}') or '').strip()
            m = (request.POST.get(f'model_{p.pk}') or '').strip()
            spec['voice'] = v if v else None
            spec['tts_model'] = m if m else None
            spec = {k: val for k, val in spec.items() if val}
            p.gen_spec = spec
            changed = True
        if changed:
            p.save()
    n = _regenerate_news_pins(c)
    return redirect(reverse('radio:news_settings') + f'?saved=1&pins={n}')


@_superuser_only
@require_POST
def save_settings(request):
    c = StationConfig.get()
    c.name = (request.POST.get('name') or c.name).strip()[:120]
    if 'news_topics' in request.POST:
        c.news_topics = (request.POST.get('news_topics') or '').strip()[:2000]
    if 'youtube_url' in request.POST:
        c.youtube_url = (request.POST.get('youtube_url') or '').strip()[:300]

    def _int(key, cur):
        try:
            return max(0, int(request.POST.get(key)))
        except (TypeError, ValueError):
            return cur
    c.std_music_per_talk = _int('std_music_per_talk', c.std_music_per_talk)
    c.song_share = max(0, min(100, _int('song_share', c.song_share)))
    c.std_jingle_every = _int('std_jingle_every', c.std_jingle_every)
    c.std_ad_every_min = _int('std_ad_every_min', c.std_ad_every_min)

    # Übergänge / Crossfade
    upd = ['name', 'news_topics', 'youtube_url', 'std_music_per_talk', 'std_jingle_every', 'std_ad_every_min', 'song_share']
    if 'mix_section' in request.POST:   # nur wenn der Übergänge-Block mitgesendet wurde
        c.mix_crossfade = bool(request.POST.get('mix_crossfade'))
        c.mix_xfade_songs = bool(request.POST.get('mix_xfade_songs'))
        try:
            c.mix_xfade_sec = max(0.0, min(3.8, float((request.POST.get('mix_xfade_sec') or '1.5').replace(',', '.'))))
        except (TypeError, ValueError):
            pass
        upd += ['mix_crossfade', 'mix_xfade_songs', 'mix_xfade_sec']
    c.save(update_fields=upd)
    scheduler.apply_mix_settings()   # sofort live an Liquidsoap

    # Rubrik-Kategorien fürs Standardprogramm (Felder cat_<pk>)
    from .models import Rubrik
    valid = {'talk', 'jingle', 'ad', 'music'}
    for k, v in request.POST.items():
        if not k.startswith('cat_'):
            continue
        try:
            pk = int(k[4:])
        except ValueError:
            continue
        v = (v or '').strip()
        Rubrik.objects.filter(pk=pk).update(category=(v if v in valid else ''))
    return redirect(reverse('radio:settings') + '?saved=1')


@_superuser_only
@require_POST
def upload_clone_voice(request):
    """Lädt eine Referenz-Audioprobe hoch → konvertiert zu WAV → Klon-Stimme."""
    import subprocess
    f = request.FILES.get('file')
    if not f:
        return redirect(reverse('radio:settings') + '?err=nofile')
    media_dir = os.path.join(settings.MEDIA_ROOT, 'radio')
    os.makedirs(media_dir, exist_ok=True)
    raw = os.path.join(media_dir, '_clone_src')
    with open(raw, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)
    wav = os.path.join(media_dir, 'clone_voice.wav')
    # Mono, 22.05 kHz, auf max 30 s begrenzt — ideal für XTTS-Referenz
    subprocess.run(['ffmpeg', '-y', '-i', raw, '-t', '30', '-ac', '1', '-ar', '22050', wav],
                   capture_output=True, timeout=60)
    try:
        os.remove(raw)
    except OSError:
        pass
    c = StationConfig.get()
    c.clone_voice.name = 'radio/clone_voice.wav'
    c.clone_voice_label = (request.POST.get('label') or 'Meine Klon-Stimme').strip()[:80]
    c.save(update_fields=['clone_voice', 'clone_voice_label'])
    return redirect(reverse('radio:settings') + '?clone=1')


from . import gemini_tts as _gtts
from . import edgetts as _edgetts

STUDIO_VOICES = (
    # Gemini Cloud-TTS — natürlich, menschlich
    [(f'gemini-{name}', f'🌟 {label}') for name, label in _gtts.VOICES]
    # Edge-TTS (Microsoft) — gratis, keine lokale Last
    + [(f'edge-{vid}', f'🔊 {label} · gratis') for vid, label in _edgetts.VOICES]
)


@_superuser_only
def compose(request):
    """Studio: Beitrag erstellen (Typ wählen, Text/Beschreibung, GLM-Assistent, Stimme)."""
    config = StationConfig.get()
    voices = list(STUDIO_VOICES)
    # Rubriken aus DB (editierbar); Fallback auf die eingebauten KIND-Choices
    from .models import Rubrik
    rubriken = list(Rubrik.objects.filter(is_active=True).values('key', 'label', 'rtype'))
    kinds = [(r['key'], r['label']) for r in rubriken] or list(PlaylistEntry.KIND)
    speech_keys = [r['key'] for r in rubriken if r['rtype'] != 'music'] or ['news', 'story', 'tip', 'wissen', 'kreativ', 'jingle', 'ad']
    import json as _json
    from . import elevenlabs as _el
    gemini_voices = [{'value': v, 'label': l} for (v, l) in voices if v.startswith('gemini-')]
    try:
        eleven_voices = [{'value': f'eleven-{vid}', 'label': lbl} for (vid, lbl) in _el.list_voices()]
    except Exception:
        eleven_voices = []
    _guide = os.path.join(settings.MEDIA_ROOT, 'radio', 'KI-Musik-Guide.pdf')
    _guide_ts = int(os.path.getmtime(_guide)) if os.path.exists(_guide) else 0
    resp = render(request, 'radio/compose.html', {
        'guide_ts': _guide_ts,
        'kinds': kinds,
        'speech_keys': speech_keys,
        'voices': voices,
        'gemini_voices_json': _json.dumps(gemini_voices),
        'eleven_voices_json': _json.dumps(eleven_voices),
        'tts_settings_json': _json.dumps(_tts_settings_dict()),
        'bg_tracks_json': _json.dumps(_bg_track_choices()),
        'fal_music_json': _json.dumps(_fal_models('music')),
        'fal_speech_json': _json.dumps(_fal_models('speech')),
        'sample_base': f'{settings.MEDIA_URL}radio/voicesamples/',
    })
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


def _fal_models(kind):
    from . import fal
    src = fal.MUSIC_MODELS if kind == 'music' else fal.SPEECH_MODELS
    return [{'value': m['id'], 'label': m['label']} for m in src]


def _bg_track_choices():
    """Instrumental-/Musik-Tracks der Bibliothek für die Hintergrundmusik-Auswahl."""
    qs = (Track.objects.filter(is_active=True).exclude(audio_file='')
          .exclude(source='elevenlabs').order_by('lyrics', '-created_at'))
    out = []
    for t in qs[:100]:
        tag = '🎤 ' if t.lyrics else '🎵 '
        out.append({'value': t.pk, 'label': tag + (t.title or f'Track {t.pk}')})
    return out


def _tts_settings_dict():
    c = StationConfig.get()
    return {
        'gemini_tts_model': c.gemini_tts_model,
        'eleven_model_id': c.eleven_model_id,
        'eleven_stability': c.eleven_stability,
        'eleven_similarity': c.eleven_similarity,
        'eleven_style': c.eleven_style,
        'eleven_speaker_boost': c.eleven_speaker_boost,
    }


@_superuser_only
@require_POST
def tts_settings(request):
    """Speichert das TTS-Feintuning (Gemini-Modell + ElevenLabs-Voice-Settings) in StationConfig."""
    data = json.loads(request.body or '{}')
    c = StationConfig.get()
    if data.get('gemini_tts_model') in ('flash', 'pro'):
        c.gemini_tts_model = data['gemini_tts_model']
    if data.get('eleven_model_id'):
        c.eleven_model_id = str(data['eleven_model_id'])[:40]

    def _clamp(v, lo, hi, default):
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return default
    c.eleven_stability = _clamp(data.get('eleven_stability'), 0, 1, c.eleven_stability)
    c.eleven_similarity = _clamp(data.get('eleven_similarity'), 0, 1, c.eleven_similarity)
    c.eleven_style = _clamp(data.get('eleven_style'), 0, 1, c.eleven_style)
    if 'eleven_speaker_boost' in data:
        c.eleven_speaker_boost = bool(data['eleven_speaker_boost'])
    c.save()
    return JsonResponse({'ok': True, 'settings': _tts_settings_dict()})


VIZ_DEFAULTS = {
    'viz_type': 'showcqt', 'width': 1280, 'height': 720, 'fps': 25,
    'palette': 'rainbow', 'base_color': '#33d1ff', 'bg_color': '#0c1626',
    'bar_count': 64, 'scale': 'log', 'show_logo': True, 'logo_size': 140,
    'show_nowplaying': True, 'text_size': 30,
}
_VIZ_FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def _viz_cfg():
    c = dict(VIZ_DEFAULTS)
    c.update(StationConfig.get().viz_settings or {})
    return c


def _viz_media(name):
    return os.path.join(settings.MEDIA_ROOT, 'radio', name)


@_superuser_only
def visualizer(request):
    """Einstellungs-Oberfläche für den Audio-Visualizer."""
    from . import visualizer as vz
    import json as _json
    cur_mode = 'image'
    try:
        with open(_viz_media('visual_mode')) as f:
            cur_mode = f.read().strip()
    except OSError:
        pass
    return render(request, 'radio/visualizer.html', {
        'cfg_json': _json.dumps(_viz_cfg()),
        'types_json': _json.dumps(vz.VIZ_TYPES),
        'palettes_json': _json.dumps(vz.SPECTRUM_COLORS),
        'active': cur_mode == 'visualizer',
    })


@_superuser_only
@require_POST
def visualizer_save(request):
    data = json.loads(request.body or '{}')
    c = StationConfig.get()
    cfg = dict(VIZ_DEFAULTS)
    cfg.update(c.viz_settings or {})
    for k in VIZ_DEFAULTS:
        if k in data:
            cfg[k] = data[k]
    c.viz_settings = cfg
    c.save(update_fields=['viz_settings'])
    return JsonResponse({'ok': True})


@_superuser_only
@require_POST
def visualizer_preview(request):
    """Rendert ein ~6s-Muster aus einem Bibliotheks-Track mit den aktuellen Einstellungen."""
    import subprocess
    data = json.loads(request.body or '{}')
    cfg = dict(VIZ_DEFAULTS)
    cfg.update(StationConfig.get().viz_settings or {})
    for k in VIZ_DEFAULTS:
        if k in data:
            cfg[k] = data[k]
    track = Track.objects.exclude(audio_file='').order_by('?').first()
    if not track:
        return JsonResponse({'error': 'Keine Audio-Datei in der Bibliothek für die Vorschau.'}, status=400)
    from . import visualizer as vz
    logo = _viz_media('viz_logo.png') if (cfg.get('show_logo') and os.path.exists(_viz_media('viz_logo.png'))) else None
    npf = _viz_media('nowplaying.txt')
    if cfg.get('show_nowplaying'):
        try:
            with open(npf, 'w') as f:
                f.write('Naturmacher Radio')
        except OSError:
            npf = None
    font = _VIZ_FONT if os.path.exists(_VIZ_FONT) else None
    flt = vz.build_filter(cfg, logo_path=logo, nowplaying_file=npf if font else None, font_file=font)
    out = _viz_media('viz_preview.mp4')
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', track.audio_file.path,
           '-filter_complex', flt, '-map', '[v]', '-map', '0:a', '-t', '6',
           '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(out):
        return JsonResponse({'error': (p.stderr or 'Render-Fehler')[-200:]}, status=500)
    return JsonResponse({'ok': True, 'url': f'{settings.MEDIA_URL}radio/viz_preview.mp4?v={int(timezone.now().timestamp())}'})


def _restart_stream_ffmpeg():
    import subprocess
    try:
        with open(_viz_media('stream_ffmpeg.pid')) as f:
            pid = int(f.read().strip())
        subprocess.run(['kill', str(pid)], capture_output=True)
    except (OSError, ValueError):
        pass


@_superuser_only
@require_POST
def visualizer_activate(request):
    """Schaltet den Visualizer im Live-Stream an ({on:true}) oder aus → Bild ({on:false})."""
    data = json.loads(request.body or '{}')
    if data.get('on') is False:
        try:
            with open(_viz_media('visual_mode'), 'w') as f:
                f.write('image')
        except OSError as e:
            return JsonResponse({'error': f'Konnte nicht umschalten: {e}'}, status=500)
        _restart_stream_ffmpeg()
        return JsonResponse({'ok': True, 'mode': 'image'})

    import subprocess
    cfg = _viz_cfg()
    from . import visualizer as vz
    logo = _viz_media('viz_logo.png') if (cfg.get('show_logo') and os.path.exists(_viz_media('viz_logo.png'))) else None
    npf = _viz_media('nowplaying.txt')
    font = _VIZ_FONT if os.path.exists(_VIZ_FONT) else None
    flt = vz.build_filter(cfg, logo_path=logo, nowplaying_file=npf if font else None, font_file=font)
    try:
        with open(_viz_media('visualizer_filter.txt'), 'w') as f:
            f.write(flt)
        with open(_viz_media('visualizer_fps.txt'), 'w') as f:
            f.write(str(int(cfg.get('fps') or 25)))
        with open(_viz_media('visual_mode'), 'w') as f:
            f.write('visualizer')
    except OSError as e:
        return JsonResponse({'error': f'Konnte Stream-Dateien nicht schreiben: {e}'}, status=500)
    _restart_stream_ffmpeg()  # stream.sh startet mit dem Visualizer neu
    return JsonResponse({'ok': True, 'mode': 'visualizer'})


@_superuser_only
def pexels_search(request):
    """Sucht Videos bei Pexels (für „Video"-Button im Studio)."""
    import requests
    from django.contrib.auth import get_user_model
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'videos': []})
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    user = get_user_model().objects.filter(username='taras').first()
    key = ((getattr(user, 'pexels_api_key', '') or '').strip()) if user else ''
    if not key:
        return JsonResponse({'error': 'Kein Pexels-Key hinterlegt.'}, status=400)
    per_page = 12
    try:
        r = requests.get('https://api.pexels.com/videos/search', headers={'Authorization': key},
                         params={'query': q, 'per_page': per_page, 'page': page,
                                 'orientation': 'landscape'}, timeout=15)
        data = r.json()
    except Exception as e:
        return JsonResponse({'error': str(e)[:120]}, status=502)
    out = []
    for v in data.get('videos', []):
        files = sorted([f for f in v.get('video_files', []) if f.get('file_type') == 'video/mp4'],
                       key=lambda f: -(f.get('width') or 0))
        best = next((f for f in files if (f.get('width') or 0) <= 1920), files[0] if files else None)
        # kleinere Datei zum schnellen Vorschau-Abspielen (~SD)
        prev = next((f for f in sorted(files, key=lambda f: (f.get('width') or 0))
                     if (f.get('width') or 0) >= 640), best)
        if best:
            out.append({'id': v.get('id'), 'thumb': v.get('image'),
                        'duration': v.get('duration'), 'url': best['link'],
                        'preview': (prev or best)['link']})
    total = data.get('total_results', 0)
    return JsonResponse({'videos': out, 'page': page, 'per_page': per_page,
                         'total': total, 'pages': max(1, -(-total // per_page))})


@_superuser_only
@require_POST
def glm_assist(request):
    """
    GLM-5.1-Assistent: nimmt Typ, Anweisung und aktuellen Entwurf entgegen und
    liefert einen überarbeiteten Vorlesetext zurück (AJAX, iterativ nutzbar).
    """
    data = json.loads(request.body or '{}')
    kind = data.get('kind', 'wissen')
    instruction = (data.get('instruction') or '').strip()
    draft = (data.get('draft') or '').strip()
    # Im Wizard ist das Thema/die Richtung optional — für die generativen Rubriken
    # (Lied, Musik, Dialog, Effekt) darf GLM auch ohne Anweisung allein aus der
    # Rubrik einen Vorschlag erzeugen. Nur die reine Überarbeitung ohne jeglichen
    # Kontext (kein Entwurf, keine Anweisung, kein bekannter Typ) wird abgelehnt.
    _generative = {'song', 'music', 'dialog', 'effekt'}
    if not instruction and not draft and kind not in _generative:
        return JsonResponse({'error': 'Bitte eine Anweisung eingeben.'}, status=400)

    # Optionale Ziel-Länge (Sekunden) → ungefähre Wortzahl als Vorgabe für GLM.
    # Deutsches Radio-/Vorlese-Tempo ~ 2,3 Wörter/Sekunde (siehe WORDS_PER_SEC).
    try:
        target_sec = int(float(data.get('target_sec') or 0))
    except (TypeError, ValueError):
        target_sec = 0
    length_hint = ''
    if target_sec > 0:
        target_words = max(8, round(target_sec * WORDS_PER_SEC))
        length_hint = (f'Der Text soll vorgelesen etwa {target_sec} Sekunden dauern — '
                       f'das sind ungefähr {target_words} Wörter. Halte diese Länge ein.')

    # Musik: GLM hilft, die Musikrichtung/Stimmung zu beschreiben (wird später
    # zum MusicGen-Prompt). Sprache: GLM entwirft/überarbeitet den Vorlesetext.
    if kind == 'music':
        system = (
            'Du bist Musikredakteur eines modernen Naturmacher-Radiosenders '
            '(Natur, Garten, Basteln, Familie). Du hilfst, die gewünschte Musik '
            'treffend zu beschreiben: Genre, Stimmung, Instrumentierung, Tempo. '
            'Modern, instrumental, markenpassend.'
        )
        parts = ['Formuliere eine prägnante Beschreibung der gewünschten Musik (1–3 Sätze, Deutsch).']
        if draft:
            parts.append(f'Bisheriger Entwurf:\n"""\n{draft}\n"""')
        if instruction:
            parts.append(f'Wunsch des Redakteurs: {instruction}')
        parts.append('Gib NUR die überarbeitete Beschreibung zurück (Fließtext, ohne Kommentare).')
        try:
            text = glm.glm_chat('\n\n'.join(parts), system=system, max_tokens=600)
        except Exception as e:
            return JsonResponse({'error': f'GLM nicht erreichbar: {e}'}, status=502)
        return JsonResponse({'text': text.strip()})

    if kind == 'effekt':
        parts = ['Beschreibe einen kurzen Radio-Sound-Effekt/Jingle auf ENGLISCH (1 Satz, '
                 'z. B. "short bright radio ident chime, cheerful, sparkly").']
        if instruction:
            parts.append(f'Wunsch: {instruction}')
        if draft:
            parts.append(f'Bisher: {draft}')
        parts.append('Gib NUR die englische Effekt-Beschreibung zurück.')
        try:
            text = glm.glm_chat('\n\n'.join(parts),
                                system='Du bist Sounddesigner eines Radiosenders.', max_tokens=120)
        except Exception as e:
            return JsonResponse({'error': f'GLM nicht erreichbar: {e}'}, status=502)
        return JsonResponse({'text': text.strip()})

    if kind == 'song':
        system = (
            'Du bist Songwriter für einen modernen Naturmacher-Radiosender '
            '(Natur, Garten, Basteln, Familie). Du schreibst eingängige, '
            'sympathische deutsche Liedtexte.'
        )
        parts = [
            'Schreibe einen deutschen Liedtext. Gliedere ihn mit Struktur-Tags in '
            'eckigen Klammern auf ENGLISCH: [verse], [chorus], optional [bridge]. '
            'Der gesungene Text selbst ist DEUTSCH. Keine Erklärungen.',
        ]
        if draft:
            parts.append(f'Bisheriger Entwurf:\n"""\n{draft}\n"""')
        if instruction:
            parts.append(f'Thema/Wunsch des Redakteurs: {instruction}')
        if target_sec > 0:
            mins = round(target_sec / 60.0, 1)
            # moderat halten: zu viele Strophen lehnt Lyria ab (Fehler "OTHER"); MiniMax
            # kommt mit mehr Text zurecht. Daher auf ~4 Strophen begrenzen.
            n_verse = max(2, min(4, round(target_sec / 55)))
            parts.append(
                f'Ziel-Länge: ca. {mins} Minuten. Die Liedlänge hängt vom Textumfang ab – '
                f'schreibe ungefähr {n_verse} Strophen und {max(2, n_verse - 1)} Refrains '
                f'(Refrain darf sich wiederholen), bei längeren Liedern eine [bridge]. '
                f'Hinweis: Längere Lieder (über ~1,5 Min) gelingen am besten mit der '
                f'MiniMax-Engine; Lyria liefert eher kürzere Stücke.')
        parts.append('Gib NUR den fertigen Liedtext zurück (mit [verse]/[chorus]-Tags).')
        try:
            text = glm.glm_chat('\n\n'.join(parts), system=system, max_tokens=2000)
        except Exception as e:
            return JsonResponse({'error': f'GLM nicht erreichbar: {e}'}, status=502)
        text = text.strip()
        return JsonResponse({'text': text, 'title': glm.make_title(text)})

    if kind == 'dialog':
        a = (data.get('speaker_a') or 'Anna').strip()[:30]
        b = (data.get('speaker_b') or 'Tom').strip()[:30]
        system = (
            'Du bist Redakteur eines modernen Naturmacher-Radiosenders (Natur, Garten, '
            'Basteln, Familie). Du schreibst lockere, natürlich klingende Radio-Dialoge '
            'zwischen zwei Moderatoren.'
        )
        parts = [
            f'Schreibe einen kurzweiligen Radio-Dialog zwischen genau zwei Sprechern: {a} und {b}.',
            f'WICHTIG: Jede Zeile beginnt mit dem Sprecher-Namen und Doppelpunkt, also "{a}:" bzw. "{b}:". '
            'Keine Regieanweisungen, keine Klammern, nur gesprochener Text.',
        ]
        if draft:
            parts.append(f'Bisheriger Entwurf:\n"""\n{draft}\n"""')
        if instruction:
            parts.append(f'Thema/Wunsch des Redakteurs: {instruction}')
        else:
            _avoid = glm.avoid_topics_instruction(kind)
            if _avoid:
                parts.append(_avoid)
        if length_hint:
            parts.append(length_hint)
        _ann = glm.announce_instruction(kind)
        if _ann:
            parts.append(_ann)
        parts.append('Gib NUR den fertigen Dialog zurück (abwechselnd, je Zeile ein Sprecher).')
        try:
            text = glm.glm_chat('\n\n'.join(parts), system=system, max_tokens=1500)
        except Exception as e:
            return JsonResponse({'error': f'GLM nicht erreichbar: {e}'}, status=502)
        text = text.strip()
        return JsonResponse({'text': text, 'title': glm.make_title(text)})

    if kind == 'klanggeschichte':
        system = (
            'Du bist Hörspiel-Autor eines modernen Naturmacher-Senders (Natur, Garten, '
            'Basteln, Familie). Du schreibst lebendige deutsche Hörgeschichten und setzt '
            'dabei gezielt Klang-Regie ein.'
        )
        parts = [
            'Schreibe eine deutsche Hörgeschichte und bette Klang-Regie als Marker ein:',
            '• [AMBIENCE: <englische Beschreibung>] für einen durchgehenden Klangteppich '
            '(z. B. [AMBIENCE: gentle forest with distant birdsong]). Setze einen gleich '
            'am Anfang und wechsle ihn nur bei klarem Szenenwechsel.',
            '• [SFX: <englische Beschreibung>] für einzelne Geräusche an genau der Stelle, '
            'wo sie passieren (z. B. [SFX: owl hooting], [SFX: creaking wooden door]).',
            'WICHTIG: Die Beschreibungen IN den eckigen Klammern sind ENGLISCH (ElevenLabs '
            'versteht Englisch am besten), der ERZÄHLTEXT selbst ist DEUTSCH. Setze Marker '
            'sparsam und sinnvoll (etwa alle 2–4 Sätze ein SFX). Marker stehen für sich, '
            'keine Klammern im Erzähltext sonst.',
        ]
        if draft:
            parts.append(f'Bisheriger Entwurf:\n"""\n{draft}\n"""')
        if instruction:
            parts.append(f'Thema/Wunsch des Redakteurs: {instruction}')
        else:
            _avoid = glm.avoid_topics_instruction(kind)
            if _avoid:
                parts.append(_avoid)
        if length_hint:
            parts.append(length_hint + ' (Marker zählen nicht zur Vorlese-Länge.)')
        _ann = glm.announce_instruction(kind)
        if _ann:
            parts.append(_ann + ' (Die Ankündigung steht als erster Erzählsatz NACH dem ersten [AMBIENCE]-Marker.)')
        parts.append('Gib NUR die fertige Hörgeschichte mit eingebetteten [AMBIENCE]/[SFX]-Markern zurück.')
        try:
            text = glm.glm_chat('\n\n'.join(parts), system=system, max_tokens=2000)
        except Exception as e:
            return JsonResponse({'error': f'GLM nicht erreichbar: {e}'}, status=502)
        text = text.strip()
        return JsonResponse({'text': text, 'title': glm.make_title(text)})

    # DB-Rubrik-Prompts haben Vorrang (wichtig für EIGENE Rubriken – vorher fiel
    # alles Unbekannte fälschlich auf die "Wissenswertes"-Vorgaben zurück)
    spec = glm.SPOKEN_SPECS.get(kind, glm.SPOKEN_SPECS['wissen'])
    system, task = glm._rubrik_prompts(kind, spec['system'], spec['task'])
    parts = [task]
    if draft:
        parts.append(f'Hier ist der bisherige Entwurf:\n"""\n{draft}\n"""')
    if instruction:
        parts.append(f'Anweisung des Redakteurs: {instruction}')
    else:
        _avoid = glm.avoid_topics_instruction(kind)
        if _avoid:
            parts.append(_avoid)
    if length_hint:
        parts.append(length_hint)
    ann = glm.announce_instruction(kind)
    if ann:
        parts.append(ann)
    parts.append(
        'Gib NUR den überarbeiteten, fertig vorlesbaren Text zurück (reiner '
        'Fließtext, ohne Anführungszeichen, ohne Kommentare).'
    )
    try:
        text = glm.glm_chat('\n\n'.join(parts), system=system, max_tokens=2000)
    except Exception as e:
        return JsonResponse({'error': f'GLM nicht erreichbar: {e}'}, status=502)
    text = text.strip()
    return JsonResponse({'text': text, 'title': glm.make_title(text)})


@_superuser_only
def eleven_balance(request):
    """Liefert das ElevenLabs-Restguthaben (für die Live-Anzeige im Studio)."""
    from . import elevenlabs as el
    return JsonResponse(el.get_balance() or {'error': 'nicht verfügbar'})


@_superuser_only
@require_POST
def tts_test(request):
    """Live-Kurzprobe einer Stimme: synthetisiert einen kurzen Satz mit der aktuellen
    Auswahl (Gemini Flash/Pro oder ElevenLabs) und liefert das Audio als Daten-URI."""
    import base64
    data = json.loads(request.body or '{}')
    voice = data.get('voice') or 'gemini-Charon'
    gemini_model = (data.get('gemini_model') or '').strip() or None
    eleven_model = (data.get('eleven_model') or '').strip() or None
    text = (data.get('text') or '').strip() or \
        'Hallo, schön dass du reinhörst – so klingt diese Stimme im Naturmacher Radio.'
    text = text[:240]
    from . import gemini_tts
    from . import elevenlabs as el
    try:
        if str(voice).startswith('fal:'):
            from . import fal
            mp3 = fal.tts(voice.split(':', 1)[1], text)
        elif el.is_eleven_voice(voice):
            c = StationConfig.get()
            mp3 = el.text_to_speech(text, el.voice_id_of(voice), model_id=(eleven_model or c.eleven_model_id),
                                    stability=c.eleven_stability, similarity=c.eleven_similarity,
                                    style=c.eleven_style, speaker_boost=c.eleven_speaker_boost)
        elif str(voice).startswith('edge-'):
            from . import edgetts
            mp3 = edgetts.synth(text, voice=voice)
        else:
            model = gemini_model or StationConfig.get().gemini_tts_model
            mp3 = gemini_tts.synth(text, voice=voice, kind='wissen', model=model)
    except Exception as e:
        return JsonResponse({'error': str(e)[:200]}, status=502)
    return JsonResponse({'audio': 'data:audio/mp3;base64,' + base64.b64encode(mp3).decode()})


@_superuser_only
@require_POST
def compose_move(request):
    """Verschiebt einen erzeugten Sprach-Beitrag in eine andere Rubrik (ändert kind)."""
    data = json.loads(request.body or '{}')
    typ = data.get('type')
    pk = data.get('pk')
    kind = (data.get('kind') or '').strip()
    if not kind:
        return JsonResponse({'error': 'Keine Ziel-Rubrik angegeben.'}, status=400)
    if typ != 'spoken':
        return JsonResponse({'error': 'Nur Sprach-Beiträge können die Rubrik wechseln '
                             '(Musik/Effekte werden über ihren Typ einsortiert).'}, status=400)
    from .models import SpokenContent, Rubrik
    label = (Rubrik.objects.filter(key=kind).values_list('label', flat=True).first()
             or dict(SpokenContent.KIND).get(kind, kind))
    n = SpokenContent.objects.filter(pk=pk).update(kind=kind)
    if not n:
        return JsonResponse({'error': 'Beitrag nicht gefunden.'}, status=404)
    return JsonResponse({'ok': True, 'kind': kind, 'label': label})


@_superuser_only
@require_POST
def compose_generate(request):
    """Startet die Audio-Erzeugung (Celery) und liefert die Task-ID."""
    from .tasks import compose_generate_task
    data = json.loads(request.body or '{}')
    kind = data.get('kind', 'wissen')
    text = (data.get('text') or '').strip()
    voice = data.get('voice') or None
    title = (data.get('title') or '').strip() or None
    try:
        duration_sec = int(float(data.get('duration_min', 5)) * 60)
    except (ValueError, TypeError):
        duration_sec = 300
    if not text:
        return JsonResponse({'error': 'Bitte Text bzw. Beschreibung eingeben.'}, status=400)
    voice2 = data.get('voice2') or None
    speaker_a = (data.get('speaker_a') or '').strip() or None
    speaker_b = (data.get('speaker_b') or '').strip() or None
    style = (data.get('style') or '').strip() or None
    try:
        seconds = int(float(data.get('seconds', 4)))
    except (ValueError, TypeError):
        seconds = 4
    engine = (data.get('engine') or '').strip() or None
    bg_music = bool(data.get('bg_music'))
    try:
        bg_volume = max(0.0, min(1.0, float(data.get('bg_volume', 0.12))))
    except (TypeError, ValueError):
        bg_volume = 0.12
    try:
        bg_track_id = int(data.get('bg_track_id')) if data.get('bg_track_id') else None
    except (TypeError, ValueError):
        bg_track_id = None
    mm_model = (data.get('mm_model') or '').strip() or None
    lyria_model = (data.get('lyria_model') or '').strip() or None
    gemini_model = (data.get('gemini_model') or '').strip() or None
    eleven_model = (data.get('eleven_model') or '').strip() or None
    fal_model = (data.get('fal_model') or '').strip() or None
    tags = (data.get('tags') or '').strip()[:200]
    auto = bool(data.get('auto', True))

    # Auto-Übersetzung: Musik-/Effekt-Prompts versteht das Modell englisch am besten.
    # Liedtext (bei 'song' = text) bleibt unangetastet.
    if bool(data.get('translate')) and kind in ('music', 'song', 'effekt'):
        from . import glm as _glm

        def _to_en(t):
            if not t or len(t) < 3:
                return t
            try:
                out = _glm.glm_chat(
                    'Übersetze die folgende Musik-/Sound-Stilbeschreibung präzise ins Englische. '
                    'Musik-Fachbegriffe (BPM, Lo-Fi, Instrumente, Genres) korrekt verwenden. '
                    'Antworte NUR mit der Übersetzung, ohne Anführungszeichen oder Erklärungen:\n\n' + t,
                    system='Du bist Übersetzer für Musikproduktions-Prompts.', max_tokens=500).strip()
                return out or t
            except Exception:
                return t
        if kind in ('music', 'effekt'):
            text = _to_en(text)
        elif kind == 'song' and style:
            style = _to_en(style)

    res = compose_generate_task.delay(
        kind=kind, text=text, voice=voice, title=title, duration_sec=duration_sec,
        voice2=voice2, speaker_a=speaker_a, speaker_b=speaker_b, style=style, seconds=seconds,
        engine=engine, bg_music=bg_music, bg_volume=bg_volume, bg_track_id=bg_track_id,
        mm_model=mm_model, lyria_model=lyria_model, gemini_model=gemini_model, eleven_model=eleven_model,
        fal_model=fal_model, tags=tags, auto=auto,
    )
    return JsonResponse({'task_id': res.id})


@_superuser_only
def compose_status(request, task_id):
    """Pollt den Status der Audio-Erzeugung."""
    from celery.result import AsyncResult
    r = AsyncResult(task_id)
    if r.successful():
        return JsonResponse({'state': 'done', 'result': r.result})
    if r.failed():
        return JsonResponse({'state': 'failed', 'error': str(r.result)[:300]})
    return JsonResponse({'state': r.state.lower()})


@_superuser_only
@require_POST
def compose_accept(request):
    """Fügt den erzeugten Beitrag vorne in den Sendeplan ein (spielt als Nächstes)."""
    data = json.loads(request.body or '{}')
    ctype = data.get('type')
    pk = data.get('pk')
    kind = data.get('kind', 'music')
    video_url = (data.get('video_url') or '').strip()
    with transaction.atomic():
        entry = PlaylistEntry(kind=kind, status='queued', manual=True, video_url=video_url)
        if ctype == 'track':
            entry.track = Track.objects.filter(pk=pk).first()
        else:
            entry.spoken = SpokenContent.objects.filter(pk=pk).first()
        if not entry.content:
            return JsonResponse({'error': 'Inhalt nicht gefunden.'}, status=404)
        # vorne einfügen: alle wartenden eins nach hinten, neuer Beitrag auf 0
        PlaylistEntry.objects.filter(status='queued').update(position=models.F('position') + 1)
        entry.position = 0
        entry.save()
    if video_url:
        from .tasks import download_entry_video
        download_entry_video.delay(entry.pk, video_url)
    scheduler.renumber()
    return JsonResponse({'ok': True})


# ============================================================================
#  Bibliothek — alle erzeugten Audios, sortiert nach Rubriken
# ============================================================================
# Deutsches Vorlese-/Radio-Tempo für die Dauerschätzung (Wörter pro Sekunde).
# ~138 Wörter/Minute — bewusst eher ruhig, passt zu Geschichten/Moderation.
WORDS_PER_SEC = 2.3


def _fmt_dur(sec):
    """Sekunden → „m:ss" (leer, wenn unbekannt; Client liest die Dauer dann selbst aus)."""
    try:
        sec = int(sec or 0)
    except (TypeError, ValueError):
        sec = 0
    if sec <= 0:
        return ''
    return f'{sec // 60}:{sec % 60:02d}'


def _fmt_played(dt):
    """Zeitpunkt des letzten Abspielens als kompakte relative Angabe (z. B. „vor 3 Std")."""
    if not dt:
        return ''
    from django.utils import timezone as _tz
    delta = _tz.now() - dt
    s = int(delta.total_seconds())
    if s < 0:
        return ''
    if s < 90:
        return 'gerade eben'
    if s < 3600:
        return f'vor {s // 60} Min'
    if s < 86400:
        return f'vor {s // 3600} Std'
    if s < 7 * 86400:
        return f'vor {s // 86400} Tg'
    return dt.strftime('%d.%m.%Y')


_SRC_LABELS = {'lyria': 'Google Lyria', 'minimax': 'MiniMax', 'elevenmusic': 'ElevenLabs Music',
               'elevenlabs': 'ElevenLabs', 'fal': 'fal.ai', 'musicgen': 'MusicGen',
               'acestep': 'ACE-Step', 'upload': 'Upload'}


_GEN_MODEL_LABELS = {  # technische IDs -> sprechende Modellnamen
    'music-generator': 'CassetteAI',
    'cassetteai/music-generator': 'CassetteAI',
    'text-to-audio': 'Stable Audio 2.5',
    'fal-ai/stable-audio-25/text-to-audio': 'Stable Audio 2.5',
    'lyria-3-pro-preview': 'Lyria 3 Pro',
    'lyria-3-clip-preview': 'Lyria 3 Clip',
    'pro': 'Gemini Pro-TTS',
    'flash': 'Gemini Flash-TTS',
}


def _engine_label_track(t):
    base = _SRC_LABELS.get(t.source, t.source or '—')
    gm = getattr(t, 'gen_model', '')
    return f'{base} · {_GEN_MODEL_LABELS.get(gm, gm)}' if gm else base


def _engine_label_voice(voice):
    v = voice or ''
    if v.startswith('gemini-'):
        eng = 'Gemini'
    elif v.startswith('xtts'):
        eng = 'XTTS'
    elif v.startswith('fal:'):
        eng = 'fal.ai'
    elif 'eleven' in v.lower():
        eng = 'ElevenLabs'
    elif v.startswith('piper'):
        eng = 'Piper'
    else:
        eng = '—'
    return f'{eng} · {v}' if v else eng


def _fmt_created(dt):
    """Erstellzeit als 'TT.MM.JJJJ HH:MM' in Berlin-Zeit (oder '')."""
    if not dt:
        return ''
    try:
        return dt.astimezone(BERLIN).strftime('%d.%m.%Y %H:%M')
    except Exception:
        return ''


def _track_item(t):
    return {'type': 'track', 'pk': t.pk, 'title': t.title, 'engine': _engine_label_track(t),
            'created': _fmt_created(t.created_at),
            'audio_url': t.audio_file.url if t.audio_file else '',
            'sub': (t.description or t.mood or ''), 'dur': _fmt_dur(t.duration_sec),
            'played': _fmt_played(t.last_played_at),
            'auto': t.is_active, 'tags': t.tags or '', 'genre': t.mood or '',
            'text': t.lyrics or '', 'text_kind': 'lyrics' if t.lyrics else ''}


@_superuser_only
def library_list(request):
    """Liefert die Bibliothek als Kategorien (Rubriken) mit ihren Audio-Beiträgen."""
    cats = []
    tracks = list(Track.objects.exclude(audio_file='').order_by('-created_at'))
    def _tk(t):
        if t.category in ('music', 'song', 'effekt', 'ad'):
            return t.category
        if t.source == 'elevenlabs' or t.mood == 'jingle':
            return 'effekt'
        if t.lyrics or t.source == 'acestep':
            return 'song'
        return 'music'
    songs = [t for t in tracks if _tk(t) == 'song']
    fx = [t for t in tracks if _tk(t) == 'effekt']
    track_ads = [t for t in tracks if _tk(t) == 'ad']
    music = [t for t in tracks if _tk(t) == 'music']
    if music:
        cats.append({'key': 'music', 'label': '🎵 Musik (instrumental)', 'items': [_track_item(t) for t in music]})
    if songs:
        cats.append({'key': 'song', 'label': '🎤 Musik mit Gesang', 'items': [_track_item(t) for t in songs]})
    if fx:
        cats.append({'key': 'effekt', 'label': '🔔 Sound-Effekte / Jingles', 'items': [_track_item(t) for t in fx]})
    if track_ads:
        cats.append({'key': 'ad', 'label': '📣 Werbung / Spots (Musik)', 'items': [_track_item(t) for t in track_ads]})

    # Wort-Inhalte je vorhandener Rubrik (kind) — mit gesprochenem Text
    from .models import Rubrik as _Rb
    kind_labels = dict(SpokenContent.KIND)
    kind_labels.update({r.key: r.label for r in _Rb.objects.all()})  # eigene Rubriken: echter Name
    present = (SpokenContent.objects.exclude(audio_file='').exclude(audio_file__isnull=True)
               .order_by().values_list('kind', flat=True).distinct())
    for k in present:
        items = [{'type': 'spoken', 'pk': s.pk, 'title': s.title,
                  'audio_url': s.audio_file.url if s.audio_file else '',
                  'sub': (s.description or (s.air_date.strftime('%d.%m.%Y') if s.air_date else '')),
                  'dur': _fmt_dur(s.duration_sec), 'played': _fmt_played(s.last_played_at),
                  'auto': s.auto_include, 'tags': s.tags or '', 'genre': s.description or '',
                  'engine': _engine_label_voice(s.voice) + ((' · ' + _GEN_MODEL_LABELS.get(s.gen_model, s.gen_model)) if getattr(s, 'gen_model', '') else ''), 'created': _fmt_created(s.created_at),
                  'text': s.text or '', 'text_kind': 'text' if s.text else ''}
                 for s in SpokenContent.objects.filter(kind=k).exclude(audio_file='').order_by('-created_at')]
        if items:
            existing = next((c for c in cats if c['key'] == k), None)
            if existing:  # z. B. 'ad': gesungene (Track) + gesprochene Spots in EINER Rubrik
                existing['label'] = '📣 Werbung / Spots'
                existing['items'].extend(items)
            else:
                cats.append({'key': k, 'label': kind_labels.get(k, k.title()), 'items': items})

    total = sum(len(c['items']) for c in cats)
    music_sec = sum((t.duration_sec or 0) for t in tracks)
    speech_sec = (SpokenContent.objects.exclude(audio_file='').exclude(audio_file__isnull=True)
                  .aggregate(x=models.Sum('duration_sec'))['x'] or 0)
    return JsonResponse({'categories': cats, 'total': total,
                         'music_sec': music_sec, 'speech_sec': speech_sec})


@_superuser_only
@require_POST
def library_toggle_auto(request):
    """Schaltet, ob ein Inhalt AUTOMATISCH eingeplant werden darf
    (Track.is_active bzw. SpokenContent.auto_include). Manuell bleibt er nutzbar."""
    data = json.loads(request.body or '{}')
    on = bool(data.get('on'))
    if data.get('type') == 'track':
        obj = Track.objects.filter(pk=data.get('pk')).first()
        if not obj:
            return JsonResponse({'error': 'nicht gefunden'}, status=404)
        obj.is_active = on
        obj.save(update_fields=['is_active'])
    else:
        obj = SpokenContent.objects.filter(pk=data.get('pk')).first()
        if not obj:
            return JsonResponse({'error': 'nicht gefunden'}, status=404)
        obj.auto_include = on
        obj.save(update_fields=['auto_include'])
    return JsonResponse({'ok': True, 'on': on})


@_superuser_only
@require_POST
def content_tags(request):
    """Setzt die Tags (kommasepariert) eines Inhalts."""
    data = json.loads(request.body or '{}')
    tags = (data.get('tags') or '').strip()[:200]
    obj = (Track.objects.filter(pk=data.get('pk')).first() if data.get('type') == 'track'
           else SpokenContent.objects.filter(pk=data.get('pk')).first())
    if not obj:
        return JsonResponse({'error': 'nicht gefunden'}, status=404)
    obj.tags = tags
    obj.save(update_fields=['tags'])
    return JsonResponse({'ok': True, 'tags': tags})


@_superuser_only
def tags_list(request):
    """Alle Inhalts-Tags (Saison-Tags) für Verwaltung/Anzeige."""
    from .models import ContentTag
    out = [{'name': t.name, 'label': t.label, 'color': t.color,
            'start_md': t.start_md, 'end_md': t.end_md, 'boost': t.boost,
            'exclusive': t.exclusive, 'is_active': t.is_active}
           for t in ContentTag.objects.all()]
    return JsonResponse({'tags': out})


@_superuser_only
def radio_stats(request):
    """Live-Statistik aus Icecast: aktuelle Hörer, Tagesspitze, gesendeter Traffic."""
    import urllib.request, base64, re as _re
    user = os.environ.get('ICECAST_ADMIN_USER', 'admin')
    pw = os.environ.get('ICECAST_ADMIN_PW', '')
    out = {'ok': False, 'listeners': 0, 'peak': 0, 'bytes': 0, 'since': ''}
    try:
        req = urllib.request.Request('http://127.0.0.1:8000/admin/stats.xml')
        req.add_header('Authorization', 'Basic ' + base64.b64encode(('%s:%s' % (user, pw)).encode()).decode())
        xml = urllib.request.urlopen(req, timeout=5).read().decode('utf-8', 'ignore')
    except Exception:
        return JsonResponse(out)
    m = _re.search(r'<server_start_iso8601>([^<]+)', xml)
    if m:
        out['since'] = m.group(1)
    seg = _re.search(r'<source mount="/radio\.mp3".*?</source>', xml, _re.S)
    block = seg.group(0) if seg else xml

    def num(tag, s):
        mm = _re.search(r'<%s>(\d+)' % tag, s)
        return int(mm.group(1)) if mm else 0
    out['listeners'] = num('listeners', block)
    out['peak'] = num('listener_peak', block)
    out['bytes'] = num('total_bytes_sent', block)
    out['ok'] = True
    return JsonResponse(out)


@_superuser_only
def tags_overview(request):
    """Übersicht ALLER Tags: definierte Saison-Tags + tatsächlich an Inhalten
    verwendete Schlagworte (mit Anzahl). Für Autovervollständigung + Verwaltung."""
    from .models import ContentTag
    from collections import Counter
    cnt = Counter()
    rows = (list(Track.objects.exclude(tags='').values_list('tags', flat=True))
            + list(SpokenContent.objects.exclude(tags='').values_list('tags', flat=True)))
    for tagstr in rows:
        for name in [x.strip().lower() for x in (tagstr or '').split(',') if x.strip()]:
            cnt[name] += 1
    defined = {t.name: t for t in ContentTag.objects.all()}
    out = []
    for name in sorted(set(cnt) | set(defined)):
        d = defined.get(name)
        out.append({'name': name, 'count': cnt.get(name, 0), 'defined': bool(d),
                    'season': ((d.start_md + '–' + d.end_md) if (d and d.start_md and d.end_md) else ''),
                    'start_md': (d.start_md if d else ''), 'end_md': (d.end_md if d else ''),
                    'boost': (d.boost if d else 1), 'exclusive': (d.exclusive if d else True),
                    'color': (d.color if d else '')})
    return JsonResponse({'tags': out})


@_superuser_only
@require_POST
def tag_save(request):
    """Legt einen Inhalts-Tag an oder aktualisiert ihn (Schlüssel = name)."""
    from .models import ContentTag
    from django.utils.text import slugify
    data = json.loads(request.body or '{}')
    name = slugify(data.get('name') or '')[:40]
    if not name:
        return JsonResponse({'error': 'Name fehlt'}, status=400)
    tag, _ = ContentTag.objects.get_or_create(name=name)
    tag.label = (data.get('label') or name)[:80]
    tag.color = (data.get('color') or '#8b5cf6')[:9]
    tag.start_md = (data.get('start_md') or '')[:5]
    tag.end_md = (data.get('end_md') or '')[:5]
    tag.exclusive = bool(data.get('exclusive', True))
    try:
        tag.boost = max(1, min(10, int(data.get('boost', tag.boost or 1))))
    except (TypeError, ValueError):
        pass
    tag.is_active = bool(data.get('is_active', True))
    tag.save()
    return JsonResponse({'ok': True, 'name': name})


@_superuser_only
@require_POST
def tag_delete(request):
    """Löscht einen Inhalts-Tag (die Tag-Namen an Inhalten bleiben als Text bestehen)."""
    from .models import ContentTag
    data = json.loads(request.body or '{}')
    ContentTag.objects.filter(name=data.get('name')).delete()
    return JsonResponse({'ok': True})


# ============================================================================
#  Planbare Tages-Timeline (absolute Pins + theoretische Vorschau)
# ============================================================================
def _parse_date(s):
    from datetime import datetime as _dt
    try:
        return _dt.strptime(s, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return timezone.now().astimezone(BERLIN).date()


def _pin_dict(p):
    return {'pk': p.pk, 'name': p.name, 'mode': p.mode, 'rubrik_key': p.rubrik_key,
            'track': p.track_id, 'spoken': p.spoken_id,
            'track_title': p.track.title if p.track_id else '',
            'spoken_title': p.spoken.title if p.spoken_id else '',
            'start_time': p.start_time.strftime('%H:%M'),
            'on_date': p.on_date.isoformat() if p.on_date else '',
            'days': p.days, 'enforce': p.enforce, 'topic': p.topic,
            'is_active': p.is_active, 'order': p.order,
            'gen_status': p.gen_status,
            'target_sec': (p.gen_spec or {}).get('duration_sec') or (p.gen_spec or {}).get('seconds') or 60,
            'gen_text': (p.gen_spec or {}).get('text', ''),
            'gen_title': (p.gen_spec or {}).get('title', ''),
            'gen_voice': (p.gen_spec or {}).get('voice', ''),
            'gen_style': (p.gen_spec or {}).get('style', ''),
            'gen_engine': (p.gen_spec or {}).get('engine', ''),
            'gen_auto': (p.gen_spec or {}).get('auto', False),
            'gen_tags': (p.gen_spec or {}).get('tags', '')}


@_superuser_only
def timeline(request):
    """Seite: planbare Tages-Timeline mit Kacheln."""
    gemini_voices = [(v, l) for (v, l) in STUDIO_VOICES if v.startswith('gemini-')]
    return render(request, 'radio/timeline.html', {
        'config': StationConfig.get(),
        'kinds': planner_kinds(),
        'voices': gemini_voices,
        'today': timezone.now().astimezone(BERLIN).date(),
    })


@_superuser_only
def timeline_data(request):
    """JSON: voraussichtliche Timeline (real + theoretisch) + editierbare Pins eines Tages."""
    from . import scheduler
    d = _parse_date(request.GET.get('date'))
    rows = scheduler.projected_timeline(d)
    pins = [_pin_dict(p) for p in ScheduledItem.objects.filter(is_active=True) if p.applies_on(d)]
    return JsonResponse({'date': d.isoformat(), 'rows': rows, 'pins': pins})


@_superuser_only
@require_POST
def pin_save(request):
    """Legt einen Pin (ScheduledItem) an oder aktualisiert ihn (spiegelt slot_save)."""
    from datetime import datetime as _dt
    data = json.loads(request.body or '{}')
    pk = data.get('pk')
    p = ScheduledItem.objects.filter(pk=pk).first() if pk else ScheduledItem()
    if pk and not p:
        return JsonResponse({'error': 'nicht gefunden'}, status=404)
    p.name = (data.get('name') or '')[:120]
    mode = data.get('mode') if data.get('mode') in dict(ScheduledItem.MODES) else 'rubrik_auto'
    p.mode = mode
    valid_keys = {k for k, _ in planner_kinds()}
    rk = data.get('rubrik_key') or ''
    p.rubrik_key = rk if rk in valid_keys else ''
    p.track = Track.objects.filter(pk=data.get('track')).first() if mode == 'pinned_track' else None
    p.spoken = SpokenContent.objects.filter(pk=data.get('spoken')).first() if mode == 'pinned_spoken' else None

    fire_compose = False
    if mode == 'compose':
        p.rubrik_key = rk if rk in valid_keys else 'wissen'
        gtext = (data.get('gen_text') or '').strip()
        if not gtext:
            return JsonResponse({'error': 'Bitte Text bzw. Anweisung für den Beitrag eingeben.'}, status=400)
        try:
            tsec = max(3, int(data.get('target_sec') or 60))
        except (TypeError, ValueError):
            tsec = 60
        spec = {'kind': p.rubrik_key, 'text': gtext[:8000],
                'title': (data.get('gen_title') or p.name or '')[:200],
                'auto': bool(data.get('gen_auto')), 'tags': (data.get('tags') or '')[:200]}
        if data.get('gen_voice'):
            spec['voice'] = data['gen_voice']
        if p.rubrik_key in ('music', 'song'):
            spec['duration_sec'] = tsec
            if data.get('gen_style'):
                spec['style'] = data['gen_style'][:300]
            if data.get('gen_engine'):
                spec['engine'] = data['gen_engine']
        elif p.rubrik_key == 'effekt':
            spec['seconds'] = min(30, tsec)
            if data.get('gen_engine'):
                spec['engine'] = data['gen_engine']
        p.gen_spec = spec
        # nur bei NEUEM Pin oder geänderter Spec neu erzeugen
        if (not pk) or p.gen_status not in ('done',) or (data.get('regen')):
            p.gen_status = 'pending'
            p.track = None
            p.spoken = None
            fire_compose = True
    try:
        p.start_time = _dt.strptime(data.get('start_time') or '12:00', '%H:%M').time()
    except ValueError:
        return JsonResponse({'error': 'Ungültige Uhrzeit'}, status=400)
    od = data.get('on_date') or ''
    try:
        p.on_date = _dt.strptime(od, '%Y-%m-%d').date() if od else None
    except ValueError:
        p.on_date = None
    days = data.get('days') or []
    p.days = ','.join(str(int(x)) for x in days if str(x).isdigit()) if isinstance(days, list) else ''
    p.enforce = data.get('enforce') if data.get('enforce') in dict(ScheduledItem.ENFORCE) else 'anchor'
    p.topic = (data.get('topic') or '')[:200]
    p.is_active = bool(data.get('is_active', True))
    try:
        p.order = int(data.get('order') or 0)
    except (TypeError, ValueError):
        p.order = 0
    p.save()
    if fire_compose:
        from .tasks import generate_pin_content
        generate_pin_content.delay(p.pk)
    # Steht ein bereits vorgeplanter Tag an, auf den dieser Pin in den nächsten
    # 7 Tagen fällt? Dann ist er dort NICHT automatisch enthalten -> Nutzer fragen.
    planned_info = None
    if p.is_active:
        from datetime import timedelta as _td2, date as _date2
        now2 = timezone.now()
        # bis wann ist die Queue geplant?
        last_st = (PlaylistEntry.objects.filter(status='queued')
                   .exclude(scheduled_time=None).order_by('-scheduled_time')
                   .values_list('scheduled_time', flat=True).first())
        if last_st:
            planned_through = last_st.astimezone(BERLIN).date()
            today2 = now2.astimezone(BERLIN).date()
            for off in range(0, 8):
                d = today2 + _td2(days=off)
                if d > planned_through:
                    break
                if p.applies_on(d):
                    pt = _dt.combine(d, p.start_time)
                    # nur künftige Zeitpunkte zählen
                    import datetime as _dtm
                    if _dtm.datetime.combine(d, p.start_time, tzinfo=BERLIN) > now2:
                        WD = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
                        planned_info = {'date': d.isoformat(),
                                        'label': '%s, %s' % (WD[d.weekday()], d.strftime('%d.%m.')),
                                        'time': p.start_time.strftime('%H:%M')}
                        break
    return JsonResponse({'ok': True, 'pk': p.pk, 'pin': _pin_dict(p),
                         'already_planned': planned_info})


@_superuser_only
@require_POST
def pin_delete(request):
    data = json.loads(request.body or '{}')
    ScheduledItem.objects.filter(pk=data.get('pk')).delete()
    return JsonResponse({'ok': True})


@_superuser_only
def content_picker(request):
    """JSON wählbarer konkreter Beiträge (für feste Pins). Optional ?kind=."""
    kind = (request.GET.get('kind') or '').strip()
    out = []
    for t in Track.objects.exclude(audio_file='').order_by('-created_at')[:200]:
        out.append({'type': 'track', 'pk': t.pk, 'title': t.title,
                    'sub': (t.mood or t.description or '')[:60], 'dur': _fmt_dur(t.duration_sec)})
    sq = SpokenContent.objects.filter(status='generated').exclude(audio_file='').order_by('-created_at')
    if kind:
        sq = sq.filter(kind=kind)
    for s in sq[:200]:
        out.append({'type': 'spoken', 'pk': s.pk, 'title': s.title,
                    'sub': s.get_kind_display(), 'dur': _fmt_dur(s.duration_sec)})
    return JsonResponse({'items': out})


@_superuser_only
@require_POST
def replan_now(request):
    """Baut den kompletten anstehenden Sendeplan ab JETZT neu auf (inkl. gerade
    gesetzter Pins). Der laufende Titel bleibt unberührt; nur die Warteschlange
    wird verworfen und sauber neu materialisiert + auf >=10 h aufgefüllt."""
    from . import scheduler
    try:
        scheduler.materialize_day(None, replace=True, generate=False)  # heute ab jetzt neu
        made = scheduler.ensure_queue_filled(min_hours=10, max_days=3)  # Folgetage anhängen
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    n, reach = _queue_reach()
    return JsonResponse({'ok': True, 'count': n, 'reach': reach})


@_superuser_only
def materialize_now(request):
    """Materialisiert den Tagesplan eines Tages in die Queue (async, erzeugt fehlende Beiträge)."""
    from .tasks import materialize_day_task
    data = json.loads(request.body or '{}')
    d = data.get('date') or None
    replace = bool(data.get('replace'))
    has_plan = (ScheduledItem.objects.filter(is_active=True).exists()
                or ProgramSlot.objects.filter(is_active=True).exists())
    if not has_plan:
        return JsonResponse({'error': 'Kein Tagesplan vorhanden (Pins oder Slots anlegen).'}, status=400)
    res = materialize_day_task.delay(target_date_iso=d, replace=replace, generate=True)
    return JsonResponse({'ok': True, 'task_id': res.id})


@_superuser_only
@require_POST
def library_upload(request):
    """Lädt eine Audiodatei in die Bibliothek (mit Kurzbeschreibung + optional Text/Lyrics)."""
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'Keine Datei.'}, status=400)
    title = (request.POST.get('title') or f.name.rsplit('.', 1)[0])[:200]
    desc = (request.POST.get('description') or '')[:300]
    text = request.POST.get('text') or ''
    ctype = request.POST.get('ctype') or 'music'  # 'music' | 'song' | 'spoken'
    dur = 0
    if ctype == 'spoken':
        sc = SpokenContent(kind=(request.POST.get('kind') or 'wissen'), title=title,
                           description=desc, text=text, voice='upload', status='generated')
        sc.audio_file.save(f'upload_{sc.pk or ""}{f.name}', f, save=False)
        sc.save()
        sc.duration_sec = _probe_dur(sc.audio_file.path)
        sc.save(update_fields=['duration_sec'])
        return JsonResponse({'ok': True, 'type': 'spoken', 'pk': sc.pk})
    t = Track(title=title, description=desc, source='upload',
              lyrics=(text if ctype == 'song' else ''), mood=desc[:120])
    t.audio_file.save(f.name, f, save=False)
    t.save()
    t.duration_sec = _probe_dur(t.audio_file.path)
    t.save(update_fields=['duration_sec'])
    return JsonResponse({'ok': True, 'type': 'track', 'pk': t.pk})


def _probe_dur(path):
    import subprocess
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=30).stdout.strip()
        return int(float(out)) if out else 0
    except Exception:
        return 0


@_superuser_only
def music_search(request):
    """Seite: freie Musik bei Openverse suchen und in die Bibliothek übernehmen
    (gleiche Bedienung wie der Pexels-Video-Picker, nur für Musik)."""
    return render(request, 'radio/music_search.html', {'config': StationConfig.get()})


@_superuser_only
def openverse_search(request):
    """Sucht freie Musik bei Openverse (JSON, paginiert – wie pexels_search)."""
    from . import openverse
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'results': [], 'page': 1, 'pages': 1, 'total': 0})
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        return JsonResponse(openverse.search(q, page=page))
    except Exception as e:
        return JsonResponse({'error': str(e)[:160]}, status=502)


@_superuser_only
@require_POST
def openverse_import(request):
    """Lädt einen Openverse-Track herunter und speichert ihn als Track in der Bibliothek."""
    from django.core.files.base import ContentFile
    from . import openverse
    data = json.loads(request.body or '{}')
    url = (data.get('url') or '').strip()
    title = (data.get('title') or 'Openverse-Track')[:200]
    if not url:
        return JsonResponse({'error': 'Keine Audio-URL.'}, status=400)
    # Doppelte vermeiden: gleicher Titel + Quelle bereits vorhanden?
    if Track.objects.filter(source='openverse', title=title).exists():
        return JsonResponse({'error': 'Dieser Track ist bereits in der Bibliothek.'}, status=409)
    try:
        raw = openverse.fetch_audio(url)
    except Exception as e:
        return JsonResponse({'error': f'Download fehlgeschlagen: {str(e)[:120]}'}, status=502)
    if not raw or len(raw) < 2048:
        return JsonResponse({'error': 'Leere/zu kleine Audiodatei erhalten.'}, status=502)
    attrib = openverse.attribution(data)
    t = Track(title=title, description=attrib[:300], source='openverse',
              mood=(data.get('license') or 'openverse')[:120])
    safe = ''.join(c for c in title if c.isalnum() or c in ' -_')[:60].strip() or 'track'
    t.audio_file.save(f'openverse_{safe}.mp3', ContentFile(raw), save=False)
    t.save()
    t.duration_sec = _probe_dur(t.audio_file.path)
    t.save(update_fields=['duration_sec'])
    return JsonResponse({'ok': True, 'pk': t.pk, 'title': title, 'attribution': attrib})


# ============================================================================
#  Öffentliche Hörseite (einbettbar auf naturmacher.de)
# ============================================================================
def _entry_info(e):
    """Titel + Rubrik-Label eines PlaylistEntry (Track oder gesprochener Beitrag)."""
    if getattr(e, 'spoken_id', None) and e.spoken:
        try:
            kind = e.spoken.get_kind_display()
        except Exception:
            kind = getattr(e.spoken, 'kind', '') or ''
        return e.spoken.title, kind
    if getattr(e, 'track_id', None) and e.track:
        mood = (getattr(e.track, 'mood', '') or '')
        kind = 'Jingle' if mood == 'jingle' else 'Musik'
        return e.track.title, kind
    return '—', ''


@xframe_options_exempt
def live_page(request):
    """Öffentliche, einbettbare Radio-Hörseite (Dark/Glassmorphism). Kein Login."""
    from .models import ScheduledItem as _SI
    import json as _json
    rub_times = {}
    for _p in _SI.objects.filter(is_active=True).order_by('start_time'):
        if _p.rubrik_key:
            rub_times.setdefault(_p.rubrik_key, []).append(_p.start_time.strftime('%H:%M'))
    return render(request, 'radio/live.html', {'config': StationConfig.get(),
                                               'rubrik_times_json': _json.dumps(rub_times)})


def _stream_capacity():
    """Aktuelle Hörerzahl vs. Limit (für „voll → bitte YouTube nutzen")."""
    import urllib.request, base64, re as _re
    try:
        maxc = int(os.environ.get('ICECAST_MAX_CLIENTS', 100))
    except (TypeError, ValueError):
        maxc = 100
    reserve = 2  # Puffer (u.a. die eine YouTube-Einspeisung)
    try:
        user = os.environ.get('ICECAST_ADMIN_USER', 'admin')
        pw = os.environ.get('ICECAST_ADMIN_PW', '')
        req = urllib.request.Request('http://127.0.0.1:8000/admin/stats.xml')
        req.add_header('Authorization', 'Basic ' + base64.b64encode(('%s:%s' % (user, pw)).encode()).decode())
        xml = urllib.request.urlopen(req, timeout=4).read().decode('utf-8', 'ignore')
        seg = _re.search(r'<source mount="/radio\.mp3".*?</source>', xml, _re.S)
        block = seg.group(0) if seg else xml
        mm = _re.search(r'<listeners>(\d+)', block)
        listeners = int(mm.group(1)) if mm else 0
    except Exception:
        return {'listeners': 0, 'max': maxc, 'full': False}
    return {'listeners': listeners, 'max': maxc, 'full': listeners >= max(1, maxc - reserve)}


def _content_ref(e):
    """Track/Spoken-Referenz + Auto-Status eines Eintrags (für Dashboard-Schalter)."""
    if e.track_id and e.track:
        return {'type': 'track', 'pk': e.track_id, 'auto': bool(e.track.is_active)}
    if e.spoken_id and e.spoken:
        return {'type': 'spoken', 'pk': e.spoken_id,
                'auto': bool(getattr(e.spoken, 'auto_include', True))}
    return None


def live_state(request):
    """Öffentlicher Live-Status (JSON): läuft gerade + als Nächstes. Selbst-aktualisierend."""
    from django.utils import timezone as _tz
    current = (PlaylistEntry.objects.filter(status='playing')
               .select_related('track', 'spoken').order_by('-started_at').first())
    queued = list(PlaylistEntry.objects.filter(status='queued')
                  .select_related('track', 'spoken').order_by('position')[:6])
    now = _tz.now()
    t = now
    if current and current.started_at:
        rest = (current.duration_sec or 0) - (now - current.started_at).total_seconds()
        if rest > 0:
            t = now + timedelta(seconds=rest)
    nxt = []
    for e in queued:
        pe = t.astimezone(BERLIN)
        ti, ki = _entry_info(e)
        item = {'title': ti, 'kind': ki, 'kind_key': e.kind, 'time': pe.strftime('%H:%M')}
        if request.user.is_authenticated and request.user.is_superuser:
            item['engine'], item['prompt'] = _entry_meta(e)
            item['ref'] = _content_ref(e)
            item['entry_pk'] = e.pk
        nxt.append(item)
        t += timedelta(seconds=e.duration_sec or 120)
    cur = None
    if current:
        ti, ki = _entry_info(current)
        cur = {'title': ti, 'kind': ki, 'kind_key': current.kind,
               'started': int(current.started_at.timestamp()) if current.started_at else None,
               'dur': current.duration_sec or 0,
               'server_now': int(now.timestamp())}
        if request.user.is_authenticated and request.user.is_superuser:
            cur['engine'], cur['prompt'] = _entry_meta(current)
            cur['ref'] = _content_ref(current)
    prev_e = (PlaylistEntry.objects.filter(status='played')
              .exclude(pk=current.pk if current else 0)
              .select_related('track', 'spoken').order_by('-started_at', '-id').first())
    prev = None
    if prev_e:
        ti, ki = _entry_info(prev_e)
        prev = {'title': ti, 'kind': ki, 'kind_key': prev_e.kind,
                'time': prev_e.started_at.astimezone(BERLIN).strftime('%H:%M') if prev_e.started_at else ''}
        if request.user.is_authenticated and request.user.is_superuser:
            prev['engine'], prev['prompt'] = _entry_meta(prev_e)
            prev['ref'] = _content_ref(prev_e)
    config = StationConfig.get()
    try:
        with open(os.path.join(settings.MEDIA_ROOT, 'radio', 'stream_enabled')) as f:
            live = f.read().strip() != '0'
    except OSError:
        live = True
    warn = ''
    if request.user.is_authenticated and request.user.is_superuser:
        from datetime import date as _dw
        from zoneinfo import ZoneInfo as _ZIw
        _hw = timezone.now().astimezone(_ZIw('Europe/Berlin')).hour
        _edw = None
        if 9 <= _hw < 14:
            _edw = 'Morgenausgabe'
        elif 14 <= _hw < 20:
            _edw = 'Mittagsausgabe'
        elif _hw >= 20:
            _edw = 'Abendausgabe'
        if _edw and not SpokenContent.objects.filter(
                kind='news', air_date=_dw.today(), status='generated',
                title__contains=_edw).exists():
            warn = f'Journal-{_edw} heute fehlt — News-Slot nutzt Saisonales-Fallback.'
    resp = JsonResponse({'on_air': bool(config.on_air and live), 'now': cur, 'next': nxt, 'prev': prev,
                         'warn': warn,
                         'cap': _stream_capacity(),
                         'youtube_url': config.youtube_url or ''})
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


def app_state(request):
    """Öffentlicher Status für die Naturmacher-Radio-App (JSON):
    läuft gerade + projizierter Sendeplan + geplante Sendungen (Pins, markiert).
    Bewusst OHNE interne Metadaten (Engine/Prompts)."""
    days, queued, current, nxt = _projected_days()
    WD = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    sched = []
    for day in days:
        for e in day['entries']:
            sched.append({'_dt': e.proj, 'title': e.title, 'kind': e.get_kind_display(),
                          'kind_key': e.kind, 'time': e.proj_str,
                          'day_label': day['label'], 'pinned': False,
                          'prompt': getattr(e, 'gen_prompt', '') or ''})
    for pin in _upcoming_pins(days=3, limit=25):
        dt = pin['dt']
        sched.append({'_dt': dt, 'title': pin['content'], 'kind': 'Geplante Sendung',
                      'kind_key': 'pin', 'time': pin['time'],
                      'day_label': f"{WD[dt.weekday()]}, {dt.strftime('%d.%m.')}",
                      'pinned': True})
    sched.sort(key=lambda x: x['_dt'])
    for it in sched:
        it.pop('_dt', None)
    cur = None
    if current:
        ti, ki = _entry_info(current)
        cur = {'title': ti, 'kind': ki, 'kind_key': current.kind,
               'started': int(current.started_at.timestamp()) if current.started_at else None,
               'dur': current.duration_sec or 0}
    config = StationConfig.get()
    _pc = StationConfig.get()
    raw_lines = [l.strip() for l in (_pc.app_promo_lines or '').splitlines() if l.strip()]
    cfg_lines = [l for l in raw_lines if not l.startswith('#')]  # '#' = deaktiviert
    promo = {
        'url': _pc.app_promo_url or 'https://www.naturmacher.de/',
        'code': _pc.app_promo_code or 'Naturmacher-Radio',
        'benefit': _pc.app_promo_benefit or '',
        'lines': cfg_lines or ['Personalisierte Blumentöpfe & Anzuchtsets – naturmacher.de'],
    }
    if (request.GET.get('all') and request.user.is_authenticated
            and request.user.is_superuser):
        promo['all_lines'] = raw_lines  # inkl. deaktivierter (für die Verwaltung)
    resp = JsonResponse({'on_air': bool(config.on_air), 'now': cur,
                         'schedule': sched[:120],
                         'promo': promo,
                         'stream': 'https://alexa.workloom.de/radio/live.mp3'})
    resp['Cache-Control'] = 'no-store, max-age=0'
    resp['Access-Control-Allow-Origin'] = '*'
    return resp


RUBRIK_ABOUT = [
    ('🧠 Wissen', [
        ('anna-theo', 'Anna fragt, Opa Theo weiß es', 'Die neugierige Anna stellt die Fragen, die Kinder wirklich beschäftigen – und ihr Opa Theo erklärt sie warmherzig, geduldig und anschaulich.'),
        ('falsch-oder-fakt', 'Falsch oder Fakt?', 'Eine verblüffende Behauptung – stimmt sie oder nicht? Erst raten, dann staunen: das Mitrate-Format für die ganze Familie.'),
        ('zahlen-bitte', 'Zahlen, bitte!', 'Eine einzige erstaunliche Zahl und die spannende Geschichte dahinter – kurz, knackig, zum Weitererzählen.'),
        ('wissen', 'Wissenswertes', 'Spannendes Wissen aus Natur, Garten und Alltag – freundlich erklärt in zwei Minuten.'),
        ('news', 'Saisonales & News', 'Was gerade ansteht: Aussaat-Zeiten, Gartenarbeiten des Monats und Saisonales aus dem Jahreslauf der Natur.'),
    ]),
    ('🌱 Garten & Natur', [
        ('tip', 'Gartentipp', 'Ein praktischer Tipp für Topf, Beet oder Balkon – konkret erklärt und sofort umsetzbar.'),
        ('spaziergang', 'Sonntags-Spaziergang', 'Ein gemütlicher Hörspaziergang durch Wald und Wiese – entdecken, was am Wegesrand wächst, summt und raschelt.'),
        ('bastelidee', 'Bastelidee Natur', 'Schritt-für-Schritt-Anleitungen zum Basteln mit der Natur – von der Bienentränke bis zum Blätterdruck.'),
        ('kreativ', 'Kreativ-Beitrag', 'Kreative Projekte zum Selbermachen für drinnen und draußen – mal künstlerisch, mal praktisch.'),
    ]),
    ('🧘 Achtsamkeit', [
        ('garten-meditation', 'Garten-Meditation', 'Eine geführte Meditation mitten im Garten – extrem langsam und einfühlsam gesprochen, mit sanfter Musik. Zum richtigen Loslassen.'),
        ('drei-atemzuege', 'Drei Atemzüge', 'Die kürzeste Pause der Welt: drei bewusste Atemzüge, liebevoll angeleitet.'),
        ('tee-minute', 'Die Tee-Minute', 'Eine Tasse Tee, ein ruhiger Gedanke – kleine Auszeit zum Durchatmen.'),
        ('perspektivwechsel', 'Der Perspektivwechsel', 'Ein vertrautes Thema aus überraschend neuem Blickwinkel – regt zum Nachdenken und Schmunzeln an.'),
    ]),
    ('👪 Familie', [
        ('omas-trick', 'Omas Trick', 'Bewährte Haushalts- und Lebenstricks aus Großmutters Schatzkiste – einfach, günstig, verblüffend wirksam.'),
        ('blitzrezept', 'Blitzrezept – einfach & gesund', 'Gesunde Rezepte mit maximal fünf Zutaten – schnell gekocht, von Kindern geliebt.'),
        ('klanggeschichte', 'Hörgeschichten mit Klangkulisse', 'Geschichten zum Eintauchen mit echten Geräuschen und Atmosphäre – Kino für die Ohren.'),
        ('story', 'Gute-Nacht-Geschichte', 'Ruhige, liebevoll erzählte Geschichten zum Einschlafen – das tägliche Abendritual.'),
        ('dialog', 'Gespräch zu zweit', 'Zwei Stimmen, ein Thema: ein lockeres Gespräch wie am Küchentisch.'),
    ]),
]


@_superuser_only
def presence_state(request):
    """Überblick: wo der Sender überall verfügbar ist + aktueller Zustand."""
    import subprocess
    # Live-Checks
    stream_ok = False
    try:
        import urllib.request as _ur
        with _ur.urlopen('http://127.0.0.1:8000/status-json.xsl', timeout=5) as r:
            stream_ok = b'radio.mp3' in r.read()
    except Exception:
        pass
    push = {'youtube': False, 'twitch': False, 'kick': False}
    try:
        out = subprocess.run(['pgrep', '-af', 'ffmpeg'], capture_output=True, text=True, timeout=5).stdout
        push['youtube'] = 'rtmp.youtube.com' in out
        push['twitch'] = 'live.twitch.tv' in out
        push['kick'] = 'live-video.net' in out
    except Exception:
        pass
    onair = StationConfig.get().on_air
    yt = StationConfig.get().youtube_url or 'https://www.youtube.com/@naturmacher'

    def st(ok, live='Live', down='Gestört'):
        return {'state': 'ok' if ok else 'warn', 'label': live if ok else down}

    groups = [
        ('📻 Stream & Hören', [
            {'name': 'Sender-Kern (Icecast/Liquidsoap)', 'url': '', **st(stream_ok and onair, 'On Air', 'prüfen!')},
            {'name': 'Hörseite workloom.de/radio/live', 'url': 'https://workloom.de/radio/live/', **st(stream_ok)},
            {'name': 'naturmacher.de/pages/radio (eingebettet)', 'url': 'https://www.naturmacher.de/pages/radio', **st(stream_ok)},
            {'name': 'Amazon Alexa („Alexa, öffne Naturmacher Radio“)', 'url': '', **st(stream_ok, 'Aktiv', 'prüfen!')},
        ]),
        ('🎥 Video-Simulcast', [
            {'name': 'YouTube Live', 'url': yt, **st(push['youtube'], 'Sendet', 'kein Push!')},
            {'name': 'Twitch (twitch.tv/naturmacher)', 'url': 'https://www.twitch.tv/naturmacher', **st(push['twitch'], 'Sendet', 'kein Push!')},
            {'name': 'Kick (kick.com/naturmacher)', 'url': 'https://kick.com/naturmacher', **st(push['kick'], 'Sendet', 'kein Push!')},
        ]),
        ('📱 Apps', [
            {'name': 'Android-App · Google Play', 'url': '', 'state': 'pend', 'label': 'Identitätsprüfung läuft'},
            {'name': 'Android-App · Amazon Appstore (Fire-Tablets)', 'url': '', 'state': 'ok', 'label': 'Live seit 12.06.'},
            {'name': 'Web-App (PWA) auf der Hörseite', 'url': 'https://workloom.de/radio/live/', 'state': 'ok', 'label': 'Aktiv'},
            {'name': 'Huawei AppGallery', 'url': '', 'state': 'pend', 'label': 'Konto in Prüfung'},
            {'name': 'Samsung Galaxy Store', 'url': '', 'state': 'idle', 'label': 'übersprungen (Play deckt ab)'},
        ]),
        ('📚 Radio-Verzeichnisse', [
            {'name': 'radio-browser.info', 'url': 'https://www.radio-browser.info', 'state': 'ok', 'label': 'Eingetragen'},
            {'name': 'myTuner Radio (200+ Länder, Auto/TV/Wearables)', 'url': 'https://mytuner-radio.com/radio/naturmacher-radio-520147/', 'state': 'ok', 'label': 'Live seit 13.06.'},
            {'name': 'airable (WLAN-Radios/HiFi)', 'url': '', 'state': 'ok', 'label': 'zugesagt, ab 14.06.'},
            {'name': 'TuneIn · radio.de · Radio Garden · OnlineRadioBox', 'url': '', 'state': 'pend', 'label': 'beantragt'},
            {'name': 'phonostar', 'url': 'https://www.phonostar.de/radio/naturmacherradio', 'state': 'ok', 'label': 'Live ab 16.06.'},
            {'name': 'surfmusik · Streema · vTuner · internet-radio.com', 'url': '', 'state': 'idle', 'label': 'offen'},
        ]),
    ]
    return JsonResponse({'groups': [{'title': t, 'items': i} for t, i in groups]})


def app_manifest(request):
    """PWA-Manifest: macht die Hörseite als App installierbar (iPhone/Desktop)."""
    resp = JsonResponse({
        "name": "Naturmacher Radio",
        "short_name": "Naturmacher",
        "description": "Familienradio: entspannte Musik, Wissen & Geschichten – rund um die Uhr.",
        "start_url": "/radio/live/",
        "scope": "/radio/",
        "display": "standalone",
        "background_color": "#06140f",
        "theme_color": "#08251b",
        "lang": "de",
        "icons": [
            {"src": "/media/radio/pwa_icon_192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/media/radio/pwa_icon_512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })
    resp['Cache-Control'] = 'max-age=3600'
    return resp


def radio_sw(request):
    """Minimaler Service Worker (Installierbarkeit; Stream wird NIE gecacht)."""
    js = """
self.addEventListener('install', function(e){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(clients.claim()); });
self.addEventListener('fetch', function(e){
  // Live-Stream und API niemals cachen — alles direkt aus dem Netz
  e.respondWith(fetch(e.request));
});
"""
    resp = HttpResponse(js, content_type='application/javascript')
    resp['Cache-Control'] = 'max-age=3600'
    return resp


def app_privacy(request):
    """Datenschutzerklärung der Naturmacher-Radio-App (für Google Play)."""
    html = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Datenschutzerklärung – Naturmacher Radio App</title>
<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:720px;margin:40px auto;
padding:0 20px;line-height:1.6;color:#222}h1{font-size:26px}h2{font-size:19px;margin-top:28px}</style>
</head><body>
<h1>Datenschutzerklärung – Naturmacher Radio App</h1>
<p>Stand: Juni 2026</p>
<h2>1. Verantwortlicher</h2>
<p>Naturmacher (naturmacher.de), Bensheim, Deutschland<br>Kontakt: kontakt@naturmacher.de</p>
<h2>2. Welche Daten verarbeitet die App?</h2>
<p>Die Naturmacher-Radio-App erhebt, speichert und teilt <strong>keine personenbezogenen
Daten</strong>. Es gibt keine Registrierung, kein Konto, keine Analyse- oder Werbe-SDKs
und keine Weitergabe von Daten an Dritte.</p>
<h2>3. Technisch notwendige Verbindungen</h2>
<p>Zum Abspielen des Radios verbindet sich die App mit unseren Servern
(workloom.de). Dabei wird – wie bei jedem Internetzugriff technisch unvermeidlich –
Ihre IP-Adresse übertragen. Sie wird ausschließlich zur Auslieferung des
Audio-Streams und der Programmdaten verwendet und nicht zu Profilen verknüpft.
Server-Protokolle werden nach kurzer Zeit automatisch gelöscht.</p>
<h2>4. Berechtigungen</h2>
<p>Die App nutzt die Berechtigungen Internet (Stream), Vordergrund-Dienst
(Wiedergabe bei gesperrtem Bildschirm) und Benachrichtigungen
(Wiedergabe-Steuerung auf dem Sperrbildschirm). Keine dieser Berechtigungen
wird für andere Zwecke verwendet.</p>
<h2>5. Externe Links</h2>
<p>Die App enthält Links zu naturmacher.de und YouTube. Beim Öffnen gelten die
Datenschutzbestimmungen der jeweiligen Anbieter.</p>
<h2>6. Kontakt</h2>
<p>Fragen zum Datenschutz: kontakt@naturmacher.de</p>
</body></html>"""
    return HttpResponse(html)


def app_about(request):
    """Über-das-Radio-Text für die App (HTML): Erklärung + Rubriken mit aktuellen Sendezeiten."""
    from .models import ScheduledItem as _SI
    times = {}
    for _p in _SI.objects.filter(is_active=True).order_by('start_time'):
        if _p.rubrik_key:
            times.setdefault(_p.rubrik_key, []).append(_p.start_time.strftime('%H:%M'))
    parts = [
        '<b>📻 Naturmacher Radio</b><br>',
        'Unser Familienradio läuft rund um die Uhr – mit entspannter Musik und liebevoll '
        'gestalteten Beiträgen für Eltern und Kinder.<br><br>',
        '<b>🕐 Wann läuft was?</b><br>'
        'Zu jeder vollen und halben Stunde ein Beitrag – tagsüber Wissen &amp; Praktisches, '
        'nachts Ruhiges zum Träumen, dazwischen immer Musik.<br>',
    ]
    for group, items in RUBRIK_ABOUT:
        parts.append(f'<br><b>{group}</b><br>')
        for key, label, desc in items:
            t = times.get(key)
            tstr = (' <i>(täglich ' + ', '.join(t) + ' Uhr)</i>') if t else ''
            parts.append(f'<b>{label}</b>{tstr}<br>{desc}<br><br>')
    parts.append('<b>🎧 Außerdem:</b> Hör uns auf Amazon Alexa („Alexa, öffne Naturmacher Radio“), '
                 'im YouTube-Live-Stream oder auf naturmacher.de.')
    resp = JsonResponse({'html': ''.join(parts)})
    resp['Cache-Control'] = 'no-store, max-age=0'
    resp['Access-Control-Allow-Origin'] = '*'
    return resp


@_superuser_only
@require_POST
def promo_save(request):
    """Speichert die Naturmacher-Ankündigungen (App + Hörseite), eine pro Zeile."""
    data = json.loads(request.body or '{}')
    cfg = StationConfig.get()
    cfg.app_promo_lines = (data.get('lines') or '').strip()
    if 'code' in data:
        cfg.app_promo_code = (data.get('code') or '').strip()[:60]
    if 'benefit' in data:
        cfg.app_promo_benefit = (data.get('benefit') or '').strip()[:60]
    if 'url' in data:
        u = (data.get('url') or '').strip()
        if u and not u.startswith('http'):
            u = 'https://' + u
        cfg.app_promo_url = u
    cfg.save(update_fields=['app_promo_lines', 'app_promo_code', 'app_promo_benefit', 'app_promo_url'])
    n = len([l for l in cfg.app_promo_lines.splitlines()
             if l.strip() and not l.strip().startswith('#')])
    return JsonResponse({'ok': True, 'count': n})


@csrf_exempt
def alexa_skill(request):
    """Alexa-Custom-Skill-Endpunkt: spielt den Live-Stream. URL: /radio/alexa/"""
    if request.method != 'POST':
        return HttpResponse('Naturmacher Radio Alexa-Endpunkt', content_type='text/plain')
    from . import alexa
    return alexa.handle(request)


@_superuser_only
@require_POST
def library_delete(request):
    """Löscht einen Bibliotheks-Beitrag (Track/SpokenContent) samt Audiodatei + Sendeplan-Bezügen."""
    data = json.loads(request.body or '{}')
    ctype = data.get('type')
    pk = data.get('pk')
    obj = (Track.objects.filter(pk=pk).first() if ctype == 'track'
           else SpokenContent.objects.filter(pk=pk).first())
    if not obj:
        return JsonResponse({'error': 'nicht gefunden'}, status=404)
    if ctype == 'track':
        PlaylistEntry.objects.filter(track=obj).delete()
    else:
        PlaylistEntry.objects.filter(spoken=obj).delete()
    try:
        if obj.audio_file:
            obj.audio_file.delete(save=False)
    except Exception:
        pass
    obj.delete()
    return JsonResponse({'ok': True})


@_superuser_only
@require_POST
def auto_program_now(request):
    """Stößt die GLM-Programm-Zusammenstellung sofort an (für die nächsten ~2 Std)."""
    from .tasks import auto_program
    minutes = int(request.POST.get('minutes') or 120)
    res = auto_program.delay(target_minutes=minutes)
    return JsonResponse({'ok': True, 'task_id': res.id})


# Emoji je Rubrik-Key (nur zur Verschönerung). Die Liste der Rubriken selbst
# kommt IMMER aus der DB-Tabelle Rubrik (Einstellungen) — damit Planer, Wizard,
# Studio und Einstellungen exakt dieselben Rubriken zeigen.
RUBRIK_ICONS = {
    'music': '🎵', 'song': '🎤', 'news': '📰', 'tip': '💡', 'wissen': '🧠',
    'story': '🌙', 'dialog': '👥', 'kreativ': '✨', 'jingle': '🔔',
    'effekt': '🔊', 'ad': '📣', 'klanggeschichte': '🎧',
}


def planner_kinds():
    """(key, label)-Liste der aktiven Rubriken aus der DB — einzige Quelle der Wahrheit."""
    from .models import Rubrik
    out = []
    for r in Rubrik.objects.filter(is_active=True).order_by('order'):
        icon = RUBRIK_ICONS.get(r.key, '•')
        out.append((r.key, f'{icon} {r.label}'))
    return out


@_superuser_only
def wizard(request):
    """Content-Wizard: Rubriken wählen → GLM erzeugt Texte → bearbeiten → vertonen → Bibliothek."""
    from .models import Rubrik
    rubriken = [{'key': r.key, 'label': r.label, 'rtype': r.rtype, 'voice': r.voice}
                for r in Rubrik.objects.filter(is_active=True).order_by('order')]
    gemini_voices = [(v, l) for (v, l) in STUDIO_VOICES if v.startswith('gemini-')]
    import json as _json
    from . import elevenlabs as _el
    try:
        eleven_voices = [{'value': f'eleven-{vid}', 'label': lbl} for (vid, lbl) in _el.list_voices()]
    except Exception:
        eleven_voices = []
    return render(request, 'radio/wizard.html', {
        'rubriken_json': _json.dumps(rubriken),
        'voices': gemini_voices,
        'voices_json': _json.dumps([{'value': v, 'label': l} for (v, l) in gemini_voices]),
        'eleven_voices_json': _json.dumps(eleven_voices),
        'tts_settings_json': _json.dumps(_tts_settings_dict()),
        'bg_tracks_json': _json.dumps(_bg_track_choices()),
        'voice_by_kind': _json.dumps(VOICE_BY_KIND_FOR_TEMPLATE()),
        'sample_base': f'{settings.MEDIA_URL}radio/voicesamples/',
    })


def VOICE_BY_KIND_FOR_TEMPLATE():
    from .tasks import VOICE_BY_KIND
    return VOICE_BY_KIND


@_superuser_only
def planner(request):
    """DEAKTIVIERT (2026-06): Der alte Block-Tagesplan ist zugunsten der Timeline
    ausgeblendet. Die Seite leitet auf die Timeline um; Modell/Daten bleiben intakt."""
    return redirect('radio:timeline')
    from .models import ProgramSlot  # noqa: unreachable (Logik bewusst erhalten)
    import json as _json
    slots = list(ProgramSlot.objects.all().order_by('start_time', 'order'))
    data = [{
        'pk': s.pk, 'name': s.name,
        'start': s.start_time.strftime('%H:%M') if s.start_time else '08:00',
        'duration_min': s.duration_min,
        'kinds': [k for k in (s.kinds or '').split(',') if k],
        'music_per_talk': s.music_per_talk, 'ad_every_min': s.ad_every_min,
        'is_active': s.is_active,
    } for s in slots]
    return render(request, 'radio/planner.html', {
        'slots_json': _json.dumps(data), 'kinds': planner_kinds(),
    })


@_superuser_only
@require_POST
def slot_save(request):
    from datetime import datetime
    from .models import ProgramSlot
    pk = request.POST.get('pk')
    s = ProgramSlot.objects.filter(pk=pk).first() if pk else ProgramSlot()
    if s is None:
        s = ProgramSlot()
    s.name = (request.POST.get('name') or 'Slot').strip()[:120]
    try:
        s.start_time = datetime.strptime(request.POST.get('start_time') or '08:00', '%H:%M').time()
    except ValueError:
        s.start_time = datetime.strptime('08:00', '%H:%M').time()
    s.duration_min = max(5, int(request.POST.get('duration_min') or 120))
    valid = {k for k, _ in planner_kinds()}
    s.kinds = ','.join(k for k in request.POST.getlist('kinds') if k in valid) or 'music'
    s.music_per_talk = int(request.POST.get('music_per_talk') or 0)
    s.ad_every_min = int(request.POST.get('ad_every_min') or 0)
    s.is_active = (request.POST.get('is_active') == '1')
    s.slot_type = 'music'
    s.save()
    return JsonResponse({'ok': True, 'pk': s.pk})


@_superuser_only
@require_POST
def slot_delete(request):
    from .models import ProgramSlot
    ProgramSlot.objects.filter(pk=request.POST.get('pk')).delete()
    return JsonResponse({'ok': True})


@_superuser_only
@require_POST
def slot_fill(request):
    from .tasks import fill_slot
    res = fill_slot.delay(int(request.POST.get('pk')))
    return JsonResponse({'ok': True, 'task_id': res.id})


@_superuser_only
@require_POST
def plan_day_now(request):
    from .tasks import plan_day
    from .models import ProgramSlot
    active = ProgramSlot.objects.filter(is_active=True).count()
    if active == 0:
        return JsonResponse({'ok': False, 'error': 'Keine aktiven Slots vorhanden. '
                             'Lege zuerst links über „➕ Neuer Slot" mindestens einen Slot an '
                             '(Zeit, Länge, Inhalte) und speichere ihn.'}, status=400)
    res = plan_day.delay(replace=(request.POST.get('replace', '1') == '1'))
    return JsonResponse({'ok': True, 'task_id': res.id, 'slots': active})


@_superuser_only
def news_drafts(request):
    """Liefert die aktuellen, von GLM zusammengefassten News-Entwürfe (für das Studio)."""
    items = [{'pk': s.pk, 'title': s.title, 'topic': s.description, 'text': s.text}
             for s in SpokenContent.objects.filter(kind='news', status='draft').order_by('-created_at')]
    return JsonResponse({'drafts': items})


@_superuser_only
@require_POST
def fetch_news_now(request):
    """Stößt die Online-News-Recherche + GLM-Zusammenfassung sofort an."""
    from .tasks import fetch_news
    res = fetch_news.delay()
    return JsonResponse({'ok': True, 'task_id': res.id})


@_superuser_only
@require_POST
def library_add(request):
    """Hängt einen vorhandenen Bibliotheks-Beitrag hinten an den Sendeplan an."""
    data = json.loads(request.body or '{}')
    ctype = data.get('type')
    pk = data.get('pk')
    with transaction.atomic():
        entry = PlaylistEntry(status='queued', manual=True)
        if ctype == 'track':
            t = Track.objects.filter(pk=pk).first()
            entry.track = t
            entry.kind = 'song' if (t and t.source == 'acestep') else 'music'
        else:
            s = SpokenContent.objects.filter(pk=pk).first()
            entry.spoken = s
            entry.kind = s.kind if s else 'wissen'
        if not entry.content:
            return JsonResponse({'error': 'Inhalt nicht gefunden.'}, status=404)
        last = (PlaylistEntry.objects.order_by('-position')
                .values_list('position', flat=True).first()) or 0
        entry.position = last + 1
        entry.save()
    scheduler.renumber()
    return JsonResponse({'ok': True, 'title': entry.title})


# ============================================================================
#  Liquidsoap-Schnittstellen (token-geschützt)
# ============================================================================
def _esc(s):
    return (s or '').replace('"', "'")


def _check_token(request):
    token = getattr(settings, 'RADIO_STREAM_TOKEN', None) or os.environ.get('RADIO_STREAM_TOKEN', '')
    return token and request.GET.get('token') == token


@csrf_exempt
def _rubrik_of_entry(entry):
    """Rubrik-Key eines PlaylistEntry (Spoken-Kind bzw. Track-Kategorie)."""
    if entry.spoken_id and entry.spoken:
        return entry.spoken.kind
    if entry.track_id and entry.track:
        from .tasks import _track_kind
        return _track_kind(entry.track)
    return None


def _intro_track_for(entry):
    """Liefert das Rubrik-Intro (Track) für einen PlaylistEntry – oder None."""
    from .models import Rubrik
    key = _rubrik_of_entry(entry)
    if not key:
        return None
    r = Rubrik.objects.filter(key=key, is_active=True).select_related('intro').first()
    return r.intro if (r and r.intro_id) else None


def _outro_track_for(entry):
    """Liefert das Rubrik-Outro (Track) für einen PlaylistEntry – oder None."""
    from .models import Rubrik
    key = _rubrik_of_entry(entry)
    if not key:
        return None
    r = Rubrik.objects.filter(key=key, is_active=True).select_related('outro').first()
    return r.outro if (r and r.outro_id) else None


@_superuser_only
def notes_page(request):
    """Notiz-Pinnwand: Kacheln mit Titel, Text, Autor, Datum."""
    return render(request, 'radio/notes.html', {})


@_superuser_only
def notes_list(request):
    """Alle Notizen als JSON (neueste zuerst)."""
    from .models import RadioNote
    out = []
    for n in RadioNote.objects.all():
        out.append({'pk': n.pk, 'title': n.title, 'body': n.body, 'author': n.author,
                    'color': n.color or '#2b7a4b',
                    'created': n.created_at.astimezone(BERLIN).strftime('%d.%m.%Y %H:%M'),
                    'updated': n.updated_at.astimezone(BERLIN).strftime('%d.%m.%Y %H:%M')})
    return JsonResponse({'notes': out})


@_superuser_only
@require_POST
def note_save(request):
    """Legt eine Notiz an oder aktualisiert sie."""
    from .models import RadioNote
    data = json.loads(request.body or '{}')
    pk = data.get('pk')
    n = RadioNote.objects.filter(pk=pk).first() if pk else RadioNote()
    if pk and not n:
        return JsonResponse({'error': 'Notiz nicht gefunden.'}, status=404)
    title = (data.get('title') or '').strip()
    if not title:
        return JsonResponse({'error': 'Bitte einen Titel eingeben.'}, status=400)
    n.title = title[:160]
    n.body = (data.get('body') or '').strip()
    n.author = (data.get('author') or '').strip()[:80]
    c = (data.get('color') or '').strip()
    n.color = c[:16] if c else '#2b7a4b'
    n.save()
    return JsonResponse({'ok': True, 'pk': n.pk})


@_superuser_only
@require_POST
def note_delete(request):
    from .models import RadioNote
    data = json.loads(request.body or '{}')
    RadioNote.objects.filter(pk=data.get('pk')).delete()
    return JsonResponse({'ok': True})


def next_track(request):
    """Nächster Sendeplan-Eintrag als annotierte URI; markiert ihn als gespielt."""
    if not _check_token(request):
        return HttpResponseForbidden('forbidden')

    # Pause: on_air aus -> Stille, Warteschlange rückt NICHT vor (resume an Ort & Stelle)
    if not StationConfig.get().on_air:
        return HttpResponse('', content_type='text/plain')

    with transaction.atomic():
        # Rubrik-Outro: hängt am zuletzt gespielten Beitrag noch ein Outro,
        # wird ZUERST dieses ausgeliefert (läuft also direkt nach dem Beitrag).
        prev = (PlaylistEntry.objects.select_for_update()
                .filter(outro_pending=True).order_by('-id').first())
        if prev is not None:
            PlaylistEntry.objects.filter(outro_pending=True).update(outro_pending=False)
            outro = _outro_track_for(prev)
            if outro is not None:
                try:
                    opath = outro.audio_file.path if outro.audio_file else None
                except (ValueError, NotImplementedError):
                    opath = None
                if opath and os.path.exists(opath):
                    Track.objects.filter(pk=outro.pk).update(play_count=models.F('play_count') + 1)
                    ouri = f'annotate:title="{_esc(outro.title)}",kind="jingle":{opath}'
                    return HttpResponse(ouri + '\n', content_type='text/plain')

        entry = PlaylistEntry.objects.select_for_update().filter(status='queued').order_by('position').first()
        if not entry:
            # Leere Queue: wenn ein Tagesplan (Pins/Slots) existiert, diesen
            # materialisieren (ohne Inline-Generierung = schnell), sonst Musik-Teppich.
            made = 0
            try:
                made = scheduler.ensure_queue_filled(min_hours=6, max_days=2)
            except Exception:
                made = 0
            if not made:
                scheduler.build_schedule()
            entry = PlaylistEntry.objects.select_for_update().filter(status='queued').order_by('position').first()
        if not entry:
            return HttpResponse('', content_type='text/plain')

        content = entry.content
        f = getattr(content, 'audio_file', None) if content else None
        try:
            path = f.path if f else None
        except (ValueError, NotImplementedError):
            path = None

        # Rubrik-Intro: hat die Rubrik dieses Beitrags ein Intro und wurde es für
        # diesen Eintrag noch nicht gespielt, wird ZUERST das Intro ausgeliefert
        # (Eintrag bleibt in der Queue, kommt beim nächsten Abruf direkt danach).
        if path and not entry.intro_done:
            intro = _intro_track_for(entry)
            PlaylistEntry.objects.filter(pk=entry.pk).update(intro_done=True)
            if intro is not None:
                try:
                    ipath = intro.audio_file.path if intro.audio_file else None
                except (ValueError, NotImplementedError):
                    ipath = None
                if ipath and os.path.exists(ipath):
                    Track.objects.filter(pk=intro.pk).update(play_count=models.F('play_count') + 1)
                    iuri = f'annotate:title="{_esc(intro.title)}",kind="jingle":{ipath}'
                    return HttpResponse(iuri + '\n', content_type='text/plain')

        entry.status = 'played'
        # Outro vormerken: Hat die Rubrik dieses Beitrags ein Outro, wird es beim
        # NÄCHSTEN Abruf (= direkt nach diesem Beitrag) ausgespielt.
        entry.outro_pending = _outro_track_for(entry) is not None
        entry.save(update_fields=['status', 'outro_pending'])
        if entry.track_id:
            Track.objects.filter(pk=entry.track_id).update(play_count=models.F('play_count') + 1)

    if not path or not os.path.exists(path):
        return next_track(request)

    uri = f'annotate:title="{_esc(entry.title)}",entry_id="{entry.pk}",kind="{entry.kind}":{path}'
    return HttpResponse(uri + '\n', content_type='text/plain')


@csrf_exempt
def now_playing(request):
    """
    Liquidsoap meldet hier den TATSÄCHLICH startenden Beitrag (on_metadata),
    damit das Dashboard 'läuft gerade' korrekt zeigt (trotz Prefetch).
    """
    if not _check_token(request):
        return HttpResponseForbidden('forbidden')
    try:
        eid = int(request.GET.get('entry_id', '0'))
    except ValueError:
        eid = 0
    if eid:
        PlaylistEntry.objects.filter(status='playing').update(status='played')
        PlaylistEntry.objects.filter(pk=eid).update(status='playing', started_at=timezone.now())
        # „Zuletzt abgespielt"-Zeitstempel am zugrunde liegenden Track/Beitrag setzen
        try:
            e = PlaylistEntry.objects.filter(pk=eid).values('track_id', 'spoken_id').first() or {}
            now = timezone.now()
            if e.get('track_id'):
                Track.objects.filter(pk=e['track_id']).update(last_played_at=now)
            if e.get('spoken_id'):
                SpokenContent.objects.filter(pk=e['spoken_id']).update(last_played_at=now)
        except Exception:
            pass
        try:
            _apply_entry_visual(eid)
        except Exception:
            pass
    return HttpResponse('ok', content_type='text/plain')


def _kill_stream_ffmpeg():
    """Beendet den laufenden Stream-ffmpeg gezielt per PID (stream.sh startet ihn neu)."""
    import signal
    pidfile = os.path.join(settings.MEDIA_ROOT, 'radio', 'stream_ffmpeg.pid')
    try:
        with open(pidfile) as pf:
            pid = int(pf.read().strip())
        with open(f'/proc/{pid}/comm') as c:
            if c.read().strip() != 'ffmpeg':
                return
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _apply_entry_visual(eid):
    """Schaltet das Stream-Visual auf das Beitrags-Video (falls vorhanden) bzw. zurück."""
    import shutil
    e = PlaylistEntry.objects.filter(pk=eid).first()
    if not e:
        return
    media_dir = os.path.join(settings.MEDIA_ROOT, 'radio')
    cfg = StationConfig.get()
    try:
        vid = e.video_file.path if (e.video_file and e.video_file.name) else None
    except (ValueError, NotImplementedError):
        vid = None

    if vid and os.path.exists(vid):
        shutil.copy(vid, os.path.join(media_dir, 'background.mp4'))
        with open(os.path.join(media_dir, 'visual_mode'), 'w') as f:
            f.write('video_loop')
        cfg.visual_mode, cfg.visual_auto = 'video_loop', True
        cfg.save(update_fields=['visual_mode', 'visual_auto'])
        _kill_stream_ffmpeg()
    elif cfg.visual_auto:
        # Vorheriger Beitrag hatte ein Video -> zurück auf Standbild
        with open(os.path.join(media_dir, 'visual_mode'), 'w') as f:
            f.write('image')
        cfg.visual_mode, cfg.visual_auto = 'image', False
        cfg.save(update_fields=['visual_mode', 'visual_auto'])
        _kill_stream_ffmpeg()


# ---------------------------------------------------------------------------
# Schwebender KI-Assistent (GLM 5.1) mit Radio-Wissen + optionaler Web-Recherche
# ---------------------------------------------------------------------------
def _assistant_system():
    """System-Prompt: erklärt das Radiosystem + aktueller Zustand (für GLM 5.1)."""
    from .models import StationConfig, Rubrik, Track, SpokenContent
    c = StationConfig.get()
    rubs = Rubrik.objects.filter(is_active=True)
    catmap = dict(Rubrik.CATEGORIES)
    rub_lines = []
    for r in rubs:
        rub_lines.append(f'  • {r.label} – {r.get_rtype_display()}, '
                         f'Kategorie: {catmap.get(r.category) or "automatisch"}'
                         + (f', Stimme: {r.voice}' if r.voice else '')
                         + (f', Ziel-Länge: {r.target_sec}s' if r.target_sec else ''))
    n_tracks = Track.objects.filter(is_active=True).exclude(audio_file='').count()
    n_spoken = SpokenContent.objects.filter(status='generated').exclude(audio_file='').count()
    rub_txt = '\n'.join(rub_lines) or '  (keine aktiven Rubriken)'
    return (
        'Du bist der freundliche, kompetente Assistent für das „Naturmacher KI-Radio" '
        '– einen vollautomatischen 24/7-Webradiosender (Marke Naturmacher: Natur, Garten, '
        'Basteln, Familie). Du hilfst dem Betreiber (Taras) beim Bedienen und Verstehen des '
        'Systems, beantwortest Fragen knapp und konkret auf Deutsch und gibst praktische '
        'Schritt-für-Schritt-Hinweise. Sei ehrlich, wenn du etwas nicht sicher weißt.\n\n'
        'SO FUNKTIONIERT DAS RADIO:\n'
        '• Sendebetrieb: Liquidsoap spielt eine Warteschlange (Sendeplan) ab, Icecast streamt, '
        'ffmpeg pusht zusätzlich zu YouTube. Ein Audio-Visualizer erzeugt das Videobild.\n'
        '• Standardprogramm: Läuft automatisch, wenn nichts Festes geplant ist. Mischung über '
        'Einstellungen steuerbar: „alle N Musiktitel ein Wortbeitrag", „Jingle alle K Titel", '
        '„Werbung alle M Minuten". Welche Rubrik als Wortbeitrag/Jingle/Werbung/Musik zählt, '
        'wird ebenfalls dort (Standardprogramm) pro Rubrik festgelegt.\n'
        '• Rubriken (Einstellungen → Rubriken): Vorlagen, aus denen GLM 5.1 Inhalte erzeugt. '
        'Pro Rubrik: System-/Aufgaben-Prompt, Typ (Sprache/Musik), Stimme, KI-Modell '
        '(TTS-Modell bei Sprache bzw. Musik-Engine bei Musik), gewünschte Länge in Sekunden.\n'
        '• Studio (Beitrag erstellen): Einzelbeiträge manuell erzeugen – Sprache (Stimme wählbar), '
        'Musik (instrumental) oder Musik mit Gesang (mit Musikrichtung-Auswahl), Effekt/Jingle. '
        'Tags und „für Pool freigeben" wählbar.\n'
        '• Timeline (Programm planen): Beiträge zu festen Datum/Uhrzeiten „pinnen". Modi: selbst '
        'erzeugen, bestimmter Titel, Rubrik zufällig, Rubrik automatisch erzeugen. Genauigkeit '
        '„Anker" (schonend als Nächstes) oder „Exakt" (unterbricht). Wiederholung einmalig/'
        'täglich/wochentags (nicht bei „selbst erzeugen"). Pins feuern automatisch zur Zeit, '
        'unabhängig vom Grundprogramm.\n'
        '• Tags/Saison: Inhalte taggen; Saison-Tags (z. B. „weihnachten", MM-TT-Fenster) laufen '
        'nur in ihrer Zeit.\n'
        '• Visualizer: mehrere Stile (u. a. bunte Regenbogen-Balken „Aurora"); umschaltbar unter '
        '/radio/visualizer/.\n'
        '• Öffentliche Hörseite + Alexa-Skill + YouTube-Ausweich-Link bei Überlastung.\n'
        '• KI: Texte schreibt GLM 5.1; Sprache via Gemini-TTS/ElevenLabs/XTTS/Piper; Musik via '
        'Google Lyria/MiniMax/fal.ai/ElevenLabs Music.\n\n'
        f'AKTUELLER ZUSTAND:\n'
        f'• Sendername: {c.name}\n'
        f'• On-Air: {"ja" if c.on_air else "nein"}\n'
        f'• Standardprogramm: alle {c.std_music_per_talk} Titel ein Wortbeitrag, '
        f'Jingle alle {c.std_jingle_every} Titel, Werbung alle {c.std_ad_every_min} Min\n'
        f'• Bibliothek: {n_tracks} aktive Musik-/Effekt-Titel, {n_spoken} fertige Wortbeiträge\n'
        f'• Aktive Rubriken:\n{rub_txt}\n'
    )


def assistant_answer(question, history):
    """Kernlogik: erzeugt die Assistenten-Antwort (optional mit Web-Recherche).
    Gibt dict {answer, searched} zurück. Wird vom Celery-Task aufgerufen, damit
    die Antwort einen Seiten-Reload übersteht."""
    from . import glm, news
    convo = ''
    for m in (history or [])[-8:]:
        who = 'Nutzer' if m.get('role') == 'user' else 'Assistent'
        convo += f'{who}: {(m.get("content") or "")[:1500]}\n'
    convo += f'Nutzer: {question}\nAssistent:'

    system = _assistant_system()
    directive = (
        system + '\n\nWICHTIG: Wenn du für eine fundierte Antwort AKTUELLE oder externe '
        'Informationen aus dem Internet brauchst (z. B. Fakten, Zahlen, Neuigkeiten außerhalb '
        'des Radiosystems), antworte AUSSCHLIESSLICH mit einer einzigen Zeile in der Form:\n'
        'SEARCH: <kurzer Suchbegriff>\n'
        'Brauchst du keine Recherche, antworte direkt, hilfreich und auf Deutsch.'
    )
    searched = None
    first = (glm.glm_chat(convo, system=directive, max_tokens=1200) or '').strip()

    if first.upper().startswith('SEARCH:'):
        q = first.split(':', 1)[1].strip()[:200]
        searched = q
        res = news.web_research(q)
        followup = (
            convo + f'\n[Ergebnisse einer Web-Recherche zu "{q}"]:\n{res or "(nichts gefunden)"}\n\n'
            'Beantworte die letzte Nutzerfrage jetzt knapp, hilfreich und auf Deutsch und '
            'nutze die Rechercheergebnisse. Erwähne kurz, dass die Info aus einer Web-Recherche stammt.'
        )
        try:
            answer = (glm.glm_chat(followup, system=system, max_tokens=1200) or '').strip()
        except Exception:
            answer = res or 'Ich konnte dazu nichts Belastbares finden.'
    else:
        answer = first

    return {'answer': answer or '…', 'searched': searched}


@_superuser_only
@require_POST
def assistant_chat(request):
    """Startet die Antwort-Erzeugung im Hintergrund (Celery) und liefert die Task-ID.
    So bleibt die Antwort auch bei einem Seiten-Reload abrufbar."""
    from .tasks import assistant_answer_task
    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Ungültige Anfrage.'}, status=400)
    question = (data.get('message') or '').strip()
    if not question:
        return JsonResponse({'error': 'Leere Nachricht.'}, status=400)
    history = data.get('history') or []
    res = assistant_answer_task.delay(question, history)
    return JsonResponse({'task_id': res.id})


@_superuser_only
def assistant_status(request, task_id):
    """Pollt den Status einer Assistenten-Antwort (für Reload-Wiederaufnahme)."""
    from celery.result import AsyncResult
    r = AsyncResult(task_id)
    if r.successful():
        return JsonResponse({'state': 'done', 'result': r.result})
    if r.failed():
        return JsonResponse({'state': 'failed', 'error': str(r.result)[:300]})
    return JsonResponse({'state': r.state.lower()})


@_superuser_only
def library_manage(request):
    """Vollständige Bibliotheks-Verwaltung (eigene Seite): filtern, bearbeiten,
    löschen, abspielen, Rubrik ändern. Lädt die Daten per AJAX von library_list."""
    import json as _json
    from .models import Rubrik as _Rb
    # Vollständige Filter-Liste: Musik-Arten + ALLE aktiven Sprach-Rubriken
    # (auch ohne vorhandene Inhalte) + evtl. Alt-Kinds
    filter_cats = [('music', '🎵 Musik (instrumental)'), ('song', '🎤 Musik mit Gesang'),
                   ('effekt', '🔔 Sound-Effekte / Jingles')]
    seen = {k for k, _ in filter_cats}
    for r in _Rb.objects.filter(is_active=True, rtype='speech').order_by('order', 'label'):
        if r.key not in seen:
            filter_cats.append((r.key, r.label)); seen.add(r.key)
    for k, l in SpokenContent.KIND:
        if k not in seen:
            filter_cats.append((k, l)); seen.add(k)
    return render(request, 'radio/library_manage.html', {
        'spoken_kinds_json': _json.dumps([[k, l] for k, l in SpokenContent.KIND]),
        'track_cats_json': _json.dumps([[k, l] for k, l in Track.CATEGORY_CHOICES if k]),
        'filter_cats': filter_cats,
    })


@_superuser_only
@require_POST
def library_edit(request):
    """Bearbeitet Titel, Genre/Stimmung und Tags eines Bibliotheks-Beitrags."""
    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Ungültige Anfrage.'}, status=400)
    ctype = data.get('type')
    title = (data.get('title') or '').strip()[:200]
    genre = (data.get('genre') or '').strip()[:300]
    tags = (data.get('tags') or '').strip()[:200]
    kind = (data.get('kind') or '').strip()
    if ctype == 'track':
        obj = Track.objects.filter(pk=data.get('pk')).first()
        if not obj:
            return JsonResponse({'error': 'nicht gefunden'}, status=404)
        if title:
            obj.title = title
        obj.mood = genre[:120]
        obj.tags = tags
        fields = ['title', 'mood', 'tags']
        if kind in ('music', 'song', 'effekt', 'ad'):
            obj.category = kind
            fields.append('category')
        obj.save(update_fields=fields)
    else:
        obj = SpokenContent.objects.filter(pk=data.get('pk')).first()
        if not obj:
            return JsonResponse({'error': 'nicht gefunden'}, status=404)
        if title:
            obj.title = title
        obj.description = genre
        obj.tags = tags
        fields = ['title', 'description', 'tags']
        if kind in dict(SpokenContent.KIND):
            obj.kind = kind
            fields.append('kind')
        obj.save(update_fields=fields)
    return JsonResponse({'ok': True})


@_superuser_only
def weekprogram_data(request):
    """Alle wiederkehrenden Programm-Einträge (Wochenprogramm): ScheduledItems OHNE
    festes Datum (on_date null) – also täglich oder an bestimmten Wochentagen.
    Wird jede Woche automatisch wiederholt (über enforce_pins)."""
    from .models import ScheduledItem
    items = (ScheduledItem.objects.filter(on_date__isnull=True)
             .select_related('track', 'spoken').order_by('start_time', 'order'))
    return JsonResponse({'entries': [_pin_dict(p) for p in items]})


def listener_history(request):
    """Hörer-Verlauf der letzten N Stunden als JSON (für das Dashboard-Diagramm)."""
    from .models import ListenerStat
    from django.utils import timezone as _tz
    from datetime import timedelta as _td
    try:
        hours = max(1, min(720, int(request.GET.get('hours', 24))))
    except (TypeError, ValueError):
        hours = 24
    since = _tz.now() - _td(hours=hours)
    rows = ListenerStat.objects.filter(ts__gte=since).order_by('ts')
    pts = [{'t': r.ts.isoformat(), 'l': r.listeners} for r in rows]
    return JsonResponse({'points': pts, 'hours': hours})
