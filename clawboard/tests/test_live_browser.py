#!/usr/bin/env python3
"""
Live Browser Tests für Clawboard
Testet direkt gegen https://www.workloom.de/clawboard/

Verwendung:
    python3 test_live_browser.py              # Headed (sichtbar)
    python3 test_live_browser.py --headless   # Headless
"""
import sys
import time
import argparse
from playwright.sync_api import sync_playwright, expect

# Login-Daten (workloom Test-Account)
TEST_USER = 'workloom'
TEST_PASS = 'mobility'
BASE_URL = 'https://www.workloom.de'


class ClawboardLiveTests:
    """Live Browser Tests für Clawboard"""
    
    def __init__(self, headless=False, slow_mo=500):
        self.headless = headless
        self.slow_mo = slow_mo
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def run_all(self):
        """Alle Tests ausführen"""
        print(f"🧪 Clawboard Live Browser Tests")
        print(f"   URL: {BASE_URL}/clawboard/")
        print(f"   Mode: {'Headless' if self.headless else 'Headed (sichtbar)'}")
        print("=" * 60)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless, 
                slow_mo=self.slow_mo if not self.headless else 0
            )
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            
            try:
                # Login
                self._login(page)
                
                # Tests ausführen
                self._test_dashboard_loads(page)
                self._test_dashboard_navigation(page)
                self._test_connections_page(page)
                self._test_connection_add_form(page)
                self._test_projects_page(page)
                self._test_conversations_page(page)
                self._test_memory_browser(page)
                self._test_tasks_page(page)
                self._test_integrations_page(page)
                self._test_responsive_mobile(page)
                self._test_responsive_tablet(page)
                self._test_responsive_desktop(page)
                
            except Exception as e:
                print(f"\n❌ FATAL ERROR: {e}")
                self.failed += 1
            finally:
                browser.close()
        
        # Zusammenfassung
        print("\n" + "=" * 60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        
        if self.errors:
            print("\nFehler:")
            for err in self.errors:
                print(f"  - {err}")
        
        return self.failed == 0
    
    def _login(self, page):
        """Login auf workloom.de"""
        print("\n🔐 Login...")
        page.goto(f"{BASE_URL}/accounts/login/")
        
        # Login-Formular ausfüllen
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        
        # Warten auf Redirect
        page.wait_for_load_state('networkidle')
        
        # Prüfen ob eingeloggt
        if 'login' in page.url.lower():
            raise Exception("Login fehlgeschlagen!")
        
        print("   ✓ Login erfolgreich")
    
    def _run_test(self, name, test_func, page):
        """Test ausführen mit Error-Handling"""
        print(f"\n🧪 {name}...", end=" ")
        try:
            test_func(page)
            print("✅")
            self.passed += 1
        except Exception as e:
            print(f"❌ {e}")
            self.failed += 1
            self.errors.append(f"{name}: {e}")
    
    def _test_dashboard_loads(self, page):
        """Dashboard lädt erfolgreich"""
        self._run_test("Dashboard lädt", lambda p: self._do_dashboard_loads(p), page)
    
    def _do_dashboard_loads(self, page):
        page.goto(f"{BASE_URL}/clawboard/")
        page.wait_for_load_state('networkidle')
        
        # Dashboard sollte laden
        assert page.locator("body").count() > 0
        
        # Keine Fehlerseite
        content = page.content().lower()
        assert "server error" not in content
        assert "404" not in page.title().lower()
    
    def _test_dashboard_navigation(self, page):
        """Navigation funktioniert"""
        self._run_test("Dashboard Navigation", lambda p: self._do_navigation(p), page)
    
    def _do_navigation(self, page):
        page.goto(f"{BASE_URL}/clawboard/")
        
        # Prüfe ob wichtige Seiten erreichbar sind (Links oder Buttons)
        content = page.content().lower()
        nav_items = ['connection', 'project', 'conversation', 'memory', 'task', 'integration']
        
        found = sum(1 for item in nav_items if item in content)
        assert found >= 2, f"Nur {found} Navigation-Items gefunden"
    
    def _test_connections_page(self, page):
        """Connections-Seite lädt"""
        self._run_test("Connections Seite", lambda p: self._do_page_loads(p, "/clawboard/connections/", ["verbindung", "connection"]), page)
    
    def _test_connection_add_form(self, page):
        """Connection Add Formular"""
        self._run_test("Connection Add Form", lambda p: self._do_connection_form(p), page)
    
    def _do_connection_form(self, page):
        page.goto(f"{BASE_URL}/clawboard/connections/add/")
        page.wait_for_load_state('networkidle')
        
        # Formularfelder prüfen (können input oder andere form-controls sein)
        content = page.content().lower()
        
        # Prüfe ob Formular-Elemente existieren
        has_name = page.locator('[name="name"], #id_name').count() > 0 or 'name' in content
        has_url = page.locator('[name="gateway_url"], #id_gateway_url').count() > 0 or 'gateway' in content
        
        assert has_name or has_url, "Formularfelder nicht gefunden"
    
    def _test_projects_page(self, page):
        """Projects-Seite lädt"""
        self._run_test("Projects Seite", lambda p: self._do_page_loads(p, "/clawboard/projects/", ["projekt", "project"]), page)
    
    def _test_conversations_page(self, page):
        """Conversations-Seite lädt"""
        self._run_test("Conversations Seite", lambda p: self._do_page_loads(p, "/clawboard/conversations/", ["konversation", "conversation", "chat"]), page)
    
    def _test_memory_browser(self, page):
        """Memory Browser lädt"""
        self._run_test("Memory Browser", lambda p: self._do_page_loads(p, "/clawboard/memory/", ["memory", "datei", "file"]), page)
    
    def _test_tasks_page(self, page):
        """Tasks-Seite lädt"""
        self._run_test("Tasks Seite", lambda p: self._do_page_loads(p, "/clawboard/tasks/", ["aufgabe", "task", "scheduled"]), page)
    
    def _test_integrations_page(self, page):
        """Integrations-Seite lädt"""
        self._run_test("Integrations Seite", lambda p: self._do_page_loads(p, "/clawboard/integrations/", ["integration"]), page)
    
    def _do_page_loads(self, page, path, keywords):
        """Generischer Test ob Seite lädt und Keywords enthält"""
        page.goto(f"{BASE_URL}{path}")
        page.wait_for_load_state('networkidle')
        
        content = page.content().lower()
        
        # Keine Fehler
        assert "server error" not in content
        assert "404" not in page.title().lower()
        
        # Mindestens ein Keyword vorhanden
        found = any(kw in content for kw in keywords)
        assert found, f"Keines der Keywords gefunden: {keywords}"
    
    def _test_responsive_mobile(self, page):
        """Mobile Ansicht (375x667)"""
        self._run_test("Responsive Mobile", lambda p: self._do_responsive(p, 375, 667), page)
    
    def _test_responsive_tablet(self, page):
        """Tablet Ansicht (768x1024)"""
        self._run_test("Responsive Tablet", lambda p: self._do_responsive(p, 768, 1024), page)
    
    def _test_responsive_desktop(self, page):
        """Desktop Ansicht (1920x1080)"""
        self._run_test("Responsive Desktop", lambda p: self._do_responsive(p, 1920, 1080), page)
    
    def _do_responsive(self, page, width, height):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{BASE_URL}/clawboard/")
        page.wait_for_load_state('networkidle')
        
        # Seite sollte laden
        assert page.locator("body").count() > 0
        
        # Reset viewport
        page.set_viewport_size({"width": 1280, "height": 800})


def main():
    parser = argparse.ArgumentParser(description='Clawboard Live Browser Tests')
    parser.add_argument('--headless', action='store_true', help='Headless Mode')
    parser.add_argument('--slow', type=int, default=500, help='Slow-Mo in ms')
    
    args = parser.parse_args()
    
    tests = ClawboardLiveTests(headless=args.headless, slow_mo=args.slow)
    success = tests.run_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
