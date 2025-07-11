from django.urls import path
from . import views

app_name = 'bug_report'

urlpatterns = [
    path('submit/', views.submit_bug_report, name='submit_bug_report'),
    path('upload/', views.upload_bug_attachment, name='upload_bug_attachment'),
    path('list/', views.bug_report_list, name='bug_report_list'),
    path('<int:bug_report_id>/', views.bug_report_detail, name='bug_report_detail'),
    path('<int:bug_report_id>/status/', views.update_bug_status, name='update_bug_status'),
]