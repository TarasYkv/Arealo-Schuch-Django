from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


class Collection(models.Model):
    """Gruppierung von Referenzen (z.B. 'Promotion', 'Workloom-Artikel', ...)"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="library_collections")
    name = models.CharField(max_length=200, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    zotero_key = models.CharField(max_length=32, blank=True,
                                  help_text="Zotero Collection Key (für API-Sync)")
    color = models.CharField(max_length=7, default="#0b3d60", help_text="Farbe (HEX) für UI")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("owner", "name")]
        verbose_name = "Sammlung"
        verbose_name_plural = "Sammlungen"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("library:collection_detail", args=[self.pk])

    @property
    def reference_count(self):
        return self.references.count()


class Reference(models.Model):
    """Ein einzelner Literaturverweis."""
    TYPE_CHOICES = [
        ("article", "Zeitschriftenartikel"),
        ("book", "Buch"),
        ("inproceedings", "Konferenzbeitrag"),
        ("thesis", "Abschlussarbeit"),
        ("report", "Report / Preprint"),
        ("misc", "Sonstiges"),
    ]

    STATUS_CHOICES = [
        ("unread", "Ungelesen"),
        ("reading", "Lesen"),
        ("read", "Gelesen"),
        ("cited", "Zitiert in Diss"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="library_references")
    collection = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="references")

    bibtex_key = models.CharField(max_length=100, db_index=True,
                                  help_text="Eindeutiger Citation-Key")
    zotero_key = models.CharField(max_length=32, blank=True, db_index=True,
                                  help_text="Zotero Item Key")

    entry_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="article")

    title = models.CharField(max_length=500)
    authors = models.CharField(max_length=500, blank=True,
                               help_text="Semikolon-getrennt")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    journal = models.CharField(max_length=300, blank=True)
    publisher = models.CharField(max_length=300, blank=True)
    volume = models.CharField(max_length=50, blank=True)
    issue = models.CharField(max_length=50, blank=True)
    pages = models.CharField(max_length=50, blank=True)
    doi = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=50, blank=True)
    url = models.URLField(max_length=500, blank=True)

    abstract = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text="Eigene Notizen")
    tags = models.CharField(max_length=500, blank=True,
                            help_text="Komma-getrennt")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unread")
    relevance = models.PositiveSmallIntegerField(default=3,
                                                 help_text="1-5 Sterne")

    raw_bibtex = models.TextField(blank=True, help_text="Original BibTeX-Eintrag")

    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced = models.DateTimeField(null=True, blank=True,
                                       help_text="Letzter Zotero-API-Sync")

    class Meta:
        ordering = ["-added_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "year"]),
        ]
        verbose_name = "Referenz"
        verbose_name_plural = "Referenzen"

    def __str__(self):
        return f"[{self.bibtex_key}] {self.title[:60]}"

    def get_absolute_url(self):
        return reverse("library:reference_detail", args=[self.pk])

    @property
    def authors_list(self):
        return [a.strip() for a in self.authors.split(";") if a.strip()]

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def doi_url(self):
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return None


class ModuleLink(models.Model):
    """Verknüpfung einer Referenz mit einem Lernmodul/Diss-Kapitel."""
    reference = models.ForeignKey(Reference, on_delete=models.CASCADE, related_name="module_links")
    module_code = models.CharField(max_length=50,
                                    help_text="z.B. 'M01' oder 'Diss-Kap-3'")
    module_title = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("reference", "module_code")]
        verbose_name = "Modul-Verknüpfung"
        verbose_name_plural = "Modul-Verknüpfungen"

    def __str__(self):
        return f"{self.reference.bibtex_key} → {self.module_code}"


class ZoteroAccount(models.Model):
    """Persönlicher Zotero-API-Zugang."""
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="library_zotero")
    user_id = models.CharField(max_length=32, verbose_name="Zotero User ID")
    api_key = models.CharField(max_length=64, verbose_name="Zotero API Key")
    library_type = models.CharField(
        max_length=10,
        choices=[("users", "Persönliche Bibliothek"), ("groups", "Gruppen-Bibliothek")],
        default="users",
    )
    group_id = models.CharField(max_length=32, blank=True,
                                help_text="Nur bei Gruppen-Bibliothek")
    last_sync = models.DateTimeField(null=True, blank=True)
    auto_sync = models.BooleanField(default=False,
                                    help_text="Automatische stündliche Synchronisation")

    class Meta:
        verbose_name = "Zotero-Zugang"
        verbose_name_plural = "Zotero-Zugänge"

    def __str__(self):
        return f"Zotero ({self.user_id}) für {self.owner}"
