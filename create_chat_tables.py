#!/usr/bin/env python
"""
Script to manually create chat tables when Django isn't available
Run this with: python create_chat_tables.py
"""

import os
import sys
import sqlite3
from datetime import datetime

def create_chat_tables():
    """Create chat tables manually in SQLite database"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    # SQL commands to create chat tables
    sql_commands = [
        # ChatRoom table
        """
        CREATE TABLE IF NOT EXISTS chat_chatroom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200),
            created_at DATETIME NOT NULL,
            last_message_at DATETIME NOT NULL,
            is_group_chat BOOLEAN NOT NULL DEFAULT 0,
            created_by_id INTEGER NOT NULL,
            FOREIGN KEY (created_by_id) REFERENCES auth_user (id)
        );
        """,
        
        # ChatRoomParticipant table
        """
        CREATE TABLE IF NOT EXISTS chat_chatroomparticipant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            joined_at DATETIME NOT NULL,
            last_read_at DATETIME NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            chat_room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (chat_room_id) REFERENCES chat_chatroom (id),
            FOREIGN KEY (user_id) REFERENCES auth_user (id),
            UNIQUE (chat_room_id, user_id)
        );
        """,
        
        # ChatMessage table
        """
        CREATE TABLE IF NOT EXISTS chat_chatmessage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_type VARCHAR(20) NOT NULL DEFAULT 'text',
            content TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            is_edited BOOLEAN NOT NULL DEFAULT 0,
            chat_room_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            reply_to_id INTEGER,
            FOREIGN KEY (chat_room_id) REFERENCES chat_chatroom (id),
            FOREIGN KEY (sender_id) REFERENCES auth_user (id),
            FOREIGN KEY (reply_to_id) REFERENCES chat_chatmessage (id)
        );
        """,
        
        # ChatMessageRead table
        """
        CREATE TABLE IF NOT EXISTS chat_chatmessageread (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            read_at DATETIME NOT NULL,
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (message_id) REFERENCES chat_chatmessage (id),
            FOREIGN KEY (user_id) REFERENCES auth_user (id),
            UNIQUE (message_id, user_id)
        );
        """,
        
        # Insert migration record
        """
        INSERT OR IGNORE INTO django_migrations (app, name, applied) 
        VALUES ('chat', '0001_initial', datetime('now'));
        """
    ]
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔧 Creating chat tables...")
        
        # Execute each SQL command
        for i, sql in enumerate(sql_commands, 1):
            try:
                cursor.execute(sql)
                print(f"✓ Command {i}/5 executed successfully")
            except Exception as e:
                print(f"✗ Error in command {i}: {e}")
                print(f"SQL: {sql[:100]}...")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("\n🎉 Chat tables created successfully!")
        print("✅ Migration record added to database")
        print("🚀 You can now access /chat/ in your browser")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

def check_existing_tables():
    """Check what tables already exist"""
    db_path = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("📋 Existing tables in database:")
        for table in sorted(tables):
            print(f"  - {table}")
        
        # Check for chat tables specifically
        chat_tables = [t for t in tables if t.startswith('chat_')]
        if chat_tables:
            print(f"\n✅ Found {len(chat_tables)} existing chat tables:")
            for table in chat_tables:
                print(f"  - {table}")
        else:
            print("\n❌ No chat tables found")
        
        conn.close()
        return len(chat_tables) > 0
        
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("Chat Tables Creation Script")
    print("=" * 50)
    
    # Check current state
    has_chat_tables = check_existing_tables()
    
    if has_chat_tables:
        response = input("\n⚠️  Chat tables already exist. Recreate them? (y/N): ")
        if response.lower() != 'y':
            print("❌ Aborted by user")
            sys.exit(0)
    
    # Create tables
    success = create_chat_tables()
    
    if success:
        print("\n✅ Setup complete! Next steps:")
        print("1. Start your Django server: python manage.py runserver")
        print("2. Navigate to /chat/ in your browser")
        print("3. Start chatting with other users!")
    else:
        print("\n❌ Setup failed. Please check the error messages above.")
        sys.exit(1)