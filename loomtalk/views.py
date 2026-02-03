from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator

from .models import Category, Tag, Topic, Reply, Vote, Mention

User = get_user_model()


# ==========================================
# MIXINS
# ==========================================

class LoomTalkPublicMixin:
    """Mixin fuer oeffentliche Views - setzt can_write Context"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_write'] = self.request.user.is_authenticated
        return context


class LoomTalkWriteMixin(LoginRequiredMixin):
    """Mixin fuer Views die Login erfordern - prueft App-Zugriff"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # AppPermission pruefen (inkl. superuser_bypass)
        from accounts.models import AppPermission
        if not AppPermission.user_has_access('loomtalk', request.user):
            messages.error(request, 'Du hast keinen Zugriff auf LoomTalk.')
            return redirect('startseite')

        return super().dispatch(request, *args, **kwargs)


# ==========================================
# PUBLIC VIEWS (Lesen ohne Login)
# ==========================================

class ForumHomeView(LoomTalkPublicMixin, ListView):
    """Startseite des Forums - Kategorien und aktuelle Themen"""
    template_name = 'loomtalk/home.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('order', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Aktuelle Themen
        context['recent_topics'] = Topic.objects.filter(
            is_active=True
        ).select_related('author', 'category').order_by('-created_at')[:10]

        # Beliebte Themen (nach Score)
        context['popular_topics'] = Topic.objects.filter(
            is_active=True
        ).select_related('author', 'category').order_by('-score', '-views_count')[:5]

        # Beliebte Tags
        context['popular_tags'] = Tag.objects.filter(
            usage_count__gt=0
        ).order_by('-usage_count')[:15]

        # Stats
        context['total_topics'] = Topic.objects.filter(is_active=True).count()
        context['total_replies'] = Reply.objects.filter(is_active=True).count()
        context['total_users'] = User.objects.filter(
            loomtalk_topics__isnull=False
        ).distinct().count()

        return context


class TopicListView(LoomTalkPublicMixin, ListView):
    """Liste aller Themen mit Filterung und Sortierung"""
    template_name = 'loomtalk/topic_list.html'
    context_object_name = 'topics'
    paginate_by = 20

    def get_queryset(self):
        queryset = Topic.objects.filter(
            is_active=True
        ).select_related('author', 'category').prefetch_related('tags')

        # Sortierung
        sort = self.request.GET.get('sort', 'recent')
        if sort == 'popular':
            queryset = queryset.order_by('-score', '-views_count')
        elif sort == 'hot':
            # Hot = viele Antworten in letzter Zeit
            queryset = queryset.order_by('-last_activity_at')
        else:  # recent
            queryset = queryset.order_by('-created_at')

        # Kategorie-Filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Tag-Filter
        tag_slug = self.request.GET.get('tag')
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)

        # Status-Filter
        status = self.request.GET.get('status')
        if status in ['open', 'closed', 'pinned']:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['popular_tags'] = Tag.objects.filter(usage_count__gt=0).order_by('-usage_count')[:20]
        context['current_sort'] = self.request.GET.get('sort', 'recent')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_tag'] = self.request.GET.get('tag', '')
        return context


class CategoryDetailView(LoomTalkPublicMixin, DetailView):
    """Zeigt alle Themen einer Kategorie"""
    model = Category
    template_name = 'loomtalk/category_detail.html'
    context_object_name = 'category'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Themen in dieser Kategorie
        topics = Topic.objects.filter(
            category=self.object,
            is_active=True
        ).select_related('author').prefetch_related('tags').order_by('-last_activity_at')

        paginator = Paginator(topics, 20)
        page = self.request.GET.get('page', 1)
        context['topics'] = paginator.get_page(page)

        return context


class TopicDetailView(LoomTalkPublicMixin, DetailView):
    """Zeigt ein Thema mit allen Antworten"""
    model = Topic
    template_name = 'loomtalk/topic_detail.html'
    context_object_name = 'topic'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        return Topic.objects.filter(is_active=True).select_related('author', 'category').prefetch_related('tags')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # View-Counter erhoehen
        self.object.increment_views()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Antworten laden - nur Top-Level (parent=None)
        replies = Reply.objects.filter(
            topic=self.object,
            is_active=True,
            parent=None
        ).select_related('author').prefetch_related(
            Prefetch(
                'children',
                queryset=Reply.objects.filter(is_active=True).select_related('author').order_by('created_at')
            )
        ).order_by('created_at')

        context['replies'] = replies

        # User's Vote (falls eingeloggt)
        if self.request.user.is_authenticated:
            context['user_vote'] = Vote.objects.filter(
                user=self.request.user,
                topic=self.object
            ).first()

            # User's Votes auf Replies
            reply_votes = Vote.objects.filter(
                user=self.request.user,
                reply__in=replies
            ).values_list('reply_id', 'vote_type')
            context['user_reply_votes'] = dict(reply_votes)

        return context


class TagTopicsView(LoomTalkPublicMixin, ListView):
    """Zeigt alle Themen mit einem bestimmten Tag"""
    template_name = 'loomtalk/tag_topics.html'
    context_object_name = 'topics'
    paginate_by = 20

    def get_queryset(self):
        self.tag = get_object_or_404(Tag, slug=self.kwargs['slug'])
        return Topic.objects.filter(
            tags=self.tag,
            is_active=True
        ).select_related('author', 'category').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tag'] = self.tag
        return context


class SearchView(LoomTalkPublicMixin, ListView):
    """Suche in Themen und Antworten"""
    template_name = 'loomtalk/search.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if not query or len(query) < 3:
            return Topic.objects.none()

        return Topic.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query),
            is_active=True
        ).select_related('author', 'category').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


# ==========================================
# PROTECTED VIEWS (Schreiben mit Login)
# ==========================================

class TopicCreateView(LoomTalkWriteMixin, CreateView):
    """Neues Thema erstellen"""
    model = Topic
    template_name = 'loomtalk/topic_create.html'
    fields = ['title', 'content', 'category']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['can_write'] = True
        return context

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)

        # Tags verarbeiten (aus POST)
        tags_str = self.request.POST.get('tags', '')
        if tags_str:
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for tag_name in tag_names[:5]:  # Max 5 Tags
                tag, created = Tag.objects.get_or_create(
                    name=tag_name,
                    defaults={'slug': tag_name.lower().replace(' ', '-')}
                )
                self.object.tags.add(tag)
                # Usage Counter erhoehen
                Tag.objects.filter(pk=tag.pk).update(usage_count=tag.usage_count + 1)

        # Mentions parsen
        self._process_mentions(form.instance.content, self.object)

        # Kategorie-Counter aktualisieren
        Category.objects.filter(pk=form.instance.category_id).update(
            topics_count=Count('topics')
        )

        messages.success(self.request, 'Dein Thema wurde erstellt!')
        return response

    def get_success_url(self):
        return reverse('loomtalk:topic_detail', kwargs={'pk': self.object.pk})

    def _process_mentions(self, content, topic):
        """Verarbeitet @mentions im Content"""
        import re
        pattern = r'@(\w+)'
        usernames = re.findall(pattern, content)

        for username in set(usernames):
            try:
                mentioned_user = User.objects.get(username=username)
                if mentioned_user != self.request.user:
                    Mention.objects.create(
                        mentioned_user=mentioned_user,
                        mentioning_user=self.request.user,
                        topic=topic
                    )
            except User.DoesNotExist:
                pass


class TopicEditView(LoomTalkWriteMixin, UpdateView):
    """Thema bearbeiten (nur eigene)"""
    model = Topic
    template_name = 'loomtalk/topic_edit.html'
    fields = ['title', 'content', 'category']
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        # Nur eigene Themen oder Superuser
        if self.request.user.is_superuser:
            return Topic.objects.all()
        return Topic.objects.filter(author=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['can_write'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Dein Thema wurde aktualisiert!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('loomtalk:topic_detail', kwargs={'pk': self.object.pk})


class ReplyCreateView(LoomTalkWriteMixin, View):
    """Antwort auf ein Thema erstellen"""

    def post(self, request, pk):
        topic = get_object_or_404(Topic, pk=pk, is_active=True)
        content = request.POST.get('content', '').strip()
        parent_id = request.POST.get('parent_id')

        if not content:
            messages.error(request, 'Bitte gib eine Antwort ein.')
            return redirect('loomtalk:topic_detail', pk=pk)

        if len(content) > 5000:
            messages.error(request, 'Deine Antwort ist zu lang (max. 5000 Zeichen).')
            return redirect('loomtalk:topic_detail', pk=pk)

        parent = None
        if parent_id:
            parent = Reply.objects.filter(pk=parent_id, topic=topic).first()

        reply = Reply.objects.create(
            topic=topic,
            author=request.user,
            content=content,
            parent=parent
        )

        # Topic last_activity aktualisieren
        Topic.objects.filter(pk=pk).update(last_activity_at=timezone.now())

        # Reply-Counter aktualisieren
        topic.update_replies_count()

        # Mentions parsen
        self._process_mentions(content, reply)

        messages.success(request, 'Deine Antwort wurde gepostet!')
        return redirect(f"{reverse('loomtalk:topic_detail', kwargs={'pk': pk})}#reply-{reply.pk}")

    def _process_mentions(self, content, reply):
        """Verarbeitet @mentions im Content"""
        import re
        pattern = r'@(\w+)'
        usernames = re.findall(pattern, content)

        for username in set(usernames):
            try:
                mentioned_user = User.objects.get(username=username)
                if mentioned_user != self.request.user:
                    Mention.objects.create(
                        mentioned_user=mentioned_user,
                        mentioning_user=self.request.user,
                        reply=reply
                    )
            except User.DoesNotExist:
                pass


class VoteView(LoomTalkWriteMixin, View):
    """Upvote/Downvote fuer Topics und Replies"""

    def post(self, request, content_type, pk):
        vote_type = int(request.POST.get('vote_type', 0))

        if vote_type not in [1, -1]:
            return JsonResponse({'error': 'Ungueltiger Vote-Typ'}, status=400)

        if content_type == 'topic':
            target = get_object_or_404(Topic, pk=pk)
            vote, created = Vote.objects.get_or_create(
                user=request.user,
                topic=target,
                defaults={'vote_type': vote_type}
            )
        elif content_type == 'reply':
            target = get_object_or_404(Reply, pk=pk)
            vote, created = Vote.objects.get_or_create(
                user=request.user,
                reply=target,
                defaults={'vote_type': vote_type}
            )
        else:
            return JsonResponse({'error': 'Ungueltiger Content-Typ'}, status=400)

        if not created:
            if vote.vote_type == vote_type:
                # Gleicher Vote -> entfernen
                vote.delete()
                target.refresh_from_db()
                return JsonResponse({
                    'success': True,
                    'action': 'removed',
                    'new_score': target.score
                })
            else:
                # Anderen Vote -> aendern
                vote.vote_type = vote_type
                vote.save()

        target.refresh_from_db()
        return JsonResponse({
            'success': True,
            'action': 'voted',
            'new_score': target.score
        })


class MentionsView(LoomTalkWriteMixin, ListView):
    """Zeigt alle Erwaehnungen des eingeloggten Users"""
    template_name = 'loomtalk/mentions.html'
    context_object_name = 'mentions'
    paginate_by = 20

    def get_queryset(self):
        return Mention.objects.filter(
            mentioned_user=self.request.user
        ).select_related(
            'mentioning_user', 'topic', 'reply', 'reply__topic'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_write'] = True
        context['unread_count'] = Mention.objects.filter(
            mentioned_user=self.request.user,
            is_read=False
        ).count()
        return context


class MarkMentionReadView(LoomTalkWriteMixin, View):
    """Markiert eine Erwaehnung als gelesen"""

    def post(self, request, pk):
        mention = get_object_or_404(
            Mention,
            pk=pk,
            mentioned_user=request.user
        )
        mention.is_read = True
        mention.save(update_fields=['is_read'])

        return JsonResponse({'success': True})


# ==========================================
# API VIEWS
# ==========================================

class TagSearchView(View):
    """API: Sucht nach Tags (fuer Autocomplete)"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'tags': []})

        tags = Tag.objects.filter(
            name__icontains=query
        ).order_by('-usage_count')[:10]

        return JsonResponse({
            'tags': [{'name': t.name, 'slug': t.slug, 'count': t.usage_count} for t in tags]
        })


class UserSearchView(View):
    """API: Sucht nach Usern (fuer @mentions Autocomplete)"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'users': []})

        users = User.objects.filter(
            username__icontains=query
        )[:10]

        return JsonResponse({
            'users': [{'username': u.username, 'id': u.id} for u in users]
        })
