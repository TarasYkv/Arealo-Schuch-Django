"""
Pytest fixtures für Clawboard Browser-Tests
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from playwright.sync_api import sync_playwright, Browser, Page

User = get_user_model()


@pytest.fixture(scope="session")
def browser():
    """Playwright Browser (wiederverwendbar für alle Tests)"""
    with sync_playwright() as p:
        # Headed mode für sichtbare Tests
        browser = p.chromium.launch(headless=False, slow_mo=500)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def browser_headless():
    """Headless Browser für CI/CD"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Neue Browser-Seite pro Test"""
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture
def page_headless(browser_headless):
    """Headless Seite für CI/CD"""
    page = browser_headless.new_page()
    yield page
    page.close()


@pytest.fixture
def test_user(db):
    """Test-Benutzer erstellen"""
    user = User.objects.create_user(
        username='testuser',
        email='test@workloom.de',
        password='testpass123'
    )
    return user


@pytest.fixture
def authenticated_page(page, test_user, live_server):
    """Seite mit eingeloggtem Benutzer"""
    # Login-Seite aufrufen
    page.goto(f"{live_server.url}/accounts/login/")
    
    # Einloggen
    page.fill('input[name="username"]', 'testuser')
    page.fill('input[name="password"]', 'testpass123')
    page.click('button[type="submit"]')
    
    # Warten bis Login abgeschlossen
    page.wait_for_load_state('networkidle')
    
    return page


@pytest.fixture
def base_url(live_server):
    """Basis-URL für Tests"""
    return live_server.url
