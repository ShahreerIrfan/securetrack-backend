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
        fields = ('id', 'report', 'author', 'content', 'created_at', 'updated_at')
        read_only_fields = ('id', 'report', 'author', 'created_at', 'updated_at')


class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ('content',)


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
            'id', 'title', 'description', 'severity', 'status', 'priority',
            'category', 'vulnerability_type', 'due_date', 'created_by', 'assigned_to',
            'comments', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')


# Deliberately exclude "status" and "assigned_to" from both write
# serializers below. Those two fields only ever move through the
# role-gated set_status action - letting them through here would let any
# authenticated user PATCH them directly and bypass that logic entirely.
class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'priority', 'category',
            'vulnerability_type', 'due_date',
        )
        read_only_fields = ('id',)


class ReportUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'priority', 'category',
            'vulnerability_type', 'due_date',
        )
        read_only_fields = ('id',)
