from django.core.management.base import BaseCommand
from somi_plan.models import Platform, TemplateCategory, PostTemplate


class Command(BaseCommand):
    help = 'Setup initial platforms and templates for SoMi-Plan'

    def handle(self, *args, **options):
        self.stdout.write('Setting up SoMi-Plan platforms and templates...')

        # Create Platforms
        platforms_data = [
            {
                'name': 'Instagram',
                'icon': 'fab fa-instagram',
                'color': '#E4405F',
                'character_limit': 2200,
                'description': 'Visual content focused social media platform'
            },
            {
                'name': 'LinkedIn',
                'icon': 'fab fa-linkedin',
                'color': '#0077B5',
                'character_limit': 3000,
                'description': 'Professional networking platform'
            },
            {
                'name': 'Twitter/X',
                'icon': 'fab fa-twitter',
                'color': '#1DA1F2',
                'character_limit': 280,
                'description': 'Microblogging platform'
            },
            {
                'name': 'Facebook',
                'icon': 'fab fa-facebook',
                'color': '#1877F2',
                'character_limit': 63206,
                'description': 'Social networking platform'
            },
            {
                'name': 'TikTok',
                'icon': 'fab fa-tiktok',
                'color': '#000000',
                'character_limit': 2200,
                'description': 'Short-form video platform'
            },
            {
                'name': 'YouTube',
                'icon': 'fab fa-youtube',
                'color': '#FF0000',
                'character_limit': 5000,
                'description': 'Video sharing platform'
            },
            {
                'name': 'Pinterest',
                'icon': 'fab fa-pinterest',
                'color': '#BD081C',
                'character_limit': 500,
                'description': 'Visual discovery platform'
            },
        ]

        for platform_data in platforms_data:
            platform, created = Platform.objects.get_or_create(
                name=platform_data['name'],
                defaults=platform_data
            )
            if created:
                self.stdout.write(f'✅ Created platform: {platform.name}')
            else:
                self.stdout.write(f'⚠️  Platform already exists: {platform.name}')

        # Create Template Categories for Instagram (example)
        instagram = Platform.objects.get(name='Instagram')
        
        categories_data = [
            {
                'name': 'Tipps & Tricks',
                'description': 'Hilfreiche Tipps für die Zielgruppe',
                'icon': 'fas fa-lightbulb'
            },
            {
                'name': 'Behind the Scenes',
                'description': 'Einblicke hinter die Kulissen',
                'icon': 'fas fa-camera'
            },
            {
                'name': 'Produktvorstellung',
                'description': 'Präsentation von Produkten oder Services',
                'icon': 'fas fa-star'
            },
            {
                'name': 'Motivation',
                'description': 'Motivierende und inspirierende Inhalte',
                'icon': 'fas fa-rocket'
            },
            {
                'name': 'Bildung',
                'description': 'Lehrreiche und informative Inhalte',
                'icon': 'fas fa-graduation-cap'
            },
        ]

        for category_data in categories_data:
            category, created = TemplateCategory.objects.get_or_create(
                name=category_data['name'],
                platform=instagram,
                defaults=category_data
            )
            if created:
                self.stdout.write(f'✅ Created category: {category.name} for {instagram.name}')

        # Create Example Templates
        tipps_category = TemplateCategory.objects.get(name='Tipps & Tricks', platform=instagram)
        
        template_data = {
            'name': 'Quick-Tipp Template',
            'content_template': '''🔥 TIPP: {titel}

{problem_beschreibung}

💡 LÖSUNG:
{loesung_schritte}

✅ WARUM ES FUNKTIONIERT:
{erklaerung}

👆 Speicher dir diesen Post für später!

#tipps #{zielgruppe} #{thema}''',
            'script_template': '''POST-SKRIPT: Quick-Tipp Template

🎯 ZIEL: Wertvolle Hilfe für {zielgruppe} bieten

📱 ANWEISUNGEN:
1. Starke Hook mit konkretem Problem
2. Klare, umsetzbare Lösung in Schritten
3. Begründung warum es funktioniert
4. Call-to-Action zum Speichern
5. Relevante Hashtags verwenden

⏰ BESTE POSTING-ZEIT: 18:00-20:00 Uhr
📊 ERWARTUNG: Hohe Engagement-Rate durch praktischen Nutzen
🎨 VISUAL: Carousel mit Schritt-für-Schritt Anleitung oder Infografik''',
            'ai_system_prompt': '''Du bist ein Experte für Instagram-Content-Erstellung. Erstelle hilfreiche, praktische Tipps die echten Mehrwert bieten.

WICHTIG:
- Verwende eine freundliche, direkte Ansprache
- Halte dich an das Template-Format
- Mache konkrete, umsetzbare Vorschläge
- Verwende relevante Emojis sparsam
- Achte auf das Zeichen-Limit von Instagram''',
            'ai_user_prompt_template': '''Erstelle einen Instagram-Post mit einem praktischen Tipp für {zielgruppe} zum Thema {thema}.

KONTEXT:
- Zielgruppe: {zielgruppe}
- Thema/Problem: {thema}
- Geschäftskontext: {business_kontext}

Verwende das Template und erstelle einen wertvollen, teilbaren Tipp-Post.'''
        }

        template, created = PostTemplate.objects.get_or_create(
            name=template_data['name'],
            category=tipps_category,
            defaults=template_data
        )
        if created:
            self.stdout.write(f'✅ Created template: {template.name}')

        self.stdout.write(self.style.SUCCESS('\n🎉 SoMi-Plan setup completed successfully!'))
        self.stdout.write(f'Created {Platform.objects.count()} platforms')
        self.stdout.write(f'Created {TemplateCategory.objects.count()} template categories')
        self.stdout.write(f'Created {PostTemplate.objects.count()} post templates')