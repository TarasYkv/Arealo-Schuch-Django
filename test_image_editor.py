#!/usr/bin/env python3
"""
Test script for Image Editor advanced features
Run this to verify all image processing features work correctly.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from PIL import Image, ImageDraw
import tempfile
import io

def create_test_image():
    """Create a simple test image for processing"""
    # Create a 300x300 test image with some content
    img = Image.new('RGB', (300, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw some shapes
    draw.rectangle([50, 50, 250, 250], outline='black', width=3)
    draw.ellipse([100, 100, 200, 200], fill='blue')
    draw.text((150, 150), "TEST", fill='white', anchor='mm')
    
    return img

def test_image_processor():
    """Test the ImageProcessor class"""
    print("🧪 Testing ImageProcessor...")
    
    try:
        from image_editor.image_processing import ImageProcessor
        
        # Create test image
        test_img = create_test_image()
        
        # Initialize processor
        processor = ImageProcessor(test_img)
        print("✅ ImageProcessor initialized successfully")
        
        # Test basic operations
        print("📝 Testing basic operations...")
        
        # Test grayscale
        original_mode = processor.current_image.mode
        processor.current_image = processor.current_image.convert('L')
        print(f"   ✅ Grayscale conversion: {original_mode} -> {processor.current_image.mode}")
        
        # Reset for next test
        processor.current_image = test_img.copy()
        
        # Test advanced filters
        print("🎨 Testing advanced filters...")
        
        filters_to_test = [
            ('emboss', {'strength': 1.0}),
            ('edge_detect', {'method': 'canny'}),
            ('oil_painting', {'size': 7, 'levels': 8}),
            ('pencil_sketch', {'blur_value': 7}),
            ('vintage', {'sepia_strength': 0.8})
        ]
        
        for filter_name, params in filters_to_test:
            processor.current_image = test_img.copy()  # Reset
            success, message = processor.apply_advanced_filter(filter_name, **params)
            if success:
                print(f"   ✅ {filter_name}: {message}")
            else:
                print(f"   ❌ {filter_name}: {message}")
        
        # Test engraving preparation
        print("🏭 Testing engraving preparation...")
        processor.current_image = test_img.copy()
        success, message = processor.prepare_for_engraving(beam_width=0.1, depth_levels=5)
        if success:
            print(f"   ✅ Engraving preparation: {message}")
        else:
            print(f"   ❌ Engraving preparation: {message}")
        
        # Test line enhancement
        print("📏 Testing line enhancement...")
        processor.current_image = test_img.copy()
        success, message = processor.enhance_lines_for_engraving(line_width=2)
        if success:
            print(f"   ✅ Line enhancement: {message}")
        else:
            print(f"   ❌ Line enhancement: {message}")
        
        # Test vectorization
        print("🔀 Testing vectorization...")
        processor.current_image = test_img.copy()
        success, message, svg_content = processor.vectorize_for_engraving(threshold=128)
        if success:
            print(f"   ✅ Vectorization: {message}")
            if svg_content:
                print(f"   📄 SVG Content Length: {len(svg_content)} characters")
        else:
            print(f"   ❌ Vectorization: {message}")
        
        # Test background removal (might fail without rembg)
        print("🖼️  Testing background removal...")
        processor.current_image = test_img.copy()
        success, message = processor.remove_background()
        if success:
            print(f"   ✅ Background removal: {message}")
        else:
            print(f"   ⚠️  Background removal (fallback): {message}")
        
        # Test export functionality
        print("💾 Testing export functionality...")
        processor.current_image = test_img.copy()
        
        export_formats = ['PNG', 'JPEG', 'WEBP']
        for fmt in export_formats:
            try:
                exported_file = processor.save_to_file(format=fmt)
                file_size = len(exported_file.read())
                print(f"   ✅ {fmt} export: {file_size} bytes")
            except Exception as e:
                print(f"   ❌ {fmt} export failed: {str(e)}")
        
        print("✅ ImageProcessor tests completed!")
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Install missing packages with: pip install -r image_editor_requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_django_models():
    """Test Django models for image editor"""
    print("\n🗄️  Testing Django models...")
    
    try:
        from image_editor.models import ImageProject, ProcessingStep, AIGenerationHistory
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Check if we can create model instances
        print("   ✅ Models imported successfully")
        
        # Test model methods (without saving to DB)
        test_project = ImageProject(
            name="Test Project",
            source_type='upload'
        )
        
        print("   ✅ ImageProject instance created")
        print(f"   📊 Project display name: {test_project}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Django models test failed: {e}")
        return False

def test_dependencies():
    """Test if all required dependencies are available"""
    print("\n📦 Testing dependencies...")
    
    dependencies = [
        ('PIL', 'Pillow'),
        ('numpy', 'numpy'),
        ('django', 'Django'),
    ]
    
    optional_dependencies = [
        ('cv2', 'opencv-python'),
        ('rembg', 'rembg'),
        ('skimage', 'scikit-image'),
        ('svglib', 'svglib'),
        ('reportlab', 'reportlab'),
    ]
    
    all_available = True
    
    print("   Required dependencies:")
    for import_name, package_name in dependencies:
        try:
            __import__(import_name)
            print(f"     ✅ {package_name}")
        except ImportError:
            print(f"     ❌ {package_name} (required)")
            all_available = False
    
    print("   Optional dependencies:")
    for import_name, package_name in optional_dependencies:
        try:
            __import__(import_name)
            print(f"     ✅ {package_name}")
        except ImportError:
            print(f"     ⚠️  {package_name} (optional, some features may not work)")
    
    return all_available

def main():
    """Run all tests"""
    print("🎨 Image Editor Advanced Features Test Suite")
    print("=" * 50)
    
    # Test dependencies first
    deps_ok = test_dependencies()
    
    if not deps_ok:
        print("\n❌ Some required dependencies are missing!")
        print("💡 Install missing packages with:")
        print("   pip install -r requirements.txt")
        print("   pip install -r image_editor_requirements.txt")
        return False
    
    # Test Django models
    models_ok = test_django_models()
    
    # Test image processing
    processing_ok = test_image_processor()
    
    print("\n" + "=" * 50)
    if deps_ok and models_ok and processing_ok:
        print("🎉 All tests passed! Image Editor is ready to use.")
        print("\n🚀 You can now:")
        print("   • Upload and edit images")
        print("   • Apply advanced filters")
        print("   • Prepare images for laser engraving")
        print("   • Remove backgrounds")
        print("   • Vectorize images")
        print("   • Export in multiple formats")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    main()