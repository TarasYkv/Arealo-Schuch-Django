"""
Tests for SoMi-Plan models
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time, date, timedelta
import json

from somi_plan.models import (
    Platform, PostingPlan, PlanningSession, PostContent, 
    PostSchedule, TemplateCategory, PostTemplate
)


class PlatformModelTest(TestCase):
    """Test the Platform model"""
    
    def setUp(self):
        self.platform_data = {
            'name': 'Instagram',
            'icon': 'fab fa-instagram',
            'color': '#E4405F',
            'character_limit': 2200,
            'description': 'Visual social media platform',
            'is_active': True
        }
    
    def test_platform_creation(self):
        """Test platform creation with valid data"""
        platform = Platform.objects.create(**self.platform_data)
        
        self.assertEqual(platform.name, 'Instagram')
        self.assertEqual(platform.icon, 'fab fa-instagram')
        self.assertEqual(platform.color, '#E4405F')
        self.assertEqual(platform.character_limit, 2200)
        self.assertTrue(platform.is_active)
        self.assertIsNotNone(platform.created_at)
        self.assertIsNotNone(platform.updated_at)
    
    def test_platform_str_representation(self):
        """Test platform string representation"""
        platform = Platform.objects.create(**self.platform_data)
        self.assertEqual(str(platform), 'Instagram')
    
    def test_platform_ordering(self):
        """Test platform ordering by name"""
        Platform.objects.create(name='Twitter', **{k: v for k, v in self.platform_data.items() if k != 'name'})
        Platform.objects.create(name='LinkedIn', **{k: v for k, v in self.platform_data.items() if k != 'name'})
        Platform.objects.create(name='Instagram', **{k: v for k, v in self.platform_data.items() if k != 'name'})
        
        platforms = Platform.objects.all()
        self.assertEqual(platforms[0].name, 'Instagram')
        self.assertEqual(platforms[1].name, 'LinkedIn')
        self.assertEqual(platforms[2].name, 'Twitter')
    
    def test_platform_character_limit_validation(self):
        """Test character limit validation"""
        with self.assertRaises(ValidationError):
            platform = Platform(**{**self.platform_data, 'character_limit': -1})
            platform.full_clean()
    
    def test_platform_color_validation(self):
        """Test color hex validation"""
        # Valid hex color
        platform = Platform(**{**self.platform_data, 'color': '#123456'})
        platform.full_clean()  # Should not raise
        
        # Invalid hex color
        with self.assertRaises(ValidationError):
            platform = Platform(**{**self.platform_data, 'color': 'invalid'})
            platform.full_clean()


class PostingPlanModelTest(TestCase):
    """Test the PostingPlan model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200
        )
        self.plan_data = {
            'title': 'Test Marketing Plan',
            'user': self.user,
            'platform': self.platform,
            'user_profile': 'Social Media Manager at Tech Company',
            'target_audience': 'Tech enthusiasts and professionals',
            'goals': 'Increase brand awareness and engagement',
            'vision': 'Become the leading voice in tech innovation',
            'strategy_data': {
                'posting_frequency': 'daily',
                'best_times': ['09:00', '18:00'],
                'content_types': ['tips', 'behind_scenes'],
                'ai_generated_at': '2024-01-01T10:00:00Z'
            }
        }
    
    def test_posting_plan_creation(self):
        """Test posting plan creation"""
        plan = PostingPlan.objects.create(**self.plan_data)
        
        self.assertEqual(plan.title, 'Test Marketing Plan')
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.platform, self.platform)
        self.assertEqual(plan.status, 'draft')  # Default status
        self.assertIsInstance(plan.strategy_data, dict)
        self.assertIsNotNone(plan.created_at)
    
    def test_posting_plan_str_representation(self):
        """Test posting plan string representation"""
        plan = PostingPlan.objects.create(**self.plan_data)
        self.assertEqual(str(plan), 'Test Marketing Plan (Instagram)')
    
    def test_posting_plan_get_post_count(self):
        """Test get_post_count method"""
        plan = PostingPlan.objects.create(**self.plan_data)
        
        # Initially no posts
        self.assertEqual(plan.get_post_count(), 0)
        
        # Add some posts
        PostContent.objects.create(
            posting_plan=plan,
            title='Test Post 1',
            content='Test content 1'
        )
        PostContent.objects.create(
            posting_plan=plan,
            title='Test Post 2',
            content='Test content 2'
        )
        
        self.assertEqual(plan.get_post_count(), 2)
    
    def test_posting_plan_get_scheduled_count(self):
        """Test get_scheduled_count method"""
        plan = PostingPlan.objects.create(**self.plan_data)
        
        # Create posts
        post1 = PostContent.objects.create(
            posting_plan=plan,
            title='Test Post 1',
            content='Test content 1'
        )
        post2 = PostContent.objects.create(
            posting_plan=plan,
            title='Test Post 2',
            content='Test content 2'
        )
        
        # Initially no scheduled posts
        self.assertEqual(plan.get_scheduled_count(), 0)
        
        # Schedule one post
        PostSchedule.objects.create(
            post_content=post1,
            scheduled_date=timezone.now().date(),
            scheduled_time=time(12, 0),
            status='scheduled'
        )
        
        self.assertEqual(plan.get_scheduled_count(), 1)
    
    def test_posting_plan_status_choices(self):
        """Test status field choices"""
        plan = PostingPlan.objects.create(**self.plan_data)
        
        # Test valid statuses
        valid_statuses = ['draft', 'active', 'paused', 'completed']
        for status in valid_statuses:
            plan.status = status
            plan.full_clean()  # Should not raise
        
        # Test invalid status
        plan.status = 'invalid'
        with self.assertRaises(ValidationError):
            plan.full_clean()


class PlanningSessionModelTest(TestCase):
    """Test the PlanningSession model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200
        )
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
    
    def test_planning_session_creation(self):
        """Test planning session creation"""
        session = PlanningSession.objects.create(
            posting_plan=self.plan,
            current_step=1
        )
        
        self.assertEqual(session.posting_plan, self.plan)
        self.assertEqual(session.current_step, 1)
        self.assertEqual(session.completed_steps, [])
        self.assertIsNotNone(session.created_at)
    
    def test_planning_session_complete_step(self):
        """Test complete_step method"""
        session = PlanningSession.objects.create(
            posting_plan=self.plan,
            current_step=1
        )
        
        # Complete step 1
        session.complete_step(1)
        self.assertIn(1, session.completed_steps)
        
        # Complete step 2
        session.complete_step(2)
        self.assertIn(2, session.completed_steps)
        self.assertEqual(len(session.completed_steps), 2)
    
    def test_planning_session_is_step_completed(self):
        """Test is_step_completed method"""
        session = PlanningSession.objects.create(
            posting_plan=self.plan,
            current_step=1
        )
        
        # Initially no steps completed
        self.assertFalse(session.is_step_completed(1))
        
        # Complete step 1
        session.complete_step(1)
        self.assertTrue(session.is_step_completed(1))
        self.assertFalse(session.is_step_completed(2))
    
    def test_planning_session_get_progress_percentage(self):
        """Test get_progress_percentage method"""
        session = PlanningSession.objects.create(
            posting_plan=self.plan,
            current_step=1
        )
        
        # No steps completed
        self.assertEqual(session.get_progress_percentage(), 0)
        
        # Complete step 1 (1/3 = 33%)
        session.complete_step(1)
        self.assertAlmostEqual(session.get_progress_percentage(), 33.33, places=1)
        
        # Complete all steps
        session.complete_step(2)
        session.complete_step(3)
        self.assertEqual(session.get_progress_percentage(), 100)


class PostContentModelTest(TestCase):
    """Test the PostContent model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=280
        )
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        self.post_data = {
            'posting_plan': self.plan,
            'title': 'Test Post',
            'content': 'This is a test post content that demonstrates our platform.',
            'hashtags': '#test #social #media',
            'call_to_action': 'Click the link in our bio!',
            'script': 'Additional implementation notes',
            'post_type': 'tips',
            'priority': 1,
            'ai_generated': True,
            'ai_model_used': 'gpt-4'
        }
    
    def test_post_content_creation(self):
        """Test post content creation"""
        post = PostContent.objects.create(**self.post_data)
        
        self.assertEqual(post.title, 'Test Post')
        self.assertEqual(post.posting_plan, self.plan)
        self.assertTrue(post.ai_generated)
        self.assertEqual(post.post_type, 'tips')
        self.assertEqual(post.priority, 1)
        self.assertIsNotNone(post.created_at)
    
    def test_post_content_str_representation(self):
        """Test post content string representation"""
        post = PostContent.objects.create(**self.post_data)
        self.assertEqual(str(post), 'Test Post')
    
    def test_post_content_character_count(self):
        """Test character_count property"""
        post = PostContent.objects.create(**self.post_data)
        expected_count = len('This is a test post content that demonstrates our platform.')
        self.assertEqual(post.character_count, expected_count)
    
    def test_post_content_get_character_limit_percentage(self):
        """Test get_character_limit_percentage method"""
        post = PostContent.objects.create(**self.post_data)
        expected_percentage = (len(post.content) / self.platform.character_limit) * 100
        self.assertAlmostEqual(post.get_character_limit_percentage(), expected_percentage, places=1)
    
    def test_post_content_is_over_limit(self):
        """Test is_over_limit method"""
        # Normal post under limit
        post = PostContent.objects.create(**self.post_data)
        self.assertFalse(post.is_over_limit())
        
        # Post over limit
        long_content = 'x' * (self.platform.character_limit + 1)
        post_over = PostContent.objects.create(
            **{**self.post_data, 'content': long_content, 'title': 'Over Limit Post'}
        )
        self.assertTrue(post_over.is_over_limit())
    
    def test_post_content_post_type_choices(self):
        """Test post_type field choices"""
        post = PostContent.objects.create(**self.post_data)
        
        # Test valid post types
        valid_types = ['tips', 'behind_scenes', 'motivational', 'product', 'news', 'educational', 'entertainment']
        for post_type in valid_types:
            post.post_type = post_type
            post.full_clean()  # Should not raise
        
        # Test invalid post type
        post.post_type = 'invalid'
        with self.assertRaises(ValidationError):
            post.full_clean()
    
    def test_post_content_priority_validation(self):
        """Test priority field validation"""
        post = PostContent.objects.create(**self.post_data)
        
        # Valid priorities
        for priority in [1, 2, 3]:
            post.priority = priority
            post.full_clean()  # Should not raise
        
        # Invalid priorities
        for invalid_priority in [0, 4, -1]:
            post.priority = invalid_priority
            with self.assertRaises(ValidationError):
                post.full_clean()


class PostScheduleModelTest(TestCase):
    """Test the PostSchedule model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200
        )
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        self.post = PostContent.objects.create(
            posting_plan=self.plan,
            title='Test Post',
            content='Test content'
        )
        self.schedule_data = {
            'post_content': self.post,
            'scheduled_date': date.today() + timedelta(days=1),
            'scheduled_time': time(14, 30),
            'notes': 'Remember to check engagement',
            'status': 'scheduled'
        }
    
    def test_post_schedule_creation(self):
        """Test post schedule creation"""
        schedule = PostSchedule.objects.create(**self.schedule_data)
        
        self.assertEqual(schedule.post_content, self.post)
        self.assertEqual(schedule.status, 'scheduled')
        self.assertIsNotNone(schedule.scheduled_date)
        self.assertIsNotNone(schedule.scheduled_time)
        self.assertIsNotNone(schedule.created_at)
    
    def test_post_schedule_str_representation(self):
        """Test post schedule string representation"""
        schedule = PostSchedule.objects.create(**self.schedule_data)
        expected_str = f'Test Post - {schedule.scheduled_date} {schedule.scheduled_time}'
        self.assertEqual(str(schedule), expected_str)
    
    def test_post_schedule_mark_completed(self):
        """Test mark_completed method"""
        schedule = PostSchedule.objects.create(**self.schedule_data)
        
        # Mark as completed with URL
        test_url = 'https://instagram.com/p/test123'
        schedule.mark_completed(test_url)
        
        self.assertEqual(schedule.status, 'completed')
        self.assertEqual(schedule.published_url, test_url)
        self.assertIsNotNone(schedule.completed_at)
    
    def test_post_schedule_mark_failed(self):
        """Test mark_failed method"""
        schedule = PostSchedule.objects.create(**self.schedule_data)
        
        error_message = 'API connection failed'
        schedule.mark_failed(error_message)
        
        self.assertEqual(schedule.status, 'failed')
        self.assertEqual(schedule.failure_reason, error_message)
        self.assertIsNotNone(schedule.completed_at)
    
    def test_post_schedule_is_overdue(self):
        """Test is_overdue method"""
        # Past schedule
        past_schedule = PostSchedule.objects.create(
            **{**self.schedule_data, 
               'scheduled_date': date.today() - timedelta(days=1),
               'scheduled_time': time(12, 0)}
        )
        self.assertTrue(past_schedule.is_overdue())
        
        # Future schedule
        future_schedule = PostSchedule.objects.create(
            **{**self.schedule_data, 
               'scheduled_date': date.today() + timedelta(days=1)}
        )
        self.assertFalse(future_schedule.is_overdue())
        
        # Completed schedule (not overdue even if past)
        completed_schedule = PostSchedule.objects.create(
            **{**self.schedule_data, 
               'scheduled_date': date.today() - timedelta(days=1),
               'status': 'completed'}
        )
        self.assertFalse(completed_schedule.is_overdue())
    
    def test_post_schedule_status_choices(self):
        """Test status field choices"""
        schedule = PostSchedule.objects.create(**self.schedule_data)
        
        # Test valid statuses
        valid_statuses = ['scheduled', 'completed', 'failed', 'cancelled']
        for status in valid_statuses:
            schedule.status = status
            schedule.full_clean()  # Should not raise
        
        # Test invalid status
        schedule.status = 'invalid'
        with self.assertRaises(ValidationError):
            schedule.full_clean()


class TemplateCategoryModelTest(TestCase):
    """Test the TemplateCategory model"""
    
    def test_template_category_creation(self):
        """Test template category creation"""
        category = TemplateCategory.objects.create(
            name='Marketing Tips',
            description='Templates for marketing advice posts',
            icon='fas fa-lightbulb'
        )
        
        self.assertEqual(category.name, 'Marketing Tips')
        self.assertEqual(category.icon, 'fas fa-lightbulb')
        self.assertTrue(category.is_active)
        self.assertIsNotNone(category.created_at)
    
    def test_template_category_str_representation(self):
        """Test template category string representation"""
        category = TemplateCategory.objects.create(
            name='Marketing Tips',
            description='Templates for marketing advice posts'
        )
        self.assertEqual(str(category), 'Marketing Tips')
    
    def test_template_category_ordering(self):
        """Test template category ordering"""
        cat1 = TemplateCategory.objects.create(name='Zebra Category')
        cat2 = TemplateCategory.objects.create(name='Alpha Category')
        cat3 = TemplateCategory.objects.create(name='Beta Category')
        
        categories = TemplateCategory.objects.all()
        self.assertEqual(categories[0].name, 'Alpha Category')
        self.assertEqual(categories[1].name, 'Beta Category')
        self.assertEqual(categories[2].name, 'Zebra Category')


class PostTemplateModelTest(TestCase):
    """Test the PostTemplate model"""
    
    def setUp(self):
        self.category = TemplateCategory.objects.create(
            name='Marketing Tips',
            description='Templates for marketing advice posts'
        )
        self.template_data = {
            'title': 'Monday Motivation',
            'category': self.category,
            'content_template': 'Start your week with this tip: {tip_content}',
            'hashtags_template': '#MondayMotivation #Tips #{industry}',
            'call_to_action_template': 'What motivates you? Comment below!',
            'variables': ['tip_content', 'industry'],
            'post_type': 'motivational',
            'description': 'Weekly motivation post template'
        }
    
    def test_post_template_creation(self):
        """Test post template creation"""
        template = PostTemplate.objects.create(**self.template_data)
        
        self.assertEqual(template.title, 'Monday Motivation')
        self.assertEqual(template.category, self.category)
        self.assertEqual(template.post_type, 'motivational')
        self.assertIn('tip_content', template.variables)
        self.assertTrue(template.is_active)
        self.assertIsNotNone(template.created_at)
    
    def test_post_template_str_representation(self):
        """Test post template string representation"""
        template = PostTemplate.objects.create(**self.template_data)
        self.assertEqual(str(template), 'Monday Motivation')
    
    def test_post_template_generate_content(self):
        """Test generate_content method"""
        template = PostTemplate.objects.create(**self.template_data)
        
        variables = {
            'tip_content': 'Always plan your day the night before',
            'industry': 'productivity'
        }
        
        content = template.generate_content(variables)
        
        expected_content = 'Start your week with this tip: Always plan your day the night before'
        expected_hashtags = '#MondayMotivation #Tips #productivity'
        expected_cta = 'What motivates you? Comment below!'
        
        self.assertEqual(content['content'], expected_content)
        self.assertEqual(content['hashtags'], expected_hashtags)
        self.assertEqual(content['call_to_action'], expected_cta)
    
    def test_post_template_generate_content_missing_variables(self):
        """Test generate_content with missing variables"""
        template = PostTemplate.objects.create(**self.template_data)
        
        # Missing 'industry' variable
        variables = {
            'tip_content': 'Always plan your day the night before'
        }
        
        content = template.generate_content(variables)
        
        # Should contain placeholder for missing variable
        self.assertIn('{industry}', content['hashtags'])
    
    def test_post_template_get_usage_count(self):
        """Test get_usage_count method"""
        template = PostTemplate.objects.create(**self.template_data)
        
        # Initially no usage
        self.assertEqual(template.get_usage_count(), 0)
        
        # This would be incremented when posts are created from this template
        # For now, just test the method exists and returns 0
        self.assertIsInstance(template.get_usage_count(), int)


class ModelIntegrationTest(TestCase):
    """Test model relationships and integrations"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200
        )
    
    def test_complete_workflow(self):
        """Test a complete workflow from plan creation to scheduling"""
        # Create posting plan
        plan = PostingPlan.objects.create(
            title='Complete Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        # Create planning session
        session = PlanningSession.objects.create(
            posting_plan=plan,
            current_step=1
        )
        
        # Complete steps
        session.complete_step(1)
        session.complete_step(2)
        
        # Create content
        post = PostContent.objects.create(
            posting_plan=plan,
            title='Test Post',
            content='This is test content for our workflow.',
            post_type='tips',
            priority=1
        )
        
        # Schedule post
        schedule = PostSchedule.objects.create(
            post_content=post,
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(15, 0),
            status='scheduled'
        )
        
        # Test relationships
        self.assertEqual(plan.get_post_count(), 1)
        self.assertEqual(plan.get_scheduled_count(), 1)
        self.assertTrue(session.is_step_completed(1))
        self.assertTrue(session.is_step_completed(2))
        self.assertFalse(post.is_over_limit())
        self.assertFalse(schedule.is_overdue())
        
        # Mark as completed
        schedule.mark_completed('https://instagram.com/p/test123')
        self.assertEqual(schedule.status, 'completed')
        self.assertIsNotNone(schedule.completed_at)
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior"""
        # Create plan with content
        plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        post = PostContent.objects.create(
            posting_plan=plan,
            title='Test Post',
            content='Test content'
        )
        
        schedule = PostSchedule.objects.create(
            post_content=post,
            scheduled_date=date.today(),
            scheduled_time=time(12, 0)
        )
        
        # Verify objects exist
        self.assertTrue(PostingPlan.objects.filter(id=plan.id).exists())
        self.assertTrue(PostContent.objects.filter(id=post.id).exists())
        self.assertTrue(PostSchedule.objects.filter(id=schedule.id).exists())
        
        # Delete plan should cascade
        plan.delete()
        
        # Verify cascade deletion
        self.assertFalse(PostingPlan.objects.filter(id=plan.id).exists())
        self.assertFalse(PostContent.objects.filter(id=post.id).exists())
        self.assertFalse(PostSchedule.objects.filter(id=schedule.id).exists())