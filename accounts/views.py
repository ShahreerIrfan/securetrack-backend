from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin

from .models import CustomUser
from .serializers import (
    ChangePasswordSerializer,
    MeUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    """Public self-signup endpoint. Always creates role="user" accounts —
    use the admin-only UserViewSet to create staff roles."""

    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(role=CustomUser.Role.USER, is_active=True)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserViewSet(viewsets.ModelViewSet):
    """Admin-only user management. Unlike RegisterView, allows setting any
    role directly."""

    permission_classes = (IsAdmin,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_fields = ('role', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering_fields = ('date_joined', 'last_login', 'email', 'role')
    ordering = ('id',)

    def get_queryset(self):
        return CustomUser.objects.annotate(
            reports_created_count=Count('reports_created', distinct=True),
            reports_assigned_count=Count('reports_assigned', distinct=True),
        )

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return UserSerializer
        return UserCreateSerializer

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.pk == self.request.user.pk:
            # An admin editing their own row could otherwise demote or
            # deactivate themselves and lose access to this very endpoint,
            # with no way back in short of the Django shell.
            new_role = serializer.validated_data.get('role', instance.role)
            if new_role != instance.role:
                raise ValidationError({'role': 'You cannot change your own role.'})
            if serializer.validated_data.get('is_active', instance.is_active) is False:
                raise ValidationError({'is_active': 'You cannot deactivate your own account.'})
        serializer.save()

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError({'detail': 'You cannot delete your own account.'})
        instance.delete()


class MeView(APIView):
    """The authenticated user's own identity, resolved from their JWT -
    readable by anyone logged in, and editable for the few fields that
    aren't privilege-bearing (name and email, never role/is_active)."""

    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _payload(user):
        return {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
        }

    def get(self, request):
        return Response(self._payload(request.user))

    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._payload(request.user))


class ChangePasswordView(APIView):
    """Password change for the logged-in user. Separate from MeView so the
    profile form can't accidentally submit a password field, and so the
    current-password check lives in exactly one place."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password updated.'})
