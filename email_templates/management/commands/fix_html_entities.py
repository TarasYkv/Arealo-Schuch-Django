from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplate
import html


class Command(BaseCommand):
    help = 'Fix HTML entities in all email templates'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Fixing HTML entities in email templates...'))

        # Get all templates
        templates = EmailTemplate.objects.all()
        fixed_count = 0

        for template in templates:
            needs_fix = False

            # Check if HTML content contains entities
            if template.html_content and ('&auml;' in template.html_content or
                                          '&ouml;' in template.html_content or
                                          '&uuml;' in template.html_content or
                                          '&Auml;' in template.html_content or
                                          '&Ouml;' in template.html_content or
                                          '&Uuml;' in template.html_content or
                                          '&szlig;' in template.html_content):
                self.stdout.write(f'Found HTML entities in: {template.name}')
                template.html_content = html.unescape(template.html_content)
                needs_fix = True

            # Check if text content contains entities
            if template.text_content and ('&auml;' in template.text_content or
                                          '&ouml;' in template.text_content or
                                          '&uuml;' in template.text_content or
                                          '&Auml;' in template.text_content or
                                          '&Ouml;' in template.text_content or
                                          '&Uuml;' in template.text_content or
                                          '&szlig;' in template.text_content):
                self.stdout.write(f'Found HTML entities in text of: {template.name}')
                template.text_content = html.unescape(template.text_content)
                needs_fix = True

            # Check subject
            if template.subject and ('&auml;' in template.subject or
                                     '&ouml;' in template.subject or
                                     '&uuml;' in template.subject or
                                     '&Auml;' in template.subject or
                                     '&Ouml;' in template.subject or
                                     '&Uuml;' in template.subject or
                                     '&szlig;' in template.subject):
                self.stdout.write(f'Found HTML entities in subject of: {template.name}')
                template.subject = html.unescape(template.subject)
                needs_fix = True

            if needs_fix:
                template.save()
                fixed_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Fixed: {template.name}'))

        self.stdout.write(self.style.SUCCESS(f'\n🎉 Fixed {fixed_count} templates!'))