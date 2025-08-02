"""
Unit Tests für die behobenen Bugs im Social Media Planer
"""
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch, MagicMock
from somi_plan.models import PostingPlan, PostContent, Platform, PostSchedule
from somi_plan.services import SomiPlanAIService

User = get_user_model()


class BugFixTestCase(TestCase):
    """Tests für die behobenen Bugs"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='Instagram',
            character_limit=2200,
            icon='fab fa-instagram',
            color='#E1306C'
        )
        self.plan = PostingPlan.objects.create(
            user=self.user,
            platform=self.platform,
            topic='Test Topic',
            goal='Test Goal'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_postcontent_related_name_fix(self):
        """Test: posts.all() funktioniert statt postcontent_set.all()"""
        # Erstelle Test-Posts
        post1 = PostContent.objects.create(
            posting_plan=self.plan,
            title='Test Post 1',
            content='Test Content 1'
        )
        post2 = PostContent.objects.create(
            posting_plan=self.plan,
            title='Test Post 2',
            content='Test Content 2'
        )
        
        # Teste den korrekten related_name
        posts = self.plan.posts.all()
        self.assertEqual(posts.count(), 2)
        self.assertIn(post1, posts)
        self.assertIn(post2, posts)
        
        # Stelle sicher, dass postcontent_set nicht mehr existiert
        with self.assertRaises(AttributeError):
            self.plan.postcontent_set.all()
    
    def test_re_module_import(self):
        """Test: re Modul ist verfügbar in views"""
        url = reverse('somi_plan:create_post', args=[self.plan.id])
        
        # Mock AI Service
        with patch('somi_plan.views.SomiPlanAIService') as mock_ai_service:
            mock_instance = MagicMock()
            mock_ai_service.return_value = mock_instance
            mock_instance._call_openai_api.return_value = {
                'success': True,
                'content': '{"title": "Test", "content": "Test Content"}'
            }
            
            response = self.client.post(url, {
                'topic': 'Test Topic',
                'ai_provider': 'openai',
                'ai_model': 'gpt-3.5-turbo'
            })
            
            # Sollte erfolgreich sein ohne ImportError
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertTrue(data['success'])
    
    def test_unique_together_removed(self):
        """Test: unique_together Constraint wurde entfernt"""
        # Erstelle einen PostContent mit Schedule
        post = PostContent.objects.create(
            posting_plan=self.plan,
            title='Test Post',
            content='Test Content'
        )
        
        # Sollte nur eine Schedule pro Post erlauben (OneToOne)
        schedule1 = PostSchedule.objects.create(
            post_content=post,
            scheduled_date='2024-12-31'
        )
        
        # Zweiter Schedule sollte fehlschlagen wegen OneToOne
        with self.assertRaises(Exception):
            PostSchedule.objects.create(
                post_content=post,
                scheduled_date='2024-12-30'
            )
    
    def test_ai_service_error_handling(self):
        """Test: AI Service Fehler werden korrekt behandelt"""
        url = reverse('somi_plan:create_step2', args=[self.plan.id])
        
        # Mock AI Service mit Fehler
        with patch('somi_plan.views.SomiPlanAIService') as mock_ai_service:
            mock_ai_service.side_effect = Exception('API Key nicht gefunden')
            
            response = self.client.post(url, {
                'use_ai_strategy': True,
                'posting_frequency': 'daily'
            })
            
            # Sollte nicht abstürzen
            self.assertEqual(response.status_code, 200)
            messages = list(response.context['messages'])
            self.assertTrue(any('Fehler beim AI-Service' in str(m) for m in messages))
    
    def test_no_api_key_debug_prints(self):
        """Test: API Keys werden nicht mehr in Logs ausgegeben"""
        # Setze Test API Keys
        self.user.openai_api_key = 'sk-test123456789'
        self.user.anthropic_api_key = 'ant-test123456789'
        self.user.google_api_key = 'ggl-test123456789'
        self.user.save()
        
        # Capture stdout
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Erstelle Service
        service = SomiPlanAIService(self.user)
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        output = captured_output.getvalue()
        
        # Prüfe, dass keine API Keys im Output sind
        self.assertNotIn('sk-test', output)
        self.assertNotIn('ant-test', output)
        self.assertNotIn('ggl-test', output)
        self.assertNotIn('DEBUG - OpenAI Key start:', output)
    
    def test_user_ownership_security(self):
        """Test: User kann nur eigene Pläne/Posts sehen"""
        # Erstelle zweiten User mit eigenem Plan
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        other_plan = PostingPlan.objects.create(
            user=other_user,
            platform=self.platform,
            topic='Other Topic',
            goal='Other Goal'
        )
        
        # Versuche auf fremden Plan zuzugreifen
        url = reverse('somi_plan:plan_detail', args=[other_plan.id])
        response = self.client.get(url)
        
        # Sollte 404 zurückgeben
        self.assertEqual(response.status_code, 404)
        
        # Eigener Plan sollte funktionieren
        url = reverse('somi_plan:plan_detail', args=[self.plan.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_ai_service_fallback_handling(self):
        """Test: AI Service Fallback bei API Fehler"""
        url = reverse('somi_plan:create_post', args=[self.plan.id])
        
        with patch('somi_plan.views.SomiPlanAIService') as mock_ai_service:
            mock_instance = MagicMock()
            mock_ai_service.return_value = mock_instance
            
            # Simuliere API Fehler
            mock_instance._call_openai_api.return_value = {
                'success': False,
                'error': 'API Rate Limit erreicht'
            }
            
            response = self.client.post(url, {
                'topic': 'Test Topic',
                'ai_provider': 'openai',
                'ai_model': 'gpt-3.5-turbo'
            })
            
            data = json.loads(response.content)
            self.assertFalse(data['success'])
            self.assertIn('AI-Fehler', data['error'])


class IntegrationTestCase(TestCase):
    """Integrationstests für komplette Workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.platform = Platform.objects.create(
            name='LinkedIn',
            character_limit=3000,
            icon='fab fa-linkedin',
            color='#0077B5'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_complete_planning_workflow(self):
        """Test: Kompletter 3-Schritte Planungsprozess"""
        # Schritt 1: Plan erstellen
        url = reverse('somi_plan:create_step1')
        response = self.client.post(url, {
            'platform': self.platform.id,
            'topic': 'Software Testing Best Practices',
            'goal': 'Expertise zeigen und Leads generieren',
            'target_audience': 'Software Entwickler und QA Engineers'
        })
        
        # Sollte zu Schritt 2 weiterleiten
        self.assertEqual(response.status_code, 302)
        plan = PostingPlan.objects.get(user=self.user)
        self.assertEqual(plan.topic, 'Software Testing Best Practices')
        
        # Schritt 2: Strategie (ohne AI)
        url = reverse('somi_plan:create_step2', args=[plan.id])
        response = self.client.post(url, {
            'use_ai_strategy': False,
            'posting_frequency': 'weekly',
            'best_times': 'Dienstag und Donnerstag, 10-11 Uhr',
            'content_types': 'Tipps, Case Studies, Tools',
            'cross_platform': True,
            'additional_notes': 'Fokus auf praktische Beispiele'
        })
        
        # Sollte zu Schritt 3 weiterleiten
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertIsNotNone(plan.strategy_data)
        self.assertEqual(plan.strategy_data['posting_frequency'], 'weekly')
        
        # Schritt 3: Content Preview
        url = reverse('somi_plan:create_step3', args=[plan.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Software Testing Best Practices')