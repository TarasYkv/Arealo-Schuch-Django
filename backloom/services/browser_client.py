"""HTTP-Client fuer den Browser-Stack-Container (Control-API).

Worker, der auf demselben Hetzner-Host laeuft, ruft die Control-API auf
127.0.0.1:8888 — der Container exposed sie nur lokal (sicher).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

CONTROL_API_BASE = "http://127.0.0.1:8888"
NOVNC_PUBLIC_BASE = "https://workloom.de/backloom/browser/vnc.html"


class BrowserContainerError(RuntimeError):
    pass


class BrowserContainerClient:
    """Duenne HTTP-Wrapper-Klasse — kapselt URL-Conventions und Timeouts."""

    def __init__(self, base_url: str = CONTROL_API_BASE, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---- Lifecycle ----------------------------------------------------------

    def healthz(self) -> dict:
        r = httpx.get(f"{self.base_url}/healthz", timeout=5.0)
        r.raise_for_status()
        return r.json()

    def start_session(self, start_url: str = "about:blank",
                      user_agent: Optional[str] = None,
                      locale: str = "de-DE") -> dict:
        """Spawnt eine neue Chromium-Session. Liefert {active, pid, started_at, cdp_endpoint}."""
        payload: dict[str, Any] = {"start_url": start_url, "locale": locale}
        if user_agent:
            payload["user_agent"] = user_agent
        r = httpx.post(f"{self.base_url}/sessions/start",
                       json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise BrowserContainerError(
                f"start_session failed [{r.status_code}]: {r.text[:200]}"
            )
        return r.json()

    def stop_session(self) -> dict:
        r = httpx.post(f"{self.base_url}/sessions/stop", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def current_session(self) -> dict:
        r = httpx.get(f"{self.base_url}/sessions/current", timeout=5.0)
        r.raise_for_status()
        return r.json()

    def screenshot(self) -> bytes:
        r = httpx.post(f"{self.base_url}/sessions/screenshot", timeout=self.timeout)
        if r.status_code != 200:
            raise BrowserContainerError(
                f"screenshot failed [{r.status_code}]: {r.text[:200]}"
            )
        return r.content

    @staticmethod
    def public_novnc_url() -> str:
        """URL die der User im Workloom-Frontend in einem iframe oeffnet."""
        return NOVNC_PUBLIC_BASE
