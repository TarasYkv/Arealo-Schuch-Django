
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage

User = get_user_model()

def send_system_message(user_id, message_content):
    """
    Sends a system message to a specific user.
    Finds or creates a 1-on-1 chat room between the 'system' user and the target user.
    """
    try:
        # Get the user to notify
        target_user = User.objects.get(id=user_id)

        # Get the system user (assuming a user with username 'system' exists)
        system_user, _ = User.objects.get_or_create(
            username='system',
            defaults={'first_name': 'System', 'last_name': 'Bot', 'is_staff': True}
        )

        # Find or create a 1-on-1 chat room
        # A simple way to get a unique room for two users is to sort their IDs
        user_ids = sorted([system_user.id, target_user.id])
        room_name = f"dm_{user_ids[0]}_{user_ids[1]}"

        chat_room, created = ChatRoom.objects.get_or_create(
            name=room_name,
            defaults={'is_group_chat': False, 'created_by': system_user}
        )

        if created:
            chat_room.participants.add(system_user, target_user)

        # Create the system message
        message = ChatMessage.objects.create(
            chat_room=chat_room,
            sender=system_user,
            content=message_content,
            is_system_message=True
        )

        # Schedule email notification for system messages too
        from .email_service import ChatEmailNotificationService
        ChatEmailNotificationService.schedule_notification_for_message(message)

        return True, f"Message sent to {target_user.username}"

    except User.DoesNotExist:
        return False, "User not found."
    except Exception as e:
        return False, f"An error occurred: {str(e)}"

