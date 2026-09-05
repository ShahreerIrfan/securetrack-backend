from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-and-acknowledge only. Notifications are never created through
    the API - they're a side effect of actions elsewhere (see
    notifications/services.py)."""

    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)

    MAX_LIMIT = 100

    def get_queryset(self):
        # Scoped to the requester in one place, so no action below can
        # accidentally expose or mutate someone else's notifications.
        queryset = Notification.objects.filter(
            recipient=self.request.user,
        ).select_related('actor', 'report')

        if self.request.query_params.get('unread') == 'true':
            queryset = queryset.filter(is_read=False)
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            limit = int(request.query_params.get('limit', 20))
        except ValueError:
            return Response({'detail': '"limit" must be an integer.'}, status=400)
        limit = max(1, min(limit, self.MAX_LIMIT))

        queryset = self.get_queryset()
        return Response({
            'count': queryset.count(),
            'unread_count': self.get_queryset().filter(is_read=False).count(),
            'results': self.get_serializer(queryset[:limit], many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()
        return Response({'unread_count': count})

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).update(is_read=True)
        return Response({'marked_read': updated})
