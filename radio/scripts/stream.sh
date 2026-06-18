#!/usr/bin/env bash
# =============================================================================
#  Naturmacher KI-Radio – ffmpeg RTMP-Push an YouTube Live (mit Auto-Reconnect)
# =============================================================================
#  Visual wird dynamisch gewählt (vom Dashboard änderbar):
#    media/radio/visual_mode  -> "image" | "video_loop" | "video_once"
#    media/radio/standbild.png   (Standbild)
#    media/radio/background.mp4  (hochgeladenes Video)
#  Django schreibt visual_mode + Datei und beendet den ffmpeg per PID
#  (media/radio/stream_ffmpeg.pid) -> diese Schleife startet mit neuem Visual.
# =============================================================================
set -u

MEDIA="${RADIO_MEDIA:-/var/www/workloom/media/radio}"
ICECAST_URL="${ICECAST_URL:-http://127.0.0.1:8000/radio.mp3}"
YT_RTMP_URL="${YT_RTMP_URL:-rtmp://a.rtmp.youtube.com/live2}"
STANDBILD="${RADIO_STANDBILD:-$MEDIA/standbild.png}"
VIDEO="$MEDIA/background.mp4"
PIDFILE="$MEDIA/stream_ffmpeg.pid"

if [[ -z "${YT_STREAM_KEY:-}" ]]; then
  echo "[stream.sh] FEHLER: YT_STREAM_KEY nicht gesetzt." >&2; exit 1
fi

# Ausgabeziele: YouTube immer, Twitch zusätzlich wenn Key gesetzt.
# tee-Muxer dupliziert den fertigen Stream ohne Doppel-Encoding;
# onfail=ignore: fällt eine Plattform aus, läuft die andere weiter.
TEE_OUT="[f=flv:onfail=ignore]${YT_RTMP_URL}/${YT_STREAM_KEY}"
if [[ -n "${TWITCH_STREAM_KEY:-}" ]]; then
  TEE_OUT="${TEE_OUT}|[f=flv:onfail=ignore]rtmp://live.twitch.tv/app/${TWITCH_STREAM_KEY}"
fi
if [[ -n "${KICK_STREAM_KEY:-}" ]]; then
  TEE_OUT="${TEE_OUT}|[f=flv:onfail=ignore]rtmps://fa723fc1b171.global-contribute.live-video.net:443/app/${KICK_STREAM_KEY}"
fi

# ---------------------------------------------------------------------------
# Watchdog: startet ffmpeg neu, sobald ein Stream-Ziel (YouTube/Twitch/IVS)
# wegbricht. Ohne ihn liefe ffmpeg wegen onfail=ignore nur mit den restlichen
# Zielen weiter und wuerde das ausgefallene Ziel NIE von selbst neu verbinden
# (= YouTube bleibt stundenlang tot). Erkennung ueber die ffmpeg-Logmeldung
# "Slave muxer #N failed" im journal. Anlauf-/Pruefintervall verhindert
# einen Crash-Loop bei dauerhaft kaputtem Ziel.
wait_with_watchdog() {
  local pid="$1"
  (
    sleep 25
    while kill -0 "$pid" 2>/dev/null; do
      if journalctl -u naturmacher-radio-stream --since "25 seconds ago" 2>/dev/null \
           | grep -qE "Slave muxer .* failed|All tee outputs failed"; then
        echo "[stream.sh] Watchdog: Stream-Ziel ausgefallen -> ffmpeg-Neustart (alle Ziele neu verbinden)" >&2
        kill "$pid" 2>/dev/null
        return
      fi
      sleep 20
    done
  ) &
  local wd=$!
  wait "$pid"
  kill "$wd" 2>/dev/null
  wait "$wd" 2>/dev/null
}

while true; do
  # Sendung an/aus (vom Dashboard schaltbar, ohne Root). Default: an.
  ENABLED=1; [[ -f "$MEDIA/stream_enabled" ]] && ENABLED="$(tr -d '[:space:]' < "$MEDIA/stream_enabled")"
  if [[ "$ENABLED" != "1" ]]; then
    rm -f "$PIDFILE"
    sleep 5
    continue
  fi

  MODE="image"; [[ -f "$MEDIA/visual_mode" ]] && MODE="$(tr -d '[:space:]' < "$MEDIA/visual_mode")"

  # --- Audio-Visualizer: Video wird aus dem Live-Ton erzeugt (radio/visualizer.py) ---
  if [[ "$MODE" == "visualizer" && -f "$MEDIA/visualizer_filter.txt" ]]; then
    VFLT="$(cat "$MEDIA/visualizer_filter.txt")"
    VFPS=25; [[ -f "$MEDIA/visualizer_fps.txt" ]] && VFPS="$(tr -d '[:space:]' < "$MEDIA/visualizer_fps.txt")"
    ffmpeg -hide_banner -loglevel warning \
      -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -i "${ICECAST_URL}" \
      -filter_complex "$VFLT" \
      -map "[v]" -map 0:a \
      -c:v libx264 -preset veryfast -pix_fmt yuv420p \
      -b:v 3000k -maxrate 3000k -bufsize 6000k -r "$VFPS" -g $((VFPS*2)) \
      -c:a aac -b:a 192k -ar 44100 \
      -flags +global_header -f tee "${TEE_OUT}" &
    FFPID=$!
    echo "$FFPID" > "$PIDFILE"
    wait_with_watchdog "$FFPID"
    echo "[stream.sh] visualizer-ffmpeg beendet (Code $?). Neustart in 3s..." >&2
    sleep 3
    continue
  fi

  if [[ "$MODE" == "video_loop" && -f "$VIDEO" ]]; then
    VIN=(-stream_loop -1 -re -i "$VIDEO");           VFPS=25; VTUNE=()
  elif [[ "$MODE" == "video_once" && -f "$VIDEO" ]]; then
    VIN=(-re -i "$VIDEO");                            VFPS=25; VTUNE=()
  else
    VIN=(-loop 1 -framerate 2 -i "$STANDBILD");       VFPS=2;  VTUNE=(-tune stillimage)
  fi

  ffmpeg -hide_banner -loglevel warning \
    "${VIN[@]}" \
    -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -i "${ICECAST_URL}" \
    -map 0:v -map 1:a \
    -c:v libx264 -preset veryfast "${VTUNE[@]}" -pix_fmt yuv420p \
    -b:v 3000k -maxrate 3000k -bufsize 6000k -r "$VFPS" -g $((VFPS*2)) \
    -c:a aac -b:a 192k -ar 44100 \
    -flags +global_header -f tee "${TEE_OUT}" &
  FFPID=$!
  echo "$FFPID" > "$PIDFILE"
  wait_with_watchdog "$FFPID"

  # Nach einmaligem Video automatisch zurück auf Standbild
  [[ "$MODE" == "video_once" ]] && echo "image" > "$MEDIA/visual_mode"

  echo "[stream.sh] ffmpeg beendet (Code $?). Neustart in 3s..." >&2
  sleep 3
done
