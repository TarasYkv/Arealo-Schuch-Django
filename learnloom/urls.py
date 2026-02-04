from django.urls import path
from . import views

app_name = 'learnloom'

urlpatterns = [
    # Page Routes
    path('', views.index, name='index'),
    path('view/<uuid:book_id>/', views.pdf_viewer, name='pdf_viewer'),
    path('notes/<uuid:book_id>/', views.notes_view, name='notes'),
    path('vocabulary/<uuid:book_id>/', views.vocabulary_list, name='vocabulary'),

    # PDF API
    path('api/upload/', views.api_upload_pdf, name='api_upload'),
    path('api/pdf/<uuid:book_id>/', views.api_serve_pdf, name='api_serve_pdf'),
    path('api/pdf/<uuid:book_id>/delete/', views.api_delete_pdf, name='api_delete'),
    path('api/pdf/<uuid:book_id>/metadata/', views.api_update_metadata, name='api_metadata'),

    # Notes API
    path('api/notes/<uuid:book_id>/', views.api_get_notes, name='api_get_notes'),
    path('api/notes/<uuid:book_id>/save/', views.api_save_note, name='api_save_note'),
    path('api/notes/<uuid:note_id>/delete/', views.api_delete_note, name='api_delete_note'),

    # Translation API
    path('api/translate/', views.api_translate, name='api_translate'),
    path('api/highlights/<uuid:book_id>/', views.api_get_highlights, name='api_get_highlights'),
    path('api/highlights/<uuid:book_id>/save/', views.api_save_highlight, name='api_save_highlight'),

    # Vocabulary API
    path('api/vocabulary/<uuid:book_id>/', views.api_get_vocabulary, name='api_get_vocabulary'),
    path('api/vocabulary/<uuid:book_id>/add/', views.api_add_vocabulary, name='api_add_vocabulary'),
    path('api/vocabulary/<uuid:vocab_id>/delete/', views.api_delete_vocabulary, name='api_delete_vocabulary'),

    # Progress API
    path('api/progress/<uuid:book_id>/', views.api_get_progress, name='api_get_progress'),
    path('api/progress/<uuid:book_id>/save/', views.api_save_progress, name='api_save_progress'),
]
