# VOLLSTÄNDIGER CODE FÜR: pdf_sucher/urls.py

from django.urls import path
from . import views

app_name = 'pdf_sucher'

urlpatterns = [
    # KORREKTUR: Der Name wurde auf 'pdf_suche' zurückgeändert, um konsistent zu sein.
    # Die Templates (base.html, startseite.html) sollten {% url 'pdf_sucher:pdf_suche' %} verwenden.
    path('suche/', views.pdf_suche, name='pdf_suche'),

    # KORREKTUR: Der Pfad wurde angepasst, damit er zum Aufruf im Template passt.
    path('preview/<str:filename>/<int:page_num>/', views.pdf_page_preview, name='pdf_page_preview'),

    path('view/<str:filename>/', views.view_pdf, name='view_pdf'),
]