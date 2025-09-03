from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class PageSnapshot(models.Model):
    """Snapshots of page edits for backup and versioning"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='page_snapshots')
    page = models.CharField(max_length=100)
    html_content = models.TextField(blank=True)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.page} - {self.user.username} - {self.created_at}"