# in sportplatzApp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Ich bekomme die Anfrage und schaue, ob sie zu 'rechner/' passt.
    # Wenn ja, rufe ich die Funktion 'rechnerAnsicht' auf.
    path('rechner/', views.rechnerAnsicht, name='rechner'),
]