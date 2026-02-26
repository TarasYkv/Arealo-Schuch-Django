from django.urls import path
from . import views

app_name = 'learnloom'

urlpatterns = [
    # Page Routes
    path('', views.index, name='index'),
    path('view/<uuid:book_id>/', views.pdf_viewer, name='pdf_viewer'),
    path('notes/<uuid:book_id>/', views.notes_view, name='notes'),
    path('summary/<uuid:book_id>/', views.summary_view, name='summary'),
    path('vocabulary/<uuid:book_id>/', views.vocabulary_list, name='vocabulary'),
    path('all-vocabulary/', views.all_vocabulary, name='all_vocabulary'),
    path('all-notes/', views.all_notes, name='all_notes'),

    # PDF API
    path('api/extract-title/', views.api_extract_title, name='api_extract_title'),
    path('api/add-online/', views.api_add_online_article, name='api_add_online'),
    path('api/upload/', views.api_upload_pdf, name='api_upload'),
    path('api/pdf/<uuid:book_id>/', views.api_serve_pdf, name='api_serve_pdf'),
    path('api/pdf/<uuid:book_id>/delete/', views.api_delete_pdf, name='api_delete'),
    path('api/pdf/<uuid:book_id>/metadata/', views.api_update_metadata, name='api_metadata'),
    path('api/pdf/<uuid:book_id>/reading-status/', views.api_update_reading_status, name='api_reading_status'),

    # Notes API
    path('api/notes/<uuid:book_id>/', views.api_get_notes, name='api_get_notes'),
    path('api/notes/<uuid:book_id>/save/', views.api_save_note, name='api_save_note'),
    path('api/notes/<uuid:note_id>/delete/', views.api_delete_note, name='api_delete_note'),

    # Translation API
    path('api/translate/', views.api_translate, name='api_translate'),
    path('api/translate-detailed/', views.api_translate_detailed, name='api_translate_detailed'),
    path('api/highlights/<uuid:book_id>/', views.api_get_highlights, name='api_get_highlights'),
    path('api/highlights/<uuid:book_id>/save/', views.api_save_highlight, name='api_save_highlight'),

    # Explanation API
    path('api/explain/', views.api_explain, name='api_explain'),
    path('api/explain-image/', views.api_explain_image, name='api_explain_image'),
    path('api/followup/', views.api_followup, name='api_followup'),
    path('api/explanations/<uuid:book_id>/', views.api_get_explanations, name='api_get_explanations'),
    path('api/explanations/<uuid:book_id>/save/', views.api_save_explanation, name='api_save_explanation'),
    path('api/explanations/<uuid:explanation_id>/delete/', views.api_delete_explanation, name='api_delete_explanation'),

    # Summary API
    path('api/summary/<uuid:book_id>/', views.api_get_summary, name='api_get_summary'),
    path('api/summary/<uuid:book_id>/generate/', views.api_generate_summary, name='api_generate_summary'),
    path('api/summary/<uuid:book_id>/delete/', views.api_delete_summary, name='api_delete_summary'),
    path('api/summary/<uuid:book_id>/section/', views.api_summarize_section, name='api_summarize_section'),

    # Audio Summary API
    path('api/audio/<uuid:book_id>/generate/', views.api_generate_audio, name='api_generate_audio'),
    path('api/audio/<uuid:book_id>/status/', views.api_get_audio_status, name='api_get_audio_status'),

    # PDF Chat API
    path('api/pdf/<uuid:book_id>/chat/', views.api_pdf_chat, name='api_pdf_chat'),

    # Vocabulary API
    path('api/vocabulary/<uuid:book_id>/', views.api_get_vocabulary, name='api_get_vocabulary'),
    path('api/vocabulary/<uuid:book_id>/add/', views.api_add_vocabulary, name='api_add_vocabulary'),
    path('api/vocabulary/<uuid:vocab_id>/delete/', views.api_delete_vocabulary, name='api_delete_vocabulary'),
    path('api/vocabulary/<uuid:book_id>/pdf/', views.api_vocabulary_pdf, name='api_vocabulary_pdf'),
    path('api/vocabulary/all/pdf/', views.api_all_vocabulary_pdf, name='api_all_vocabulary_pdf'),

    # Progress API
    path('api/progress/<uuid:book_id>/', views.api_get_progress, name='api_get_progress'),
    path('api/progress/<uuid:book_id>/save/', views.api_save_progress, name='api_save_progress'),

    # Reading List API
    path('api/reading-list/', views.api_get_reading_list, name='api_reading_list'),
    path('api/reading-list/add/', views.api_add_reading_list_item, name='api_add_reading_list'),
    path('api/reading-list/<uuid:item_id>/update/', views.api_update_reading_list_item, name='api_update_reading_list'),
    path('api/reading-list/<uuid:item_id>/delete/', views.api_delete_reading_list_item, name='api_delete_reading_list'),
]
