"""
Management Command: create_default_skills

Erstellt Default Skill-Kategorien und Skills für LoomConnect.
Kann mehrfach ausgeführt werden - prüft auf Duplikate.

Usage:
    python manage.py create_default_skills
    python manage.py create_default_skills --reset  # Löscht erst alle Skills
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from loomconnect.models import SkillCategory, Skill


class Command(BaseCommand):
    help = 'Erstellt Default Skill-Kategorien und Skills für LoomConnect'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Löscht alle existierenden Skills und Kategorien vor dem Erstellen',
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)

        if reset:
            self.stdout.write(self.style.WARNING('⚠️  Lösche alle existierenden Skills und Kategorien...'))
            Skill.objects.all().delete()
            SkillCategory.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Gelöscht'))

        self.stdout.write(self.style.HTTP_INFO('🚀 Starte Erstellung der Default Skills...'))

        # Definition der Kategorien und Skills
        categories_data = {
            'Programmierung': {
                'icon': '💻',
                'description': 'Programmiersprachen und Frameworks',
                'skills': [
                    'Python', 'JavaScript', 'TypeScript', 'Java', 'C#', 'C++', 'PHP',
                    'Ruby', 'Go', 'Rust', 'Swift', 'Kotlin', 'Dart',
                    'React', 'Vue.js', 'Angular', 'Next.js', 'Django', 'Flask',
                    'Node.js', 'Express', 'FastAPI', 'Spring Boot', 'Laravel',
                ]
            },
            'Design': {
                'icon': '🎨',
                'description': 'Design, UI/UX und Kreatives',
                'skills': [
                    'UI Design', 'UX Design', 'Grafikdesign', 'Webdesign',
                    'Logo Design', 'Illustration', 'Animation', '3D Design',
                    'Figma', 'Adobe XD', 'Sketch', 'Photoshop', 'Illustrator',
                    'After Effects', 'Blender', 'Canva',
                ]
            },
            'Marketing': {
                'icon': '📈',
                'description': 'Marketing, SEO und Social Media',
                'skills': [
                    'SEO', 'Content Marketing', 'Social Media Marketing',
                    'Email Marketing', 'Google Ads', 'Facebook Ads',
                    'Instagram Marketing', 'LinkedIn Marketing',
                    'Copywriting', 'Storytelling', 'Branding',
                    'Analytics', 'Marketing Automation',
                ]
            },
            'Business': {
                'icon': '💼',
                'description': 'Business, Management und Finanzen',
                'skills': [
                    'Projektmanagement', 'Produktmanagement', 'Agile',
                    'Scrum', 'Business Development', 'Strategy',
                    'Finanzplanung', 'Buchhaltung', 'Controlling',
                    'Verhandlung', 'Präsentation', 'Leadership',
                ]
            },
            'Daten & AI': {
                'icon': '🤖',
                'description': 'Data Science, Machine Learning und AI',
                'skills': [
                    'Data Science', 'Machine Learning', 'Deep Learning',
                    'AI', 'Data Analysis', 'Data Visualization',
                    'SQL', 'Python Data Science', 'R', 'TensorFlow',
                    'PyTorch', 'scikit-learn', 'Pandas', 'NumPy',
                ]
            },
            'DevOps & Cloud': {
                'icon': '☁️',
                'description': 'DevOps, Cloud und Infrastructure',
                'skills': [
                    'DevOps', 'Docker', 'Kubernetes', 'CI/CD',
                    'AWS', 'Azure', 'Google Cloud', 'Terraform',
                    'Linux', 'Git', 'GitHub Actions', 'Jenkins',
                    'Monitoring', 'Security',
                ]
            },
            'Content': {
                'icon': '✍️',
                'description': 'Content Creation und Medien',
                'skills': [
                    'Schreiben', 'Blogging', 'Technical Writing',
                    'Journalismus', 'Videoproduktion', 'Fotografie',
                    'Podcasting', 'Video Editing', 'Audio Editing',
                    'YouTube', 'TikTok', 'Instagram Reels',
                ]
            },
            'Sprachen': {
                'icon': '🌍',
                'description': 'Fremdsprachen und Übersetzung',
                'skills': [
                    'Englisch', 'Deutsch', 'Spanisch', 'Französisch',
                    'Italienisch', 'Portugiesisch', 'Chinesisch', 'Japanisch',
                    'Koreanisch', 'Arabisch', 'Russisch',
                    'Übersetzung', 'Lokalisierung', 'Untertitelung',
                ]
            },
            'Beratung': {
                'icon': '🎯',
                'description': 'Beratung und Coaching',
                'skills': [
                    'Business Coaching', 'Life Coaching', 'Career Coaching',
                    'Unternehmensberatung', 'IT-Beratung', 'Marketing Beratung',
                    'Finanzberatung', 'Rechtsberatung', 'HR Beratung',
                    'Mentoring', 'Training', 'Workshops',
                ]
            },
            'Soft Skills': {
                'icon': '🤝',
                'description': 'Soft Skills und zwischenmenschliche Fähigkeiten',
                'skills': [
                    'Kommunikation', 'Teamarbeit', 'Zeitmanagement',
                    'Problemlösung', 'Kritisches Denken', 'Kreativität',
                    'Empathie', 'Konfliktlösung', 'Selbstorganisation',
                    'Networking', 'Public Speaking', 'Moderation',
                ]
            },
        }

        created_categories = 0
        created_skills = 0
        skipped_items = 0

        with transaction.atomic():
            for category_name, category_info in categories_data.items():
                # Kategorie erstellen oder abrufen
                category, created = SkillCategory.objects.get_or_create(
                    name=category_name,
                    defaults={
                        'description': category_info['description'],
                        'is_active': True,
                    }
                )

                if created:
                    created_categories += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Kategorie erstellt: {category_info["icon"]} {category_name}'
                        )
                    )
                else:
                    skipped_items += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⊘ Kategorie existiert: {category_info["icon"]} {category_name}'
                        )
                    )

                # Skills in dieser Kategorie erstellen
                for skill_name in category_info['skills']:
                    skill, created = Skill.objects.get_or_create(
                        name=skill_name,
                        defaults={
                            'category': category,
                            'is_predefined': True,
                            'is_active': True,
                        }
                    )

                    if created:
                        created_skills += 1
                        self.stdout.write(f'    • {skill_name}')
                    else:
                        skipped_items += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('📊 Zusammenfassung:'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ {created_categories} Kategorien erstellt'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ {created_skills} Skills erstellt'))
        if skipped_items > 0:
            self.stdout.write(self.style.WARNING(f'  ⊘ {skipped_items} Items übersprungen (existieren bereits)'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Fertig! LoomConnect Skills wurden erfolgreich erstellt.'))

        # Statistik ausgeben
        total_categories = SkillCategory.objects.count()
        total_skills = Skill.objects.count()
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO(f'📈 Gesamt in Datenbank:'))
        self.stdout.write(f'   {total_categories} Kategorien')
        self.stdout.write(f'   {total_skills} Skills')
