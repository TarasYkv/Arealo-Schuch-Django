from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Video, UserStorage, Subscription

User = get_user_model()


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'priority', 'get_file_size_mb', 'get_share_link', 'created_at']
    list_filter = ['status', 'priority', 'created_at', 'user__userstorage__is_premium']
    search_fields = ['title', 'description', 'user__username']
    readonly_fields = ['unique_id', 'share_link', 'file_size', 'created_at', 'updated_at', 'archived_at', 'archive_expires_at']
    actions = ['update_storage_usage', 'archive_selected_videos', 'restore_selected_videos', 'recalculate_archival_scores']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('user', 'title', 'description')
        }),
        ('Status & Priorität', {
            'fields': ('status', 'priority')
        }),
        ('Dateien', {
            'fields': ('video_file', 'thumbnail')
        }),
        ('Archivierung', {
            'fields': ('archived_at', 'archived_reason', 'archive_expires_at'),
            'classes': ('collapse',)
        }),
        ('Zugriffstracking', {
            'fields': ('last_accessed', 'access_count'),
            'classes': ('collapse',)
        }),
        ('Links', {
            'fields': ('unique_id', 'share_link')
        }),
        ('Metadaten', {
            'fields': ('file_size', 'duration', 'created_at', 'updated_at')
        }),
    )
    
    def get_file_size_mb(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB"
    get_file_size_mb.short_description = 'Dateigröße'
    
    def get_share_link(self, obj):
        return format_html('<a href="{}" target="_blank">🔗 Link</a>', obj.share_link)
    get_share_link.short_description = 'Share-Link'
    
    def update_storage_usage(self, request, queryset):
        """Update storage usage for users of selected videos"""
        users_updated = set()
        for video in queryset:
            user = video.user
            if user not in users_updated:
                total_size = Video.objects.filter(user=user, status='active').aggregate(
                    total=Sum('file_size')
                )['total'] or 0
                
                user_storage, created = UserStorage.objects.get_or_create(user=user)
                user_storage.used_storage = total_size
                user_storage.save()
                users_updated.add(user)
        
        messages.success(request, f'Speicherplatz für {len(users_updated)} Benutzer aktualisiert.')
    update_storage_usage.short_description = 'Speicherplatz-Nutzung aktualisieren'
    
    def archive_selected_videos(self, request, queryset):
        """Archive selected videos"""
        count = 0
        for video in queryset:
            if video.status == 'active':
                video.archive(reason="Manual archiving by admin")
                count += 1
        
        messages.success(request, f'{count} Videos archiviert.')
    archive_selected_videos.short_description = 'Videos archivieren'
    
    def restore_selected_videos(self, request, queryset):
        """Restore selected archived videos"""
        count = 0
        for video in queryset:
            if video.status == 'archived':
                video.restore()
                count += 1
        
        messages.success(request, f'{count} Videos wiederhergestellt.')
    restore_selected_videos.short_description = 'Videos wiederherstellen'
    
    def recalculate_archival_scores(self, request, queryset):
        """Show archival scores for selected videos"""
        scores = []
        for video in queryset:
            score = video.get_archival_score()
            scores.append(f"{video.title}: {score:.2f}")
        
        score_text = "; ".join(scores[:10])  # Show max 10
        if len(scores) > 10:
            score_text += f" ... und {len(scores) - 10} weitere"
        
        messages.info(request, f"Archivierungs-Scores: {score_text}")
    recalculate_archival_scores.short_description = 'Archivierungs-Scores anzeigen'


@admin.register(UserStorage)
class UserStorageAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_plan_type', 'get_used_storage_mb', 'get_max_storage_mb', 'get_usage_percentage', 'get_overage_status', 'created_at', 'admin_actions']
    list_filter = ['is_premium', 'is_in_grace_period', 'overage_restriction_level', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['used_storage', 'created_at', 'updated_at']
    actions = ['recalculate_storage', 'upgrade_to_premium', 'reset_to_free_plan', 'increase_quota_100mb', 'increase_quota_500mb', 'clear_overage_status', 'start_grace_period_manually']
    
    fieldsets = (
        ('Benutzer', {
            'fields': ('user',)
        }),
        ('Speicherplatz', {
            'fields': ('used_storage', 'max_storage', 'is_premium')
        }),
        ('Überschreitung & Grace Period', {
            'fields': ('grace_period_start', 'grace_period_end', 'is_in_grace_period', 
                      'overage_restriction_level', 'storage_overage_notified', 'last_overage_notification'),
            'classes': ('collapse',)
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_used_storage_mb(self, obj):
        return f"{obj.get_used_storage_mb():.2f} MB"
    get_used_storage_mb.short_description = 'Belegter Speicher'
    
    def get_max_storage_mb(self, obj):
        return f"{obj.get_max_storage_mb():.2f} MB"
    get_max_storage_mb.short_description = 'Max. Speicher'
    
    def get_plan_type(self, obj):
        if obj.is_premium:
            return format_html('<span class="badge" style="background-color: #007bff; color: white;">Premium</span>')
        else:
            return format_html('<span class="badge" style="background-color: #28a745; color: white;">Kostenlos</span>')
    get_plan_type.short_description = 'Plan-Typ'
    
    def get_usage_percentage(self, obj):
        if obj.max_storage > 0:
            percentage = (obj.used_storage / obj.max_storage) * 100
            if percentage > 100:
                color = "red"
                icon = "⚠️"
            elif percentage > 90:
                color = "red"
                icon = "🔴"
            elif percentage > 75:
                color = "orange"
                icon = "🟡"
            else:
                color = "green"
                icon = "🟢"
            return format_html('<span style="color: {}; font-weight: bold">{} {}</span>', color, icon, f"{percentage:.1f}%")
        return "0%"
    get_usage_percentage.short_description = 'Auslastung'
    
    def get_overage_status(self, obj):
        if obj.is_storage_exceeded():
            if obj.is_in_grace_period:
                return format_html('<span style="color: orange;">🕒 Grace Period</span>')
            elif obj.overage_restriction_level > 0:
                level_names = {1: "Upload-Stopp", 2: "Sharing aus", 3: "Archivierung"}
                level_name = level_names.get(obj.overage_restriction_level, f"Level {obj.overage_restriction_level}")
                return format_html('<span style="color: red;">🚫 {}</span>', level_name)
            else:
                return format_html('<span style="color: red;">⚠️ Überschritten</span>')
        return format_html('<span style="color: green;">✅ OK</span>')
    get_overage_status.short_description = 'Überschreitung'
    
    def admin_actions(self, obj):
        """Quick action buttons for individual users"""
        recalc_url = reverse('admin:videos_userstorage_recalculate_single', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Neu berechnen</a>',
            recalc_url
        )
    admin_actions.short_description = 'Aktionen'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('recalculate/<int:storage_id>/', self.admin_site.admin_view(self.recalculate_single_view), 
                 name='videos_userstorage_recalculate_single'),
            path('dashboard/', self.admin_site.admin_view(self.storage_dashboard_view), 
                 name='videos_storage_dashboard'),
        ]
        return custom_urls + urls
    
    # Admin Actions
    def recalculate_storage(self, request, queryset):
        """Recalculate storage for selected users"""
        updated_count = 0
        for storage in queryset:
            total_size = Video.objects.filter(user=storage.user).aggregate(
                total=Sum('file_size')
            )['total'] or 0
            
            old_usage = storage.used_storage
            storage.used_storage = total_size
            storage.save()
            
            if old_usage != total_size:
                updated_count += 1
        
        messages.success(request, f'Speicherplatz für {updated_count} Benutzer neu berechnet.')
    recalculate_storage.short_description = 'Speicherplatz neu berechnen'
    
    def upgrade_to_premium(self, request, queryset):
        """Upgrade selected users to premium"""
        count = 0
        for storage in queryset:
            if not storage.is_premium:
                storage.is_premium = True
                storage.max_storage = 5368709120  # 5GB
                storage.save()
                count += 1
        
        messages.success(request, f'{count} Benutzer zu Premium erweitert (5GB Speicher).')
    upgrade_to_premium.short_description = 'Auf Premium erweitern (5GB)'
    
    def reset_to_free_plan(self, request, queryset):
        """Reset selected users to free plan and handle downgrade properly"""
        from .signals import reset_user_to_free_plan
        
        count = 0
        for storage in queryset:
            if storage.is_premium:
                reset_user_to_free_plan(storage.user)
                count += 1
        
        messages.warning(request, f'{count} Benutzer auf kostenlosen Plan zurückgesetzt (50MB). Grace Period gestartet falls nötig.')
    reset_to_free_plan.short_description = 'Auf kostenlosen Plan zurücksetzen (50MB)'
    
    def clear_overage_status(self, request, queryset):
        """Clear overage status for selected users"""
        count = 0
        for storage in queryset:
            if storage.is_storage_exceeded() or storage.overage_restriction_level > 0:
                storage.clear_overage_status()
                count += 1
        
        messages.success(request, f'Überschreitungs-Status für {count} Benutzer zurückgesetzt.')
    clear_overage_status.short_description = 'Überschreitungs-Status zurücksetzen'
    
    def start_grace_period_manually(self, request, queryset):
        """Manually start grace period for selected users"""
        count = 0
        for storage in queryset:
            if storage.is_storage_exceeded() and not storage.is_in_grace_period:
                storage.start_grace_period()
                count += 1
        
        messages.success(request, f'Grace Period für {count} Benutzer gestartet.')
    start_grace_period_manually.short_description = 'Grace Period manuell starten'
    
    def increase_quota_100mb(self, request, queryset):
        """Increase storage quota by 100MB"""
        count = queryset.count()
        for storage in queryset:
            storage.max_storage += 104857600  # +100MB
            storage.save()
        
        messages.success(request, f'Speicherplatz für {count} Benutzer um 100MB erhöht.')
    increase_quota_100mb.short_description = 'Speicherplatz um 100MB erhöhen'
    
    def increase_quota_500mb(self, request, queryset):
        """Increase storage quota by 500MB"""
        count = queryset.count()
        for storage in queryset:
            storage.max_storage += 524288000  # +500MB
            storage.save()
        
        messages.success(request, f'Speicherplatz für {count} Benutzer um 500MB erhöht.')
    increase_quota_500mb.short_description = 'Speicherplatz um 500MB erhöhen'
    
    # Custom Views
    def recalculate_single_view(self, request, storage_id):
        """Recalculate storage for a single user"""
        try:
            storage = UserStorage.objects.get(pk=storage_id)
            total_size = Video.objects.filter(user=storage.user).aggregate(
                total=Sum('file_size')
            )['total'] or 0
            
            old_usage = storage.used_storage
            storage.used_storage = total_size
            storage.save()
            
            messages.success(
                request, 
                f'Speicherplatz für {storage.user.username} neu berechnet: '
                f'{old_usage/1024/1024:.2f} MB → {total_size/1024/1024:.2f} MB'
            )
        except UserStorage.DoesNotExist:
            messages.error(request, 'Speicherplatz-Eintrag nicht gefunden.')
        
        return redirect('admin:videos_userstorage_changelist')
    
    def storage_dashboard_view(self, request):
        """Storage dashboard with statistics"""
        # Calculate statistics
        all_storage = UserStorage.objects.all()
        total_users = all_storage.count()
        premium_users = all_storage.filter(is_premium=True).count()
        
        total_used = sum(s.used_storage for s in all_storage) / 1024 / 1024  # MB
        total_allocated = sum(s.max_storage for s in all_storage) / 1024 / 1024  # MB
        
        # Top users by usage
        top_users = all_storage.order_by('-used_storage')[:10]
        
        # Users near quota (>80%)
        near_quota_users = [
            s for s in all_storage 
            if s.max_storage > 0 and (s.used_storage / s.max_storage) > 0.8
        ]
        
        context = {
            'title': 'Speicherplatz-Dashboard',
            'total_users': total_users,
            'premium_users': premium_users,
            'free_users': total_users - premium_users,
            'total_used_mb': total_used,
            'total_allocated_mb': total_allocated,
            'usage_percentage': (total_used / total_allocated * 100) if total_allocated > 0 else 0,
            'top_users': top_users,
            'near_quota_users': near_quota_users,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/videos/storage_dashboard.html', context)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_plan_name', 'storage_limit_mb', 'price_monthly', 'is_active', 'start_date']
    list_filter = ['storage_limit_mb', 'is_active', 'start_date']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_plan_name(self, obj):
        return obj.get_plan_name()
    get_plan_name.short_description = 'Plan'
