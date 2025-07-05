from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import CustomUser, AmpelCategory, CategoryKeyword


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})


class ApiKeyForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['openai_api_key', 'anthropic_api_key']
        widgets = {
            'openai_api_key': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ihr OpenAI API Key'}),
            'anthropic_api_key': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ihr Anthropic API Key'}),
        }


class AmpelCategoryForm(forms.ModelForm):
    class Meta:
        model = AmpelCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CategoryKeywordForm(forms.ModelForm):
    class Meta:
        model = CategoryKeyword
        fields = ['keyword', 'weight']
        widgets = {
            'keyword': forms.TextInput(attrs={'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
        }


class KeywordBulkForm(forms.Form):
    keywords = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Geben Sie Suchbegriffe ein, getrennt durch Kommas oder neue Zeilen...'
        }),
        help_text="Mehrere Begriffe können durch Kommas oder neue Zeilen getrennt werden."
    )