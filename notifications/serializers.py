from rest_framework import serializers

from .models import Notification


class NotificationActorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class NotificationSerializer(serializers.ModelSerializer):
    actor = NotificationActorSerializer(read_only=True)
    # Denormalised so the notification list can link to and label a report
    # without the client fetching each one separately.
    report_id = serializers.IntegerField(source='report.id', read_only=True, default=None)
    report_title = serializers.CharField(source='report.title', read_only=True, default=None)

    class Meta:
        model = Notification
        fields = (
            'id', 'kind', 'message', 'is_read', 'created_at',
            'actor', 'report_id', 'report_title',
        )
        read_only_fields = fields
