from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from organization.models import Event, EventReminder
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
import asyncio

User = get_user_model()


class Command(BaseCommand):
    help = 'Sendet Terminerinnerungen über das Chat-System'

    def handle(self, *args, **options):
        asyncio.run(self.send_reminders())

    async def send_reminders(self):
        channel_layer = get_channel_layer()
        now = timezone.now()
        
        # Finde alle Events, die eine Erinnerung benötigen
        events = Event.objects.filter(
            start_time__gt=now,
            start_time__lte=now + timezone.timedelta(minutes=60)  # Nächste Stunde
        )
        
        for event in events:
            reminder_time = event.start_time - timezone.timedelta(minutes=event.reminder_minutes)
            
            # Prüfe ob Erinnerung gesendet werden sollte
            if now >= reminder_time:
                # Erinnerung für Organisator
                await self.send_reminder_to_user(channel_layer, event, event.organizer)
                
                # Erinnerung für alle Teilnehmer
                for participant in event.participants.all():
                    await self.send_reminder_to_user(channel_layer, event, participant)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Erinnerung für Event "{event.title}" gesendet')
                )

    async def send_reminder_to_user(self, channel_layer, event, user):
        # Prüfe ob Erinnerung bereits gesendet wurde
        reminder, created = EventReminder.objects.get_or_create(
            event=event,
            user=user,
            defaults={
                'reminder_time': timezone.now(),
                'is_sent': False
            }
        )
        
        if not reminder.is_sent:
            message = f"🔔 Erinnerung: '{event.title}' beginnt in {event.reminder_minutes} Minuten"
            if event.location:
                message += f" (Ort: {event.location})"
            
            # Sende Nachricht an User's WebSocket
            await channel_layer.group_send(
                f'user_{user.id}',
                {
                    'type': 'reminder_message',
                    'message': message,
                    'event_id': event.id,
                    'event_title': event.title,
                    'event_start_time': event.start_time.isoformat(),
                    'event_location': event.location or '',
                }
            )
            
            # Markiere Erinnerung als gesendet
            reminder.is_sent = True
            reminder.sent_at = timezone.now()
            reminder.save()
            
            self.stdout.write(f'Erinnerung an {user.username} gesendet')