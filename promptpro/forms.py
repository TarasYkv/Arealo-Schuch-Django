from django import forms
from .models import Prompt, Category


class PromptForm(forms.ModelForm):
    class Meta:
        model = Prompt
        fields = ["title", "description", "content", "category", "visibility"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Titel"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Kurze Beschreibung"}),
            "content": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 6, "placeholder": "Dein KI-Prompt"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "visibility": forms.Select(attrs={"class": "form-select"}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Kategoriename"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Beschreibung (optional)"}),
        }

