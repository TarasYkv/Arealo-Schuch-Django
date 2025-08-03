#!/usr/bin/env python3
"""
Test SoMi-Plan access as logged in user
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

def test_logged_in_access():
    """Test accessing the plan detail page as logged in user"""
    
    print("🧪 Testing Logged-In Access to SoMi-Plan")
    print("=" * 50)
    
    try:
        from django.test import Client
        from accounts.models import CustomUser
        
        # Create test client
        client = Client()
        
        # Get test user
        username = 'somiplan_test'
        try:
            user = CustomUser.objects.get(username=username)
            print(f"✅ Found test user: {user.username}")
        except CustomUser.DoesNotExist:
            print(f"❌ Test user not found: {username}")
            print("Run create_test_user.py first!")
            return False
        
        # Login the user
        client.force_login(user)
        print(f"✅ Logged in as: {user.username}")
        
        # Test access to plan detail
        response = client.get('/somi-plan/plan/4/')
        
        print(f"\n📊 Response Analysis:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            html_content = response.content.decode('utf-8')
            
            # Check for key elements
            checks = {
                'SoMi-Plan header': 'SoMi-Plan' in html_content,
                'Plan title': 'TikTok' in html_content or 'Plan' in html_content,
                'Emergency JavaScript': 'EMERGENCY JAVASCRIPT' in html_content,
                'showPostModal function': 'showPostModal' in html_content,
                'schedulePost function': 'schedulePost' in html_content,
                'Post cards': 'post-card' in html_content or 'onclick="showPostModal' in html_content,
                'Bootstrap': 'bootstrap' in html_content.lower(),
                'Modal HTML': 'postModal' in html_content,
                'Console log': 'console.log' in html_content
            }
            
            print(f"\n🔍 Content Analysis:")
            all_good = True
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check}")
                if not result:
                    all_good = False
            
            # Check specific onclick handlers
            onclick_patterns = [
                'onclick="showPostModal(',
                'onclick="schedulePost(',
                'onclick="generateMorePosts('
            ]
            
            print(f"\n🖱️ OnClick Handlers:")
            for pattern in onclick_patterns:
                found = pattern in html_content
                status = "✅" if found else "❌"
                print(f"   {status} {pattern}")
                if not found:
                    all_good = False
            
            # Show HTML snippet
            print(f"\n📄 HTML Length: {len(html_content):,} characters")
            
            if 'EMERGENCY JAVASCRIPT' in html_content:
                print(f"✅ Emergency JavaScript found in HTML!")
                
                # Find the emergency JS section
                start = html_content.find('EMERGENCY JAVASCRIPT')
                end = html_content.find('</script>', start)
                if end > start:
                    js_section = html_content[start:end + 9]
                    print(f"\n📜 Emergency JavaScript Section:")
                    print("-" * 30)
                    print(js_section[:300] + "..." if len(js_section) > 300 else js_section)
                    print("-" * 30)
            
            # Check context data
            if hasattr(response, 'context') and response.context:
                context = response.context
                print(f"\n📊 Template Context:")
                
                if 'plan' in context:
                    plan = context['plan']
                    print(f"   ✅ Plan: {plan.title}")
                else:
                    print(f"   ❌ No plan in context")
                    all_good = False
                
                if 'posts' in context:
                    posts = context['posts']
                    print(f"   ✅ Posts: {len(posts)} found")
                    
                    # Show first post details
                    if posts:
                        first_post = posts[0]
                        print(f"       First post: {first_post.title}")
                else:
                    print(f"   ❌ No posts in context")
                    all_good = False
            
            return all_good
            
        elif response.status_code == 404:
            print(f"❌ Plan not found (404)")
            return False
        elif response.status_code == 302:
            print(f"❌ Redirect detected (still not logged in?)")
            print(f"   Redirect to: {response.get('Location', 'Unknown')}")
            return False
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_logged_in_access()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SUCCESS: Logged-in access works!")
        print("JavaScript should now be functional in the browser.")
        print("\n🌐 Test in browser:")
        print("1. Go to: http://127.0.0.1:8000/accounts/login/")
        print("2. Login with: somiplan_test / testpass123")
        print("3. Visit: http://127.0.0.1:8000/somi-plan/plan/4/")
        print("4. Click on post cards to test showPostModal")
    else:
        print("❌ FAILED: Issues found with logged-in access")
        print("Check the error messages above.")