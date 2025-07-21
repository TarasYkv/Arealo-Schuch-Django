#!/usr/bin/env python3
"""
Simple test to isolate the blog creation issue
"""

import os
import sys
import django

# Django setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arealo_schuch.settings')
django.setup()

def test_simple_blog_creation():
    """Test simple blog post creation"""
    
    print("🧪 TESTE EINFACHE BLOG-POST ERSTELLUNG")
    print("=" * 50)
    
    try:
        from shopify_manager.models import ShopifyBlog, ShopifyStore
        from shopify_manager.shopify_api import ShopifyAPIClient
        
        # Get a blog
        blog = ShopifyBlog.objects.first()
        if not blog:
            print("❌ Kein Blog gefunden")
            return
            
        print(f"📘 Teste mit Blog: {blog.title}")
        print(f"🏪 Store: {blog.store.shop_name}")
        
        # Get API client
        api = ShopifyAPIClient(blog.store)
        
        # Create minimal test article data
        article_data = {
            'id': 'test_12345',
            'title': 'Test Blog Post',
            'handle': 'test-blog-post',
            'body_html': '<p>Test content</p>',
            'summary_html': 'Test summary',
            'author': 'Test Author',
            'status': 'published',
            'published_at': '2024-01-01T10:00:00Z',
            'created_at': '2024-01-01T10:00:00Z',
            'updated_at': '2024-01-01T10:00:00Z',
            'tags': 'test,blog',
            'image': None
        }
        
        print(f"📝 Teste Erstellung mit Artikel-Daten:")
        print(f"   ID: {article_data['id']}")
        print(f"   Title: {article_data['title']}")
        
        # Try to create the blog post
        try:
            post, created = api._create_or_update_blog_post(blog, article_data)
            print(f"✅ ERFOLG: Created={created}, Post={post.title}")
            
            # Clean up test post
            if created:
                post.delete()
                print(f"🧹 Test-Post gelöscht")
                
        except Exception as e:
            print(f"❌ FEHLER bei Blog-Post Erstellung: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Allgemeiner Fehler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_blog_creation()