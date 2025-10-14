from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
import uuid

User = get_user_model()


class ConnectProfile(models.Model):
    """User-Profil für LoomConnect"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='connect_profile')
    bio = models.TextField(blank=True, verbose_name='Über mich', max_length=500)
    avatar = models.ImageField(upload_to='loomconnect/avatars/%Y/%m/', blank=True, null=True, verbose_name='Profilbild')
    location = models.CharField(max_length=200, blank=True, verbose_name='Standort')
    website = models.URLField(blank=True, verbose_name='Website')
    linkedin = models.URLField(blank=True, verbose_name='LinkedIn')
    is_public = models.BooleanField(default=True, verbose_name='Öffentliches Profil')
    show_online_status = models.BooleanField(default=True, verbose_name='Online-Status anzeigen')

    AVAILABILITY_CHOICES = [
        ('available', 'Verfügbar'),
        ('busy', 'Beschäftigt'),
        ('away', 'Abwesend'),
        ('dnd', 'Nicht stören'),
    ]
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='available', verbose_name='Verfügbarkeit')

    # Notification preferences
    notify_new_matches = models.BooleanField(default=True, verbose_name='Benachrichtigung bei neuen Matches')
    notify_messages = models.BooleanField(default=True, verbose_name='Benachrichtigung bei neuen Nachrichten')
    notify_weekly_digest = models.BooleanField(default=False, verbose_name='Wöchentliche Zusammenfassung')

    # Stats
    profile_views_count = models.IntegerField(default=0, verbose_name='Profil-Aufrufe')
    karma_score = models.IntegerField(default=0, verbose_name='Karma-Punkte')
    successful_connections = models.IntegerField(default=0, verbose_name='Erfolgreiche Verbindungen')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    onboarding_completed = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Connect-Profil'
        verbose_name_plural = 'Connect-Profile'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def get_absolute_url(self):
        return reverse('loomconnect:profile', kwargs={'username': self.user.username})

    def is_online(self):
        """Check if user is online (last activity < 5 minutes)"""
        if not self.show_online_status:
            return False
        return self.user.is_currently_online() if hasattr(self.user, 'is_currently_online') else False

    def get_skills(self):
        """Get all skills user offers"""
        return self.userskill_set.filter(is_offering=True)

    def get_needs(self):
        """Get all active needs"""
        return self.userneed_set.filter(is_active=True)

    def get_connections_count(self):
        """Get total connections"""
        return Connection.objects.filter(
            Q(profile_1=self) | Q(profile_2=self)
        ).count()


class SkillCategory(models.Model):
    """Skill-Kategorien (Entwicklung, Design, etc.)"""
    name = models.CharField(max_length=100, unique=True, verbose_name='Name')
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, verbose_name='Icon', help_text='Emoji oder Icon-Klasse')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    order = models.IntegerField(default=0, verbose_name='Reihenfolge')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        verbose_name = 'Skill-Kategorie'
        verbose_name_plural = 'Skill-Kategorien'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
            # Ensure unique slug
            counter = 1
            original_slug = self.slug
            while SkillCategory.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_skills_count(self):
        """Count active skills in this category"""
        return self.skill_set.filter(is_active=True).count()


class Skill(models.Model):
    """Skills (vordefiniert + custom)"""
    category = models.ForeignKey(SkillCategory, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100, verbose_name='Name')
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, verbose_name='Icon')
    description = models.TextField(blank=True, verbose_name='Beschreibung')

    # Predefined vs Custom
    is_predefined = models.BooleanField(default=False, verbose_name='Vordefiniert')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='custom_skills')

    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    usage_count = models.IntegerField(default=0, verbose_name='Verwendungen')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
            # Ensure unique slug
            counter = 1
            original_slug = self.slug
            while Skill.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Skill'
        verbose_name_plural = 'Skills'
        ordering = ['-usage_count', 'name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])


class UserSkill(models.Model):
    """Skills die ein User hat/anbietet"""
    LEVEL_CHOICES = [
        ('anfaenger', 'Anfänger'),
        ('fortgeschritten', 'Fortgeschritten'),
        ('experte', 'Experte'),
        ('profi', 'Profi'),
    ]

    profile = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='fortgeschritten')
    years_experience = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Jahre Erfahrung',
        validators=[
            MinValueValidator(0, message='Die Anzahl der Jahre muss mindestens 0 sein.'),
            MaxValueValidator(50, message='Die Anzahl der Jahre darf maximal 50 sein.')
        ]
    )
    is_offering = models.BooleanField(default=True, verbose_name='Bietet Hilfe an')
    description = models.TextField(blank=True, verbose_name='Zusatzinfo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'User-Skill'
        verbose_name_plural = 'User-Skills'
        unique_together = ('profile', 'skill')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.user.username} - {self.skill.name} ({self.get_level_display()})"

    def save(self, *args, **kwargs):
        # Increment skill usage counter
        if not self.pk:
            self.skill.increment_usage()
        super().save(*args, **kwargs)


class UserNeed(models.Model):
    """Skills die ein User sucht"""
    URGENCY_CHOICES = [
        ('niedrig', 'Niedrig'),
        ('mittel', 'Mittel'),
        ('hoch', 'Hoch'),
    ]

    profile = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    description = models.TextField(verbose_name='Beschreibung', max_length=500)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='mittel')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User-Bedarf'
        verbose_name_plural = 'User-Bedarfe'
        ordering = ['-urgency', '-created_at']

    def __str__(self):
        return f"{self.profile.user.username} sucht: {self.skill.name}"


class ConnectPost(models.Model):
    """Feed Posts"""
    POST_TYPES = [
        ('offering', 'Biete Skill an'),
        ('seeking', 'Suche Skill'),
        ('update', 'Update/Neuigkeit'),
        ('achievement', 'Erfolg/Meilenstein'),
        ('question', 'Frage'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Öffentlich'),
        ('connections', 'Nur meine Connections'),
        ('local', 'Nur aus meiner Umgebung'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(verbose_name='Inhalt', max_length=1000)
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default='update')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='public', verbose_name='Sichtbarkeit')
    location = models.CharField(max_length=200, blank=True, verbose_name='Standort', help_text='Nur relevant bei "Nur aus meiner Umgebung"')

    # Shared/Repost
    shared_from = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='shares', verbose_name='Geteilt von')

    # Optional
    image = models.ImageField(upload_to='loomconnect/posts/%Y/%m/', blank=True, null=True)
    related_skills = models.ManyToManyField(Skill, blank=True, related_name='posts')

    # Stats
    likes_count = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

    def __str__(self):
        return f"{self.author.user.username} - {self.get_post_type_display()} ({self.created_at.strftime('%Y-%m-%d')})"

    def get_absolute_url(self):
        return reverse('loomconnect:post_detail', kwargs={'pk': self.pk})

    def increment_views(self):
        """Increment views counter"""
        self.views_count += 1
        self.save(update_fields=['views_count'])


class PostComment(models.Model):
    """Kommentare zu Posts"""
    post = models.ForeignKey(ConnectPost, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name='Kommentar', max_length=500)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Kommentar'
        verbose_name_plural = 'Kommentare'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.user.username} on {self.post.id}: {self.content[:50]}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Update comment counter on post
        if is_new:
            self.post.comments_count = self.post.comments.count()
            self.post.save(update_fields=['comments_count'])


class PostLike(models.Model):
    """Likes für Posts"""
    post = models.ForeignKey(ConnectPost, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Like'
        verbose_name_plural = 'Likes'
        unique_together = ('post', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} likes {self.post.id}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Update like counter on post
        if is_new:
            self.post.likes_count = self.post.likes.count()
            self.post.save(update_fields=['likes_count'])


class ConnectRequest(models.Model):
    """Connect-Anfragen zwischen Usern"""
    REQUEST_TYPES = [
        ('skill_exchange', 'Skill-Tausch'),
        ('help_request', 'Hilfe-Anfrage'),
        ('networking', 'Networking'),
        ('collaboration', 'Zusammenarbeit'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('accepted', 'Akzeptiert'),
        ('declined', 'Abgelehnt'),
        ('expired', 'Abgelaufen'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_profile = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='sent_requests')
    to_profile = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='received_requests')

    message = models.TextField(verbose_name='Nachricht', max_length=500)
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='networking')
    related_skill = models.ForeignKey(Skill, on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    chat_room = models.ForeignKey('chat.ChatRoom', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Connect-Anfrage'
        verbose_name_plural = 'Connect-Anfragen'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['to_profile', 'status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.from_profile.user.username} → {self.to_profile.user.username} ({self.get_status_display()})"

    def accept(self):
        """Accept the connect request"""
        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.save()

    def decline(self):
        """Decline the connect request"""
        self.status = 'declined'
        self.responded_at = timezone.now()
        self.save()

    def is_expired(self):
        """Check if request is expired"""
        if self.expires_at and self.status == 'pending':
            return timezone.now() > self.expires_at
        return False


class Connection(models.Model):
    """Aktive Verbindungen zwischen Usern"""
    profile_1 = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='connections_as_profile_1')
    profile_2 = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='connections_as_profile_2')
    chat_room = models.ForeignKey('chat.ChatRoom', on_delete=models.SET_NULL, null=True, blank=True)
    connect_request = models.OneToOneField(ConnectRequest, on_delete=models.SET_NULL, null=True, blank=True)

    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Verbindung'
        verbose_name_plural = 'Verbindungen'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile_1.user.username} ↔ {self.profile_2.user.username}"

    def get_other_profile(self, profile):
        """Get the other profile in the connection"""
        return self.profile_2 if self.profile_1 == profile else self.profile_1


class SkillExchange(models.Model):
    """Tracking von Skill-Tausch Aktivitäten"""
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('completed', 'Abgeschlossen'),
        ('cancelled', 'Abgebrochen'),
    ]

    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='skill_exchanges')
    skill_offered = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='exchanges_as_offered')
    skill_requested = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='exchanges_as_requested')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True, verbose_name='Notizen')

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Skill-Tausch'
        verbose_name_plural = 'Skill-Tausche'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.skill_offered.name} ↔ {self.skill_requested.name}"

    def complete(self):
        """Mark exchange as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class ProfileView(models.Model):
    """Tracking von Profil-Aufrufen"""
    viewer = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='profile_views_made')
    viewed_profile = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='profile_views_received')
    viewed_at = models.DateTimeField(auto_now_add=True)
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Profil-Aufruf'
        verbose_name_plural = 'Profil-Aufrufe'
        ordering = ['-viewed_at']

    def __str__(self):
        viewer_name = self.viewer.user.username if self.viewer else 'Anonymous'
        return f"{viewer_name} → {self.viewed_profile.user.username}"


class ConnectStory(models.Model):
    """Stories (24h verfügbar)"""
    STORY_TYPES = [
        ('available', 'Verfügbar'),
        ('project', 'Projekt'),
        ('achievement', 'Erfolg'),
        ('update', 'Update'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, related_name='stories')
    content = models.TextField(verbose_name='Inhalt', max_length=500)
    story_type = models.CharField(max_length=20, choices=STORY_TYPES, default='update')
    image = models.ImageField(upload_to='loomconnect/stories/%Y/%m/', blank=True, null=True)

    views_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Story'
        verbose_name_plural = 'Stories'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile.user.username} - {self.get_story_type_display()}"

    def is_active(self):
        """Check if story is still active (not expired)"""
        return timezone.now() < self.expires_at

    def save(self, *args, **kwargs):
        # Set expiration to 24h from creation
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)


class StoryView(models.Model):
    """Tracking von Story-Views"""
    story = models.ForeignKey(ConnectStory, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(ConnectProfile, on_delete=models.CASCADE, null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Story-View'
        verbose_name_plural = 'Story-Views'
        unique_together = ('story', 'viewer')
        ordering = ['-viewed_at']

    def __str__(self):
        viewer_name = self.viewer.user.username if self.viewer else 'Anonymous'
        return f"{viewer_name} viewed {self.story.profile.user.username}'s story"
