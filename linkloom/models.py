from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

# Plattform-Choices für Social Icons (gleich wie in superconfig)
PLATFORM_CHOICES = [
    ('instagram', 'Instagram'),
    ('tiktok', 'TikTok'),
    ('youtube', 'YouTube'),
    ('facebook', 'Facebook'),
    ('twitter', 'X (Twitter)'),
    ('linkedin', 'LinkedIn'),
    ('pinterest', 'Pinterest'),
    ('snapchat', 'Snapchat'),
    ('twitch', 'Twitch'),
    ('discord', 'Discord'),
    ('telegram', 'Telegram'),
    ('whatsapp', 'WhatsApp'),
    ('spotify', 'Spotify'),
    ('github', 'GitHub'),
    ('website', 'Website'),
    ('email', 'E-Mail'),
]

# FontAwesome Icons für jede Plattform
FA_ICONS = {
    'instagram': 'fab fa-instagram',
    'tiktok': 'fab fa-tiktok',
    'youtube': 'fab fa-youtube',
    'facebook': 'fab fa-facebook',
    'twitter': 'fab fa-x-twitter',
    'linkedin': 'fab fa-linkedin',
    'pinterest': 'fab fa-pinterest',
    'snapchat': 'fab fa-snapchat',
    'twitch': 'fab fa-twitch',
    'discord': 'fab fa-discord',
    'telegram': 'fab fa-telegram',
    'whatsapp': 'fab fa-whatsapp',
    'spotify': 'fab fa-spotify',
    'github': 'fab fa-github',
    'website': 'fas fa-globe',
    'email': 'fas fa-envelope',
}

# Reservierte Slugs die nicht verwendet werden dürfen
RESERVED_SLUGS = [
    'admin', 'api', 'social', 'accounts', 'login', 'logout', 'register',
    'impressum', 'datenschutz', 'agb', 'help', 'support', 'contact',
    'about', 'workloom', 'linkloom', 'static', 'media', 'assets',
    'dashboard', 'settings', 'profile', 'user', 'users', 'new', 'edit',
    'delete', 'create', 'update', 'list', 'index', 'home', 'app', 'apps',
]


class LinkLoomPage(models.Model):
    """
    Hauptmodell - Eine Seite pro User.
    Jeder eingeloggte User kann eine eigene Link-Seite erstellen.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='linkloom_page',
        verbose_name='Benutzer'
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Nur Kleinbuchstaben, Zahlen und Bindestriche erlaubt'
            )
        ],
        verbose_name='URL-Slug',
        help_text='workloom.de/l/<slug>'
    )

    # Profil
    profile_picture = models.ImageField(
        upload_to='linkloom/profiles/',
        blank=True,
        null=True,
        verbose_name='Profilbild'
    )
    profile_description = models.TextField(
        blank=True,
        max_length=500,
        verbose_name='Beschreibung'
    )

    # Design
    background_color = models.CharField(
        max_length=7,
        default='#ffffff',
        verbose_name='Hintergrundfarbe'
    )
    button_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name='Button-Farbe'
    )
    button_text_color = models.CharField(
        max_length=7,
        default='#ffffff',
        verbose_name='Button-Textfarbe'
    )
    profile_text_color = models.CharField(
        max_length=7,
        default='#333333',
        verbose_name='Profil-Textfarbe'
    )

    # Footer / Impressum
    custom_impressum = models.TextField(
        blank=True,
        verbose_name='Eigenes Impressum',
        help_text='Dein individuelles Impressum für diese Seite'
    )
    show_affiliate_disclaimer = models.BooleanField(
        default=False,
        verbose_name='Affiliate-Hinweis anzeigen'
    )
    affiliate_disclaimer_text = models.TextField(
        blank=True,
        default='Diese Seite enthält Affiliate-Links. Bei einem Kauf erhalte ich eine kleine Provision.',
        verbose_name='Affiliate-Hinweis Text'
    )

    # Meta
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erstellt am'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Aktualisiert am'
    )

    class Meta:
        verbose_name = 'LinkLoom Seite'
        verbose_name_plural = 'LinkLoom Seiten'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.slug} ({self.user.username})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('linkloom_public', kwargs={'slug': self.slug})


class LinkLoomIcon(models.Model):
    """
    Social Media Icons für eine LinkLoom Seite.
    """
    page = models.ForeignKey(
        LinkLoomPage,
        on_delete=models.CASCADE,
        related_name='icons',
        verbose_name='Seite'
    )
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        verbose_name='Plattform'
    )
    url = models.URLField(
        verbose_name='URL'
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name='Sortierung'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv'
    )

    class Meta:
        verbose_name = 'Social Icon'
        verbose_name_plural = 'Social Icons'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.get_platform_display()} - {self.page.slug}"

    @property
    def fa_icon_class(self):
        """Gibt die FontAwesome Icon-Klasse zurück."""
        return FA_ICONS.get(self.platform, 'fas fa-link')


class LinkLoomButton(models.Model):
    """
    Klickbare Buttons/Links für eine LinkLoom Seite.
    """
    page = models.ForeignKey(
        LinkLoomPage,
        on_delete=models.CASCADE,
        related_name='buttons',
        verbose_name='Seite'
    )
    title = models.CharField(
        max_length=100,
        verbose_name='Titel'
    )
    url = models.URLField(
        verbose_name='URL'
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Beschreibung'
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name='Sortierung'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv'
    )
    click_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Klicks'
    )
    last_clicked = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Zuletzt geklickt'
    )

    class Meta:
        verbose_name = 'Button'
        verbose_name_plural = 'Buttons'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.title} - {self.page.slug}"


class LinkLoomClick(models.Model):
    """
    Click-Tracking für Buttons.
    IP-Adressen werden anonymisiert gespeichert (DSGVO).
    """
    button = models.ForeignKey(
        LinkLoomButton,
        on_delete=models.CASCADE,
        related_name='clicks',
        verbose_name='Button'
    )
    clicked_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Geklickt am'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP-Adresse (anonymisiert)'
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='User Agent'
    )
    referer = models.URLField(
        blank=True,
        verbose_name='Referer'
    )

    class Meta:
        verbose_name = 'Klick'
        verbose_name_plural = 'Klicks'
        ordering = ['-clicked_at']

    def __str__(self):
        return f"Klick auf {self.button.title} am {self.clicked_at}"
