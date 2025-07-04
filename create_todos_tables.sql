-- SQL Script to create todos tables manually
-- Run this if migrations don't work

-- TodoList table
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

-- TodoList shared_with many-to-many table
CREATE TABLE IF NOT EXISTS todos_todolist_shared_with (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    todolist_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (todolist_id) REFERENCES todos_todolist (id),
    FOREIGN KEY (user_id) REFERENCES auth_user (id),
    UNIQUE (todolist_id, user_id)
);

-- Todo table
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

-- TodoAssignment table
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

-- TodoComment table
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

-- TodoActivity table
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

-- Insert migration record
INSERT OR IGNORE INTO django_migrations (app, name, applied) 
VALUES ('todos', '0001_initial', datetime('now'));