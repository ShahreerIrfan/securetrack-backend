import random
from datetime import timedelta

from accounts.models import CustomUser
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from reports.models import ActivityLog, Report

DEMO_PASSWORD = 'SecureTrack123'

DEMO_USERS = [
    ('analyst@securetrack.test', 'Ayesha', 'Rahman', CustomUser.Role.ANALYST),
    ('dev1@securetrack.test', 'Tanvir', 'Hasan', CustomUser.Role.DEVELOPER),
    ('dev2@securetrack.test', 'Nusrat', 'Jahan', CustomUser.Role.DEVELOPER),
    ('reporter@securetrack.test', 'Rakib', 'Islam', CustomUser.Role.USER),
]

TITLES = [
    'Reflected XSS on the search results page',
    'IDOR exposes other tenants\' invoices',
    'Session cookie missing HttpOnly and Secure flags',
    'SQL injection in the report export filter',
    'Rate limiting missing on the password reset endpoint',
    'Stored XSS in report comment bodies',
    'JWT refresh tokens never expire',
    'Directory listing enabled on the static host',
    'Weak password policy allows 4-character passwords',
    'CSRF token not validated on profile update',
    'Sensitive data written to application logs',
    'Outdated dependency with a known RCE advisory',
    'Admin panel reachable without MFA',
    'Unrestricted file upload accepts .svg payloads',
    'Email enumeration through the login error message',
    'Open redirect in the post-login "next" parameter',
    'Missing authorization check on report deletion',
    'Backup archive publicly readable in object storage',
]


class Command(BaseCommand):
    help = (
        'Populate the database with demo users, reports and activity so the '
        'role dashboards render with real data. Safe to re-run - it skips '
        'anything that already exists.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reports', type=int, default=len(TITLES),
            help='How many demo reports to create (default: one per demo title).',
        )
        parser.add_argument(
            '--days', type=int, default=30,
            help='Spread report creation dates over this many past days (default: 30).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)  # reproducible demo data across runs
        users = self._ensure_users()
        analyst = users[CustomUser.Role.ANALYST][0]
        developers = users[CustomUser.Role.DEVELOPER]
        reporters = users[CustomUser.Role.USER]
        admins = users[CustomUser.Role.ADMIN]

        if not admins:
            self.stdout.write(self.style.WARNING(
                'No admin account exists yet. Create one with:\n'
                '  python manage.py createsuperuser\n'
                'then set its role with:\n'
                '  python manage.py promote_admin <email>',
            ))

        created = self._create_reports(
            count=options['reports'],
            days=options['days'],
            reporters=reporters,
            analyst=analyst,
            developers=developers,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created} report(s). Demo accounts use password "{DEMO_PASSWORD}".',
        ))

    def _ensure_users(self):
        by_role = {role: [] for role, _ in CustomUser.Role.choices}

        for email, first, last, role in DEMO_USERS:
            user, was_created = CustomUser.objects.get_or_create(
                email=email,
                defaults={'first_name': first, 'last_name': last, 'role': role},
            )
            if was_created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                self.stdout.write(f'  + {role}: {email}')

        for user in CustomUser.objects.all():
            by_role[user.role].append(user)
        return by_role

    def _create_reports(self, *, count, days, reporters, analyst, developers):
        if not reporters:
            self.stdout.write(self.style.ERROR('No "user" accounts to author reports.'))
            return 0

        now = timezone.now()
        severities = [s for s, _ in Report.Severity.choices]
        created = 0

        for index in range(count):
            title = TITLES[index % len(TITLES)]
            if count > len(TITLES):
                title = f'{title} ({index // len(TITLES) + 1})'
            if Report.objects.filter(title=title).exists():
                continue

            age_days = random.randint(0, max(days - 1, 0))
            created_at = now - timedelta(days=age_days, hours=random.randint(0, 23))
            status = self._status_for_age(age_days, days)
            assignee = (
                random.choice(developers)
                if developers and status in (
                    Report.Status.ASSIGNED, Report.Status.RESOLVED, Report.Status.CLOSED,
                )
                else None
            )

            report = Report.objects.create(
                title=title,
                description=(
                    f'Demo finding seeded for dashboard testing. Reproduced on '
                    f'{created_at.date()}. Severity triaged by the reporting workflow.'
                ),
                severity=random.choice(severities),
                status=status,
                created_by=random.choice(reporters),
                assigned_to=assignee,
            )

            # created_at/updated_at are auto_now_add/auto_now, so they can
            # only be backdated with an explicit post-save update.
            resolved_at = created_at + timedelta(hours=random.randint(4, 96))
            Report.objects.filter(pk=report.pk).update(
                created_at=created_at,
                updated_at=resolved_at if status in (
                    Report.Status.RESOLVED, Report.Status.CLOSED,
                ) else created_at,
            )

            self._log_history(report, created_at, status, analyst, assignee)
            created += 1

        return created

    @staticmethod
    def _status_for_age(age_days, window):
        """Older reports are further along the workflow, so the trend chart
        shows a believable intake-then-resolution curve rather than noise."""
        if age_days < window * 0.15:
            return Report.Status.NEW
        if age_days < window * 0.3:
            return random.choice([Report.Status.NEW, Report.Status.IN_REVIEW])
        if age_days < window * 0.5:
            return random.choice([Report.Status.IN_REVIEW, Report.Status.VERIFIED])
        if age_days < window * 0.7:
            return random.choice([Report.Status.VERIFIED, Report.Status.ASSIGNED])
        return random.choice([Report.Status.RESOLVED, Report.Status.CLOSED])

    def _log_history(self, report, created_at, status, analyst, assignee):
        actor = assignee or analyst
        if actor is None or status == Report.Status.NEW:
            return
        log = ActivityLog.objects.create(
            report=report,
            actor=actor,
            action='status_changed',
            detail=f'Status changed from "new" to "{status}"',
        )
        ActivityLog.objects.filter(pk=log.pk).update(
            created_at=created_at + timedelta(hours=2),
        )
