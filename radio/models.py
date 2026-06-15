"""
Datenmodell des Naturmacher KI-Radiosenders.

Diese Tabellen sind die **Single Source of Truth** der Programmplanung:
- Die Timeline-App (Superuser-UI) schreibt hier hinein.
- Die GLM-Agenten (Programmdirektor) schreiben hier hinein.
- Liquidsoap liest daraus (via generierter Config / JSON-Export).

Niemand spielt etwas direkt aus — alles geht über diese DB.
"""
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


class StationConfig(models.Model):
    """Globale Sender-Konfiguration. Als Singleton gedacht (pk=1)."""

    name = models.CharField(max_length=120, default='Naturmacher Radio')

    # YouTube-Live-Anbindung
    rtmp_url = models.CharField(
        max_length=255,
        default='rtmp://a.rtmp.youtube.com/live2',
        help_text='RTMP-Ingest-URL von YouTube Live',
    )
    stream_key = EncryptedCharField(
        max_length=255, blank=True, default='',
        help_text='YouTube-Stream-Schlüssel (verschlüsselt gespeichert)',
    )

    # Stream-Status
    on_air = models.BooleanField(default=False, help_text='Soll der Sender senden?')
    standbild = models.ImageField(
        upload_to='radio/standbilder/', blank=True, null=True,
        help_text='Aktuelles Standbild des Streams (von FLUX generiert oder Upload)',
    )

    VISUAL_MODES = [
        ('image', 'Standbild'),
        ('video_loop', 'Video (Endlosschleife)'),
        ('video_once', 'Video (einmalig, dann Standbild)'),
    ]
    visual_mode = models.CharField(max_length=20, choices=VISUAL_MODES, default='image',
                                   help_text='Was im Stream als Bild läuft')
    visual_auto = models.BooleanField(default=False, help_text='Aktuelles Visual stammt aus einem Beitrag (auto)')

    # Programm-Defaults
    default_mood = models.CharField(
        max_length=120, default='moderne Musik, abwechslungsreich, instrumental',
        help_text='Standard-Stimmung/Genre für Musik-Batches, wenn kein Slot etwas anderes sagt',
    )

    # GPU-Pod-Lifecycle (create-on-demand + auto-terminate bei Leerlauf)
    gpu_pod_id = models.CharField(max_length=40, blank=True, default='',
                                  help_text='Aktueller RunPod-Pod (wird bei Bedarf erstellt)')
    gpu_last_used = models.DateTimeField(null=True, blank=True)
    gpu_busy = models.BooleanField(default=False, help_text='Generierung/Install läuft – nicht beenden')

    # Voice-Cloning (XTTS): Referenz-Audio der zu klonenden Stimme
    clone_voice = models.FileField(upload_to='radio/', blank=True, null=True,
                                   help_text='Referenz-Audio (15-30s) für die geklonte XTTS-Stimme')
    clone_voice_label = models.CharField(max_length=80, blank=True, default='',
                                         help_text='Name der Klon-Stimme')

    # ElevenLabs (Sound-Effekte / Jingles)
    elevenlabs_api_key = EncryptedCharField(
        max_length=255, blank=True, default='',
        help_text='ElevenLabs API-Key (für Sound-Effekte/Jingles), verschlüsselt',
    )
    # MiniMax (günstige Instrumental-/Gesangsmusik)
    fal_api_key = EncryptedCharField(
        max_length=255, blank=True, default='',
        help_text='fal.ai API-Key (Format key_id:secret) für Stimmen/Musik über fal.ai',
    )
    minimax_api_key = EncryptedCharField(
        max_length=255, blank=True, default='',
        help_text='MiniMax Music API-Key (verschlüsselt)',
    )
    # News-Themen (für die automatische 2-Std-News-Suche), eine pro Zeile
    news_topics = models.TextField(
        blank=True,
        default='Garten und Pflanzen\nNachhaltigkeit und Umwelt\nBasteln und DIY mit Kindern\nFamilie und Natur',
        help_text='Relevante News-Themen (eine pro Zeile) für die automatische Recherche',
    )
    # Tagesnews/Journal-Zeitplan (über die News-Seite editierbar)
    news_enabled = models.BooleanField(default=True, help_text='Tagesnews automatisch erzeugen und einplanen')
    news_minute = models.PositiveSmallIntegerField(default=50, help_text='Minute der Stunde, zu der die News laufen (z.B. 50 = 10 vor voll)')
    news_from_hour = models.PositiveSmallIntegerField(default=0, help_text='Erste Stunde (0-23)')
    news_to_hour = models.PositiveSmallIntegerField(default=23, help_text='Letzte Stunde (0-23)')
    news_interval_h = models.PositiveSmallIntegerField(default=1, help_text='Abstand in Stunden (1 = jede Stunde)')
    news_intro_enabled = models.BooleanField(default=True, help_text='Festes Intro vor jede Tagesnews mischen')

    # Öffentliche YouTube-Live-Adresse (für „Ausweichen bei hoher Auslastung")
    youtube_url = models.CharField(
        max_length=300, blank=True, default='',
        help_text='YouTube-Live-Adresse des Senders (Ausweich-Link bei voller Auslastung)')

    # --- Standardprogramm: Misch-Regeln, wenn nichts Festes geplant ist ---
    std_music_per_talk = models.PositiveIntegerField(
        default=4, help_text='So viele Musiktitel, dann ein Wortbeitrag (0 = nie Wortbeitrag automatisch)')
    std_jingle_every = models.PositiveIntegerField(
        default=0, help_text='Jingle/Senderkennung etwa alle N Musiktitel (0 = keine)')
    std_ad_every_min = models.PositiveIntegerField(
        default=0, help_text='Werbung/Spot etwa alle M Minuten (0 = keine)')

    # --- Übergänge / Crossfade (live an Liquidsoap via Telnet) ---
    mix_crossfade = models.BooleanField(
        default=True, help_text='Sanftes Überblenden zwischen Titeln aktivieren')
    mix_xfade_sec = models.DecimalField(
        max_digits=3, decimal_places=1, default=1.5,
        help_text='Überblend-Dauer in Sekunden (0–3.8); Sprache/Geschichten laufen immer ganz aus')
    mix_xfade_songs = models.BooleanField(
        default=False, help_text='Auch Lieder MIT Gesang überblenden (sonst spielen sie vollständig zu Ende)')

    # --- TTS-Feintuning (gilt global für die jeweilige Engine) ---
    gemini_tts_model = models.CharField(
        max_length=10, default='flash',
        choices=[('flash', 'Flash (schnell, zuverlässig)'), ('pro', 'Pro (höchste Qualität, langsamer)')],
        help_text='Gemini-TTS-Modell',
    )
    eleven_model_id = models.CharField(
        max_length=40, default='eleven_multilingual_v2',
        help_text='ElevenLabs-TTS-Modell (z. B. eleven_multilingual_v2, eleven_turbo_v2_5)',
    )
    eleven_stability = models.FloatField(default=0.5, help_text='ElevenLabs Stabilität 0–1')
    eleven_similarity = models.FloatField(default=0.75, help_text='ElevenLabs Similarity Boost 0–1')
    eleven_style = models.FloatField(default=0.0, help_text='ElevenLabs Style Exaggeration 0–1')
    eleven_speaker_boost = models.BooleanField(default=True, help_text='ElevenLabs Speaker Boost')

    # Audio-Visualizer (Stream-Visual): freie Einstellungs-Map (siehe radio/visualizer.py)
    viz_settings = models.JSONField(default=dict, blank=True,
                                    help_text='Audio-Visualizer-Einstellungen (Typ, Farben, Auflösung …)')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sender-Konfiguration'
        verbose_name_plural = 'Sender-Konfiguration'

    app_promo_lines = models.TextField(blank=True, default='', help_text='Naturmacher-Ankündigungen für App & Hörseite (eine pro Zeile)')
    song_share = models.PositiveSmallIntegerField(default=35, help_text='Anteil Lieder MIT Gesang an der Musik-Rotation in Prozent (0 = nur Instrumental, 100 = nur Gesang)')
    app_promo_code = models.CharField(max_length=60, blank=True, default='Naturmacher-Radio', help_text='Rabattcode im Promo-Badge')
    app_promo_benefit = models.CharField(max_length=60, blank=True, default='Gratis-Versand', help_text='Vorteils-Text neben dem Code (leer = nur Code)')
    app_promo_url = models.URLField(blank=True, default='https://www.naturmacher.de/?utm_source=radio_app&utm_medium=app&utm_campaign=promo', help_text='Ziel-Link der Promo-Kachel')
    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Rubrik(models.Model):
    """
    Eine editierbare Beitrags-Rubrik. GLM 5.1 erzeugt Inhalte anhand dieser
    Daten. Built-in-Rubriken (Musik, Geschichte, …) sind vorbefüllt, eigene
    können angelegt/entfernt werden.
    """
    TYPES = [('music', 'Musik'), ('speech', 'Sprache')]
    CATEGORIES = [
        ('', 'Automatisch (nach Art)'),
        ('talk', 'Wortbeitrag'),
        ('jingle', 'Jingle / Effekt'),
        ('ad', 'Werbung / Spot'),
        ('music', 'Musik'),
    ]

    key = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    rtype = models.CharField(max_length=10, choices=TYPES, default='speech')
    system_prompt = models.TextField(help_text='Rolle/Stil-Vorgabe für GLM 5.1')
    task_prompt = models.TextField(blank=True, default='', help_text='Konkreter Schreibauftrag (Sprache) bzw. Zusatz (Musik)')
    voice = models.CharField(max_length=60, blank=True, default='piper-thorsten-medium',
                             help_text='Stimme (nur Sprache)')
    intro = models.ForeignKey('Track', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='+',
                              help_text='Optionales Intro (z.B. Jingle), das automatisch VOR jedem Beitrag dieser Rubrik gespielt wird')
    outro = models.ForeignKey('Track', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='+',
                              help_text='Optionales Outro, das automatisch NACH jedem Beitrag dieser Rubrik gespielt wird')
    tts_model = models.CharField(max_length=40, blank=True, default='',
                                 help_text='Optionales TTS-Modell-Detail passend zur Engine der Stimme '
                                           '(z. B. Gemini flash/pro oder ein ElevenLabs-Modell); leer = Standard')
    target_sec = models.PositiveIntegerField(default=0,
                                             help_text='Gewünschte Audiolänge in Sekunden (0 = automatisch je nach Rubrik-Art)')
    category = models.CharField(max_length=12, blank=True, default='', choices=CATEGORIES,
                                help_text='Zählt diese Rubrik im Standardprogramm als Wortbeitrag, Jingle, '
                                          'Werbung oder Musik? Leer = automatisch nach Art.')
    topic_memory = models.TextField(blank=True, default='',
                                    help_text='Themen-Gedächtnis: eine Zeile = ein bereits vergebenes Thema. '
                                              'Neue Beiträge meiden diese Themen; frei editierbar.')
    in_nightly = models.BooleanField(default=False, help_text='Teil des nächtlichen Auto-Pakets')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=100)
    builtin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'label']
        verbose_name = 'Rubrik'
        verbose_name_plural = 'Rubriken'

    def __str__(self):
        return f'{self.label} ({self.key})'


class ContentTag(models.Model):
    """
    Schlagwort/Saison-Tag für Inhalte (z.B. "weihnachten", "ostern", "ruhig").

    Inhalte (Track/SpokenContent) tragen die Tag-Namen als kommaseparierte
    Liste im Feld `tags`. Hat ein Tag ein Zeitfenster (start_md..end_md als
    "MM-TT") und ist `exclusive`, dann werden so getaggte Inhalte AUTOMATISCH
    nur innerhalb des Fensters eingeplant und sonst gesperrt.
    """
    name = models.SlugField(max_length=40, unique=True, help_text='z.B. weihnachten')
    label = models.CharField(max_length=80, blank=True, default='')
    color = models.CharField(max_length=9, blank=True, default='#8b5cf6',
                             help_text='Hex-Farbe für die Anzeige')
    start_md = models.CharField(max_length=5, blank=True, default='',
                                help_text='Saison-Beginn "MM-TT", z.B. 12-01 (leer = kein Fenster)')
    end_md = models.CharField(max_length=5, blank=True, default='',
                              help_text='Saison-Ende "MM-TT", z.B. 12-26')
    exclusive = models.BooleanField(default=True,
                                    help_text='Außerhalb des Fensters automatisch sperren')
    boost = models.PositiveSmallIntegerField(default=1,
                                             help_text='Gewichtung WÄHREND der Saison: 1 = normal, '
                                                       'N = N-fach so häufig im Automatik-Pool (max 10)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Inhalts-Tag'
        verbose_name_plural = 'Inhalts-Tags'

    def __str__(self):
        return self.label or self.name

    def is_in_season(self, d):
        """Ob das Datum d im Saison-Fenster liegt. Kein Fenster = immer True."""
        if not (self.start_md and self.end_md):
            return True
        md = '%02d-%02d' % (d.month, d.day)
        s, e = self.start_md, self.end_md
        if s <= e:
            return s <= md <= e
        # Jahreswechsel-Wrap (z.B. 12-20 .. 01-06)
        return md >= s or md <= e


class Track(models.Model):
    """Ein abspielbarer Musik-Titel (KI-generiert via MusicGen oder Upload)."""

    SOURCE_CHOICES = [
        ('musicgen', 'KI (MusicGen, RunPod)'),
        ('acestep', 'KI mit Gesang (ACE-Step, RunPod)'),
        ('lyria', 'KI-Musik (Google Lyria)'),
        ('minimax', 'KI-Musik (MiniMax)'),
        ('elevenmusic', 'KI-Musik (ElevenLabs)'),
        ('fal', 'KI-Musik (fal.ai)'),
        ('elevenlabs', 'Sound-Effekt/Jingle (ElevenLabs)'),
        ('openverse', 'Freie Musik (Openverse/Jamendo)'),
        ('upload', 'Manueller Upload'),
    ]

    title = models.CharField(max_length=200)
    audio_file = models.FileField(upload_to='radio/music/')
    mood = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Stimmung/Genre-Tags, z.B. "ruhig, ambient, kindgerecht"',
    )
    description = models.CharField(max_length=300, blank=True, default='',
                                   help_text='Kurzbeschreibung für die Bibliothek')
    CATEGORY_CHOICES = [('', 'Automatisch'), ('music', 'Musik (instrumental)'),
                        ('song', 'Musik mit Gesang'), ('effekt', 'Sound-Effekt / Jingle'),
                        ('ad', 'Werbung / Spot')]
    category = models.CharField(max_length=10, blank=True, default='', choices=CATEGORY_CHOICES,
                                help_text='Manuelle Rubrik-Zuordnung (leer = automatisch aus Quelle abgeleitet)')
    gen_model = models.CharField(max_length=60, blank=True, default='',
                                 help_text='Konkretes KI-Modell, mit dem der Track erzeugt wurde (z.B. lyria-3-pro)')
    lyrics = models.TextField(blank=True, default='',
                              help_text='Gesangstext (bei Liedern mit Gesang)')
    duration_sec = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='musicgen')
    prompt = models.TextField(blank=True, default='', help_text='MusicGen-Prompt, mit dem der Track erzeugt wurde')
    tags = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Schlagworte/Saison-Tags (kommasepariert), z.B. "weihnachten, ruhig"',
    )

    is_active = models.BooleanField(default=True, help_text='Darf automatisch gespielt werden? (aus = nur manuell)')
    play_count = models.PositiveIntegerField(default=0)
    last_played_at = models.DateTimeField(null=True, blank=True, help_text='Zuletzt im Sender abgespielt')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.mood})'


class ProgramSlot(models.Model):
    """
    Ein wiederkehrender Programmblock in der Timeline.

    Das ist die Einheit, die in der Timeline-App bearbeitet wird:
    Musikrichtung, News-Slot, Werbung, Gute-Nacht-Geschichte zu fester Uhrzeit.
    """

    SLOT_TYPES = [
        ('music', 'Musik'),
        ('news', 'News (vorgelesen)'),
        ('story', 'Gute-Nacht-Geschichte'),
        ('jingle', 'Jingle'),
        ('ad', 'Werbung'),
    ]

    WEEKDAYS = [
        (0, 'Montag'), (1, 'Dienstag'), (2, 'Mittwoch'), (3, 'Donnerstag'),
        (4, 'Freitag'), (5, 'Samstag'), (6, 'Sonntag'),
    ]

    name = models.CharField(max_length=120)
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPES, default='music')

    start_time = models.TimeField(help_text='Uhrzeit, zu der dieser Block startet (z.B. 18:00)')
    duration_min = models.PositiveIntegerField(default=5, help_text='Dauer in Minuten')

    # Tage, an denen der Slot aktiv ist (kommaseparierte Wochentag-Indizes 0-6, leer = täglich)
    days = models.CharField(
        max_length=20, blank=True, default='',
        help_text='Wochentage als kommaseparierte Zahlen 0=Mo..6=So, leer = täglich',
    )

    # Für Musik-Slots: gewünschte Stimmung. Für News: Themen.
    mood = models.CharField(max_length=120, blank=True, default='')
    topics = models.CharField(
        max_length=255, blank=True, default='',
        help_text='News-Themen (kommasepariert), passend zu naturmacher',
    )

    # Slot-Planer: erlaubte Inhalts-Rubriken in diesem Slot + Mischregeln
    kinds = models.CharField(
        max_length=200, blank=True, default='music,song',
        help_text='Erlaubte Rubriken in diesem Slot (kommasepariert: music,song,news,tip,wissen,story,dialog,jingle,effekt,ad)',
    )
    music_per_talk = models.PositiveIntegerField(
        default=3, help_text='So viele Musiktitel, dann ein Wortbeitrag (0 = nie Wort dazwischen)')
    ad_every_min = models.PositiveIntegerField(
        default=0, help_text='Werbung/Spot etwa alle N Minuten (0 = keine)')

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['start_time', 'order']
        verbose_name = 'Programm-Slot'
        verbose_name_plural = 'Programm-Slots'

    def __str__(self):
        return f'{self.start_time:%H:%M} {self.get_slot_type_display()} – {self.name}'

    def active_weekdays(self):
        if not self.days.strip():
            return list(range(7))
        return [int(d) for d in self.days.split(',') if d.strip().isdigit()]


class SpokenContent(models.Model):
    """
    Vorgelesener Inhalt (News-Block oder Gute-Nacht-Geschichte).

    Texte werden von GLM-Agenten geschrieben, Audio von Piper (CPU) erzeugt.
    Liquidsoap zieht das fertige Audio zur geplanten Sendezeit.
    """

    STATUS = [
        ('draft', 'Entwurf (Text)'),
        ('generated', 'Audio erzeugt'),
        ('aired', 'Gesendet'),
        ('archived', 'Archiviert'),
    ]

    KIND = [
        ('story', 'Gute-Nacht-Geschichte'),
        ('klanggeschichte', 'Klang-Hörgeschichte (mit Effekten)'),
        ('wissen', 'Wissenswertes'),
        ('tip', 'Tipp'),
        ('news', 'News'),
        ('kreativ', 'Kreativ-Beitrag'),
        ('dialog', 'Dialog (zwei Sprecher)'),
        ('jingle', 'Jingle / Senderkennung'),
        ('effekt', 'Sound-Effekt / Jingle (ElevenLabs)'),
        ('ad', 'Marken-Spot / Mitmach'),
    ]

    slot = models.ForeignKey(
        ProgramSlot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='spoken_contents',
    )
    kind = models.CharField(max_length=20, choices=KIND, default='wissen')
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True, default='',
                                   help_text='Kurzbeschreibung für die Bibliothek')
    text = models.TextField(help_text='Vorlesetext (von GLM-Agent geschrieben)')
    audio_file = models.FileField(upload_to='radio/spoken/', blank=True, null=True)
    gen_model = models.CharField(max_length=60, blank=True, default='', help_text='KI-Modell der Vertonung (z. B. pro, eleven_multilingual_v2)')
    duration_sec = models.PositiveIntegerField(default=0, help_text='Länge der Vertonung in Sekunden')

    voice = models.CharField(
        max_length=60, default='piper-thorsten-medium',
        help_text='Piper-Stimme, vgl. video/tts.py PIPER_VOICE_MAP',
    )
    air_date = models.DateField(null=True, blank=True, help_text='Für welchen Tag geplant')
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    auto_include = models.BooleanField(
        default=True,
        help_text='Darf automatisch in den Sendeplan aufgenommen werden (aus = nur manuell/per festem Pin)',
    )
    tags = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Schlagworte/Saison-Tags (kommasepariert), z.B. "weihnachten"',
    )
    last_played_at = models.DateTimeField(null=True, blank=True, help_text='Zuletzt im Sender abgespielt')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-air_date', '-created_at']
        verbose_name = 'Vorgelesener Inhalt'
        verbose_name_plural = 'Vorgelesene Inhalte'

    def __str__(self):
        return f'[{self.get_status_display()}] {self.title}'


class ScheduledItem(models.Model):
    """
    Ein zeitgebundener Programm-Pin im Tagesplan.

    Anders als ProgramSlot (Block mit Mischregeln) plant ein ScheduledItem GENAU
    EINEN Beitrag zu einer ABSOLUTEN Uhrzeit:
      - rubrik_auto:    zur Uhrzeit einen ZUFÄLLIGEN passenden Bibliotheks-Beitrag
                        der Rubrik (z.B. 19:00 irgendeine Klanggeschichte)
      - rubrik_gen:     wie rubrik_auto, aber wenn keiner da ist, NEU erzeugen
      - pinned_track:   einen KONKRETEN Track
      - pinned_spoken:  einen KONKRETEN Wort-Beitrag

    Wiederkehrend via `days` (CSV 0-6, leer=täglich) ODER einmalig via `on_date`.
    WICHTIG: start_time ist Senderzeit Europe/Berlin (anders als ProgramSlot=UTC);
    Umrechnung passiert zentral im Materializer/Timeline (scheduler.py).
    """

    MODES = [
        ('compose', 'Beitrag selbst erzeugen (wie im Studio)'),
        ('rubrik_auto', 'Rubrik – zufällig aus Bibliothek'),
        ('rubrik_gen', 'Rubrik – erzeugen falls keiner da'),
        ('pinned_track', 'Fester Musik-Titel'),
        ('pinned_spoken', 'Fester Wort-Beitrag'),
    ]
    ENFORCE = [
        ('anchor', 'Ungefähr (Anker)'),
        ('exact', 'Exakt (unterbricht)'),
    ]

    name = models.CharField(max_length=120, blank=True, default='')
    mode = models.CharField(max_length=20, choices=MODES, default='rubrik_auto')
    rubrik_key = models.SlugField(max_length=40, blank=True, default='')
    track = models.ForeignKey('Track', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='scheduled_items')
    spoken = models.ForeignKey('SpokenContent', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='scheduled_items')

    start_time = models.TimeField(help_text='Uhrzeit des Pins (Senderzeit Berlin), z.B. 19:00')
    on_date = models.DateField(null=True, blank=True,
                               help_text='Einmaliger Termin (leer = wiederkehrend nach Wochentagen)')
    days = models.CharField(max_length=20, blank=True, default='',
                            help_text='Wochentage 0=Mo..6=So kommasepariert, leer=täglich (nur wenn on_date leer)')
    enforce = models.CharField(max_length=10, choices=ENFORCE, default='anchor')
    topic = models.TextField(blank=True, default='',
                             help_text='Themenhinweis(e) für GLM; mehrere kommagetrennt (News-Termine)')
    gen_spec = models.JSONField(default=dict, blank=True,
                                help_text='Selbst definierte Beitrags-Vorgaben (Modus compose): '
                                          'kind/title/text/voice/target_sec/style/engine')
    gen_status = models.CharField(max_length=12, blank=True, default='',
                                  help_text='compose-Status: pending/generating/done/failed')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Reihenfolge bei gleicher Uhrzeit')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time', 'order']
        verbose_name = 'Geplanter Pin'
        verbose_name_plural = 'Geplante Pins'

    def __str__(self):
        return f'{self.start_time:%H:%M} {self.get_mode_display()} – {self.name or self.rubrik_key}'

    def active_weekdays(self):
        if self.on_date:
            return [self.on_date.weekday()]
        if not self.days.strip():
            return list(range(7))
        return [int(d) for d in self.days.split(',') if d.strip().isdigit()]

    def applies_on(self, d):
        if not self.is_active:
            return False
        if self.on_date:
            return self.on_date == d
        return d.weekday() in self.active_weekdays()

    @property
    def content(self):
        if self.mode == 'pinned_track':
            return self.track
        if self.mode == 'pinned_spoken':
            return self.spoken
        return None


class MusicBatchJob(models.Model):
    """Protokoll eines nächtlichen MusicGen-Batch-Laufs auf RunPod."""

    STATUS = [
        ('pending', 'Wartet'),
        ('running', 'Läuft'),
        ('done', 'Fertig'),
        ('failed', 'Fehlgeschlagen'),
    ]

    mood = models.CharField(max_length=120, default='')
    count_requested = models.PositiveIntegerField(default=10)
    count_done = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    log = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Musik-Batch-Job'
        verbose_name_plural = 'Musik-Batch-Jobs'

    def __str__(self):
        return f'Batch {self.created_at:%Y-%m-%d %H:%M} – {self.get_status_display()} ({self.count_done}/{self.count_requested})'


class PlaylistEntry(models.Model):
    """
    Ein Eintrag im Sendeplan (die rollierende Warteschlange).

    Das ist die Einheit, in die der Superuser in der Timeline-App "reinhört"
    und die er bearbeitet (umsortieren, ersetzen, rauswerfen) BEVOR sie
    ausgestrahlt wird. Liquidsoap spielt diese Liste der Reihe nach ab.

    Ein Eintrag verweist je nach Typ auf einen Track (Musik) oder einen
    SpokenContent (News/Geschichte/Tipp). Jingles/Spots können später als
    eigene Asset-Typen ergänzt werden; bis dahin tragen sie ihr Audio direkt.
    """

    KIND = [
        ('music', 'Musik'),
        ('news', 'News'),
        ('story', 'Gute-Nacht-Geschichte'),
        ('tip', 'Tipp'),
        ('wissen', 'Wissenswertes'),
        ('kreativ', 'Kreativ-Beitrag'),
        ('dialog', 'Dialog (zwei Sprecher)'),
        ('jingle', 'Jingle / Senderkennung'),
        ('effekt', 'Sound-Effekt / Jingle (ElevenLabs)'),
        ('ad', 'Marken-Spot / Mitmach'),
    ]

    STATUS = [
        ('queued', 'In Warteschlange'),
        ('playing', 'Läuft gerade'),
        ('played', 'Gespielt'),
        ('skipped', 'Übersprungen'),
    ]

    position = models.PositiveIntegerField(default=0, db_index=True, help_text='Reihenfolge im Sendeplan')
    kind = models.CharField(max_length=20, choices=KIND, default='music')

    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, blank=True, related_name='playlist_entries')
    spoken = models.ForeignKey(SpokenContent, on_delete=models.SET_NULL, null=True, blank=True, related_name='playlist_entries')

    # Geplante Sendezeit (geschätzt, ergibt sich aus Reihenfolge + Dauer)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='queued')
    started_at = models.DateTimeField(null=True, blank=True, help_text='Wann der Beitrag tatsächlich zu spielen begann')

    manual = models.BooleanField(default=False, help_text='Manuell im Studio erstellt')
    intro_done = models.BooleanField(default=False,
                                     help_text='Rubrik-Intro für diesen Eintrag wurde bereits ausgespielt')
    outro_pending = models.BooleanField(default=False,
                                        help_text='Nach diesem Eintrag soll noch das Rubrik-Outro gespielt werden')
    # Optionales Video (Pexels) als Stream-Visual während dieser Beitrag läuft
    video_url = models.CharField(max_length=500, blank=True, default='')
    video_file = models.FileField(upload_to='radio/entry_videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']
        verbose_name = 'Sendeplan-Eintrag'
        verbose_name_plural = 'Sendeplan'

    def __str__(self):
        return f'{self.position:03d} [{self.get_kind_display()}] {self.title}'

    @property
    def content(self):
        """Das verknüpfte Inhaltsobjekt (Track oder SpokenContent)."""
        return self.track or self.spoken

    @property
    def title(self):
        c = self.content
        return getattr(c, 'title', '—') if c else '—'

    @property
    def audio_url(self):
        """URL der Audiodatei zum Reinhören (oder None)."""
        c = self.content
        f = getattr(c, 'audio_file', None) if c else None
        try:
            return f.url if f else None
        except ValueError:
            return None

    @property
    def duration_sec(self):
        c = self.content
        return getattr(c, 'duration_sec', 0) if c else 0


class RadioNote(models.Model):
    """Notiz-Kachel fürs Radio-Studio (Titel, Text, Autor, Datum)."""
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True, default="")
    author = models.CharField(max_length=80, blank=True, default="")
    color = models.CharField(max_length=16, blank=True, default="#2b7a4b")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
