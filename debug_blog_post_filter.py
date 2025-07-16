#!/usr/bin/env python
"""
Debug script to test blog post filtering behavior
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'werbemacher.settings')
django.setup()

from shopify_manager.models import ShopifyBlogPost, ShopifyBlog, ShopifyStore
from django.db.models import Q

def debug_blog_post_filtering():
    print("=== BLOG POST FILTERING DEBUG ===")
    
    # Get all blog posts
    all_posts = ShopifyBlogPost.objects.all()
    print(f"Total posts in DB: {all_posts.count()}")
    
    # Check status distribution
    published = all_posts.filter(status='published')
    draft = all_posts.filter(status='draft')
    hidden = all_posts.filter(status='hidden')
    
    print(f"Published posts: {published.count()}")
    print(f"Draft posts: {draft.count()}")
    print(f"Hidden posts: {hidden.count()}")
    
    # Test the exact filter from ShopifyBlogPostListView
    print("\n=== TESTING DEFAULT FILTER (only published) ===")
    queryset = ShopifyBlogPost.objects.all()
    
    # This is the filter applied by default in ShopifyBlogPostListView
    # when no status parameter is provided
    queryset = queryset.filter(status='published')
    print(f"Posts after default filter (status='published'): {queryset.count()}")
    
    # Test pagination
    print(f"\nWith paginate_by=50:")
    print(f"  Number of pages: {queryset.count() // 50 + (1 if queryset.count() % 50 else 0)}")
    print(f"  Posts on page 1: {min(50, queryset.count())}")
    print(f"  Posts on page 5: {min(50, max(0, queryset.count() - 4*50))}")
    
    # Check if there's a difference between 250 and actual count
    if queryset.count() > 250:
        print(f"\n⚠️  POTENTIAL ISSUE: {queryset.count() - 250} posts are not visible in frontend due to pagination!")
    
    print("\n=== TESTING WITHOUT STATUS FILTER (show all) ===")
    all_queryset = ShopifyBlogPost.objects.all()
    print(f"All posts (no status filter): {all_queryset.count()}")
    
    # Check if there are users with specific data
    print("\n=== USER-SPECIFIC DATA ===")
    users = ShopifyStore.objects.values_list('user_id', flat=True).distinct()
    for user_id in users:
        user_posts = ShopifyBlogPost.objects.filter(blog__store__user_id=user_id)
        user_published = user_posts.filter(status='published')
        print(f"User {user_id}: {user_posts.count()} total, {user_published.count()} published")
        
if __name__ == "__main__":
    debug_blog_post_filtering()