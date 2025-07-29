"""
Custom test runner and test utilities for SoMi-Plan
"""
from django.test.runner import DiscoverRunner
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command
import tempfile
import os


class SomiPlanTestRunner(DiscoverRunner):
    """Custom test runner for SoMi-Plan with additional setup"""
    
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        
        # Set up test-specific settings
        from django.conf import settings
        
        # Use in-memory database for faster tests
        if 'sqlite' in settings.DATABASES['default']['ENGINE']:
            settings.DATABASES['default']['NAME'] = ':memory:'
        
        # Disable logging during tests to reduce noise
        import logging
        logging.disable(logging.CRITICAL)
    
    def teardown_test_environment(self, **kwargs):
        super().teardown_test_environment(**kwargs)
        
        # Re-enable logging
        import logging
        logging.disable(logging.NOTSET)
    
    def setup_databases(self, **kwargs):
        """Set up test databases and initial data"""
        result = super().setup_databases(**kwargs)
        
        # Set up basic platforms for all tests
        call_command('setup_platforms', verbosity=0)
        
        return result


class BaseTestCase(TestCase):
    """Base test case with common utilities"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure platforms exist for all tests
        call_command('setup_platforms', verbosity=0)
    
    def setUp(self):
        """Set up common test data"""
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from somi_plan.models import Platform
        self.test_platform = Platform.objects.filter(is_active=True).first()
    
    def create_test_plan(self, user=None, **kwargs):
        """Helper method to create test posting plans"""
        from somi_plan.models import PostingPlan
        
        defaults = {
            'title': 'Test Plan',
            'user': user or self.test_user,
            'platform': self.test_platform,
            'user_profile': 'Test user profile',
            'target_audience': 'Test target audience',
            'goals': 'Test goals',
            'vision': 'Test vision'
        }
        defaults.update(kwargs)
        
        return PostingPlan.objects.create(**defaults)
    
    def create_test_post(self, plan=None, **kwargs):
        """Helper method to create test posts"""
        from somi_plan.models import PostContent
        
        if plan is None:
            plan = self.create_test_plan()
        
        defaults = {
            'posting_plan': plan,
            'title': 'Test Post',
            'content': 'Test post content',
            'post_type': 'tips',
            'priority': 2
        }
        defaults.update(kwargs)
        
        return PostContent.objects.create(**defaults)
    
    def create_test_schedule(self, post=None, **kwargs):
        """Helper method to create test schedules"""
        from somi_plan.models import PostSchedule
        from datetime import date, time
        
        if post is None:
            post = self.create_test_post()
        
        defaults = {
            'post_content': post,
            'scheduled_date': date.today(),
            'scheduled_time': time(12, 0),
            'status': 'scheduled'
        }
        defaults.update(kwargs)
        
        return PostSchedule.objects.create(**defaults)
    
    def assertResponseContains(self, response, text, status_code=200):
        """Assert response contains text and has correct status"""
        self.assertEqual(response.status_code, status_code)
        self.assertContains(response, text, status_code=status_code)
    
    def assertJSONResponse(self, response, expected_status='success'):
        """Assert response is valid JSON with expected status"""
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        import json
        data = json.loads(response.content)
        self.assertEqual(data.get('status'), expected_status)
        return data


class PerformanceTestCase(TestCase):
    """Base test case for performance testing"""
    
    def setUp(self):
        import time
        self.start_time = time.time()
    
    def tearDown(self):
        import time
        elapsed = time.time() - self.start_time
        if elapsed > 5.0:  # Warn if test takes more than 5 seconds
            print(f"\nWarning: {self._testMethodName} took {elapsed:.2f} seconds")
    
    def assertPerformance(self, max_seconds=1.0):
        """Assert that test completed within time limit"""
        import time
        elapsed = time.time() - self.start_time
        self.assertLess(
            elapsed, 
            max_seconds, 
            f"Test took {elapsed:.2f} seconds, expected < {max_seconds}"
        )


class MockTestCase(TestCase):
    """Base test case with mocking utilities"""
    
    def mock_ai_service_success(self, mock_openai, strategy_data=None, posts_data=None):
        """Mock successful AI service responses"""
        import json
        
        if strategy_data is None:
            strategy_data = {
                'posting_frequency': 'daily',
                'best_times': ['09:00', '18:00'],
                'content_types': ['tips', 'educational']
            }
        
        if posts_data is None:
            posts_data = [{
                'title': 'Mock AI Post',
                'content': 'Mock AI generated content',
                'hashtags': '#mock #ai #test',
                'post_type': 'tips',
                'priority': 1
            }]
        
        def side_effect(*args, **kwargs):
            # Check if this is a strategy or content generation call
            messages = kwargs.get('messages', [])
            if any('strategy' in str(msg).lower() for msg in messages):
                return {
                    'choices': [{'message': {'content': json.dumps(strategy_data)}}],
                    'usage': {'total_tokens': 500}
                }
            else:
                return {
                    'choices': [{'message': {'content': json.dumps(posts_data)}}],
                    'usage': {'total_tokens': 800}
                }
        
        mock_openai.side_effect = side_effect
    
    def mock_ai_service_failure(self, mock_openai, error_message="Mock API Error"):
        """Mock AI service failure"""
        mock_openai.side_effect = Exception(error_message)


class IntegrationTestCase(BaseTestCase):
    """Base test case for integration testing"""
    
    def setUp(self):
        super().setUp()
        self.client.login(username='testuser', password='testpass123')
    
    def complete_plan_creation_workflow(self, use_ai=False):
        """Helper to complete entire plan creation workflow"""
        from django.urls import reverse
        
        # Step 1
        step1_data = {
            'title': 'Integration Test Plan',
            'platform': self.test_platform.id,
            'user_profile': 'Integration test profile',
            'target_audience': 'Integration test audience',
            'goals': 'Integration test goals',
            'vision': 'Integration test vision'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step1'), step1_data)
        
        from somi_plan.models import PostingPlan
        plan = PostingPlan.objects.get(title='Integration Test Plan')
        
        # Step 2
        step2_data = {
            'use_ai_strategy': use_ai,
            'posting_frequency': 'daily',
            'best_times': '09:00,18:00',
            'content_types': 'tips,educational',
            'cross_platform': False
        }
        
        response = self.client.post(
            reverse('somi_plan:create_plan_step2', args=[plan.id]), 
            step2_data
        )
        
        # Create some test content
        self.create_test_post(plan, title='Integration Post 1')
        self.create_test_post(plan, title='Integration Post 2')
        
        # Step 3 - Activate
        response = self.client.post(
            reverse('somi_plan:create_plan_step3', args=[plan.id]),
            {'action': 'activate'}
        )
        
        return plan


def create_temp_file(content=""):
    """Create temporary file for testing file operations"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


def cleanup_temp_file(file_path):
    """Clean up temporary file"""
    try:
        os.unlink(file_path)
    except OSError:
        pass


class FileTestMixin:
    """Mixin for tests that need file handling"""
    
    def setUp(self):
        super().setUp()
        self.temp_files = []
    
    def tearDown(self):
        super().tearDown()
        for file_path in self.temp_files:
            cleanup_temp_file(file_path)
    
    def create_temp_file(self, content=""):
        """Create temporary file and track for cleanup"""
        file_path = create_temp_file(content)
        self.temp_files.append(file_path)
        return file_path


class DatabaseTestMixin:
    """Mixin for tests that need database inspection"""
    
    def get_table_names(self):
        """Get all table names in the database"""
        from django.db import connection
        return connection.introspection.table_names()
    
    def get_table_fields(self, table_name):
        """Get field names for a table"""
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]
    
    def count_queries(self):
        """Context manager to count database queries"""
        from django.test.utils import override_settings
        from django.db import connection
        
        class QueryCounter:
            def __enter__(self):
                self.initial_queries = len(connection.queries)
                return self
            
            def __exit__(self, *args):
                self.final_queries = len(connection.queries)
                self.count = self.final_queries - self.initial_queries
        
        return QueryCounter()


# Test data factories
class TestDataFactory:
    """Factory for creating test data"""
    
    @staticmethod
    def create_user(username="testuser", **kwargs):
        """Create test user"""
        defaults = {
            'email': f'{username}@test.com',
            'password': 'testpass123'
        }
        defaults.update(kwargs)
        
        return User.objects.create_user(username=username, **defaults)
    
    @staticmethod
    def create_platform(**kwargs):
        """Create test platform"""
        from somi_plan.models import Platform
        
        defaults = {
            'name': 'Test Platform',
            'icon': 'fab fa-test',
            'color': '#000000',
            'character_limit': 500,
            'is_active': True
        }
        defaults.update(kwargs)
        
        return Platform.objects.create(**defaults)
    
    @staticmethod
    def create_plan(user=None, platform=None, **kwargs):
        """Create test posting plan"""
        from somi_plan.models import PostingPlan
        
        if user is None:
            user = TestDataFactory.create_user()
        if platform is None:
            platform = TestDataFactory.create_platform()
        
        defaults = {
            'title': 'Test Plan',
            'user': user,
            'platform': platform,
            'user_profile': 'Test profile',
            'target_audience': 'Test audience',
            'goals': 'Test goals',
            'vision': 'Test vision'
        }
        defaults.update(kwargs)
        
        return PostingPlan.objects.create(**defaults)


# Custom assertions
class SomiPlanAssertions:
    """Custom assertions for SoMi-Plan testing"""
    
    def assertPlanValid(self, plan):
        """Assert plan has all required fields"""
        self.assertIsNotNone(plan.title)
        self.assertIsNotNone(plan.user)
        self.assertIsNotNone(plan.platform)
        self.assertIsNotNone(plan.user_profile)
        self.assertIsNotNone(plan.target_audience)
        self.assertIsNotNone(plan.goals)
        self.assertIsNotNone(plan.vision)
    
    def assertPostValid(self, post):
        """Assert post has all required fields"""
        self.assertIsNotNone(post.title)
        self.assertIsNotNone(post.content)
        self.assertIsNotNone(post.posting_plan)
        self.assertIn(post.post_type, ['tips', 'behind_scenes', 'motivational', 'product', 'news', 'educational', 'entertainment'])
        self.assertIn(post.priority, [1, 2, 3])
    
    def assertScheduleValid(self, schedule):
        """Assert schedule has all required fields"""
        self.assertIsNotNone(schedule.post_content)
        self.assertIsNotNone(schedule.scheduled_date)
        self.assertIsNotNone(schedule.scheduled_time)
        self.assertIn(schedule.status, ['scheduled', 'completed', 'failed', 'cancelled'])


# Combine all custom assertions into test cases
class SomiPlanTestCase(BaseTestCase, SomiPlanAssertions):
    """Complete test case with all SoMi-Plan utilities"""
    pass


class SomiPlanIntegrationTestCase(IntegrationTestCase, SomiPlanAssertions):
    """Complete integration test case with all utilities"""
    pass


class SomiPlanPerformanceTestCase(PerformanceTestCase, SomiPlanAssertions):
    """Complete performance test case with all utilities"""
    pass