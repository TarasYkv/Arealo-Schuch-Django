#!/usr/bin/env python3
"""
Debug Django template rendering for plan_detail
"""

import os
import sys
import requests
from pathlib import Path

def test_direct_template_access():
    """Test if we can access the plan_detail template content directly"""
    
    print("🧪 Direct Template Rendering Test")
    print("=" * 50)
    
    try:
        # Get the HTML content
        response = requests.get('http://127.0.0.1:8000/somi-plan/plan/4/', timeout=10)
        html_content = response.text
        
        print(f"✅ Response status: {response.status_code}")
        print(f"📊 HTML length: {len(html_content):,} characters")
        
        # Look for specific template content that should be there
        template_markers = {
            'Base template loaded': '<title>' in html_content,
            'SoMi-Plan header': 'SoMi-Plan' in html_content,
            'Plan title in page': 'Test Plan' in html_content or 'plan' in html_content.lower(),
            'Bootstrap CSS': 'bootstrap' in html_content.lower(),
            'Bootstrap JS': 'bootstrap' in html_content.lower(),
            'Post cards container': 'post-card' in html_content,
            'Main content block': 'main_content' in html_content or 'col-lg-8' in html_content,
            'Emergency JavaScript': 'EMERGENCY JAVASCRIPT' in html_content,
            'showPostModal emergency': 'showPostModal' in html_content,
            'Console log emergency': 'console.log' in html_content
        }
        
        print(f"\n🔍 Template Content Analysis:")
        all_good = True
        for marker, found in template_markers.items():
            status = "✅" if found else "❌"
            print(f"   {status} {marker}")
            if not found:
                all_good = False
        
        # Check if our specific onclick handlers exist
        onclick_patterns = [
            'onclick="showPostModal(',
            'onclick="schedulePost(',
            'onclick="generateMorePosts('
        ]
        
        print(f"\n🖱️ OnClick Handler Analysis:")
        for pattern in onclick_patterns:
            found = pattern in html_content
            status = "✅" if found else "❌"
            print(f"   {status} {pattern}")
            if not found:
                all_good = False
        
        # Show a snippet of the HTML to see what's actually being rendered
        if len(html_content) > 1000:
            print(f"\n📄 HTML Snippet (first 500 chars):")
            print("-" * 30)
            print(html_content[:500])
            print("...")
            print("-" * 30)
            
            # Show end of HTML
            print(f"\n📄 HTML End (last 300 chars):")
            print("-" * 30)
            print("...")
            print(html_content[-300:])
            print("-" * 30)
        
        # Try to find the actual post cards
        if 'post-card' in html_content:
            print(f"\n✅ Post cards found in HTML")
        else:
            print(f"\n❌ No post cards found - checking alternatives...")
            alternatives = ['card', 'post', 'col-md-6', 'col-lg-4']
            for alt in alternatives:
                if alt in html_content:
                    print(f"   ✅ Found alternative: {alt}")
                else:
                    print(f"   ❌ Missing alternative: {alt}")
        
        return all_good, html_content
        
    except Exception as e:
        print(f"❌ Error accessing template: {e}")
        return False, None

def check_view_function():
    """Check if the view function is working correctly"""
    
    print(f"\n🔍 View Function Check:")
    print("-" * 30)
    
    try:
        # Check if the view returns the expected context
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
        django.setup()
        
        from django.test import Client
        from django.contrib.auth.models import User
        from somi_plan.models import PostingPlan, Platform
        
        # Create test client
        client = Client()
        
        # Try to create or get a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        
        # Login the test user
        client.force_login(user)
        
        # Try to access the plan detail view
        response = client.get('/somi-plan/plan/4/')
        
        print(f"✅ View response status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ View is accessible")
            
            # Check context variables
            context_keys = response.context.keys() if hasattr(response, 'context') and response.context else []
            print(f"📊 Context keys: {list(context_keys)}")
            
            if 'plan' in context_keys:
                plan = response.context['plan']
                print(f"✅ Plan in context: {plan.title if hasattr(plan, 'title') else 'No title'}")
            else:
                print(f"❌ No plan in context")
                
            if 'posts' in context_keys:
                posts = response.context['posts']
                print(f"✅ Posts in context: {len(posts) if hasattr(posts, '__len__') else 'Invalid posts'}")
            else:
                print(f"❌ No posts in context")
                
        elif response.status_code == 404:
            print(f"❌ Plan with ID 4 not found")
            
            # Try to create a test plan
            print(f"🔧 Creating test plan...")
            platform, _ = Platform.objects.get_or_create(
                name='Test Platform',
                defaults={'icon': 'fas fa-test', 'color': '#000000', 'character_limit': 280}
            )
            
            plan, _ = PostingPlan.objects.get_or_create(
                id=4,
                defaults={
                    'title': 'Test Plan',
                    'description': 'Test Description',
                    'user': user,
                    'platform': platform,
                    'status': 'active'
                }
            )
            
            print(f"✅ Test plan created: {plan.title}")
            
            # Try again
            response = client.get('/somi-plan/plan/4/')
            print(f"✅ Retry response status: {response.status_code}")
            
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Error checking view: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🔍 Django Template Rendering Debug")
    print("=" * 60)
    
    # Test direct template access
    template_ok, html_content = test_direct_template_access()
    
    # Test view function
    view_ok = check_view_function()
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   Template rendering: {'✅ OK' if template_ok else '❌ Issues'}")
    print(f"   View function: {'✅ OK' if view_ok else '❌ Issues'}")
    
    if not template_ok:
        print("\n🔧 Template Issues Detected:")
        print("   - Emergency JavaScript not found in HTML")
        print("   - Template blocks may not be rendering correctly")
        print("   - Check template inheritance chain")
        
    if not view_ok:
        print("\n🔧 View Issues Detected:")
        print("   - View function may not be working correctly")
        print("   - Database objects may be missing")
        print("   - URL routing may have issues")

if __name__ == '__main__':
    main()