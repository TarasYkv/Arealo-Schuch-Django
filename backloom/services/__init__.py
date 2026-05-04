"""Backloom-Services-Paket.

Vorher gab es eine flache services.py — jetzt ein Paket. Damit bestehende
Imports (`from backloom.services import run_backlink_search, ...`) weiter
funktionieren, re-exportieren wir alle relevanten Symbole aus dem
ehemaligen services.py (jetzt _legacy.py).

Neue Submission-Pipeline-Services liegen in eigenen Modulen:
- bot_runner.BotRunner
- browser_client.BrowserContainerClient
"""
from ._legacy import (  # noqa: F401
    sanitize_for_mysql,
    SourceHealthCheck,
    BacklinkScraper,
    run_backlink_search,
    cleanup_old_sources,
    initialize_default_queries,
)

# Neue Submission-Services explizit verfuegbar machen
from .bot_runner import BotRunner  # noqa: F401
from .browser_client import BrowserContainerClient, BrowserContainerError  # noqa: F401
from .captcha_cascade import (  # noqa: F401
    CaptchaCascade, CaptchaContext, CaptchaSolution, CaptchaKind,
)
