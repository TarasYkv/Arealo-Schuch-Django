from django import template
from django.utils.safestring import mark_safe
from ..models import GlobalMessage

register = template.Library()


@register.inclusion_tag('superconfig/includes/global_messages_scripts.html', takes_context=True)
def global_messages_scripts(context):
    """
    Include the necessary CSS and JavaScript for global messages
    """
    return {
        'request': context.get('request'),
        'user': context.get('user'),
    }


@register.simple_tag(takes_context=True)
def load_global_messages_css():
    """
    Load the CSS for global messages
    """
    return mark_safe('''
        <link rel="stylesheet" href="/static/css/global-messages.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    ''')


@register.simple_tag(takes_context=True)
def load_global_messages_js():
    """
    Load the JavaScript for global messages
    """
    return mark_safe('''
        <script src="/static/js/global-messages.js"></script>
    ''')


@register.filter
def has_active_global_messages(user):
    """
    Check if there are active global messages for the current user
    """
    try:
        messages = GlobalMessage.get_active_messages_for_user(user)
        return len(messages) > 0
    except:
        return False


@register.simple_tag(takes_context=True)
def get_active_global_messages_count(context):
    """
    Get the count of active global messages for the current user
    """
    try:
        user = context.get('user')
        if user:
            messages = GlobalMessage.get_active_messages_for_user(user)
            return len(messages)
        else:
            # For anonymous users
            messages = GlobalMessage.get_active_messages_for_user(None)
            return len(messages)
    except:
        return 0


@register.inclusion_tag('superconfig/includes/global_messages_debug.html', takes_context=True)
def global_messages_debug_info(context):
    """
    Debug information for global messages - controlled by GlobalMessageDebugSettings
    """
    from ..models import GlobalMessageDebugSettings

    user = context.get('user')

    try:
        # Get debug settings
        debug_settings = GlobalMessageDebugSettings.get_settings()

        # Check if debug should be shown for this user
        if not debug_settings or not debug_settings.should_show_debug_for_user(user):
            return {}

        all_messages = GlobalMessage.objects.all()
        active_messages = GlobalMessage.get_active_messages_for_user(user)

        debug_context = {
            'debug': True,
            'debug_settings': debug_settings,
        }

        # Add statistics if enabled
        if debug_settings.show_statistics:
            debug_context.update({
                'all_messages_count': all_messages.count(),
                'active_messages_count': len(active_messages),
            })

        # Add user info if enabled
        if debug_settings.show_user_info:
            debug_context.update({
                'user': user,
                'is_authenticated': user.is_authenticated if user else False,
            })

        # Add message details if enabled
        if debug_settings.show_message_details:
            debug_context.update({
                'messages': active_messages[:3]  # Show first 3 for debug
            })

        return debug_context

    except Exception as e:
        return {
            'debug': True,
            'error': f'Could not load debug info: {str(e)}'
        }