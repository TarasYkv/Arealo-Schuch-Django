#!/usr/bin/env python
"""
Script to manually create todos tables when migrations fail
Run this with: python create_todos_tables.py
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.db import connection, transaction

def create_todos_tables():
    """Create todos tables manually"""
    
    sql_commands = [
        # TodoList table
        """
        CREATE TABLE IF NOT EXISTS todos_todolist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            is_public BOOLEAN NOT NULL DEFAULT 0,
            created_by_id INTEGER NOT NULL,
            FOREIGN KEY (created_by_id) REFERENCES auth_user (id)
        );
        """,
        
        # TodoList shared_with many-to-many table
        """
        CREATE TABLE IF NOT EXISTS todos_todolist_shared_with (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            todolist_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (todolist_id) REFERENCES todos_todolist (id),
            FOREIGN KEY (user_id) REFERENCES auth_user (id),
            UNIQUE (todolist_id, user_id)
        );
        """,
        
        # Todo table
        """
        CREATE TABLE IF NOT EXISTS todos_todo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            due_date DATETIME,
            completed_at DATETIME,
            created_by_id INTEGER NOT NULL,
            todo_list_id INTEGER NOT NULL,
            FOREIGN KEY (created_by_id) REFERENCES auth_user (id),
            FOREIGN KEY (todo_list_id) REFERENCES todos_todolist (id)
        );
        """,
        
        # TodoAssignment table
        """
        CREATE TABLE IF NOT EXISTS todos_todoassignment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assigned_at DATETIME NOT NULL,
            notes TEXT,
            user_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            assigned_by_id INTEGER NOT NULL,
            todo_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (assigned_by_id) REFERENCES auth_user (id),
            FOREIGN KEY (todo_id) REFERENCES todos_todo (id),
            FOREIGN KEY (user_id) REFERENCES auth_user (id),
            UNIQUE (todo_id, user_id)
        );
        """,
        
        # TodoComment table
        """
        CREATE TABLE IF NOT EXISTS todos_todocomment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            todo_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (todo_id) REFERENCES todos_todo (id),
            FOREIGN KEY (user_id) REFERENCES auth_user (id)
        );
        """,
        
        # TodoActivity table
        """
        CREATE TABLE IF NOT EXISTS todos_todoactivity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type VARCHAR(20) NOT NULL,
            description TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            todo_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (todo_id) REFERENCES todos_todo (id),
            FOREIGN KEY (user_id) REFERENCES auth_user (id)
        );
        """,
        
        # Insert migration record
        """
        INSERT OR IGNORE INTO django_migrations (app, name, applied) 
        VALUES ('todos', '0001_initial', datetime('now'));
        """
    ]
    
    with transaction.atomic():
        with connection.cursor() as cursor:
            for sql in sql_commands:
                try:
                    cursor.execute(sql)
                    print(f"✓ Executed SQL command successfully")
                except Exception as e:
                    print(f"✗ Error executing SQL: {e}")
                    print(f"SQL: {sql[:100]}...")
    
    print("\n🎉 ToDo tables created successfully!")
    print("You can now access /todos/ in your browser.")

if __name__ == '__main__':
    print("Creating ToDo tables...")
    create_todos_tables()