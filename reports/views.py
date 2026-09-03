from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from common.permissions import IsOwnerOrAdmin

from .models import Report
from .serializers import ReportSerializer, ReportWriteSerializer


class ReportViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return ReportSerializer
        return ReportWriteSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Report.objects.all().order_by('-created_at')
        if user.role == 'user':
            return qs.filter(created_by=user)
        if user.role == 'developer':
            return qs.filter(assigned_to=user)
        # analyst / admin see everything
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        # IsOwnerOrAdmin already confirmed the requester is the creator or
        # an admin. Admins may delete any report; the creator may only
        # delete while it's still New.
        user = self.request.user
        if user.role != 'admin' and instance.status != Report.Status.NEW:
            raise PermissionDenied(
                'A report can only be deleted by its creator while its status is "new".'
            )
        instance.delete()
