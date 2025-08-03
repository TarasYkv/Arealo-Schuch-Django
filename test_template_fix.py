#!/usr/bin/env python3
"""
Template Fix Verification Script
Tests if the showPostModal JavaScript function is properly loaded after template fixes
"""

import os
import sys
import django
from django.conf import settings
from django.template.loader import get_template
from django.template import Context
from django.test import RequestFactory
from django.contrib.auth.models import User

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

def test_template_rendering():
    """Test if the plan_detail template renders properly with JavaScript"""
    
    try:
        # Import after Django setup
        from somi_plan.models import PostingPlan, Platform, PostContent
        
        print("🔍 Testing Template Fix...")
        print("=" * 50)
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.get('/somi-plan/plan/4/')
        
        # Create or get test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        request.user = user
        
        # Get or create test platform
        ig_platform, created = Platform.objects.get_or_create(
            name='Instagram',
            defaults={
                'icon': 'fab fa-instagram',
                'color': '#E4405F',
                'character_limit': 2200
            }
        )
        
        # Get or create test plan
        plan, created = PostingPlan.objects.get_or_create(
            id=4,
            defaults={
                'title': 'Test Plan',
                'description': 'Test Description',
                'user': user,
                'platform': ig_platform,
                'status': 'active'
            }
        )
        
        # Create test posts
        posts = []
        for i in range(2):
            post, created = PostContent.objects.get_or_create(
                posting_plan=plan,
                title=f'Test Post {i+1}',
                defaults={
                    'content': f'This is test content for post {i+1}',
                    'hashtags': '#test #post',
                    'call_to_action': 'Visit our website!',
                    'ai_generated': True
                }
            )
            posts.append(post)
        
        print(f"✅ Created test data:")
        print(f"   - Plan: {plan.title}")
        print(f"   - Posts: {len(posts)}")
        
        # Test template rendering
        template = get_template('somi_plan/plan_detail.html')
        context = {
            'plan': plan,
            'posts': posts,
            'request': request
        }
        
        rendered = template.render(context, request)
        
        # Check if JavaScript functions are present
        js_checks = {
            'showPostModal function': 'window.showPostModal = function' in rendered,
            'editPost function': 'window.editPost = function' in rendered,
            'schedulePost function': 'window.schedulePost = function' in rendered,
            'generateMorePosts function': 'window.generateMorePosts = function' in rendered,
            'copyToClipboard function': 'window.copyToClipboard = function' in rendered,
            'child_js block': '{% block child_js %}' in rendered or 'child_js' in str(template),
            'Modal HTML': 'id="postModal"' in rendered,
            'Post cards with onclick': 'onclick="showPostModal(' in rendered
        }
        
        print(f"\n🧪 JavaScript Function Checks:")
        print("-" * 30)
        all_good = True
        for check, result in js_checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check}: {result}")
            if not result:
                all_good = False
        
        # Check template inheritance
        print(f"\n🏗️ Template Structure Checks:")
        print("-" * 30)
        
        structure_checks = {
            'Extends somi_plan/base.html': '{% extends "somi_plan/base.html" %}' in rendered,
            'Has child_js block': '{% block child_js %}' in rendered,
            'JavaScript in child_js': '<script>' in rendered and 'window.showPostModal' in rendered
        }
        
        for check, result in structure_checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check}: {result}")
            if not result:
                all_good = False
        
        print(f"\n📊 Template Size: {len(rendered):,} characters")
        
        if all_good:
            print(f"\n🎉 SUCCESS: All checks passed! The template fix should work.")
            print(f"   The showPostModal function should now be properly loaded.")
        else:
            print(f"\n⚠️  ISSUES FOUND: Some checks failed. Review the output above.")
            
            # Show a snippet of where JavaScript should be
            js_start = rendered.find('<script>')
            if js_start > 0:
                js_snippet = rendered[js_start:js_start + 200]
                print(f"\n📝 JavaScript snippet found:")
                print(f"   {js_snippet}...")
            
        return all_good
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_base_template_structure():
    """Test the base template structure"""
    
    print(f"\n🏗️ Testing Base Template Structure...")
    print("=" * 50)
    
    try:
        # Read the base template file
        base_template_path = 'somi_plan/templates/somi_plan/base.html'
        with open(base_template_path, 'r', encoding='utf-8') as f:
            base_content = f.read()
        
        # Check structure
        checks = {
            'Has page_js block': '{% block page_js %}' in base_content,
            'Has child_js block': '{% block child_js %}' in base_content,
            'block.super in child_js': '{{ block.super }}' in base_content and base_content.find('{{ block.super }}') > base_content.find('{% block child_js %}'),
            'Proper block nesting': '{% block child_js %}' in base_content and '{% endblock %}' in base_content
        }
        
        all_good = True
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check}: {result}")
            if not result:
                all_good = False
        
        # Show the relevant section
        child_js_start = base_content.find('{% block child_js %}')
        if child_js_start > 0:
            child_js_end = base_content.find('{% endblock %}', child_js_start) + len('{% endblock %}')
            child_js_section = base_content[child_js_start:child_js_end]
            print(f"\n📝 child_js block structure:")
            print(f"   {child_js_section}")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Error reading base template: {e}")
        return False

if __name__ == '__main__':
    print("🧪 SoMi-Plan Template Fix Verification")
    print("=" * 60)
    
    # Test base template structure
    base_ok = test_base_template_structure()
    
    # Test full template rendering
    template_ok = test_template_rendering()
    
    print(f"\n" + "=" * 60)
    if base_ok and template_ok:
        print("🎉 ALL TESTS PASSED!")
        print("✅ The showPostModal function should now work properly.")
        print("✅ Post cards should be clickable at: http://127.0.0.1:8000/somi-plan/plan/4/")
    else:
        print("⚠️  SOME TESTS FAILED!")
        if not base_ok:
            print("❌ Base template structure needs fixing")
        if not template_ok:
            print("❌ Template rendering has issues")
    
    print(f"\n💡 Next step: Test in browser at http://127.0.0.1:8000/somi-plan/plan/4/")