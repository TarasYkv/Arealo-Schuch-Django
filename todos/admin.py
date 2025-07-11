from django.contrib import admin
from .models import TodoList, Todo, TodoAssignment, TodoComment, TodoActivity


@admin.register(TodoList)
class TodoListAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'created_at', 'is_public', 'get_todo_count', 'get_progress']
    list_filter = ['is_public', 'created_at']
    search_fields = ['title', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['shared_with']
    
    def get_todo_count(self, obj):
        return obj.todos.count()
    get_todo_count.short_description = 'Anzahl ToDos'
    
    def get_progress(self, obj):
        return f"{obj.get_progress()}%"
    get_progress.short_description = 'Fortschritt'


class TodoAssignmentInline(admin.TabularInline):
    model = TodoAssignment
    extra = 0
    readonly_fields = ['assigned_at']


class TodoCommentInline(admin.TabularInline):
    model = TodoComment
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ['title', 'todo_list', 'status', 'priority', 'created_by', 'due_date', 'is_overdue']
    list_filter = ['status', 'priority', 'todo_list', 'created_at', 'due_date']
    search_fields = ['title', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    inlines = [TodoAssignmentInline, TodoCommentInline]
    
    def is_overdue(self, obj):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'Überfällig'


@admin.register(TodoAssignment)
class TodoAssignmentAdmin(admin.ModelAdmin):
    list_display = ['todo', 'user', 'user_status', 'assigned_by', 'assigned_at']
    list_filter = ['user_status', 'assigned_at']
    search_fields = ['todo__title', 'user__username', 'assigned_by__username']
    readonly_fields = ['assigned_at']


@admin.register(TodoComment)
class TodoCommentAdmin(admin.ModelAdmin):
    list_display = ['todo', 'user', 'created_at', 'get_content_preview']
    list_filter = ['created_at']
    search_fields = ['todo__title', 'user__username', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    get_content_preview.short_description = 'Inhalt'


@admin.register(TodoActivity)
class TodoActivityAdmin(admin.ModelAdmin):
    list_display = ['todo', 'user', 'activity_type', 'created_at', 'get_description_preview']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['todo__title', 'user__username', 'description']
    readonly_fields = ['created_at']
    
    def get_description_preview(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    get_description_preview.short_description = 'Beschreibung'