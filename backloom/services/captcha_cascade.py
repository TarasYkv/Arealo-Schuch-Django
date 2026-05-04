"""Captcha-Loesungs-Cascade.

Stuft Captcha-Loeser nach Kosten + Zuverlaessigkeit ab. Wenn ein Solver
fehlschlaegt, faellt die Cascade auf den naechsten zurueck. Letzter Fallback:
Manual (gibt Marker zurueck — der Bot pausiert und benachrichtigt User).

Stufen:
1. FlareSolverr  — Cloudflare-Challenges, kostenlos (Docker auf Localhost)
2. CapSolver     — reCAPTCHA v2/v3, hCaptcha, Turnstile, ~0,002 €/Loesung
3. 2Captcha      — Backup wenn CapSolver versagt, ~0,001 €
4. Manual        — Pausiere, sende Telegram-Ping mit Live-View-URL

Aufgerufen wird der Cascade-Service vom BotRunner WENN der browser-use-Agent
einen Captcha-Marker meldet. Der Agent selbst soll Captchas NICHT zu loesen
versuchen — der Cascade uebernimmt.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CaptchaKind(str, Enum):
    NONE = 'none'
    RECAPTCHA_V2 = 'recaptcha_v2'
    RECAPTCHA_V3 = 'recaptcha_v3'
    HCAPTCHA = 'hcaptcha'
    TURNSTILE = 'turnstile'           # Cloudflare Turnstile
    CLOUDFLARE = 'cloudflare'         # Cloudflare Challenge (5s+JS)
    CUSTOM = 'custom'
    UNKNOWN = 'unknown'


@dataclass
class CaptchaContext:
    """Was der BotRunner / browser-use ermittelt hat und an den Cascade gibt."""
    kind: CaptchaKind
    page_url: str
    site_key: str = ''                # widget-data-sitekey, oder reCAPTCHA-Key
    enterprise: bool = False
    invisible: bool = False
    # Optional: Cookies oder Headers fuer FlareSolverr-Bypass-Result
    extra: dict | None = None


@dataclass
class CaptchaSolution:
    """Resultat eines Solvers — alles was der Bot zum Einfuegen braucht."""
    success: bool
    token: str = ''
    cookies: list | None = None
    user_agent: str = ''
    solver_used: str = ''
    cost_eur: Decimal = Decimal('0')
    error: str = ''
    needs_manual: bool = False


# ---------------------------------------------------------------------------
# Solver-Implementations
# ---------------------------------------------------------------------------


FLARESOLVERR_URL = 'http://localhost:8191/v1'
CAPSOLVER_URL = 'https://api.capsolver.com'
TWOCAPTCHA_URL_BASE = 'https://2captcha.com'

# Pricing (Stand Mai 2026, ungefaehr)
COST_CAPSOLVER = {
    CaptchaKind.RECAPTCHA_V2: Decimal('0.0009'),
    CaptchaKind.RECAPTCHA_V3: Decimal('0.0024'),
    CaptchaKind.HCAPTCHA:     Decimal('0.0019'),
    CaptchaKind.TURNSTILE:    Decimal('0.0014'),
}
COST_TWOCAPTCHA = {
    CaptchaKind.RECAPTCHA_V2: Decimal('0.0010'),
    CaptchaKind.RECAPTCHA_V3: Decimal('0.0020'),
    CaptchaKind.HCAPTCHA:     Decimal('0.0019'),
    CaptchaKind.TURNSTILE:    Decimal('0.0017'),
}


def solve_with_flaresolverr(ctx: CaptchaContext, timeout_s: int = 60) -> CaptchaSolution:
    """Versucht Cloudflare-Challenge ueber lokalen FlareSolverr-Container."""
    if ctx.kind not in (CaptchaKind.CLOUDFLARE, CaptchaKind.TURNSTILE, CaptchaKind.UNKNOWN):
        return CaptchaSolution(success=False, error='Wrong type for FlareSolverr')

    payload = {
        'cmd': 'request.get',
        'url': ctx.page_url,
        'maxTimeout': timeout_s * 1000,
    }
    try:
        r = httpx.post(FLARESOLVERR_URL, json=payload, timeout=timeout_s + 5)
        if r.status_code != 200:
            return CaptchaSolution(success=False,
                                    error=f'FlareSolverr HTTP {r.status_code}: {r.text[:120]}',
                                    solver_used='flaresolverr')
        data = r.json()
        sol = data.get('solution', {})
        if data.get('status') == 'ok' and sol.get('cookies'):
            return CaptchaSolution(
                success=True,
                cookies=sol.get('cookies'),
                user_agent=sol.get('userAgent', ''),
                solver_used='flaresolverr',
            )
        return CaptchaSolution(
            success=False,
            error=f'FlareSolverr nicht ok: {data.get("status")}',
            solver_used='flaresolverr',
        )
    except Exception as exc:
        logger.exception('FlareSolverr-Fehler')
        return CaptchaSolution(success=False, error=str(exc), solver_used='flaresolverr')


def solve_with_capsolver(ctx: CaptchaContext, api_key: str,
                         poll_interval_s: float = 3.0,
                         max_wait_s: int = 120) -> CaptchaSolution:
    """Loest mit CapSolver. Unterstuetzt reCAPTCHA v2/v3, hCaptcha, Turnstile."""
    if not api_key:
        return CaptchaSolution(success=False, error='Kein CapSolver API-Key',
                                solver_used='capsolver', needs_manual=False)

    task_type = _capsolver_task_type(ctx)
    if not task_type:
        return CaptchaSolution(success=False,
                                error=f'CapSolver unterstuetzt {ctx.kind} nicht direkt',
                                solver_used='capsolver')

    task_payload: dict = {
        'type': task_type,
        'websiteURL': ctx.page_url,
        'websiteKey': ctx.site_key,
    }
    if ctx.enterprise and 'ReCaptcha' in task_type:
        task_payload['type'] = task_type.replace('TaskProxyLess', 'EnterpriseTaskProxyLess')
    if ctx.invisible and ctx.kind == CaptchaKind.RECAPTCHA_V2:
        task_payload['isInvisible'] = True

    try:
        r = httpx.post(f'{CAPSOLVER_URL}/createTask', json={
            'clientKey': api_key,
            'task': task_payload,
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get('errorId', 0) != 0:
            return CaptchaSolution(success=False,
                                    error=f'CapSolver: {body.get("errorDescription")}',
                                    solver_used='capsolver')
        task_id = body['taskId']
    except Exception as exc:
        return CaptchaSolution(success=False, error=str(exc), solver_used='capsolver')

    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        try:
            r = httpx.post(f'{CAPSOLVER_URL}/getTaskResult', json={
                'clientKey': api_key, 'taskId': task_id,
            }, timeout=15)
            body = r.json()
            if body.get('status') == 'ready':
                token = (body.get('solution') or {}).get('gRecaptchaResponse') or \
                        (body.get('solution') or {}).get('token') or ''
                return CaptchaSolution(
                    success=bool(token),
                    token=token,
                    solver_used='capsolver',
                    cost_eur=COST_CAPSOLVER.get(ctx.kind, Decimal('0.002')),
                )
            if body.get('errorId', 0) != 0:
                return CaptchaSolution(success=False,
                                        error=f'CapSolver: {body.get("errorDescription")}',
                                        solver_used='capsolver')
        except Exception as exc:
            logger.warning('CapSolver poll fehlgeschlagen: %s', exc)
        time.sleep(poll_interval_s)

    return CaptchaSolution(success=False,
                            error=f'CapSolver Timeout nach {max_wait_s}s',
                            solver_used='capsolver')


def solve_with_2captcha(ctx: CaptchaContext, api_key: str,
                        poll_interval_s: float = 5.0,
                        max_wait_s: int = 180) -> CaptchaSolution:
    """Loest mit 2Captcha. Aehnliche Typ-Abdeckung wie CapSolver."""
    if not api_key:
        return CaptchaSolution(success=False, error='Kein 2Captcha API-Key',
                                solver_used='2captcha')

    method = _twocaptcha_method(ctx)
    if not method:
        return CaptchaSolution(success=False,
                                error=f'2Captcha unterstuetzt {ctx.kind} nicht direkt',
                                solver_used='2captcha')

    params = {
        'key': api_key,
        'method': method,
        'sitekey': ctx.site_key,
        'pageurl': ctx.page_url,
        'json': 1,
    }
    if ctx.invisible and ctx.kind == CaptchaKind.RECAPTCHA_V2:
        params['invisible'] = 1
    if ctx.kind == CaptchaKind.RECAPTCHA_V3:
        params['version'] = 'v3'
    if ctx.enterprise:
        params['enterprise'] = 1

    try:
        r = httpx.post(f'{TWOCAPTCHA_URL_BASE}/in.php', params=params, timeout=20)
        body = r.json()
        if body.get('status') != 1:
            return CaptchaSolution(success=False,
                                    error=f'2Captcha in.php: {body.get("request")}',
                                    solver_used='2captcha')
        captcha_id = body['request']
    except Exception as exc:
        return CaptchaSolution(success=False, error=str(exc), solver_used='2captcha')

    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        time.sleep(poll_interval_s)
        try:
            r = httpx.get(f'{TWOCAPTCHA_URL_BASE}/res.php', params={
                'key': api_key, 'action': 'get', 'id': captcha_id, 'json': 1,
            }, timeout=15)
            body = r.json()
            if body.get('status') == 1:
                return CaptchaSolution(
                    success=True,
                    token=body.get('request', ''),
                    solver_used='2captcha',
                    cost_eur=COST_TWOCAPTCHA.get(ctx.kind, Decimal('0.002')),
                )
            if body.get('request') == 'CAPCHA_NOT_READY':
                continue
            return CaptchaSolution(success=False,
                                    error=f'2Captcha: {body.get("request")}',
                                    solver_used='2captcha')
        except Exception as exc:
            logger.warning('2Captcha poll fehlgeschlagen: %s', exc)

    return CaptchaSolution(success=False,
                            error=f'2Captcha Timeout nach {max_wait_s}s',
                            solver_used='2captcha')


# ---------------------------------------------------------------------------
# Cascade-Orchestrator
# ---------------------------------------------------------------------------


class CaptchaCascade:
    """Orchestrator. Probiert Solver der Reihe nach durch.

    Aufruf:
        cascade = CaptchaCascade(capsolver_key=..., twocaptcha_key=...)
        solution = cascade.solve(ctx)
        if solution.success:
            # token in Page injizieren
        elif solution.needs_manual:
            # Telegram-Ping, Browser pausieren
    """

    def __init__(self, capsolver_key: str = '', twocaptcha_key: str = ''):
        self.capsolver_key = capsolver_key
        self.twocaptcha_key = twocaptcha_key

    def solve(self, ctx: CaptchaContext) -> CaptchaSolution:
        # Stufe 1: FlareSolverr fuer Cloudflare
        if ctx.kind in (CaptchaKind.CLOUDFLARE, CaptchaKind.TURNSTILE):
            sol = solve_with_flaresolverr(ctx)
            if sol.success:
                logger.info('Captcha geloest via FlareSolverr')
                return sol
            logger.info('FlareSolverr-Fail (%s) — Cascade fortsetzen', sol.error)

        # Stufe 2: CapSolver
        if self.capsolver_key:
            sol = solve_with_capsolver(ctx, self.capsolver_key)
            if sol.success:
                logger.info('Captcha geloest via CapSolver (%s €)', sol.cost_eur)
                return sol
            logger.info('CapSolver-Fail (%s) — Cascade fortsetzen', sol.error)

        # Stufe 3: 2Captcha
        if self.twocaptcha_key:
            sol = solve_with_2captcha(ctx, self.twocaptcha_key)
            if sol.success:
                logger.info('Captcha geloest via 2Captcha (%s €)', sol.cost_eur)
                return sol
            logger.info('2Captcha-Fail (%s) — Cascade gibt auf', sol.error)

        # Stufe 4: Manual-Fallback
        return CaptchaSolution(
            success=False,
            needs_manual=True,
            solver_used='manual',
            error='Alle Auto-Solver versagt — Mensch uebernehmen',
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _capsolver_task_type(ctx: CaptchaContext) -> str:
    """Mappt CaptchaKind auf CapSolver task type."""
    return {
        CaptchaKind.RECAPTCHA_V2: 'ReCaptchaV2TaskProxyLess',
        CaptchaKind.RECAPTCHA_V3: 'ReCaptchaV3TaskProxyLess',
        CaptchaKind.HCAPTCHA:     'HCaptchaTaskProxyLess',
        CaptchaKind.TURNSTILE:    'AntiTurnstileTaskProxyLess',
    }.get(ctx.kind, '')


def _twocaptcha_method(ctx: CaptchaContext) -> str:
    """Mappt CaptchaKind auf 2Captcha method."""
    return {
        CaptchaKind.RECAPTCHA_V2: 'userrecaptcha',
        CaptchaKind.RECAPTCHA_V3: 'userrecaptcha',
        CaptchaKind.HCAPTCHA:     'hcaptcha',
        CaptchaKind.TURNSTILE:    'turnstile',
    }.get(ctx.kind, '')
