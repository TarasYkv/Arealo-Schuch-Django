"""
Audio-Visualizer für den 24/7-Stream: erzeugt aus dem Live-Ton ein bewegtes,
reaktives Video (ffmpeg-Filter). Dieselben Filter werden für die Vorschau (aus
einer Bibliotheks-Datei) und für den YouTube-Stream (aus dem Icecast-Ton) genutzt.

`build_filter(cfg)` liefert den `-filter_complex`-String (Audio-Input = [0:a],
Ergebnis-Label = [v]); optional mit Logo- und „Läuft gerade"-Text-Overlay.
"""

# Verfügbare Visualizer-Typen: key -> (Label, Baufunktion)
# Jede Baufunktion bekommt (cfg, W, H, F) und liefert den Kern-Filter,
# der [0:a] in Video umwandelt (OHNE abschließendes [v] – das hängt build_filter an).

SPECTRUM_COLORS = ['channel', 'intensity', 'rainbow', 'moreland', 'nebulae', 'fire',
                   'fiery', 'fruit', 'cool', 'magma', 'green', 'viridis', 'plasma',
                   'cividis', 'terrain']

VIZ_TYPES = [
    ('eco_logo', '🌿 Naturmacher-Logo + Balken – sparsam (wenig CPU, empfohlen)'),
    ('aurora_flow', '✨ Aurora – Regenbogen-Balken auf animiertem Farbverlauf (modern)'),
    ('cqt_aurora', '🌈 Regenbogen-Balken – gespiegelt, leuchtend (Musikvideo-Look)'),
    ('cqt_rainbow', '🌈 Regenbogen-Balken – satt & leuchtend'),
    ('cqt_prism', '🔮 Prisma – Balken mit fließendem Farbwechsel'),
    ('showcqt', 'Musik-Balken (CQT) – farbig, musikalisch'),
    ('cqt_glow', 'Musik-Balken – mit Glow/Leuchten'),
    ('cqt_neon', 'Musik-Balken – Neon (satt, leuchtend)'),
    ('cqt_warm', 'Musik-Balken – warmes Farbschema'),
    ('cqt_mirror', 'Musik-Balken – gespiegelt (oben+unten)'),
    ('showcwt', 'Wavelet-Spektrum (CWT) – fließend, modern'),
    ('showcwt_log', 'Wavelet – logarithmisch'),
    ('showcwt_mel', 'Wavelet – Mel-Skala'),
    ('showcwt_bark', 'Wavelet – Bark-Skala'),
    ('spectrum_scroll', 'Spektrogramm – scrollend (Palette wählbar)'),
    ('spectrum_bars', 'Spektrum-Balken – stehend (Palette wählbar)'),
    ('spectrum_mirror', 'Spektrogramm – gespiegelt (Palette wählbar)'),
    ('showfreqs_bar', 'Frequenz-Balken'),
    ('freqs_dot', 'Frequenz-Punkte'),
    ('showfreqs_line', 'Frequenz-Linie'),
    ('freqs_centered', 'Frequenz-Balken – zentriert (log)'),
    ('showwaves_line', 'Wellenform – Linie'),
    ('showwaves_point', 'Wellenform – Punkte'),
    ('showwaves_cline', 'Wellenform – gefüllte Linie'),
    ('waves_p2p', 'Wellenform – Spitze-zu-Spitze'),
    ('waves_mirror', 'Wellenform – gespiegelt (symmetrisch)'),
    ('vectorscope_lissajous', 'Vektorskop – Lissajous'),
    ('vectorscope_lissajous_xy', 'Vektorskop – Lissajous XY'),
    ('vectorscope_polar', 'Vektorskop – Polar'),
    ('vectorscope_dot', 'Vektorskop – Punkte'),
    ('ahistogram', 'Audio-Histogramm – getrennt'),
    ('ahistogram_combined', 'Audio-Histogramm – kombiniert'),
    ('showvolume', 'Lautstärke-Anzeige'),
    ('showspatial', 'Stereo-Räumlich'),
]
VIZ_TYPE_KEYS = {k for k, _ in VIZ_TYPES}


def _g(cfg, key, default):
    v = cfg.get(key)
    return v if v not in (None, '') else default


def build_core(cfg, W, H, F):
    t = cfg.get('viz_type') or 'showcqt'
    color = (_g(cfg, 'palette', 'rainbow'))
    base = (_g(cfg, 'base_color', '0x33d1ff')).replace('#', '0x')
    bg = (_g(cfg, 'bg_color', '0x0c1626')).replace('#', '0x')
    bars = int(_g(cfg, 'bar_count', 64) or 64)
    scale = _g(cfg, 'scale', 'log')  # lin/log/sqrt/cbrt
    size = f'{W}x{H}'

    # --- moderne, farbenfrohe Presets ---------------------------------------
    # Technik: showcqt liefert weiße, intensitäts-skalierte Balken (cscheme=1|1|1|1|1|1
    # -> schwarz wo Stille, weiß wo Energie). Darüber wird per multiply ein horizontaler
    # Regenbogen-Verlauf gelegt, sodass jede Frequenz/Position eine eigene Farbe bekommt.
    def _rainbow(w, h, sp):
        return (f'gradients=s={w}x{h}:x0=0:y0=0:x1={w}:y1=0:nb_colors=7:'
                f'c0=0xff2d55:c1=0xff8a00:c2=0xffe000:c3=0x00d364:'
                f'c4=0x00c2ff:c5=0x3d5afe:c6=0xc043ff:speed={sp}')
    _white = 'cscheme=1|1|1|1|1|1'
    if t == 'eco_logo':
        # SPARSAM: statisches Naturmacher-Standbild als Hintergrund + farbige
        # Spektrum-Balken im unteren Drittel. KEIN gblur, KEIN animierter
        # Gradient -> nur ein Bruchteil der CPU von aurora_flow.
        # Statischer Farb-Hintergrund (Naturmacher-Grün) + bunte CQT-Balken unten.
        # KEIN movie-loop (haengt ffmpeg), KEIN gblur/gradient -> zuverlaessig + sparsam.
        # Das Logo kommt als Overlay über build_filter (show_logo=True).
        bg = (_g(cfg, 'bg_color', '0x0d2e22')).replace('#', '0x')
        bh = H * 2 // 3
        return (f'color=c={bg}:s={size}:r={F}[bg];'
                f'[0:a]showcqt=s={W}x{bh}:fps={F}:count=2:gamma=4:bar_g=2:axis_h=0:sono_h=0:'
                f'cscheme=1|0.5|0|0|0.5|1[bars];'
                f'[bg][bars]overlay=0:{H - bh}:shortest=1')
    if t == 'cqt_rainbow':
        # bunte Balken (Regenbogen nach Frequenz) + Glow
        return (f'{_rainbow(W, H, 0.006)}[gr];'
                f'[0:a]showcqt=s={size}:fps={F}:count=6:gamma=2:bar_g=2:axis_h=0:sono_h=0:{_white}[bars];'
                f'[bars][gr]blend=all_mode=multiply:shortest=1,'
                f'split[c1][c2];[c2]gblur=sigma=8[cb];[c1][cb]blend=all_mode=screen,'
                f'eq=saturation=1.4:contrast=1.08')
    if t == 'cqt_aurora':
        # gespiegelte bunte Balken mit starkem Leuchten (Musikvideo-Look)
        return (f'{_rainbow(W, H // 2, 0.006)}[gr];'
                f'[0:a]showcqt=s={W}x{H // 2}:fps={F}:count=6:gamma=2:bar_g=2:axis_h=0:sono_h=0:{_white}[bars];'
                f'[bars][gr]blend=all_mode=multiply:shortest=1,'
                f'split[c1][c2];[c2]gblur=sigma=10[cb];[c1][cb]blend=all_mode=screen,'
                f'eq=saturation=1.5:contrast=1.06,split[u][d];[d]vflip[dd];[u][dd]vstack')
    if t == 'cqt_prism':
        # bunte Balken mit langsam fließenden Farben (animierter Verlauf)
        return (f'{_rainbow(W, H, 0.045)}[gr];'
                f'[0:a]showcqt=s={size}:fps={F}:count=6:gamma=2:bar_g=2:axis_h=0:sono_h=0:{_white}[bars];'
                f'[bars][gr]blend=all_mode=multiply:shortest=1,'
                f'split[c1][c2];[c2]gblur=sigma=9[cb];[c1][cb]blend=all_mode=screen,'
                f'eq=saturation=1.5:contrast=1.08')
    if t == 'aurora_flow':
        # animierter, SEHR dunkler Farbverlauf-Hintergrund + gespiegelte bunte Leucht-Balken
        # (Hintergrund bewusst fast schwarz, damit die Regenbogen-Balken die Farben dominieren)
        return (f'gradients=s={size}:c0=0x05030f:c1=0x070a1a:c2=0x040b14:c3=0x0c0718:'
                f'nb_colors=4:speed=0.005[bg];'
                f'{_rainbow(W, H // 2, 0.012)}[gr];'
                f'[0:a]showcqt=s={W}x{H // 2}:fps={F}:count=6:gamma=2:bar_g=2:axis_h=0:sono_h=0:{_white}[bars];'
                f'[bars][gr]blend=all_mode=multiply:shortest=1,'
                f'split[c1][c2];[c2]gblur=sigma=11[cb];[c1][cb]blend=all_mode=screen,'
                f'eq=saturation=1.6:contrast=1.05,split[u][d];[d]vflip[dd];[u][dd]vstack[barsm];'
                f'[bg][barsm]blend=all_mode=screen:shortest=1')
    if t == 'showcqt':
        return f'[0:a]showcqt=s={size}:fps={F}:count=6:gamma=5:bar_g=2:axis_h=0:sono_h=0:cscheme=1|0.5|0|0|0.5|1'
    if t == 'showcwt':
        return f'[0:a]showcwt=s={size}:rate={F}'
    if t == 'showcwt_mel':
        return f'[0:a]showcwt=s={size}:rate={F}:scale=mel'
    if t == 'showcwt_bark':
        return f'[0:a]showcwt=s={size}:rate={F}:scale=bark'
    if t == 'showcwt_log':
        return f'[0:a]showcwt=s={size}:rate={F}:scale=log'
    if t == 'cqt_glow':
        return (f'[0:a]showcqt=s={size}:fps={F}:count=6:gamma=5:bar_g=2:axis_h=0:sono_h=0,split[c1][c2];'
                f'[c2]gblur=sigma=9[cb];[c1][cb]blend=all_mode=screen')
    if t == 'cqt_mirror':
        return (f'[0:a]showcqt=s={W}x{H // 2}:fps={F}:count=6:gamma=5:bar_g=2:axis_h=0:sono_h=0,split[c1][c2];'
                f'[c2]vflip[c3];[c1][c3]vstack')
    if t == 'waves_mirror':
        return (f'[0:a]showwaves=s={W}x{H // 2}:mode=cline:rate={F}:colors={base},split[w1][w2];'
                f'[w2]vflip[w3];[w1][w3]vstack')
    if t == 'waves_p2p':
        return f'[0:a]showwaves=s={size}:mode=p2p:rate={F}:colors={base}'
    if t == 'spectrum_mirror':
        c = color if color in SPECTRUM_COLORS else 'fire'
        return (f'[0:a]showspectrum=s={W}x{H // 2}:slide=scroll:mode=combined:color={c}:scale=log:fps={F},'
                f'split[s1][s2];[s2]vflip[s3];[s1][s3]vstack')
    if t == 'freqs_dot':
        return f'[0:a]showfreqs=s={size}:mode=dot:ascale=log:fscale=log:colors={base}'
    if t == 'freqs_centered':
        return f'[0:a]showfreqs=s={size}:mode=bar:ascale=log:fscale=log:colors={base}:cmode=combined:fscale=rlog'
    if t == 'vectorscope_dot':
        return f'[0:a]avectorscope=s={size}:rate={F}:mode=lissajous:draw=dot:zoom=2:rc=60:gc=200:bc=255'
    if t == 'vectorscope_lissajous_xy':
        return f'[0:a]avectorscope=s={size}:rate={F}:mode=lissajous_xy:draw=line:zoom=1.4:rc=40:gc=160:bc=255'
    if t == 'ahistogram_combined':
        return f'[0:a]ahistogram=s={size}:rate={F}:dmode=single:slide=scroll'
    if t == 'cqt_warm':
        return f'[0:a]showcqt=s={size}:fps={F}:count=6:gamma=5:bar_g=2:axis_h=0:sono_h=0:cscheme=1|0.4|0.1|0.1|0.4|0.9'
    if t == 'cqt_neon':
        return (f'[0:a]showcqt=s={size}:fps={F}:count=6:gamma=4:bar_g=1:axis_h=0:sono_h=0,'
                f'split[n1][n2];[n2]gblur=sigma=5[nb];[n1][nb]blend=all_mode=screen,'
                f'eq=saturation=1.6:contrast=1.15')
    if t == 'spectrum_scroll':
        c = color if color in SPECTRUM_COLORS else 'rainbow'
        return f'[0:a]showspectrum=s={size}:slide=scroll:mode=combined:color={c}:scale={scale if scale in ("lin","sqrt","cbrt","log","4thrt","5thrt") else "log"}:fps={F}'
    if t == 'spectrum_bars':
        c = color if color in SPECTRUM_COLORS else 'intensity'
        return f'[0:a]showspectrum=s={size}:slide=replace:mode=combined:color={c}:scale=log:fps={F}'
    if t == 'showfreqs_bar':
        return f'[0:a]showfreqs=s={size}:mode=bar:ascale=log:fscale=log:colors={base}'
    if t == 'showfreqs_line':
        return f'[0:a]showfreqs=s={size}:mode=line:ascale=log:fscale=log:colors={base}'
    if t == 'showwaves_line':
        return f'[0:a]showwaves=s={size}:mode=line:rate={F}:colors={base}'
    if t == 'showwaves_point':
        return f'[0:a]showwaves=s={size}:mode=point:rate={F}:colors={base}'
    if t == 'showwaves_cline':
        return f'[0:a]showwaves=s={size}:mode=cline:rate={F}:colors={base}'
    if t == 'vectorscope_lissajous':
        return f'[0:a]avectorscope=s={size}:rate={F}:mode=lissajous:rc=40:gc=160:bc=255:zoom=1.5:draw=line'
    if t == 'vectorscope_polar':
        return f'[0:a]avectorscope=s={size}:rate={F}:mode=polar:rc=40:gc=160:bc=255:zoom=1.5:draw=line'
    if t == 'ahistogram':
        return f'[0:a]ahistogram=s={size}:rate={F}:dmode=separate:slide=scroll'
    if t == 'showvolume':
        return (f'color=c={bg}:s={size}:r={F}[bgv];'
                f'[0:a]showvolume=r={F}:b=4:w={max(400, W - 200)}:h=40:f=0.95:c=VOLUME[vol];'
                f'[bgv][vol]overlay=(W-w)/2:(H-h)/2')
    if t == 'showspatial':
        return f'[0:a]showspatial=s={size}:rate={F}'
    # Fallback
    return f'[0:a]showcqt=s={size}:fps={F}:axis_h=0:sono_h=0'


def build_filter(cfg, logo_path=None, nowplaying_file=None, font_file=None):
    """Vollständiger -filter_complex-String. Audio = [0:a], Ergebnis-Label = [v]."""
    W = int(_g(cfg, 'width', 1280) or 1280)
    H = int(_g(cfg, 'height', 720) or 720)
    F = int(_g(cfg, 'fps', 25) or 25)
    core = build_core(cfg, W, H, F) + ',format=yuv420p'

    overlays = []
    if cfg.get('show_logo') and logo_path:
        overlays.append('logo')
    if cfg.get('show_nowplaying') and nowplaying_file and font_file:
        overlays.append('text')

    if not overlays:
        return core + '[v]'

    stages = [core + '[v0]']
    cur, i = 'v0', 1
    for kind in overlays:
        out = 'v' if i == len(overlays) else f'v{i}'
        if kind == 'logo':
            sz = int(_g(cfg, 'logo_size', 140) or 140)
            stages.append(f'movie={logo_path},scale={sz}:-1[logo]')
            stages.append(f'[{cur}][logo]overlay=W-w-24:24[{out}]')
        else:  # text
            fs = int(_g(cfg, 'text_size', 30) or 30)
            stages.append(f'[{cur}]drawtext=fontfile={font_file}:textfile={nowplaying_file}:'
                          f'reload=1:x=28:y=H-{fs + 28}:fontsize={fs}:fontcolor=white:'
                          f'box=1:boxcolor=black@0.45:boxborderw=10[{out}]')
        cur, i = out, i + 1
    return ';'.join(stages)
