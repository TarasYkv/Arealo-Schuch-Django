from django.urls import path

from . import views

app_name = 'radio'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('onair/toggle/', views.toggle_onair, name='toggle_onair'),
    path('stream/power/', views.stream_power, name='stream_power'),
    path('live/duck/', views.live_duck, name='live_duck'),
    path('background/', views.set_background, name='set_background'),
    path('schedule/build/', views.build_schedule, name='build_schedule'),
    path('schedule/fragment/', views.schedule_fragment, name='schedule_fragment'),
    path('app/state/', views.app_state, name='app_state'),
    path('app/about/', views.app_about, name='app_about'),
    path('app/privacy/', views.app_privacy, name='app_privacy'),
    path('app/manifest.json', views.app_manifest, name='app_manifest'),
    path('sw.js', views.radio_sw, name='radio_sw'),
    path('promo/save/', views.promo_save, name='promo_save'),
    path('presence/', views.presence_state, name='presence_state'),
    path('stats/history/', views.listener_history, name='listener_history'),
    path('schedule/<int:pk>/move/', views.entry_move, name='entry_move'),
    path('schedule/<int:pk>/remove/', views.entry_remove, name='entry_remove'),

    # KI-Assistent
    path('assistant/', views.assistant_chat, name='assistant_chat'),
    path('assistant/status/<str:task_id>/', views.assistant_status, name='assistant_status'),

    # Einstellungen
    path('settings/', views.settings_view, name='settings'),
    path('settings/save/', views.save_settings, name='save_settings'),
    path('news/', views.news_settings, name='news_settings'),
    path('news/save/', views.news_settings_save, name='news_settings_save'),
    path('settings/clone-voice/', views.upload_clone_voice, name='upload_clone_voice'),
    path('settings/rubrik/save/', views.rubrik_save, name='rubrik_save'),
    path('settings/rubrik/<int:pk>/delete/', views.rubrik_delete, name='rubrik_delete'),

    # Compose-Studio
    path('compose/', views.compose, name='compose'),
    path('compose/assist/', views.glm_assist, name='glm_assist'),
    path('compose/pexels/', views.pexels_search, name='pexels_search'),
    path('compose/generate/', views.compose_generate, name='compose_generate'),
    path('compose/status/<str:task_id>/', views.compose_status, name='compose_status'),
    path('compose/accept/', views.compose_accept, name='compose_accept'),
    path('compose/move/', views.compose_move, name='compose_move'),
    path('compose/tts-test/', views.tts_test, name='tts_test'),
    path('compose/eleven-balance/', views.eleven_balance, name='eleven_balance'),
    path('visualizer/', views.visualizer, name='visualizer'),
    path('visualizer/save/', views.visualizer_save, name='visualizer_save'),
    path('visualizer/preview/', views.visualizer_preview, name='visualizer_preview'),
    path('visualizer/activate/', views.visualizer_activate, name='visualizer_activate'),
    path('compose/tts-settings/', views.tts_settings, name='tts_settings'),

    # Bibliothek
    path('library/', views.library_list, name='library_list'),
    path('library/manage/', views.library_manage, name='library_manage'),
    path('library/edit/', views.library_edit, name='library_edit'),
    path('library/add/', views.library_add, name='library_add'),
    path('library/delete/', views.library_delete, name='library_delete'),
    path('library/upload/', views.library_upload, name='library_upload'),
    path('library/toggle-auto/', views.library_toggle_auto, name='library_toggle_auto'),
    path('library/tags/', views.content_tags, name='content_tags'),
    path('tags/', views.tags_list, name='tags_list'),
    path('tags/overview/', views.tags_overview, name='tags_overview'),
    path('tags/save/', views.tag_save, name='tag_save'),
    path('tags/delete/', views.tag_delete, name='tag_delete'),
    path('timeline/', views.timeline, name='timeline'),
    path('timeline/data/', views.timeline_data, name='timeline_data'),
    path('timeline/weekprogram/', views.weekprogram_data, name='weekprogram_data'),
    path('timeline/pin/save/', views.pin_save, name='pin_save'),
    path('timeline/pin/delete/', views.pin_delete, name='pin_delete'),
    path('timeline/picker/', views.content_picker, name='content_picker'),
    path('timeline/materialize/', views.materialize_now, name='materialize_now'),
    path('timeline/replan/', views.replan_now, name='replan_now'),
    path('live/', views.live_page, name='live_page'),
    path('live-state/', views.live_state, name='live_state'),
    path('stats/', views.radio_stats, name='radio_stats'),
    path('alexa/', views.alexa_skill, name='alexa_skill'),
    path('music/', views.music_search, name='music_search'),
    path('music/search/', views.openverse_search, name='openverse_search'),
    path('music/import/', views.openverse_import, name='openverse_import'),
    path('program/auto/', views.auto_program_now, name='auto_program_now'),
    path('news/drafts/', views.news_drafts, name='news_drafts'),
    path('news/fetch/', views.fetch_news_now, name='fetch_news_now'),
    # Content-Wizard (Batch-Erstellung)
    path('wizard/', views.wizard, name='wizard'),
    # Tages-/Slot-Planer
    path('planner/', views.planner, name='planner'),
    path('planner/slot/save/', views.slot_save, name='slot_save'),
    path('planner/slot/delete/', views.slot_delete, name='slot_delete'),
    path('planner/slot/fill/', views.slot_fill, name='slot_fill'),
    path('planner/day/', views.plan_day_now, name='plan_day_now'),

    path('notes/', views.notes_page, name='notes_page'),
    path('notes/list/', views.notes_list, name='notes_list'),
    path('notes/save/', views.note_save, name='note_save'),
    path('notes/delete/', views.note_delete, name='note_delete'),

    # Liquidsoap-Schnittstellen (token-geschützt)
    path('next/', views.next_track, name='next_track'),
    path('playing/', views.now_playing, name='now_playing'),
]
