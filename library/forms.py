from django import forms
from .models import Reference, Collection, ZoteroAccount


class ReferenceForm(forms.ModelForm):
    class Meta:
        model = Reference
        fields = [
            "collection", "bibtex_key", "entry_type",
            "title", "authors", "year",
            "journal", "publisher", "volume", "issue", "pages",
            "doi", "isbn", "url",
            "abstract", "notes", "tags",
            "status", "relevance", "raw_bibtex",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "authors": forms.TextInput(attrs={"class": "form-control",
                                              "placeholder": "Nachname, Vorname; Nachname, Vorname"}),
            "year": forms.NumberInput(attrs={"class": "form-control"}),
            "journal": forms.TextInput(attrs={"class": "form-control"}),
            "publisher": forms.TextInput(attrs={"class": "form-control"}),
            "volume": forms.TextInput(attrs={"class": "form-control"}),
            "issue": forms.TextInput(attrs={"class": "form-control"}),
            "pages": forms.TextInput(attrs={"class": "form-control"}),
            "doi": forms.TextInput(attrs={"class": "form-control", "placeholder": "10.xxxx/..."}),
            "isbn": forms.TextInput(attrs={"class": "form-control"}),
            "url": forms.URLInput(attrs={"class": "form-control"}),
            "abstract": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "tags": forms.TextInput(attrs={"class": "form-control",
                                           "placeholder": "Tag1, Tag2, ..."}),
            "bibtex_key": forms.TextInput(attrs={"class": "form-control"}),
            "entry_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "relevance": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 5}),
            "collection": forms.Select(attrs={"class": "form-select"}),
            "raw_bibtex": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 6}),
        }


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ["name", "description", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "color": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
        }


class ZoteroAccountForm(forms.ModelForm):
    class Meta:
        model = ZoteroAccount
        fields = ["user_id", "api_key", "library_type", "group_id", "auto_sync"]
        widgets = {
            "user_id": forms.TextInput(attrs={"class": "form-control"}),
            "api_key": forms.TextInput(attrs={"class": "form-control"}),
            "library_type": forms.Select(attrs={"class": "form-select"}),
            "group_id": forms.TextInput(attrs={"class": "form-control"}),
        }


class BibTexImportForm(forms.Form):
    file = forms.FileField(required=False, label="BibTeX-Datei",
                           widget=forms.ClearableFileInput(attrs={"class": "form-control"}))
    text = forms.CharField(required=False, label="Oder BibTeX einfügen",
                           widget=forms.Textarea(attrs={"class": "form-control font-monospace",
                                                        "rows": 10}))
    collection = forms.ModelChoiceField(queryset=Collection.objects.none(), required=False,
                                        label="Sammlung (optional)",
                                        widget=forms.Select(attrs={"class": "form-select"}))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("file") and not cleaned.get("text"):
            raise forms.ValidationError("Bitte entweder Datei oder Text angeben.")
        return cleaned
