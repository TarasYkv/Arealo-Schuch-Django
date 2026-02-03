from django.urls import path
from . import views

app_name = 'loomtalk'

urlpatterns = [
    # Oeffentlich (Lesen)
    path('', views.ForumHomeView.as_view(), name='home'),
    path('themen/', views.TopicListView.as_view(), name='topic_list'),
    path('kategorie/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('thema/<uuid:pk>/', views.TopicDetailView.as_view(), name='topic_detail'),
    path('tag/<slug:slug>/', views.TagTopicsView.as_view(), name='tag_topics'),
    path('suche/', views.SearchView.as_view(), name='search'),

    # Eingeloggt (Schreiben)
    path('thema/erstellen/', views.TopicCreateView.as_view(), name='topic_create'),
    path('thema/<uuid:pk>/bearbeiten/', views.TopicEditView.as_view(), name='topic_edit'),
    path('thema/<uuid:pk>/antworten/', views.ReplyCreateView.as_view(), name='reply_create'),
    path('erwaehnungen/', views.MentionsView.as_view(), name='mentions'),

    # AJAX/API
    path('vote/<str:content_type>/<uuid:pk>/', views.VoteView.as_view(), name='vote'),
    path('mention/<int:pk>/gelesen/', views.MarkMentionReadView.as_view(), name='mark_mention_read'),
    path('api/tags/search/', views.TagSearchView.as_view(), name='tag_search'),
    path('api/users/search/', views.UserSearchView.as_view(), name='user_search'),
]
