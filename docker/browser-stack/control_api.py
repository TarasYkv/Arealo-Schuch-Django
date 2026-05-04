"""Control-API fuer den Browser-Stack-Container.

Stellt Endpoints bereit, mit denen der Workloom-Celery-Worker Browser-Sessions
steuern kann. Eine Session = ein laufender Chromium mit aktivierter Chrome
DevTools Protocol-Schnittstelle (Port 9222), den browser-use ueber CDP attachen
kann.

Ein Container haelt zur Zeit EINE Session. Wer einen zweiten parallelen Bot
will, startet einen zweiten Container auf einem anderen Host-Port-Mapping.
Das hat den Vorteil, dass die noVNC-Live-View immer eindeutig zur Session
gehoert.

Endpoints:
  GET  /healthz                     -> {ok, session_active, uptime_s}
  POST /sessions/start              -> {cdp_endpoint, novnc_path, started_at}
  POST /sessions/stop               -> {ok, ended_at}
  GET  /sessions/current            -> aktuelle Session-Info oder 204
  POST /sessions/screenshot         -> PNG-Bytes vom aktuellen Tab
"""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

logger = logging.getLogger("control_api")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

CHROMIUM_CMD = os.environ.get("CHROMIUM_CMD", "chromium")
PROFILE_DIR = Path(os.environ.get("CHROMIUM_PROFILE", "/tmp/chromium-profile"))
DEVTOOLS_PORT = int(os.environ.get("DEVTOOLS_PORT", "9222"))
START_URL = os.environ.get("START_URL", "about:blank")
DISPLAY = os.environ.get("DISPLAY", ":99")

START_TIME = time.time()


class SessionState(BaseModel):
    active: bool
    pid: Optional[int] = None
    started_at: Optional[float] = None
    cdp_endpoint: Optional[str] = None


class SessionStartRequest(BaseModel):
    """Optionale Parameter beim Start einer neuen Session."""
    start_url: Optional[str] = None
    user_agent: Optional[str] = None
    locale: Optional[str] = "de-DE"


app = FastAPI(title="Backloom Browser-Stack Control-API", version="0.1.0")
_state = SessionState(active=False)
_proc: Optional[subprocess.Popen] = None


def _build_chromium_cmd(req: SessionStartRequest) -> list[str]:
    args = [
        CHROMIUM_CMD,
        f"--remote-debugging-port={DEVTOOLS_PORT}",
        f"--remote-debugging-address=0.0.0.0",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,InfinitePrerendering",
        "--disable-blink-features=AutomationControlled",
        "--password-store=basic",
        "--use-mock-keychain",
        f"--lang={req.locale or 'de-DE'}",
        "--start-maximized",
    ]
    if req.user_agent:
        args.append(f"--user-agent={req.user_agent}")
    args.append(req.start_url or START_URL)
    return args


def _kill_existing_chromium():
    """Killt herumgeisternde Chromium-Prozesse (z.B. nach Crash)."""
    try:
        subprocess.run(["pkill", "-f", "chromium"], check=False, timeout=5)
    except Exception as exc:
        logger.warning("pkill failed: %s", exc)


@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "session_active": _state.active,
        "uptime_s": int(time.time() - START_TIME),
        "display": DISPLAY,
        "devtools_port": DEVTOOLS_PORT,
    }


@app.get("/sessions/current", response_model=SessionState)
def get_current_session():
    return _state


@app.post("/sessions/start", response_model=SessionState)
def start_session(req: SessionStartRequest = SessionStartRequest()):
    global _proc
    if _state.active:
        raise HTTPException(409, "Session laeuft bereits — vorher /sessions/stop")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Aufraeumen falls Reste vom letzten Lauf
    _kill_existing_chromium()
    time.sleep(0.5)

    cmd = _build_chromium_cmd(req)
    logger.info("Starte Chromium: %s", " ".join(shlex.quote(a) for a in cmd))
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    _proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    started_at = time.time()
    # CDP braucht ~1-2s bis es lauscht
    cdp_endpoint = f"http://localhost:{DEVTOOLS_PORT}"
    deadline = started_at + 10
    while time.time() < deadline:
        try:
            import httpx
            r = httpx.get(f"{cdp_endpoint}/json/version", timeout=1.0)
            if r.status_code == 200:
                ws_endpoint = r.json().get("webSocketDebuggerUrl", "")
                _state.active = True
                _state.pid = _proc.pid
                _state.started_at = started_at
                _state.cdp_endpoint = ws_endpoint or cdp_endpoint
                logger.info("Session live, CDP=%s", _state.cdp_endpoint)
                return _state
        except Exception:
            time.sleep(0.4)

    # Nicht hochgekommen
    with suppress(Exception):
        _proc.terminate()
    raise HTTPException(500, "Chromium ist innerhalb von 10s nicht hochgekommen")


@app.post("/sessions/stop")
def stop_session():
    global _proc
    if not _state.active:
        return {"ok": True, "note": "war nicht aktiv"}
    if _proc is not None:
        with suppress(Exception):
            os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with suppress(Exception):
                os.killpg(os.getpgid(_proc.pid), signal.SIGKILL)
        _proc = None
    _kill_existing_chromium()
    _state.active = False
    _state.pid = None
    _state.cdp_endpoint = None
    return {"ok": True, "ended_at": time.time()}


@app.post("/sessions/screenshot")
def screenshot():
    """Macht einen Vollbild-Screenshot vom Xvfb-Display und liefert PNG."""
    if not _state.active:
        raise HTTPException(412, "Keine aktive Session")
    try:
        # xwd -> ImageMagick convert; ImageMagick optional, daher fallback ueber import
        proc = subprocess.run(
            ["bash", "-c", "xwd -root -display :99 | convert xwd:- png:-"],
            capture_output=True, timeout=10,
        )
        if proc.returncode != 0:
            # Fallback: gnome-screenshot oder scrot, hier fehler durchreichen
            raise RuntimeError(proc.stderr.decode(errors="ignore"))
        return Response(content=proc.stdout, media_type="image/png")
    except Exception as exc:
        raise HTTPException(500, f"Screenshot fehlgeschlagen: {exc}")
