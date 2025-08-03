"""
Django management command to handle expired DALL-E images
"""
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from makeads.models import Creative
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix expired DALL-E images by creating placeholder images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-placeholders',
            action='store_true',
            help='Create placeholder images for expired URLs',
        )

    def handle(self, *args, **options):
        self.stdout.write("🖼️  MakeAds Expired Image Fix Tool")
        self.stdout.write("=" * 50)
        
        # Find creatives with expired URLs
        from django.db import models
        expired_creatives = Creative.objects.filter(
            image_url__isnull=False
        ).exclude(image_url='').filter(
            models.Q(image_file__isnull=True) | models.Q(image_file='')
        )
        
        if not expired_creatives.exists():
            self.stdout.write(
                self.style.SUCCESS("✅ No creatives with expired images found!")
            )
            return
        
        self.stdout.write(f"📊 Found {expired_creatives.count()} creatives with expired DALL-E URLs")
        
        if options['create_placeholders']:
            self.stdout.write("🎨 Creating placeholder images...")
            
            success_count = 0
            for creative in expired_creatives:
                try:
                    placeholder_image = self.create_placeholder_image(creative)
                    if placeholder_image:
                        success_count += 1
                        self.stdout.write(f"   ✅ Created placeholder for: {creative.title}")
                    else:
                        self.stdout.write(f"   ❌ Failed to create placeholder for: {creative.title}")
                except Exception as e:
                    self.stdout.write(f"   ❌ Error with {creative.title}: {str(e)}")
            
            self.stdout.write(f"\n🎉 Created {success_count} placeholder images!")
        else:
            self.stdout.write("\n💡 Run with --create-placeholders to create placeholder images")
            
            for creative in expired_creatives[:5]:
                self.stdout.write(f"   • {creative.title} (Campaign: {creative.campaign.name})")
            
            if expired_creatives.count() > 5:
                self.stdout.write(f"   ... and {expired_creatives.count() - 5} more")

    def create_placeholder_image(self, creative):
        """Create a placeholder image for a creative with expired URL"""
        try:
            # Create a 512x512 image with gradient background
            width, height = 512, 512
            image = Image.new('RGB', (width, height), color='#f0f0f0')
            
            # Create gradient background
            draw = ImageDraw.Draw(image)
            for i in range(height):
                # Create a subtle gradient from light blue to light purple
                r = int(220 + (i / height) * 20)  # 220-240
                g = int(230 + (i / height) * 10)  # 230-240  
                b = int(240 - (i / height) * 20)  # 240-220
                color = (min(255, r), min(255, g), min(255, b))
                draw.line([(0, i), (width, i)], fill=color)
            
            # Add creative title
            try:
                font_size = 24
                font = ImageFont.load_default()
            except:
                font = None
            
            # Draw creative info
            title = creative.title or "Creative"
            campaign = creative.campaign.name[:30] + "..." if len(creative.campaign.name) > 30 else creative.campaign.name
            
            # Calculate text position
            if font:
                # Get text dimensions
                bbox = draw.textbbox((0, 0), title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # Center the text
                x = (width - text_width) // 2
                y = height // 2 - text_height
                
                # Draw white background for text
                padding = 10
                draw.rectangle([x-padding, y-padding, x+text_width+padding, y+text_height+padding*3], 
                             fill='white', outline='#ddd')
                
                # Draw title
                draw.text((x, y), title, fill='#333', font=font)
                
                # Draw campaign name
                campaign_bbox = draw.textbbox((0, 0), f"from: {campaign}", font=font)
                campaign_width = campaign_bbox[2] - campaign_bbox[0]
                campaign_x = (width - campaign_width) // 2
                draw.text((campaign_x, y + text_height + 5), f"from: {campaign}", fill='#666', font=font)
            
            # Add "PLACEHOLDER" watermark
            watermark_font = font
            watermark_text = "PLACEHOLDER"
            if watermark_font:
                bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
                wm_width = bbox[2] - bbox[0]
                wm_x = (width - wm_width) // 2
                wm_y = height - 50
                draw.text((wm_x, wm_y), watermark_text, fill='#999', font=watermark_font)
            
            # Save to BytesIO
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Create Django file
            filename = f"makeads/creatives/{creative.id}_placeholder.png"
            django_file = ContentFile(img_buffer.getvalue(), name=filename)
            
            # Save to creative
            creative.image_file.save(filename, django_file, save=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create placeholder for Creative {creative.id}: {str(e)}")
            return False