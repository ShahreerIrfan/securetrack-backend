from accounts.models import CustomUser
from django.urls import reverse
from reports.models import Report
from rest_framework.test import APITestCase

from .models import Notification


def make_user(email, role):
    return CustomUser.objects.create_user(
        email=email, password='pw-testing-123', first_name=role.title(),
        last_name='Account', role=role,
    )


class NotificationTriggerTests(APITestCase):
    """The events that should produce notifications, and - just as
    important - the ones that shouldn't."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('n-owner@st.test', 'user')
        cls.admin = make_user('n-admin@st.test', 'admin')
        cls.dev = make_user('n-dev@st.test', 'developer')

    def test_status_change_notifies_the_reporter(self):
        report = Report.objects.create(title='X', description='x', created_by=self.owner)
        self.client.force_authenticate(self.admin)
        self.client.patch(
            reverse('report-set-status', args=[report.id]), {'status': 'verified'},
        )
        note = Notification.objects.get(recipient=self.owner)
        self.assertEqual(note.kind, Notification.Kind.STATUS_CHANGED)
        self.assertEqual(note.actor, self.admin)
        self.assertFalse(note.is_read)

    def test_assignment_notifies_the_developer(self):
        report = Report.objects.create(
            title='X', description='x', created_by=self.owner, status='verified',
        )
        self.client.force_authenticate(self.admin)
        self.client.patch(
            reverse('report-set-status', args=[report.id]),
            {'status': 'assigned', 'assigned_to': self.dev.id},
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.dev, kind=Notification.Kind.ASSIGNED,
            ).exists(),
        )

    def test_comment_notifies_reporter_and_assignee_but_not_the_commenter(self):
        report = Report.objects.create(
            title='X', description='x', created_by=self.owner, assigned_to=self.dev,
        )
        self.client.force_authenticate(self.dev)
        self.client.post(reverse('report-comments', args=[report.id]), {'content': 'hi'})

        recipients = set(
            Notification.objects.filter(kind=Notification.Kind.COMMENT)
            .values_list('recipient__email', flat=True)
        )
        self.assertEqual(recipients, {self.owner.email})

    def test_acting_on_your_own_report_notifies_nobody(self):
        report = Report.objects.create(title='X', description='x', created_by=self.admin)
        self.client.force_authenticate(self.admin)
        self.client.patch(
            reverse('report-set-status', args=[report.id]), {'status': 'verified'},
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_admin_filing_on_behalf_notifies_that_user(self):
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('report-list'), {
            'title': 'Phoned in', 'description': 'x', 'created_by': self.owner.id,
        })
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner, kind=Notification.Kind.REPORT_FILED,
            ).exists(),
        )


class NotificationApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('n-api@st.test', 'user')
        cls.other = make_user('n-other@st.test', 'user')

    def setUp(self):
        self.client.force_authenticate(self.user)
        self.mine = Notification.objects.create(
            recipient=self.user, kind='comment', message='mine',
        )
        self.theirs = Notification.objects.create(
            recipient=self.other, kind='comment', message='theirs',
        )

    def test_list_returns_only_own_notifications(self):
        res = self.client.get(reverse('notification-list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual([n['message'] for n in res.data['results']], ['mine'])
        self.assertEqual(res.data['unread_count'], 1)

    def test_unread_count_endpoint(self):
        res = self.client.get(reverse('notification-unread-count'))
        self.assertEqual(res.data['unread_count'], 1)

    def test_mark_read(self):
        res = self.client.post(reverse('notification-mark-read', args=[self.mine.id]))
        self.assertEqual(res.status_code, 200)
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_read)

    def test_cannot_mark_someone_elses_notification_read(self):
        res = self.client.post(reverse('notification-mark-read', args=[self.theirs.id]))
        self.assertEqual(res.status_code, 404)
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)

    def test_mark_all_read_only_touches_own(self):
        res = self.client.post(reverse('notification-mark-all-read'))
        self.assertEqual(res.data['marked_read'], 1)
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)
