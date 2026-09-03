from accounts.models import CustomUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsOwnerOrAdmin

from .models import Report
from .serializers import ReportSerializer, ReportWriteSerializer


class ReportViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_fields = ('severity', 'status', 'assigned_to')
    search_fields = ('title', 'description')

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

    @action(detail=True, methods=['patch'], url_path='status')
    def set_status(self, request, pk=None):
        report = self.get_object()
        user = request.user
        new_status = request.data.get('status')

        valid_statuses = dict(Report.Status.choices)
        if new_status not in valid_statuses:
            return Response(
                {'detail': f'"{new_status}" is not a valid status.'}, status=400,
            )

        if user.role == 'analyst':
            if new_status not in (Report.Status.IN_REVIEW, Report.Status.VERIFIED):
                return Response(
                    {'detail': 'Analysts may only set status to "in_review" or "verified".'},
                    status=400,
                )

        elif user.role == 'admin':
            if new_status == Report.Status.ASSIGNED:
                assignee_id = request.data.get('assigned_to')
                if not assignee_id:
                    return Response(
                        {'detail': 'Setting status to "assigned" requires "assigned_to" in the same request.'},
                        status=400,
                    )
                try:
                    report.assigned_to = CustomUser.objects.get(pk=assignee_id)
                except CustomUser.DoesNotExist:
                    return Response(
                        {'detail': f'No user with id "{assignee_id}" exists.'}, status=400,
                    )
            # admins may set any other valid status without restriction

        elif user.role == 'developer':
            if new_status != Report.Status.RESOLVED:
                return Response(
                    {'detail': 'Developers may only set status to "resolved".'}, status=400,
                )
            if report.assigned_to_id != user.id:
                return Response(
                    {'detail': 'You may only resolve reports assigned to you.'}, status=400,
                )

        else:
            return Response(
                {'detail': f'Role "{user.role}" is not permitted to change report status.'},
                status=400,
            )

        report.status = new_status
        report.save()
        return Response(ReportSerializer(report).data)
