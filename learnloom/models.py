from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class PDFBook(models.Model):
    """Hochgeladene PDF-Bücher/Paper"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='learnloom_books',
        verbose_name='Benutzer'
    )

    title = models.CharField(max_length=255, verbose_name="Titel")
    original_filename = models.CharField(max_length=255, verbose_name="Original-Dateiname")
    file = models.FileField(upload_to='learnloom/pdfs/', verbose_name="PDF-Datei")
    thumbnail = models.ImageField(
        upload_to='learnloom/thumbnails/',
        blank=True,
        null=True,
        verbose_name="Vorschaubild"
    )

    file_size = models.BigIntegerField(default=0, verbose_name="Dateigröße (Bytes)")
    page_count = models.PositiveIntegerField(default=0, verbose_name="Seitenanzahl")

    CATEGORY_CHOICES = [
        ('book', 'Buch'),
        ('paper', 'Wissenschaftliches Paper'),
        ('article', 'Artikel'),
        ('other', 'Sonstiges'),
    ]
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='book',
        verbose_name="Kategorie"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Tags",
        help_text="Kommagetrennte Tags"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    last_opened_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Zuletzt geöffnet"
    )

    class Meta:
        ordering = ['-last_opened_at', '-created_at']
        verbose_name = "PDF-Buch"
        verbose_name_plural = "PDF-Bücher"
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'category']),
        ]

    def __str__(self):
        return f"{self.title} ({self.user.username})"

    def get_file_size_mb(self):
        """Gibt Dateigröße in MB zurück"""
        return self.file_size / (1024 * 1024)


class PDFNote(models.Model):
    """Notizen zu einem PDF"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        PDFBook,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name="PDF-Buch"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Benutzer"
    )

    content = models.TextField(verbose_name="Notizinhalt")
    page_reference = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Seitenbezug",
        help_text="Optional: Bezug zu einer bestimmten Seite"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Notiz"
        verbose_name_plural = "Notizen"

    def __str__(self):
        return f"Notiz zu {self.book.title[:30]}..."


class TranslationHighlight(models.Model):
    """Markierte und übersetzte Wörter/Phrasen"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        PDFBook,
        on_delete=models.CASCADE,
        related_name='highlights',
        verbose_name="PDF-Buch"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Benutzer"
    )

    original_text = models.CharField(max_length=500, verbose_name="Originaltext (EN)")
    translated_text = models.CharField(max_length=500, verbose_name="Übersetzung (DE)")

    page_number = models.PositiveIntegerField(verbose_name="Seitennummer")
    position_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Positionsdaten",
        help_text="JSON mit Positionsdaten für die Markierung im PDF"
    )

    source_language = models.CharField(max_length=10, default='en', verbose_name="Quellsprache")
    target_language = models.CharField(max_length=10, default='de', verbose_name="Zielsprache")

    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
    ]
    translation_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='openai',
        verbose_name="Übersetzungs-Provider"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        ordering = ['page_number', 'created_at']
        verbose_name = "Übersetzungs-Markierung"
        verbose_name_plural = "Übersetzungs-Markierungen"
        indexes = [
            models.Index(fields=['book', 'page_number']),
        ]

    def __str__(self):
        return f"'{self.original_text[:20]}...' → '{self.translated_text[:20]}...'"


class Vocabulary(models.Model):
    """Vokabelliste pro PDF"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        PDFBook,
        on_delete=models.CASCADE,
        related_name='vocabulary',
        verbose_name="PDF-Buch"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Benutzer"
    )

    english_word = models.CharField(max_length=255, verbose_name="Englisch")
    german_translation = models.CharField(max_length=255, verbose_name="Deutsch")

    times_reviewed = models.PositiveIntegerField(default=0, verbose_name="Wiederholungen")
    last_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Zuletzt wiederholt"
    )
    is_learned = models.BooleanField(default=False, verbose_name="Gelernt")

    from_highlight = models.ForeignKey(
        TranslationHighlight,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vocabulary_entries',
        verbose_name="Aus Markierung"
    )
    page_reference = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Seitenbezug"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        ordering = ['-created_at']
        unique_together = ['book', 'english_word']
        verbose_name = "Vokabel"
        verbose_name_plural = "Vokabeln"

    def __str__(self):
        return f"{self.english_word} → {self.german_translation}"


class ReadingProgress(models.Model):
    """Lesefortschritt pro PDF"""
    book = models.OneToOneField(
        PDFBook,
        on_delete=models.CASCADE,
        related_name='progress',
        verbose_name="PDF-Buch"
    )
    current_page = models.PositiveIntegerField(default=1, verbose_name="Aktuelle Seite")
    last_scroll_position = models.FloatField(
        default=0,
        verbose_name="Scroll-Position",
        help_text="Scroll-Position in Prozent (0-100)"
    )
    zoom_level = models.FloatField(default=1.0, verbose_name="Zoom-Stufe")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "Lesefortschritt"
        verbose_name_plural = "Lesefortschritte"

    def __str__(self):
        return f"{self.book.title}: Seite {self.current_page}"
