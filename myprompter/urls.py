from django.urls import path
from . import views

app_name = 'myprompter'

urlpatterns = [
    # Main teleprompter view
    path('', views.teleprompter_view, name='teleprompter'),

    # Saved texts management
    path('saved/', views.saved_texts_view, name='saved_texts'),

    # API endpoints
    path('api/save/', views.save_text, name='save_text'),
    path('api/update/<int:text_id>/', views.update_text, name='update_text'),
    path('api/delete/<int:text_id>/', views.delete_text, name='delete_text'),
    path('api/favorite/<int:text_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('api/get/<int:text_id>/', views.get_text, name='get_text'),
]
