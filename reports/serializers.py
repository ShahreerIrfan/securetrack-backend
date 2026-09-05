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
    # Deliberately not exposing the raw file field/URL - attachments can be
    # sensitive, so they're only ever fetched through the authenticated,
    # permission-scoped `attachment` action. This is just enough for the
    # UI to know one exists and show its filename.
    attachment_name = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'status', 'priority',
            'category', 'vulnerability_type', 'due_date', 'attachment_name',
            'created_by', 'assigned_to', 'comments', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def get_attachment_name(self, obj):
        return obj.attachment.name.rsplit('/', 1)[-1] if obj.attachment else None


# Deliberately exclude "status" and "assigned_to" from both write
# serializers below. Those two fields only ever move through the
# role-gated set_status action - letting them through here would let any
# authenticated user PATCH them directly and bypass that logic entirely.
class ReportCreateSerializer(serializers.ModelSerializer):
    # Optional, admin-only: lets an admin log a report on behalf of
    # another user instead of themselves. Silently ignored for non-admins
    # in ReportViewSet.perform_create, which always has the final say on
    # created_by regardless of what's submitted here.
    created_by = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), required=False,
    )

    # Not declared explicitly - the model field's blank=True/null=True
    # already make ModelSerializer auto-generate this as optional, and
    # crucially, auto-generation is also what copies the model field's
    # validators (extension whitelist, size cap) onto the serializer
    # field. Declaring it by hand here would silently drop them.
    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'priority', 'category',
            'vulnerability_type', 'due_date', 'created_by', 'attachment',
        )
        read_only_fields = ('id',)


class ReportUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'priority', 'category',
            'vulnerability_type', 'due_date', 'attachment',
        )
        read_only_fields = ('id',)
