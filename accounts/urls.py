from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Kategorie-Management
    path('kategorien/', views.category_list, name='category_list'),
    path('kategorien/neu/', views.category_create, name='category_create'),
    path('kategorien/<int:pk>/', views.category_detail, name='category_detail'),
    path('kategorien/<int:pk>/bearbeiten/', views.category_edit, name='category_edit'),
    path('kategorien/<int:pk>/loeschen/', views.category_delete, name='category_delete'),
    
    # Suchbegriff-Management
    path('kategorien/<int:category_pk>/begriffe/neu/', views.keyword_add, name='keyword_add'),
    path('kategorien/<int:category_pk>/begriffe/bulk/', views.keyword_bulk_add, name='keyword_bulk_add'),
    path('begriffe/<int:keyword_pk>/loeschen/', views.keyword_delete, name='keyword_delete'),
]