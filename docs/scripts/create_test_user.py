#!/usr/bin/env python3
"""
Create test user and test data for SoMi-Plan
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

def create_test_data():
    """Create test user and test plan data"""
    
    print("🧪 Creating Test Data for SoMi-Plan")
    print("=" * 50)
    
    try:
        from accounts.models import CustomUser
        from somi_plan.models import PostingPlan, Platform, PostContent
        
        # Create test user
        email = 'somiplan_test@example.com'
        username = 'somiplan_test'
        password = 'testpass123'
        
        # Try to get existing user first, then create if needed
        try:
            user = CustomUser.objects.get(username=username)
            created = False
            print(f"✅ Found existing user: {username}")
        except CustomUser.DoesNotExist:
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name='SoMi',
                last_name='Test'
            )
            created = True
            print(f"✅ Created new user: {username}")
        except CustomUser.MultipleObjectsReturned:
            user = CustomUser.objects.filter(username=username).first()
            created = False
            print(f"✅ Found multiple users, using first: {username}")
        
        # Ensure password is set correctly
        user.set_password(password)
        user.save()
        
        print(f"   📧 Email: {email}")
        print(f"   🔑 Password: {password}")
        
        # Create test platform
        platform, created = Platform.objects.get_or_create(
            name='Instagram',
            defaults={
                'icon': 'fab fa-instagram',
                'color': '#E4405F',
                'character_limit': 2200
            }
        )
        
        if created:
            print(f"✅ Created platform: {platform.name}")
        else:
            print(f"✅ Platform already exists: {platform.name}")
        
        # Create test plan with ID 4
        plan, created = PostingPlan.objects.get_or_create(
            id=4,
            defaults={
                'title': 'Test Social Media Plan',
                'description': 'Ein Testplan für Social Media Posts',
                'user': user,
                'platform': platform,
                'status': 'active'
            }
        )
        
        if created:
            print(f"✅ Created plan: {plan.title}")
        else:
            print(f"✅ Plan already exists: {plan.title}")
            # Update plan to ensure it belongs to test user
            plan.user = user
            plan.save()
        
        # Create test posts
        test_posts = [
            {
                'title': 'Willkommen bei unserem Service',
                'content': 'Herzlich willkommen! 🎉 Entdecke unsere neuesten Features und lass dich inspirieren. #welcome #newfeatures',
                'hashtags': '#welcome #newfeatures #inspiration',
                'call_to_action': 'Besuche unsere Website für mehr Infos!'
            },
            {
                'title': 'Tipps für bessere Social Media Posts',
                'content': '💡 3 Tipps für bessere Posts:\n1. Verwende ansprechende Bilder\n2. Schreibe authentische Texte\n3. Nutze relevante Hashtags',
                'hashtags': '#socialmedia #tips #marketing',
                'call_to_action': 'Welcher Tipp hilft dir am meisten? Kommentiere!'
            },
            {
                'title': 'Behind the Scenes',
                'content': '🎬 Ein Blick hinter die Kulissen unseres Teams. So entstehen unsere Inhalte - mit viel Leidenschaft und Kreativität!',
                'hashtags': '#behindthescenes #team #creativity',
                'call_to_action': 'Folge uns für mehr Behind-the-Scenes Content!'
            }
        ]
        
        for i, post_data in enumerate(test_posts):
            post, created = PostContent.objects.get_or_create(
                posting_plan=plan,
                title=post_data['title'],
                defaults={
                    'content': post_data['content'],
                    'hashtags': post_data['hashtags'],
                    'call_to_action': post_data['call_to_action'],
                    'ai_generated': True
                }
            )
            
            if created:
                print(f"✅ Created post: {post.title}")
            else:
                print(f"✅ Post already exists: {post.title}")
        
        print(f"\n🎯 Test Data Summary:")
        print(f"   👤 User: {user.username} ({user.email})")
        print(f"   📱 Platform: {platform.name}")
        print(f"   📋 Plan: {plan.title} (ID: {plan.id})")
        print(f"   📝 Posts: {plan.posts.count()}")
        
        print(f"\n🌐 Test URLs:")
        print(f"   Login: http://127.0.0.1:8000/accounts/login/")
        print(f"   Plan Detail: http://127.0.0.1:8000/somi-plan/plan/4/")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = create_test_data()
    
    if success:
        print(f"\n🎉 Test data created successfully!")
        print(f"\n📋 Next Steps:")
        print(f"1. Login with: {username} / {password}")
        print(f"2. Visit: http://127.0.0.1:8000/somi-plan/plan/4/")
        print(f"3. Test JavaScript functionality")
    else:
        print(f"\n❌ Failed to create test data")