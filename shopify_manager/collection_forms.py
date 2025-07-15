from django import forms
from .models import ShopifyCollection, CollectionSEOOptimization


class CollectionFilterForm(forms.Form):
    """Filter-Form für Shopify Kategorien"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Suche nach Titel, Handle oder Beschreibung...',
            'autocomplete': 'off'
        })
    )
    
    published = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Alle Kategorien'),
            ('true', 'Nur veröffentlichte'),
            ('false', 'Nur unveröffentlichte'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        })
    )
    
    sync_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Alle Sync-Status'),
            ('synced', 'Synchronisiert'),
            ('needs_sync', 'Sync erforderlich'),
            ('sync_error', 'Sync-Fehler'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        })
    )
    
    seo_score = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Alle SEO-Status'),
            ('good', 'Gut ✅'),
            ('warning', 'Warnung ⚠️'),
            ('poor', 'Schlecht ❌'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        })
    )
    
    seo_issues_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('-updated_at', 'Zuletzt aktualisiert'),
            ('title', 'Titel A-Z'),
            ('-title', 'Titel Z-A'),
            ('created_at', 'Erstellungsdatum (alt zuerst)'),
            ('-created_at', 'Erstellungsdatum (neu zuerst)'),
            ('seo_score', 'SEO-Score (schlechteste zuerst)'),
            ('-seo_score', 'SEO-Score (beste zuerst)'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        })
    )


class CollectionSEOOptimizationForm(forms.ModelForm):
    """Form für KI-gestützte SEO-Optimierung von Kategorien"""
    
    class Meta:
        model = CollectionSEOOptimization
        fields = ['keywords', 'ai_model']
        widgets = {
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'natürlich, bio, nachhaltig, gesund, qualität',
                'data-bs-toggle': 'tooltip',
                'title': 'Kommagetrennte Keywords für SEO-Optimierung'
            }),
            'ai_model': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.collection = kwargs.pop('collection', None)
        super().__init__(*args, **kwargs)
        
        # Initialisiere Keywords basierend auf Kategorien-Daten
        if self.collection and not self.instance.pk:
            suggested_keywords = self._generate_suggested_keywords()
            if suggested_keywords:
                self.fields['keywords'].widget.attrs['placeholder'] = suggested_keywords
    
    def _generate_suggested_keywords(self):
        """Generiert Keyword-Vorschläge basierend auf Kategorien-Daten"""
        if not self.collection:
            return ""
        
        keywords = []
        
        # Aus Titel extrahieren
        title_words = [word.lower().strip('.,!?"-()') for word in self.collection.title.split() 
                      if len(word.strip('.,!?"-()')) > 3]
        keywords.extend(title_words[:3])  # Top 3 längste Wörter
        
        # Aus Beschreibung extrahieren
        if self.collection.description:
            desc_words = [word.lower().strip('.,!?"-()') for word in self.collection.description.split() 
                         if len(word.strip('.,!?"-()')) > 4]
            keywords.extend(desc_words[:2])  # Top 2 Wörter aus Beschreibung
        
        # Aus Handle extrahieren (oft relevante Keywords)
        if self.collection.handle:
            handle_words = [word.lower() for word in self.collection.handle.replace('-', ' ').split() 
                           if len(word) > 3]
            keywords.extend(handle_words[:2])  # Top 2 Handle-Wörter
        
        return ', '.join(list(dict.fromkeys(keywords))[:5])  # Duplikate entfernen, max 5
    
    def save(self, commit=True):
        seo_optimization = super().save(commit=False)
        
        if self.collection:
            seo_optimization.collection = self.collection
            # Speichere Original-Daten
            seo_optimization.original_title = self.collection.title
            seo_optimization.original_description = self.collection.description or ''
            seo_optimization.original_seo_title = self.collection.seo_title or ''
            seo_optimization.original_seo_description = self.collection.seo_description or ''
        
        if commit:
            seo_optimization.save()
        
        return seo_optimization