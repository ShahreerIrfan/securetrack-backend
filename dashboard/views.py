from accounts.models import CustomUser
from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.models import Report
from reports.queries import visible_reports
from reports.serializers import ReportSerializer


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

        data = {
            'total_reports': qs.count(),
            'by_status': by_status,
            'by_severity': by_severity,
        }

        if user.role == 'admin':
            users_by_role = {choice: 0 for choice, _ in CustomUser.Role.choices}
            for row in CustomUser.objects.values('role').annotate(count=Count('id')):
                users_by_role[row['role']] = row['count']
            data['users_by_role'] = users_by_role

        return Response(data)


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
