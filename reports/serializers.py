from rest_framework import serializers

from accounts.models import CustomUser

from .models import ActivityLog, Comment, Report


class NestedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'first_name', 'last_name', 'role')
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    author = NestedUserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'report', 'author', 'content', 'created_at')
        read_only_fields = ('id', 'report', 'author', 'created_at')


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = NestedUserSerializer(read_only=True)

    class Meta:
        model = ActivityLog
        fields = ('id', 'actor', 'action', 'detail', 'created_at')
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    created_by = NestedUserSerializer(read_only=True)
    assigned_to = NestedUserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'status',
            'created_by', 'assigned_to', 'comments', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')


class ReportWriteSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Report
        fields = ('id', 'title', 'description', 'severity', 'status', 'assigned_to')
        read_only_fields = ('id',)
