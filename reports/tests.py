from accounts.models import CustomUser
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import ActivityLog, Comment, Report


def make_user(email, role, **extra):
    return CustomUser.objects.create_user(
        email=email, password='pw-testing-123', first_name=role.title(),
        last_name='Account', role=role, **extra,
    )


class ReportVisibilityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('owner@st.test', 'user')
        cls.other_user = make_user('other@st.test', 'user')
        cls.analyst = make_user('analyst@st.test', 'analyst')
        cls.dev = make_user('dev@st.test', 'developer')
        cls.other_dev = make_user('otherdev@st.test', 'developer')
        cls.admin = make_user('admin@st.test', 'admin')

        cls.owned = Report.objects.create(title='Owned', description='x', created_by=cls.owner)
        cls.others = Report.objects.create(
            title='Others', description='x', created_by=cls.other_user,
        )
        cls.assigned_to_dev = Report.objects.create(
            title='Assigned', description='x', created_by=cls.other_user, assigned_to=cls.dev,
        )

    def list_titles(self, user):
        self.client.force_authenticate(user)
        res = self.client.get(reverse('report-list'))
        return {r['title'] for r in res.data}

    def test_user_sees_only_own_created_reports(self):
        self.assertEqual(self.list_titles(self.owner), {'Owned'})

    def test_developer_sees_only_assigned_reports(self):
        self.assertEqual(self.list_titles(self.dev), {'Assigned'})
        self.assertEqual(self.list_titles(self.other_dev), set())

    def test_analyst_and_admin_see_everything(self):
        expected = {'Owned', 'Others', 'Assigned'}
        self.assertEqual(self.list_titles(self.analyst), expected)
        self.assertEqual(self.list_titles(self.admin), expected)


class ReportCreateTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('user@st.test', 'user')
        cls.other = make_user('other@st.test', 'user')

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_create_ignores_client_supplied_status_and_assigned_to_and_created_by(self):
        res = self.client.post(reverse('report-list'), {
            'title': 'New finding', 'description': 'x', 'severity': 'high',
            'status': 'closed', 'assigned_to': self.other.id, 'created_by': self.other.id,
        })
        self.assertEqual(res.status_code, 201)
        report = Report.objects.get(pk=res.data['id'])
        self.assertEqual(report.status, Report.Status.NEW)
        self.assertIsNone(report.assigned_to)
        self.assertEqual(report.created_by, self.user)

    def test_new_fields_round_trip_with_sane_defaults(self):
        res = self.client.post(reverse('report-list'), {
            'title': 'New finding', 'description': 'x',
            'priority': 'urgent', 'category': 'network', 'due_date': '2026-12-01',
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['priority'], 'urgent')
        self.assertEqual(res.data['category'], 'network')
        self.assertEqual(res.data['due_date'], '2026-12-01')

        res_defaults = self.client.post(reverse('report-list'), {'title': 'Defaults', 'description': 'x'})
        self.assertEqual(res_defaults.data['priority'], 'medium')
        self.assertEqual(res_defaults.data['category'], 'other')
        self.assertIsNone(res_defaults.data['due_date'])

    def test_invalid_choice_value_returns_400(self):
        res = self.client.post(reverse('report-list'), {
            'title': 'Bad', 'description': 'x', 'priority': 'not-a-real-priority',
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('priority', res.data)

    def test_create_logs_activity(self):
        res = self.client.post(reverse('report-list'), {'title': 'Logged', 'description': 'x'})
        logs = ActivityLog.objects.filter(report_id=res.data['id'])
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, 'created')


class ReportUpdateAuthorizationTests(APITestCase):
    """Regression coverage for the fix: PUT/PATCH /api/reports/{id}/ must
    never be able to change status or assigned_to, and only the creator
    (while status=new) or an admin may use it at all."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('owner@st.test', 'user')
        cls.other_user = make_user('other@st.test', 'user')
        cls.analyst = make_user('analyst@st.test', 'analyst')
        cls.dev = make_user('dev@st.test', 'developer')
        cls.admin = make_user('admin@st.test', 'admin')

    def setUp(self):
        self.report = Report.objects.create(
            title='Original', description='x', created_by=self.owner,
        )
        self.url = reverse('report-detail', args=[self.report.pk])

    def test_status_and_assigned_to_are_not_writable_through_generic_update(self):
        self.client.force_authenticate(self.owner)
        res = self.client.patch(self.url, {
            'title': 'Renamed', 'status': 'closed', 'assigned_to': self.dev.id,
        })
        self.assertEqual(res.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, 'Renamed')
        self.assertEqual(self.report.status, Report.Status.NEW)
        self.assertIsNone(self.report.assigned_to)

    def test_non_owner_non_admin_roles_cannot_update_at_all(self):
        # visible_reports() scopes the queryset before CanEditReport ever
        # runs, so a role that can't see this report at all (it's not
        # theirs, not assigned to them) 404s rather than 403s - the same
        # behavior the set_status lifecycle already relies on.
        for user in (self.other_user, self.dev):
            self.client.force_authenticate(user)
            res = self.client.patch(self.url, {'status': 'closed', 'assigned_to': user.id})
            self.assertEqual(res.status_code, 404, f'{user.role} should not see this report')

        # The analyst DOES see every report, so they reach the permission
        # check itself and are correctly denied by it.
        self.client.force_authenticate(self.analyst)
        res = self.client.patch(self.url, {'status': 'closed', 'assigned_to': self.analyst.id})
        self.assertEqual(res.status_code, 403)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.NEW)
        self.assertIsNone(self.report.assigned_to)

    def test_creator_can_edit_only_while_status_is_new(self):
        self.report.status = Report.Status.VERIFIED
        self.report.save()
        self.client.force_authenticate(self.owner)
        res = self.client.patch(self.url, {'title': 'Too late'})
        self.assertEqual(res.status_code, 403)

    def test_admin_can_edit_regardless_of_status(self):
        self.report.status = Report.Status.CLOSED
        self.report.save()
        self.client.force_authenticate(self.admin)
        res = self.client.patch(self.url, {'title': 'Admin fix'})
        self.assertEqual(res.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, 'Admin fix')

    def test_edit_logs_activity(self):
        self.client.force_authenticate(self.owner)
        self.client.patch(self.url, {'title': 'Renamed'})
        self.assertTrue(
            ActivityLog.objects.filter(report=self.report, action='edited').exists(),
        )


class ReportDeleteTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('owner@st.test', 'user')
        cls.other_user = make_user('other@st.test', 'user')
        cls.admin = make_user('admin@st.test', 'admin')

    def setUp(self):
        self.report = Report.objects.create(
            title='Deletable', description='x', created_by=self.owner,
        )
        self.url = reverse('report-detail', args=[self.report.pk])

    def test_creator_can_delete_while_new(self):
        self.client.force_authenticate(self.owner)
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Report.objects.filter(pk=self.report.pk).exists())

    def test_creator_cannot_delete_after_status_leaves_new(self):
        self.report.status = Report.Status.VERIFIED
        self.report.save()
        self.client.force_authenticate(self.owner)
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Report.objects.filter(pk=self.report.pk).exists())

    def test_other_user_cannot_delete(self):
        # Not the creator and this report isn't assigned to them either,
        # so visible_reports() excludes it before IsOwnerOrAdmin ever
        # runs - a 404, not a 403.
        self.client.force_authenticate(self.other_user)
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 404)

    def test_admin_can_delete_regardless_of_status(self):
        self.report.status = Report.Status.CLOSED
        self.report.save()
        self.client.force_authenticate(self.admin)
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, 204)


class SetStatusLifecycleTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('owner@st.test', 'user')
        cls.analyst = make_user('analyst@st.test', 'analyst')
        cls.dev = make_user('dev@st.test', 'developer')
        cls.other_dev = make_user('otherdev@st.test', 'developer')
        cls.admin = make_user('admin@st.test', 'admin')

    def setUp(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(reverse('report-list'), {'title': 'Lifecycle', 'description': 'x'})
        self.report = Report.objects.get(pk=res.data['id'])
        self.status_url = reverse('report-set-status', args=[self.report.pk])

    def test_analyst_may_only_set_in_review_or_verified(self):
        self.client.force_authenticate(self.analyst)
        self.assertEqual(
            self.client.patch(self.status_url, {'status': 'closed'}).status_code, 400,
        )
        self.assertEqual(
            self.client.patch(self.status_url, {'status': 'verified'}).status_code, 200,
        )

    def test_admin_assign_requires_assigned_to(self):
        self.client.force_authenticate(self.admin)
        res = self.client.patch(self.status_url, {'status': 'assigned'})
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(self.status_url, {'status': 'assigned', 'assigned_to': self.dev.id})
        self.assertEqual(res.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.assigned_to, self.dev)

    def test_developer_may_only_resolve_own_assignment(self):
        self.report.status = Report.Status.ASSIGNED
        self.report.assigned_to = self.dev
        self.report.save()

        self.client.force_authenticate(self.other_dev)
        res = self.client.patch(self.status_url, {'status': 'resolved'})
        self.assertEqual(res.status_code, 404)  # not in other_dev's scoped queryset

        self.client.force_authenticate(self.dev)
        res = self.client.patch(self.status_url, {'status': 'in_review'})
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(self.status_url, {'status': 'resolved'})
        self.assertEqual(res.status_code, 200)

    def test_full_lifecycle_produces_expected_activity_sequence(self):
        self.client.force_authenticate(self.analyst)
        self.client.patch(self.status_url, {'status': 'verified'})

        self.client.force_authenticate(self.admin)
        self.client.patch(self.status_url, {'status': 'assigned', 'assigned_to': self.dev.id})

        self.client.force_authenticate(self.dev)
        self.client.patch(self.status_url, {'status': 'resolved'})

        self.client.force_authenticate(self.admin)
        self.client.patch(self.status_url, {'status': 'closed'})

        logs = list(ActivityLog.objects.filter(report=self.report).order_by('created_at'))
        self.assertEqual(len(logs), 5)  # creation + 4 status changes
        self.assertEqual(logs[0].action, 'created')
        self.assertEqual([l.action for l in logs[1:]], ['status_changed'] * 4)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.CLOSED)


class CommentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('owner@st.test', 'user')
        cls.other_user = make_user('other@st.test', 'user')
        cls.admin = make_user('admin@st.test', 'admin')

    def setUp(self):
        self.report = Report.objects.create(
            title='Commentable', description='x', created_by=self.owner,
        )
        self.comments_url = reverse('report-comments', args=[self.report.pk])

    def detail_url(self, comment):
        return reverse('report-comment-detail', args=[self.report.pk, comment.pk])

    def test_visible_report_user_can_list_and_add_comments(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self.comments_url, {'content': 'First'})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['author']['id'], self.owner.id)
        self.assertTrue(
            ActivityLog.objects.filter(report=self.report, action='comment_added').exists(),
        )

    def test_author_can_edit_own_comment(self):
        comment = Comment.objects.create(report=self.report, author=self.owner, content='Original')
        self.client.force_authenticate(self.owner)
        res = self.client.patch(self.detail_url(comment), {'content': 'Edited'})
        self.assertEqual(res.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.content, 'Edited')
        self.assertTrue(
            ActivityLog.objects.filter(report=self.report, action='comment_edited').exists(),
        )

    def test_non_author_non_admin_cannot_edit_or_delete(self):
        # other_user can't see this report at all (not theirs, not
        # assigned) - get_object() 404s before the comment-ownership
        # check is ever reached. Use an analyst instead to actually
        # exercise the comment-ownership permission itself: analysts see
        # every report, so they reach comment_detail and are denied by
        # its own author/admin check.
        comment = Comment.objects.create(report=self.report, author=self.owner, content='Original')
        analyst = make_user('analyst@st.test', 'analyst')

        self.client.force_authenticate(self.other_user)
        self.assertEqual(
            self.client.patch(self.detail_url(comment), {'content': 'Hijacked'}).status_code, 404,
        )

        self.client.force_authenticate(analyst)
        self.assertEqual(
            self.client.patch(self.detail_url(comment), {'content': 'Hijacked'}).status_code, 403,
        )
        self.assertEqual(self.client.delete(self.detail_url(comment)).status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.content, 'Original')

    def test_admin_can_delete_any_comment(self):
        comment = Comment.objects.create(report=self.report, author=self.owner, content='Original')
        self.client.force_authenticate(self.admin)
        res = self.client.delete(self.detail_url(comment))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())
        self.assertTrue(
            ActivityLog.objects.filter(report=self.report, action='comment_deleted').exists(),
        )

    def test_author_delete_own_comment(self):
        comment = Comment.objects.create(report=self.report, author=self.owner, content='Original')
        self.client.force_authenticate(self.owner)
        res = self.client.delete(self.detail_url(comment))
        self.assertEqual(res.status_code, 204)
