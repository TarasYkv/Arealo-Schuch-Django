import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils import timezone

User = get_user_model()


class Category(models.Model):
    """Diskussions-Kategorien mit Farben und Icons"""
    name = models.CharField(max_length=100, unique=True, verbose_name='Name')
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    icon = models.CharField(
        max_length=50,
        default='bi-chat-dots',
        verbose_name='Icon',
        help_text='Bootstrap Icon Klasse (z.B. bi-chat-dots)'
    )
    color = models.CharField(
        max_length=7,
        default='#667eea',
        verbose_name='Farbe',
        help_text='Hex-Farbcode (z.B. #667eea)'
    )
    order = models.IntegerField(default=0, verbose_name='Reihenfolge')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    # Denormalisierte Stats
    topics_count = models.IntegerField(default=0, verbose_name='Anzahl Themen')
    posts_count = models.IntegerField(default=0, verbose_name='Anzahl Beitraege')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kategorie'
        verbose_name_plural = 'Kategorien'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    """Tags fuer Themen-Kategorisierung"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Name')
    slug = models.SlugField(max_length=50, unique=True)
    usage_count = models.IntegerField(default=0, verbose_name='Verwendungen')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ['-usage_count', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Topic(models.Model):
    """Diskussionsthema/Thread"""
    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('closed', 'Geschlossen'),
        ('pinned', 'Angepinnt'),
        ('archived', 'Archiviert'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loomtalk_topics',
        verbose_name='Autor'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='topics',
        verbose_name='Kategorie'
    )

    title = models.CharField(max_length=200, verbose_name='Titel')
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    content = models.TextField(verbose_name='Inhalt', max_length=10000)

    # Tags (optional)
    tags = models.ManyToManyField(Tag, blank=True, related_name='topics')

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='Status'
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    # Denormalisierte Stats fuer Performance
    replies_count = models.IntegerField(default=0, verbose_name='Antworten')
    views_count = models.IntegerField(default=0, verbose_name='Aufrufe')
    score = models.IntegerField(default=0, verbose_name='Score')  # net upvotes - downvotes

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(auto_now_add=True, verbose_name='Letzte Aktivitaet')

    class Meta:
        verbose_name = 'Thema'
        verbose_name_plural = 'Themen'
        ordering = ['-last_activity_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['category', '-last_activity_at']),
            models.Index(fields=['-score']),
            models.Index(fields=['status', 'is_active']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:200]
            unique_slug = base_slug
            counter = 1
            while Topic.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def increment_views(self):
        """Erhoeht View-Counter thread-safe"""
        Topic.objects.filter(pk=self.pk).update(views_count=models.F('views_count') + 1)

    def update_replies_count(self):
        """Aktualisiert Reply-Counter"""
        self.replies_count = self.replies.filter(is_active=True).count()
        self.save(update_fields=['replies_count'])


class Reply(models.Model):
    """Antworten auf Themen - verschachtelt moeglich"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name='Thema'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loomtalk_replies',
        verbose_name='Autor'
    )

    # Self-referential fuer verschachtelte Antworten
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Eltern-Antwort'
    )

    content = models.TextField(verbose_name='Inhalt', max_length=5000)

    # Stats
    score = models.IntegerField(default=0, verbose_name='Score')

    # Status
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    is_edited = models.BooleanField(default=False, verbose_name='Bearbeitet')
    is_solution = models.BooleanField(default=False, verbose_name='Als Loesung markiert')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Antwort'
        verbose_name_plural = 'Antworten'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['topic', 'created_at']),
            models.Index(fields=['parent']),
            models.Index(fields=['author', '-created_at']),
        ]

    def __str__(self):
        return f"Antwort von {self.author.username} auf {self.topic.title[:30]}"

    def get_depth(self):
        """Berechnet die Verschachtelungstiefe"""
        depth = 0
        parent = self.parent
        while parent and depth < 10:  # Max 10 Ebenen
            depth += 1
            parent = parent.parent
        return depth


class Vote(models.Model):
    """Upvote/Downvote System"""
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loomtalk_votes'
    )

    # Generische Verbindung zu Topic ODER Reply
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='votes'
    )
    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='votes'
    )

    vote_type = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stimme'
        verbose_name_plural = 'Stimmen'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'topic'],
                condition=models.Q(topic__isnull=False),
                name='unique_user_topic_vote'
            ),
            models.UniqueConstraint(
                fields=['user', 'reply'],
                condition=models.Q(reply__isnull=False),
                name='unique_user_reply_vote'
            ),
            models.CheckConstraint(
                check=models.Q(topic__isnull=False) | models.Q(reply__isnull=False),
                name='vote_must_have_target'
            ),
        ]

    def __str__(self):
        target = self.topic or self.reply
        vote_str = 'Upvote' if self.vote_type == 1 else 'Downvote'
        return f"{vote_str} von {self.user.username}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_vote_type = None

        if not is_new:
            try:
                old_instance = Vote.objects.get(pk=self.pk)
                old_vote_type = old_instance.vote_type
            except Vote.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Score aktualisieren
        target = self.topic or self.reply
        if target:
            if is_new:
                target.score = models.F('score') + self.vote_type
            elif old_vote_type != self.vote_type:
                # Vote geaendert
                target.score = models.F('score') - old_vote_type + self.vote_type
            target.save(update_fields=['score'])
            target.refresh_from_db()

    def delete(self, *args, **kwargs):
        target = self.topic or self.reply
        vote_type = self.vote_type
        super().delete(*args, **kwargs)

        if target:
            target.score = models.F('score') - vote_type
            target.save(update_fields=['score'])
            target.refresh_from_db()


class Mention(models.Model):
    """@username Mentions in Topics/Replies"""
    mentioned_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loomtalk_mentions',
        verbose_name='Erwaehnte Person'
    )
    mentioning_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loomtalk_mentions_made',
        verbose_name='Erwaehnende Person'
    )

    # Verbindung zu Topic ODER Reply
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='mentions'
    )
    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='mentions'
    )

    # Status
    is_read = models.BooleanField(default=False, verbose_name='Gelesen')
    notified_via_chat = models.BooleanField(default=False, verbose_name='Chat-Benachrichtigt')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Erwaehnung'
        verbose_name_plural = 'Erwaehnungen'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mentioned_user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"@{self.mentioned_user.username} von {self.mentioning_user.username}"

    def get_content_url(self):
        """Gibt die URL zum erwaehnten Content zurueck"""
        if self.topic:
            return f"/talk/thema/{self.topic.pk}/"
        elif self.reply:
            return f"/talk/thema/{self.reply.topic.pk}/#reply-{self.reply.pk}"
        return "/talk/"
