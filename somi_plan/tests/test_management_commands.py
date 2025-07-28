"""
Tests for SoMi-Plan management commands
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from datetime import date, time, timedelta
from io import StringIO

from somi_plan.models import (
    Platform, PostingPlan, PostContent, PostSchedule, 
    TemplateCategory, PostTemplate
)


class SetupPlatformsCommandTest(TestCase):
    """Test setup_platforms management command"""
    
    def test_setup_platforms_creates_default_platforms(self):
        """Test that setup_platforms creates all default platforms"""
        # Ensure no platforms exist initially
        Platform.objects.all().delete()
        
        # Run command
        out = StringIO()
        call_command('setup_platforms', stdout=out)
        
        # Check that platforms were created
        platforms = Platform.objects.all()
        self.assertGreater(platforms.count(), 0)
        
        # Check for specific platforms
        platform_names = [p.name for p in platforms]
        expected_platforms = ['Instagram', 'LinkedIn', 'Twitter', 'Facebook', 'TikTok']
        
        for expected in expected_platforms:
            self.assertIn(expected, platform_names)
        
        # Check platform properties
        instagram = Platform.objects.get(name='Instagram')
        self.assertEqual(instagram.icon, 'fab fa-instagram')
        self.assertEqual(instagram.color, '#E4405F')
        self.assertEqual(instagram.character_limit, 2200)
        self.assertTrue(instagram.is_active)
        
        linkedin = Platform.objects.get(name='LinkedIn')
        self.assertEqual(linkedin.character_limit, 3000)
        
        twitter = Platform.objects.get(name='Twitter')
        self.assertEqual(twitter.character_limit, 280)
    
    def test_setup_platforms_idempotent(self):
        """Test that running setup_platforms multiple times doesn't create duplicates"""
        # Run command twice
        call_command('setup_platforms')
        initial_count = Platform.objects.count()
        
        call_command('setup_platforms')
        final_count = Platform.objects.count()
        
        # Count should remain the same
        self.assertEqual(initial_count, final_count)
        
        # Check that existing platforms weren't modified
        instagram = Platform.objects.get(name='Instagram')
        self.assertEqual(instagram.character_limit, 2200)
    
    def test_setup_platforms_updates_existing(self):
        """Test that setup_platforms updates existing platforms if needed"""
        # Create platform with outdated info
        Platform.objects.create(
            name='Instagram',
            icon='old-icon',
            color='#000000',
            character_limit=1000,
            is_active=False
        )
        
        # Run command
        call_command('setup_platforms')
        
        # Check that platform was updated
        instagram = Platform.objects.get(name='Instagram')
        self.assertEqual(instagram.icon, 'fab fa-instagram')
        self.assertEqual(instagram.color, '#E4405F')
        self.assertEqual(instagram.character_limit, 2200)
        self.assertTrue(instagram.is_active)


class SetupTemplatesCommandTest(TestCase):
    """Test setup_templates management command"""
    
    def setUp(self):
        call_command('setup_platforms')
    
    def test_setup_templates_creates_categories(self):
        """Test that setup_templates creates template categories"""
        # Ensure no categories exist initially
        TemplateCategory.objects.all().delete()
        
        # Run command
        out = StringIO()
        call_command('setup_templates', stdout=out)
        
        # Check that categories were created
        categories = TemplateCategory.objects.all()
        self.assertGreater(categories.count(), 0)
        
        # Check for specific categories
        category_names = [c.name for c in categories]
        expected_categories = ['Marketing Tips', 'Behind the Scenes', 'Motivational', 'Product Showcase']
        
        for expected in expected_categories:
            self.assertIn(expected, category_names)
    
    def test_setup_templates_creates_templates(self):
        """Test that setup_templates creates post templates"""
        # Ensure no templates exist initially
        PostTemplate.objects.all().delete()
        TemplateCategory.objects.all().delete()
        
        # Run command
        call_command('setup_templates')
        
        # Check that templates were created
        templates = PostTemplate.objects.all()
        self.assertGreater(templates.count(), 0)
        
        # Check template properties
        tip_templates = templates.filter(post_type='tips')
        self.assertGreater(tip_templates.count(), 0)
        
        first_template = tip_templates.first()
        self.assertIsNotNone(first_template.content_template)
        self.assertIsNotNone(first_template.hashtags_template)
        self.assertTrue(first_template.is_active)
    
    def test_setup_templates_idempotent(self):
        """Test that running setup_templates multiple times doesn't create duplicates"""
        # Run command twice
        call_command('setup_templates')
        initial_count = PostTemplate.objects.count()
        
        call_command('setup_templates')
        final_count = PostTemplate.objects.count()
        
        # Count should remain the same
        self.assertEqual(initial_count, final_count)


class CleanupOldSchedulesCommandTest(TestCase):
    """Test cleanup_old_schedules management command"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
        
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
    
    def test_cleanup_old_schedules_removes_old_completed(self):
        """Test that cleanup removes old completed schedules"""
        # Create old completed schedule
        old_post = PostContent.objects.create(
            posting_plan=self.plan,
            title='Old Post',
            content='Old content'
        )
        
        old_schedule = PostSchedule.objects.create(
            post_content=old_post,
            scheduled_date=date.today() - timedelta(days=100),
            scheduled_time=time(12, 0),
            status='completed'
        )
        old_schedule.completed_at = timezone.now() - timedelta(days=100)
        old_schedule.save()
        
        # Create recent completed schedule
        recent_post = PostContent.objects.create(
            posting_plan=self.plan,
            title='Recent Post',
            content='Recent content'
        )
        
        recent_schedule = PostSchedule.objects.create(
            post_content=recent_post,
            scheduled_date=date.today() - timedelta(days=10),
            scheduled_time=time(12, 0),
            status='completed'
        )
        recent_schedule.completed_at = timezone.now() - timedelta(days=10)
        recent_schedule.save()
        
        # Create pending schedule
        pending_post = PostContent.objects.create(
            posting_plan=self.plan,
            title='Pending Post',
            content='Pending content'
        )
        
        pending_schedule = PostSchedule.objects.create(
            post_content=pending_post,
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(12, 0),
            status='scheduled'
        )
        
        initial_count = PostSchedule.objects.count()
        self.assertEqual(initial_count, 3)
        
        # Run cleanup command (default is 30 days)
        out = StringIO()
        call_command('cleanup_old_schedules', stdout=out)
        
        # Check that only old completed schedule was removed
        remaining_schedules = PostSchedule.objects.all()
        self.assertEqual(remaining_schedules.count(), 2)
        
        # Verify which schedules remain
        self.assertTrue(PostSchedule.objects.filter(id=recent_schedule.id).exists())
        self.assertTrue(PostSchedule.objects.filter(id=pending_schedule.id).exists())
        self.assertFalse(PostSchedule.objects.filter(id=old_schedule.id).exists())
    
    def test_cleanup_old_schedules_custom_days(self):
        """Test cleanup with custom days parameter"""
        # Create schedule 15 days old
        post = PostContent.objects.create(
            posting_plan=self.plan,
            title='15 Day Old Post',
            content='15 day old content'
        )
        
        schedule = PostSchedule.objects.create(
            post_content=post,
            scheduled_date=date.today() - timedelta(days=15),
            scheduled_time=time(12, 0),
            status='completed'
        )
        schedule.completed_at = timezone.now() - timedelta(days=15)
        schedule.save()
        
        # Run cleanup with 10 days
        call_command('cleanup_old_schedules', days=10)
        
        # Schedule should be removed
        self.assertFalse(PostSchedule.objects.filter(id=schedule.id).exists())
        
        # Create another schedule 5 days old
        post2 = PostContent.objects.create(
            posting_plan=self.plan,
            title='5 Day Old Post',
            content='5 day old content'
        )
        
        schedule2 = PostSchedule.objects.create(
            post_content=post2,
            scheduled_date=date.today() - timedelta(days=5),
            scheduled_time=time(12, 0),
            status='completed'
        )
        schedule2.completed_at = timezone.now() - timedelta(days=5)
        schedule2.save()
        
        # Run cleanup with 10 days
        call_command('cleanup_old_schedules', days=10)
        
        # Schedule should remain
        self.assertTrue(PostSchedule.objects.filter(id=schedule2.id).exists())


class GenerateTestDataCommandTest(TestCase):
    """Test generate_test_data management command"""
    
    def setUp(self):
        # Ensure platforms exist
        call_command('setup_platforms')
    
    def test_generate_test_data_creates_users(self):
        """Test that generate_test_data creates test users"""
        # Remove any existing test users
        User.objects.filter(username__startswith='testuser').delete()
        
        # Run command
        out = StringIO()
        call_command('generate_test_data', users=2, stdout=out)
        
        # Check that test users were created
        test_users = User.objects.filter(username__startswith='testuser')
        self.assertEqual(test_users.count(), 2)
        
        # Check user properties
        user = test_users.first()
        self.assertTrue(user.email.endswith('@test.com'))
    
    def test_generate_test_data_creates_plans(self):
        """Test that generate_test_data creates test plans"""
        # Create test user first
        user = User.objects.create_user(
            username='testuser1',
            email='testuser1@test.com',
            password='testpass123'
        )
        
        # Run command
        call_command('generate_test_data', users=1, plans_per_user=3)
        
        # Check that plans were created
        plans = PostingPlan.objects.filter(user__username__startswith='testuser')
        self.assertGreaterEqual(plans.count(), 3)
        
        # Check plan properties
        plan = plans.first()
        self.assertIsNotNone(plan.title)
        self.assertIsNotNone(plan.platform)
        self.assertIsNotNone(plan.user_profile)
    
    def test_generate_test_data_creates_posts_and_schedules(self):
        """Test that generate_test_data creates posts and schedules"""
        # Run command with specific parameters
        call_command('generate_test_data', 
                    users=1, 
                    plans_per_user=1, 
                    posts_per_plan=5, 
                    schedule_percentage=80)
        
        # Check that posts were created
        posts = PostContent.objects.all()
        self.assertGreaterEqual(posts.count(), 5)
        
        # Check that some posts were scheduled (80% of 5 = 4)
        scheduled_posts = PostSchedule.objects.all()
        self.assertGreaterEqual(scheduled_posts.count(), 3)
        
        # Check post properties
        post = posts.first()
        self.assertIsNotNone(post.title)
        self.assertIsNotNone(post.content)
        self.assertIn(post.post_type, ['tips', 'behind_scenes', 'motivational', 'product', 'educational'])
    
    def test_generate_test_data_respects_parameters(self):
        """Test that generate_test_data respects all parameters"""
        # Clear existing data
        User.objects.filter(username__startswith='testuser').delete()
        
        # Run with specific parameters
        call_command('generate_test_data',
                    users=2,
                    plans_per_user=3,
                    posts_per_plan=4,
                    schedule_percentage=50)
        
        # Verify users
        users = User.objects.filter(username__startswith='testuser')
        self.assertEqual(users.count(), 2)
        
        # Verify plans (2 users * 3 plans = 6 plans)
        plans = PostingPlan.objects.filter(user__in=users)
        self.assertEqual(plans.count(), 6)
        
        # Verify posts (6 plans * 4 posts = 24 posts)
        posts = PostContent.objects.filter(posting_plan__in=plans)
        self.assertEqual(posts.count(), 24)
        
        # Verify schedules (approximately 50% of 24 = ~12)
        schedules = PostSchedule.objects.filter(post_content__in=posts)
        self.assertGreaterEqual(schedules.count(), 10)
        self.assertLessEqual(schedules.count(), 14)


class ExportDataCommandTest(TestCase):
    """Test export_data management command"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
        
        # Create test data
        self.plan = PostingPlan.objects.create(
            title='Export Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        self.post = PostContent.objects.create(
            posting_plan=self.plan,
            title='Export Test Post',
            content='Export test content'
        )
    
    def test_export_data_json_format(self):
        """Test data export in JSON format"""
        out = StringIO()
        call_command('export_data', format='json', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Export Test Plan', output)
        self.assertIn('Export Test Post', output)
        
        # Verify it's valid JSON
        import json
        try:
            data = json.loads(output)
            self.assertIn('plans', data)
            self.assertIn('posts', data)
        except json.JSONDecodeError:
            self.fail("Output is not valid JSON")
    
    def test_export_data_csv_format(self):
        """Test data export in CSV format"""
        out = StringIO()
        call_command('export_data', format='csv', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Export Test Plan', output)
        self.assertIn('Export Test Post', output)
        
        # Check CSV headers
        lines = output.strip().split('\n')
        self.assertGreater(len(lines), 1)  # Should have headers + data
    
    def test_export_data_user_filter(self):
        """Test data export with user filter"""
        # Create another user with data
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        other_plan = PostingPlan.objects.create(
            title='Other User Plan',
            user=other_user,
            platform=self.platform,
            user_profile='Other profile',
            target_audience='Other audience',
            goals='Other goals',
            vision='Other vision'
        )
        
        # Export only testuser's data
        out = StringIO()
        call_command('export_data', user='testuser', format='json', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Export Test Plan', output)
        self.assertNotIn('Other User Plan', output)


class CommandErrorHandlingTest(TestCase):
    """Test command error handling"""
    
    def test_invalid_command_arguments(self):
        """Test handling of invalid command arguments"""
        # Test cleanup_old_schedules with invalid days
        with self.assertRaises(CommandError):
            call_command('cleanup_old_schedules', days=-1)
        
        # Test generate_test_data with invalid parameters
        with self.assertRaises(CommandError):
            call_command('generate_test_data', users=0)
        
        with self.assertRaises(CommandError):
            call_command('generate_test_data', schedule_percentage=150)
    
    def test_export_data_invalid_format(self):
        """Test export_data with invalid format"""
        with self.assertRaises(CommandError):
            call_command('export_data', format='invalid')
    
    def test_export_data_invalid_user(self):
        """Test export_data with non-existent user"""
        with self.assertRaises(CommandError):
            call_command('export_data', user='nonexistent')


class CommandOutputTest(TestCase):
    """Test command output and verbosity"""
    
    def test_command_verbosity_levels(self):
        """Test different verbosity levels"""
        # Test quiet mode
        out = StringIO()
        call_command('setup_platforms', verbosity=0, stdout=out)
        self.assertEqual(out.getvalue().strip(), '')
        
        # Test normal mode
        out = StringIO()
        call_command('setup_platforms', verbosity=1, stdout=out)
        self.assertGreater(len(out.getvalue()), 0)
        
        # Test verbose mode
        out = StringIO()
        call_command('setup_platforms', verbosity=2, stdout=out)
        verbose_output = out.getvalue()
        
        # Verbose should contain more information
        self.assertGreater(len(verbose_output), 0)
    
    def test_command_help_text(self):
        """Test that commands have proper help text"""
        from django.core.management import get_commands, load_command_class
        
        somi_plan_commands = [
            'setup_platforms',
            'setup_templates', 
            'cleanup_old_schedules',
            'generate_test_data',
            'export_data'
        ]
        
        available_commands = get_commands()
        
        for command_name in somi_plan_commands:
            if command_name in available_commands:
                command_class = load_command_class('somi_plan', command_name)
                self.assertIsNotNone(command_class.help)
                self.assertGreater(len(command_class.help), 0)