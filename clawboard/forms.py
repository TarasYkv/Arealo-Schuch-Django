from django import forms
from .models import ClawdbotConnection, Project


class ClawdbotConnectionForm(forms.ModelForm):
    """Form für Clawdbot-Verbindung"""
    
    class Meta:
        model = ClawdbotConnection
        fields = ['name', 'gateway_url', 'gateway_token', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Mein Laptop, Server, etc.'
            }),
            'gateway_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'ws://localhost:18789 oder wss://...'
            }),
            'gateway_token': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gateway Token aus clawdbot.json'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'gateway_url': 'WebSocket URL deines Clawdbot Gateway (aus clawdbot.json)',
            'gateway_token': 'Das gatewayToken aus deiner clawdbot.json Konfiguration',
        }


class ProjectForm(forms.ModelForm):
    """Form für Projekte"""
    
    class Meta:
        model = Project
        fields = ['connection', 'name', 'description', 'status', 'priority', 'color', 'icon', 'memory_path']
        widgets = {
            'connection': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Projektname'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Kurze Beschreibung des Projekts'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '🚀 oder bi-rocket'
            }),
            'memory_path': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'memory/projekt-name.md'
            }),
        }
