from rest_framework.permissions import BasePermission

ADMIN = 'admin'
ANALYST = 'analyst'
DEVELOPER = 'developer'
USER = 'user'


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ADMIN)


class IsAnalyst(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == ANALYST)


class IsDeveloper(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == DEVELOPER)


class IsAdminOrAnalyst(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (ADMIN, ANALYST)
        )


class CanEditReport(BasePermission):
    """
    Field edits (title/description/severity/etc, not status or
    assignment - those only ever move through the dedicated set_status
    action) on a report: the creator may edit while status is still
    "new"; admins may always edit. Mirrors the destroy rule enforced in
    ReportViewSet.perform_destroy, kept symmetric on purpose.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == ADMIN:
            return True
        return obj.created_by_id == user.id and obj.status == obj.Status.NEW


class IsOwnerOrAdmin(BasePermission):
    """
    Grants access to admins, and to the object's owner. Ownership is
    resolved via a `created_by` attribute when present (e.g. Report),
    falling back to comparing the object itself to request.user (e.g. a
    CustomUser instance).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == ADMIN:
            return True
        owner = getattr(obj, 'created_by', obj)
        return owner == user
