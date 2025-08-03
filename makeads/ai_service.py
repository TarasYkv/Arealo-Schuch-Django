import json
import requests
import openai
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from .models import Campaign, Creative, AIService, GenerationJob
from .api_client import CentralAPIClient
from .image_utils import download_and_store_dalle_image
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class AICreativeGenerator:
    """
    Service für die KI-gestützte Creative-Generierung
    """
    
    def __init__(self, user: User):
        self.user = user
        # Verwende den zentralen API-Client
        self.api_client = CentralAPIClient(user)
        
        # Hole API-Keys über den zentralen Client
        api_keys = self.api_client.get_api_keys()
        self.openai_api_key = api_keys.get('openai')
        self.anthropic_api_key = api_keys.get('anthropic')
        self.google_api_key = api_keys.get('google')
        
        # Debug-Ausgabe für API-Key Status
        logger.info(f"AICreativeGenerator für User {user.username} initialisiert:")
        logger.info(f"  - OpenAI: {'✓ verfügbar' if self.openai_api_key else '✗ nicht konfiguriert'}")
        logger.info(f"  - Anthropic: {'✓ verfügbar' if self.anthropic_api_key else '✗ nicht konfiguriert'}")
        logger.info(f"  - Google: {'✓ verfügbar' if self.google_api_key else '✗ nicht konfiguriert'}")
    
    def generate_creatives(
        self, 
        campaign: Campaign, 
        count: int = 10,
        ai_service: str = 'openai',
        style_preference: str = 'modern',
        color_scheme: str = 'vibrant',
        target_audience: str = '',
        custom_instructions: str = '',
        existing_examples: List[Dict] = None
    ) -> List[Creative]:
        """
        Generiert Creatives für eine Kampagne
        """
        try:
            # Generation Job erstellen
            job = GenerationJob.objects.create(
                campaign=campaign,
                job_type='initial',
                target_count=count,
                status='processing'
            )
            
            # Prompt für Text-Generierung erstellen
            text_prompt = self._build_text_prompt(
                campaign, style_preference, target_audience, custom_instructions, existing_examples
            )
            
            # Image-Prompt erstellen
            image_prompt = self._build_image_prompt(
                campaign, style_preference, color_scheme
            )
            
            creatives = []
            batch_number = self._get_next_batch_number(campaign)
            
            for i in range(count):
                try:
                    # Text generieren
                    creative_text = self._generate_text(text_prompt, ai_service)
                    
                    # Bild generieren
                    image_url = self._generate_image(image_prompt, ai_service)
                    
                    # Creative erstellen
                    creative = Creative.objects.create(
                        campaign=campaign,
                        title=f"Creative {i+1}",
                        description=creative_text.get('description', ''),
                        text_content=creative_text.get('content', ''),
                        image_url=image_url,
                        ai_prompt_used=json.dumps({
                            'text_prompt': text_prompt,
                            'image_prompt': image_prompt
                        }),
                        generation_status='completed',
                        generation_batch=batch_number
                    )
                    
                    # DALL-E Bild sofort lokal speichern um 403-Fehler zu vermeiden
                    if image_url and ('openai' in image_url or 'dalle' in image_url.lower()):
                        logger.info(f"Downloading DALL-E image for Creative {creative.id}")
                        local_path = download_and_store_dalle_image(image_url, str(creative.id))
                        if local_path:
                            creative.image_file.name = local_path
                            creative.save(update_fields=['image_file'])
                            logger.info(f"✅ DALL-E image stored locally for Creative {creative.id}")
                        else:
                            logger.warning(f"⚠️ Failed to download DALL-E image for Creative {creative.id}")
                    
                    creatives.append(creative)
                    
                    # Job-Fortschritt aktualisieren
                    job.generated_count = i + 1
                    job.save()
                    
                except Exception as e:
                    logger.error(f"Fehler bei Creative-Generierung {i+1}: {str(e)}")
                    continue
            
            # Job als abgeschlossen markieren
            job.status = 'completed'
            job.save()
            
            return creatives
            
        except Exception as e:
            logger.error(f"Fehler bei Creative-Generierung: {str(e)}")
            if 'job' in locals():
                job.status = 'failed'
                job.error_message = str(e)
                job.save()
            return []
    
    def generate_more_creatives(
        self, 
        campaign: Campaign, 
        count: int = 5,
        **kwargs
    ) -> List[Creative]:
        """
        Generiert weitere Creatives für eine bestehende Kampagne
        """
        # Batch-Nummer für neue Creatives
        batch_number = self._get_next_batch_number(campaign)
        
        # Bestehende Creatives analysieren für bessere Prompts
        existing_creatives = campaign.creatives.filter(
            generation_status='completed'
        ).order_by('-created_at')[:5]
        
        # Prompt basierend auf bestehenden Creatives anpassen
        kwargs['existing_examples'] = [
            {
                'title': c.title,
                'text': c.text_content,
                'description': c.description
            }
            for c in existing_creatives
        ]
        
        # Übergebe alle Parameter explizit an generate_creatives
        return self.generate_creatives(
            campaign=campaign, 
            count=count, 
            ai_service=kwargs.get('ai_service', 'openai'),
            style_preference=kwargs.get('style_preference', 'modern'),
            color_scheme=kwargs.get('color_scheme', 'vibrant'),
            target_audience=kwargs.get('target_audience', ''),
            custom_instructions=kwargs.get('custom_instructions', ''),
            existing_examples=kwargs.get('existing_examples')
        )
    
    def revise_creative(
        self, 
        original_creative: Creative,
        revision_instructions: str,
        revision_type: str = 'both'
    ) -> Optional[Creative]:
        """
        Überarbeitet ein bestehendes Creative
        """
        try:
            campaign = original_creative.campaign
            
            # Revision-Prompt erstellen
            if revision_type in ['text_only', 'both']:
                text_prompt = self._build_revision_text_prompt(
                    original_creative, revision_instructions
                )
                new_text = self._generate_text(text_prompt, 'openai')
            else:
                new_text = {
                    'content': original_creative.text_content,
                    'description': original_creative.description
                }
            
            if revision_type in ['image_only', 'both']:
                image_prompt = self._build_revision_image_prompt(
                    original_creative, revision_instructions
                )
                new_image_url = self._generate_image(image_prompt, 'openai')
            else:
                new_image_url = original_creative.image_url
            
            # Überarbeitetes Creative erstellen
            revised_creative = Creative.objects.create(
                campaign=campaign,
                title=f"{original_creative.title} (Überarbeitet)",
                description=new_text.get('description', original_creative.description),
                text_content=new_text.get('content', original_creative.text_content),
                image_url=new_image_url,
                ai_prompt_used=json.dumps({
                    'revision_instructions': revision_instructions,
                    'original_creative_id': str(original_creative.id)
                }),
                generation_status='completed',
                generation_batch=original_creative.generation_batch
            )
            
            # DALL-E Bild sofort lokal speichern um 403-Fehler zu vermeiden
            if new_image_url and ('openai' in new_image_url or 'dalle' in new_image_url.lower()):
                logger.info(f"Downloading DALL-E image for revised Creative {revised_creative.id}")
                local_path = download_and_store_dalle_image(new_image_url, str(revised_creative.id))
                if local_path:
                    revised_creative.image_file.name = local_path
                    revised_creative.save(update_fields=['image_file'])
                    logger.info(f"✅ DALL-E image stored locally for revised Creative {revised_creative.id}")
                else:
                    logger.warning(f"⚠️ Failed to download DALL-E image for revised Creative {revised_creative.id}")
            
            return revised_creative
            
        except Exception as e:
            logger.error(f"Fehler bei Creative-Überarbeitung: {str(e)}")
            return None
    
    def _build_text_prompt(
        self, 
        campaign: Campaign,
        style_preference: str,
        target_audience: str,
        custom_instructions: str,
        existing_examples: List[Dict] = None
    ) -> str:
        """
        Erstellt den Prompt für Text-Generierung
        """
        prompt = f"""
        Erstelle einen ansprechenden Werbetext für folgende Kampagne:
        
        Kampagne: {campaign.name}
        Grundidee: {campaign.basic_idea}
        Detailbeschreibung: {campaign.detailed_description or 'Nicht angegeben'}
        
        Stil: {style_preference}
        Zielgruppe: {target_audience or 'Allgemein'}
        
        Zusätzliche Informationen: {campaign.additional_info or 'Keine'}
        Spezielle Anweisungen: {custom_instructions or 'Keine'}
        
        Erstelle einen kreativen Werbetext, der:
        1. Aufmerksamkeit erregt
        2. Die Hauptbotschaft klar vermittelt
        3. Zur Aktion motiviert
        4. Zum gewählten Stil passt
        5. Die Zielgruppe anspricht
        
        Antworte im JSON-Format:
        {{
            "content": "Der Haupttext für das Creative",
            "description": "Eine kurze Beschreibung des Creative-Konzepts"
        }}
        """
        
        if existing_examples:
            prompt += "\n\nBerücksichtige diese bestehenden Beispiele für Konsistenz:\n"
            for example in existing_examples:
                prompt += f"- {example['title']}: {example['text'][:100]}...\n"
        
        return prompt.strip()
    
    def _build_image_prompt(
        self, 
        campaign: Campaign,
        style_preference: str,
        color_scheme: str
    ) -> str:
        """
        Erstellt den Prompt für Bild-Generierung
        """
        prompt = f"""
        Create an advertising image for: {campaign.basic_idea}
        
        Style: {style_preference}
        Color scheme: {color_scheme}
        
        Requirements:
        - High quality, professional advertising image
        - Clear visual hierarchy
        - Suitable for digital advertising
        - Engaging and eye-catching
        - {style_preference} design aesthetic
        - {color_scheme} color palette
        
        Additional context: {campaign.detailed_description or ''}
        """
        
        return prompt.strip()
    
    def _build_revision_text_prompt(
        self, 
        original_creative: Creative,
        revision_instructions: str
    ) -> str:
        """
        Erstellt Prompt für Text-Überarbeitung
        """
        return f"""
        Überarbeite folgenden Werbetext basierend auf den Anweisungen:
        
        Original Text: {original_creative.text_content}
        Original Beschreibung: {original_creative.description}
        
        Überarbeitungsanweisungen: {revision_instructions}
        
        Antworte im JSON-Format:
        {{
            "content": "Der überarbeitete Haupttext",
            "description": "Überarbeitete Beschreibung"
        }}
        """
    
    def _build_revision_image_prompt(
        self, 
        original_creative: Creative,
        revision_instructions: str
    ) -> str:
        """
        Erstellt Prompt für Bild-Überarbeitung
        """
        return f"""
        Revise this advertising image concept based on instructions:
        
        Original concept: {original_creative.description}
        Revision instructions: {revision_instructions}
        
        Create a new advertising image that incorporates these changes while maintaining professional quality.
        """
    
    def _generate_text(self, prompt: str, ai_service: str) -> Dict[str, str]:
        """
        Generiert Text mit der gewählten KI
        """
        logger.info(f"Text-Generierung angefordert - Service: {ai_service}")
        
        if ai_service == 'openai':
            if self.openai_api_key:
                logger.info("Verwende OpenAI für Text-Generierung")
                return self._generate_text_openai(prompt)
            else:
                logger.warning("OpenAI angefordert, aber kein API-Key verfügbar - verwende Mock")
        elif ai_service == 'claude':
            if self.anthropic_api_key:
                logger.info("Verwende Claude für Text-Generierung")
                return self._generate_text_claude(prompt)
            else:
                logger.warning("Claude angefordert, aber kein API-Key verfügbar - verwende Mock")
        elif ai_service == 'google':
            if self.google_api_key:
                logger.info("Verwende Google AI für Text-Generierung")
                return self._generate_text_google(prompt)
            else:
                logger.warning("Google AI angefordert, aber kein API-Key verfügbar - verwende Mock")
        
        # Fallback für Demo-Zwecke
        logger.info("Verwende Mock-Text-Generierung")
        return self._generate_mock_text(prompt)
    
    def _generate_image(self, prompt: str, ai_service: str) -> str:
        """
        Generiert Bild mit der gewählten KI
        """
        logger.info(f"Bildgenerierung angefordert - Service: {ai_service}")
        
        if ai_service == 'openai':
            if self.openai_api_key:
                logger.info("Verwende DALL-E für Bildgenerierung")
                return self._generate_image_dalle(prompt)
            else:
                logger.warning("OpenAI angefordert, aber kein API-Key verfügbar - verwende Mock-Bild")
        else:
            logger.info(f"Service {ai_service} noch nicht für Bildgenerierung implementiert - verwende Mock")
        
        # Fallback für Demo-Zwecke
        logger.info("Verwende Mock-Bildgenerierung")
        return self._generate_mock_image(prompt)
    
    def _generate_text_openai(self, prompt: str) -> Dict[str, str]:
        """
        Text-Generierung mit OpenAI (aktualisierte API)
        """
        try:
            from openai import OpenAI
            
            # OpenAI Client mit API-Key initialisieren
            client = OpenAI(api_key=self.openai_api_key)
            
            logger.info(f"Starte OpenAI Text-Generierung für User {self.user.username}")
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Du bist ein kreativer Werbetexter. Antworte immer im JSON-Format mit 'content' und 'description' Feldern."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            logger.info(f"OpenAI Text erfolgreich generiert: {content[:100]}...")
            
            # JSON-Antwort parsen
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                # Fallback wenn nicht JSON
                return {
                    "content": content,
                    "description": "KI-generierter Werbetext"
                }
                
        except Exception as e:
            logger.error(f"OpenAI Text-Generierung Fehler: {str(e)}")
            logger.error(f"API-Key verfügbar: {bool(self.openai_api_key)}")
            return self._generate_mock_text(prompt)
    
    def _generate_image_dalle(self, prompt: str) -> str:
        """
        Bild-Generierung mit DALL-E (aktualisierte API)
        """
        try:
            from openai import OpenAI
            
            # OpenAI Client mit API-Key initialisieren
            client = OpenAI(api_key=self.openai_api_key)
            
            logger.info(f"Starte DALL-E Bildgenerierung für User {self.user.username}")
            logger.info(f"Prompt: {prompt[:100]}...")
            
            response = client.images.generate(
                model="dall-e-3",  # Neuestes DALL-E Modell
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            logger.info(f"DALL-E Bild erfolgreich generiert: {image_url}")
            
            return image_url
            
        except Exception as e:
            logger.error(f"DALL-E Bild-Generierung Fehler: {str(e)}")
            logger.error(f"API-Key verfügbar: {bool(self.openai_api_key)}")
            logger.error(f"Prompt: {prompt}")
            # Fallback zu DALL-E 2 versuchen
            try:
                response = client.images.generate(
                    model="dall-e-2",
                    prompt=prompt[:1000],  # DALL-E 2 hat kürzere Prompt-Limits
                    size="1024x1024",
                    n=1,
                )
                image_url = response.data[0].url
                logger.info(f"DALL-E 2 Fallback erfolgreich: {image_url}")
                return image_url
            except Exception as e2:
                logger.error(f"DALL-E 2 Fallback auch fehlgeschlagen: {str(e2)}")
                return self._generate_mock_image(prompt)
    
    def _generate_text_claude(self, prompt: str) -> Dict[str, str]:
        """
        Text-Generierung mit Claude (Placeholder)
        """
        # TODO: Implementierung der Claude API
        return self._generate_mock_text(prompt)
    
    def _generate_text_google(self, prompt: str) -> Dict[str, str]:
        """
        Text-Generierung mit Google AI (Placeholder)
        """
        # TODO: Implementierung der Google AI API
        return self._generate_mock_text(prompt)
    
    def _generate_mock_text(self, prompt: str) -> Dict[str, str]:
        """
        Mock Text-Generierung für Demo-Zwecke
        """
        import random
        
        mock_contents = [
            "🚀 Revolutioniere dein Business! Entdecke unsere innovative Lösung und steigere deinen Erfolg um 300%!",
            "✨ Das Geheimnis erfolgreicher Unternehmen! Jetzt verfügbar und nur für kurze Zeit zum Sonderpreis!",
            "🎯 Erreiche deine Ziele schneller als je zuvor! Mit unserer bewährten Methode zum garantierten Erfolg!",
            "💡 Innovation trifft auf Effizienz! Transformiere deine Arbeitsweise mit unserem bahnbrechenden Tool!",
            "🌟 Werde zum Marktführer! Nutze die Chance und sichere dir deinen Wettbewerbsvorteil!"
        ]
        
        mock_descriptions = [
            "Dynamisches Creative mit kraftvoller Call-to-Action",
            "Emotionales Marketing-Creative für maximale Conversion",
            "Professionelles Business-Creative mit modernem Design",
            "Innovatives Product-Creative für Tech-Zielgruppe",
            "Motivierendes Service-Creative mit persönlicher Note"
        ]
        
        return {
            "content": random.choice(mock_contents),
            "description": random.choice(mock_descriptions)
        }
    
    def _generate_mock_image(self, prompt: str) -> str:
        """
        Mock Bild-URL für Demo-Zwecke
        Erstellt aussagekräftige Placeholder-Bilder die zeigen, dass kein echter API-Key verwendet wird
        """
        import random
        import urllib.parse
        
        # Verschiedene Warnmeldungen für Mock-Bilder
        warning_messages = [
            "DEMO+MODE+-+Configure+OpenAI+API+Key",
            "No+API+Key+-+Mock+Image",
            "Add+OpenAI+Key+for+Real+Images",
            "Test+Mode+-+Not+Real+AI+Generated"
        ]
        
        # Wähle zufällige Eigenschaften
        size = random.choice(['1024x1024', '800x600', '1200x800'])
        bg_color = random.choice(['FF6B6B', '4ECDC4', 'FFE66D', '95E1D3', 'A8E6CF'])
        text_color = '000000' if bg_color in ['FFE66D', '95E1D3', 'A8E6CF'] else 'FFFFFF'
        warning = random.choice(warning_messages)
        
        # Erstelle aussagekräftige URL
        mock_url = f"https://via.placeholder.com/{size}/{bg_color}/{text_color}?text={warning}"
        
        logger.warning(f"Mock-Bild generiert für User {self.user.username}: {mock_url}")
        logger.warning("Konfigurieren Sie einen OpenAI API-Key für echte DALL-E Bilder!")
        
        return mock_url
    
    def _get_next_batch_number(self, campaign: Campaign) -> int:
        """
        Ermittelt die nächste Batch-Nummer für Creatives
        """
        last_batch = campaign.creatives.aggregate(
            max_batch=models.Max('generation_batch')
        )['max_batch']
        
        return (last_batch or 0) + 1