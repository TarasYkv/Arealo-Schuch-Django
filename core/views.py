# core/views.py
from django.shortcuts import render

def startseite_ansicht(request):
    """Diese Ansicht rendert nur die Kachel-Übersicht."""
    # Wichtig: Der Pfad zum Template muss auch angepasst werden!
    return render(request, 'core/startseite.html')