"""
Tests for SoMi-Plan views
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, time, date, timedelta
import json

from somi_plan.models import (
    Platform, PostingPlan, PlanningSession, PostContent, PostSchedule
)


class BaseViewTest(TestCase):
    """Base test class with common setup"""
    
    def setUp(self):
        self.client = Client()
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
        self.client.login(username='testuser', password='testpass123')


class DashboardViewTest(BaseViewTest):
    """Test dashboard view"""
    
    def test_dashboard_access_authenticated(self):
        """Test authenticated user can access dashboard"""
        response = self.client.get(reverse('somi_plan:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SoMi-Plan Dashboard')
    
    def test_dashboard_redirect_unauthenticated(self):
        """Test unauthenticated user is redirected"""
        self.client.logout()
        response = self.client.get(reverse('somi_plan:dashboard'))
        self.assertEqual(response.status_code, 302)
    
    def test_dashboard_context_empty_state(self):
        """Test dashboard context with no data"""
        response = self.client.get(reverse('somi_plan:dashboard'))
        
        self.assertEqual(response.context['total_plans'], 0)
        self.assertEqual(response.context['total_posts'], 0)
        self.assertEqual(response.context['active_plans_count'], 0)
        self.assertEqual(len(response.context['upcoming_posts']), 0)
    
    def test_dashboard_context_with_data(self):
        """Test dashboard context with existing data"""
        # Create posting plan
        plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision',
            status='active'
        )
        
        # Create posts
        post = PostContent.objects.create(
            posting_plan=plan,
            title='Test Post',
            content='Test content'
        )
        
        # Schedule post
        PostSchedule.objects.create(
            post_content=post,
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(12, 0),
            status='scheduled'
        )
        
        response = self.client.get(reverse('somi_plan:dashboard'))
        
        self.assertEqual(response.context['total_plans'], 1)
        self.assertEqual(response.context['total_posts'], 1)
        self.assertEqual(response.context['active_plans_count'], 1)
        self.assertEqual(len(response.context['upcoming_posts']), 1)


class PlanListViewTest(BaseViewTest):
    """Test plan list view"""
    
    def test_plan_list_access(self):
        """Test plan list access"""
        response = self.client.get(reverse('somi_plan:plan_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_plan_list_pagination(self):
        """Test plan list pagination"""
        # Create multiple plans
        for i in range(15):
            PostingPlan.objects.create(
                title=f'Test Plan {i}',
                user=self.user,
                platform=self.platform,
                user_profile='Test profile',
                target_audience='Test audience',
                goals='Test goals',
                vision='Test vision'
            )
        
        response = self.client.get(reverse('somi_plan:plan_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(len(response.context['page_obj']), 12)  # Default page size


class CreatePlanStep1ViewTest(BaseViewTest):
    """Test create plan step 1 view"""
    
    def test_step1_get(self):
        """Test GET request to step 1"""
        response = self.client.get(reverse('somi_plan:create_plan_step1'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertContains(response, 'platforms')
    
    def test_step1_post_valid(self):
        """Test valid POST to step 1"""
        data = {
            'title': 'Test Plan',
            'platform': self.platform.id,
            'user_profile': 'Social Media Manager',
            'target_audience': 'Tech professionals',
            'goals': 'Increase engagement',
            'vision': 'Industry leader'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step1'), data)
        
        # Should redirect to step 2
        plan = PostingPlan.objects.get(title='Test Plan')
        self.assertRedirects(response, reverse('somi_plan:create_plan_step2', args=[plan.id]))
        
        # Check plan was created
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.platform, self.platform)
        
        # Check session was created
        session = PlanningSession.objects.get(posting_plan=plan)
        self.assertEqual(session.current_step, 2)
        self.assertTrue(session.is_step_completed(1))
    
    def test_step1_post_invalid(self):
        """Test invalid POST to step 1"""
        data = {
            'title': '',  # Missing required field
            'platform': self.platform.id
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step1'), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertFormError(response, 'form', 'title', 'This field is required.')


class CreatePlanStep2ViewTest(BaseViewTest):
    """Test create plan step 2 view"""
    
    def setUp(self):
        super().setUp()
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
        self.session = PlanningSession.objects.create(
            posting_plan=self.plan,
            current_step=2
        )
        self.session.complete_step(1)
    
    def test_step2_get(self):
        """Test GET request to step 2"""
        response = self.client.get(reverse('somi_plan:create_plan_step2', args=[self.plan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertEqual(response.context['plan'], self.plan)
    
    def test_step2_post_manual_strategy(self):
        """Test POST with manual strategy"""
        data = {
            'use_ai_strategy': False,
            'posting_frequency': 'daily',
            'best_times': '09:00,18:00',
            'content_types': 'tips,behind_scenes',
            'cross_platform': True,
            'additional_notes': 'Focus on engagement'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step2', args=[self.plan.id]), data)
        
        # Should redirect to step 3
        self.assertRedirects(response, reverse('somi_plan:create_plan_step3', args=[self.plan.id]))
        
        # Check strategy was saved
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.strategy_data)
        self.assertEqual(self.plan.strategy_data['posting_frequency'], 'daily')
        self.assertTrue(self.plan.strategy_data['manual_strategy'])
    
    def test_step2_unauthorized_access(self):
        """Test access to step 2 for wrong user"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_plan = PostingPlan.objects.create(
            title='Other Plan',
            user=other_user,
            platform=self.platform,
            user_profile='Other profile',
            target_audience='Other audience',
            goals='Other goals',
            vision='Other vision'
        )
        
        response = self.client.get(reverse('somi_plan:create_plan_step2', args=[other_plan.id]))
        self.assertEqual(response.status_code, 404)


class CreatePlanStep3ViewTest(BaseViewTest):
    """Test create plan step 3 view"""
    
    def setUp(self):
        super().setUp()
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision',
            strategy_data={
                'posting_frequency': 'daily',
                'content_types': ['tips', 'behind_scenes']
            }
        )
        self.session = PlanningSession.objects.create(
            posting_plan=self.plan,
            current_step=3
        )
        self.session.complete_step(1)
        self.session.complete_step(2)
    
    def test_step3_get(self):
        """Test GET request to step 3"""
        response = self.client.get(reverse('somi_plan:create_plan_step3', args=[self.plan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['plan'], self.plan)
    
    def test_step3_activate_plan(self):
        """Test activating plan in step 3"""
        data = {
            'action': 'activate'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step3', args=[self.plan.id]), data)
        
        # Should redirect to plan detail
        self.assertRedirects(response, reverse('somi_plan:plan_detail', args=[self.plan.id]))
        
        # Check plan was activated
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'active')
        
        # Check session completed
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_step_completed(3))
    
    def test_step3_save_draft(self):
        """Test saving plan as draft in step 3"""
        data = {
            'action': 'save_draft'
        }
        
        response = self.client.post(reverse('somi_plan:create_plan_step3', args=[self.plan.id]), data)
        
        # Should redirect to dashboard
        self.assertRedirects(response, reverse('somi_plan:dashboard'))
        
        # Check plan was saved as draft
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'draft')


class PlanDetailViewTest(BaseViewTest):
    """Test plan detail view"""
    
    def setUp(self):
        super().setUp()
        self.plan = PostingPlan.objects.create(
            title='Test Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Test profile',
            target_audience='Test audience',
            goals='Test goals',
            vision='Test vision'
        )
    
    def test_plan_detail_access(self):
        """Test plan detail access"""
        response = self.client.get(reverse('somi_plan:plan_detail', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['plan'], self.plan)
    
    def test_plan_detail_unauthorized(self):
        """Test unauthorized access to plan detail"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_plan = PostingPlan.objects.create(
            title='Other Plan',
            user=other_user,
            platform=self.platform,
            user_profile='Other profile',
            target_audience='Other audience',
            goals='Other goals',
            vision='Other vision'
        )
        
        response = self.client.get(reverse('somi_plan:plan_detail', args=[other_plan.pk]))
        self.assertEqual(response.status_code, 404)


class CalendarViewTest(BaseViewTest):
    """Test calendar view"""
    
    def test_calendar_access(self):
        """Test calendar access"""
        response = self.client.get(reverse('somi_plan:calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'calendar-container')
    
    def test_calendar_with_posts(self):
        """Test calendar with scheduled posts"""
        # Create plan and posts
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
        
        PostSchedule.objects.create(
            post_content=post,
            scheduled_date=date.today(),
            scheduled_time=time(12, 0),
            status='scheduled'
        )
        
        response = self.client.get(reverse('somi_plan:calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('posts_by_date', response.context)
    
    def test_calendar_month_navigation(self):
        """Test calendar month navigation"""
        next_month = date.today().replace(day=1) + timedelta(days=32)
        response = self.client.get(reverse('somi_plan:calendar'), {
            'year': next_month.year,
            'month': next_month.month
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['year'], next_month.year)
        self.assertEqual(response.context['month'], next_month.month)


class SchedulePostViewTest(BaseViewTest):
    """Test schedule post view"""
    
    def setUp(self):
        super().setUp()
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
    
    def test_schedule_post_get(self):
        """Test GET request to schedule post"""
        response = self.client.get(reverse('somi_plan:schedule_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertEqual(response.context['post'], self.post)
    
    def test_schedule_post_post_valid(self):
        """Test valid POST to schedule post"""
        data = {
            'scheduled_date': (date.today() + timedelta(days=1)).isoformat(),
            'scheduled_time': '14:30',
            'notes': 'Test scheduling'
        }
        
        response = self.client.post(reverse('somi_plan:schedule_post', args=[self.post.id]), data)
        
        # Should redirect to calendar
        self.assertRedirects(response, reverse('somi_plan:calendar'))
        
        # Check schedule was created
        schedule = PostSchedule.objects.get(post_content=self.post)
        self.assertEqual(schedule.scheduled_time, time(14, 30))
        self.assertEqual(schedule.notes, 'Test scheduling')
    
    def test_schedule_post_unauthorized(self):
        """Test unauthorized access to schedule post"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_plan = PostingPlan.objects.create(
            title='Other Plan',
            user=other_user,
            platform=self.platform,
            user_profile='Other profile',
            target_audience='Other audience',
            goals='Other goals',
            vision='Other vision'
        )
        other_post = PostContent.objects.create(
            posting_plan=other_plan,
            title='Other Post',
            content='Other content'
        )
        
        response = self.client.get(reverse('somi_plan:schedule_post', args=[other_post.id]))
        self.assertEqual(response.status_code, 404)


class AjaxViewTest(BaseViewTest):
    """Test AJAX views"""
    
    def setUp(self):
        super().setUp()
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
    
    def test_ajax_toggle_schedule(self):
        """Test AJAX toggle schedule"""
        response = self.client.post(
            reverse('somi_plan:ajax_toggle_schedule', args=[self.post.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['action'], 'scheduled')
        
        # Check schedule was created
        self.assertTrue(PostSchedule.objects.filter(post_content=self.post).exists())
    
    def test_ajax_update_position(self):
        """Test AJAX update position"""
        data = {
            'date': (date.today() + timedelta(days=1)).isoformat(),
            'time': '15:00'
        }
        
        response = self.client.post(
            reverse('somi_plan:ajax_update_position', args=[self.post.pk]),
            data=json.dumps(data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        
        # Check schedule was created/updated
        schedule = PostSchedule.objects.get(post_content=self.post)
        self.assertEqual(schedule.scheduled_time, time(15, 0))
    
    def test_ajax_calendar_data(self):
        """Test AJAX calendar data"""
        # Create scheduled post
        PostSchedule.objects.create(
            post_content=self.post,
            scheduled_date=date.today(),
            scheduled_time=time(12, 0),
            status='scheduled'
        )
        
        today = date.today()
        response = self.client.get(
            reverse('somi_plan:ajax_calendar_data', args=[today.year, today.month]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('posts_by_date', data)


class DeleteViewTest(BaseViewTest):
    """Test delete views"""
    
    def setUp(self):
        super().setUp()
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
    
    def test_plan_delete_get(self):
        """Test GET request to plan delete"""
        response = self.client.get(reverse('somi_plan:plan_delete', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['plan'], self.plan)
    
    def test_plan_delete_post(self):
        """Test POST request to delete plan"""
        response = self.client.post(reverse('somi_plan:plan_delete', args=[self.plan.pk]))
        
        # Should redirect to dashboard
        self.assertRedirects(response, reverse('somi_plan:dashboard'))
        
        # Check plan was deleted
        self.assertFalse(PostingPlan.objects.filter(pk=self.plan.pk).exists())
    
    def test_post_delete_post(self):
        """Test POST request to delete post"""
        response = self.client.post(reverse('somi_plan:post_delete', args=[self.post.pk]))
        
        # Should redirect to plan detail
        self.assertRedirects(response, reverse('somi_plan:plan_detail', args=[self.plan.pk]))
        
        # Check post was deleted
        self.assertFalse(PostContent.objects.filter(pk=self.post.pk).exists())


class MarkCompletedViewTest(BaseViewTest):
    """Test mark completed view"""
    
    def setUp(self):
        super().setUp()
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
        self.schedule = PostSchedule.objects.create(
            post_content=self.post,
            scheduled_date=date.today(),
            scheduled_time=time(12, 0),
            status='scheduled'
        )
    
    def test_mark_completed(self):
        """Test marking post as completed"""
        data = {
            'url': 'https://instagram.com/p/test123'
        }
        
        response = self.client.post(
            reverse('somi_plan:mark_completed', args=[self.schedule.pk]),
            data
        )
        
        # Should redirect to calendar
        self.assertRedirects(response, reverse('somi_plan:calendar'))
        
        # Check schedule was marked completed
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status, 'completed')
        self.assertEqual(self.schedule.published_url, 'https://instagram.com/p/test123')
        self.assertIsNotNone(self.schedule.completed_at)


class PermissionTest(BaseViewTest):
    """Test view permissions and security"""
    
    def test_login_required_views(self):
        """Test that views require login"""
        self.client.logout()
        
        protected_urls = [
            reverse('somi_plan:dashboard'),
            reverse('somi_plan:plan_list'),
            reverse('somi_plan:create_plan_step1'),
            reverse('somi_plan:calendar'),
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_user_isolation(self):
        """Test that users can only access their own data"""
        # Create another user with data
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_plan = PostingPlan.objects.create(
            title='Other Plan',
            user=other_user,
            platform=self.platform,
            user_profile='Other profile',
            target_audience='Other audience',
            goals='Other goals',
            vision='Other vision'
        )
        
        # Test current user cannot access other user's data
        response = self.client.get(reverse('somi_plan:plan_detail', args=[other_plan.pk]))
        self.assertEqual(response.status_code, 404)
        
        response = self.client.get(reverse('somi_plan:plan_delete', args=[other_plan.pk]))
        self.assertEqual(response.status_code, 404)


class ResponseFormatTest(BaseViewTest):
    """Test response formats and templates"""
    
    def test_html_responses(self):
        """Test HTML responses use correct templates"""
        template_tests = [
            (reverse('somi_plan:dashboard'), 'somi_plan/dashboard.html'),
            (reverse('somi_plan:plan_list'), 'somi_plan/plan_list.html'),
            (reverse('somi_plan:create_plan_step1'), 'somi_plan/create_step1.html'),
            (reverse('somi_plan:calendar'), 'somi_plan/calendar.html'),
        ]
        
        for url, expected_template in template_tests:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, expected_template)
    
    def test_ajax_responses(self):
        """Test AJAX responses return JSON"""
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
        
        response = self.client.post(
            reverse('somi_plan:ajax_toggle_schedule', args=[post.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Verify JSON is valid
        try:
            json.loads(response.content)
        except json.JSONDecodeError:
            self.fail("Response is not valid JSON")