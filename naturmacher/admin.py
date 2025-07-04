from django.contrib import admin
from .models import Thema, Training, UserTrainingFortschritt


@admin.register(Thema)
class ThemaAdmin(admin.ModelAdmin):
    list_display = ('name', 'erstellt_am')
    search_fields = ('name', 'beschreibung')
    list_filter = ('erstellt_am',)


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('titel', 'thema', 'schwierigkeit', 'dauer_minuten', 'erstellt_am')
    search_fields = ('titel', 'beschreibung', 'inhalt')
    list_filter = ('thema', 'schwierigkeit', 'erstellt_am')
    ordering = ('-erstellt_am',)


@admin.register(UserTrainingFortschritt)
class UserTrainingFortschrittAdmin(admin.ModelAdmin):
    list_display = ('user', 'training', 'erledigt', 'erledigt_am')
    list_filter = ('erledigt', 'training__thema', 'erledigt_am')
    search_fields = ('user__username', 'training__titel')
    ordering = ('-erledigt_am',)
