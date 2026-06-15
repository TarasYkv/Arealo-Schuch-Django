"""
Edge-TTS (Microsoft) — kostenlose, natürliche deutsche Cloud-Stimmen.

- Keine GPU, KEINE lokale CPU-Last (Synthese läuft auf Microsofts Servern),
  kein API-Key, keine Kosten. Ideal für den ausgelasteten Hetzner-Stream-Server.
- Stimmen-Konvention im Projekt: 'edge-<VoiceName>', z. B. 'edge-de-DE-ConradNeural'.
"""
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# edge-tts liegt im Projekt-venv
EDGE_BIN = os.environ.get('EDGE_TTS_BIN', '/var/www/workloom/venv/bin/edge-tts')

# Kuratierte deutsche Stimmen (die natürlichsten); Reihenfolge = Anzeige
VOICES = [
    ('de-DE-ConradNeural', 'Conrad (m, seriös – nachrichtentypisch)'),
    ('de-DE-KatjaNeural', 'Katja (w, warm)'),
    ('de-DE-KillianNeural', 'Killian (m, jung)'),
    ('de-DE-AmalaNeural', 'Amala (w, freundlich)'),
    ('de-DE-FlorianMultilingualNeural', 'Florian (m, mehrsprachig)'),
    ('de-DE-SeraphinaMultilingualNeural', 'Seraphina (w, mehrsprachig)'),
]
VOICE_IDS = {v for v, _ in VOICES}


def is_edge_voice(voice):
    return bool(voice) and str(voice).startswith('edge-')


def voice_id(voice):
    """'edge-de-DE-ConradNeural' -> 'de-DE-ConradNeural'."""
    name = voice.split('edge-', 1)[1] if is_edge_voice(voice) else (voice or '')
    return name or 'de-DE-ConradNeural'


def synth(text, voice=None, rate=None):
    """Vertont Text via edge-tts und liefert MP3-Bytes (b'' bei Fehler)."""
    if not text or not str(text).strip():
        return b''
    name = voice_id(voice)
    with tempfile.TemporaryDirectory() as td:
        txt = os.path.join(td, 'in.txt')
        out = os.path.join(td, 'out.mp3')
        with open(txt, 'w', encoding='utf-8') as fh:
            fh.write(text)
        cmd = [EDGE_BIN, '--voice', name, '--file', txt, '--write-media', out]
        if rate:
            cmd += ['--rate', rate]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        except Exception as e:
            logger.warning('edge-tts Fehler (%s): %s', name, e)
            return b''
        if not os.path.exists(out) or os.path.getsize(out) == 0:
            return b''
        with open(out, 'rb') as fh:
            return fh.read()
