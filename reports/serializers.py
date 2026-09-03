from rest_framework import serializers

from accounts.models import CustomUser

from .models import Report


class NestedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'role')
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    created_by = NestedUserSerializer(read_only=True)
    assigned_to = NestedUserSerializer(read_only=True)

    class Meta:
        model = Report
        fields = (
            'id', 'title', 'description', 'severity', 'status',
            'created_by', 'assigned_to', 'created_at', 'updated_at',
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
