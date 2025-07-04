from django import template

register = template.Library()

@register.filter
def get_other_participant(room, user):
    """Template filter to get the other participant in a private chat"""
    if room and not room.is_group_chat:
        return room.participants.exclude(id=user.id).first()
    return None