from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
import os

User = get_user_model()


class PDFDocument(models.Model):
    """Hochgeladene PDF-Dokumente"""
    title = models.CharField(max_length=255, help_text="Titel des Dokuments")
    original_filename = models.CharField(max_length=255, help_text="Originalname der Datei")
    file = models.FileField(upload_to='pdfs/', help_text="PDF-Datei")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pdf_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField(help_text="Dateigröße in Bytes")
    
    class Meta:
        verbose_name = "PDF Dokument"
        verbose_name_plural = "PDF Dokumente"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('pdf_sucher:document_detail', kwargs={'pk': self.pk})
    
    @property
    def file_size_mb(self):
        """Dateigröße in MB"""
        return round(self.file_size / (1024 * 1024), 2)


class PDFSummary(models.Model):
    """Zusammenfassungen von PDF-Dokumenten"""
    AI_MODEL_CHOICES = [
        ('openai_gpt4', 'OpenAI GPT-4'),
        ('openai_gpt35', 'OpenAI GPT-3.5'),
        ('google_gemini', 'Google Gemini'),
        ('anthropic_claude', 'Anthropic Claude'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('processing', 'In Bearbeitung'),
        ('completed', 'Abgeschlossen'),
        ('error', 'Fehler'),
    ]
    
    document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='summaries')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ai_model = models.CharField(max_length=20, choices=AI_MODEL_CHOICES, help_text="Verwendetes KI-Modell")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Analyseergebnisse
    extracted_text = models.TextField(blank=True, help_text="Extrahierter Text aus der PDF")
    summary_text = models.TextField(blank=True, help_text="Zusammenfassung des Dokuments")
    structured_data = models.JSONField(default=dict, blank=True, help_text="Strukturierte Daten (Positionen, etc.)")
    
    # Zusammenfassungs-PDF
    summary_pdf = models.FileField(upload_to='pdf_summaries/', blank=True, null=True, 
                                   help_text="Generierte Zusammenfassungs-PDF")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, help_text="Fehlermeldung bei Problemen")
    processing_time = models.FloatField(null=True, blank=True, help_text="Verarbeitungszeit in Sekunden")
    
    class Meta:
        verbose_name = "PDF Zusammenfassung"
        verbose_name_plural = "PDF Zusammenfassungen"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Zusammenfassung: {self.document.title} ({self.get_ai_model_display()})"
    
    def get_absolute_url(self):
        return reverse('pdf_sucher:summary_detail', kwargs={'pk': self.pk})


class TenderPosition(models.Model):
    """Einzelne Position einer Ausschreibung"""
    summary = models.ForeignKey(PDFSummary, on_delete=models.CASCADE, related_name='positions')
    position_number = models.CharField(max_length=50, help_text="Positionsnummer")
    title = models.CharField(max_length=500, help_text="Titel/Beschreibung der Position")
    description = models.TextField(blank=True, help_text="Detaillierte Beschreibung")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                   help_text="Menge/Anzahl")
    unit = models.CharField(max_length=50, blank=True, help_text="Einheit (Stk, m², kg, etc.)")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                     help_text="Einzelpreis")
    total_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, 
                                      help_text="Gesamtpreis")
    category = models.CharField(max_length=200, blank=True, help_text="Kategorie/Gewerk")
    page_reference = models.IntegerField(null=True, blank=True, help_text="Seitenverweis im Original")
    
    class Meta:
        verbose_name = "Ausschreibungsposition"
        verbose_name_plural = "Ausschreibungspositionen"
        ordering = ['position_number']
    
    def __str__(self):
        return f"Pos. {self.position_number}: {self.title[:50]}"
