from django.urls import path
from . import views

app_name = 'fileshare'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_transfer, name='create_transfer'),
    path('upload/<uuid:transfer_id>/', views.upload_file, name='upload_file'),
    path('complete/<uuid:transfer_id>/', views.complete_transfer, name='complete_transfer'),
    path('download/<uuid:transfer_id>/', views.download_page, name='download'),
    path('download/<uuid:transfer_id>/file/', views.download_file, name='download_file'),
    path('download/<uuid:transfer_id>/file/<uuid:file_id>/', views.download_file, name='download_single_file'),
    path('my-transfers/', views.my_transfers, name='my_transfers'),
    path('delete/<uuid:transfer_id>/', views.delete_transfer, name='delete_transfer'),
    path('stats/<uuid:transfer_id>/', views.transfer_stats, name='transfer_stats'),
]