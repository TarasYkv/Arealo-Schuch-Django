from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplateCategory


class Command(BaseCommand):
    help = 'Creates default email template categories'

    def handle(self, *args, **options):
        categories = [
            {
                'name': 'Bestellungen',
                'slug': 'bestellungen',
                'description': 'E-Mail-Vorlagen für Bestellprozesse',
                'icon': 'fas fa-shopping-cart',
                'order': 1
            },
            {
                'name': 'Newsletter',
                'slug': 'newsletter', 
                'description': 'E-Mail-Vorlagen für Newsletter und Marketing',
                'icon': 'fas fa-newspaper',
                'order': 2
            },
            {
                'name': 'Benutzerverwaltung',
                'slug': 'benutzerverwaltung',
                'description': 'E-Mail-Vorlagen für Benutzerregistrierung und -verwaltung',
                'icon': 'fas fa-users',
                'order': 3
            },
            {
                'name': 'Support',
                'slug': 'support',
                'description': 'E-Mail-Vorlagen für Kundensupport',
                'icon': 'fas fa-headset',
                'order': 4
            },
            {
                'name': 'Allgemein',
                'slug': 'allgemein',
                'description': 'Allgemeine E-Mail-Vorlagen',
                'icon': 'fas fa-envelope',
                'order': 5
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for category_data in categories:
            category, created = EmailTemplateCategory.objects.get_or_create(
                slug=category_data['slug'],
                defaults=category_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created category: {category.name}')
                )
            else:
                # Update existing category
                for key, value in category_data.items():
                    if key != 'slug':  # Don't update slug
                        setattr(category, key, value)
                category.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'🔄 Updated category: {category.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🎯 Categories setup complete: {created_count} created, {updated_count} updated'
            )
        )