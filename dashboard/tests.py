from accounts.models import CustomUser
from django.urls import reverse
from rest_framework.test import APITestCase

from reports.models import ActivityLog, Report


def make_user(email, role, **extra):
    return CustomUser.objects.create_user(
        email=email, password='pw-testing-123', first_name=role.title(),
        last_name='Account', role=role, **extra,
    )


class DashboardEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user('admin@st.test', 'admin')
        cls.analyst = make_user('analyst@st.test', 'analyst')
        cls.dev = make_user('dev@st.test', 'developer')
        cls.reporter = make_user('user@st.test', 'user')

        cls.open_critical = Report.objects.create(
            title='Critical open', description='x', severity=Report.Severity.CRITICAL,
            status=Report.Status.VERIFIED, created_by=cls.reporter,
        )
        cls.assigned = Report.objects.create(
            title='Assigned to dev', description='x', status=Report.Status.ASSIGNED,
            created_by=cls.reporter, assigned_to=cls.dev,
        )
        cls.done = Report.objects.create(
            title='Resolved', description='x', status=Report.Status.RESOLVED,
            created_by=cls.reporter, assigned_to=cls.dev,
        )
        ActivityLog.objects.create(
            report=cls.done, actor=cls.dev, action='status_changed',
            detail='Status changed from "assigned" to "resolved"',
        )

    def test_stats_includes_admin_extras_for_admin_only(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get(reverse('dashboard-stats')).data
        self.assertEqual(data['total_reports'], 3)
        self.assertEqual(data['open_reports'], 2)
        self.assertEqual(data['unassigned_reports'], 1)
        self.assertEqual(data['critical_open'], 1)
        self.assertEqual(data['users_by_role']['developer'], 1)
        self.assertEqual(data['active_users'], 4)

        self.client.force_authenticate(self.analyst)
        analyst_data = self.client.get(reverse('dashboard-stats')).data
        self.assertNotIn('users_by_role', analyst_data)
        self.assertNotIn('unassigned_reports', analyst_data)

    def test_stats_by_status_counts_are_grouped_not_split_per_row(self):
        self.client.force_authenticate(self.admin)
        by_status = self.client.get(reverse('dashboard-stats')).data['by_status']
        self.assertEqual(sum(by_status.values()), 3)

    def test_trends_zero_fills_every_day_in_range(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get(reverse('dashboard-trends'), {'days': 7})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 7)
        self.assertEqual(sum(p['created'] for p in res.data), 3)
        # Today's bucket holds everything created in setUpTestData.
        self.assertEqual(res.data[-1]['created'], 3)

    def test_trends_rejects_out_of_range_days(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(reverse('dashboard-trends'), {'days': 0}).status_code, 400)
        self.assertEqual(
            self.client.get(reverse('dashboard-trends'), {'days': 500}).status_code, 400,
        )
        self.assertEqual(
            self.client.get(reverse('dashboard-trends'), {'days': 'abc'}).status_code, 400,
        )

    def test_workload_counts_each_developer_queue(self):
        self.client.force_authenticate(self.admin)
        rows = self.client.get(reverse('dashboard-workload')).data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['email'], 'dev@st.test')
        self.assertEqual(rows[0]['open_assigned'], 1)
        self.assertEqual(rows[0]['resolved'], 1)
        self.assertEqual(rows[0]['total_assigned'], 2)

    def test_activity_feed_carries_its_report_and_is_newest_first(self):
        self.client.force_authenticate(self.admin)
        body = self.client.get(reverse('dashboard-activity')).data
        self.assertEqual(body['count'], 1)
        entries = body['results']
        self.assertEqual(entries[0]['report_id'], self.done.id)
        self.assertEqual(entries[0]['report_title'], 'Resolved')
        self.assertEqual(entries[0]['actor']['role'], 'developer')

    def test_activity_feed_filters_by_action_actor_and_search(self):
        ActivityLog.objects.create(
            report=self.assigned, actor=self.admin, action='comment_added',
            detail='Comment added',
        )
        self.client.force_authenticate(self.admin)
        url = reverse('dashboard-activity')

        by_action = self.client.get(url, {'action': 'comment_added'}).data
        self.assertEqual(by_action['count'], 1)
        self.assertEqual(by_action['results'][0]['action'], 'comment_added')

        by_actor = self.client.get(url, {'actor': self.dev.id}).data
        self.assertEqual(by_actor['count'], 1)
        self.assertEqual(by_actor['results'][0]['actor']['role'], 'developer')

        by_search = self.client.get(url, {'search': 'Resolved'}).data
        self.assertEqual(by_search['count'], 1)

    def test_activity_feed_paginates_with_limit_and_offset(self):
        for i in range(4):
            ActivityLog.objects.create(
                report=self.assigned, actor=self.admin, action='edited', detail=f'edit {i}',
            )
        self.client.force_authenticate(self.admin)
        url = reverse('dashboard-activity')

        first = self.client.get(url, {'limit': 2, 'offset': 0}).data
        self.assertEqual(first['count'], 5)
        self.assertEqual(len(first['results']), 2)

        second = self.client.get(url, {'limit': 2, 'offset': 2}).data
        self.assertEqual(len(second['results']), 2)
        self.assertNotEqual(
            [e['id'] for e in first['results']], [e['id'] for e in second['results']],
        )

    def test_activity_actions_lists_distinct_actions(self):
        ActivityLog.objects.create(
            report=self.assigned, actor=self.admin, action='comment_added', detail='x',
        )
        self.client.force_authenticate(self.admin)
        res = self.client.get(reverse('dashboard-activity-actions'))
        self.assertEqual(res.data, ['comment_added', 'status_changed'])

    def test_stats_includes_category_and_vulnerability_breakdowns(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get(reverse('dashboard-stats')).data
        self.assertEqual(sum(data['by_category'].values()), 3)
        self.assertEqual(sum(data['by_vulnerability_type'].values()), 3)

    def test_admin_only_endpoints_reject_lower_roles(self):
        for user in (self.analyst, self.dev, self.reporter):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(reverse('dashboard-workload')).status_code, 403)

        for user in (self.dev, self.reporter):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(reverse('dashboard-trends')).status_code, 403)
            self.assertEqual(self.client.get(reverse('dashboard-activity')).status_code, 403)

    def test_analyst_may_read_trends_and_activity(self):
        self.client.force_authenticate(self.analyst)
        self.assertEqual(self.client.get(reverse('dashboard-trends')).status_code, 200)
        self.assertEqual(self.client.get(reverse('dashboard-activity')).status_code, 200)


class AdminUserManagementTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user('admin@st.test', 'admin')
        cls.other = make_user('dev@st.test', 'developer')
        Report.objects.create(
            title='r', description='x', created_by=cls.other, assigned_to=cls.other,
        )

    def setUp(self):
        self.client.force_authenticate(self.admin)
        self.list_url = reverse('user-list')

    def detail_url(self, user):
        return reverse('user-detail', args=[user.pk])

    def test_list_includes_report_counts(self):
        row = next(u for u in self.client.get(self.list_url).data if u['id'] == self.other.pk)
        self.assertEqual(row['reports_created_count'], 1)
        self.assertEqual(row['reports_assigned_count'], 1)

    def test_search_matches_email_and_name(self):
        self.assertEqual(len(self.client.get(self.list_url, {'search': 'dev@'}).data), 1)
        self.assertEqual(len(self.client.get(self.list_url, {'search': 'Developer'}).data), 1)
        self.assertEqual(len(self.client.get(self.list_url, {'search': 'nobody'}).data), 0)

    def test_filter_by_role_and_active_flag(self):
        self.assertEqual(len(self.client.get(self.list_url, {'role': 'admin'}).data), 1)
        self.assertEqual(len(self.client.get(self.list_url, {'is_active': 'true'}).data), 2)

    def test_admin_can_deactivate_another_user_without_resetting_password(self):
        res = self.client.patch(self.detail_url(self.other), {'is_active': False})
        self.assertEqual(res.status_code, 200)
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_active)
        self.assertTrue(self.other.check_password('pw-testing-123'))

    def test_admin_cannot_demote_deactivate_or_delete_themselves(self):
        self.assertEqual(
            self.client.patch(self.detail_url(self.admin), {'role': 'user'}).status_code, 400,
        )
        self.assertEqual(
            self.client.patch(self.detail_url(self.admin), {'is_active': False}).status_code, 400,
        )
        self.assertEqual(self.client.delete(self.detail_url(self.admin)).status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, 'admin')
        self.assertTrue(self.admin.is_active)

    def test_create_requires_password_but_update_does_not(self):
        res = self.client.post(self.list_url, {
            'email': 'new@st.test', 'first_name': 'New', 'last_name': 'Analyst',
            'role': 'analyst',
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('password', res.data)

    def test_public_register_cannot_self_assign_a_privileged_role(self):
        self.client.force_authenticate(None)
        res = self.client.post(reverse('register'), {
            'email': 'sneaky@st.test', 'first_name': 'S', 'last_name': 'N',
            'password': 'pw-testing-123', 'role': 'admin',
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['role'], 'user')
