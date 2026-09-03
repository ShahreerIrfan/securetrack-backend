from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin

from .models import CustomUser
from .serializers import UserCreateSerializer, UserSerializer


class RegisterView(APIView):
    """Public self-signup endpoint. Always creates role="user" accounts —
    use the admin-only UserViewSet to create staff roles."""

    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(role=CustomUser.Role.USER)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserViewSet(viewsets.ModelViewSet):
    """Admin-only user management. Unlike RegisterView, allows setting any
    role directly."""

    queryset = CustomUser.objects.all().order_by('id')
    permission_classes = (IsAdmin,)
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('role',)

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return UserSerializer
        return UserCreateSerializer


class MeView(APIView):
    """Returns the authenticated user's identity, resolved from their JWT."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
        })
