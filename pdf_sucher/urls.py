# pdf_sucher/urls.py

from django.urls import path
from . import views

app_name = 'pdf_sucher'

urlpatterns = [
    # Wir benennen 'pdf_suche' in 'pdf_tool_start' um, damit es zu den Templates passt.
    path('suche/', views.pdf_suche, name='pdf_tool_start'), # KORRIGIERT

    # Die anderen Pfade bleiben unverändert
    path('view/<str:filename>/', views.view_pdf, name='view_pdf'),
    path('preview/<str:filename>/page/<int:page_num>/', views.pdf_page_preview, name='pdf_page_preview'),
]