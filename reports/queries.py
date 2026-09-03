from .models import Report


def visible_reports(user):
    """Reports a user is allowed to see, by role. Shared by ReportViewSet
    and the dashboard app so the visibility rule lives in exactly one
    place."""
    qs = Report.objects.all().order_by('-created_at')
    if user.role == 'user':
        return qs.filter(created_by=user)
    if user.role == 'developer':
        return qs.filter(assigned_to=user)
    # analyst / admin see everything
    return qs
