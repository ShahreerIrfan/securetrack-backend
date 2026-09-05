from django.conf import settings
from django.db import models


class Notification(models.Model):
    """One in-app alert for one recipient. Created explicitly at the point
    the triggering event happens (see notifications/services.py) rather
    than via signals, so the reasons a notification exists are all
    greppable from the views that cause them."""

    class Kind(models.TextChoices):
        STATUS_CHANGED = 'status_changed', 'Status Changed'
        ASSIGNED = 'assigned', 'Assigned'
        COMMENT = 'comment', 'New Comment'
        REPORT_FILED = 'report_filed', 'Report Filed For You'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    # The person whose action triggered this. Nullable so deleting an
    # account doesn't erase the notifications it caused for other people.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications_triggered',
    )
    report = models.ForeignKey(
        'reports.Report',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Every read path is "this user's notifications, newest first",
            # usually narrowed to unread for the badge count.
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f'{self.kind} for {self.recipient}'
