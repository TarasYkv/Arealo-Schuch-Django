from django.urls import path
from . import views

app_name = 'loomconnect'

urlpatterns = [
    # Main Pages
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('feed/', views.FeedView.as_view(), name='feed'),
    path('discover/', views.DiscoverView.as_view(), name='discover'),

    # Onboarding
    path('onboarding/', views.OnboardingWelcomeView.as_view(), name='onboarding_welcome'),
    path('onboarding/skills/', views.OnboardingSkillsView.as_view(), name='onboarding_skills'),
    path('onboarding/level/', views.OnboardingLevelView.as_view(), name='onboarding_level'),
    path('onboarding/needs/', views.OnboardingNeedsView.as_view(), name='onboarding_needs'),
    path('onboarding/availability/', views.OnboardingAvailabilityView.as_view(), name='onboarding_availability'),
    path('onboarding/profile/', views.OnboardingProfileView.as_view(), name='onboarding_profile'),
    path('onboarding/complete/', views.OnboardingCompleteView.as_view(), name='onboarding_complete'),

    # Profile
    path('profile/', views.MyProfileView.as_view(), name='my_profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/<str:username>/', views.ProfileDetailView.as_view(), name='profile'),

    # Skills Management
    path('skills/', views.SkillManagementView.as_view(), name='skills_management'),
    path('skills/add/', views.AddSkillView.as_view(), name='add_skill'),
    path('skills/<int:pk>/edit/', views.EditSkillView.as_view(), name='edit_skill'),
    path('skills/<int:pk>/delete/', views.DeleteSkillView.as_view(), name='delete_skill'),

    # Needs Management
    path('needs/', views.NeedManagementView.as_view(), name='needs_management'),
    path('needs/add/', views.AddNeedView.as_view(), name='add_need'),
    path('needs/<int:pk>/edit/', views.EditNeedView.as_view(), name='edit_need'),
    path('needs/<int:pk>/delete/', views.DeleteNeedView.as_view(), name='delete_need'),

    # Posts
    path('posts/create/', views.PostCreateView.as_view(), name='post_create'),
    path('posts/<uuid:pk>/', views.PostDetailView.as_view(), name='post_detail'),
    path('posts/<uuid:pk>/edit/', views.PostEditView.as_view(), name='post_edit'),
    path('posts/<uuid:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete'),

    # Post Interactions (AJAX)
    path('posts/<uuid:pk>/like/', views.PostLikeView.as_view(), name='post_like'),
    path('posts/<uuid:pk>/comment/', views.PostCommentView.as_view(), name='post_comment'),
    path('posts/<uuid:pk>/share/', views.PostShareView.as_view(), name='post_share'),

    # Connect Requests
    path('requests/', views.RequestInboxView.as_view(), name='request_inbox'),
    path('requests/send/<str:username>/', views.SendRequestView.as_view(), name='send_request'),
    path('requests/<uuid:pk>/accept/', views.AcceptRequestView.as_view(), name='accept_request'),
    path('requests/<uuid:pk>/decline/', views.DeclineRequestView.as_view(), name='decline_request'),

    # Connections
    path('connections/', views.ConnectionsView.as_view(), name='connections'),
    path('connections/<int:pk>/cancel/', views.CancelConnectionView.as_view(), name='cancel_connection'),

    # Stories
    path('stories/', views.StoriesView.as_view(), name='stories'),
    path('stories/create/', views.StoryCreateView.as_view(), name='story_create'),
    path('stories/<uuid:pk>/', views.StoryDetailView.as_view(), name='story_detail'),

    # Search
    path('search/', views.SearchView.as_view(), name='search'),

    # Info Page (Public)
    path('info/', views.InfoPageView.as_view(), name='info'),

    # Admin/Statistics (Superuser only)
    path('statistics/', views.StatisticsView.as_view(), name='statistics'),

    # API Endpoints (for AJAX)
    path('api/matches/', views.GetMatchesAPIView.as_view(), name='api_matches'),
    path('api/skills/search/', views.SkillSearchAPIView.as_view(), name='api_skill_search'),
]
