from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from PIL import Image
import os
import uuid
import json
import re

User = get_user_model()


class Note(models.Model):
    """Notizen-Model für die Organisations-App."""
    title = models.CharField(max_length=200, verbose_name="Titel")
    content = models.TextField(blank=True, verbose_name="Inhalt")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name="Autor")
    image = models.ImageField(upload_to='notes/images/', blank=True, null=True, verbose_name="Bild")
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='mentioned_in_notes', verbose_name="Erwähnte Benutzer")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    is_public = models.BooleanField(default=False, verbose_name="Öffentlich")
    
    class Meta:
        verbose_name = "Notiz"
        verbose_name_plural = "Notizen"
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Verarbeite @Nutzer-Erwähnungen im Inhalt
        self.process_mentions()
    
    def process_mentions(self):
        """Verarbeitet @Nutzer-Erwähnungen im Inhalt und fügt sie zu mentioned_users hinzu."""
        import re
        
        # Suche nach @Nutzername-Mustern
        mentions = re.findall(r'@(\w+)', self.content)
        
        # Lösche bisherige Erwähnungen
        self.mentioned_users.clear()
        
        # Füge neue Erwähnungen hinzu
        for username in mentions:
            try:
                user = User.objects.get(username=username)
                self.mentioned_users.add(user)
            except User.DoesNotExist:
                continue


class Event(models.Model):
    """Kalenderereignis-Model."""
    PRIORITY_CHOICES = [
        ('low', 'Niedrig'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
        ('urgent', 'Dringend'),
    ]
    
    RESPONSE_CHOICES = [
        ('pending', 'Ausstehend'),
        ('accepted', 'Angenommen'),
        ('declined', 'Abgelehnt'),
        ('maybe', 'Vielleicht'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    start_time = models.DateTimeField(verbose_name="Startzeit")
    end_time = models.DateTimeField(verbose_name="Endzeit")
    location = models.CharField(max_length=300, blank=True, verbose_name="Ort")
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events', verbose_name="Organisator")
    participants = models.ManyToManyField(User, through='EventParticipant', blank=True, verbose_name="Teilnehmer")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', verbose_name="Priorität")
    reminder_minutes = models.IntegerField(default=15, verbose_name="Erinnerung (Minuten vorher)")
    is_all_day = models.BooleanField(default=False, verbose_name="Ganztägig")
    is_recurring = models.BooleanField(default=False, verbose_name="Wiederkehrend")
    recurrence_pattern = models.CharField(max_length=50, blank=True, verbose_name="Wiederholungsmuster")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    
    class Meta:
        verbose_name = "Termin"
        verbose_name_plural = "Termine"
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%d.%m.%Y %H:%M')}"
    
    def is_upcoming(self):
        """Prüft ob der Termin noch bevorsteht."""
        return self.start_time > timezone.now()
    
    def needs_reminder(self):
        """Prüft ob eine Erinnerung gesendet werden sollte."""
        if not self.is_upcoming():
            return False
        
        reminder_time = self.start_time - timezone.timedelta(minutes=self.reminder_minutes)
        return timezone.now() >= reminder_time
    
    def get_duration(self):
        """Gibt die Dauer des Termins zurück."""
        return self.end_time - self.start_time


class EventParticipant(models.Model):
    """Zwischentabelle für Terminpartizipanten mit Antwortmöglichkeiten."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, verbose_name="Termin")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Benutzer")
    response = models.CharField(max_length=10, choices=Event.RESPONSE_CHOICES, default='pending', verbose_name="Antwort")
    response_time = models.DateTimeField(null=True, blank=True, verbose_name="Antwortzeit")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    
    class Meta:
        verbose_name = "Terminpartizipant"
        verbose_name_plural = "Terminpartizipanten"
        unique_together = ['event', 'user']
    
    def __str__(self):
        return f"{self.user.username} - {self.event.title} ({self.response})"


class IdeaBoard(models.Model):
    """Ideenboard-Model für kollaborative Zeichnungen."""
    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_boards', verbose_name="Ersteller")
    collaborators = models.ManyToManyField(User, blank=True, related_name='collaborated_boards', verbose_name="Mitarbeiter")
    canvas_data = models.JSONField(default=dict, verbose_name="Canvas-Daten")
    width = models.IntegerField(default=1200, verbose_name="Breite")
    height = models.IntegerField(default=800, verbose_name="Höhe")
    background_color = models.CharField(max_length=7, default='#ffffff', verbose_name="Hintergrundfarbe")
    is_public = models.BooleanField(default=False, verbose_name="Öffentlich")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    
    class Meta:
        verbose_name = "Ideenboard"
        verbose_name_plural = "Ideenboards"
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.title
    
    def get_all_users(self):
        """Gibt alle Benutzer zurück, die Zugriff auf das Board haben."""
        users = [self.creator]
        users.extend(self.collaborators.all())
        return list(set(users))


class BoardElement(models.Model):
    """Einzelne Elemente auf dem Ideenboard."""
    ELEMENT_TYPES = [
        ('line', 'Linie'),
        ('arrow', 'Pfeil'),
        ('rectangle', 'Rechteck'),
        ('circle', 'Kreis'),
        ('triangle', 'Dreieck'),
        ('text', 'Text'),
        ('image', 'Bild'),
        ('freehand', 'Freihand'),
    ]
    
    board = models.ForeignKey(IdeaBoard, on_delete=models.CASCADE, related_name='elements', verbose_name="Board")
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPES, verbose_name="Element-Typ")
    data = models.JSONField(verbose_name="Element-Daten")
    position_x = models.IntegerField(verbose_name="X-Position")
    position_y = models.IntegerField(verbose_name="Y-Position")
    width = models.IntegerField(default=100, verbose_name="Breite")
    height = models.IntegerField(default=100, verbose_name="Höhe")
    color = models.CharField(max_length=7, default='#000000', verbose_name="Farbe")
    stroke_width = models.IntegerField(default=2, verbose_name="Strichstärke")
    opacity = models.FloatField(default=1.0, verbose_name="Transparenz")
    rotation = models.FloatField(default=0.0, verbose_name="Rotation (Grad)")
    layer_index = models.IntegerField(default=0, verbose_name="Ebenen-Index")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Erstellt von")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    
    class Meta:
        verbose_name = "Board-Element"
        verbose_name_plural = "Board-Elemente"
        ordering = ['layer_index', 'created_at']
    
    def __str__(self):
        return f"{self.element_type} auf {self.board.title}"


class EventReminder(models.Model):
    """Erinnerungen für Termine."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reminders', verbose_name="Termin")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Benutzer")
    reminder_time = models.DateTimeField(verbose_name="Erinnerungszeit")
    is_sent = models.BooleanField(default=False, verbose_name="Gesendet")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Gesendet am")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    
    class Meta:
        verbose_name = "Termin-Erinnerung"
        verbose_name_plural = "Termin-Erinnerungen"
        unique_together = ['event', 'user']
    
    def __str__(self):
        return f"Erinnerung: {self.event.title} für {self.user.username}"


class VideoCall(models.Model):
    """Video/Audio Call Model für Agora Integration."""
    STATUS_CHOICES = [
        ('waiting', 'Wartend'),
        ('active', 'Aktiv'),
        ('ended', 'Beendet'),
        ('missed', 'Verpasst'),
    ]
    
    CALL_TYPE_CHOICES = [
        ('video', 'Video-Anruf'),
        ('audio', 'Audio-Anruf'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel_name = models.CharField(max_length=100, unique=True, verbose_name="Kanal-Name")
    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='made_calls', verbose_name="Anrufer")
    participants = models.ManyToManyField(User, through='CallParticipant', verbose_name="Teilnehmer")
    call_type = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES, default='video', verbose_name="Anruf-Typ")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='waiting', verbose_name="Status")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Gestartet um")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Beendet um")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    
    # Agora-spezifische Felder
    agora_token = models.TextField(blank=True, verbose_name="Agora Token")
    token_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Token läuft ab")
    
    class Meta:
        verbose_name = "Video-Anruf"
        verbose_name_plural = "Video-Anrufe"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.call_type} - {self.caller.username} - {self.status}"
    
    def get_duration(self):
        """Berechnet die Dauer des Anrufs."""
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return None
    
    def is_active(self):
        """Prüft ob der Anruf aktiv ist."""
        return self.status == 'active'
    
    def generate_channel_name(self):
        """Generiert einen eindeutigen Kanal-Namen."""
        if not self.channel_name:
            self.channel_name = f"call_{self.id}_{int(timezone.now().timestamp())}"
            self.save()
        return self.channel_name


class CallParticipant(models.Model):
    """Teilnehmer eines Video/Audio-Anrufs."""
    STATUS_CHOICES = [
        ('invited', 'Eingeladen'),
        ('joined', 'Beigetreten'),
        ('left', 'Verlassen'),
        ('declined', 'Abgelehnt'),
    ]
    
    call = models.ForeignKey(VideoCall, on_delete=models.CASCADE, verbose_name="Anruf")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Benutzer")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='invited', verbose_name="Status")
    joined_at = models.DateTimeField(null=True, blank=True, verbose_name="Beigetreten um")
    left_at = models.DateTimeField(null=True, blank=True, verbose_name="Verlassen um")
    agora_uid = models.IntegerField(null=True, blank=True, verbose_name="Agora User ID")
    
    class Meta:
        verbose_name = "Anruf-Teilnehmer"
        verbose_name_plural = "Anruf-Teilnehmer"
        unique_together = ['call', 'user']
    
    def __str__(self):
        return f"{self.user.username} - {self.call.channel_name} ({self.status})"
    
    def get_duration(self):
        """Berechnet die Teilnahmedauer."""
        if self.joined_at and self.left_at:
            return self.left_at - self.joined_at
        elif self.joined_at:
            return timezone.now() - self.joined_at
        return None
