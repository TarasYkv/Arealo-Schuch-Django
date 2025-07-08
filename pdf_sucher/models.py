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
        # OpenAI Models
        ('openai_gpt4o', 'OpenAI GPT-4o (128k Token, $2.50/$10.00 pro 1M Token)'),
        ('openai_gpt4o_mini', 'OpenAI GPT-4o Mini (128k Token, $0.15/$0.60 pro 1M Token)'),
        ('openai_gpt4_turbo', 'OpenAI GPT-4 Turbo (128k Token, $10.00/$30.00 pro 1M Token)'),
        ('openai_gpt4', 'OpenAI GPT-4 (8k Token, $30.00/$60.00 pro 1M Token)'),
        ('openai_gpt35_turbo', 'OpenAI GPT-3.5 Turbo (16k Token, $0.50/$1.50 pro 1M Token)'),
        
        # Google Models
        ('google_gemini_pro', 'Google Gemini Pro (1M Token, $0.50/$1.50 pro 1M Token)'),
        ('google_gemini_flash', 'Google Gemini Flash (1M Token, $0.075/$0.30 pro 1M Token)'),
        
        # Anthropic Models
        ('anthropic_claude_opus', 'Anthropic Claude-3 Opus (200k Token, $15.00/$75.00 pro 1M Token)'),
        ('anthropic_claude_sonnet', 'Anthropic Claude-3.5 Sonnet (200k Token, $3.00/$15.00 pro 1M Token)'),
        ('anthropic_claude_haiku', 'Anthropic Claude-3 Haiku (200k Token, $0.25/$1.25 pro 1M Token)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('processing', 'In Bearbeitung'),
        ('completed', 'Abgeschlossen'),
        ('error', 'Fehler'),
    ]
    
    document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='summaries')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ai_model = models.CharField(max_length=30, choices=AI_MODEL_CHOICES, help_text="Verwendetes KI-Modell")
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
    
    @classmethod
    def get_model_info(cls):
        """Gibt detaillierte Informationen zu allen AI-Modellen zurück"""
        return {
            # OpenAI Models
            'openai_gpt4o': {
                'name': 'GPT-4o',
                'provider': 'OpenAI',
                'context_length': 128000,
                'input_price_per_1m': 2.50,
                'output_price_per_1m': 10.00,
                'speed': 'Mittel',
                'quality': 'Sehr hoch',
                'description': 'Neuestes multimodales Modell von OpenAI'
            },
            'openai_gpt4o_mini': {
                'name': 'GPT-4o Mini',
                'provider': 'OpenAI',
                'context_length': 128000,
                'input_price_per_1m': 0.15,
                'output_price_per_1m': 0.60,
                'speed': 'Schnell',
                'quality': 'Hoch',
                'description': 'Kosteneffiziente Version von GPT-4o'
            },
            'openai_gpt4_turbo': {
                'name': 'GPT-4 Turbo',
                'provider': 'OpenAI',
                'context_length': 128000,
                'input_price_per_1m': 10.00,
                'output_price_per_1m': 30.00,
                'speed': 'Mittel',
                'quality': 'Sehr hoch',
                'description': 'Erweiterte Version von GPT-4 mit größerem Kontext'
            },
            'openai_gpt4': {
                'name': 'GPT-4',
                'provider': 'OpenAI',
                'context_length': 8192,
                'input_price_per_1m': 30.00,
                'output_price_per_1m': 60.00,
                'speed': 'Langsam',
                'quality': 'Sehr hoch',
                'description': 'Original GPT-4 Modell (legacy)'
            },
            'openai_gpt35_turbo': {
                'name': 'GPT-3.5 Turbo',
                'provider': 'OpenAI',
                'context_length': 16385,
                'input_price_per_1m': 0.50,
                'output_price_per_1m': 1.50,
                'speed': 'Sehr schnell',
                'quality': 'Gut',
                'description': 'Schnelles und kostengünstiges Modell'
            },
            
            # Google Models
            'google_gemini_pro': {
                'name': 'Gemini Pro',
                'provider': 'Google',
                'context_length': 1048576,
                'input_price_per_1m': 0.50,
                'output_price_per_1m': 1.50,
                'speed': 'Schnell',
                'quality': 'Hoch',
                'description': 'Googles fortschrittliches Sprachmodell'
            },
            'google_gemini_flash': {
                'name': 'Gemini Flash',
                'provider': 'Google',
                'context_length': 1048576,
                'input_price_per_1m': 0.075,
                'output_price_per_1m': 0.30,
                'speed': 'Sehr schnell',
                'quality': 'Gut',
                'description': 'Schnellste und kostengünstigste Gemini-Variante'
            },
            
            # Anthropic Models
            'anthropic_claude_opus': {
                'name': 'Claude-3 Opus',
                'provider': 'Anthropic',
                'context_length': 200000,
                'input_price_per_1m': 15.00,
                'output_price_per_1m': 75.00,
                'speed': 'Langsam',
                'quality': 'Sehr hoch',
                'description': 'Anthropics stärkstes Modell für komplexe Aufgaben'
            },
            'anthropic_claude_sonnet': {
                'name': 'Claude-3.5 Sonnet',
                'provider': 'Anthropic',
                'context_length': 200000,
                'input_price_per_1m': 3.00,
                'output_price_per_1m': 15.00,
                'speed': 'Mittel',
                'quality': 'Sehr hoch',
                'description': 'Ausgewogenes Verhältnis von Leistung und Kosten'
            },
            'anthropic_claude_haiku': {
                'name': 'Claude-3 Haiku',
                'provider': 'Anthropic',
                'context_length': 200000,
                'input_price_per_1m': 0.25,
                'output_price_per_1m': 1.25,
                'speed': 'Sehr schnell',
                'quality': 'Gut',
                'description': 'Schnellstes Claude-Modell für einfache Aufgaben'
            }
        }


class TenderPosition(models.Model):
    """Einzelne Position einer Ausschreibung"""
    summary = models.ForeignKey(PDFSummary, on_delete=models.CASCADE, related_name='positions')
    position_number = models.CharField(max_length=50, help_text="Positionsnummer")
    title = models.CharField(max_length=500, help_text="Titel/Beschreibung der Position")
    description = models.TextField(blank=True, help_text="Detaillierte Beschreibung")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                   help_text="Menge/Anzahl")
    unit = models.CharField(max_length=50, blank=True, null=True, default='', help_text="Einheit (Stk, m², kg, etc.)")
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
