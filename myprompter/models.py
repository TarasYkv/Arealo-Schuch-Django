from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class PrompterText(models.Model):
    """Model for storing teleprompter texts"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='prompter_texts',
        verbose_name='Benutzer'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Titel',
        help_text='Bezeichnung für diesen Teleprompter-Text'
    )
    content = models.TextField(
        verbose_name='Text',
        help_text='Der Text für den Teleprompter'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erstellt am'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Aktualisiert am'
    )
    is_favorite = models.BooleanField(
        default=False,
        verbose_name='Favorit',
        help_text='Als Favorit markieren'
    )

    class Meta:
        verbose_name = 'Teleprompter-Text'
        verbose_name_plural = 'Teleprompter-Texte'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.user.username})"

    @property
    def word_count(self):
        """Count words in the content"""
        return len(self.content.split())
