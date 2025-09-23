"""
LoomLine Forms - Einfache Formulare für Projekt Timeline
"""

from django import forms
from django.contrib.auth import get_user_model
from .models import Project, TaskEntry

User = get_user_model()


class ProjectForm(forms.ModelForm):
    """Formular für Projekt erstellen/bearbeiten"""

    class Meta:
        model = Project
        fields = ['name', 'description', 'domain']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Website Relaunch'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Kurze Beschreibung des Projekts...'
            }),
            'domain': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. example.com (optional)'
            }),
        }


class TaskEntryForm(forms.ModelForm):
    """Formular für erledigte Aufgabe hinzufügen"""

    class Meta:
        model = TaskEntry
        fields = ['title', 'description', 'completed_at']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Was wurde erledigt?',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Zusätzliche Details (optional)...'
            }),
            'completed_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Completed_at ist optional - wenn leer, wird timezone.now() verwendet
        self.fields['completed_at'].required = False


class QuickTaskEntryForm(forms.ModelForm):
    """Formular für schnelles Aufgabe eintragen mit Projektauswahl"""

    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        empty_label="Projekt auswählen...",
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label="Projekt"
    )

    class Meta:
        model = TaskEntry
        fields = ['project', 'title', 'description', 'completed_at']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Header-Design überarbeitet',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Was genau wurde gemacht? (optional)...'
            }),
            'completed_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['project'].queryset = Project.objects.filter(
                owner=user, is_active=True
            ).order_by('name')

        # Completed_at ist optional
        self.fields['completed_at'].required = False


class ProjectMembersForm(forms.ModelForm):
    """Formular für Projekt-Mitglieder verwalten"""

    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Mitglieder hinzufügen",
        help_text="Wählen Sie Nutzer aus, die an diesem Projekt mitarbeiten sollen"
    )

    class Meta:
        model = Project
        fields = ['members']

    def __init__(self, project_owner=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if project_owner:
            # Owner ausschließen (kann sich nicht selbst als Member hinzufügen)
            self.fields['members'].queryset = User.objects.exclude(id=project_owner.id).order_by('username')


class AddMemberForm(forms.Form):
    """Einfaches Formular um einen Nutzer per Username hinzuzufügen"""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Benutzername eingeben...'
        }),
        label="Benutzername",
        help_text="Geben Sie den Benutzernamen des Nutzers ein, den Sie einladen möchten"
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            user = User.objects.get(username=username)
            return user
        except User.DoesNotExist:
            raise forms.ValidationError(f'Benutzer "{username}" wurde nicht gefunden.')

    def get_user(self):
        """Gibt den gefundenen Benutzer zurück"""
        if self.is_valid():
            return self.cleaned_data['username']
        return None