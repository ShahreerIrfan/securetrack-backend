from django.contrib import admin

from .models import ActivityLog, Comment, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'status', 'created_by', 'assigned_to', 'created_at')
    list_filter = ('severity', 'status')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('report', 'author', 'created_at')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('report', 'actor', 'action', 'created_at')
