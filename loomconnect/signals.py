from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import ConnectRequest, Connection
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ConnectRequest)
def create_chat_on_accept(sender, instance, created, **kwargs):
    """
    Erstellt automatisch einen ChatRoom wenn eine ConnectRequest akzeptiert wird
    """
    # Nur wenn Request gerade akzeptiert wurde und noch kein ChatRoom existiert
    if instance.status == 'accepted' and not instance.chat_room:
        from chat.models import ChatRoom

        # ChatRoom erstellen
        room_name = f"{instance.from_profile.user.username} & {instance.to_profile.user.username}"

        chat_room = ChatRoom.objects.create(
            name=room_name,
            created_by=instance.from_profile.user,
            is_group_chat=False
        )

        # Participants hinzufügen
        chat_room.participants.add(
            instance.from_profile.user,
            instance.to_profile.user
        )

        # ChatRoom mit Request verknüpfen
        instance.chat_room = chat_room
        instance.save(update_fields=['chat_room'])

        # Connection erstellen
        Connection.objects.create(
            profile_1=instance.from_profile,
            profile_2=instance.to_profile,
            chat_room=chat_room,
            connect_request=instance
        )

        # Karma-Score erhöhen
        instance.from_profile.karma_score += 5
        instance.from_profile.successful_connections += 1
        instance.from_profile.save(update_fields=['karma_score', 'successful_connections'])

        instance.to_profile.karma_score += 5
        instance.to_profile.successful_connections += 1
        instance.to_profile.save(update_fields=['karma_score', 'successful_connections'])

        # Email-Benachrichtigung: Verbindung akzeptiert (an den Anfragenden)
        if instance.from_profile.notify_new_matches:
            send_connection_accepted_email(instance)


@receiver(post_save, sender=Connection)
def update_profile_stats_on_connection(sender, instance, created, **kwargs):
    """
    Aktualisiert Profil-Statistiken bei neuer Verbindung
    """
    if created:
        # Update connection counts (falls nicht schon durch Signal oben gemacht)
        pass


# Email notification helper functions
def send_connection_accepted_email(connect_request):
    """Send email when connection request is accepted"""
    try:
        from email_templates.trigger_manager import TriggerManager
        from django.contrib.sites.models import Site

        trigger_manager = TriggerManager()
        current_site = Site.objects.get_current()

        # Email an den Anfragenden (from_profile)
        context_data = {
            'user_name': connect_request.from_profile.user.get_full_name() or connect_request.from_profile.user.username,
            'accepter_username': connect_request.to_profile.user.username,
            'accepter_name': connect_request.to_profile.user.get_full_name() or connect_request.to_profile.user.username,
            'accepter_bio': connect_request.to_profile.bio[:200] if connect_request.to_profile.bio else '',
            'chat_url': f"https://{current_site.domain}/chat/room/{connect_request.chat_room.id}/" if connect_request.chat_room else '',
            'profile_url': f"https://{current_site.domain}/connect/profile/{connect_request.to_profile.user.username}/",
            'site_url': f"https://{current_site.domain}"
        }

        trigger_manager.fire_trigger(
            trigger_key='loomconnect_connection_accepted',
            context_data=context_data,
            recipient_email=connect_request.from_profile.user.email,
            recipient_name=connect_request.from_profile.user.get_full_name(),
            sent_by=None
        )

        logger.info(f"Sent connection accepted email to {connect_request.from_profile.user.email}")
    except Exception as e:
        logger.error(f"Failed to send connection accepted email: {str(e)}")


def send_new_message_email(chat_message):
    """Send email when new chat message is received"""
    try:
        from email_templates.trigger_manager import TriggerManager
        from django.contrib.sites.models import Site

        # Nur wenn LoomConnect-Connection
        if not hasattr(chat_message.chat_room, 'connection'):
            return

        trigger_manager = TriggerManager()
        current_site = Site.objects.get_current()

        # Email an alle Teilnehmer außer dem Sender
        for participant in chat_message.chat_room.participants.exclude(id=chat_message.sender.id):
            # Prüfe ob User LoomConnect-Profile hat und Benachrichtigungen aktiviert hat
            if hasattr(participant, 'connect_profile') and participant.connect_profile.notify_messages:
                # Ungelesene Nachrichten zählen
                from chat.models import ChatMessage
                unread_count = ChatMessage.objects.filter(
                    chat_room=chat_message.chat_room,
                    is_read=False
                ).exclude(sender=participant).count()

                context_data = {
                    'user_name': participant.get_full_name() or participant.username,
                    'sender_username': chat_message.sender.username,
                    'sender_name': chat_message.sender.get_full_name() or chat_message.sender.username,
                    'message_preview': chat_message.message[:100] + '...' if len(chat_message.message) > 100 else chat_message.message,
                    'chat_room_name': chat_message.chat_room.name,
                    'chat_url': f"https://{current_site.domain}/chat/room/{chat_message.chat_room.id}/",
                    'unread_count': str(unread_count),
                    'site_url': f"https://{current_site.domain}"
                }

                trigger_manager.fire_trigger(
                    trigger_key='loomconnect_new_message',
                    context_data=context_data,
                    recipient_email=participant.email,
                    recipient_name=participant.get_full_name(),
                    sent_by=chat_message.sender
                )

                logger.info(f"Sent new message email to {participant.email}")
    except Exception as e:
        logger.error(f"Failed to send new message email: {str(e)}")
