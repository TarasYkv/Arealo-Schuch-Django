"""
Test-Suite für LoomLine Timeline-System
TDD-basierte Tests für alle Funktionalitäten
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
from loomline.models import Project, TaskEntry

User = get_user_model()


class BaseTestCase(TestCase):
    """Basis-Testklasse mit gemeinsamen Setup-Methoden"""

    def setUp(self):
        """Setup für jeden Test"""
        self.client = Client()

        # Testbenutzer erstellen
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )

        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )

        # Testprojekt erstellen
        self.project = Project.objects.create(
            name='Test Projekt',
            description='Test Beschreibung',
            owner=self.user1
        )

        # Hauptaufgabe erstellen
        self.main_task = TaskEntry.objects.create(
            project=self.project,
            title='Hauptaufgabe Test',
            description='Beschreibung der Hauptaufgabe',
            completed_by=self.user1,
            completed_at=timezone.now()
        )

        # Sub-Aufgabe erstellen
        self.subtask = TaskEntry.objects.create(
            project=self.project,
            title='Sub-Aufgabe Test',
            description='Beschreibung der Sub-Aufgabe',
            completed_by=self.user1,
            parent_task=self.main_task,
            completed_at=timezone.now()
        )


class TaskTilesViewTest(BaseTestCase):
    """Tests für die Kachelansicht"""

    def test_tiles_view_requires_login(self):
        """Test: Kachelansicht erfordert Anmeldung"""
        response = self.client.get(reverse('loomline:tasks-tiles'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_tiles_view_shows_main_tasks_only(self):
        """Test: Kachelansicht zeigt nur Hauptaufgaben"""
        self.client.login(username='testuser1', password='testpass123')
        response = self.client.get(reverse('loomline:tasks-tiles'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hauptaufgabe Test')
        self.assertIn('tasks', response.context)

        # Prüfe, dass nur Hauptaufgaben in der Liste sind
        tasks = response.context['tasks']
        for task in tasks:
            self.assertIsNone(task.parent_task)

    def test_tiles_view_shows_subtasks_with_main_task(self):
        """Test: Sub-Aufgaben werden mit Hauptaufgabe angezeigt"""
        self.client.login(username='testuser1', password='testpass123')
        response = self.client.get(reverse('loomline:tasks-tiles'))

        self.assertEqual(response.status_code, 200)
        # Sub-Aufgabe sollte im HTML enthalten sein
        self.assertContains(response, 'Sub-Aufgabe Test')


class EditTaskTest(BaseTestCase):
    """Tests für die Edit-Funktionalität"""

    def test_edit_task_requires_login(self):
        """Test: Bearbeiten erfordert Anmeldung"""
        response = self.client.post(
            reverse('loomline:edit-task', kwargs={'task_id': self.main_task.id})
        )
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_edit_task_success_json(self):
        """Test: Erfolgreiche Bearbeitung via JSON"""
        self.client.login(username='testuser1', password='testpass123')

        new_data = {
            'title': 'Aktualisierte Hauptaufgabe',
            'description': 'Neue Beschreibung'
        }

        response = self.client.post(
            reverse('loomline:edit-task', kwargs={'task_id': self.main_task.id}),
            data=json.dumps(new_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

        # Prüfe, dass Änderungen gespeichert wurden
        self.main_task.refresh_from_db()
        self.assertEqual(self.main_task.title, 'Aktualisierte Hauptaufgabe')
        self.assertEqual(self.main_task.description, 'Neue Beschreibung')

    def test_edit_task_unauthorized(self):
        """Test: Bearbeitung verweigert für nicht berechtigten Benutzer"""
        self.client.login(username='testuser2', password='testpass123')

        response = self.client.post(
            reverse('loomline:edit-task', kwargs={'task_id': self.main_task.id}),
            data=json.dumps({'title': 'Hacker Versuch'}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 302)  # Redirect

    def test_edit_subtask_not_allowed(self):
        """Test: Sub-Aufgaben können nicht über edit-task bearbeitet werden"""
        self.client.login(username='testuser1', password='testpass123')

        response = self.client.post(
            reverse('loomline:edit-task', kwargs={'task_id': self.subtask.id}),
            data=json.dumps({'title': 'Versuch Sub-Task zu editieren'}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 404)  # Not found


class DeleteTaskTest(BaseTestCase):
    """Tests für die Delete-Funktionalität"""

    def test_delete_main_task_success(self):
        """Test: Hauptaufgabe erfolgreich löschen"""
        self.client.login(username='testuser1', password='testpass123')

        task_id = self.main_task.id
        response = self.client.post(
            reverse('loomline:delete-task', kwargs={'task_id': task_id})
        )

        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertFalse(TaskEntry.objects.filter(id=task_id).exists())

    def test_delete_main_task_deletes_subtasks(self):
        """Test: Löschen der Hauptaufgabe löscht auch Sub-Aufgaben"""
        self.client.login(username='testuser1', password='testpass123')

        main_id = self.main_task.id
        sub_id = self.subtask.id

        response = self.client.post(
            reverse('loomline:delete-task', kwargs={'task_id': main_id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskEntry.objects.filter(id=main_id).exists())
        self.assertFalse(TaskEntry.objects.filter(id=sub_id).exists())

    def test_delete_subtask_success(self):
        """Test: Sub-Aufgabe erfolgreich löschen"""
        self.client.login(username='testuser1', password='testpass123')

        sub_id = self.subtask.id
        response = self.client.post(
            reverse('loomline:delete-subtask', kwargs={'subtask_id': sub_id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskEntry.objects.filter(id=sub_id).exists())
        # Hauptaufgabe sollte noch existieren
        self.assertTrue(TaskEntry.objects.filter(id=self.main_task.id).exists())

    def test_delete_task_unauthorized(self):
        """Test: Löschen verweigert für nicht berechtigten Benutzer"""
        self.client.login(username='testuser2', password='testpass123')

        response = self.client.post(
            reverse('loomline:delete-task', kwargs={'task_id': self.main_task.id})
        )

        self.assertEqual(response.status_code, 302)
        # Task sollte noch existieren
        self.assertTrue(TaskEntry.objects.filter(id=self.main_task.id).exists())


class AddSubtaskTest(BaseTestCase):
    """Tests für das Hinzufügen von Sub-Aufgaben"""

    def test_add_subtask_success(self):
        """Test: Sub-Aufgabe erfolgreich hinzufügen"""
        self.client.login(username='testuser1', password='testpass123')

        data = {
            'parent_task_id': self.main_task.id,
            'title': 'Neue Sub-Aufgabe',
            'description': 'Beschreibung der neuen Sub-Aufgabe'
        }

        response = self.client.post(reverse('loomline:add-subtask'), data=data)

        self.assertEqual(response.status_code, 302)

        # Prüfe, dass Sub-Aufgabe erstellt wurde
        new_subtask = TaskEntry.objects.filter(
            parent_task=self.main_task,
            title='Neue Sub-Aufgabe'
        ).first()

        self.assertIsNotNone(new_subtask)
        self.assertEqual(new_subtask.project, self.project)
        self.assertEqual(new_subtask.completed_by, self.user1)

    def test_add_subtask_without_title_fails(self):
        """Test: Sub-Aufgabe ohne Titel schlägt fehl"""
        self.client.login(username='testuser1', password='testpass123')

        data = {
            'parent_task_id': self.main_task.id,
            'title': '',  # Leerer Titel
            'description': 'Beschreibung'
        }

        response = self.client.post(reverse('loomline:add-subtask'), data=data)

        self.assertEqual(response.status_code, 302)

        # Keine neue Sub-Aufgabe sollte erstellt worden sein
        subtask_count = TaskEntry.objects.filter(parent_task=self.main_task).count()
        self.assertEqual(subtask_count, 1)  # Nur die ursprüngliche Sub-Aufgabe

    def test_add_subtask_to_nonexistent_task_fails(self):
        """Test: Sub-Aufgabe zu nicht existierender Aufgabe schlägt fehl"""
        self.client.login(username='testuser1', password='testpass123')

        data = {
            'parent_task_id': 99999,  # Nicht existierende ID
            'title': 'Neue Sub-Aufgabe',
            'description': 'Beschreibung'
        }

        response = self.client.post(reverse('loomline:add-subtask'), data=data)

        self.assertEqual(response.status_code, 404)


class ProjectAccessTest(BaseTestCase):
    """Tests für Projekt-Zugriffskontrolle"""

    def test_project_member_can_access_tasks(self):
        """Test: Projekt-Mitglied kann Aufgaben sehen"""
        # User2 als Mitglied hinzufügen
        self.project.members.add(self.user2)

        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get(reverse('loomline:tasks-tiles'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hauptaufgabe Test')

    def test_non_member_cannot_see_tasks(self):
        """Test: Nicht-Mitglied kann Aufgaben nicht sehen"""
        # Erstelle Projekt ohne user2 als Mitglied
        other_project = Project.objects.create(
            name='Privates Projekt',
            owner=self.user1
        )

        other_task = TaskEntry.objects.create(
            project=other_project,
            title='Private Aufgabe',
            completed_by=self.user1
        )

        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get(reverse('loomline:tasks-tiles'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Private Aufgabe')


class FilterTest(BaseTestCase):
    """Tests für die Filter-Funktionalität"""

    def test_project_filter(self):
        """Test: Projekt-Filter funktioniert"""
        # Zweites Projekt erstellen
        project2 = Project.objects.create(
            name='Anderes Projekt',
            owner=self.user1
        )

        task2 = TaskEntry.objects.create(
            project=project2,
            title='Aufgabe in anderem Projekt',
            completed_by=self.user1
        )

        self.client.login(username='testuser1', password='testpass123')

        # Filter nach erstem Projekt
        response = self.client.get(
            reverse('loomline:tasks-tiles'),
            {'project': self.project.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hauptaufgabe Test')
        self.assertNotContains(response, 'Aufgabe in anderem Projekt')

    def test_timeframe_filter_today(self):
        """Test: Zeitraum-Filter 'heute' funktioniert"""
        # Alte Aufgabe erstellen
        old_task = TaskEntry.objects.create(
            project=self.project,
            title='Alte Aufgabe',
            completed_by=self.user1,
            completed_at=timezone.now() - timedelta(days=7)
        )

        self.client.login(username='testuser1', password='testpass123')

        response = self.client.get(
            reverse('loomline:tasks-tiles'),
            {'timeframe': 'today'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hauptaufgabe Test')
        self.assertNotContains(response, 'Alte Aufgabe')

    def test_user_filter(self):
        """Test: Benutzer-Filter funktioniert"""
        # Aufgabe von anderem Benutzer
        self.project.members.add(self.user2)

        task_by_user2 = TaskEntry.objects.create(
            project=self.project,
            title='Aufgabe von User2',
            completed_by=self.user2
        )

        self.client.login(username='testuser1', password='testpass123')

        response = self.client.get(
            reverse('loomline:tasks-tiles'),
            {'user': self.user1.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hauptaufgabe Test')
        self.assertNotContains(response, 'Aufgabe von User2')