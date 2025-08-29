from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        super().save(*args, **kwargs)


class Prompt(models.Model):
    VISIBILITY_CHOICES = [
        ("private", "Privat"),
        ("public", "Öffentlich"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="prompts")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.TextField(help_text="Speichere hier deinen KI-Prompt")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="prompts")
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="private")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Prompt"
        verbose_name_plural = "Prompts"

    def __str__(self):
        return f"{self.title}"

