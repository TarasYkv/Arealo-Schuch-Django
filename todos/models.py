from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


class TodoList(models.Model):
    """ToDo-Liste die von mehreren Benutzern geteilt werden kann"""
    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_todo_lists', verbose_name="Erstellt von")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    
    # Benutzer die Zugriff auf diese Liste haben
    shared_with = models.ManyToManyField(User, blank=True, related_name='shared_todo_lists', verbose_name="Geteilt mit")
    
    # Sichtbarkeitseinstellungen
    is_public = models.BooleanField(default=False, verbose_name="Öffentlich sichtbar")
    
    class Meta:
        verbose_name = "ToDo-Liste"
        verbose_name_plural = "ToDo-Listen"
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('todos:list_detail', kwargs={'pk': self.pk})
    
    def get_all_users(self):
        """Gibt alle Benutzer zurück die Zugriff auf diese Liste haben"""
        users = set([self.created_by])
        users.update(self.shared_with.all())
        return list(users)
    
    def can_user_access(self, user):
        """Prüft ob ein Benutzer Zugriff auf diese Liste hat"""
        if not user.is_authenticated:
            return self.is_public
        return (
            user == self.created_by or 
            user in self.shared_with.all() or 
            self.is_public
        )
    
    def can_user_edit(self, user):
        """Prüft ob ein Benutzer diese Liste bearbeiten kann"""
        if not user.is_authenticated:
            return False
        return user == self.created_by or user in self.shared_with.all()
    
    def get_progress(self):
        """Berechnet den Fortschritt der Liste in Prozent"""
        total_todos = self.todos.count()
        if total_todos == 0:
            return 100
        completed_todos = self.todos.filter(status='completed').count()
        return int((completed_todos / total_todos) * 100)


class Todo(models.Model):
    """Einzelne ToDo-Aufgabe"""
    STATUS_CHOICES = [
        ('pending', 'Steht aus'),
        ('in_progress', 'In Bearbeitung'),
        ('completed', 'Erledigt'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Niedrig'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
        ('urgent', 'Dringend'),
    ]
    
    todo_list = models.ForeignKey(TodoList, on_delete=models.CASCADE, related_name='todos', verbose_name="Liste")
    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Priorität")
    
    # Benutzer-Zuordnung
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_todos', verbose_name="Erstellt von")
    assigned_to = models.ManyToManyField(
        User, 
        blank=True, 
        through='TodoAssignment',
        through_fields=('todo', 'user'),
        related_name='assigned_todos', 
        verbose_name="Zugeordnet an"
    )
    
    # Zeitstempel
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    due_date = models.DateTimeField(null=True, blank=True, verbose_name="Fälligkeitsdatum")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Erledigt am")
    
    class Meta:
        verbose_name = "ToDo"
        verbose_name_plural = "ToDos"
        ordering = ['-priority', 'due_date', '-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def get_absolute_url(self):
        return reverse('todos:todo_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        # Setze completed_at wenn Status auf 'completed' geändert wird
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'completed':
            self.completed_at = None
        super().save(*args, **kwargs)
    
    def is_overdue(self):
        """Prüft ob das ToDo überfällig ist"""
        if not self.due_date or self.status == 'completed':
            return False
        return timezone.now() > self.due_date
    
    def get_assigned_users_display(self):
        """Gibt eine lesbare Liste der zugeordneten Benutzer zurück"""
        assignments = self.assignments.select_related('user')
        if not assignments:
            return "Niemand zugeordnet"
        return ", ".join([a.user.get_full_name() or a.user.username for a in assignments])
    
    def get_priority_color(self):
        """Gibt eine CSS-Klasse für die Prioritätsfarbe zurück"""
        colors = {
            'low': 'text-secondary',
            'medium': 'text-primary',
            'high': 'text-warning',
            'urgent': 'text-danger',
        }
        return colors.get(self.priority, 'text-secondary')
    
    def get_status_color(self):
        """Gibt eine CSS-Klasse für die Statusfarbe zurück"""
        colors = {
            'pending': 'text-muted',
            'in_progress': 'text-warning',
            'completed': 'text-success',
        }
        return colors.get(self.status, 'text-muted')


class TodoAssignment(models.Model):
    """Zuordnung eines ToDos zu einem Benutzer mit zusätzlichen Informationen"""
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE, related_name='assignments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_todos_by')
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="Zugeordnet am")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    
    # Status für den spezifischen Benutzer
    user_status = models.CharField(
        max_length=20, 
        choices=Todo.STATUS_CHOICES, 
        default='pending',
        verbose_name="Benutzerstatus"
    )
    
    class Meta:
        unique_together = ['todo', 'user']
        verbose_name = "ToDo-Zuordnung"
        verbose_name_plural = "ToDo-Zuordnungen"
    
    def __str__(self):
        return f"{self.todo.title} → {self.user.get_full_name() or self.user.username}"


class TodoComment(models.Model):
    """Kommentare zu ToDos"""
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_comments')
    content = models.TextField(verbose_name="Kommentar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    
    class Meta:
        verbose_name = "ToDo-Kommentar"
        verbose_name_plural = "ToDo-Kommentare"
        ordering = ['created_at']
    
    def __str__(self):
        return f"Kommentar von {self.user.get_full_name() or self.user.username} zu {self.todo.title}"


class TodoActivity(models.Model):
    """Aktivitätsprotokoll für ToDos"""
    ACTIVITY_TYPES = [
        ('created', 'Erstellt'),
        ('updated', 'Aktualisiert'),
        ('status_changed', 'Status geändert'),
        ('assigned', 'Zugeordnet'),
        ('unassigned', 'Zuordnung entfernt'),
        ('commented', 'Kommentiert'),
        ('due_date_set', 'Fälligkeitsdatum gesetzt'),
        ('due_date_changed', 'Fälligkeitsdatum geändert'),
    ]
    
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(verbose_name="Beschreibung")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    
    # Zusätzliche Daten als JSON
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "ToDo-Aktivität"
        verbose_name_plural = "ToDo-Aktivitäten"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} {self.get_activity_type_display()}: {self.todo.title}"