from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Campaign, Creative, AIService, GenerationJob
from .ai_service import AICreativeGenerator

User = get_user_model()


class MakeAdsModelTests(TestCase):
    """
    Tests für die MakeAds Models
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_campaign_creation(self):
        """Test Campaign Model"""
        campaign = Campaign.objects.create(
            user=self.user,
            name='Test Kampagne',
            description='Test Beschreibung',
            basic_idea='Eine innovative App für Fitness-Tracking'
        )
        
        self.assertEqual(campaign.name, 'Test Kampagne')
        self.assertEqual(campaign.user, self.user)
        self.assertEqual(str(campaign), f'Test Kampagne - {self.user.username}')
        
    def test_creative_creation(self):
        """Test Creative Model"""
        campaign = Campaign.objects.create(
            user=self.user,
            name='Test Kampagne',
            basic_idea='Test Idee'
        )
        
        creative = Creative.objects.create(
            campaign=campaign,
            title='Test Creative',
            description='Test Beschreibung',
            text_content='Test Text',
            generation_status='completed'
        )
        
        self.assertEqual(creative.title, 'Test Creative')
        self.assertEqual(creative.campaign, campaign)
        self.assertEqual(creative.generation_status, 'completed')
        self.assertFalse(creative.is_favorite)
        
    def test_ai_service_creation(self):
        """Test AIService Model"""
        service = AIService.objects.create(
            name='OpenAI Test',
            service_type='openai',
            default_model='gpt-3.5-turbo'
        )
        
        self.assertEqual(service.name, 'OpenAI Test')
        self.assertEqual(service.service_type, 'openai')
        self.assertTrue(service.is_active)
        
    def test_generation_job_creation(self):
        """Test GenerationJob Model"""
        campaign = Campaign.objects.create(
            user=self.user,
            name='Test Kampagne',
            basic_idea='Test Idee'
        )
        
        job = GenerationJob.objects.create(
            campaign=campaign,
            job_type='initial',
            target_count=10
        )
        
        self.assertEqual(job.campaign, campaign)
        self.assertEqual(job.job_type, 'initial')
        self.assertEqual(job.target_count, 10)
        self.assertEqual(job.generated_count, 0)
        self.assertEqual(job.status, 'queued')


class MakeAdsViewTests(TestCase):
    """
    Tests für die MakeAds Views
    """
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_dashboard_view_requires_login(self):
        """Dashboard erfordert Login"""
        response = self.client.get(reverse('makeads:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
    def test_dashboard_view_with_login(self):
        """Dashboard mit eingeloggtem User"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('makeads:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MakeAds Dashboard')
        
    def test_campaign_create_step1(self):
        """Test Schritt 1 der Kampagnenerstellung"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('makeads:campaign_create_step1'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ideeneingabe')
        
    def test_campaign_create_post(self):
        """Test POST für Kampagnenerstellung"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Test Kampagne',
            'basic_idea': 'Eine innovative Fitness-App',
            'detailed_description': 'Detaillierte Beschreibung der App'
        }
        
        response = self.client.post(reverse('makeads:campaign_create_step1'), data)
        self.assertEqual(response.status_code, 302)  # Redirect to step 2
        
        # Verify campaign was created
        campaign = Campaign.objects.get(name='Test Kampagne')
        self.assertEqual(campaign.user, self.user)
        self.assertEqual(campaign.basic_idea, 'Eine innovative Fitness-App')


class AICreativeGeneratorTests(TestCase):
    """
    Tests für den AI Creative Generator
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.campaign = Campaign.objects.create(
            user=self.user,
            name='Test Kampagne',
            basic_idea='Eine innovative Fitness-App',
            detailed_description='App für Fitness-Tracking'
        )
        
    def test_ai_generator_initialization(self):
        """Test AI Generator Initialisierung"""
        generator = AICreativeGenerator(self.user)
        self.assertEqual(generator.user, self.user)
        
    def test_prompt_building(self):
        """Test Prompt-Erstellung"""
        generator = AICreativeGenerator(self.user)
        
        text_prompt = generator._build_text_prompt(
            self.campaign,
            style_preference='modern',
            target_audience='Junge Erwachsene',
            custom_instructions='Verwende motivierende Sprache'
        )
        
        self.assertIn(self.campaign.name, text_prompt)
        self.assertIn(self.campaign.basic_idea, text_prompt)
        self.assertIn('modern', text_prompt)
        self.assertIn('Junge Erwachsene', text_prompt)
        
    def test_mock_text_generation(self):
        """Test Mock Text-Generierung"""
        generator = AICreativeGenerator(self.user)
        
        result = generator._generate_mock_text('Test prompt')
        
        self.assertIn('content', result)
        self.assertIn('description', result)
        self.assertTrue(len(result['content']) > 0)
        self.assertTrue(len(result['description']) > 0)
        
    def test_mock_image_generation(self):
        """Test Mock Bild-Generierung"""
        generator = AICreativeGenerator(self.user)
        
        image_url = generator._generate_mock_image('Test prompt')
        
        self.assertTrue(image_url.startswith('https://'))
        self.assertIn('placeholder', image_url)
        
    def test_batch_number_calculation(self):
        """Test Batch-Nummer Berechnung"""
        generator = AICreativeGenerator(self.user)
        
        # Erster Batch sollte 1 sein
        batch_num = generator._get_next_batch_number(self.campaign)
        self.assertEqual(batch_num, 1)
        
        # Creative erstellen
        Creative.objects.create(
            campaign=self.campaign,
            title='Test Creative',
            description='Test',
            text_content='Test',
            generation_batch=1
        )
        
        # Nächster Batch sollte 2 sein
        batch_num = generator._get_next_batch_number(self.campaign)
        self.assertEqual(batch_num, 2)