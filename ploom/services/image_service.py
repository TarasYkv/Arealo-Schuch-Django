"""
P-Loom Image Service für Gravur-Workflow Bildgenerierung
Wrapper um GeminiImageService mit spezialisierten Prompts für Blumentopf-Gravuren

2-Schritt-Prozess für konsistente Bilder:
1. Basis-Topf generieren (Topf + Gravur auf neutralem Hintergrund)
2. Szenen-Bilder generieren mit dem Basis-Topf als Referenz
"""
import base64
import logging
import os
from datetime import datetime

from django.core.files.base import ContentFile

from ideopin.gemini_service import GeminiImageService, spell_out_text

logger = logging.getLogger(__name__)

# Verfügbare Bild-Typen für den Workflow
IMAGE_TYPES = {
    # Spezial-Typen
    'design': {
        'label': 'Design (weißer Hintergrund)',
        'category': 'Spezial',
        'prompt': 'Nur der Gravur-Text auf reinweißem Hintergrund. Elegante Typografie, kein Topf, kein Hintergrund, nur der Text. Zentriert, gut lesbar, hohe Auflösung.',
        'is_design_only': True,
    },
    # Mit Menschen
    'lifestyle': {
        'label': 'Lifestyle',
        'category': 'Mit Menschen',
        'prompt': 'Lifestyle-Produktfoto: Eine junge Frau hält den gravierten Blumentopf, natürliche entspannte Pose. Der Topf ist bepflanzt mit einer grünen Pflanze. Authentisch, warm, wie ein Instagram-Foto.',
    },
    'geschenk_uebergabe': {
        'label': 'Geschenk-Übergabe',
        'category': 'Mit Menschen',
        'prompt': 'Eine Person überreicht einer anderen den gravierten Blumentopf als Geschenk. Freudige Gesichter, emotionaler Moment. Schöne Verpackung oder Schleife sichtbar.',
    },
    'balkon': {
        'label': 'Balkon/Terrasse',
        'category': 'Mit Menschen',
        'prompt': 'Eine junge Frau auf einem sonnigen Balkon oder einer Terrasse, arrangiert den gravierten Blumentopf zwischen anderen Pflanzen. Urbanes Garten-Feeling, grüne Oase.',
    },
    'kuechenfenster': {
        'label': 'Küchenfenster',
        'category': 'Mit Menschen',
        'prompt': 'Eine junge Frau stellt den gravierten Blumentopf liebevoll auf die Fensterbank in einer hellen, modernen Küche. Warmes Tageslicht fällt durch das Fenster.',
    },
    'garten': {
        'label': 'Garten',
        'category': 'Mit Menschen',
        'prompt': 'Eine junge Frau kniet in einem schönen Garten und pflanzt eine Pflanze in den gravierten Blumentopf. Natürliche Umgebung, Erde, grüne Pflanzen.',
    },
    'selfie': {
        'label': 'Selfie-Style',
        'category': 'Mit Menschen',
        'prompt': 'Eine junge Frau zeigt den gravierten Blumentopf stolz in die Kamera, nah, Selfie-Perspektive. Strahlendes Lächeln, der Topf und die Gravur sind gut sichtbar.',
    },
    'paar': {
        'label': 'Paar-Moment',
        'category': 'Mit Menschen',
        'prompt': 'Ein junges Pärchen schaut gemeinsam den gravierten Blumentopf an. Romantischer, intimer Moment. Warme Beleuchtung.',
    },
    'unboxing': {
        'label': 'Auspacken/Unboxing',
        'category': 'Mit Menschen',
        'prompt': 'Eine Person packt den gravierten Blumentopf aus einer hübschen Geschenkbox aus. Überraschungsmoment, Freude im Gesicht. Verpackungsmaterial sichtbar.',
    },
    # Ohne Menschen
    'topf_nur': {
        'label': 'Nur Topf',
        'category': 'Ohne Menschen',
        'prompt': 'Der gravierte Blumentopf allein auf einem cleanen, hellen Hintergrund. Professionelles Produktfoto, keine Ablenkung.',
    },
    'nahaufnahme': {
        'label': 'Nahaufnahme Gravur',
        'category': 'Ohne Menschen',
        'prompt': 'Extreme Nahaufnahme / Close-up der Gravur auf dem Keramik-Blumentopf. Die Buchstaben und die Textur der Keramik sind scharf und detailliert sichtbar. Makro-Stil.',
    },
    'flatlay': {
        'label': 'Flatlay',
        'category': 'Ohne Menschen',
        'prompt': 'Flatlay von oben fotografiert: Der gravierte Blumentopf auf einer schönen Unterlage (Holz oder Marmor), dekorativ arrangiert mit Pflanzen, Erde, kleinen Werkzeugen.',
    },
    'fensterbank': {
        'label': 'Fensterbank',
        'category': 'Ohne Menschen',
        'prompt': 'Der gravierte Blumentopf bepflanzt auf einer hellen Fensterbank. Warmes Tageslicht, Vorhänge, gemütliche Atmosphäre. Die Gravur ist gut lesbar.',
    },
    'tisch': {
        'label': 'Tisch-Arrangement',
        'category': 'Ohne Menschen',
        'prompt': 'Der gravierte Blumentopf als Deko-Element auf einem schön gedeckten Tisch. Kerzen, Servietten, stilvoll arrangiert.',
    },
    'geschenk': {
        'label': 'Geschenk',
        'category': 'Ohne Menschen',
        'prompt': 'Der gravierte Blumentopf hübsch verpackt mit Schleife und Geschenkpapier, bereit zum Verschenken. Festliche, einladende Atmosphäre.',
    },
    'natur': {
        'label': 'Natur',
        'category': 'Ohne Menschen',
        'prompt': 'Der gravierte Blumentopf draußen in der Natur. Moos, Holz, Steine, natürliche Umgebung. Rustikal und organisch.',
    },
}


class PLoomImageService:
    """Service für Gravur-Workflow Bildgenerierung

    2-Schritt-Prozess:
    1. generate_base_pot() — Topf + Gravur auf neutralem Hintergrund (wird als Referenz gespeichert)
    2. generate_pot_image() — Szene mit dem Referenz-Topf
    """

    def __init__(self, user):
        self.user = user
        self.settings = None
        self.gemini_service = None

        if user and user.is_authenticated:
            from ..models import PLoomSettings
            self.settings = PLoomSettings.objects.filter(user=user).first()

            api_key = user.gemini_api_key or getattr(user, 'google_api_key', None)
            if api_key:
                self.gemini_service = GeminiImageService(api_key=api_key)

    def _get_pot_description(self):
        """Gibt die Topf-Beschreibung aus den Settings zurück"""
        pot_desc = 'runder Keramik-Blumentopf, cremeweiß, matte Oberfläche, ca. 14cm Durchmesser, 12cm hoch'
        if self.settings and self.settings.pot_description:
            pot_desc = self.settings.pot_description
        return pot_desc

    def _get_engraving_style(self):
        """Gibt den Gravur-Stil aus den Settings zurück"""
        style = 'elegante Schreibschrift'
        if self.settings and self.settings.engraving_style:
            style = self.settings.engraving_style
        return style

    def _get_model(self):
        """Gibt das Bildgenerierungs-Modell zurück"""
        if self.settings and self.settings.image_generation_model:
            return self.settings.image_generation_model
        return None

    def _get_reference_image(self):
        """Gibt den Pfad zum Settings-Referenzbild zurück"""
        if self.settings and self.settings.reference_image:
            try:
                return self.settings.reference_image.path
            except Exception:
                pass
        return None

    def generate_base_pot(self, engraving_text: str) -> dict:
        """
        SCHRITT 1: Generiert den Basis-Topf mit Gravur auf neutralem Hintergrund.
        Dieses Bild dient als Referenz für alle weiteren Szenen-Bilder.

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        if not self.gemini_service:
            return {'success': False, 'error': 'Gemini API-Key nicht konfiguriert'}

        pot_desc = self._get_pot_description()
        engraving_style = self._get_engraving_style()
        spelled_text = spell_out_text(engraving_text)

        prompt = (
            f"Erstelle ein professionelles Produktfoto eines einzelnen Blumentopfs auf reinweißem Hintergrund. "
            f"\n\nDER TOPF: {pot_desc}. "
            f"\n\nDIE GRAVUR: Auf der Vorderseite des Topfs ist in {engraving_style} der Text {spelled_text} eingraviert. "
            f"Die Gravur ist in den Ton eingeritzt (nicht aufgemalt, nicht aufgedruckt). "
            f"Die Buchstaben sind leicht vertieft und heben sich durch Licht/Schatten vom Topf ab. "
            f"Der Text '{engraving_text}' muss EXAKT und vollständig lesbar sein. "
            f"\n\nFOTO-STIL: Reinweißer Hintergrund, professionelle Studio-Beleuchtung, "
            f"leichter Schatten unter dem Topf, kein anderes Objekt im Bild. "
            f"Frontalansicht, Gravur direkt zur Kamera. Quadratisches Format."
        )

        try:
            result = self.gemini_service.generate_image(
                prompt=prompt,
                reference_image=self._get_reference_image(),
                width=1024,
                height=1024,
                model=self._get_model(),
            )
            return result
        except Exception as e:
            logger.error(f"Base pot generation failed: {e}")
            return {'success': False, 'error': str(e)}

    def generate_design_image(self, engraving_text: str) -> dict:
        """
        Generiert nur den Gravur-Text auf weißem Hintergrund (für Download).

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        if not self.gemini_service:
            return {'success': False, 'error': 'Gemini API-Key nicht konfiguriert'}

        engraving_style = self._get_engraving_style()
        spelled_text = spell_out_text(engraving_text)

        prompt = (
            f"Erstelle ein Bild mit NUR Text auf reinweißem Hintergrund. "
            f"Der Text lautet: {spelled_text}. "
            f"Schriftstil: {engraving_style}. "
            f"Der Text ist zentriert, elegant, groß und gut lesbar. "
            f"Kein Topf, keine Dekoration, nur der Text '{engraving_text}' auf weißem Hintergrund. "
            f"Quadratisches Format, hohe Auflösung."
        )

        try:
            result = self.gemini_service.generate_image(
                prompt=prompt,
                width=1024,
                height=1024,
                model=self._get_model(),
            )
            return result
        except Exception as e:
            logger.error(f"Design image generation failed: {e}")
            return {'success': False, 'error': str(e)}

    def generate_pot_image(self, engraving_text: str, scene_description: str,
                           variant_type: str = 'komplett', base_pot_image_path: str = None) -> dict:
        """
        SCHRITT 2: Generiert ein Szenen-Bild mit dem Topf.
        Verwendet das Basis-Topf-Bild als Referenz für Konsistenz.

        Args:
            engraving_text: Der Gravur-Text auf dem Topf
            scene_description: Beschreibung der Szene/Hintergrund
            variant_type: Bild-Typ aus IMAGE_TYPES
            base_pot_image_path: Pfad zum Basis-Topf-Bild (für Referenz)

        Returns:
            dict mit 'success', 'image_data' (base64) oder 'error'
        """
        if not self.gemini_service:
            return {'success': False, 'error': 'Gemini API-Key nicht konfiguriert'}

        # Design-only Typ
        image_type_config = IMAGE_TYPES.get(variant_type, {})
        if image_type_config.get('is_design_only'):
            return self.generate_design_image(engraving_text)

        pot_desc = self._get_pot_description()
        engraving_style = self._get_engraving_style()
        spelled_text = spell_out_text(engraving_text)

        # Szenen-Prompt
        scene_prompt = image_type_config.get('prompt', scene_description) if image_type_config else scene_description

        # Referenzbild: Basis-Topf hat Priorität, dann Settings-Referenzbild
        reference_image = None
        if base_pot_image_path:
            from django.conf import settings as django_settings
            full_path = os.path.join(django_settings.MEDIA_ROOT, base_pot_image_path)
            if os.path.exists(full_path):
                reference_image = full_path
                logger.info(f"Using base pot as reference: {full_path}")

        if not reference_image:
            reference_image = self._get_reference_image()

        # Prompt mit Referenz auf Basis-Topf
        if base_pot_image_path:
            prompt = (
                f"Erstelle ein Produktfoto. Das Referenzbild zeigt den EXAKTEN Blumentopf, "
                f"den du in der neuen Szene verwenden sollst. "
                f"Übernimm den Topf GENAU so wie er im Referenzbild aussieht — "
                f"gleiche Form, Farbe, Größe, Gravur. Verändere den Topf NICHT. "
                f"\n\nDer Topf hat die Gravur '{engraving_text}' in {engraving_style}. "
                f"Die Gravur muss EXAKT wie im Referenzbild aussehen. "
                f"\n\nGrößenverhältnis: Der Topf ist klein, ca. 14cm hoch — "
                f"passt bequem in eine Erwachsenen-Hand. "
                f"\n\nNEUE SZENE: {scene_prompt} "
                f"\n\nSzenen-Kontext: {scene_description}. "
                f"\n\nBildanforderungen: Professionelles Produktfoto, hohe Qualität, "
                f"professionelle Beleuchtung, warme Atmosphäre. "
                f"Die Gravur '{engraving_text}' muss klar lesbar sein. "
                f"Quadratisches Format."
            )
        else:
            # Fallback ohne Basis-Topf (wie bisher)
            prompt = (
                f"WICHTIG - Der Blumentopf muss auf JEDEM Bild IDENTISCH aussehen: "
                f"{pot_desc}. "
                f"Auf dem Topf ist in {engraving_style} die Gravur {spelled_text} eingraviert. "
                f"Die Gravur ist in den Ton eingeritzt (nicht aufgemalt). "
                f"Der Topf ist ein kleiner Blumentopf — passt bequem in eine Hand. "
                f"\n\nSzene: {scene_prompt} "
                f"\n\nSzenen-Kontext: {scene_description}. "
                f"\n\nBildanforderungen: Professionelles Produktfoto, hohe Qualität, "
                f"professionelle Beleuchtung, warme Atmosphäre. "
                f"Die Gravur '{engraving_text}' muss klar lesbar sein. "
                f"Quadratisches Format."
            )

        try:
            result = self.gemini_service.generate_image(
                prompt=prompt,
                reference_image=reference_image,
                width=1024,
                height=1024,
                model=self._get_model(),
            )
            return result
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {'success': False, 'error': str(e)}

    def save_generated_image(self, image_base64: str, filename: str) -> str:
        """
        Speichert ein generiertes Bild als Datei.

        Args:
            image_base64: Base64-kodierte Bilddaten
            filename: Gewünschter Dateiname

        Returns:
            Relativer Dateipfad zum gespeicherten Bild
        """
        from django.conf import settings as django_settings

        now = datetime.now()
        rel_path = f"ploom/workflow_images/{now.year}/{now.month:02d}"
        full_dir = os.path.join(django_settings.MEDIA_ROOT, rel_path)
        os.makedirs(full_dir, exist_ok=True)

        # Dateiname eindeutig machen
        base, ext = os.path.splitext(filename)
        if not ext:
            ext = '.png'
        unique_filename = f"{base}_{now.strftime('%H%M%S')}{ext}"
        full_path = os.path.join(full_dir, unique_filename)

        # Speichern
        image_data = base64.b64decode(image_base64)
        with open(full_path, 'wb') as f:
            f.write(image_data)

        return f"{rel_path}/{unique_filename}"
