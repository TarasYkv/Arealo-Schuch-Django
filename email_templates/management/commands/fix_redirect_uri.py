from django.core.management.base import BaseCommand
from django.urls import reverse
from email_templates.models import ZohoMailServerConnection


class Command(BaseCommand):
    help = 'Fix redirect URI for Zoho connections'

    def handle(self, *args, **options):
        connections = ZohoMailServerConnection.objects.all()
        
        for conn in connections:
            correct_redirect_uri = f'http://127.0.0.1:8000{reverse("email_templates:oauth_callback")}'
            
            self.stdout.write(f'Connection "{conn.name}" (ID: {conn.id}):')
            self.stdout.write(f'  Current: {conn.redirect_uri}')
            self.stdout.write(f'  Correct: {correct_redirect_uri}')
            
            if conn.redirect_uri != correct_redirect_uri:
                conn.redirect_uri = correct_redirect_uri
                conn.save()
                self.stdout.write(self.style.SUCCESS('  ✅ Updated'))
            else:
                self.stdout.write(self.style.SUCCESS('  ✅ Already correct'))
            
            self.stdout.write('')