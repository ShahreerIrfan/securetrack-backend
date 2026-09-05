from accounts.models import CustomUser
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import CanEditReport, IsOwnerOrAdmin

from .models import ActivityLog, Comment, Report
from .queries import visible_reports
from .serializers import (
    ActivityLogSerializer,
    CommentSerializer,
    CommentUpdateSerializer,
    ReportCreateSerializer,
    ReportSerializer,
    ReportUpdateSerializer,
)


class ReportViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_fields = ('severity', 'status', 'priority', 'category', 'vulnerability_type', 'assigned_to')
    search_fields = ('title', 'description')

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        if self.action in ('update', 'partial_update'):
            return [IsAuthenticated(), CanEditReport()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return ReportSerializer
        if self.action == 'create':
            return ReportCreateSerializer
        if self.action in ('update', 'partial_update'):
            return ReportUpdateSerializer
        return ReportSerializer

    def get_queryset(self):
        return visible_reports(self.request.user)

    def perform_create(self, serializer):
        report = serializer.save(created_by=self.request.user)
        ActivityLog.objects.create(
            report=report, actor=self.request.user, action='created', detail='Report created',
        )

    def perform_update(self, serializer):
        serializer.save()
        ActivityLog.objects.create(
            report=serializer.instance, actor=self.request.user, action='edited',
            detail='Report details updated',
        )

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

        old_status = report.status
        assignment_detail = ''

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
                    assignee = CustomUser.objects.get(pk=assignee_id)
                except CustomUser.DoesNotExist:
                    return Response(
                        {'detail': f'No user with id "{assignee_id}" exists.'}, status=400,
                    )
                report.assigned_to = assignee
                assignment_detail = f' and assigned to {assignee.first_name} {assignee.last_name}'
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

        ActivityLog.objects.create(
            report=report,
            actor=user,
            action='status_changed',
            detail=f'Status changed from "{old_status}" to "{new_status}"{assignment_detail}',
        )

        return Response(ReportSerializer(report).data)

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        report = self.get_object()

        if request.method == 'POST':
            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comment = serializer.save(report=report, author=request.user)
            ActivityLog.objects.create(
                report=report, actor=request.user, action='comment_added',
                detail='Comment added',
            )
            return Response(CommentSerializer(comment).data, status=201)

        return Response(CommentSerializer(report.comments.all(), many=True).data)

    @action(
        detail=True, methods=['patch', 'delete'],
        url_path=r'comments/(?P<comment_id>[^/.]+)',
    )
    def comment_detail(self, request, pk=None, comment_id=None):
        report = self.get_object()
        comment = get_object_or_404(Comment, pk=comment_id, report=report)
        user = request.user

        if comment.author_id != user.id and user.role != 'admin':
            raise PermissionDenied('You may only edit or delete your own comments.')

        if request.method == 'DELETE':
            comment.delete()
            ActivityLog.objects.create(
                report=report, actor=user, action='comment_deleted',
                detail=f'Comment #{comment_id} deleted',
            )
            return Response(status=204)

        serializer = CommentUpdateSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        ActivityLog.objects.create(
            report=report, actor=user, action='comment_edited', detail='Comment edited',
        )
        return Response(CommentSerializer(comment).data)

    @action(detail=True, methods=['get'], url_path='activity')
    def activity(self, request, pk=None):
        report = self.get_object()
        return Response(ActivityLogSerializer(report.activity_logs.all(), many=True).data)
