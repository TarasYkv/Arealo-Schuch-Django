from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from makeads.models import Campaign, ReferenceImage
from makeads.image_processor import ImageURLProcessor, ReferenceImageAnalyzer, ReferenceManager
from makeads.api_client import CentralAPIClient
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test image processing and analysis functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username for testing (default: first superuser)',
        )
        parser.add_argument(
            '--url',
            type=str,
            default='https://naturmacher.de/cdn/shop/files/5_e353accd-afbf-40ac-8ecb-a2cc9575ff74.png?v=1752828934',
            help='Test image URL',
        )
        parser.add_argument(
            '--skip-analysis',
            action='store_true',
            help='Skip AI analysis (only test URL processing)',
        )
        
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧪 Testing Image Processing & Analysis'))
        
        # Get test user
        user = self.get_test_user(options.get('user'))
        self.stdout.write(f"Using user: {user.username}")
        
        # Test URL processing
        test_url = options.get('url')
        self.stdout.write(f"Testing URL: {test_url}")
        
        try:
            # Test URL detection
            url_processor = ImageURLProcessor()
            detected_urls = url_processor.extract_image_urls(test_url)
            
            if detected_urls:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ URL detection: {len(detected_urls)} image URL(s) detected")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  URL detection: No image URLs detected in '{test_url}'")
                )
                # Try to treat the URL as a direct image URL
                detected_urls = [test_url] if url_processor._is_potential_image_url(test_url) else []
            
            if not detected_urls:
                self.stdout.write(self.style.ERROR("❌ No valid image URLs to test"))
                return
                
            # Test image download
            for url in detected_urls[:1]:  # Test only first URL
                self.stdout.write(f"\n📥 Testing image download for: {url}")
                
                content_file, metadata = url_processor.download_image(url, "test")
                
                if metadata['success']:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Download successful: {metadata['filename']} ({metadata['size']} bytes)"
                        )
                    )
                    
                    # Test AI analysis (if not skipped)
                    if not options.get('skip_analysis'):
                        self.test_ai_analysis(user, content_file, metadata['filename'])
                    
                    # Cleanup - remove the temporary file
                    # (In real usage, this would be saved to ReferenceImage)
                    
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Download failed: {metadata.get('error', 'Unknown error')}")
                    )
            
            # Test full ReferenceManager workflow
            self.test_reference_manager(user, test_url, options.get('skip_analysis', False))
            
        except Exception as e:
            logger.exception("Error during image processing test")
            self.stdout.write(
                self.style.ERROR(f"❌ Test failed with error: {str(e)}")
            )
            
    def get_test_user(self, username=None):
        """Get test user"""
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' not found")
        else:
            # Get first superuser
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                raise CommandError("No superuser found. Please create one or specify --user")
            return superuser
    
    def test_ai_analysis(self, user, content_file, filename):
        """Test AI image analysis"""
        self.stdout.write(f"\n🤖 Testing AI analysis...")
        
        # Get API key
        api_client = CentralAPIClient(user)
        api_keys = api_client.get_api_keys()
        openai_api_key = api_keys.get('openai')
        
        if not openai_api_key:
            self.stdout.write(
                self.style.WARNING("⚠️  No OpenAI API key found. Skipping AI analysis.")
            )
            return
            
        try:
            analyzer = ReferenceImageAnalyzer(openai_api_key)
            analysis = analyzer.analyze_image(content_file, filename)
            
            if analysis.get('success'):
                self.stdout.write(
                    self.style.SUCCESS("✅ AI Analysis successful:")
                )
                
                self.stdout.write(f"  📝 Description: {analysis.get('description', 'N/A')}")
                
                style_elements = analysis.get('style_elements', {})
                if style_elements:
                    self.stdout.write(f"  🎨 Style: {style_elements.get('overall_style', 'N/A')}")
                    self.stdout.write(f"  😊 Mood: {style_elements.get('mood', 'N/A')}")
                    
                colors = analysis.get('colors', [])
                if colors:
                    color_info = ', '.join([f"{c.get('color', 'N/A')} ({c.get('description', 'N/A')})" for c in colors[:2]])
                    self.stdout.write(f"  🌈 Colors: {color_info}")
                    
                recommendations = analysis.get('recommendations', [])
                if recommendations:
                    self.stdout.write(f"  💡 Recommendations: {len(recommendations)} provided")
                    
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ AI Analysis failed: {analysis.get('error', 'Unknown error')}")
                )
                
        except Exception as e:
            logger.exception("Error during AI analysis test")
            self.stdout.write(
                self.style.ERROR(f"❌ AI Analysis error: {str(e)}")
            )
    
    def test_reference_manager(self, user, test_url, skip_analysis=False):
        """Test the complete ReferenceManager workflow"""
        self.stdout.write(f"\n🔄 Testing complete ReferenceManager workflow...")
        
        try:
            # Create test campaign
            campaign = Campaign.objects.create(
                user=user,
                name="Test Campaign for Image Processing",
                description="Test campaign",
                basic_idea="Testing image processing features"
            )
            
            self.stdout.write(f"Created test campaign: {campaign.name}")
            
            # Get API key
            api_client = CentralAPIClient(user)
            api_keys = api_client.get_api_keys()
            openai_api_key = api_keys.get('openai') if not skip_analysis else None
            
            # Test ReferenceManager
            reference_manager = ReferenceManager(openai_api_key)
            
            # Create web_links text with test URL
            web_links_text = f"{test_url}\nhttps://example.com/not-an-image"
            
            results = reference_manager.process_web_links(web_links_text, campaign)
            
            processed_count = sum(1 for r in results if r.get('processed'))
            failed_count = len(results) - processed_count
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ ReferenceManager processed: {processed_count} successful, {failed_count} failed"
                )
            )
            
            for result in results:
                if result.get('processed'):
                    ref_image = result.get('reference_image')
                    analysis = result.get('analysis', {})
                    
                    self.stdout.write(f"  📸 Created ReferenceImage: {ref_image.id}")
                    self.stdout.write(f"     Description: {ref_image.description}")
                    
                    if analysis.get('success'):
                        self.stdout.write(f"     AI Analysis: {analysis.get('description', 'N/A')}")
                else:
                    self.stdout.write(f"  ❌ Failed: {result.get('url')} - {result.get('error')}")
            
            # Cleanup
            self.stdout.write(f"\n🧹 Cleaning up test campaign...")
            campaign.delete()
            self.stdout.write("Test campaign deleted")
            
        except Exception as e:
            logger.exception("Error during ReferenceManager test")
            self.stdout.write(
                self.style.ERROR(f"❌ ReferenceManager test error: {str(e)}")
            )