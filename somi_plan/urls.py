from django.urls import path
from . import views

app_name = 'somi_plan'

urlpatterns = [
    # Dashboard und Übersicht
    path('', views.dashboard, name='dashboard'),
    path('plans/', views.plan_list, name='plan_list'),
    
    # 3-Stufen-Assistent
    path('create/', views.create_plan_step1, name='create_plan_step1'),
    path('create/step2/<int:plan_id>/', views.create_plan_step2, name='create_plan_step2'),
    path('create/step3/<int:plan_id>/', views.create_plan_step3, name='create_plan_step3'),
    
    # Plan Management
    path('plan/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plan/<int:pk>/edit/', views.plan_edit, name='plan_edit'),
    path('plan/<int:pk>/delete/', views.plan_delete, name='plan_delete'),
    
    # Post Content Management
    path('plan/<int:plan_id>/post/create/', views.post_create, name='post_create'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/edit/', views.post_edit, name='post_edit'),
    path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),
    
    # Kalender-Funktionen
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/<int:year>/<int:month>/', views.calendar_month, name='calendar_month'),
    path('post/<int:post_id>/schedule/', views.schedule_post, name='schedule_post'),
    path('schedule/<int:pk>/complete/', views.mark_completed, name='mark_completed'),
    
    # KI-Features
    path('plan/<int:plan_id>/generate-more/', views.generate_more_ideas, name='generate_more_ideas'),
    path('plan/<int:plan_id>/regenerate-strategy/', views.regenerate_strategy, name='regenerate_strategy'),
    
    # AJAX Endpoints
    path('ajax/post/<int:pk>/toggle-schedule/', views.ajax_toggle_schedule, name='ajax_toggle_schedule'),
    path('ajax/plan/<int:plan_id>/save-session/', views.ajax_save_session, name='ajax_save_session'),
    path('ajax/post/<int:pk>/update-position/', views.ajax_update_position, name='ajax_update_position'),
    path('ajax/calendar-data/<int:year>/<int:month>/', views.ajax_calendar_data, name='ajax_calendar_data'),
    
    # Template System
    path('templates/', views.template_list, name='template_list'),
    path('templates/category/<int:category_id>/', views.template_category, name='template_category'),
]