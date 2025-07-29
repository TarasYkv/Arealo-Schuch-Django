from django.core.management.base import BaseCommand
from accounts.models import AppPermission


class Command(BaseCommand):
    help = 'Sets up Email Templates app permission for superuser access only'

    def handle(self, *args, **options):
        # Create or update the email_templates app permission
        permission, created = AppPermission.objects.get_or_create(
            app_name='email_templates',
            defaults={
                'access_level': 'in_development',  # Only superusers can access
                'hide_in_frontend': False,
                'superuser_bypass': True,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Created Email Templates permission with access level: {permission.access_level}'
                )
            )
        else:
            # Update existing permission to ensure correct settings
            permission.access_level = 'in_development'
            permission.superuser_bypass = True
            permission.is_active = True
            permission.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Updated Email Templates permission with access level: {permission.access_level}'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                '🎯 Email Templates app is now accessible to superusers only'
            )
        )