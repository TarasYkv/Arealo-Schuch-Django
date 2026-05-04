#!/bin/bash
# Entrypoint-Wrapper: passt SCREEN_RESOLUTION durch und startet Supervisord.
set -euo pipefail

: "${SCREEN_RESOLUTION:=1280x800x24}"
export SCREEN_RESOLUTION

mkdir -p /var/log /tmp/chromium-profile

echo "[entrypoint] Browser-Stack startet"
echo "[entrypoint]   Display: ${DISPLAY:-:99}"
echo "[entrypoint]   Resolution: ${SCREEN_RESOLUTION}"
echo "[entrypoint]   Time: $(date)"

exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/browser-stack.conf
