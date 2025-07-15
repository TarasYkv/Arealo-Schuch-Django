from django.urls import path
from . import views
from . import sales_views
from . import collection_views

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
    
    
    # Separate SEO Optimization (spezifische Templates)
    path('products/<int:product_id>/do-seo/', views.product_seo_optimization_view, name='product_seo_optimization'),
    path('blog-posts/<int:blog_post_id>/do-seo/', views.blog_post_seo_optimization_view, name='blog_post_seo_optimization'),
    
    # SEO Optimization API
    path('api/generate-seo/', views.generate_seo_view, name='generate_seo'),
    path('api/apply-seo/', views.apply_seo_view, name='apply_seo'),
    
    # Alt-Text Manager
    path('alt-text-manager/', views.alt_text_manager_overview_view, name='alt_text_manager'),
    path('products/<int:product_id>/alt-text/', views.alt_text_manager_view, name='product_alt_text_manager'),
    path('api/alt-text-data/<int:store_id>/', views.get_alt_text_data_view, name='get_alt_text_data'),
    path('api/update-alt-text/', views.update_alt_text_view, name='update_alt_text'),
    path('api/generate-alt-text/', views.generate_alt_text_view, name='generate_alt_text'),
    
    
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
    
    
    # Blog-Post Management APIs  
    path('api/blog-posts/<int:blog_post_id>/delete-local/', views.delete_blog_post_local_view, name='delete_blog_post_local'),
    path('api/blog-posts/<int:blog_post_id>/sync/', views.sync_blog_post_view, name='sync_blog_post'),
    
    # Blog-Post Alt-Text Manager
    path('blog-posts/<int:blog_post_id>/alt-text/', views.blog_post_alt_text_manager_view, name='blog_post_alt_text_manager'),
    
    # Collection Management
    path('collections/', collection_views.ShopifyCollectionListView.as_view(), name='collection_list'),
    path('collections/<int:pk>/', collection_views.ShopifyCollectionDetailView.as_view(), name='collection_detail'),
    path('collections/<int:pk>/edit/', collection_views.ShopifyCollectionUpdateView.as_view(), name='collection_edit'),
    
    # Collection SEO Optimization
    path('collections/<int:collection_id>/do-seo/', collection_views.collection_seo_optimization_view, name='collection_seo_optimization'),
    path('collections/<int:collection_id>/seo-optimization/', collection_views.collection_seo_ajax_view, name='collection_seo_ajax'),
    path('api/collections/seo-optimization/<int:optimization_id>/apply/', collection_views.apply_collection_seo_optimization_view, name='apply_collection_seo_optimization'),
    
    # Collection Alt-Text Manager
    path('collections/<int:collection_id>/alt-text/', collection_views.collection_alt_text_manager_view, name='collection_alt_text_manager'),
    
    # Collection API Endpoints
    path('api/collections/import/', collection_views.collection_import_view, name='collection_import'),
    path('api/collections/<int:collection_id>/alt-text/', collection_views.update_collection_alt_text_view, name='update_collection_alt_text'),
    path('api/collections/<int:collection_id>/alt-text-suggestion/', collection_views.generate_collection_alt_text_view, name='generate_collection_alt_text'),
    
    # Sales Statistics
    path('sales/', sales_views.sales_dashboard_view, name='sales_dashboard'),
    path('sales/import/', sales_views.import_sales_data_view, name='import_sales_data'),
    path('sales/data/', sales_views.sales_data_list_view, name='sales_data_list'),
    path('sales/cost-breakdown/', sales_views.cost_breakdown_view, name='cost_breakdown'),
    
    # Shipping Profiles
    path('shipping-profiles/', sales_views.ShippingProfileListView.as_view(), name='shipping_profiles'),
    path('shipping-profiles/add/', sales_views.ShippingProfileCreateView.as_view(), name='shipping_profile_add'),
    path('shipping-profiles/<int:pk>/edit/', sales_views.ShippingProfileUpdateView.as_view(), name='shipping_profile_edit'),
    path('shipping-profiles/<int:pk>/delete/', sales_views.ShippingProfileDeleteView.as_view(), name='shipping_profile_delete'),
    path('shipping-profiles/assign/', sales_views.assign_shipping_profile_view, name='assign_shipping_profile'),
    
    # Recurring Costs
    path('recurring-costs/', sales_views.RecurringCostListView.as_view(), name='recurring_costs'),
    path('recurring-costs/add/', sales_views.RecurringCostCreateView.as_view(), name='recurring_cost_add'),
    path('recurring-costs/<int:pk>/edit/', sales_views.RecurringCostUpdateView.as_view(), name='recurring_cost_edit'),
    path('recurring-costs/<int:pk>/delete/', sales_views.RecurringCostDeleteView.as_view(), name='recurring_cost_delete'),
    
    # Ads Costs
    path('ads-costs/', sales_views.AdsCostListView.as_view(), name='ads_costs'),
    path('ads-costs/add/', sales_views.AdsCostCreateView.as_view(), name='ads_cost_add'),
    path('ads-costs/<int:pk>/edit/', sales_views.AdsCostUpdateView.as_view(), name='ads_cost_edit'),
    path('ads-costs/<int:pk>/delete/', sales_views.AdsCostDeleteView.as_view(), name='ads_cost_delete'),
    
    # Product Cost Management
    path('product-costs/', sales_views.product_cost_management_view, name='product_cost_management'),
    path('api/update-product-cost/', sales_views.update_product_cost_view, name='update_product_cost'),
    
    # PayPal Analysis
    path('sales/paypal-analysis/', sales_views.paypal_fees_analysis_view, name='paypal_fees_analysis'),
    
    # Orders Table
    path('sales/orders/', sales_views.orders_table_view, name='orders_table'),
    
    # Google Ads Integration
    path('google-ads/config/', sales_views.google_ads_config_view, name='google_ads_config'),
    path('google-ads/<int:store_id>/sync/', sales_views.google_ads_sync_view, name='google_ads_sync'),
]