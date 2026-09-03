from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'status', 'created_by', 'assigned_to', 'created_at')
    list_filter = ('severity', 'status')
