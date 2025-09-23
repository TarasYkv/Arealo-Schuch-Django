"""
LoomLine - Einfache Projekt Timeline
Vereinfachtes Modell für Projekt-Feed mit erledigten Aufgaben
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Project(models.Model):
    """Einfaches Projekt"""

    name = models.CharField(
        max_length=200,
        verbose_name="Projektname",
        help_text="Name des Projekts"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
        help_text="Kurze Projektbeschreibung"
    )

    domain = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Website/URL",
        help_text="Website oder relevante URL (optional)"
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='projects',
        verbose_name="Ersteller"
    )

    members = models.ManyToManyField(
        User,
        blank=True,
        related_name='project_memberships',
        verbose_name="Mitglieder",
        help_text="Andere Nutzer, die an diesem Projekt mitarbeiten können"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv"
    )

    def __str__(self):
        return self.name

    def can_access(self, user):
        """Prüft ob ein Nutzer Zugriff auf das Projekt hat"""
        return user == self.owner or user in self.members.all()

    def can_edit(self, user):
        """Prüft ob ein Nutzer das Projekt bearbeiten darf (nur Owner)"""
        return user == self.owner

    def get_all_users(self):
        """Gibt alle Nutzer zurück (Owner + Members)"""
        users = [self.owner]
        users.extend(self.members.all())
        return users

    class Meta:
        verbose_name = "Projekt"
        verbose_name_plural = "Projekte"
        ordering = ['-created_at']


class TaskEntry(models.Model):
    """Einfache erledigte Aufgabe für Timeline/Feed"""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name="Projekt"
    )

    title = models.CharField(
        max_length=200,
        verbose_name="Aufgabe",
        help_text="Was wurde erledigt?"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Details",
        help_text="Zusätzliche Beschreibung (optional)"
    )

    completed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Erledigt von",
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Erledigt am"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Eingetragen am"
    )

    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks',
        verbose_name="Übergeordnete Aufgabe",
        help_text="Verweis auf die Hauptaufgabe (bei Sub-Aufgaben)"
    )

    def __str__(self):
        return f"{self.title} - {self.project.name}"

    def is_subtask(self):
        """Prüft ob dies eine Sub-Aufgabe ist"""
        return self.parent_task is not None

    def is_main_task(self):
        """Prüft ob dies eine Hauptaufgabe ist"""
        return self.parent_task is None

    def get_subtask_count(self):
        """Anzahl der Sub-Aufgaben"""
        return self.subtasks.count()

    class Meta:
        verbose_name = "Erledigte Aufgabe"
        verbose_name_plural = "Erledigte Aufgaben"
        ordering = ['-completed_at']