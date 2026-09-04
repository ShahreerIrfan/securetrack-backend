from rest_framework import serializers

from reports.models import ActivityLog


class ActorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()


class GlobalActivitySerializer(serializers.ModelSerializer):
    """Activity log entry for the system-wide feed. Unlike the per-report
    serializer in "reports", this one carries the report it belongs to so
    the admin feed can link straight to it."""

    actor = ActorSerializer(read_only=True)
    report_id = serializers.IntegerField(source='report.id', read_only=True)
    report_title = serializers.CharField(source='report.title', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ('id', 'report_id', 'report_title', 'actor', 'action', 'detail', 'created_at')


class WorkloadRowSerializer(serializers.Serializer):
    """One developer's queue depth, built from annotations in WorkloadView."""

    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    open_assigned = serializers.IntegerField()
    resolved = serializers.IntegerField()
    total_assigned = serializers.IntegerField()


class TrendPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    created = serializers.IntegerField()
    resolved = serializers.IntegerField()
