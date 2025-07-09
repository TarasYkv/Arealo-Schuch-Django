from django.urls import path
from . import views

app_name = 'shopify_manager'

urlpatterns = [
    # Hauptseiten
    path('', views.index_view, name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Store Management
    path('stores/', views.ShopifyStoreListView.as_view(), name='store_list'),
    path('stores/add/', views.ShopifyStoreCreateView.as_view(), name='store_add'),
    path('stores/<int:pk>/edit/', views.ShopifyStoreUpdateView.as_view(), name='store_edit'),
    path('stores/<int:store_id>/test/', views.test_store_connection_view, name='test_store_connection'),
    path('stores/<int:store_id>/delete/', views.delete_store_view, name='store_delete'),
    
    # Product Management
    path('products/', views.ShopifyProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', views.ShopifyProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ShopifyProductEditView.as_view(), name='product_edit'),
    
    # API Endpoints
    path('api/test-connection/', views.test_connection_api_view, name='test_connection_api'),
    path('api/import/', views.import_products_view, name='import_products'),
    path('api/products/<int:product_id>/sync/', views.sync_product_view, name='sync_product'),
    path('api/products/<int:product_id>/delete-local/', views.delete_product_local_view, name='delete_product_local'),
    path('api/products/<int:product_id>/debug/', views.debug_product_data_view, name='debug_product_data'),
    path('api/products/<int:product_id>/update-seo/', views.update_seo_data_view, name='update_seo_data'),
    path('api/products/<int:product_id>/webrex-search/', views.webrex_search_view, name='webrex_search'),
    path('api/bulk-seo-analysis/', views.bulk_seo_analysis_view, name='bulk_seo_analysis'),
    path('seo-dashboard/', views.seo_dashboard_view, name='seo_dashboard'),
    
    # Unified SEO Optimization
    path('seo-optimization/', views.unified_seo_optimization_view, name='unified_seo_optimization'),
    
    # Integrated SEO Optimization (neue Ein-Seiten-Lösung)
    path('do-seo/<str:content_type>/<int:content_id>/', views.integrated_seo_optimization_view, name='integrated_seo_optimization'),
    path('api/generate-integrated-seo/', views.generate_integrated_seo_view, name='generate_integrated_seo'),
    path('api/apply-integrated-seo/', views.apply_integrated_seo_view, name='apply_integrated_seo'),
    
    # Separate SEO Optimization (spezifische Templates)
    path('products/<int:product_id>/do-seo/', views.product_seo_optimization_view, name='product_seo_optimization'),
    path('blog-posts/<int:blog_post_id>/do-seo/', views.blog_post_seo_optimization_view, name='blog_post_seo_optimization'),
    
    # Alt-Text Manager
    path('alt-text-manager/', views.alt_text_manager_overview_view, name='alt_text_manager'),
    path('products/<int:product_id>/alt-text/', views.alt_text_manager_view, name='product_alt_text_manager'),
    path('api/alt-text-data/<int:store_id>/', views.get_alt_text_data_view, name='get_alt_text_data'),
    path('api/update-alt-text/', views.update_alt_text_view, name='update_alt_text'),
    path('api/generate-alt-text/', views.generate_alt_text_view, name='generate_alt_text'),
    
    # SEO-Optimierung mit KI (unterstützt sowohl lokale ID als auch Shopify-ID)
    path('products/<int:product_id>/seo-optimization/', views.seo_optimization_view, name='seo_optimization'),
    path('seo-optimization/<int:pk>/', views.seo_optimization_detail_view, name='seo_optimization_detail'),
    path('api/seo-optimization/<int:pk>/generate/', views.generate_seo_ai_view, name='generate_seo_ai'),
    path('api/seo-optimization/<int:pk>/apply/', views.apply_seo_optimization_view, name='apply_seo_optimization'),
    
    path('api/bulk-action/', views.bulk_action_view, name='bulk_action'),
    
    # Blog Management
    path('blogs/', views.ShopifyBlogListView.as_view(), name='blog_list'),
    path('blogs/<int:pk>/', views.ShopifyBlogDetailView.as_view(), name='blog_detail'),
    path('blog-posts/', views.ShopifyBlogPostListView.as_view(), name='blog_post_list'),
    path('blog-posts/<int:pk>/', views.ShopifyBlogPostDetailView.as_view(), name='blog_post_detail'),
    
    # Blog API Endpoints
    path('api/import-blogs/', views.import_blogs_view, name='import_blogs'),
    path('api/import-blog-posts/', views.import_blog_posts_view, name='import_blog_posts'),
    path('api/import-blog-posts-progress/<str:import_id>/', views.import_blog_posts_progress_view, name='import_blog_posts_progress'),
    path('api/import-all-blog-posts/', views.import_all_blog_posts_view, name='import_all_blog_posts'),
    path('api/get-blogs-for-store/<int:store_id>/', views.get_blogs_for_store_view, name='get_blogs_for_store'),
    path('api/update-blog-alt-text/', views.update_blog_alt_text_view, name='update_blog_alt_text'),
    
    # Blog SEO-Optimierung mit KI
    path('blog-posts/<int:blog_post_id>/seo-optimization/', views.blog_post_seo_optimization_view, name='blog_post_seo_optimization'),
    path('blog-post-seo-optimization/<int:pk>/', views.blog_post_seo_optimization_detail_view, name='blog_post_seo_optimization_detail'),
    path('api/blog-post-seo-optimization/<int:pk>/generate/', views.generate_blog_post_seo_ai_view, name='generate_blog_post_seo_ai'),
    path('api/blog-post-seo-optimization/<int:pk>/apply/', views.apply_blog_post_seo_optimization_view, name='apply_blog_post_seo_optimization'),
    
    # Blog-Post Management APIs  
    path('api/blog-posts/<int:blog_post_id>/delete-local/', views.delete_blog_post_local_view, name='delete_blog_post_local'),
    path('api/blog-posts/<int:blog_post_id>/sync/', views.sync_blog_post_view, name='sync_blog_post'),
    
    # Blog-Post Alt-Text Manager
    path('blog-posts/<int:blog_post_id>/alt-text/', views.blog_post_alt_text_manager_view, name='blog_post_alt_text_manager'),
]