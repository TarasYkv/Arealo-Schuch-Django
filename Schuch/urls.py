from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Die URLs unserer Sportplatz-App (erstmal wie vorher)
    path('', include('sportplatzApp.urls')),

    # Die URLs unserer PDF-Sucher-App
    path('pdf-tool/', include('pdf_sucher.urls')),
]