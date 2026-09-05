from datetime import timedelta

from accounts.models import CustomUser
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin, IsAdminOrAnalyst
from reports.models import ActivityLog, Report
from reports.queries import visible_reports
from reports.serializers import ReportSerializer

from .serializers import (
    GlobalActivitySerializer,
    TrendPointSerializer,
    WorkloadRowSerializer,
)

# A report is "open" until someone resolves or closes it - these two
# groupings drive the open/unassigned/backlog numbers on every dashboard.
OPEN_STATUSES = (
    Report.Status.NEW,
    Report.Status.IN_REVIEW,
    Report.Status.VERIFIED,
    Report.Status.ASSIGNED,
)
DONE_STATUSES = (Report.Status.RESOLVED, Report.Status.CLOSED)


class StatsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        qs = visible_reports(user)

        # visible_reports() orders by -created_at; values().annotate()
        # would otherwise fold that into GROUP BY (created_at is unique
        # per row), silently splitting every report into its own group of
        # 1 instead of a real per-status/severity total. Clear it first.
        unordered = qs.order_by()

        by_status = {choice: 0 for choice, _ in Report.Status.choices}
        for row in unordered.values('status').annotate(count=Count('id')):
            by_status[row['status']] = row['count']

        by_severity = {choice: 0 for choice, _ in Report.Severity.choices}
        for row in unordered.values('severity').annotate(count=Count('id')):
            by_severity[row['severity']] = row['count']

        by_category = {choice: 0 for choice, _ in Report.Category.choices}
        for row in unordered.values('category').annotate(count=Count('id')):
            by_category[row['category']] = row['count']

        by_vulnerability_type = {
            choice: 0 for choice, _ in Report.VulnerabilityType.choices
        }
        for row in unordered.values('vulnerability_type').annotate(count=Count('id')):
            by_vulnerability_type[row['vulnerability_type']] = row['count']

        data = {
            'total_reports': qs.count(),
            'by_status': by_status,
            'by_severity': by_severity,
            'by_category': by_category,
            'by_vulnerability_type': by_vulnerability_type,
        }

        if user.role == 'admin':
            data.update(self._admin_extras(unordered))

        return Response(data)

    def _admin_extras(self, reports):
        """The extra counters only the admin dashboard renders. Kept off
        every other role's payload so a non-admin never receives
        system-wide numbers they aren't allowed to see."""
        week_ago = timezone.now() - timedelta(days=7)

        users_by_role = {choice: 0 for choice, _ in CustomUser.Role.choices}
        for row in CustomUser.objects.values('role').annotate(count=Count('id')):
            users_by_role[row['role']] = row['count']

        # Resolution time is measured as updated_at - created_at on
        # finished reports. updated_at moves on any edit, so treat this as
        # an approximation of turnaround rather than an exact SLA number.
        avg_resolution = reports.filter(status__in=DONE_STATUSES).aggregate(
            avg=Avg(F('updated_at') - F('created_at')),
        )['avg']

        return {
            'users_by_role': users_by_role,
            'active_users': CustomUser.objects.filter(is_active=True).count(),
            'inactive_users': CustomUser.objects.filter(is_active=False).count(),
            'open_reports': reports.filter(status__in=OPEN_STATUSES).count(),
            'unassigned_reports': reports.filter(
                status__in=OPEN_STATUSES, assigned_to__isnull=True,
            ).count(),
            'critical_open': reports.filter(
                status__in=OPEN_STATUSES, severity=Report.Severity.CRITICAL,
            ).count(),
            'created_this_week': reports.filter(created_at__gte=week_ago).count(),
            'resolved_this_week': reports.filter(
                status__in=DONE_STATUSES, updated_at__gte=week_ago,
            ).count(),
            'avg_resolution_hours': (
                round(avg_resolution.total_seconds() / 3600, 1) if avg_resolution else None
            ),
        }


class RecentView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        qs = visible_reports(user)

        if user.role == 'user':
            # most recent
            qs = qs.order_by('-created_at')
        elif user.role == 'analyst':
            # oldest-unreviewed
            qs = qs.filter(status=Report.Status.NEW).order_by('created_at')
        elif user.role == 'developer':
            # assigned-to-me (already scoped by visible_reports); most
            # recently touched first
            qs = qs.order_by('-updated_at')
        elif user.role == 'admin':
            # newest-verified-unassigned
            qs = qs.filter(
                status=Report.Status.VERIFIED, assigned_to__isnull=True,
            ).order_by('-created_at')

        return Response(ReportSerializer(qs[:5], many=True).data)


class TrendsView(APIView):
    """Per-day created vs. resolved counts for the intake/throughput chart.

    Days with no activity are filled in with zeros so the chart shows a
    continuous timeline instead of collapsing empty days together.
    """

    permission_classes = (IsAdminOrAnalyst,)

    MAX_DAYS = 90

    def get(self, request):
        try:
            days = int(request.query_params.get('days', 14))
        except ValueError:
            return Response({'detail': '"days" must be an integer.'}, status=400)
        if not 1 <= days <= self.MAX_DAYS:
            return Response(
                {'detail': f'"days" must be between 1 and {self.MAX_DAYS}.'}, status=400,
            )

        reports = visible_reports(request.user).order_by()
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        created = self._count_by_day(reports.filter(created_at__date__gte=start), 'created_at')
        resolved = self._count_by_day(
            reports.filter(status__in=DONE_STATUSES, updated_at__date__gte=start), 'updated_at',
        )

        points = [
            {
                'date': start + timedelta(days=offset),
                'created': created.get(start + timedelta(days=offset), 0),
                'resolved': resolved.get(start + timedelta(days=offset), 0),
            }
            for offset in range(days)
        ]
        return Response(TrendPointSerializer(points, many=True).data)

    @staticmethod
    def _count_by_day(queryset, field):
        rows = queryset.annotate(day=TruncDate(field)).values('day').annotate(count=Count('id'))
        return {row['day']: row['count'] for row in rows}


class WorkloadView(APIView):
    """Per-developer queue depth, so an admin can see who is overloaded
    before assigning the next report."""

    permission_classes = (IsAdmin,)

    def get(self, request):
        developers = (
            CustomUser.objects.filter(role=CustomUser.Role.DEVELOPER, is_active=True)
            .annotate(
                open_assigned=Count(
                    'reports_assigned',
                    filter=Q(reports_assigned__status__in=OPEN_STATUSES),
                    distinct=True,
                ),
                resolved=Count(
                    'reports_assigned',
                    filter=Q(reports_assigned__status__in=DONE_STATUSES),
                    distinct=True,
                ),
                total_assigned=Count('reports_assigned', distinct=True),
            )
            .order_by('-open_assigned', 'first_name')
        )
        return Response(WorkloadRowSerializer(developers, many=True).data)


class ActivityFeedView(APIView):
    """System-wide audit trail across every report - the admin-side
    counterpart to the per-report /api/reports/{id}/activity/ endpoint.

    Returns a {count, results} envelope rather than a bare list so the
    audit log page can paginate without a second count request.
    """

    permission_classes = (IsAdminOrAnalyst,)

    MAX_LIMIT = 100

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 15))
            offset = int(request.query_params.get('offset', 0))
        except ValueError:
            return Response(
                {'detail': '"limit" and "offset" must be integers.'}, status=400,
            )
        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        logs = ActivityLog.objects.select_related('actor', 'report')

        action = request.query_params.get('action')
        if action:
            logs = logs.filter(action=action)

        actor = request.query_params.get('actor')
        if actor:
            try:
                logs = logs.filter(actor_id=int(actor))
            except ValueError:
                return Response({'detail': '"actor" must be a user id.'}, status=400)

        days = request.query_params.get('days')
        if days:
            try:
                days_int = int(days)
            except ValueError:
                return Response({'detail': '"days" must be an integer.'}, status=400)
            if days_int < 1:
                return Response({'detail': '"days" must be at least 1.'}, status=400)
            logs = logs.filter(created_at__gte=timezone.now() - timedelta(days=days_int))

        search = request.query_params.get('search')
        if search:
            logs = logs.filter(
                Q(detail__icontains=search) | Q(report__title__icontains=search),
            )

        total = logs.count()
        page = logs.order_by('-created_at')[offset:offset + limit]
        return Response({
            'count': total,
            'results': GlobalActivitySerializer(page, many=True).data,
        })


class ActivityActionsView(APIView):
    """The distinct action values actually present in the log, so the audit
    page's filter only ever offers options that would return rows."""

    permission_classes = (IsAdminOrAnalyst,)

    def get(self, request):
        actions = (
            ActivityLog.objects.order_by().values_list('action', flat=True).distinct()
        )
        return Response(sorted(actions))
