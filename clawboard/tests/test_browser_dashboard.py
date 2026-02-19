"""
Browser-Tests für das Clawboard Dashboard
Testet die Hauptfunktionalitäten der Clawdbot-App im Browser
"""
import pytest
from django.urls import reverse
from clawboard.models import ClawdbotConnection, Project


@pytest.mark.django_db(transaction=True)
class TestDashboard:
    """Tests für die Dashboard-Seite"""
    
    def test_dashboard_loads(self, authenticated_page, base_url):
        """Dashboard lädt erfolgreich"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # Titel prüfen
        assert "Clawboard" in authenticated_page.title() or "Dashboard" in authenticated_page.title()
        
        # Wichtige Elemente vorhanden
        assert authenticated_page.locator("text=Dashboard").count() > 0
    
    def test_dashboard_shows_empty_state(self, authenticated_page, base_url):
        """Dashboard zeigt leeren Zustand ohne Connections"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # Sollte Hinweis zeigen dass keine Verbindungen existieren
        page_content = authenticated_page.content()
        assert "Verbindung" in page_content or "Connection" in page_content
    
    def test_dashboard_navigation(self, authenticated_page, base_url):
        """Navigation funktioniert"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # Prüfe ob Nav-Links existieren
        nav_links = [
            "connections",
            "projects", 
            "conversations",
            "memory",
            "tasks",
        ]
        
        for link in nav_links:
            locator = authenticated_page.locator(f'a[href*="{link}"]')
            assert locator.count() > 0, f"Navigation link for {link} missing"


@pytest.mark.django_db(transaction=True)
class TestConnectionManagement:
    """Tests für Connection-Verwaltung"""
    
    def test_connection_list_page_loads(self, authenticated_page, base_url):
        """Connection-Liste lädt"""
        authenticated_page.goto(f"{base_url}/clawboard/connections/")
        assert authenticated_page.locator("text=Verbindung").count() > 0
    
    def test_add_connection_form(self, authenticated_page, base_url):
        """Formular zum Hinzufügen einer Verbindung"""
        authenticated_page.goto(f"{base_url}/clawboard/connections/add/")
        
        # Formularfelder prüfen
        assert authenticated_page.locator('input[name="name"]').count() > 0
        assert authenticated_page.locator('input[name="gateway_url"]').count() > 0
        assert authenticated_page.locator('input[name="api_token"]').count() > 0
    
    def test_create_connection(self, authenticated_page, base_url, test_user):
        """Verbindung erstellen"""
        authenticated_page.goto(f"{base_url}/clawboard/connections/add/")
        
        # Formular ausfüllen
        authenticated_page.fill('input[name="name"]', 'Test Connection')
        authenticated_page.fill('input[name="gateway_url"]', 'ws://localhost:18789')
        authenticated_page.fill('input[name="api_token"]', 'test-token-123')
        
        # Absenden
        authenticated_page.click('button[type="submit"]')
        authenticated_page.wait_for_load_state('networkidle')
        
        # Prüfen ob erstellt
        assert ClawdbotConnection.objects.filter(name='Test Connection').exists()
    
    def test_connection_test_button(self, authenticated_page, base_url, test_user):
        """Verbindung testen Button"""
        # Erst Connection erstellen
        connection = ClawdbotConnection.objects.create(
            user=test_user,
            name='Test Connection',
            gateway_url='ws://localhost:18789',
            api_token='test-token',
            is_active=True
        )
        
        authenticated_page.goto(f"{base_url}/clawboard/connections/{connection.pk}/")
        
        # Test-Button finden und klicken
        test_button = authenticated_page.locator('button:has-text("Test")')
        if test_button.count() > 0:
            test_button.click()
            authenticated_page.wait_for_timeout(1000)
    
    def test_delete_connection(self, authenticated_page, base_url, test_user):
        """Verbindung löschen"""
        # Connection erstellen
        connection = ClawdbotConnection.objects.create(
            user=test_user,
            name='To Delete',
            gateway_url='ws://localhost:18789',
            api_token='test-token',
            is_active=True
        )
        
        authenticated_page.goto(f"{base_url}/clawboard/connections/{connection.pk}/delete/")
        
        # Löschen bestätigen
        authenticated_page.click('button[type="submit"]')
        authenticated_page.wait_for_load_state('networkidle')
        
        # Prüfen ob gelöscht
        assert not ClawdbotConnection.objects.filter(pk=connection.pk).exists()


@pytest.mark.django_db(transaction=True)
class TestProjectManagement:
    """Tests für Projekt-Verwaltung"""
    
    @pytest.fixture
    def connection(self, test_user):
        """Test-Connection für Projekte"""
        return ClawdbotConnection.objects.create(
            user=test_user,
            name='Test Connection',
            gateway_url='ws://localhost:18789',
            api_token='test-token',
            is_active=True
        )
    
    def test_project_list_page_loads(self, authenticated_page, base_url):
        """Projekt-Liste lädt"""
        authenticated_page.goto(f"{base_url}/clawboard/projects/")
        assert authenticated_page.locator("text=Projekt").count() > 0
    
    def test_add_project_form(self, authenticated_page, base_url, connection):
        """Formular zum Erstellen eines Projekts"""
        authenticated_page.goto(f"{base_url}/clawboard/projects/add/")
        
        # Formularfelder prüfen
        assert authenticated_page.locator('input[name="name"]').count() > 0
        assert authenticated_page.locator('select[name="connection"]').count() > 0
    
    def test_create_project(self, authenticated_page, base_url, connection):
        """Projekt erstellen"""
        authenticated_page.goto(f"{base_url}/clawboard/projects/add/")
        
        # Formular ausfüllen
        authenticated_page.fill('input[name="name"]', 'Test Project')
        authenticated_page.select_option('select[name="connection"]', str(connection.pk))
        
        # Optional: Beschreibung
        desc_field = authenticated_page.locator('textarea[name="description"]')
        if desc_field.count() > 0:
            desc_field.fill('Test project description')
        
        # Absenden
        authenticated_page.click('button[type="submit"]')
        authenticated_page.wait_for_load_state('networkidle')
        
        # Prüfen ob erstellt
        assert Project.objects.filter(name='Test Project').exists()
    
    def test_project_detail_page(self, authenticated_page, base_url, connection):
        """Projekt-Detailseite"""
        project = Project.objects.create(
            connection=connection,
            name='Detail Test Project',
            workspace_path='/test/path'
        )
        
        authenticated_page.goto(f"{base_url}/clawboard/projects/{project.pk}/")
        
        assert "Detail Test Project" in authenticated_page.content()


@pytest.mark.django_db(transaction=True)
class TestMemoryBrowser:
    """Tests für den Memory Browser"""
    
    def test_memory_browser_loads(self, authenticated_page, base_url):
        """Memory Browser lädt"""
        authenticated_page.goto(f"{base_url}/clawboard/memory/")
        
        page_content = authenticated_page.content()
        assert "Memory" in page_content or "Dateien" in page_content


@pytest.mark.django_db(transaction=True)
class TestScheduledTasks:
    """Tests für geplante Aufgaben"""
    
    def test_task_list_loads(self, authenticated_page, base_url):
        """Task-Liste lädt"""
        authenticated_page.goto(f"{base_url}/clawboard/tasks/")
        
        page_content = authenticated_page.content()
        assert "Aufgabe" in page_content or "Task" in page_content


@pytest.mark.django_db(transaction=True)
class TestIntegrations:
    """Tests für Integrationen"""
    
    def test_integrations_list_loads(self, authenticated_page, base_url):
        """Integrations-Liste lädt"""
        authenticated_page.goto(f"{base_url}/clawboard/integrations/")
        
        page_content = authenticated_page.content()
        assert "Integration" in page_content


@pytest.mark.django_db(transaction=True)
class TestResponsiveDesign:
    """Tests für responsive Design"""
    
    def test_mobile_viewport(self, authenticated_page, base_url):
        """Mobile Ansicht funktioniert"""
        # Mobile viewport setzen
        authenticated_page.set_viewport_size({"width": 375, "height": 667})
        
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # Seite sollte laden ohne Fehler
        assert authenticated_page.locator("body").count() > 0
    
    def test_tablet_viewport(self, authenticated_page, base_url):
        """Tablet Ansicht funktioniert"""
        authenticated_page.set_viewport_size({"width": 768, "height": 1024})
        
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        assert authenticated_page.locator("body").count() > 0
    
    def test_desktop_viewport(self, authenticated_page, base_url):
        """Desktop Ansicht funktioniert"""
        authenticated_page.set_viewport_size({"width": 1920, "height": 1080})
        
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        assert authenticated_page.locator("body").count() > 0
