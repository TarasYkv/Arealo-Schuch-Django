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
import json

from .models import ChatRoom, ChatMessage, ChatRoomParticipant, ChatMessageRead

User = get_user_model()


@login_required
def chat_home(request):
    """
    Chat overview page showing all user's chat rooms
    """
    # Get all chat rooms for the current user
    chat_rooms = ChatRoom.objects.filter(
        participants=request.user
    ).annotate(
        message_count=Count('messages'),
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_at')
    
    # Get unread counts for each chat room
    for room in chat_rooms:
        room.unread_count = room.get_unread_count(request.user)
    
    # Get recent users for starting new chats
    recent_users = User.objects.exclude(
        id=request.user.id
    ).order_by('-last_login')[:10]
    
    context = {
        'chat_rooms': chat_rooms,
        'recent_users': recent_users,
    }
    
    return render(request, 'chat/home.html', context)


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
        return redirect('chat:room_detail', room_id=existing_chat.id)
    
    # Create new private chat
    chat_room = ChatRoom.objects.create(
        created_by=request.user,
        is_group_chat=False
    )
    
    # Add participants
    ChatRoomParticipant.objects.create(chat_room=chat_room, user=request.user)
    ChatRoomParticipant.objects.create(chat_room=chat_room, user=other_user)
    
    # Create welcome message
    ChatMessage.objects.create(
        chat_room=chat_room,
        sender=request.user,
        message_type='system',
        content=f"Chat gestartet zwischen {request.user.get_full_name() or request.user.username} und {other_user.get_full_name() or other_user.username}"
    )
    
    return redirect('chat:room_detail', room_id=chat_room.id)


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
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Nachricht darf nicht leer sein'})
        
        # Create message
        message = ChatMessage.objects.create(
            chat_room=chat_room,
            sender=request.user,
            content=content,
            message_type=message_type,
            reply_to_id=reply_to_id if reply_to_id else None
        )
        
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
                'sender_id': message.sender.id,
                'created_at': message.get_formatted_time(),
                'message_type': message.message_type,
                'reply_to': message.reply_to.id if message.reply_to else None
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
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check if user is participant
        if not chat_room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Zugriff verweigert'})
        
        since_id = request.GET.get('since_id')
        if since_id:
            messages = chat_room.messages.filter(
                id__gt=since_id
            ).select_related('sender').order_by('created_at')
        else:
            messages = chat_room.messages.select_related('sender').order_by('created_at')[:50]
        
        messages_data = []
        for message in messages:
            messages_data.append({
                'id': message.id,
                'content': message.content,
                'sender': message.sender.get_full_name() or message.sender.username,
                'sender_id': message.sender.id,
                'created_at': message.get_formatted_time(),
                'message_type': message.message_type,
                'reply_to': message.reply_to.id if message.reply_to else None
            })
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'last_message_id': messages.last().id if messages.exists() else None
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
        ChatMessage.objects.create(
            chat_room=chat_room,
            sender=request.user,
            message_type='system',
            content=f"Gruppenchat '{name}' wurde von {request.user.get_full_name() or request.user.username} erstellt."
        )
        
        messages.success(request, f"Gruppenchat '{name}' wurde erstellt.")
        return redirect('chat:room_detail', room_id=chat_room.id)
    
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