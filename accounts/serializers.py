from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    # Populated by UserViewSet.get_queryset()'s annotations so the admin
    # user table can show each account's footprint without an N+1 of
    # per-row count queries.
    reports_created_count = serializers.IntegerField(read_only=True)
    reports_assigned_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'date_joined',
            'last_login',
            'reports_created_count',
            'reports_assigned_count',
        )
        read_only_fields = fields


class MeUpdateSerializer(serializers.ModelSerializer):
    """Self-service profile edit. Deliberately excludes role and is_active
    so a user can never promote or reactivate themselves here - those stay
    admin-only, via UserViewSet."""

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email')

    def validate_first_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('This field may not be blank.')
        return value

    def validate_last_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('This field may not be blank.')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        # Requiring the current password means a hijacked session still
        # can't lock the real owner out of their own account.
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    # Optional on update so an admin can change a role or deactivate an
    # account without being forced to reset that user's password.
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'first_name', 'last_name', 'password', 'role', 'is_active')

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'This field is required.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance
