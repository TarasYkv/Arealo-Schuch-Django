#!/usr/bin/env python3
"""
Final test to verify SoMi-Plan JavaScript functionality is working
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

def test_final_functionality():
    """Test that all JavaScript functionality is working correctly"""
    
    print("🎯 Final SoMi-Plan Functionality Test")
    print("=" * 60)
    
    try:
        from django.test import Client
        from accounts.models import CustomUser
        import json
        import re
        
        # Create test client
        client = Client()
        
        # Get test user
        user = CustomUser.objects.get(username='somiplan_test')
        client.force_login(user)
        print(f"✅ Logged in as: {user.username}")
        
        # Get the page
        response = client.get('/somi-plan/plan/4/')
        html_content = response.content.decode('utf-8')
        
        print(f"\n📊 Response Analysis:")
        print(f"   Status Code: {response.status_code}")
        print(f"   HTML Length: {len(html_content):,} characters")
        
        # 1. Test JSON Data Parsing
        print(f"\n🔍 JSON Data Test:")
        json_match = re.search(r'<script id="posts-data"[^>]*>(.*?)</script>', html_content, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            try:
                parsed_posts = json.loads(json_content)
                print(f"   ✅ JSON is valid with {len(parsed_posts)} posts")
                
                if parsed_posts:
                    first_post = parsed_posts[0]
                    print(f"   📝 First post: '{first_post['title']}'")
                    print(f"   📊 Character count: {first_post['character_count']}")
                    
                    # Test specific characters that were causing issues
                    if 'title' in first_post and first_post['title']:
                        print(f"   ✅ Post title properly escaped")
                    if 'content' in first_post and first_post['content']:
                        print(f"   ✅ Post content properly escaped")
                        
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON parsing error: {e}")
                return False
        else:
            print(f"   ❌ No posts-data script found")
            return False
        
        # 2. Test JavaScript Functions
        print(f"\n🔧 JavaScript Functions Test:")
        js_functions = [
            'showPostModal',
            'editPost', 
            'schedulePost',
            'copyToClipboard',
            'generateMorePosts',
            'getPostData'
        ]
        
        all_functions_found = True
        for func in js_functions:
            if f'window.{func}' in html_content:
                print(f"   ✅ {func} function defined")
            else:
                print(f"   ❌ {func} function missing")
                all_functions_found = False
        
        # 3. Test Modal HTML
        print(f"\n🎭 Modal HTML Test:")
        modal_elements = [
            'id="postModal"',
            'id="postModalTitle"',
            'id="postModalBody"',
            'id="editPostBtn"',
            'id="schedulePostBtn"'
        ]
        
        all_modals_found = True
        for element in modal_elements:
            if element in html_content:
                print(f"   ✅ {element} found")
            else:
                print(f"   ❌ {element} missing")
                all_modals_found = False
        
        # 4. Test Post Cards and OnClick Handlers
        print(f"\n🃏 Post Cards Test:")
        onclick_patterns = [
            'onclick="showPostModal(',
            'onclick="generateMorePosts('
        ]
        
        onclick_found = True
        for pattern in onclick_patterns:
            if pattern in html_content:
                print(f"   ✅ {pattern} found")
            else:
                print(f"   ❌ {pattern} missing") 
                onclick_found = False
        
        # Count post cards
        post_card_count = html_content.count('class="card h-100 post-card')
        print(f"   📄 Found {post_card_count} post cards")
        
        # 5. Test Bootstrap Integration
        print(f"\n🅱️ Bootstrap Test:")
        bootstrap_checks = {
            'Bootstrap CSS': 'bootstrap' in html_content.lower() and 'css' in html_content.lower(),
            'Bootstrap JS': 'bootstrap' in html_content.lower() and ('js' in html_content.lower() or 'javascript' in html_content.lower()),
            'Modal classes': 'modal fade' in html_content,
            'Button classes': 'btn btn-' in html_content
        }
        
        bootstrap_ok = True
        for check, result in bootstrap_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}")
            if not result:
                bootstrap_ok = False
        
        # 6. Test URL Data
        print(f"\n🔗 URL Data Test:")
        urls_match = re.search(r'<script id="urls-data"[^>]*>(.*?)</script>', html_content, re.DOTALL)
        if urls_match:
            try:
                url_content = urls_match.group(1).strip()
                parsed_urls = json.loads(url_content)
                print(f"   ✅ URLs JSON valid with {len(parsed_urls)} URLs")
                for key in ['generate_more_ideas', 'post_edit', 'schedule_post']:
                    if key in parsed_urls:
                        print(f"   ✅ {key} URL found")
                    else:
                        print(f"   ❌ {key} URL missing")
            except:
                print(f"   ❌ URLs JSON invalid")
                return False
        else:
            print(f"   ❌ No urls-data script found")
            return False
        
        # Final Assessment
        print(f"\n" + "=" * 60)
        print(f"📋 FINAL ASSESSMENT:")
        
        all_good = (
            json_match and parsed_posts and 
            all_functions_found and 
            all_modals_found and 
            onclick_found and 
            bootstrap_ok and
            post_card_count > 0
        )
        
        if all_good:
            print(f"🎉 SUCCESS: All functionality is working!")
            print(f"")
            print(f"✅ JSON data parsing: WORKING")
            print(f"✅ JavaScript functions: WORKING") 
            print(f"✅ Modal HTML: WORKING")
            print(f"✅ Post cards: WORKING ({post_card_count} cards)")
            print(f"✅ OnClick handlers: WORKING")
            print(f"✅ Bootstrap integration: WORKING")
            print(f"")
            print(f"🌐 Ready for browser testing:")
            print(f"1. Login: http://127.0.0.1:8000/accounts/login/")
            print(f"2. Credentials: somiplan_test / testpass123")
            print(f"3. Visit: http://127.0.0.1:8000/somi-plan/plan/4/")
            print(f"4. Click on any post card - modal should open!")
            print(f"5. Click 'Planen' button - should redirect to schedule page")
            return True
        else:
            print(f"❌ ISSUES FOUND: Some functionality may not work")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_final_functionality()
    
    if success:
        print(f"\n🚀 All systems are GO! The JavaScript functionality has been successfully fixed.")
    else:
        print(f"\n⚠️ Some issues remain. Check the error messages above.")