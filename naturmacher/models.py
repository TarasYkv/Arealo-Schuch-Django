import os
import re
import requests
from django.db import models
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class Thema(models.Model):
    name = models.CharField(max_length=100)
    beschreibung = models.TextField()
    bild = models.ImageField(upload_to='naturmacher/themen/', blank=True, null=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('naturmacher:thema_detail', kwargs={'pk': self.pk})

    def get_fortschritt(self, user):
        """Gibt den Fortschritt für einen Benutzer zurück (0-100%)"""
        if not user.is_authenticated:
            return 0
        
        total_trainings = self.trainings.count()
        if total_trainings == 0:
            return 100
        
        erledigte_trainings = UserTrainingFortschritt.objects.filter(
            user=user,
            training__thema=self,
            erledigt=True
        ).count()
        
        return int((erledigte_trainings / total_trainings) * 100)
    
    def ist_komplett_erledigt(self, user):
        """Prüft ob alle Trainings eines Themas für einen User erledigt sind"""
        return self.get_fortschritt(user) == 100

    def get_inhaltsverzeichnis(self):
        """Liest das Inhaltsverzeichnis aus der entsprechenden Datei"""
        try:
            # Finde den passenden Ordner im Trainings-Verzeichnis
            trainings_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
            if not os.path.exists(trainings_path):
                return None
            
            # Suche nach einem Ordner, der den Thema-Namen enthält
            for folder_name in os.listdir(trainings_path):
                folder_path = os.path.join(trainings_path, folder_name)
                if os.path.isdir(folder_path) and self.name in folder_name:
                    inhaltsverzeichnis_path = os.path.join(folder_path, 'inhaltsverzeichnis.txt')
                    if os.path.exists(inhaltsverzeichnis_path):
                        with open(inhaltsverzeichnis_path, 'r', encoding='utf-8') as f:
                            return f.read()
            return None
        except Exception:
            return None

    def get_alle_notizen(self, user):
        """Gibt alle Notizen eines Users für alle Trainings dieses Themas zurück"""
        if not user.is_authenticated:
            return []
        
        notizen_list = []
        for training in self.trainings.all().order_by('titel'):
            try:
                notizen = UserTrainingNotizen.objects.get(user=user, training=training)
                if notizen.notizen.strip():
                    notizen_list.append({
                        'training': training,
                        'notizen': notizen.notizen,
                        'aktualisiert_am': notizen.aktualisiert_am
                    })
            except UserTrainingNotizen.DoesNotExist:
                continue
        
        return notizen_list

    def hat_notizen(self, user):
        """Prüft ob ein User Notizen für Trainings dieses Themas hat"""
        return len(self.get_alle_notizen(user)) > 0

    def get_thumbnail_from_folder(self):
        """Sucht nach einer Thumbnail-Datei im Themen-Ordner"""
        try:
            trainings_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
            if not os.path.exists(trainings_path):
                return None
            
            # Suche nach einem Ordner, der den Thema-Namen enthält
            for folder_name in os.listdir(trainings_path):
                folder_path = os.path.join(trainings_path, folder_name)
                if os.path.isdir(folder_path) and self.name in folder_name:
                    # Suche nach Thumbnail-Dateien
                    for file_name in os.listdir(folder_path):
                        if file_name.lower().startswith('thumbnail'):
                            file_path = os.path.join(folder_path, file_name)
                            if os.path.isfile(file_path):
                                # Relativen Pfad für Web-Zugriff erstellen
                                rel_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                                return settings.MEDIA_URL + rel_path.replace('\\', '/')
            return None
        except Exception:
            return None

    def get_display_image(self):
        """Gibt das anzuzeigende Bild zurück (eigenes Bild, Thumbnail aus Ordner oder zufälliges Training-Bild)"""
        if self.bild:
            return self.bild.url
        thumbnail = self.get_thumbnail_from_folder()
        if thumbnail:
            return thumbnail
        
        # Fallback: Zufälliges Bild von den Trainings dieses Themas
        import random
        trainings_with_images = self.trainings.exclude(bild='').exclude(bild__isnull=True)
        if trainings_with_images.exists():
            random_training = random.choice(trainings_with_images)
            return random_training.bild.url
        
        # Wenn keine Training-Bilder vorhanden, versuche YouTube-Thumbnails
        trainings_with_youtube = self.trainings.exclude(youtube_links='').exclude(youtube_links__isnull=True)
        if trainings_with_youtube.exists():
            random_training = random.choice(trainings_with_youtube)
            youtube_thumbnail = random_training.get_first_youtube_thumbnail()
            if youtube_thumbnail:
                return youtube_thumbnail
        
        return None

    class Meta:
        verbose_name = 'Thema'
        verbose_name_plural = 'Themen'


class Training(models.Model):
    SCHWIERIGKEIT_CHOICES = [
        ('anfaenger', 'Anfänger'),
        ('fortgeschritten', 'Fortgeschritten'),
        ('experte', 'Experte'),
    ]

    titel = models.CharField(max_length=200)
    beschreibung = models.TextField()
    thema = models.ForeignKey(Thema, on_delete=models.CASCADE, related_name='trainings')
    schwierigkeit = models.CharField(max_length=20, choices=SCHWIERIGKEIT_CHOICES, default='anfaenger')
    dauer_minuten = models.PositiveIntegerField()
    bild = models.ImageField(upload_to='naturmacher/trainings/', blank=True, null=True)
    youtube_links = models.TextField(blank=True, help_text="YouTube-Links (einer pro Zeile)")
    inhalt = models.TextField()
    ai_model_used = models.CharField(max_length=100, blank=True, null=True, help_text="KI-Modell, das zum Erstellen dieses Trainings verwendet wurde")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    aktualisiert_am = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titel

    def get_absolute_url(self):
        return reverse('naturmacher:training_detail', kwargs={'pk': self.pk})

    def ist_erledigt(self, user):
        """Prüft ob ein Training für einen User erledigt ist"""
        if not user.is_authenticated:
            return False
        
        try:
            fortschritt = UserTrainingFortschritt.objects.get(user=user, training=self)
            return fortschritt.erledigt
        except UserTrainingFortschritt.DoesNotExist:
            return False

    def get_notizen(self, user):
        """Gibt die Notizen eines Users für dieses Training zurück"""
        if not user.is_authenticated:
            return ""
        
        try:
            notizen = UserTrainingNotizen.objects.get(user=user, training=self)
            return notizen.notizen
        except UserTrainingNotizen.DoesNotExist:
            return ""

    def hat_notizen(self, user):
        """Prüft ob ein User Notizen für dieses Training hat"""
        if not user.is_authenticated:
            return False
        
        try:
            notizen = UserTrainingNotizen.objects.get(user=user, training=self)
            return bool(notizen.notizen.strip())
        except UserTrainingNotizen.DoesNotExist:
            return False

    def get_youtube_video_id(self, url):
        """Extrahiert die Video-ID aus einer YouTube-URL"""
        youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)'
        match = re.search(youtube_regex, url)
        return match.group(1) if match else None

    def get_first_youtube_thumbnail(self):
        """Gibt das Thumbnail des ersten YouTube-Videos zurück"""
        if not self.youtube_links:
            return None
        
        lines = self.youtube_links.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line:
                video_id = self.get_youtube_video_id(line)
                if video_id:
                    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return None

    def get_display_image(self):
        """Gibt das anzuzeigende Bild zurück (eigenes Bild oder YouTube-Thumbnail)"""
        if self.bild:
            return self.bild.url
        thumbnail = self.get_first_youtube_thumbnail()
        if thumbnail:
            return thumbnail
        return None
    
    def get_ai_model_display(self):
        """Formatiert die Anzeige des KI-Modells mit Provider und spezifischem Modellnamen"""
        if not self.ai_model_used:
            return None
        
        model = self.ai_model_used.lower()
        
        # OpenAI Modelle
        if model.startswith('gpt-') or model.startswith('o'):
            if model == 'gpt-4.1':
                return 'OpenAI GPT-4.1'
            elif model == 'gpt-4o':
                return 'OpenAI GPT-4o'
            elif model == 'o3':
                return 'OpenAI o3'
            elif model == 'o4-mini':
                return 'OpenAI o4-mini'
            else:
                return f'OpenAI {model.upper()}'
        
        # Claude Modelle
        elif model.startswith('claude'):
            if model == 'claude-opus-4':
                return 'Anthropic Claude Opus 4'
            elif model == 'claude-sonnet-4':
                return 'Anthropic Claude Sonnet 4'
            elif model == 'claude-haiku-4':
                return 'Anthropic Claude Haiku 4'
            else:
                return f'Anthropic {model.title()}'
        
        # Gemini Modelle
        elif model.startswith('gemini'):
            if model == 'gemini-2.5-pro':
                return 'Google Gemini 2.5 Pro'
            elif model == 'gemini-2.5-flash':
                return 'Google Gemini 2.5 Flash'
            elif model == 'gemini-2.0-pro':
                return 'Google Gemini 2.0 Pro'
            elif model == 'gemini-2.0-flash':
                return 'Google Gemini 2.0 Flash'
            elif model == 'gemini-1.5-pro':
                return 'Google Gemini 1.5 Pro'
            elif model == 'gemini-1.5-flash':
                return 'Google Gemini 1.5 Flash'
            elif model == 'gemini':
                return 'Google Gemini'
            else:
                return f'Google {model.title()}'
        
        # Fallback für andere Modelle
        else:
            return self.ai_model_used
    
    def get_html_content(self):
        """Lädt den HTML-Inhalt aus der Datei, falls vorhanden"""
        # Überprüfe ob es sich um eine KI-generierte Schulung handelt
        if "HTML-Datei:" not in self.inhalt:
            return None
        
        try:
            # Extrahiere Dateiname aus dem inhalt Feld
            lines = self.inhalt.split('\n')
            filename = None
            for line in lines:
                if line.startswith('HTML-Datei:'):
                    filename = line.replace('HTML-Datei:', '').strip()
                    break
            
            if not filename:
                return None
            
            # Finde den passenden Thema-Ordner
            trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
            if not os.path.exists(trainings_base_path):
                return None
            
            for folder in os.listdir(trainings_base_path):
                folder_path = os.path.join(trainings_base_path, folder)
                if os.path.isdir(folder_path) and self.thema.name.lower() in folder.lower():
                    file_path = os.path.join(folder_path, filename)
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                            # Extrahiere nur den Body-Inhalt für bessere Integration
                            return self.extract_body_content(html_content)
                    break
            
            return None
            
        except Exception as e:
            print(f"Fehler beim Laden der HTML-Datei: {e}")
            return None
    
    def extract_body_content(self, html_content):
        """Extrahiert nur den Body-Inhalt aus der HTML-Datei"""
        try:
            import re
            # Extrahiere Inhalt zwischen <body> Tags
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_content = body_match.group(1)
                
                # Entferne das eigene Styling, da wir Bootstrap verwenden
                # Aber behalte die inline Styles für Tabellen etc.
                body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL)
                
                return body_content.strip()
            
            # Fallback: ganzer Inhalt wenn kein Body-Tag gefunden
            return html_content
            
        except Exception as e:
            print(f"Fehler beim Extrahieren des Body-Inhalts: {e}")
            return html_content

    class Meta:
        verbose_name = 'Training'
        verbose_name_plural = 'Trainings'
        ordering = ['-erstellt_am']


class UserTrainingFortschritt(models.Model):
    """Speichert den Fortschritt eines Users bei den Trainings"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    training = models.ForeignKey(Training, on_delete=models.CASCADE)
    erledigt = models.BooleanField(default=False)
    erledigt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Erledigt" if self.erledigt else "Offen"
        return f"{self.user.username} - {self.training.titel} ({status})"

    class Meta:
        unique_together = ['user', 'training']
        verbose_name = 'Training-Fortschritt'
        verbose_name_plural = 'Training-Fortschritte'


class UserTrainingNotizen(models.Model):
    """Speichert persönliche Notizen eines Users zu Trainings"""
    INPUT_TYPE_CHOICES = [
        ('text', 'Text'),
        ('handwriting', 'Handschrift'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    training = models.ForeignKey(Training, on_delete=models.CASCADE)
    notizen = models.TextField(blank=True)
    input_type = models.CharField(max_length=20, choices=INPUT_TYPE_CHOICES, default='text')
    erstellt_am = models.DateTimeField(auto_now_add=True)
    aktualisiert_am = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.training.titel} (Notizen)"

    class Meta:
        unique_together = ['user', 'training']
        verbose_name = 'Training-Notizen'
        verbose_name_plural = 'Training-Notizen'


class APIBalance(models.Model):
    """Speichert die API-Kontostände für alle Provider"""
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI (ChatGPT)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('google', 'Google (Gemini)'),
        ('youtube', 'YouTube Data API'),
        ('canva', 'Canva'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Aktueller Kontostand in USD/EUR")
    currency = models.CharField(max_length=3, default='USD', help_text="Währung (USD, EUR)")
    last_updated = models.DateTimeField(auto_now=True)
    auto_warning_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, help_text="Warnung bei diesem Kontostand")
    
    def __str__(self):
        return f"{self.user.username} - {self.get_provider_display()}: {self.balance} {self.currency}"
    
    def is_low_balance(self):
        """Prüft ob der Kontostand niedrig ist"""
        return self.balance <= self.auto_warning_threshold
    
    def get_balance_status(self):
        """Gibt den Status des Kontostands zurück"""
        if self.balance <= 0:
            return 'empty'
        elif self.balance <= self.auto_warning_threshold:
            return 'low'
        elif self.balance <= self.auto_warning_threshold * 3:
            return 'medium'
        else:
            return 'high'
    
    def has_api_key(self):
        """Prüft ob ein API-Key hinterlegt ist (aus dem User-Profil)"""
        from naturmacher.utils.api_helpers import get_user_api_key
        return bool(get_user_api_key(self.user, self.provider))
    
    def get_masked_api_key(self):
        """Gibt den API-Key maskiert zurück für Anzeige (aus dem User-Profil)"""
        from naturmacher.utils.api_helpers import get_user_api_key
        api_key = get_user_api_key(self.user, self.provider)
        if not api_key:
            return "Nicht konfiguriert"
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]

    class Meta:
        unique_together = ['user', 'provider']
        verbose_name = 'API-Kontostand'
        verbose_name_plural = 'API-Kontostände'


class CanvaAPISettings(models.Model):
    """Speichert Canva-spezifische API-Einstellungen für Benutzer"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='canva_settings')
    client_id = models.CharField(max_length=100, blank=True, help_text="Canva Client ID")
    client_secret = models.CharField(max_length=200, blank=True, help_text="Canva Client Secret")
    access_token = models.TextField(blank=True, help_text="OAuth Access Token")
    refresh_token = models.TextField(blank=True, help_text="OAuth Refresh Token")
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text="Token Ablaufzeit")
    brand_template_id = models.CharField(max_length=100, blank=True, help_text="Standard Brand Template ID")
    folder_id = models.CharField(max_length=100, blank=True, help_text="Standard Ordner ID")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Canva API Settings"
        verbose_name_plural = "Canva API Settings"
    
    def __str__(self):
        return f"Canva Settings für {self.user.username}"
    
    def has_valid_credentials(self):
        """Prüft ob gültige Canva-Anmeldedaten vorhanden sind"""
        return bool(self.client_id and self.client_secret)
    
    def has_access_token(self):
        """Prüft ob ein Access Token vorhanden ist"""
        return bool(self.access_token)
    
    def is_token_expired(self):
        """Prüft ob der Access Token abgelaufen ist"""
        if not self.token_expires_at:
            return True
        from django.utils import timezone
        return timezone.now() > self.token_expires_at


class APIUsageLog(models.Model):
    """Protokolliert die API-Nutzung für Kostentracking"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=APIBalance.PROVIDER_CHOICES)
    model_name = models.CharField(max_length=50, help_text="z.B. gpt-4.1, claude-opus-4")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=4, default=0.0000)
    training = models.ForeignKey(Training, on_delete=models.SET_NULL, null=True, blank=True, help_text="Zugehöriges Training falls vorhanden")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.provider} ({self.model_name}): ${self.estimated_cost}"
    
    class Meta:
        verbose_name = 'API-Nutzungsprotokoll'
        verbose_name_plural = 'API-Nutzungsprotokolle'
        ordering = ['-created_at']
