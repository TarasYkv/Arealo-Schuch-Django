# in sportplatzApp/admin.py

from django.contrib import admin
from .models import Projekt, Komponente, Variante  # Alle drei Modelle müssen hier importiert werden

# Jedes Modell, das im Admin erscheinen soll, braucht eine eigene register-Zeile.
admin.site.register(Projekt)
admin.site.register(Komponente)
admin.site.register(Variante)