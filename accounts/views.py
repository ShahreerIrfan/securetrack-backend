from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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
