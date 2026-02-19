"""
Browser-Tests für die Clawboard API Endpoints
Testet AJAX/API Funktionalität
"""
import pytest
import json
from clawboard.models import ClawdbotConnection, MemoryFile


@pytest.mark.django_db(transaction=True)
class TestAPIEndpoints:
    """Tests für API Endpoints"""
    
    @pytest.fixture
    def connection(self, test_user):
        """Test-Connection"""
        return ClawdbotConnection.objects.create(
            user=test_user,
            name='API Test Connection',
            gateway_url='ws://localhost:18789',
            api_token='test-token',
            is_active=True,
            status='online'
        )
    
    def test_api_status_endpoint(self, authenticated_page, base_url, connection):
        """API Status Endpoint"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # API Request via JavaScript
        response = authenticated_page.evaluate(f"""
            async () => {{
                const response = await fetch('/clawboard/api/status/?connection={connection.pk}');
                return await response.json();
            }}
        """)
        
        assert response['success'] == True
        assert 'status' in response
    
    def test_api_sync_endpoint(self, authenticated_page, base_url, connection):
        """API Sync Endpoint"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        response = authenticated_page.evaluate(f"""
            async () => {{
                const response = await fetch('/clawboard/api/sync/?connection={connection.pk}');
                return await response.json();
            }}
        """)
        
        assert response['success'] == True
    
    def test_memory_file_view_endpoint(self, authenticated_page, base_url, connection):
        """Memory File View Endpoint"""
        # Memory File erstellen
        memory_file = MemoryFile.objects.create(
            connection=connection,
            filename='MEMORY.md',
            path='/home/test/clawd/MEMORY.md',
            content='# Test Memory Content'
        )
        
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        response = authenticated_page.evaluate(f"""
            async () => {{
                const response = await fetch('/clawboard/memory/file/?id={memory_file.pk}');
                return await response.json();
            }}
        """)
        
        assert response['success'] == True
        assert response['filename'] == 'MEMORY.md'
        assert '# Test Memory Content' in response['content']
    
    def test_memory_file_save_endpoint(self, authenticated_page, base_url, connection):
        """Memory File Save Endpoint"""
        # Memory File erstellen
        memory_file = MemoryFile.objects.create(
            connection=connection,
            filename='TEST.md',
            path='/home/test/clawd/TEST.md',
            content='Original content'
        )
        
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # CSRF Token holen
        csrf_token = authenticated_page.evaluate("""
            () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                  document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''
        """)
        
        # File speichern
        response = authenticated_page.evaluate(f"""
            async () => {{
                const response = await fetch('/clawboard/memory/file/save/', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{csrf_token}'
                    }},
                    body: JSON.stringify({{
                        id: {memory_file.pk},
                        content: 'Updated content from test'
                    }})
                }});
                return await response.json();
            }}
        """)
        
        assert response['success'] == True
        
        # Prüfen ob gespeichert
        memory_file.refresh_from_db()
        assert memory_file.content == 'Updated content from test'


@pytest.mark.django_db(transaction=True)
class TestConnectionTestAPI:
    """Tests für Connection Test API"""
    
    def test_connection_test_returns_json(self, authenticated_page, base_url, test_user):
        """Connection Test gibt JSON zurück"""
        connection = ClawdbotConnection.objects.create(
            user=test_user,
            name='Test Connection',
            gateway_url='ws://localhost:18789',
            api_token='test-token',
            is_active=True
        )
        
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        response = authenticated_page.evaluate(f"""
            async () => {{
                const response = await fetch('/clawboard/connections/{connection.pk}/test/');
                return await response.json();
            }}
        """)
        
        assert response['success'] == True
        assert 'status' in response


@pytest.mark.django_db(transaction=True)
class TestUIInteractions:
    """Tests für UI Interaktionen"""
    
    @pytest.fixture
    def connection(self, test_user):
        return ClawdbotConnection.objects.create(
            user=test_user,
            name='UI Test Connection',
            gateway_url='ws://localhost:18789',
            api_token='test-token',
            is_active=True,
            cpu_percent=45.5,
            ram_used_mb=2048,
            ram_total_mb=4096
        )
    
    def test_dashboard_status_cards_update(self, authenticated_page, base_url, connection):
        """Dashboard Status-Karten zeigen Daten"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        page_content = authenticated_page.content()
        
        # CPU oder RAM sollte angezeigt werden
        assert any([
            'CPU' in page_content,
            'RAM' in page_content,
            'Memory' in page_content,
            '45' in page_content,  # CPU Wert
        ])
    
    def test_modal_opens_and_closes(self, authenticated_page, base_url):
        """Modals öffnen und schließen"""
        authenticated_page.goto(f"{base_url}/clawboard/")
        
        # Versuche Modal zu öffnen (falls Button existiert)
        modal_trigger = authenticated_page.locator('[data-bs-toggle="modal"], [data-toggle="modal"]')
        
        if modal_trigger.count() > 0:
            modal_trigger.first.click()
            authenticated_page.wait_for_timeout(500)
            
            # Modal sollte sichtbar sein
            modal = authenticated_page.locator('.modal.show, .modal[style*="display: block"]')
            if modal.count() > 0:
                # Modal schließen
                close_btn = authenticated_page.locator('.modal .btn-close, .modal [data-bs-dismiss="modal"]')
                if close_btn.count() > 0:
                    close_btn.first.click()
    
    def test_form_validation_client_side(self, authenticated_page, base_url):
        """Client-seitige Formular-Validierung"""
        authenticated_page.goto(f"{base_url}/clawboard/connections/add/")
        
        # Leeres Formular absenden
        submit_btn = authenticated_page.locator('button[type="submit"]')
        submit_btn.click()
        
        # HTML5 Validierung sollte greifen (required fields)
        # Prüfen ob Seite nicht gewechselt hat (Validierung verhindert Submit)
        assert '/connections/add' in authenticated_page.url or 'add' in authenticated_page.url
