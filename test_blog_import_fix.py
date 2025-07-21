#!/usr/bin/env python3
"""
Test-Script für die neuen Shopify Blog Import Lösungen
"""

import os
import sys
import django

# Django Setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arealo_schuch.settings')
django.setup()

from shopify_manager.models import ShopifyBlog, ShopifyStore
from shopify_manager.shopify_import import ShopifyImportManager

def test_blog_import_solutions():
    """Teste alle neuen Blog Import Lösungen"""
    
    print("🧪 TESTE NEUE SHOPIFY BLOG IMPORT LÖSUNGEN")
    print("=" * 60)
    
    # Hole ersten Blog
    try:
        blog = ShopifyBlog.objects.first()
        if not blog:
            print("❌ Kein Blog gefunden. Zuerst Blogs importieren!")
            return
            
        print(f"📘 Teste mit Blog: {blog.title}")
        print(f"🏪 Store: {blog.store.shop_name}")
        print(f"🆔 Blog ID: {blog.shopify_id}")
        print()
        
        # Erstelle Import Manager
        manager = ShopifyImportManager(blog.store)
        
        # TEST 1: Moderne REST API mit cursor-basierter Pagination
        print("🔬 TEST 1: Moderne REST API (cursor-basierte Pagination)")
        print("-" * 50)
        
        try:
            log1 = manager.import_blog_posts(blog, 'all')  # Verwendet neue _fetch_all_blog_posts
            print(f"✅ Erfolg: {log1.products_success} Posts importiert")
            print(f"❌ Fehler: {log1.products_failed} Posts fehlgeschlagen")
            print(f"📊 Status: {log1.status}")
            if log1.error_message:
                print(f"⚠️ Fehler: {log1.error_message}")
        except Exception as e:
            print(f"❌ Test 1 fehlgeschlagen: {e}")
        
        print()
        
        # TEST 2: GraphQL API
        print("🔬 TEST 2: GraphQL API")
        print("-" * 50)
        
        try:
            log2 = manager.import_blog_posts(blog, 'all_graphql')
            print(f"✅ Erfolg: {log2.products_success} Posts importiert")
            print(f"❌ Fehler: {log2.products_failed} Posts fehlgeschlagen")
            print(f"📊 Status: {log2.status}")
            if log2.error_message:
                print(f"⚠️ Fehler: {log2.error_message}")
        except Exception as e:
            print(f"❌ Test 2 fehlgeschlagen: {e}")
        
        print()
        
        # TEST 3: Robuste Fallback-Strategie
        print("🔬 TEST 3: Robuste Fallback-Strategie")
        print("-" * 50)
        
        try:
            log3 = manager.import_blog_posts(blog, 'all_robust')
            print(f"✅ Erfolg: {log3.products_success} Posts importiert")
            print(f"❌ Fehler: {log3.products_failed} Posts fehlgeschlagen")
            print(f"📊 Status: {log3.status}")
            if log3.error_message:
                print(f"⚠️ Fehler: {log3.error_message}")
        except Exception as e:
            print(f"❌ Test 3 fehlgeschlagen: {e}")
        
        print()
        print("🏁 TESTS ABGESCHLOSSEN")
        print("=" * 60)
        
        # Zusammenfassung
        from shopify_manager.models import ShopifyBlogPost
        total_posts = ShopifyBlogPost.objects.filter(blog=blog).count()
        print(f"📊 Gesamt importierte Blog-Posts: {total_posts}")
        
        if total_posts > 250:
            print("✅ PROBLEM GELÖST: Mehr als 250 Posts wurden importiert!")
        else:
            print("⚠️ Möglicherweise noch nicht alle Posts - prüfe Logs")
            
    except Exception as e:
        print(f"❌ Allgemeiner Fehler: {e}")
        import traceback
        traceback.print_exc()

def test_direct_api_calls():
    """Teste direkte API-Calls"""
    
    print("🧪 TESTE DIREKTE API CALLS")
    print("=" * 60)
    
    try:
        store = ShopifyStore.objects.first()
        blog = ShopifyBlog.objects.first()
        
        if not store or not blog:
            print("❌ Store oder Blog nicht gefunden")
            return
            
        from shopify_manager.shopify_api import ShopifyAPIClient
        api = ShopifyAPIClient(store)
        
        print(f"🔬 Teste moderne REST API mit Blog ID: {blog.shopify_id}")
        
        # Test moderne REST API
        success, articles, message, next_page_info = api.fetch_blog_posts(blog.shopify_id, limit=50)
        
        if success:
            print(f"✅ Moderne REST API: {len(articles)} Posts abgerufen")
            print(f"📄 Next page_info: {'Ja' if next_page_info else 'Nein'}")
            
            # Zeige erste 3 Posts
            for i, article in enumerate(articles[:3]):
                print(f"   {i+1}. {article['title'][:50]}... (ID: {article['id']})")
        else:
            print(f"❌ Moderne REST API Fehler: {message}")
            
        print()
        
        # Test GraphQL API
        print(f"🔬 Teste GraphQL API mit Blog ID: {blog.shopify_id}")
        
        success, articles, message, next_cursor = api.fetch_blog_posts_graphql(blog.shopify_id, limit=50)
        
        if success:
            print(f"✅ GraphQL API: {len(articles)} Posts abgerufen")
            print(f"📄 Next cursor: {'Ja' if next_cursor else 'Nein'}")
            
            # Zeige erste 3 Posts
            for i, article in enumerate(articles[:3]):
                print(f"   {i+1}. {article['title'][:50]}... (ID: {article['id']})")
        else:
            print(f"❌ GraphQL API Fehler: {message}")
            
    except Exception as e:
        print(f"❌ API Test Fehler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 STARTE SHOPIFY BLOG IMPORT FIX TESTS")
    print("=" * 60)
    
    # Wähle Test-Modus
    print("Verfügbare Tests:")
    print("1. Vollständige Import-Tests (empfohlen)")
    print("2. Direkte API-Call Tests")
    print("3. Beide")
    
    choice = input("Wähle Test (1-3): ").strip()
    
    if choice in ['1', '3']:
        test_blog_import_solutions()
        
    if choice in ['2', '3']:
        print()
        test_direct_api_calls()
        
    print()
    print("🎉 TESTS BEENDET")
    print()
    print("💡 NÄCHSTE SCHRITTE:")
    print("   - Prüfe die Logs auf erfolgreiche Pagination")
    print("   - Verwende 'all_robust' Modus für Production")
    print("   - Erwäge GraphQL für langfristige Lösung")