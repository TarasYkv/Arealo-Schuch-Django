FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    SCREEN_RESOLUTION=1280x800x24 \
    LANG=de_DE.UTF-8 \
    LC_ALL=de_DE.UTF-8 \
    TZ=Europe/Berlin \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg locales tzdata imagemagick x11-apps \
        xvfb x11vnc fluxbox \
        python3 python3-pip python3-venv \
        novnc websockify \
        supervisor \
        fonts-liberation fonts-dejavu fonts-noto-color-emoji \
        libnss3 libxss1 libasound2 libatk-bridge2.0-0 libatk1.0-0 \
        libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libxcomposite1 \
        libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 libpango-1.0-0 \
    && sed -i '/de_DE.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# noVNC Default-Index als Symlink fuer simple URL
RUN ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html

WORKDIR /opt/browser-stack

COPY requirements.txt /opt/browser-stack/requirements.txt
RUN pip3 install --no-cache-dir -r /opt/browser-stack/requirements.txt \
    && python3 -m playwright install --with-deps chromium

# Symlink auf die playwright-Chromium-Binary, damit /usr/bin/chromium funktioniert.
# Pfad: /root/.cache/ms-playwright/chromium-<rev>/chrome-linux/chrome
RUN CHROME_BIN=$(find /root/.cache/ms-playwright -maxdepth 4 -name chrome -path '*chromium-*chrome-linux/chrome' -executable | head -1) \
    && echo "Chromium-Binary: $CHROME_BIN" \
    && ln -sf "$CHROME_BIN" /usr/bin/chromium \
    && /usr/bin/chromium --version

COPY supervisord.conf /etc/supervisor/conf.d/browser-stack.conf
COPY control_api.py /opt/browser-stack/control_api.py
COPY entrypoint.sh /opt/browser-stack/entrypoint.sh
COPY xvfb-screen.sh /opt/browser-stack/xvfb-screen.sh
RUN chmod +x /opt/browser-stack/entrypoint.sh /opt/browser-stack/xvfb-screen.sh

# 6080: noVNC WebSocket (Live-View)
# 8888: Control-API
# 9222: Chrome DevTools (intern, aber exposed fuer Cross-Container Debug)
EXPOSE 6080 8888 9222

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8888/healthz || exit 1

CMD ["/opt/browser-stack/entrypoint.sh"]
