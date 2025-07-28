"""
Tests for SoMi-Plan AI services
"""
from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json

from somi_plan.models import Platform, PostingPlan, PostContent
from somi_plan.services import SomiPlanAIService


class SomiPlanAIServiceTest(TestCase):
    """Test SomiPlanAIService"""
    
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
            title='Test Marketing Plan',
            user=self.user,
            platform=self.platform,
            user_profile='Social Media Manager at Tech Startup',
            target_audience='Tech professionals and entrepreneurs aged 25-40',
            goals='Increase brand awareness and generate leads',
            vision='Become the go-to resource for tech innovation insights'
        )
        self.ai_service = SomiPlanAIService(self.user)
    
    def test_ai_service_initialization(self):
        """Test AI service initialization"""
        self.assertEqual(self.ai_service.user, self.user)
        self.assertIsNotNone(self.ai_service.model_preference)
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_generate_strategy_openai_success(self, mock_openai):
        """Test successful strategy generation with OpenAI"""
        # Mock OpenAI response
        mock_response = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'posting_frequency': 'daily',
                        'best_times': ['09:00', '18:00'],
                        'content_types': ['tips', 'behind_scenes', 'educational'],
                        'content_pillars': ['Industry Insights', 'Company Culture', 'Educational Content'],
                        'engagement_strategy': 'Focus on interactive content and community building',
                        'hashtag_strategy': 'Mix of trending and niche hashtags',
                        'cross_platform_notes': 'Adapt content for each platform while maintaining brand voice'
                    })
                }
            }],
            'usage': {'total_tokens': 500}
        }
        mock_openai.return_value = mock_response
        
        result = self.ai_service.generate_strategy(self.plan)
        
        self.assertTrue(result['success'])
        self.assertIn('strategy_data', result)
        self.assertEqual(result['strategy_data']['posting_frequency'], 'daily')
        self.assertIn('09:00', result['strategy_data']['best_times'])
        self.assertIn('ai_generated_at', result['strategy_data'])
        self.assertEqual(result['model_used'], 'openai')
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_generate_strategy_openai_failure(self, mock_openai):
        """Test strategy generation failure with OpenAI"""
        # Mock OpenAI exception
        mock_openai.side_effect = Exception("API Error")
        
        result = self.ai_service.generate_strategy(self.plan)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('API Error', result['error'])
    
    @patch('somi_plan.services.anthropic.Anthropic')
    def test_generate_strategy_anthropic_success(self, mock_anthropic_class):
        """Test successful strategy generation with Anthropic"""
        # Mock Anthropic response
        mock_anthropic = MagicMock()
        mock_anthropic_class.return_value = mock_anthropic
        
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            'posting_frequency': 'twice_daily',
            'best_times': ['08:00', '17:00'],
            'content_types': ['motivational', 'tips'],
            'content_pillars': ['Motivation', 'Growth'],
            'engagement_strategy': 'Ask questions to encourage interaction',
            'hashtag_strategy': 'Use relevant industry hashtags',
            'cross_platform_notes': 'Tailor content length for each platform'
        })
        mock_anthropic.messages.create.return_value = mock_response
        
        # Set service to use Anthropic
        self.ai_service.model_preference = 'anthropic'
        
        result = self.ai_service.generate_strategy(self.plan)
        
        self.assertTrue(result['success'])
        self.assertIn('strategy_data', result)
        self.assertEqual(result['strategy_data']['posting_frequency'], 'twice_daily')
        self.assertEqual(result['model_used'], 'anthropic')
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_generate_posts_success(self, mock_openai):
        """Test successful post generation"""
        # Set up plan with strategy
        self.plan.strategy_data = {
            'posting_frequency': 'daily',
            'content_types': ['tips', 'educational'],
            'content_pillars': ['Industry Insights', 'Educational Content']
        }
        self.plan.save()
        
        # Mock OpenAI response
        mock_response = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'title': '5 Essential Tech Trends for 2024',
                            'content': 'Here are the top 5 technology trends that will shape 2024...',
                            'hashtags': '#TechTrends #Innovation #2024 #Technology #FutureTech',
                            'call_to_action': 'Which trend excites you most? Share your thoughts!',
                            'script': 'Focus on the visual appeal of emerging technologies',
                            'post_type': 'tips',
                            'priority': 1
                        },
                        {
                            'title': 'Understanding AI in Business',
                            'content': 'Artificial Intelligence is transforming how businesses operate...',
                            'hashtags': '#AI #Business #Innovation #MachineLearning #Tech',
                            'call_to_action': 'How is AI impacting your industry? Tell us below!',
                            'script': 'Use infographics to explain AI concepts simply',
                            'post_type': 'educational',
                            'priority': 2
                        }
                    ])
                }
            }],
            'usage': {'total_tokens': 800}
        }
        mock_openai.return_value = mock_response
        
        result = self.ai_service.generate_posts(self.plan, count=2)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['count'], 2)
        self.assertIn('posts', result)
        
        # Check posts were created in database
        posts = PostContent.objects.filter(posting_plan=self.plan)
        self.assertEqual(posts.count(), 2)
        
        first_post = posts.first()
        self.assertEqual(first_post.title, '5 Essential Tech Trends for 2024')
        self.assertEqual(first_post.post_type, 'tips')
        self.assertTrue(first_post.ai_generated)
        self.assertEqual(first_post.ai_model_used, 'openai')
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_generate_posts_failure(self, mock_openai):
        """Test post generation failure"""
        mock_openai.side_effect = Exception("API Error")
        
        result = self.ai_service.generate_posts(self.plan, count=5)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertEqual(result['count'], 0)
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_generate_more_ideas_success(self, mock_openai):
        """Test generating more creative ideas"""
        # Create existing posts
        PostContent.objects.create(
            posting_plan=self.plan,
            title='Existing Post 1',
            content='Existing content 1',
            post_type='tips'
        )
        PostContent.objects.create(
            posting_plan=self.plan,
            title='Existing Post 2',
            content='Existing content 2',
            post_type='educational'
        )
        
        # Mock OpenAI response
        mock_response = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'title': 'Creative Tech Innovation Story',
                            'content': 'Behind every great innovation is an even greater story...',
                            'hashtags': '#Innovation #TechStory #Creativity #Inspiration',
                            'call_to_action': 'What tech innovation story inspires you?',
                            'script': 'Use storytelling format with emotional hook',
                            'post_type': 'behind_scenes',
                            'priority': 2
                        }
                    ])
                }
            }],
            'usage': {'total_tokens': 600}
        }
        mock_openai.return_value = mock_response
        
        result = self.ai_service.generate_more_ideas(self.plan, existing_count=2)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['count'], 1)
        
        # Check new post was created
        new_posts = PostContent.objects.filter(
            posting_plan=self.plan,
            title='Creative Tech Innovation Story'
        )
        self.assertEqual(new_posts.count(), 1)
    
    def test_build_strategy_prompt(self):
        """Test strategy prompt building"""
        prompt = self.ai_service._build_strategy_prompt(self.plan)
        
        self.assertIn(self.plan.user_profile, prompt)
        self.assertIn(self.plan.target_audience, prompt)
        self.assertIn(self.plan.goals, prompt)
        self.assertIn(self.plan.vision, prompt)
        self.assertIn(self.plan.platform.name, prompt)
        self.assertIn('JSON', prompt)
    
    def test_build_content_prompt(self):
        """Test content generation prompt building"""
        strategy_data = {
            'posting_frequency': 'daily',
            'content_types': ['tips', 'educational'],
            'content_pillars': ['Industry Insights', 'Educational Content']
        }
        
        prompt = self.ai_service._build_content_prompt(self.plan, strategy_data, count=3)
        
        self.assertIn(self.plan.user_profile, prompt)
        self.assertIn(self.plan.target_audience, prompt)
        self.assertIn('3', prompt)  # Count
        self.assertIn('tips', prompt)
        self.assertIn('educational', prompt)
        self.assertIn('JSON', prompt)
    
    def test_validate_strategy_data(self):
        """Test strategy data validation"""
        # Valid strategy data
        valid_data = {
            'posting_frequency': 'daily',
            'best_times': ['09:00', '18:00'],
            'content_types': ['tips', 'educational']
        }
        
        is_valid, validated = self.ai_service._validate_strategy_data(valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(validated['posting_frequency'], 'daily')
        
        # Invalid strategy data
        invalid_data = {
            'posting_frequency': 'invalid_frequency',
            'best_times': 'not_a_list'
        }
        
        is_valid, validated = self.ai_service._validate_strategy_data(invalid_data)
        self.assertTrue(is_valid)  # Service should handle gracefully
        self.assertIn('posting_frequency', validated)
    
    def test_validate_post_data(self):
        """Test post data validation"""
        # Valid post data
        valid_posts = [
            {
                'title': 'Test Post',
                'content': 'Test content',
                'hashtags': '#test',
                'post_type': 'tips',
                'priority': 1
            }
        ]
        
        is_valid, validated = self.ai_service._validate_post_data(valid_posts)
        self.assertTrue(is_valid)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]['title'], 'Test Post')
        
        # Invalid post data
        invalid_posts = [
            {
                'title': '',  # Empty title
                'content': 'Test content'
            }
        ]
        
        is_valid, validated = self.ai_service._validate_post_data(invalid_posts)
        self.assertFalse(is_valid)
        self.assertEqual(len(validated), 0)
    
    def test_character_limit_consideration(self):
        """Test that AI service considers platform character limits"""
        # Create platform with very small character limit
        small_platform = Platform.objects.create(
            name='Twitter',
            icon='fab fa-twitter',
            color='#1DA1F2',
            character_limit=50  # Very small for testing
        )
        
        small_plan = PostingPlan.objects.create(
            title='Twitter Plan',
            user=self.user,
            platform=small_platform,
            user_profile='Twitter user',
            target_audience='Twitter followers',
            goals='Increase followers',
            vision='Twitter thought leader'
        )
        
        prompt = self.ai_service._build_content_prompt(small_plan, {}, count=1)
        self.assertIn('50', prompt)  # Character limit should be mentioned
        self.assertIn('character', prompt.lower())
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_ai_service_error_handling(self, mock_openai):
        """Test AI service error handling"""
        # Test JSON parsing error
        mock_response = {
            'choices': [{
                'message': {
                    'content': 'Invalid JSON response'
                }
            }],
            'usage': {'total_tokens': 100}
        }
        mock_openai.return_value = mock_response
        
        result = self.ai_service.generate_strategy(self.plan)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('parse', result['error'].lower())
    
    def test_ai_service_model_fallback(self):
        """Test AI service fallback between models"""
        # This would test the fallback mechanism when one AI service fails
        # and the system tries another one
        
        service = SomiPlanAIService(self.user)
        
        # Test that both OpenAI and Anthropic are available as options
        available_models = ['openai', 'anthropic']
        self.assertIn(service.model_preference, available_models)
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_token_usage_tracking(self, mock_openai):
        """Test that token usage is tracked"""
        mock_response = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'posting_frequency': 'daily',
                        'best_times': ['09:00'],
                        'content_types': ['tips']
                    })
                }
            }],
            'usage': {'total_tokens': 150}
        }
        mock_openai.return_value = mock_response
        
        result = self.ai_service.generate_strategy(self.plan)
        
        self.assertTrue(result['success'])
        self.assertIn('tokens_used', result)
        self.assertEqual(result['tokens_used'], 150)
    
    def test_user_specific_ai_preferences(self):
        """Test that AI service respects user-specific preferences"""
        # This would test user preferences for AI model choice
        # For now, just verify the service initializes with user context
        
        service = SomiPlanAIService(self.user)
        self.assertEqual(service.user, self.user)
        
        # Could be extended to test user preferences like:
        # - Preferred AI model
        # - Creativity level
        # - Content style preferences


class AIServiceIntegrationTest(TestCase):
    """Test AI service integration with other components"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='LinkedIn',
            icon='fab fa-linkedin',
            color='#0077B5',
            character_limit=3000
        )
        self.plan = PostingPlan.objects.create(
            title='LinkedIn Strategy',
            user=self.user,
            platform=self.platform,
            user_profile='B2B Marketing Professional',
            target_audience='Business decision makers',
            goals='Generate quality leads',
            vision='Industry thought leadership'
        )
    
    @patch('somi_plan.services.openai.ChatCompletion.create')
    def test_end_to_end_ai_workflow(self, mock_openai):
        """Test complete AI workflow from strategy to posts"""
        # Mock strategy generation
        strategy_response = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'posting_frequency': 'twice_daily',
                        'best_times': ['08:00', '17:00'],
                        'content_types': ['professional', 'educational'],
                        'content_pillars': ['Industry Insights', 'Professional Development'],
                        'engagement_strategy': 'Professional networking and thought leadership',
                        'hashtag_strategy': 'Industry-specific and trending professional hashtags'
                    })
                }
            }],
            'usage': {'total_tokens': 400}
        }
        
        # Mock post generation
        posts_response = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'title': 'B2B Marketing Trends 2024',
                            'content': 'The B2B marketing landscape is evolving rapidly...',
                            'hashtags': '#B2BMarketing #MarketingTrends #BusinessGrowth',
                            'call_to_action': 'What B2B trends are you seeing in your industry?',
                            'post_type': 'professional',
                            'priority': 1
                        }
                    ])
                }
            }],
            'usage': {'total_tokens': 600}
        }
        
        # Set up mock to return different responses
        mock_openai.side_effect = [strategy_response, posts_response]
        
        ai_service = SomiPlanAIService(self.user)
        
        # Generate strategy
        strategy_result = ai_service.generate_strategy(self.plan)
        self.assertTrue(strategy_result['success'])
        
        # Update plan with strategy
        self.plan.strategy_data = strategy_result['strategy_data']
        self.plan.save()
        
        # Generate posts
        posts_result = ai_service.generate_posts(self.plan, count=1)
        self.assertTrue(posts_result['success'])
        
        # Verify integration
        self.assertEqual(posts_result['count'], 1)
        post = PostContent.objects.get(posting_plan=self.plan)
        self.assertEqual(post.title, 'B2B Marketing Trends 2024')
        self.assertTrue(post.ai_generated)
    
    def test_ai_service_platform_adaptation(self):
        """Test that AI service adapts content for different platforms"""
        ai_service = SomiPlanAIService(self.user)
        
        # LinkedIn prompt should mention professional content
        linkedin_prompt = ai_service._build_strategy_prompt(self.plan)
        self.assertIn('LinkedIn', linkedin_prompt)
        self.assertIn('professional', linkedin_prompt.lower())
        
        # Create Instagram plan for comparison
        instagram_platform = Platform.objects.create(
            name='Instagram',
            icon='fab fa-instagram',
            color='#E4405F',
            character_limit=2200
        )
        
        instagram_plan = PostingPlan.objects.create(
            title='Instagram Strategy',
            user=self.user,
            platform=instagram_platform,
            user_profile='Creative Content Creator',
            target_audience='Visual content consumers',
            goals='Increase engagement',
            vision='Creative inspiration'
        )
        
        instagram_prompt = ai_service._build_strategy_prompt(instagram_plan)
        self.assertIn('Instagram', instagram_prompt)
        self.assertIn('visual', instagram_prompt.lower())
    
    def test_ai_service_error_recovery(self):
        """Test AI service error recovery and graceful degradation"""
        ai_service = SomiPlanAIService(self.user)
        
        # Test with empty plan data
        minimal_plan = PostingPlan.objects.create(
            title='Minimal Plan',
            user=self.user,
            platform=self.platform,
            user_profile='',  # Empty
            target_audience='',  # Empty
            goals='',  # Empty
            vision=''  # Empty
        )
        
        # Should still generate a prompt without errors
        prompt = ai_service._build_strategy_prompt(minimal_plan)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)