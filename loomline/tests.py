"""
Comprehensive Test Suite for LoomLine App (SEO Task Timeline)
Test-Driven Development implementation following Django best practices
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import datetime, timedelta
import json

User = get_user_model()


class ProjectModelTest(TestCase):
    """Test suite for Project model - TDD approach"""

    def setUp(self):
        """Set up test data"""
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

    def test_project_creation_with_valid_data(self):
        """Test creating a project with valid data"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test SEO Project",
            description="Test project for SEO tracking",
            owner=self.user1,
            domain="example.com"
        )

        self.assertEqual(project.name, "Test SEO Project")
        self.assertEqual(project.owner, self.user1)
        self.assertEqual(project.domain, "example.com")
        self.assertTrue(project.is_active)
        self.assertIsNotNone(project.created_at)
        self.assertIsNotNone(project.updated_at)

    def test_project_name_required(self):
        """Test that project name is required"""
        from loomline.models import Project

        with self.assertRaises(ValidationError):
            project = Project(
                description="Test project",
                owner=self.user1
            )
            project.full_clean()

    def test_project_owner_required(self):
        """Test that project owner is required"""
        from loomline.models import Project

        with self.assertRaises(ValidationError):
            project = Project(
                name="Test Project",
                description="Test project"
            )
            project.full_clean()

    def test_project_string_representation(self):
        """Test string representation of project"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user1
        )

        self.assertEqual(str(project), "Test Project")

    def test_project_member_management(self):
        """Test adding and removing project members"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user1
        )

        # Add member
        project.members.add(self.user2)
        self.assertIn(self.user2, project.members.all())

        # Remove member
        project.members.remove(self.user2)
        self.assertNotIn(self.user2, project.members.all())

    def test_project_get_all_participants(self):
        """Test getting all project participants (owner + members)"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user1
        )
        project.members.add(self.user2)

        participants = project.get_all_participants()
        self.assertIn(self.user1, participants)  # Owner
        self.assertIn(self.user2, participants)  # Member

    def test_project_user_has_access(self):
        """Test user access checking"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user1
        )

        # Owner has access
        self.assertTrue(project.user_has_access(self.user1))

        # Non-member doesn't have access
        self.assertFalse(project.user_has_access(self.user2))

        # Member has access
        project.members.add(self.user2)
        self.assertTrue(project.user_has_access(self.user2))


class TaskEntryModelTest(TestCase):
    """Test suite for TaskEntry model - TDD approach"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_task_entry_creation_with_valid_data(self):
        """Test creating a task entry with valid data"""
        from loomline.models import Project, TaskEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="SEO Optimization Task",
            description="Optimize meta tags for homepage",
            author=self.user,
            category="on_page_seo"
        )

        self.assertEqual(task.title, "SEO Optimization Task")
        self.assertEqual(task.project, project)
        self.assertEqual(task.author, self.user)
        self.assertEqual(task.category, "on_page_seo")
        self.assertEqual(task.priority, "medium")  # Default
        self.assertEqual(task.status, "todo")  # Default
        self.assertIsNotNone(task.created_at)

    def test_task_entry_required_fields(self):
        """Test that required fields are validated"""
        from loomline.models import TaskEntry

        with self.assertRaises(ValidationError):
            task = TaskEntry(
                description="Test task"
                # Missing project, title, author
            )
            task.full_clean()

    def test_task_entry_category_choices(self):
        """Test that only valid categories are accepted"""
        from loomline.models import Project, TaskEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        # Valid category
        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user,
            category="technical_seo"
        )
        self.assertEqual(task.category, "technical_seo")

        # Invalid category should raise ValidationError
        with self.assertRaises(ValidationError):
            invalid_task = TaskEntry(
                project=project,
                title="Invalid Task",
                author=self.user,
                category="invalid_category"
            )
            invalid_task.full_clean()

    def test_task_entry_priority_choices(self):
        """Test task priority validation"""
        from loomline.models import Project, TaskEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        # Test all valid priorities
        valid_priorities = ['low', 'medium', 'high', 'urgent']
        for priority in valid_priorities:
            task = TaskEntry.objects.create(
                project=project,
                title=f"Task {priority}",
                author=self.user,
                priority=priority
            )
            self.assertEqual(task.priority, priority)

    def test_task_entry_status_choices(self):
        """Test task status validation"""
        from loomline.models import Project, TaskEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        # Test all valid statuses
        valid_statuses = ['todo', 'in_progress', 'review', 'done', 'cancelled']
        for status in valid_statuses:
            task = TaskEntry.objects.create(
                project=project,
                title=f"Task {status}",
                author=self.user,
                status=status
            )
            self.assertEqual(task.status, status)

    def test_task_entry_string_representation(self):
        """Test string representation of task entry"""
        from loomline.models import Project, TaskEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user
        )

        expected_str = f"Test Project - Test Task"
        self.assertEqual(str(task), expected_str)

    def test_task_entry_assignee_functionality(self):
        """Test task assignee assignment"""
        from loomline.models import Project, TaskEntry

        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user,
            assignee=user2
        )

        self.assertEqual(task.assignee, user2)

    def test_task_entry_due_date_functionality(self):
        """Test task due date handling"""
        from loomline.models import Project, TaskEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        future_date = timezone.now() + timedelta(days=7)

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user,
            due_date=future_date
        )

        self.assertEqual(task.due_date, future_date)


class TimelineEntryModelTest(TestCase):
    """Test suite for TimelineEntry model - TDD approach"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_timeline_entry_creation_with_valid_data(self):
        """Test creating a timeline entry with valid data"""
        from loomline.models import Project, TaskEntry, TimelineEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user
        )

        timeline_entry = TimelineEntry.objects.create(
            task=task,
            user=self.user,
            action="created",
            description="Task was created"
        )

        self.assertEqual(timeline_entry.task, task)
        self.assertEqual(timeline_entry.user, self.user)
        self.assertEqual(timeline_entry.action, "created")
        self.assertEqual(timeline_entry.description, "Task was created")
        self.assertIsNotNone(timeline_entry.timestamp)

    def test_timeline_entry_action_choices(self):
        """Test timeline entry action validation"""
        from loomline.models import Project, TaskEntry, TimelineEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user
        )

        valid_actions = [
            'created', 'updated', 'status_changed', 'assigned',
            'commented', 'completed', 'deleted'
        ]

        for action in valid_actions:
            timeline_entry = TimelineEntry.objects.create(
                task=task,
                user=self.user,
                action=action,
                description=f"Task was {action}"
            )
            self.assertEqual(timeline_entry.action, action)

    def test_timeline_entry_string_representation(self):
        """Test string representation of timeline entry"""
        from loomline.models import Project, TaskEntry, TimelineEntry

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user
        )

        timeline_entry = TimelineEntry.objects.create(
            task=task,
            user=self.user,
            action="created",
            description="Task was created"
        )

        expected_str = f"{self.user.username} created Test Task"
        self.assertEqual(str(timeline_entry), expected_str)


class CommentModelTest(TestCase):
    """Test suite for Comment model - TDD approach"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_comment_creation_with_valid_data(self):
        """Test creating a comment with valid data"""
        from loomline.models import Project, TaskEntry, Comment

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user
        )

        comment = Comment.objects.create(
            task=task,
            author=self.user,
            content="This is a test comment"
        )

        self.assertEqual(comment.task, task)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.content, "This is a test comment")
        self.assertIsNotNone(comment.created_at)
        self.assertIsNotNone(comment.updated_at)

    def test_comment_required_fields(self):
        """Test that required fields are validated"""
        from loomline.models import Comment

        with self.assertRaises(ValidationError):
            comment = Comment(
                content="Test comment"
                # Missing task and author
            )
            comment.full_clean()

    def test_comment_string_representation(self):
        """Test string representation of comment"""
        from loomline.models import Project, TaskEntry, Comment

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user
        )

        comment = Comment.objects.create(
            task=task,
            author=self.user,
            content="This is a test comment"
        )

        expected_str = f"{self.user.username} on Test Task: This is a test comment"
        self.assertEqual(str(comment), expected_str)


class SEOMetricsModelTest(TestCase):
    """Test suite for SEOMetrics model - TDD approach"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_seo_metrics_creation_with_valid_data(self):
        """Test creating SEO metrics with valid data"""
        from loomline.models import Project, TaskEntry, SEOMetrics

        project = Project.objects.create(
            name="Test Project",
            owner=self.user,
            domain="example.com"
        )

        task = TaskEntry.objects.create(
            project=project,
            title="SEO Task",
            author=self.user
        )

        metrics = SEOMetrics.objects.create(
            task=task,
            url="https://example.com/page",
            organic_traffic=1000,
            keyword_rankings={'keyword1': 5, 'keyword2': 12},
            page_load_speed=2.5,
            core_web_vitals={'lcp': 2.1, 'fid': 0.8, 'cls': 0.05}
        )

        self.assertEqual(metrics.task, task)
        self.assertEqual(metrics.url, "https://example.com/page")
        self.assertEqual(metrics.organic_traffic, 1000)
        self.assertEqual(metrics.page_load_speed, 2.5)
        self.assertIsInstance(metrics.keyword_rankings, dict)
        self.assertIsInstance(metrics.core_web_vitals, dict)

    def test_seo_metrics_json_field_functionality(self):
        """Test JSON field functionality for keyword rankings and core web vitals"""
        from loomline.models import Project, TaskEntry, SEOMetrics

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="SEO Task",
            author=self.user
        )

        complex_rankings = {
            'primary_keyword': 3,
            'secondary_keyword': 15,
            'long_tail_keyword': 8
        }

        complex_vitals = {
            'lcp': 2.3,
            'fid': 0.9,
            'cls': 0.06,
            'fcp': 1.8,
            'ttfb': 0.5
        }

        metrics = SEOMetrics.objects.create(
            task=task,
            keyword_rankings=complex_rankings,
            core_web_vitals=complex_vitals
        )

        # Refresh from database
        metrics.refresh_from_db()

        self.assertEqual(metrics.keyword_rankings['primary_keyword'], 3)
        self.assertEqual(metrics.core_web_vitals['lcp'], 2.3)

    def test_seo_metrics_string_representation(self):
        """Test string representation of SEO metrics"""
        from loomline.models import Project, TaskEntry, SEOMetrics

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        task = TaskEntry.objects.create(
            project=project,
            title="SEO Task",
            author=self.user
        )

        metrics = SEOMetrics.objects.create(
            task=task,
            url="https://example.com/page"
        )

        expected_str = f"SEO Task - https://example.com/page"
        self.assertEqual(str(metrics), expected_str)


class LoomLineAPITestCase(APITestCase):
    """Test suite for LoomLine API endpoints - TDD approach"""

    def setUp(self):
        """Set up test data for API tests"""
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

    def test_project_list_api_authenticated_user(self):
        """Test project list API for authenticated user"""
        self.client.force_authenticate(user=self.user1)

        url = reverse('loomline:project-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_project_list_api_unauthenticated_user(self):
        """Test project list API for unauthenticated user"""
        url = reverse('loomline:project-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_project_create_api_valid_data(self):
        """Test project creation API with valid data"""
        self.client.force_authenticate(user=self.user1)

        url = reverse('loomline:project-list')
        data = {
            'name': 'New SEO Project',
            'description': 'Test project creation',
            'domain': 'example.com'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New SEO Project')
        self.assertEqual(response.data['owner'], self.user1.id)

    def test_project_create_api_invalid_data(self):
        """Test project creation API with invalid data"""
        self.client.force_authenticate(user=self.user1)

        url = reverse('loomline:project-list')
        data = {
            'description': 'Project without name'
            # Missing required 'name' field
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_task_entry_create_api_valid_data(self):
        """Test task entry creation API with valid data"""
        from loomline.models import Project

        self.client.force_authenticate(user=self.user1)

        project = Project.objects.create(
            name="Test Project",
            owner=self.user1
        )

        url = reverse('loomline:taskentry-list')
        data = {
            'project': project.id,
            'title': 'New SEO Task',
            'description': 'Test task creation',
            'category': 'on_page_seo',
            'priority': 'high'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New SEO Task')
        self.assertEqual(response.data['author'], self.user1.id)

    def test_task_entry_access_control(self):
        """Test task entry access control"""
        from loomline.models import Project, TaskEntry

        # Create project owned by user1
        project = Project.objects.create(
            name="User1 Project",
            owner=self.user1
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Private Task",
            author=self.user1
        )

        # User2 should not be able to access user1's task
        self.client.force_authenticate(user=self.user2)

        url = reverse('loomline:taskentry-detail', kwargs={'pk': task.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_timeline_api_functionality(self):
        """Test timeline API functionality"""
        from loomline.models import Project, TaskEntry

        self.client.force_authenticate(user=self.user1)

        project = Project.objects.create(
            name="Test Project",
            owner=self.user1
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Test Task",
            author=self.user1
        )

        url = reverse('loomline:timeline-list', kwargs={'project_id': project.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class LoomLineViewsTestCase(TestCase):
    """Test suite for LoomLine Views - TDD approach"""

    def setUp(self):
        """Set up test data for view tests"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_project_dashboard_view(self):
        """Test project dashboard view"""
        url = reverse('loomline:dashboard')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LoomLine')
        self.assertContains(response, 'SEO Task Timeline')

    def test_project_detail_view(self):
        """Test project detail view"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        url = reverse('loomline:project-detail', kwargs={'pk': project.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, project.name)

    def test_project_access_control_view(self):
        """Test project access control in views"""
        from loomline.models import Project

        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        project = Project.objects.create(
            name="Other User Project",
            owner=other_user
        )

        url = reverse('loomline:project-detail', kwargs={'pk': project.id})
        response = self.client.get(url)

        # Should return 403 or 404 for unauthorized access
        self.assertIn(response.status_code, [403, 404])

    def test_task_create_view(self):
        """Test task creation view"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        url = reverse('loomline:task-create', kwargs={'project_id': project.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Task')

    def test_timeline_view(self):
        """Test timeline view"""
        from loomline.models import Project

        project = Project.objects.create(
            name="Test Project",
            owner=self.user
        )

        url = reverse('loomline:timeline', kwargs={'project_id': project.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Timeline')


class LoomLineIntegrationTest(TestCase):
    """Integration tests for LoomLine app functionality"""

    def setUp(self):
        """Set up test data for integration tests"""
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )

    def test_collaborative_project_workflow(self):
        """Test complete collaborative project workflow"""
        from loomline.models import Project, TaskEntry, TimelineEntry, Comment

        # 1. User1 creates a project
        project = Project.objects.create(
            name="Collaborative SEO Project",
            description="Testing collaboration features",
            owner=self.user1,
            domain="collaborative-site.com"
        )

        # 2. User1 adds User2 as a member
        project.members.add(self.user2)

        # 3. User1 creates a task
        task = TaskEntry.objects.create(
            project=project,
            title="Optimize Homepage Meta Tags",
            description="Update meta title and description for homepage",
            author=self.user1,
            category="on_page_seo",
            priority="high"
        )

        # 4. User2 assigns themselves to the task
        task.assignee = self.user2
        task.save()

        # 5. User2 updates task status
        task.status = "in_progress"
        task.save()

        # 6. User2 adds a comment
        comment = Comment.objects.create(
            task=task,
            author=self.user2,
            content="Started working on this. Will update meta tags based on keyword research."
        )

        # 7. User1 adds timeline entry for status change
        timeline_entry = TimelineEntry.objects.create(
            task=task,
            user=self.user2,
            action="status_changed",
            description="Status changed from 'todo' to 'in_progress'"
        )

        # Verify the workflow
        self.assertTrue(project.user_has_access(self.user1))
        self.assertTrue(project.user_has_access(self.user2))
        self.assertEqual(task.assignee, self.user2)
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(comment.author, self.user2)
        self.assertEqual(timeline_entry.action, "status_changed")

    def test_seo_metrics_tracking_workflow(self):
        """Test SEO metrics tracking workflow"""
        from loomline.models import Project, TaskEntry, SEOMetrics

        # Create project and task
        project = Project.objects.create(
            name="SEO Metrics Project",
            owner=self.user1,
            domain="metrics-site.com"
        )

        task = TaskEntry.objects.create(
            project=project,
            title="Improve Page Load Speed",
            author=self.user1,
            category="technical_seo"
        )

        # Add initial metrics
        initial_metrics = SEOMetrics.objects.create(
            task=task,
            url="https://metrics-site.com/",
            organic_traffic=500,
            keyword_rankings={'main_keyword': 15, 'secondary_keyword': 23},
            page_load_speed=4.2,
            core_web_vitals={'lcp': 3.1, 'fid': 1.2, 'cls': 0.08}
        )

        # Simulate task completion and improved metrics
        task.status = "done"
        task.save()

        # Add improved metrics
        improved_metrics = SEOMetrics.objects.create(
            task=task,
            url="https://metrics-site.com/",
            organic_traffic=650,
            keyword_rankings={'main_keyword': 8, 'secondary_keyword': 15},
            page_load_speed=2.1,
            core_web_vitals={'lcp': 2.1, 'fid': 0.8, 'cls': 0.05}
        )

        # Verify improvements
        self.assertEqual(task.status, "done")
        self.assertGreater(improved_metrics.organic_traffic, initial_metrics.organic_traffic)
        self.assertLess(improved_metrics.page_load_speed, initial_metrics.page_load_speed)
        self.assertLess(
            improved_metrics.keyword_rankings['main_keyword'],
            initial_metrics.keyword_rankings['main_keyword']
        )
