from .models import Notification


def notify(*, recipients, actor, report, kind, message):
    """Create one notification per distinct recipient.

    Skips the actor themselves (nobody needs telling about their own
    action) and any None entries, so callers can pass optional people
    like report.assigned_to without null-checking first.
    """
    seen = set()
    to_create = []
    for recipient in recipients:
        if recipient is None or recipient == actor or recipient.pk in seen:
            continue
        seen.add(recipient.pk)
        to_create.append(Notification(
            recipient=recipient,
            actor=actor,
            report=report,
            kind=kind,
            message=message,
        ))

    if to_create:
        Notification.objects.bulk_create(to_create)
    return to_create
