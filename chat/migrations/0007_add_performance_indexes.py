# Generated migration for performance indexes
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0006_call_callparticipant'),
    ]

    operations = [
        # ChatMessage indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_message_created_at ON chat_chatmessage(created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_message_created_at;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_message_chat_room_created ON chat_chatmessage(chat_room_id, created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_message_chat_room_created;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_message_sender ON chat_chatmessage(sender_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_message_sender;"
        ),
        
        # ChatRoom indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_room_last_message ON chat_chatroom(last_message_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_room_last_message;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_room_created_by ON chat_chatroom(created_by_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_room_created_by;"
        ),
        
        # ChatRoomParticipant indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_participant_user ON chat_chatroomparticipant(user_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_participant_user;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_participant_room ON chat_chatroomparticipant(chat_room_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_participant_room;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_chat_participant_last_read ON chat_chatroomparticipant(last_read_at);",
            reverse_sql="DROP INDEX IF EXISTS idx_chat_participant_last_read;"
        ),
        
        # Call indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_call_chat_room_status ON chat_call(chat_room_id, status);",
            reverse_sql="DROP INDEX IF EXISTS idx_call_chat_room_status;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_call_started_at ON chat_call(started_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_call_started_at;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_call_caller ON chat_call(caller_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_call_caller;"
        ),
        
        # CallParticipant indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_call_participant_call ON chat_callparticipant(call_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_call_participant_call;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_call_participant_user ON chat_callparticipant(user_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_call_participant_user;"
        ),
    ]