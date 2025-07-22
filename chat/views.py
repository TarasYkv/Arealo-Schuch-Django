from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
import json

from .models import ChatRoom, ChatMessage, ChatRoomParticipant, ChatMessageRead, ChatMessageAttachment
from .agora_utils import generate_agora_token
from accounts.decorators import require_app_permission

User = get_user_model()


@login_required
def schuch_dashboard(request):
    """
    Schuch Dashboard with the 4 specific sections: Ampel-Kategorien, Quick Links, Meine Kategorien, Tipps
    """
    from accounts.models import AmpelCategory
    from django.contrib import messages
    
    # Handle POST request for settings
    if request.method == 'POST':
        # Toggle für benutzerdefinierte Kategorien
        use_custom = request.POST.get('use_custom_categories') == 'on'
        request.user.use_custom_categories = use_custom
        
        # Toggle für KI-Keyword-Erweiterung
        enable_ai_expansion = request.POST.get('enable_ai_keyword_expansion') == 'on'
        request.user.enable_ai_keyword_expansion = enable_ai_expansion
        
        request.user.save()
        
        # Feedback-Nachrichten
        if use_custom:
            messages.success(request, 'Benutzerdefinierte Kategorien wurden aktiviert.')
        else:
            messages.info(request, 'Standard-Kategorien werden verwendet.')
            
        if enable_ai_expansion and use_custom:
            messages.success(request, 'KI-Keyword-Erweiterung für Ihre Kategorien wurde aktiviert.')
        elif enable_ai_expansion and not use_custom:
            messages.warning(request, 'KI-Erweiterung ist nur mit benutzerdefinierten Kategorien verfügbar.')
        else:
            messages.info(request, 'KI-Keyword-Erweiterung wurde deaktiviert.')
        
        return redirect('chat:schuch_dashboard')
    
    # Get user's categories
    categories = AmpelCategory.objects.filter(user=request.user)
    
    context = {
        'categories': categories,
        'use_custom_categories': getattr(request.user, 'use_custom_categories', False),
        'enable_ai_keyword_expansion': getattr(request.user, 'enable_ai_keyword_expansion', False),
    }
    
    return render(request, 'chat/schuch_dashboard.html', context)


@require_app_permission('chat')
def chat_home(request):
    """
    Stable chat interface without scrollbar jumping issues
    """
    # Get all chat rooms for the current user
    chat_rooms = ChatRoom.objects.filter(
        participants=request.user
    ).annotate(
        message_count=Count('messages'),
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_at', '-created_at')
    
    # Get unread counts and other data for each chat room
    for room in chat_rooms:
        room.unread_count = room.get_unread_count(request.user)
        
        # Set proper room name and user info
        if room.is_group_chat:
            room.avatar_text = "👥"
            room.display_name = room.name or f"Gruppenchat ({room.participants.count()} Teilnehmer)"
            room.online_status = "group"
        else:
            other_user = room.get_other_participant(request.user)
            if other_user:
                # Set display name
                room.display_name = other_user.get_full_name() or other_user.username
                
                # Set profile picture or create initials
                if other_user.profile_picture:
                    room.profile_picture_url = other_user.profile_picture.url
                    room.avatar_text = ""  # Use picture instead of text
                else:
                    room.profile_picture_url = None
                    # Create initials from first/last name or username
                    if other_user.first_name and other_user.last_name:
                        room.avatar_text = (other_user.first_name[:1] + other_user.last_name[:1]).upper()
                    else:
                        room.avatar_text = other_user.username[:2].upper()
                
                # Set online status
                if other_user.is_currently_online():
                    room.online_status = "online"
                    room.online_status_text = "Online"
                    room.online_status_class = "text-success"
                else:
                    room.online_status = "offline"
                    room.online_status_text = "Offline"
                    room.online_status_class = "text-muted"
            else:
                room.avatar_text = "💬"
                room.display_name = "Unbekannter Chat"
                room.online_status = "unknown"
        
        # Get last message preview
        last_message = room.messages.order_by('-created_at').first()
        if last_message:
            room.last_message = last_message.content[:50] + ('...' if len(last_message.content) > 50 else '')
        else:
            room.last_message = ""
    
    # Get recent users for starting new chats
    recent_users = User.objects.exclude(
        id=request.user.id
    ).order_by('-last_login')[:10]
    
    context = {
        'chat_rooms': chat_rooms,
        'recent_users': recent_users,
        'agora_app_id': settings.AGORA_APP_ID,
    }
    
    return render(request, 'chat/home_new.html', context)


# Stable chat function integrated into main chat_home function above


@login_required
def room_detail(request, room_id):
    """
    Display a specific chat room with messages
    """
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    
    # Check if user is participant
    if not chat_room.participants.filter(id=request.user.id).exists():
        raise Http404("Chat room not found")
    
    # Get messages with pagination
    messages_list = chat_room.messages.select_related('sender').order_by('created_at')
    paginator = Paginator(messages_list, 50)
    page_number = request.GET.get('page', 1)
    messages = paginator.get_page(page_number)
    
    # Mark messages as read
    unread_messages = chat_room.messages.exclude(
        read_by__user=request.user
    ).exclude(sender=request.user)
    
    for message in unread_messages:
        ChatMessageRead.objects.get_or_create(
            message=message,
            user=request.user
        )
    
    # Update last_read_at
    participant, created = ChatRoomParticipant.objects.get_or_create(
        chat_room=chat_room,
        user=request.user
    )
    participant.last_read_at = timezone.now()
    participant.save()
    
    context = {
        'chat_room': chat_room,
        'messages': messages,
        'participants': chat_room.participants.all(),
        'is_group_chat': chat_room.is_group_chat,
    }
    
    return render(request, 'chat/room_detail.html', context)


@login_required
def start_chat(request, user_id):
    """
    Start a new chat with a specific user
    """
    other_user = get_object_or_404(User, id=user_id)
    
    if other_user == request.user:
        messages.error(request, "Sie können nicht mit sich selbst chatten.")
        return redirect('chat:home')
    
    # Check if a private chat already exists
    existing_chat = ChatRoom.objects.filter(
        participants=request.user,
        is_group_chat=False
    ).filter(
        participants=other_user
    ).first()
    
    if existing_chat:
        return redirect(f'/chat/?room={existing_chat.id}')
    
    # Create new private chat
    chat_room = ChatRoom.objects.create(
        created_by=request.user,
        is_group_chat=False
    )
    
    # Add participants
    ChatRoomParticipant.objects.create(chat_room=chat_room, user=request.user)
    ChatRoomParticipant.objects.create(chat_room=chat_room, user=other_user)
    
    # Create welcome message
    welcome_message = ChatMessage.objects.create(
        chat_room=chat_room,
        sender=request.user,
        message_type='system',
        content=f"Chat gestartet zwischen {request.user.get_full_name() or request.user.username} und {other_user.get_full_name() or other_user.username}"
    )
    
    # Ensure last_message_at is set properly
    chat_room.last_message_at = welcome_message.created_at
    chat_room.save(update_fields=['last_message_at'])
    
    return redirect(f'/chat/?room={chat_room.id}')


@login_required
def user_search(request):
    """
    Search for users to start a chat with
    """
    query = request.GET.get('q', '').strip()
    users = []
    
    if query and len(query) >= 2:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(
            id=request.user.id
        ).order_by('username')[:20]
    
    context = {
        'users': users,
        'query': query,
    }
    
    return render(request, 'chat/user_search.html', context)


@login_required
@require_http_methods(["POST"])
def send_message(request, room_id):
    """
    Send a message to a chat room (AJAX endpoint)
    """
    try:
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        content = request.POST.get('content', '').strip()
        message_type = request.POST.get('message_type', 'text')
        reply_to_id = request.POST.get('reply_to')
        
        # Handle file uploads
        uploaded_files = request.FILES.getlist('attachments')
        
        if not content and not uploaded_files:
            return JsonResponse({'success': False, 'error': 'Nachricht oder Anhang erforderlich'})
        
        # Create message
        message = ChatMessage.objects.create(
            chat_room=chat_room,
            sender=request.user,
            content=content or '',
            message_type=message_type,
            reply_to_id=reply_to_id if reply_to_id else None
        )
        
        # Handle attachments
        attachments = []
        for uploaded_file in uploaded_files:
            attachment = ChatMessageAttachment.objects.create(
                message=message,
                file=uploaded_file,
                filename=uploaded_file.name,
                file_size=uploaded_file.size,
                file_type=uploaded_file.content_type
            )
            attachments.append({
                'id': attachment.id,
                'filename': attachment.filename,
                'file_size': attachment.get_file_size_display(),
                'file_type': attachment.file_type,
                'file_url': attachment.file.url,
                'is_image': attachment.is_image(),
                'is_video': attachment.is_video(),
                'is_audio': attachment.is_audio()
            })
        
        # Mark as read by sender
        ChatMessageRead.objects.create(
            message=message,
            user=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'sender': message.sender.get_full_name() or message.sender.username,
                'sender_name': message.sender.get_full_name() or message.sender.username,
                'sender_id': message.sender.id,
                'is_own': True,
                'formatted_time': message.get_formatted_time(),
                'message_type': message.message_type,
                'reply_to': message.reply_to.id if message.reply_to else None,
                'attachments': attachments
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_messages(request, room_id):
    """
    Get messages for a chat room (AJAX endpoint for polling)
    """
    try:
        print(f"DEBUG: Getting messages for room {room_id}")
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        since_id = request.GET.get('since_id')
        page = request.GET.get('page', 1)
        messages_per_page = 20
        
        try:
            page = int(page)
        except ValueError:
            page = 1
            
        if since_id:
            # Real-time updates - get messages newer than since_id
            messages_queryset = chat_room.messages.filter(
                id__gt=since_id
            ).select_related('sender').order_by('created_at')
            messages_list = list(messages_queryset)
            has_more = False
            total_messages = len(messages_list)
        else:
            # Initial load or pagination - get messages with pagination
            messages_queryset = chat_room.messages.select_related('sender').order_by('-created_at')
            
            # Apply pagination
            start_index = (page - 1) * messages_per_page
            end_index = start_index + messages_per_page
            
            messages_page = messages_queryset[start_index:end_index]
            messages_list = list(reversed(messages_page))  # Reverse for chronological order
            
            # Check if there are more messages
            total_messages = messages_queryset.count()
            has_more = total_messages > end_index
        
        print(f"DEBUG: Found {len(messages_list)} messages")
        messages_data = []
        for message in messages_list:
            # Handle anonymous messages (no sender)
            if message.sender:
                sender_name = message.sender.get_full_name() or message.sender.username
                sender_id = message.sender.id
                avatar_text = (message.sender.get_full_name() or message.sender.username)[0].upper()
            else:
                sender_name = message.sender_name or "Anonym"
                sender_id = None
                avatar_text = (message.sender_name or "A")[0].upper()
            
            # Get attachments
            attachments = []
            for attachment in message.attachments.all():
                attachments.append({
                    'id': attachment.id,
                    'filename': attachment.filename,
                    'file_size': attachment.get_file_size_display(),
                    'file_type': attachment.file_type,
                    'file_url': attachment.file.url,
                    'is_image': attachment.is_image(),
                    'is_video': attachment.is_video(),
                    'is_audio': attachment.is_audio()
                })
            
            messages_data.append({
                'id': message.id,
                'content': message.content,
                'sender': sender_name,
                'sender_name': sender_name,
                'sender_id': sender_id,
                'is_own': message.sender == request.user if message.sender else False,
                'timestamp': message.created_at.isoformat(),
                'formatted_time': message.created_at.strftime('%H:%M'),
                'message_type': message.message_type,
                'reply_to': message.reply_to.id if message.reply_to else None,
                'attachments': attachments
            })
        
        # Also return room info for chat header
        room_info = {
            'id': chat_room.id,
            'name': chat_room.name,
            'display_name': str(chat_room),
            'is_group_chat': chat_room.is_group_chat,
            'participant_count': chat_room.participants.count(),
            'avatar_text': 'G' if chat_room.is_group_chat else 'U'
        }
        
        print(f"DEBUG: Returning {len(messages_data)} messages")
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'room': room_info,
            'last_message_id': messages_list[-1].id if messages_list else None,
            'pagination': {
                'page': page,
                'messages_per_page': messages_per_page,
                'total_messages': total_messages,
                'has_more': has_more,
                'has_previous': page > 1
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def create_group_chat(request):
    """
    Create a new group chat
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        participant_ids = request.POST.getlist('participants')
        
        if not name:
            messages.error(request, "Gruppenname ist erforderlich.")
            return redirect('chat:create_group_chat')
        
        if len(participant_ids) < 2:
            messages.error(request, "Mindestens 2 Teilnehmer erforderlich.")
            return redirect('chat:create_group_chat')
        
        # Create group chat
        chat_room = ChatRoom.objects.create(
            name=name,
            created_by=request.user,
            is_group_chat=True
        )
        
        # Add creator as participant
        ChatRoomParticipant.objects.create(chat_room=chat_room, user=request.user)
        
        # Add selected participants
        for user_id in participant_ids:
            try:
                user = User.objects.get(id=user_id)
                ChatRoomParticipant.objects.create(chat_room=chat_room, user=user)
            except User.DoesNotExist:
                continue
        
        # Create welcome message
        welcome_message = ChatMessage.objects.create(
            chat_room=chat_room,
            sender=request.user,
            message_type='system',
            content=f"Gruppenchat '{name}' wurde von {request.user.get_full_name() or request.user.username} erstellt."
        )
        
        # Ensure last_message_at is set properly
        chat_room.last_message_at = welcome_message.created_at
        chat_room.save(update_fields=['last_message_at'])
        
        messages.success(request, f"Gruppenchat '{name}' wurde erstellt.")
        return redirect(f'/chat/?room={chat_room.id}')
    
    # GET request - show form
    users = User.objects.exclude(id=request.user.id).order_by('username')
    
    context = {
        'users': users,
    }
    
    return render(request, 'chat/create_group_chat.html', context)


@login_required
def mark_messages_read(request, room_id):
    """
    Mark messages as read (AJAX endpoint)
    """
    try:
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Mark all unread messages as read
        unread_messages = chat_room.messages.exclude(
            read_by__user=request.user
        ).exclude(sender=request.user)
        
        for message in unread_messages:
            ChatMessageRead.objects.get_or_create(
                message=message,
                user=request.user
            )
        
        # Update last_read_at
        participant = ChatRoomParticipant.objects.get(
            chat_room=chat_room,
            user=request.user
        )
        participant.last_read_at = timezone.now()
        participant.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_unread_count(request):
    """
    Get total unread message count for the current user
    """
    try:
        unread_count = request.user.get_unread_chat_count()
        
        # Get latest unread message for notification
        latest_message = None
        if unread_count > 0:
            # Find the latest unread message
            unread_messages = ChatMessage.objects.filter(
                chat_room__participants=request.user
            ).exclude(
                read_by__user=request.user
            ).exclude(
                sender=request.user
            ).select_related('sender', 'chat_room').order_by('-created_at').first()
            
            if unread_messages:
                latest_message = {
                    'room_id': unread_messages.chat_room.id,
                    'sender_name': unread_messages.sender.get_full_name() or unread_messages.sender.username if unread_messages.sender else 'Anonym',
                    'content': unread_messages.content[:100],
                    'created_at': unread_messages.created_at.isoformat()
                }
        
        return JsonResponse({
            'unread_count': unread_count,
            'latest_message': latest_message
        })
    except Exception as e:
        return JsonResponse({'unread_count': 0, 'error': str(e)})


@login_required
def update_online_status(request):
    """
    Update user's online status
    """
    try:
        # Update both is_online and last_activity
        request.user.is_online = True
        request.user.last_activity = timezone.now()
        request.user.save(update_fields=['is_online', 'last_activity'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def set_offline(request):
    """
    Set user offline when leaving the page
    """
    try:
        request.user.is_online = False
        request.user.save(update_fields=['is_online'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def send_call_notification(request):
    """
    Send call notification to other chat participants
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            room_id = data.get('room_id')
            call_type = data.get('call_type')
            channel_name = data.get('channel_name')
            
            # Get the chat room
            room = get_object_or_404(ChatRoom, id=room_id)
            
            # Check if user is participant
            if not room.participants.filter(id=request.user.id).exists():
                return JsonResponse({'success': False, 'error': 'No permission'})
            
            # Remove any existing call notifications for this room to avoid duplicates
            ChatMessage.objects.filter(
                chat_room=room,
                content__startswith='AGORA_CALL:',
                message_type='system'
            ).delete()
            
            # Create a single call notification message
            call_message = ChatMessage.objects.create(
                chat_room=room,
                sender=request.user,
                content=f"AGORA_CALL:{call_type}:{channel_name}",
                message_type='system'
            )
            
            return JsonResponse({
                'success': True,
                'message_id': call_message.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


def check_incoming_calls(request):
    if not request.user.is_authenticated:
        return JsonResponse({'has_call': False, 'error': 'Authentication required'})
    """
    Check for incoming calls for the current user across all chat rooms using Call model
    """
    try:
        from .models import Call
        from django.utils import timezone
        from datetime import timedelta
        
        # First, clean up stale calls (older than 5 minutes)
        stale_calls = Call.objects.filter(
            status__in=['initiated', 'ringing'],
            started_at__lt=timezone.now() - timedelta(minutes=5)
        )
        stale_calls.update(status='missed')
        
        # Get the room_id from query params (optional, for backward compatibility)
        room_id = request.GET.get('room_id')
        
        # Get all rooms where user is a participant
        user_rooms = ChatRoom.objects.filter(participants=request.user)
        
        if room_id:
            # If room_id is specified, check only that room
            active_calls = Call.objects.filter(
                chat_room_id=room_id,
                status__in=['initiated', 'ringing'],
                chat_room__participants=request.user
            ).exclude(caller=request.user).order_by('-started_at')
        else:
            # Check all user's chat rooms for incoming calls
            active_calls = Call.objects.filter(
                chat_room__in=user_rooms,
                status__in=['initiated', 'ringing']
            ).exclude(caller=request.user).order_by('-started_at')
        
        if active_calls.exists():
            latest_call = active_calls.first()
            
            return JsonResponse({
                'has_call': True,
                'call_type': latest_call.call_type,
                'channel_name': f"call_{latest_call.chat_room.id}_{latest_call.id}",
                'caller_name': latest_call.caller.get_full_name() or latest_call.caller.username,
                'caller_id': latest_call.caller.id,
                'room_id': latest_call.chat_room.id,
                'call_id': latest_call.id,
                'message_id': latest_call.id,  # For backward compatibility
                'status': latest_call.status
            })
        
        return JsonResponse({'has_call': False})
        
    except Exception as e:
        return JsonResponse({'has_call': False, 'error': str(e)})


@login_required
@csrf_exempt
def debug_calls(request):
    """
    Debug endpoint to see all calls in the database
    """
    try:
        from .models import Call
        from django.utils import timezone
        
        all_calls = Call.objects.all().order_by('-started_at')[:20]  # Last 20 calls
        
        call_data = []
        for call in all_calls:
            age_minutes = (timezone.now() - call.started_at).total_seconds() / 60
            call_data.append({
                'id': call.id,
                'status': call.status,
                'call_type': call.call_type,
                'caller': call.caller.username,
                'room_id': call.chat_room.id,
                'age_minutes': round(age_minutes, 2),
                'started_at': call.started_at.isoformat()
            })
        
        active_calls = [call for call in call_data if call['status'] in ['initiated', 'ringing', 'connected']]
        
        return JsonResponse({
            'success': True,
            'all_calls': call_data,
            'active_calls': active_calls,
            'active_call_count': len(active_calls)
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@login_required
@csrf_exempt
def cleanup_all_calls(request):
    """
    Emergency cleanup of all stale calls - for debugging
    """
    if request.method == 'POST':
        try:
            from .models import Call
            from django.utils import timezone
            from datetime import timedelta
            
            # Get information about all active calls first
            all_active_calls = Call.objects.filter(
                status__in=['initiated', 'ringing', 'connected']
            )
            
            call_info = []
            for call in all_active_calls:
                age_minutes = (timezone.now() - call.started_at).total_seconds() / 60
                call_info.append({
                    'id': call.id,
                    'status': call.status,
                    'caller': call.caller.username,
                    'room_id': call.chat_room.id,
                    'age_minutes': round(age_minutes, 2),
                    'started_at': call.started_at.isoformat()
                })
            
            # Clean up all calls older than 30 seconds (very aggressive)
            stale_calls = Call.objects.filter(
                status__in=['initiated', 'ringing', 'connected'],
                started_at__lt=timezone.now() - timedelta(seconds=30)
            )
            
            count = stale_calls.count()
            stale_calls.update(status='ended')
            
            # Also clean up calls from the same user trying to call again
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_calls = Call.objects.filter(
                    caller=request.user,
                    status__in=['initiated', 'ringing', 'connected']
                )
                user_call_count = user_calls.count()
                user_calls.update(status='ended')
                count += user_call_count
            
            return JsonResponse({
                'success': True,
                'cleaned_up_count': count,
                'all_active_calls_before': call_info,
                'message': f'Cleaned up {count} stale calls (30+ seconds old)'
            })
            
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            })
    
    return JsonResponse({'success': False, 'error': 'Only POST method allowed'})


@login_required
@csrf_exempt
def clear_call_notification(request):
    """
    Clear call notification after answering/rejecting (now using Call model)
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_id = data.get('message_id')
            action = data.get('action', 'clear')  # 'clear', 'accept', 'reject'
            
            if message_id:
                # Clear the call status (for backward compatibility, message_id is actually call_id)
                from .models import Call
                try:
                    call = Call.objects.get(id=message_id)
                    
                    if action == 'accept':
                        call.status = 'connected'
                        call.connected_at = timezone.now()
                        print(f"DEBUG: Call {message_id} marked as connected (accepted)")
                    elif action == 'reject':
                        call.status = 'rejected'
                        print(f"DEBUG: Call {message_id} marked as rejected")
                    else:
                        # Default behavior for clearing - don't change status
                        print(f"DEBUG: Call {message_id} notification cleared without status change")
                    
                    call.save()
                    
                except Call.DoesNotExist:
                    print(f"DEBUG: Call {message_id} not found")
                    pass
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


@login_required
@csrf_exempt
def end_call_notification(request):
    """
    End call and clear all related notifications
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            room_id = data.get('room_id')
            
            if not room_id:
                return JsonResponse({'success': False, 'error': 'Room ID required'})
            
            # Get the chat room
            room = get_object_or_404(ChatRoom, id=room_id)
            
            # Check if user is participant
            if not room.participants.filter(id=request.user.id).exists():
                return JsonResponse({'success': False, 'error': 'No permission'})
            
            # End any active calls in this room
            from .models import Call
            active_calls = Call.objects.filter(
                chat_room=room,
                status__in=['initiated', 'ringing', 'connected']
            )
            
            calls_ended = 0
            for call in active_calls:
                call.status = 'ended'
                call.ended_at = timezone.now()
                call.save()
                calls_ended += 1
                print(f"DEBUG: Call {call.id} ended by end_call_notification")
            
            # Also remove old call notifications for backward compatibility
            deleted_count = ChatMessage.objects.filter(
                chat_room=room,
                content__startswith='AGORA_CALL:',
                message_type='system'
            ).delete()[0]
            
            return JsonResponse({
                'success': True,
                'cleared_notifications': deleted_count,
                'calls_ended': calls_ended
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


@login_required
@csrf_exempt
def reject_call(request):
    """
    Reject an incoming call
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            call_id = data.get('call_id')
            
            if not call_id:
                return JsonResponse({'success': False, 'error': 'Call ID required'})
            
            from .models import Call
            try:
                call = Call.objects.get(id=call_id)
                
                # Check if user is participant
                if not call.chat_room.participants.filter(id=request.user.id).exists():
                    return JsonResponse({'success': False, 'error': 'No permission'})
                
                # Mark the call as rejected
                call.status = 'rejected'
                call.save()
                
                print(f"DEBUG: Call {call_id} rejected by user {request.user.username}")
                
                return JsonResponse({'success': True, 'message': 'Call rejected'})
                
            except Call.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Call not found'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


@login_required
@csrf_exempt
def accept_call(request):
    """
    Accept an incoming call
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            call_id = data.get('call_id')
            
            if not call_id:
                return JsonResponse({'success': False, 'error': 'Call ID required'})
            
            from .models import Call
            try:
                call = Call.objects.get(id=call_id)
                
                # Check if user is participant
                if not call.chat_room.participants.filter(id=request.user.id).exists():
                    return JsonResponse({'success': False, 'error': 'No permission'})
                
                # Check if call is still active
                if call.status == 'connected':
                    return JsonResponse({
                        'success': True,
                        'message': 'Call is already connected',
                        'already_connected': True
                    })
                elif call.status not in ['initiated', 'ringing']:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Call is no longer active',
                        'current_status': call.status
                    })
                
                # Mark the call as connected
                call.status = 'connected'
                call.connected_at = timezone.now()
                call.save()
                
                print(f"DEBUG: Call {call_id} accepted by user {request.user.username}")
                
                return JsonResponse({'success': True, 'message': 'Call accepted'})
                
            except Call.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Call not found'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


@login_required
def redirect_to_chat(request, room_id):
    """
    Redirect room URLs to main chat page with room selected
    """
    # Verify user has access to this room
    try:
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        if not chat_room.participants.filter(id=request.user.id).exists():
            messages.error(request, "Sie haben keinen Zugriff auf diesen Chat.")
            return redirect('chat:home')
    except ChatRoom.DoesNotExist:
        messages.error(request, "Chat-Raum nicht gefunden.")
        return redirect('chat:home')
    
    # Redirect to main chat page with room_id as parameter
    return redirect(f'/chat/?room={room_id}')


@login_required
def delete_chat(request, room_id):
    """
    Delete a chat room (only for creator or remove user from participants)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # If user is the creator and it's a private chat, delete the entire chat
        if chat_room.created_by == request.user and not chat_room.is_group_chat:
            chat_room.delete()
            return JsonResponse({'success': True, 'message': 'Chat wurde gelöscht'})
        
        # If it's a group chat and user is creator, delete entire chat
        elif chat_room.created_by == request.user and chat_room.is_group_chat:
            chat_room.delete()
            return JsonResponse({'success': True, 'message': 'Gruppenchat wurde gelöscht'})
        
        # If user is not creator, just remove them from participants
        else:
            participant = ChatRoomParticipant.objects.get(chat_room=chat_room, user=request.user)
            participant.delete()
            return JsonResponse({'success': True, 'message': 'Sie haben den Chat verlassen'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_chat_info(request, room_id):
    """
    Get chat room information including participant profiles
    """
    try:
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Get participants with detailed info
        participants = []
        participants_detailed = []
        other_user_info = None
        
        for participant in chat_room.participants.all():
            user_info = {
                'id': participant.id,
                'username': participant.username,
                'first_name': participant.first_name,
                'last_name': participant.last_name,
                'name': participant.get_full_name() or participant.username,
                'email': participant.email if participant == request.user or request.user.is_superuser else None,
                'is_online': participant.is_currently_online(),
                'last_activity': participant.last_activity.strftime('%d.%m.%Y %H:%M') if participant.last_activity else None,
                'date_joined': participant.date_joined.strftime('%d.%m.%Y'),
                'profile_picture': participant.profile_picture.url if participant.profile_picture else None,
                'is_current_user': participant == request.user
            }
            participants.append(user_info['name'])
            participants_detailed.append(user_info)
            
            # If it's a private chat, get info about the other user
            if not chat_room.is_group_chat and participant != request.user:
                other_user_info = user_info
        
        # Get recent messages count
        recent_messages_count = chat_room.messages.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        
        room_info = {
            'id': chat_room.id,
            'name': chat_room.name,
            'is_group_chat': chat_room.is_group_chat,
            'created_at': chat_room.created_at.strftime('%d.%m.%Y %H:%M'),
            'created_by': {
                'name': chat_room.created_by.get_full_name() or chat_room.created_by.username,
                'username': chat_room.created_by.username
            } if chat_room.created_by else None,
            'participants': participants,
            'participants_detailed': participants_detailed,
            'participants_count': chat_room.participants.count(),
            'total_messages': chat_room.messages.count(),
            'recent_messages_count': recent_messages_count,
            'last_message_at': chat_room.last_message_at.strftime('%d.%m.%Y %H:%M') if chat_room.last_message_at else None,
            'other_user': other_user_info
        }
        
        return JsonResponse({'success': True, 'room': room_info})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def initiate_call(request, room_id):
    """
    Initiate a call in a chat room
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        data = json.loads(request.body)
        call_type = data.get('call_type', 'audio')
        
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Check if there's already an active call
        from .models import Call, CallParticipant
        
        # First, clean up any stale calls (older than 10 minutes) - allows time for auto-answer
        from django.utils import timezone
        from datetime import timedelta
        
        stale_calls = Call.objects.filter(
            chat_room=chat_room,
            status__in=['initiated', 'ringing'],
            started_at__lt=timezone.now() - timedelta(minutes=10)
        )
        stale_calls.update(status='missed')
        
        # Also clean up calls that are still "connected" but older than 30 minutes
        old_connected_calls = Call.objects.filter(
            chat_room=chat_room,
            status='connected',
            started_at__lt=timezone.now() - timedelta(minutes=30)
        )
        old_connected_calls.update(status='ended')
        
        # Now check for active calls
        active_call = Call.objects.filter(
            chat_room=chat_room,
            status__in=['initiated', 'ringing', 'connected']
        ).first()
        
        if active_call:
            # Force cleanup if call is too old (older than 2 minutes for better UX)
            if active_call.started_at < timezone.now() - timedelta(minutes=2):
                active_call.status = 'missed'
                active_call.save()
                print(f"DEBUG: Force cleaned up old call {active_call.id}")
            else:
                # Check if this is a really stuck call (same caller trying to call again)
                if active_call.caller == request.user:
                    print(f"DEBUG: Same user trying to initiate another call - cleaning up previous call {active_call.id}")
                    active_call.status = 'ended'
                    active_call.save()
                else:
                    # Provide detailed information about the blocking call
                    age_minutes = (timezone.now() - active_call.started_at).total_seconds() / 60
                    print(f"DEBUG: Active call found: {active_call.id}, started: {active_call.started_at}, caller: {active_call.caller}, age: {age_minutes:.1f}min, status: {active_call.status}")
                    
                    return JsonResponse({
                        'success': False, 
                        'error': f'Es läuft bereits ein Anruf in diesem Chat (ID: {active_call.id}, Status: {active_call.status}, Alter: {age_minutes:.1f} Min)',
                        'active_call_id': active_call.id,
                        'active_call_caller': active_call.caller.username,
                        'active_call_started': active_call.started_at.isoformat(),
                        'active_call_status': active_call.status,
                        'active_call_age_minutes': round(age_minutes, 2)
                    })
        
        # Create new call
        call = Call.objects.create(
            chat_room=chat_room,
            caller=request.user,
            call_type=call_type,
            status='initiated'
        )
        
        # Add all participants to the call
        for participant in chat_room.participants.all():
            CallParticipant.objects.create(
                call=call,
                user=participant,
                status='invited'
            )
        
        # Send global notification to all participants (except caller)
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        participants = chat_room.participants.exclude(id=request.user.id)
        print(f"🔔 Sending call notifications to {participants.count()} participants")
        
        for participant in participants:
            print(f"📤 Sending notification to user {participant.username} (ID: {participant.id})")
            async_to_sync(channel_layer.group_send)(
                f'user_{participant.id}',
                {
                    'type': 'global_call_notification',
                    'call_id': call.id,
                    'caller': request.user.username,
                    'caller_full_name': request.user.get_full_name() or request.user.username,
                    'call_type': call_type,
                    'room_id': str(chat_room.id),
                    'room_name': str(chat_room),
                    'timestamp': timezone.now().isoformat()
                }
            )
        
        return JsonResponse({
            'success': True,
            'call_id': call.id,
            'call_type': call_type,
            'message': 'Anruf gestartet'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def end_call(request, call_id):
    """
    End an active call
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        from .models import Call
        call = get_object_or_404(Call, id=call_id)
        
        # Check if user is participant
        if not call.participants.filter(user=request.user).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Update call status
        call.status = 'ended'
        call.ended_at = timezone.now()
        
        # Calculate duration if call was connected
        if call.connected_at:
            call.duration = call.ended_at - call.connected_at
        
        call.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Anruf beendet',
            'duration': call.get_duration_display()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_call_info_by_id(request, call_id):
    """
    Get call information by call ID
    """
    try:
        from .models import Call
        
        # Try to get the call
        try:
            call = Call.objects.get(id=call_id)
        except Call.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Call nicht gefunden - möglicherweise bereits beendet'
            })
        
        # Check if user is participant
        if not call.chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Check if call is still active/answerable
        if call.status not in ['initiated', 'ringing', 'connected']:
            return JsonResponse({
                'success': False, 
                'error': f'Call ist bereits {call.status} und kann nicht mehr angenommen werden'
            })
        
        # Generate channel name for Agora
        channel_name = f"call_{call.chat_room.id}_{call.id}"
        
        return JsonResponse({
            'success': True,
            'call_id': call.id,
            'call_type': call.call_type,
            'channel_name': channel_name,
            'room_id': call.chat_room.id,
            'caller_name': call.caller.get_full_name() or call.caller.username,
            'status': call.status
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_active_call_info(request, room_id):
    """
    Get information about any active call in a room
    """
    try:
        from .models import Call
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Look for active call in the room
        active_call = Call.objects.filter(
            chat_room=chat_room,
            status__in=['initiated', 'ringing', 'connected']
        ).first()
        
        if active_call:
            # Generate channel name for Agora
            channel_name = f"call_{chat_room.id}_{active_call.id}"
            
            return JsonResponse({
                'success': True,
                'has_active_call': True,
                'call_id': active_call.id,
                'call_type': active_call.call_type,
                'channel_name': channel_name,
                'room_id': chat_room.id,
                'caller_name': active_call.caller.get_full_name() or active_call.caller.username,
                'status': active_call.status
            })
        else:
            return JsonResponse({
                'success': True,
                'has_active_call': False,
                'message': 'Kein aktiver Anruf in diesem Raum'
            })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_call_history(request, room_id):
    """
    Get call history for a chat room
    """
    try:
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        # Get recent calls
        from .models import Call
        calls = Call.objects.filter(chat_room=chat_room).order_by('-started_at')[:10]
        
        call_history = []
        for call in calls:
            call_history.append({
                'id': call.id,
                'caller': call.caller.username,
                'call_type': call.get_call_type_display(),
                'status': call.get_status_display(),
                'started_at': call.started_at.strftime('%d.%m.%Y %H:%M'),
                'duration': call.get_duration_display() if call.duration else '00:00'
            })
        
        return JsonResponse({
            'success': True,
            'calls': call_history
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def websocket_test(request):
    """
    WebSocket connection test page
    """
    return render(request, 'chat/websocket_test.html')


@login_required
def test_call(request):
    """
    WebRTC call test page
    """
    # Get rooms where user is a participant
    user_rooms = ChatRoom.objects.filter(participants=request.user).order_by('-created_at')
    
    context = {
        'user_rooms': user_rooms,
        'default_room_id': request.GET.get('room_id', '1')
    }
    return render(request, 'chat/test_call.html', context)


@login_required
@require_http_methods(["POST"])
def get_agora_token(request):
    """
    Generate Agora token for video/audio calls
    """
    try:
        import time
        from django.conf import settings
        
        data = json.loads(request.body)
        channel = data.get('channel')
        uid = data.get('uid', 0)
        
        if not channel:
            return JsonResponse({
                'success': False,
                'error': 'Channel name required'
            })
        
        # Generate real Agora token
        result = generate_agora_token(channel, uid)
        
        if result['success']:
            print(f"Generated Agora token for channel: {channel}, uid: {result['uid']}")
            return JsonResponse({
                'success': True,
                'token': result['token'],
                'uid': result['uid'],
                'expire_time': result['expire_time']
            })
        else:
            print(f"Token generation failed: {result['error']}")
            return JsonResponse({
                'success': False,
                'error': result['error']
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })