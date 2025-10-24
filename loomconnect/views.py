from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, Prefetch, Exists, OuterRef
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from .models import (
    ConnectProfile, Skill, SkillCategory, UserSkill, UserNeed,
    ConnectPost, PostComment, PostLike, ConnectRequest, Connection,
    ConnectStory, ProfileView, StoryView
)
from .forms import (
    OnboardingSkillsForm, OnboardingLevelForm, OnboardingNeedsForm,
    OnboardingProfileForm, ProfileEditForm, AddSkillForm, EditSkillForm,
    AddNeedForm, EditNeedForm, PostCreateForm, PostCommentForm,
    SendConnectRequestForm, StoryCreateForm, SearchForm
)

User = get_user_model()


# ==========================================
# MIXINS & UTILITIES
# ==========================================

class LoomConnectAccessMixin(LoginRequiredMixin):
    """Base Mixin für alle LoomConnect Views - prüft App-Zugriff"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # AppPermission prüfen (inkl. superuser_bypass)
        from accounts.models import AppPermission
        if not AppPermission.user_has_access('loomconnect', request.user):
            messages.error(request, 'Du hast keinen Zugriff auf LoomConnect.')
            return redirect('startseite')

        return super().dispatch(request, *args, **kwargs)


def get_or_create_profile(user):
    """Hilfsfunktion: ConnectProfile erstellen falls nicht vorhanden"""
    profile, created = ConnectProfile.objects.get_or_create(user=user)
    return profile


# ==========================================
# ONBOARDING VIEWS
# ==========================================

class OnboardingWelcomeView(LoomConnectAccessMixin, View):
    """Schritt 0: Willkommen"""
    template_name = 'loomconnect/onboarding/welcome.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)

        # Wenn bereits completed → redirect zu Dashboard
        if profile.onboarding_completed:
            messages.info(request, 'Du hast das Onboarding bereits abgeschlossen!')
            return redirect('loomconnect:dashboard')

        return render(request, self.template_name, {'profile': profile})


class OnboardingSkillsView(LoomConnectAccessMixin, View):
    """Schritt 1: Skills auswählen"""
    template_name = 'loomconnect/onboarding/skills.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)
        form = OnboardingSkillsForm()

        # Kategorien für bessere Übersicht
        categories = SkillCategory.objects.filter(is_active=True).prefetch_related(
            Prefetch('skills', queryset=Skill.objects.filter(is_active=True, is_predefined=True))
        )

        return render(request, self.template_name, {
            'form': form,
            'categories': categories,
            'profile': profile
        })

    def post(self, request):
        profile = get_or_create_profile(request.user)
        form = OnboardingSkillsForm(request.POST)

        if form.is_valid():
            skills = form.cleaned_data['skills']
            custom_skill_name = form.cleaned_data.get('custom_skill_name')
            custom_skill_category = form.cleaned_data.get('custom_skill_category')

            # Skills in Session speichern für nächsten Schritt
            request.session['onboarding_skills'] = [s.id for s in skills]

            # Custom Skill erstellen
            if custom_skill_name and custom_skill_category:
                custom_skill, created = Skill.objects.get_or_create(
                    name=custom_skill_name,
                    category=custom_skill_category,
                    defaults={
                        'is_predefined': False,
                        'created_by': request.user
                    }
                )
                request.session['onboarding_custom_skill'] = custom_skill.id

            return redirect('loomconnect:onboarding_level')

        categories = SkillCategory.objects.filter(is_active=True).prefetch_related('skills')
        return render(request, self.template_name, {
            'form': form,
            'categories': categories,
            'profile': profile
        })


class OnboardingLevelView(LoomConnectAccessMixin, View):
    """Schritt 2: Level für ausgewählte Skills"""
    template_name = 'loomconnect/onboarding/level.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)

        # Skills aus Session holen
        skill_ids = request.session.get('onboarding_skills', [])
        custom_skill_id = request.session.get('onboarding_custom_skill')

        if custom_skill_id:
            skill_ids.append(custom_skill_id)

        if not skill_ids:
            messages.warning(request, 'Bitte wähle zuerst Skills aus.')
            return redirect('loomconnect:onboarding_skills')

        skills = Skill.objects.filter(id__in=skill_ids)
        form = OnboardingLevelForm(skills=skills)

        return render(request, self.template_name, {
            'form': form,
            'skills': skills,
            'profile': profile
        })

    def post(self, request):
        profile = get_or_create_profile(request.user)

        skill_ids = request.session.get('onboarding_skills', [])
        custom_skill_id = request.session.get('onboarding_custom_skill')
        if custom_skill_id:
            skill_ids.append(custom_skill_id)

        skills = Skill.objects.filter(id__in=skill_ids)
        form = OnboardingLevelForm(request.POST, skills=skills)

        if form.is_valid():
            # UserSkills erstellen
            for skill in skills:
                level = form.cleaned_data.get(f'skill_{skill.id}_level')
                years = form.cleaned_data.get(f'skill_{skill.id}_years')
                offering = form.cleaned_data.get(f'skill_{skill.id}_offering', True)

                UserSkill.objects.update_or_create(
                    profile=profile,
                    skill=skill,
                    defaults={
                        'level': level,
                        'years_experience': years or 0,
                        'is_offering': offering
                    }
                )

            return redirect('loomconnect:onboarding_needs')

        return render(request, self.template_name, {
            'form': form,
            'skills': skills,
            'profile': profile
        })


class OnboardingNeedsView(LoomConnectAccessMixin, View):
    """Schritt 3: Was suchst du?"""
    template_name = 'loomconnect/onboarding/needs.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)
        form = OnboardingNeedsForm()

        categories = SkillCategory.objects.filter(is_active=True).prefetch_related(
            Prefetch('skills', queryset=Skill.objects.filter(is_active=True, is_predefined=True))
        )

        return render(request, self.template_name, {
            'form': form,
            'categories': categories,
            'profile': profile
        })

    def post(self, request):
        profile = get_or_create_profile(request.user)
        form = OnboardingNeedsForm(request.POST)

        if form.is_valid():
            needs = form.cleaned_data['needs']

            # UserNeeds erstellen
            for need_skill in needs:
                description = form.cleaned_data.get(f'need_{need_skill.id}_description', '')
                urgency = form.cleaned_data.get(f'need_{need_skill.id}_urgency', 'mittel')

                UserNeed.objects.update_or_create(
                    profile=profile,
                    skill=need_skill,
                    defaults={
                        'description': description,
                        'urgency': urgency
                    }
                )

            return redirect('loomconnect:onboarding_availability')

        categories = SkillCategory.objects.filter(is_active=True).prefetch_related('skills')
        return render(request, self.template_name, {
            'form': form,
            'categories': categories,
            'profile': profile
        })


class OnboardingAvailabilityView(LoomConnectAccessMixin, View):
    """Schritt 4: Verfügbarkeit"""
    template_name = 'loomconnect/onboarding/availability.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)

        return render(request, self.template_name, {'profile': profile})

    def post(self, request):
        profile = get_or_create_profile(request.user)

        # Verfügbarkeit speichern
        availability = request.POST.get('availability', 'flexibel')
        profile.availability = availability
        profile.save()

        return redirect('loomconnect:onboarding_profile')


class OnboardingProfileView(LoomConnectAccessMixin, View):
    """Schritt 5: Profil-Details"""
    template_name = 'loomconnect/onboarding/profile.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)
        form = OnboardingProfileForm(instance=profile)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })

    def post(self, request):
        profile = get_or_create_profile(request.user)
        form = OnboardingProfileForm(request.POST, request.FILES, instance=profile)

        if form.is_valid():
            form.save()
            return redirect('loomconnect:onboarding_complete')

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })


class OnboardingCompleteView(LoomConnectAccessMixin, View):
    """Schritt 6: Abschluss & Glückwunsch"""
    template_name = 'loomconnect/onboarding/complete.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)

        # Onboarding als abgeschlossen markieren
        profile.onboarding_completed = True
        profile.save()

        # Session cleanup
        request.session.pop('onboarding_skills', None)
        request.session.pop('onboarding_custom_skill', None)

        messages.success(request, 'Willkommen bei LoomConnect! 🎉')

        return render(request, self.template_name, {'profile': profile})


# ==========================================
# MAIN VIEWS
# ==========================================

class DashboardView(LoomConnectAccessMixin, View):
    """LoomConnect Dashboard - Aktivitäten & Feed Übersicht"""
    template_name = 'loomconnect/dashboard.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)

        # Wenn Onboarding nicht abgeschlossen → redirect
        if not profile.onboarding_completed:
            return redirect('loomconnect:onboarding_welcome')

        # Connection count für Stats
        my_connections = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).count()

        # Pending requests count
        pending_requests = ConnectRequest.objects.filter(
            to_profile=profile,
            status='pending'
        ).count()

        # Feed Posts von Connections (nicht eigene Posts)
        my_connection_profiles = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).values_list('profile_1_id', 'profile_2_id')

        connection_profile_ids = set()
        for p1, p2 in my_connection_profiles:
            connection_profile_ids.add(p1)
            connection_profile_ids.add(p2)
        connection_profile_ids.discard(profile.id)

        feed_posts = ConnectPost.objects.filter(
            author_id__in=connection_profile_ids
        ).select_related('author', 'author__user').prefetch_related(
            'related_skills', 'comments', 'likes'
        ).order_by('-created_at')[:5]

        # Suggested Matches (Skills die ich biete vs. Needs von anderen)
        my_skill_ids = UserSkill.objects.filter(
            profile=profile,
            is_offering=True
        ).values_list('skill_id', flat=True)

        potential_matches = UserNeed.objects.filter(
            skill_id__in=my_skill_ids,
            is_active=True
        ).exclude(profile=profile).select_related('profile', 'profile__user', 'skill')[:5]

        context = {
            'profile': profile,
            'my_connections': my_connections,
            'pending_requests': pending_requests,
            'feed_posts': feed_posts,
            'potential_matches': potential_matches,
        }

        return render(request, self.template_name, context)


class FeedView(LoomConnectAccessMixin, ListView):
    """Feed mit Posts von Connections"""
    model = ConnectPost
    template_name = 'loomconnect/feed.html'
    context_object_name = 'posts'
    paginate_by = 20

    def get_queryset(self):
        profile = get_or_create_profile(self.request.user)

        if not profile.onboarding_completed:
            return ConnectPost.objects.none()

        # Posts von mir selbst + Posts von meinen Connections
        my_connections = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).values_list('profile_1_id', 'profile_2_id')

        connection_profile_ids = set()
        for p1, p2 in my_connections:
            connection_profile_ids.add(p1)
            connection_profile_ids.add(p2)
        connection_profile_ids.discard(profile.id)

        return ConnectPost.objects.filter(
            Q(author=profile) | Q(author_id__in=connection_profile_ids)
        ).select_related('author', 'author__user').prefetch_related(
            'related_skills', 'comments', 'likes'
        ).annotate(
            user_has_liked=Exists(
                PostLike.objects.filter(
                    post=OuterRef('pk'),
                    user=self.request.user
                )
            )
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = get_or_create_profile(self.request.user)
        context['profile'] = profile

        # Active Stories (letzte 24h)
        context['active_stories'] = ConnectStory.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).select_related('author', 'author__connect_profile').order_by('-created_at')[:10]

        # Suggested Users (Users die nicht verbunden sind)
        connected_profile_ids = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).values_list('profile_1_id', 'profile_2_id')

        all_connected_ids = set()
        for p1, p2 in connected_profile_ids:
            all_connected_ids.add(p1)
            all_connected_ids.add(p2)
        all_connected_ids.discard(profile.id)

        context['suggested_users'] = User.objects.filter(
            connect_profile__onboarding_completed=True,
            connect_profile__is_public=True
        ).exclude(
            id=self.request.user.id
        ).exclude(
            connect_profile__id__in=all_connected_ids
        ).select_related('connect_profile')[:5]

        # Trending Skills (meistgenutzte Skills)
        context['trending_skills'] = Skill.objects.filter(
            is_active=True
        ).annotate(
            usage_count=Count('userskill')
        ).order_by('-usage_count')[:10]

        return context


class DiscoverView(LoomConnectAccessMixin, ListView):
    """Discover - Alle User & Skills durchsuchen"""
    model = User
    template_name = 'loomconnect/discover.html'
    context_object_name = 'users'
    paginate_by = 24

    def get_queryset(self):
        # User mit ConnectProfile vorgeladen
        queryset = User.objects.filter(
            connect_profile__onboarding_completed=True,
            connect_profile__is_public=True
        ).exclude(id=self.request.user.id).select_related('connect_profile').prefetch_related(
            Prefetch('connect_profile__userskill_set', to_attr='user_skills'),
            Prefetch('connect_profile__userneed_set', queryset=UserNeed.objects.filter(is_active=True), to_attr='user_needs')
        ).annotate(
            skills_count=Count('connect_profile__userskill'),
            connections_count=Count('connect_profile__connections_as_profile_1') + Count('connect_profile__connections_as_profile_2')
        )

        # Einfache Sortierung nach Karma und Aktivität
        queryset = queryset.order_by('-connect_profile__karma_score', '-connect_profile__updated_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = get_or_create_profile(self.request.user)
        context['profile'] = profile
        context['categories'] = SkillCategory.objects.filter(is_active=True)
        context['popular_skills'] = Skill.objects.filter(is_active=True).order_by('-usage_count')[:20]

        # Match-System: Berechne Top Matches
        from .services import MatchService
        view_mode = self.request.GET.get('mode', 'all')
        if view_mode == 'matches':
            # Zeige nur Matches an
            matches = MatchService.find_matches_for_profile(profile, limit=50, min_score=30)
            context['matches'] = matches
            context['view_mode'] = 'matches'
        else:
            # Standard: Alle Profile mit Score-Berechnung für Top 3
            top_matches = MatchService.find_matches_for_profile(profile, limit=3, min_score=50)
            context['top_matches'] = top_matches
            context['view_mode'] = 'all'

        return context


# ==========================================
# PROFILE VIEWS
# ==========================================

class MyProfileView(LoomConnectAccessMixin, View):
    """Eigenes Profil anzeigen"""
    template_name = 'loomconnect/profile/my_profile.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)

        user_skills = UserSkill.objects.filter(profile=profile).select_related('skill', 'skill__category')
        user_needs = UserNeed.objects.filter(profile=profile, is_active=True).select_related('skill')
        user_posts = ConnectPost.objects.filter(author=profile).order_by('-created_at')[:5]

        connections_count = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).count()

        skills_count = user_skills.count()

        # Profile views count
        profile_views = ProfileView.objects.filter(viewed_profile=profile).count()

        # Check if user is online (using model method)
        is_online = profile.is_online()

        return render(request, self.template_name, {
            'profile': profile,
            'user_skills': user_skills,
            'user_needs': user_needs,
            'user_posts': user_posts,
            'connections_count': connections_count,
            'skills_count': skills_count,
            'profile_views': profile_views,
            'is_online': is_online,
        })


class ProfileDetailView(LoomConnectAccessMixin, DetailView):
    """Profil eines anderen Users anzeigen"""
    model = ConnectProfile
    template_name = 'loomconnect/profile/profile_detail.html'
    context_object_name = 'viewed_profile'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'

    def get_object(self, queryset=None):
        username = self.kwargs.get('username')
        user = get_object_or_404(User, username=username)
        profile = get_or_create_profile(user)

        # ProfileView tracken (nur wenn nicht eigenes Profil)
        if user != self.request.user:
            viewer_profile = get_or_create_profile(self.request.user)
            ProfileView.objects.create(
                viewed_profile=profile,
                viewer=viewer_profile
            )

        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        viewed_user = self.object.user

        context['my_profile'] = get_or_create_profile(self.request.user)
        context['profile_user'] = viewed_user  # User object for template
        context['user_skills'] = UserSkill.objects.filter(profile=viewed_user.connect_profile).select_related('skill', 'skill__category')
        context['user_needs'] = UserNeed.objects.filter(profile=viewed_user.connect_profile, is_active=True).select_related('skill')
        context['user_posts'] = ConnectPost.objects.filter(author=viewed_user.connect_profile).order_by('-created_at')[:5]

        # Counts für Template
        context['user_skills_count'] = context['user_skills'].count()
        context['connections_count'] = Connection.objects.filter(
            Q(profile_1=viewed_user.connect_profile) | Q(profile_2=viewed_user.connect_profile)
        ).count()
        context['profile_views'] = ProfileView.objects.filter(viewed_profile=viewed_user.connect_profile).count()
        context['is_online'] = viewed_user.connect_profile.is_online()

        # Connection Status prüfen
        context['is_connected'] = Connection.objects.filter(
            Q(profile_1=context['my_profile'], profile_2=viewed_user.connect_profile) |
            Q(profile_1=viewed_user.connect_profile, profile_2=context['my_profile'])
        ).exists()

        # Pending Request prüfen
        context['pending_request'] = ConnectRequest.objects.filter(
            Q(from_profile=context['my_profile'], to_profile=viewed_user.connect_profile) |
            Q(from_profile=viewed_user.connect_profile, to_profile=context['my_profile']),
            status='pending'
        ).first()

        context['has_pending_request'] = context['pending_request'] is not None

        return context


class ProfileEditView(LoomConnectAccessMixin, View):
    """Profil bearbeiten"""
    template_name = 'loomconnect/profile/profile_edit.html'

    def get(self, request):
        profile = get_or_create_profile(request.user)
        form = ProfileEditForm(instance=profile)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })

    def post(self, request):
        profile = get_or_create_profile(request.user)
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)

        if form.is_valid():
            form.save()
            messages.success(request, 'Profil erfolgreich aktualisiert!')
            return redirect('loomconnect:my_profile')

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })


# ==========================================
# SKILL MANAGEMENT VIEWS
# ==========================================

class SkillManagementView(LoomConnectAccessMixin, ListView):
    """Eigene Skills verwalten"""
    model = UserSkill
    template_name = 'loomconnect/skills/skill_management.html'
    context_object_name = 'my_skills'

    def get_queryset(self):
        return UserSkill.objects.filter(profile=self.request.user.connect_profile).select_related('skill', 'skill__category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)
        return context


class AddSkillView(LoomConnectAccessMixin, View):
    """Neuen Skill hinzufügen"""
    template_name = 'loomconnect/skills/add_skill.html'

    def get(self, request):
        form = AddSkillForm()
        profile = get_or_create_profile(request.user)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })

    def post(self, request):
        form = AddSkillForm(request.POST)
        profile = get_or_create_profile(request.user)

        if form.is_valid():
            skill = form.cleaned_data.get('skill')
            custom_skill_name = form.cleaned_data.get('custom_skill_name')
            custom_skill_category = form.cleaned_data.get('custom_skill_category')

            # Custom Skill erstellen falls notwendig
            if custom_skill_name and custom_skill_category:
                skill, created = Skill.objects.get_or_create(
                    name=custom_skill_name,
                    category=custom_skill_category,
                    defaults={
                        'is_predefined': False,
                        'created_by': request.user
                    }
                )

            # Prüfen ob Skill bereits vorhanden
            if UserSkill.objects.filter(profile=profile, skill=skill).exists():
                messages.warning(request, 'Diesen Skill hast du bereits!')
                return redirect('loomconnect:skills_management')

            # UserSkill erstellen
            UserSkill.objects.create(
                profile=profile,
                skill=skill,
                level=form.cleaned_data['level'],
                years_experience=form.cleaned_data.get('years_experience', 0),
                is_offering=form.cleaned_data.get('is_offering', True),
                description=form.cleaned_data.get('description', '')
            )

            messages.success(request, f'Skill "{skill.name}" erfolgreich hinzugefügt!')
            return redirect('loomconnect:skills_management')

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })


class EditSkillView(LoomConnectAccessMixin, UpdateView):
    """Skill bearbeiten"""
    model = UserSkill
    form_class = EditSkillForm
    template_name = 'loomconnect/skills/edit_skill.html'
    success_url = reverse_lazy('loomconnect:skills_management')

    def get_queryset(self):
        return UserSkill.objects.filter(profile=self.request.user.connect_profile)

    def form_valid(self, form):
        messages.success(self.request, 'Skill erfolgreich aktualisiert!')
        return super().form_valid(form)


class DeleteSkillView(LoomConnectAccessMixin, DeleteView):
    """Skill löschen"""
    model = UserSkill
    success_url = reverse_lazy('loomconnect:skills_management')

    def get_queryset(self):
        return UserSkill.objects.filter(profile=self.request.user.connect_profile)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Skill erfolgreich entfernt!')
        return super().delete(request, *args, **kwargs)


# ==========================================
# NEED MANAGEMENT VIEWS
# ==========================================

class NeedManagementView(LoomConnectAccessMixin, ListView):
    """Eigene Bedarfe verwalten"""
    model = UserNeed
    template_name = 'loomconnect/needs/need_management.html'
    context_object_name = 'my_needs'

    def get_queryset(self):
        return UserNeed.objects.filter(profile=self.request.user.connect_profile).select_related('skill')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)
        return context


class AddNeedView(LoomConnectAccessMixin, View):
    """Neuen Bedarf hinzufügen"""
    template_name = 'loomconnect/needs/add_need.html'

    def get(self, request):
        form = AddNeedForm()
        profile = get_or_create_profile(request.user)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })

    def post(self, request):
        form = AddNeedForm(request.POST)
        profile = get_or_create_profile(request.user)

        if form.is_valid():
            skill = form.cleaned_data['skill']

            # Prüfen ob Need bereits vorhanden
            if UserNeed.objects.filter(profile=profile, skill=skill, is_active=True).exists():
                messages.warning(request, 'Diesen Bedarf hast du bereits!')
                return redirect('loomconnect:needs_management')

            # UserNeed erstellen
            UserNeed.objects.create(
                profile=profile,
                skill=skill,
                description=form.cleaned_data['description'],
                urgency=form.cleaned_data['urgency']
            )

            messages.success(request, f'Bedarf für "{skill.name}" erfolgreich hinzugefügt!')
            return redirect('loomconnect:needs_management')

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })


class EditNeedView(LoomConnectAccessMixin, UpdateView):
    """Bedarf bearbeiten"""
    model = UserNeed
    form_class = EditNeedForm
    template_name = 'loomconnect/needs/edit_need.html'
    success_url = reverse_lazy('loomconnect:needs_management')

    def get_queryset(self):
        return UserNeed.objects.filter(profile=self.request.user.connect_profile)

    def form_valid(self, form):
        messages.success(self.request, 'Bedarf erfolgreich aktualisiert!')
        return super().form_valid(form)


class DeleteNeedView(LoomConnectAccessMixin, DeleteView):
    """Bedarf löschen"""
    model = UserNeed
    success_url = reverse_lazy('loomconnect:needs_management')

    def get_queryset(self):
        return UserNeed.objects.filter(profile=self.request.user.connect_profile)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Bedarf erfolgreich entfernt!')
        return super().delete(request, *args, **kwargs)


# ==========================================
# POST VIEWS
# ==========================================

class PostCreateView(LoomConnectAccessMixin, View):
    """Neuen Post erstellen"""
    template_name = 'loomconnect/posts/post_create.html'

    def get(self, request):
        form = PostCreateForm()
        profile = get_or_create_profile(request.user)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })

    def post(self, request):
        form = PostCreateForm(request.POST, request.FILES)
        profile = get_or_create_profile(request.user)

        if form.is_valid():
            post = form.save(commit=False)
            post.author = profile
            post.save()

            # Process skills_input
            skills_input = form.cleaned_data.get('skills_input', '')
            if skills_input:
                skill_names = [s.strip() for s in skills_input.split(',') if s.strip()]
                for skill_name in skill_names:
                    # Get or create skill (default to first category if new)
                    skill, created = Skill.objects.get_or_create(
                        name__iexact=skill_name,
                        defaults={
                            'name': skill_name,
                            'category': SkillCategory.objects.first(),
                            'is_predefined': False,
                            'created_by': request.user
                        }
                    )
                    post.related_skills.add(skill)

            messages.success(request, 'Post erfolgreich erstellt!')
            return redirect('loomconnect:feed')

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })


class PostDetailView(LoomConnectAccessMixin, DetailView):
    """Post Detail mit Kommentaren"""
    model = ConnectPost
    template_name = 'loomconnect/posts/post_detail.html'
    context_object_name = 'post'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)
        context['comment_form'] = PostCommentForm()
        context['comments'] = self.object.comments.select_related('author', 'author__user').order_by('created_at')
        context['user_has_liked'] = self.object.likes.filter(user=self.request.user).exists()

        return context


class PostEditView(LoomConnectAccessMixin, UpdateView):
    """Post bearbeiten"""
    model = ConnectPost
    form_class = PostCreateForm
    template_name = 'loomconnect/posts/post_edit.html'

    def get_queryset(self):
        return ConnectPost.objects.filter(author=self.request.user.connect_profile)

    def get_success_url(self):
        return reverse('loomconnect:post_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        post = form.save()

        # Process skills_input
        skills_input = form.cleaned_data.get('skills_input', '')
        post.related_skills.clear()  # Clear existing skills
        if skills_input:
            skill_names = [s.strip() for s in skills_input.split(',') if s.strip()]
            for skill_name in skill_names:
                skill, created = Skill.objects.get_or_create(
                    name__iexact=skill_name,
                    defaults={
                        'name': skill_name,
                        'category': SkillCategory.objects.first(),
                        'is_predefined': False,
                        'created_by': self.request.user
                    }
                )
                post.related_skills.add(skill)

        messages.success(self.request, 'Post erfolgreich aktualisiert!')
        return super().form_valid(form)


class PostDeleteView(LoomConnectAccessMixin, DeleteView):
    """Post löschen"""
    model = ConnectPost
    success_url = reverse_lazy('loomconnect:feed')

    def get_queryset(self):
        return ConnectPost.objects.filter(author=self.request.user.connect_profile)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Post erfolgreich gelöscht!')
        return super().delete(request, *args, **kwargs)


class PostLikeView(LoomConnectAccessMixin, View):
    """Post liken/unliken (AJAX)"""

    def post(self, request, pk):
        post = get_object_or_404(ConnectPost, pk=pk)

        like, created = PostLike.objects.get_or_create(
            post=post,
            user=request.user
        )

        if not created:
            # Unlike
            like.delete()
            liked = False
        else:
            liked = True

        likes_count = post.likes.count()

        return JsonResponse({
            'liked': liked,
            'likes_count': likes_count
        })


class PostCommentView(LoomConnectAccessMixin, View):
    """Kommentar zu Post hinzufügen (AJAX)"""

    def post(self, request, pk):
        import json

        post = get_object_or_404(ConnectPost, pk=pk)
        profile = get_or_create_profile(request.user)

        # Handle JSON data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                content = data.get('content', '').strip()
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'errors': {'content': ['Invalid JSON']}
                }, status=400)
        else:
            # Handle form data
            content = request.POST.get('content', '').strip()

        if not content:
            return JsonResponse({
                'success': False,
                'errors': {'content': ['Kommentar darf nicht leer sein']}
            }, status=400)

        # Create comment
        comment = PostComment.objects.create(
            post=post,
            author=profile,
            content=content
        )

        return JsonResponse({
            'success': True,
            'comment': {
                'author': request.user.username,
                'content': comment.content,
                'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
            }
        })


class PostShareView(LoomConnectAccessMixin, View):
    """Post teilen/reposten (AJAX)"""

    def post(self, request, pk):
        original_post = get_object_or_404(ConnectPost, pk=pk)
        profile = get_or_create_profile(request.user)

        # Check if already shared by this user
        already_shared = ConnectPost.objects.filter(
            author=profile,
            shared_from=original_post
        ).exists()

        if already_shared:
            return JsonResponse({
                'success': False,
                'error': 'Du hast diesen Beitrag bereits geteilt.'
            }, status=400)

        # Create shared post
        shared_post = ConnectPost.objects.create(
            author=profile,
            content=original_post.content,
            post_type=original_post.post_type,
            visibility=original_post.visibility,
            location=original_post.location,
            image=original_post.image,
            shared_from=original_post
        )

        # Copy related skills
        shared_post.related_skills.set(original_post.related_skills.all())

        return JsonResponse({
            'success': True,
            'message': 'Beitrag erfolgreich geteilt!'
        })


# ==========================================
# CONNECT REQUEST VIEWS
# ==========================================

class RequestInboxView(LoomConnectAccessMixin, ListView):
    """Connect-Anfragen Inbox"""
    model = ConnectRequest
    template_name = 'loomconnect/requests/inbox.html'
    context_object_name = 'requests'

    def get_queryset(self):
        profile = get_or_create_profile(self.request.user)
        return ConnectRequest.objects.filter(
            to_profile=profile,
            status='pending'
        ).select_related('from_profile', 'from_profile__user', 'related_skill').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)

        # Sent Requests
        context['sent_requests'] = ConnectRequest.objects.filter(
            from_profile=context['profile'],
            status='pending'
        ).select_related('to_profile', 'to_profile__user')

        return context


class SendRequestView(LoomConnectAccessMixin, View):
    """Connect-Anfrage senden"""
    template_name = 'loomconnect/requests/send_request.html'

    def get(self, request, username):
        receiver = get_object_or_404(User, username=username)

        if receiver == request.user:
            messages.error(request, 'Du kannst dir selbst keine Anfrage senden!')
            return redirect('loomconnect:discover')

        # Profile erhalten
        my_profile = get_or_create_profile(request.user)
        receiver_profile = get_or_create_profile(receiver)

        # Prüfen ob bereits verbunden
        if Connection.objects.filter(
            Q(profile_1=my_profile, profile_2=receiver_profile) | Q(profile_1=receiver_profile, profile_2=my_profile)
        ).exists():
            messages.info(request, 'Ihr seid bereits verbunden!')
            return redirect('loomconnect:profile', username=username)

        # Prüfen ob bereits Anfrage existiert
        if ConnectRequest.objects.filter(
            Q(from_profile=my_profile, to_profile=receiver_profile) | Q(from_profile=receiver_profile, to_profile=my_profile),
            status='pending'
        ).exists():
            messages.warning(request, 'Es existiert bereits eine offene Anfrage!')
            return redirect('loomconnect:profile', username=username)

        form = SendConnectRequestForm()
        profile = get_or_create_profile(request.user)
        receiver_profile = get_or_create_profile(receiver)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile,
            'receiver': receiver,
            'receiver_profile': receiver_profile
        })

    def post(self, request, username):
        receiver = get_object_or_404(User, username=username)
        form = SendConnectRequestForm(request.POST)
        profile = get_or_create_profile(request.user)
        receiver_profile = get_or_create_profile(receiver)

        if form.is_valid():
            connect_request = ConnectRequest.objects.create(
                from_profile=profile,
                to_profile=receiver_profile,
                request_type=form.cleaned_data['request_type'],
                message=form.cleaned_data['message'],
                related_skill=form.cleaned_data.get('related_skill')
            )

            messages.success(request, f'Anfrage an {receiver.username} erfolgreich gesendet!')
            return redirect('loomconnect:profile', username=username)

        receiver_profile = get_or_create_profile(receiver)
        return render(request, self.template_name, {
            'form': form,
            'profile': profile,
            'receiver': receiver,
            'receiver_profile': receiver_profile
        })


class AcceptRequestView(LoomConnectAccessMixin, View):
    """Connect-Anfrage akzeptieren"""

    def post(self, request, pk):
        profile = get_or_create_profile(request.user)
        connect_request = get_object_or_404(
            ConnectRequest,
            pk=pk,
            to_profile=profile,
            status='pending'
        )

        connect_request.status = 'accepted'
        connect_request.save()

        # Signal erstellt automatisch Connection + ChatRoom
        messages.success(request, f'Du bist jetzt mit {connect_request.from_profile.user.username} verbunden!')
        return redirect('loomconnect:request_inbox')


class DeclineRequestView(LoomConnectAccessMixin, View):
    """Connect-Anfrage ablehnen"""

    def post(self, request, pk):
        profile = get_or_create_profile(request.user)
        connect_request = get_object_or_404(
            ConnectRequest,
            pk=pk,
            to_profile=profile,
            status='pending'
        )

        connect_request.status = 'declined'
        connect_request.save()

        messages.info(request, 'Anfrage abgelehnt.')
        return redirect('loomconnect:request_inbox')


# ==========================================
# CONNECTION VIEWS
# ==========================================

class ConnectionsView(LoomConnectAccessMixin, ListView):
    """Alle meine Connections"""
    model = Connection
    template_name = 'loomconnect/connections/connections.html'
    context_object_name = 'connections'
    paginate_by = 30

    def get_queryset(self):
        profile = get_or_create_profile(self.request.user)
        return Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).select_related('profile_1', 'profile_2', 'profile_1__user', 'profile_2__user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)

        return context


# ==========================================
# STORY VIEWS
# ==========================================

class StoriesView(LoomConnectAccessMixin, ListView):
    """Stories anzeigen (24h)"""
    model = ConnectStory
    template_name = 'loomconnect/stories/stories.html'
    context_object_name = 'stories'

    def get_queryset(self):
        # Nur Stories der letzten 24h
        return ConnectStory.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).select_related('profile', 'profile__user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)

        return context


class StoryCreateView(LoomConnectAccessMixin, View):
    """Neue Story erstellen"""
    template_name = 'loomconnect/stories/story_create.html'

    def get(self, request):
        form = StoryCreateForm()
        profile = get_or_create_profile(request.user)

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })

    def post(self, request):
        form = StoryCreateForm(request.POST, request.FILES)
        profile = get_or_create_profile(request.user)

        if form.is_valid():
            story = form.save(commit=False)
            story.profile = profile
            story.save()

            messages.success(request, 'Story erfolgreich erstellt!')
            return redirect('loomconnect:stories')

        return render(request, self.template_name, {
            'form': form,
            'profile': profile
        })


class StoryDetailView(LoomConnectAccessMixin, DetailView):
    """Story Detail anzeigen"""
    model = ConnectStory
    template_name = 'loomconnect/stories/story_detail.html'
    context_object_name = 'story'

    def get_object(self, queryset=None):
        story = super().get_object(queryset)

        # StoryView tracken
        viewer_profile = get_or_create_profile(self.request.user)
        StoryView.objects.create(
            story=story,
            viewer=viewer_profile
        )

        return story

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_or_create_profile(self.request.user)
        return context


# ==========================================
# SEARCH VIEW
# ==========================================

class SearchView(LoomConnectAccessMixin, View):
    """Suche nach Profiles/Skills"""
    template_name = 'loomconnect/search/search.html'

    def get(self, request):
        form = SearchForm(request.GET)
        profile = get_or_create_profile(request.user)

        results = []

        if form.is_valid():
            query = form.cleaned_data.get('query', '')
            category = form.cleaned_data.get('category')
            availability = form.cleaned_data.get('availability')
            sort_by = form.cleaned_data.get('sort_by', 'relevance')

            if query or category or availability:
                # Suche
                results = ConnectProfile.objects.filter(
                    onboarding_completed=True,
                    is_public=True
                ).exclude(user=request.user).select_related('user').annotate(
                    skills_count=Count('userskill'),
                    connections_count=Count('connections_as_profile_1') + Count('connections_as_profile_2')
                )

                if query:
                    results = results.filter(
                        Q(user__username__icontains=query) |
                        Q(user__first_name__icontains=query) |
                        Q(user__last_name__icontains=query) |
                        Q(bio__icontains=query) |
                        Q(userskill__skill__name__icontains=query)
                    ).distinct()

                if category:
                    results = results.filter(userskill__skill__category=category).distinct()

                if availability == 'online':
                    results = results.filter(last_seen__gte=timezone.now() - timedelta(minutes=15))
                elif availability == 'active':
                    results = results.filter(last_seen__gte=timezone.now() - timedelta(days=7))

                # Sortierung
                if sort_by == 'karma':
                    results = results.order_by('-karma_score')
                elif sort_by == 'connections':
                    results = results.order_by('-connections_count')
                elif sort_by == 'recent':
                    results = results.order_by('-user__date_joined')
                else:
                    results = results.order_by('-karma_score', '-skills_count')


        return render(request, self.template_name, {
            'form': form,
            'profile': profile,
            'results': results
        })


# ==========================================
# INFO PAGE (PUBLIC)
# ==========================================

class InfoPageView(View):
    """Öffentliche Info-Seite über LoomConnect (SEO)"""
    template_name = 'loomconnect/info.html'

    def get(self, request):
        # Public page - no login required

        # Stats für SEO
        total_users = ConnectProfile.objects.filter(onboarding_completed=True).count()
        total_skills = Skill.objects.filter(is_active=True).count()
        total_connections = Connection.objects.count()


        return render(request, self.template_name, {
            'total_users': total_users,
            'total_skills': total_skills,
            'total_connections': total_connections,
        })


# ==========================================
# API VIEWS (AJAX)
# ==========================================

class GetMatchesAPIView(LoomConnectAccessMixin, View):
    """API: Matches basierend auf Skills abrufen"""

    def get(self, request):
        profile = get_or_create_profile(request.user)

        # Meine Skills die ich anbiete
        my_offering_skills = UserSkill.objects.filter(
            profile=profile,
            is_offering=True
        ).values_list('skill_id', flat=True)

        # User die genau diese Skills suchen
        matches = UserNeed.objects.filter(
            skill_id__in=my_offering_skills,
            is_active=True
        ).exclude(profile=profile).select_related('profile', 'profile__user', 'skill')[:10]

        data = []
        for match in matches:
            data.append({
                'user_id': match.profile.user.id,
                'username': match.profile.user.username,
                'skill': match.skill.name,
                'description': match.description,
                'urgency': match.get_urgency_display(),
                'karma_score': match.profile.karma_score
            })

        return JsonResponse({'matches': data})


class SkillSearchAPIView(LoomConnectAccessMixin, View):
    """API: Skills für Autocomplete suchen"""

    def get(self, request):
        query = request.GET.get('q', '')

        if len(query) < 2:
            return JsonResponse({'skills': []})

        skills = Skill.objects.filter(
            is_active=True,
            name__icontains=query
        ).order_by('-usage_count')[:10]

        data = []
        for skill in skills:
            data.append({
                'id': skill.id,
                'name': skill.name,
                'category': skill.category.name if skill.category else ''
            })

        return JsonResponse({'skills': data})


# ==========================================
# ADMIN/STATISTICS VIEWS
# ==========================================

class StatisticsView(UserPassesTestMixin, TemplateView):
    """
    Admin-View: Statistiken über LoomConnect
    Nur für Superuser zugänglich
    """
    template_name = 'loomconnect/statistics.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from .services import StatisticsService

        # Global stats
        context['stats'] = StatisticsService.get_global_stats()

        # Recent connections (last 10)
        recent_connections = Connection.objects.select_related(
            'profile_1__user', 'profile_2__user'
        ).order_by('-created_at')[:10]
        context['recent_connections'] = recent_connections

        # Recent profiles (last 10)
        recent_profiles = ConnectProfile.objects.select_related('user').order_by('-created_at')[:10]
        context['recent_profiles'] = recent_profiles

        return context
