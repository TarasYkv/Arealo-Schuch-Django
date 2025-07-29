"""
Tests for SoMi-Plan forms
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import date, time, timedelta

from somi_plan.models import Platform, PostingPlan, PostContent, PostSchedule
from somi_plan.forms import Step1Form, Step2StrategyForm, PostContentForm, PostScheduleForm


class Step1FormTest(TestCase):
    """Test Step1Form (Basic Setup)"""
    
    def setUp(self):
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200,
            is_active=True
        )
        self.valid_data = {
            'title': 'Test Marketing Plan',
            'platform': self.platform.id,
            'user_profile': 'Social Media Manager at Tech Company',
            'target_audience': 'Tech enthusiasts and professionals aged 25-40',
            'goals': 'Increase brand awareness and drive website traffic',
            'vision': 'Become the leading voice in tech innovation on social media'
        }
    
    def test_step1_form_valid_data(self):
        """Test Step1Form with valid data"""
        form = Step1Form(data=self.valid_data)
        self.assertTrue(form.is_valid())
    
    def test_step1_form_missing_required_fields(self):
        """Test Step1Form with missing required fields"""
        # Missing title
        data = {**self.valid_data}
        del data['title']
        form = Step1Form(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        
        # Missing platform
        data = {**self.valid_data}
        del data['platform']
        form = Step1Form(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('platform', form.errors)
        
        # Missing user_profile
        data = {**self.valid_data}
        del data['user_profile']
        form = Step1Form(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('user_profile', form.errors)
    
    def test_step1_form_field_max_lengths(self):
        """Test Step1Form field max lengths"""
        # Title too long (over 200 chars)
        data = {**self.valid_data, 'title': 'x' * 201}
        form = Step1Form(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_step1_form_platform_queryset(self):
        """Test Step1Form platform queryset includes only active platforms"""
        # Create inactive platform
        inactive_platform = Platform.objects.create(
            name='Inactive Platform',
            icon='fab fa-test',
            color='#000000',
            character_limit=100,
            is_active=False
        )
        
        form = Step1Form()
        platform_choices = [choice[0] for choice in form.fields['platform'].choices if choice[0]]
        
        self.assertIn(self.platform.id, platform_choices)
        self.assertNotIn(inactive_platform.id, platform_choices)
    
    def test_step1_form_save(self):
        """Test Step1Form save method"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        form = Step1Form(data=self.valid_data)
        self.assertTrue(form.is_valid())
        
        plan = form.save(commit=False)
        plan.user = user
        plan.save()
        
        self.assertEqual(plan.title, 'Test Marketing Plan')
        self.assertEqual(plan.platform, self.platform)
        self.assertEqual(plan.user, user)
        self.assertEqual(plan.status, 'draft')  # Default status


class Step2StrategyFormTest(TestCase):
    """Test Step2StrategyForm (Strategy Development)"""
    
    def setUp(self):
        self.valid_data = {
            'use_ai_strategy': False,
            'posting_frequency': 'daily',
            'best_times': '09:00,18:00',
            'content_types': 'tips,behind_scenes',
            'cross_platform': True,
            'additional_notes': 'Focus on engagement and community building'
        }
    
    def test_step2_form_valid_data(self):
        """Test Step2StrategyForm with valid data"""
        form = Step2StrategyForm(data=self.valid_data)
        self.assertTrue(form.is_valid())
    
    def test_step2_form_ai_strategy_enabled(self):
        """Test Step2StrategyForm with AI strategy enabled"""
        data = {**self.valid_data, 'use_ai_strategy': True}
        form = Step2StrategyForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['use_ai_strategy'])
    
    def test_step2_form_posting_frequency_choices(self):
        """Test Step2StrategyForm posting frequency choices"""
        valid_frequencies = ['daily', 'twice_daily', 'every_other_day', 'weekly', 'twice_weekly']
        
        for frequency in valid_frequencies:
            data = {**self.valid_data, 'posting_frequency': frequency}
            form = Step2StrategyForm(data=data)
            self.assertTrue(form.is_valid())
        
        # Invalid frequency
        data = {**self.valid_data, 'posting_frequency': 'invalid'}
        form = Step2StrategyForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('posting_frequency', form.errors)
    
    def test_step2_form_best_times_validation(self):
        """Test Step2StrategyForm best_times field validation"""
        # Valid times
        valid_times = ['09:00', '09:00,18:00', '08:00,12:00,18:00']
        
        for times in valid_times:
            data = {**self.valid_data, 'best_times': times}
            form = Step2StrategyForm(data=data)
            self.assertTrue(form.is_valid())
        
        # Invalid time format
        data = {**self.valid_data, 'best_times': '25:00'}
        form = Step2StrategyForm(data=data)
        self.assertFalse(form.is_valid())
    
    def test_step2_form_content_types_validation(self):
        """Test Step2StrategyForm content_types field validation"""
        # Valid content types
        valid_types = ['tips', 'tips,behind_scenes', 'motivational,product,educational']
        
        for types in valid_types:
            data = {**self.valid_data, 'content_types': types}
            form = Step2StrategyForm(data=data)
            self.assertTrue(form.is_valid())
    
    def test_step2_form_cross_platform_boolean(self):
        """Test Step2StrategyForm cross_platform boolean field"""
        # Test True
        data = {**self.valid_data, 'cross_platform': True}
        form = Step2StrategyForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['cross_platform'])
        
        # Test False
        data = {**self.valid_data, 'cross_platform': False}
        form = Step2StrategyForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['cross_platform'])
    
    def test_step2_form_optional_fields(self):
        """Test Step2StrategyForm with optional fields empty"""
        # Only required fields
        minimal_data = {
            'use_ai_strategy': False,
            'posting_frequency': 'daily'
        }
        
        form = Step2StrategyForm(data=minimal_data)
        self.assertTrue(form.is_valid())


class PostContentFormTest(TestCase):
    """Test PostContentForm"""
    
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
        self.valid_data = {
            'title': 'Test Post Title',
            'content': 'This is a test post about social media marketing tips.',
            'hashtags': '#socialmedia #marketing #tips #business',
            'call_to_action': 'What are your favorite marketing tips? Share below!',
            'script': 'Additional implementation notes for this post',
            'post_type': 'tips',
            'priority': 2
        }
    
    def test_post_content_form_valid_data(self):
        """Test PostContentForm with valid data"""
        form = PostContentForm(data=self.valid_data)
        self.assertTrue(form.is_valid())
    
    def test_post_content_form_required_fields(self):
        """Test PostContentForm required fields"""
        # Missing title
        data = {**self.valid_data}
        del data['title']
        form = PostContentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        
        # Missing content
        data = {**self.valid_data}
        del data['content']
        form = PostContentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)
    
    def test_post_content_form_post_type_choices(self):
        """Test PostContentForm post_type choices"""
        valid_types = ['tips', 'behind_scenes', 'motivational', 'product', 'news', 'educational', 'entertainment']
        
        for post_type in valid_types:
            data = {**self.valid_data, 'post_type': post_type}
            form = PostContentForm(data=data)
            self.assertTrue(form.is_valid())
        
        # Invalid post type
        data = {**self.valid_data, 'post_type': 'invalid'}
        form = PostContentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('post_type', form.errors)
    
    def test_post_content_form_priority_choices(self):
        """Test PostContentForm priority choices"""
        valid_priorities = [1, 2, 3]
        
        for priority in valid_priorities:
            data = {**self.valid_data, 'priority': priority}
            form = PostContentForm(data=data)
            self.assertTrue(form.is_valid())
        
        # Invalid priority
        data = {**self.valid_data, 'priority': 0}
        form = PostContentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('priority', form.errors)
        
        data = {**self.valid_data, 'priority': 4}
        form = PostContentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('priority', form.errors)
    
    def test_post_content_form_character_count_validation(self):
        """Test PostContentForm character count considerations"""
        # Create platform with small character limit
        small_platform = Platform.objects.create(
            name='Twitter',
            icon='fab fa-twitter',
            color='#1DA1F2',
            character_limit=280
        )
        
        # Content over limit - form should still be valid but warn user
        long_content = 'x' * 300
        data = {**self.valid_data, 'content': long_content}
        form = PostContentForm(data=data)
        self.assertTrue(form.is_valid())  # Form validation doesn't enforce platform limits
    
    def test_post_content_form_optional_fields(self):
        """Test PostContentForm with optional fields empty"""
        minimal_data = {
            'title': 'Minimal Post',
            'content': 'Just the basics.',
            'post_type': 'tips',
            'priority': 2
        }
        
        form = PostContentForm(data=minimal_data)
        self.assertTrue(form.is_valid())
    
    def test_post_content_form_save(self):
        """Test PostContentForm save method"""
        form = PostContentForm(data=self.valid_data)
        self.assertTrue(form.is_valid())
        
        post = form.save(commit=False)
        post.posting_plan = self.plan
        post.save()
        
        self.assertEqual(post.title, 'Test Post Title')
        self.assertEqual(post.posting_plan, self.plan)
        self.assertEqual(post.post_type, 'tips')
        self.assertEqual(post.priority, 2)


class PostScheduleFormTest(TestCase):
    """Test PostScheduleForm"""
    
    def setUp(self):
        self.valid_data = {
            'scheduled_date': date.today() + timedelta(days=1),
            'scheduled_time': time(14, 30),
            'notes': 'Remember to check engagement after posting',
            'status': 'scheduled'
        }
    
    def test_post_schedule_form_valid_data(self):
        """Test PostScheduleForm with valid data"""
        form = PostScheduleForm(data=self.valid_data)
        self.assertTrue(form.is_valid())
    
    def test_post_schedule_form_required_fields(self):
        """Test PostScheduleForm required fields"""
        # Missing scheduled_date
        data = {**self.valid_data}
        del data['scheduled_date']
        form = PostScheduleForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('scheduled_date', form.errors)
        
        # Missing scheduled_time
        data = {**self.valid_data}
        del data['scheduled_time']
        form = PostScheduleForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('scheduled_time', form.errors)
    
    def test_post_schedule_form_date_validation(self):
        """Test PostScheduleForm date validation"""
        # Past date - should be allowed by form (business logic might prevent it)
        data = {**self.valid_data, 'scheduled_date': date.today() - timedelta(days=1)}
        form = PostScheduleForm(data=data)
        self.assertTrue(form.is_valid())  # Form doesn't enforce future dates
        
        # Future date
        data = {**self.valid_data, 'scheduled_date': date.today() + timedelta(days=7)}
        form = PostScheduleForm(data=data)
        self.assertTrue(form.is_valid())
    
    def test_post_schedule_form_time_validation(self):
        """Test PostScheduleForm time validation"""
        # Valid times
        valid_times = [time(0, 0), time(12, 30), time(23, 59)]
        
        for test_time in valid_times:
            data = {**self.valid_data, 'scheduled_time': test_time}
            form = PostScheduleForm(data=data)
            self.assertTrue(form.is_valid())
    
    def test_post_schedule_form_status_choices(self):
        """Test PostScheduleForm status choices"""
        valid_statuses = ['scheduled', 'completed', 'failed', 'cancelled']
        
        for status in valid_statuses:
            data = {**self.valid_data, 'status': status}
            form = PostScheduleForm(data=data)
            self.assertTrue(form.is_valid())
        
        # Invalid status
        data = {**self.valid_data, 'status': 'invalid'}
        form = PostScheduleForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('status', form.errors)
    
    def test_post_schedule_form_optional_fields(self):
        """Test PostScheduleForm with optional fields empty"""
        minimal_data = {
            'scheduled_date': date.today() + timedelta(days=1),
            'scheduled_time': time(14, 30)
        }
        
        form = PostScheduleForm(data=minimal_data)
        self.assertTrue(form.is_valid())
    
    def test_post_schedule_form_save(self):
        """Test PostScheduleForm save method"""
        # Create necessary objects
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200
        )
        plan = PostingPlan.objects.create(
            title='Test Plan',
            user=user,
            platform=platform,
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
        
        form = PostScheduleForm(data=self.valid_data)
        self.assertTrue(form.is_valid())
        
        schedule = form.save(commit=False)
        schedule.post_content = post
        schedule.save()
        
        self.assertEqual(schedule.scheduled_date, self.valid_data['scheduled_date'])
        self.assertEqual(schedule.scheduled_time, self.valid_data['scheduled_time'])
        self.assertEqual(schedule.notes, self.valid_data['notes'])
        self.assertEqual(schedule.post_content, post)


class FormIntegrationTest(TestCase):
    """Test form integrations and workflows"""
    
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
            character_limit=2200,
            is_active=True
        )
    
    def test_complete_form_workflow(self):
        """Test complete workflow using all forms"""
        # Step 1: Create plan
        step1_data = {
            'title': 'Integration Test Plan',
            'platform': self.platform.id,
            'user_profile': 'Social Media Manager',
            'target_audience': 'Tech professionals',
            'goals': 'Increase engagement',
            'vision': 'Industry thought leader'
        }
        
        step1_form = Step1Form(data=step1_data)
        self.assertTrue(step1_form.is_valid())
        
        plan = step1_form.save(commit=False)
        plan.user = self.user
        plan.save()
        
        # Step 2: Set strategy
        step2_data = {
            'use_ai_strategy': False,
            'posting_frequency': 'daily',
            'best_times': '09:00,18:00',
            'content_types': 'tips,educational',
            'cross_platform': False,
            'additional_notes': 'Focus on quality content'
        }
        
        step2_form = Step2StrategyForm(data=step2_data)
        self.assertTrue(step2_form.is_valid())
        
        # Step 3: Create content
        content_data = {
            'title': 'Great Marketing Tip',
            'content': 'Here is an amazing tip for better social media engagement.',
            'hashtags': '#marketing #tips #socialmedia',
            'call_to_action': 'Try this tip and let us know how it works!',
            'post_type': 'tips',
            'priority': 1
        }
        
        content_form = PostContentForm(data=content_data)
        self.assertTrue(content_form.is_valid())
        
        post = content_form.save(commit=False)
        post.posting_plan = plan
        post.save()
        
        # Step 4: Schedule post
        schedule_data = {
            'scheduled_date': date.today() + timedelta(days=1),
            'scheduled_time': time(9, 0),
            'notes': 'Post during peak engagement time',
            'status': 'scheduled'
        }
        
        schedule_form = PostScheduleForm(data=schedule_data)
        self.assertTrue(schedule_form.is_valid())
        
        schedule = schedule_form.save(commit=False)
        schedule.post_content = post
        schedule.save()
        
        # Verify complete workflow
        self.assertEqual(plan.title, 'Integration Test Plan')
        self.assertEqual(plan.get_post_count(), 1)
        self.assertEqual(plan.get_scheduled_count(), 1)
        self.assertEqual(post.title, 'Great Marketing Tip')
        self.assertEqual(schedule.scheduled_time, time(9, 0))
    
    def test_form_validation_consistency(self):
        """Test that form validation is consistent with model validation"""
        # Test that invalid model data also fails form validation
        
        # Invalid platform (inactive)
        inactive_platform = Platform.objects.create(
            name='Inactive Platform',
            icon='fab fa-test',
            color='#000000',
            character_limit=100,
            is_active=False
        )
        
        step1_data = {
            'title': 'Test Plan',
            'platform': inactive_platform.id,
            'user_profile': 'Test profile',
            'target_audience': 'Test audience',
            'goals': 'Test goals',
            'vision': 'Test vision'
        }
        
        form = Step1Form(data=step1_data)
        self.assertFalse(form.is_valid())  # Should fail because platform is inactive
    
    def test_form_error_messages(self):
        """Test that forms provide helpful error messages"""
        # Empty form
        form = Step1Form(data={})
        self.assertFalse(form.is_valid())
        
        # Check that error messages are present for required fields
        required_fields = ['title', 'platform', 'user_profile', 'target_audience', 'goals', 'vision']
        for field in required_fields:
            self.assertIn(field, form.errors)
            self.assertTrue(len(form.errors[field]) > 0)
    
    def test_form_field_widgets(self):
        """Test that forms use appropriate widgets"""
        # Step1Form
        step1_form = Step1Form()
        self.assertEqual(step1_form.fields['user_profile'].widget.__class__.__name__, 'Textarea')
        self.assertEqual(step1_form.fields['target_audience'].widget.__class__.__name__, 'Textarea')
        
        # PostContentForm
        content_form = PostContentForm()
        self.assertEqual(content_form.fields['content'].widget.__class__.__name__, 'Textarea')
        self.assertEqual(content_form.fields['script'].widget.__class__.__name__, 'Textarea')
        
        # PostScheduleForm
        schedule_form = PostScheduleForm()
        self.assertEqual(schedule_form.fields['scheduled_date'].widget.__class__.__name__, 'DateInput')
        self.assertEqual(schedule_form.fields['scheduled_time'].widget.__class__.__name__, 'TimeInput')


class FormSecurityTest(TestCase):
    """Test form security and data validation"""
    
    def setUp(self):
        self.platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200,
            is_active=True
        )
    
    def test_form_xss_protection(self):
        """Test that forms handle potentially malicious input"""
        malicious_script = '<script>alert("XSS")</script>'
        
        # Step1Form
        data = {
            'title': malicious_script,
            'platform': self.platform.id,
            'user_profile': malicious_script,
            'target_audience': 'Normal audience',
            'goals': 'Normal goals',
            'vision': 'Normal vision'
        }
        
        form = Step1Form(data=data)
        self.assertTrue(form.is_valid())  # Form should accept the data
        
        # The template rendering should escape the script tags
        cleaned_title = form.cleaned_data['title']
        self.assertEqual(cleaned_title, malicious_script)  # Data preserved as-is
    
    def test_form_sql_injection_protection(self):
        """Test that forms handle SQL injection attempts"""
        sql_injection = "'; DROP TABLE somi_plan_postingplan; --"
        
        data = {
            'title': sql_injection,
            'platform': self.platform.id,
            'user_profile': 'Normal profile',
            'target_audience': 'Normal audience',
            'goals': 'Normal goals',
            'vision': 'Normal vision'
        }
        
        form = Step1Form(data=data)
        self.assertTrue(form.is_valid())  # Django ORM protects against SQL injection
        
        cleaned_title = form.cleaned_data['title']
        self.assertEqual(cleaned_title, sql_injection)  # Data preserved as-is
    
    def test_form_data_length_limits(self):
        """Test that forms respect database field length limits"""
        # Test title length limit (200 chars)
        long_title = 'x' * 201
        data = {
            'title': long_title,
            'platform': self.platform.id,
            'user_profile': 'Normal profile',
            'target_audience': 'Normal audience',
            'goals': 'Normal goals',
            'vision': 'Normal vision'
        }
        
        form = Step1Form(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)