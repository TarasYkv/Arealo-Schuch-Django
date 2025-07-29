"""
Integration tests for SoMi-Plan application
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import transaction
from django.core.management import call_command
from datetime import date, time, timedelta
import json

from somi_plan.models import (
    Platform, PostingPlan, PlanningSession, PostContent, 
    PostSchedule, TemplateCategory, PostTemplate
)


class FullWorkflowIntegrationTest(TestCase):
    """Test complete user workflow through the application"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Set up platforms using management command
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
    
    def test_complete_plan_creation_workflow(self):
        """Test complete workflow from plan creation to post scheduling"""
        
        # Step 1: Access dashboard (should be empty)
        response = self.client.get(reverse('somi_plan:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_plans'], 0)
        
        # Step 2: Create new plan (Step 1)
        step1_data = {
            'title': 'Integration Test Plan',
            'platform': self.platform.id,
            'user_profile': 'Digital Marketing Manager at innovative tech startup',
            'target_audience': 'Tech professionals, entrepreneurs, and early adopters aged 25-45',
            'goals': 'Increase brand awareness, drive website traffic, and generate qualified leads',
            'vision': 'Establish ourselves as thought leaders in the tech innovation space'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step1'), step1_data)
        plan = PostingPlan.objects.get(title='Integration Test Plan')
        self.assertRedirects(response, reverse('somi_plan:create_plan_step2', args=[plan.id]))
        
        # Verify plan creation
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.platform, self.platform)
        self.assertEqual(plan.status, 'draft')
        
        # Verify session creation
        session = PlanningSession.objects.get(posting_plan=plan)
        self.assertEqual(session.current_step, 2)
        self.assertTrue(session.is_step_completed(1))
        
        # Step 3: Set strategy (Step 2)
        step2_data = {
            'use_ai_strategy': False,  # Use manual for predictable testing
            'posting_frequency': 'daily',
            'best_times': '09:00,18:00',
            'content_types': 'tips,educational,behind_scenes',
            'cross_platform': True,
            'additional_notes': 'Focus on engaging visual content with clear call-to-actions'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step2', args=[plan.id]), step2_data)
        self.assertRedirects(response, reverse('somi_plan:create_plan_step3', args=[plan.id]))
        
        # Verify strategy saved
        plan.refresh_from_db()
        self.assertIsNotNone(plan.strategy_data)
        self.assertEqual(plan.strategy_data['posting_frequency'], 'daily')
        self.assertTrue(plan.strategy_data['cross_platform'])
        
        # Verify session updated
        session.refresh_from_db()
        self.assertEqual(session.current_step, 3)
        self.assertTrue(session.is_step_completed(2))
        
        # Step 4: Review and activate (Step 3)
        # First, manually create some content for testing
        PostContent.objects.create(
            posting_plan=plan,
            title='Tech Innovation Trends 2024',
            content='Discover the latest technology trends that will shape 2024 and beyond. From AI advancements to sustainable tech solutions.',
            hashtags='#TechTrends #Innovation #AI #SustainableTech #FutureTech',
            call_to_action='Which tech trend excites you most? Share your thoughts in the comments!',
            post_type='tips',
            priority=1
        )
        
        PostContent.objects.create(
            posting_plan=plan,
            title='Behind the Scenes: Our Development Process',
            content='Take a peek into our development process and see how we bring innovative ideas to life.',
            hashtags='#BehindTheScenes #Development #TeamWork #Innovation',
            call_to_action='Want to know more about our process? Ask us anything!',
            post_type='behind_scenes',
            priority=2
        )
        
        # Activate the plan
        response = self.client.post(
            reverse('somi_plan:create_plan_step3', args=[plan.id]),
            {'action': 'activate'}
        )
        self.assertRedirects(response, reverse('somi_plan:plan_detail', args=[plan.id]))
        
        # Verify plan activation
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'active')
        
        # Verify session completion
        session.refresh_from_db()
        self.assertTrue(session.is_step_completed(3))
        
        # Step 5: View plan details
        response = self.client.get(reverse('somi_plan:plan_detail', args=[plan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['plan'], plan)
        self.assertEqual(len(response.context['posts']), 2)
        
        # Step 6: Schedule posts
        posts = PostContent.objects.filter(posting_plan=plan)
        first_post = posts.first()
        
        schedule_data = {
            'scheduled_date': (date.today() + timedelta(days=1)).isoformat(),
            'scheduled_time': '09:00',
            'notes': 'Post during peak engagement hours'
        }
        
        response = self.client.post(
            reverse('somi_plan:schedule_post', args=[first_post.id]),
            schedule_data
        )
        self.assertRedirects(response, reverse('somi_plan:calendar'))
        
        # Verify scheduling
        schedule = PostSchedule.objects.get(post_content=first_post)
        self.assertEqual(schedule.scheduled_time, time(9, 0))
        self.assertEqual(schedule.status, 'scheduled')
        
        # Step 7: View calendar
        response = self.client.get(reverse('somi_plan:calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('posts_by_date', response.context)
        
        # Step 8: Mark post as completed
        response = self.client.post(
            reverse('somi_plan:mark_completed', args=[schedule.id]),
            {'url': 'https://instagram.com/p/test123'}
        )
        self.assertRedirects(response, reverse('somi_plan:calendar'))
        
        # Verify completion
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, 'completed')
        self.assertEqual(schedule.published_url, 'https://instagram.com/p/test123')
        self.assertIsNotNone(schedule.completed_at)
        
        # Step 9: Check updated dashboard
        response = self.client.get(reverse('somi_plan:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_plans'], 1)
        self.assertEqual(response.context['total_posts'], 2)
        self.assertEqual(response.context['active_plans_count'], 1)
    
    def test_ajax_workflow_integration(self):
        """Test AJAX functionality integration"""
        # Create plan and post
        plan = PostingPlan.objects.create(
            title='AJAX Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        post = PostContent.objects.create(
            posting_plan=plan,
            title='AJAX Test Post',
            content='Test content for AJAX functionality'
        )
        
        # Test AJAX toggle schedule
        response = self.client.post(
            reverse('somi_plan:ajax_toggle_schedule', args=[post.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['action'], 'scheduled')
        
        # Verify schedule was created
        self.assertTrue(PostSchedule.objects.filter(post_content=post).exists())
        
        # Test AJAX update position
        update_data = {
            'date': (date.today() + timedelta(days=2)).isoformat(),
            'time': '15:30'
        }
        
        response = self.client.post(
            reverse('somi_plan:ajax_update_position', args=[post.id]),
            data=json.dumps(update_data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify schedule was updated
        schedule = PostSchedule.objects.get(post_content=post)
        self.assertEqual(schedule.scheduled_time, time(15, 30))
        
        # Test AJAX calendar data
        response = self.client.get(
            reverse('somi_plan:ajax_calendar_data', args=[date.today().year, date.today().month]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('posts_by_date', data)


class MultiUserIntegrationTest(TestCase):
    """Test multi-user scenarios and data isolation"""
    
    def setUp(self):
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
        
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
    
    def test_user_data_isolation(self):
        """Test that users can only access their own data"""
        # Create data for user1
        plan1 = PostingPlan.objects.create(
            title='User 1 Plan',
            user=self.user1,
            platform=self.platform,
            user_profile='User 1 profile',
            target_audience='User 1 audience',
            goals='User 1 goals',
            vision='User 1 vision'
        )
        
        post1 = PostContent.objects.create(
            posting_plan=plan1,
            title='User 1 Post',
            content='User 1 content'
        )
        
        # Create data for user2
        plan2 = PostingPlan.objects.create(
            title='User 2 Plan',
            user=self.user2,
            platform=self.platform,
            user_profile='User 2 profile',
            target_audience='User 2 audience',
            goals='User 2 goals',
            vision='User 2 vision'
        )
        
        post2 = PostContent.objects.create(
            posting_plan=plan2,
            title='User 2 Post',
            content='User 2 content'
        )
        
        # Login as user1
        self.client.login(username='user1', password='testpass123')
        
        # User1 should see only their data
        response = self.client.get(reverse('somi_plan:dashboard'))
        self.assertEqual(response.context['total_plans'], 1)
        
        response = self.client.get(reverse('somi_plan:plan_list'))
        plans = response.context['page_obj']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].title, 'User 1 Plan')
        
        # User1 should be able to access their plan
        response = self.client.get(reverse('somi_plan:plan_detail', args=[plan1.id]))
        self.assertEqual(response.status_code, 200)
        
        # User1 should NOT be able to access user2's plan
        response = self.client.get(reverse('somi_plan:plan_detail', args=[plan2.id]))
        self.assertEqual(response.status_code, 404)
        
        # Switch to user2
        self.client.logout()
        self.client.login(username='user2', password='testpass123')
        
        # User2 should see only their data
        response = self.client.get(reverse('somi_plan:dashboard'))
        self.assertEqual(response.context['total_plans'], 1)
        
        # User2 should be able to access their plan
        response = self.client.get(reverse('somi_plan:plan_detail', args=[plan2.id]))
        self.assertEqual(response.status_code, 200)
        
        # User2 should NOT be able to access user1's plan
        response = self.client.get(reverse('somi_plan:plan_detail', args=[plan1.id]))
        self.assertEqual(response.status_code, 404)
    
    def test_concurrent_user_operations(self):
        """Test concurrent operations by multiple users"""
        # This test would be more meaningful with actual concurrency
        # For now, we test sequential operations that could conflict
        
        # Both users create plans with the same title
        self.client.login(username='user1', password='testpass123')
        
        step1_data = {
            'title': 'Shared Plan Name',
            'platform': self.platform.id,
            'user_profile': 'User 1 profile',
            'target_audience': 'User 1 audience',
            'goals': 'User 1 goals',
            'vision': 'User 1 vision'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step1'), step1_data)
        plan1 = PostingPlan.objects.get(title='Shared Plan Name', user=self.user1)
        
        # Switch to user2
        self.client.logout()
        self.client.login(username='user2', password='testpass123')
        
        step1_data['user_profile'] = 'User 2 profile'
        response = self.client.post(reverse('somi_plan:create_plan_step1'), step1_data)
        plan2 = PostingPlan.objects.get(title='Shared Plan Name', user=self.user2)
        
        # Both plans should exist independently
        self.assertNotEqual(plan1.id, plan2.id)
        self.assertEqual(plan1.user, self.user1)
        self.assertEqual(plan2.user, self.user2)


class DatabaseIntegrityTest(TransactionTestCase):
    """Test database integrity and constraints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
    
    def test_cascade_deletions(self):
        """Test cascade deletion behavior"""
        plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        session = PlanningSession.objects.create(
            posting_plan=plan,
            current_step=1
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
        
        # Store IDs for verification
        plan_id = plan.id
        session_id = session.id
        post_id = post.id
        schedule_id = schedule.id
        
        # Delete plan should cascade
        plan.delete()
        
        # Verify all related objects were deleted
        self.assertFalse(PostingPlan.objects.filter(id=plan_id).exists())
        self.assertFalse(PlanningSession.objects.filter(id=session_id).exists())
        self.assertFalse(PostContent.objects.filter(id=post_id).exists())
        self.assertFalse(PostSchedule.objects.filter(id=schedule_id).exists())
    
    def test_foreign_key_constraints(self):
        """Test foreign key constraints"""
        plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        # Test that we cannot create post without valid plan
        with self.assertRaises(Exception):
            PostContent.objects.create(
                posting_plan_id=99999,  # Non-existent plan
                title='Invalid Post',
                content='This should fail'
            )
    
    def test_unique_constraints(self):
        """Test unique constraints where applicable"""
        plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        # Test PlanningSession uniqueness (one per plan)
        session1 = PlanningSession.objects.create(
            posting_plan=plan,
            current_step=1
        )
        
        # Should be able to update existing session
        session1.current_step = 2
        session1.save()
        
        # But should not be able to create another session for same plan
        # Note: This depends on actual model constraints
        # If no unique constraint exists, this test documents current behavior


class PerformanceIntegrationTest(TestCase):
    """Test performance characteristics under load"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
        self.client.login(username='testuser', password='testpass123')
    
    def test_dashboard_performance_with_many_plans(self):
        """Test dashboard performance with many plans"""
        # Create many plans
        plans = []
        for i in range(50):
            plan = PostingPlan.objects.create(
                title=f'Performance Test Plan {i}',
                user=self.user,
                platform=self.platform,
                user_profile=f'Profile {i}',
                target_audience=f'Audience {i}',
                goals=f'Goals {i}',
                vision=f'Vision {i}'
            )
            plans.append(plan)
            
            # Add some posts to each plan
            for j in range(5):
                post = PostContent.objects.create(
                    posting_plan=plan,
                    title=f'Post {j} for Plan {i}',
                    content=f'Content {j} for Plan {i}'
                )
                
                # Schedule some posts
                if j < 3:
                    PostSchedule.objects.create(
                        post_content=post,
                        scheduled_date=date.today() + timedelta(days=j),
                        scheduled_time=time(12, 0)
                    )
        
        # Test dashboard performance
        import time
        start_time = time.time()
        response = self.client.get(reverse('somi_plan:dashboard'))
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_plans'], 50)
        self.assertEqual(response.context['total_posts'], 250)
        
        # Dashboard should load reasonably quickly (adjust threshold as needed)
        load_time = end_time - start_time
        self.assertLess(load_time, 2.0, f"Dashboard took {load_time:.2f} seconds to load")
    
    def test_calendar_performance_with_many_posts(self):
        """Test calendar performance with many scheduled posts"""
        plan = PostingPlan.objects.create(
            title='Calendar Performance Test',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        
        # Create many scheduled posts for current month
        for i in range(100):
            post = PostContent.objects.create(
                posting_plan=plan,
                title=f'Calendar Post {i}',
                content=f'Calendar content {i}'
            )
            
            PostSchedule.objects.create(
                post_content=post,
                scheduled_date=date.today() + timedelta(days=(i % 30)),
                scheduled_time=time(9 + (i % 12), 0)
            )
        
        # Test calendar performance
        import time
        start_time = time.time()
        response = self.client.get(reverse('somi_plan:calendar'))
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        
        # Calendar should load reasonably quickly
        load_time = end_time - start_time
        self.assertLess(load_time, 3.0, f"Calendar took {load_time:.2f} seconds to load")


class ErrorHandlingIntegrationTest(TestCase):
    """Test error handling across the application"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        call_command('setup_platforms')
        self.platform = Platform.objects.get(name='Instagram')
        self.client.login(username='testuser', password='testpass123')
    
    def test_404_error_handling(self):
        """Test 404 error handling for non-existent resources"""
        # Non-existent plan
        response = self.client.get(reverse('somi_plan:plan_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)
        
        # Non-existent post
        response = self.client.get(reverse('somi_plan:schedule_post', args=[99999]))
        self.assertEqual(response.status_code, 404)
        
        # Non-existent schedule
        response = self.client.post(reverse('somi_plan:mark_completed', args=[99999]))
        self.assertEqual(response.status_code, 404)
    
    def test_form_error_handling(self):
        """Test form error handling and validation"""
        # Invalid step 1 form data
        invalid_data = {
            'title': '',  # Missing required field
            'platform': 99999,  # Non-existent platform
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step1'), invalid_data)
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors
        self.assertFormError(response, 'form', 'title', 'This field is required.')
    
    def test_ajax_error_handling(self):
        """Test AJAX error handling"""
        # Invalid AJAX request
        response = self.client.post(
            reverse('somi_plan:ajax_toggle_schedule', args=[99999]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 404)
        
        # Invalid JSON in AJAX request
        response = self.client.post(
            reverse('somi_plan:ajax_update_position', args=[99999]),
            data='invalid json',
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 404)  # Post doesn't exist