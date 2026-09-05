from django.urls import reverse
from rest_framework.test import APITestCase

from .models import CustomUser


def make_user(email, role, **extra):
    return CustomUser.objects.create_user(
        email=email, password='pw-testing-123', first_name=role.title(),
        last_name='Account', role=role, **extra,
    )


class MeProfileTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('me@st.test', 'user')
        cls.other = make_user('taken@st.test', 'user')

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_get_returns_own_identity(self):
        res = self.client.get(reverse('me'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['email'], 'me@st.test')
        self.assertEqual(res.data['role'], 'user')

    def test_patch_updates_name_and_email(self):
        res = self.client.patch(reverse('me'), {
            'first_name': 'New', 'last_name': 'Name', 'email': 'new@st.test',
        })
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'New')
        self.assertEqual(self.user.email, 'new@st.test')

    def test_patch_rejects_duplicate_email(self):
        res = self.client.patch(reverse('me'), {'email': 'taken@st.test'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('email', res.data)

    def test_patch_rejects_blank_name(self):
        res = self.client.patch(reverse('me'), {'first_name': '   '})
        self.assertEqual(res.status_code, 400)
        self.assertIn('first_name', res.data)

    def test_patch_cannot_escalate_own_role(self):
        self.client.patch(reverse('me'), {'role': 'admin', 'is_active': False})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, 'user')
        self.assertTrue(self.user.is_active)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('me')).status_code, 401)


class ChangePasswordTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('pw@st.test', 'user')

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_changes_password_with_correct_current_password(self):
        res = self.client.post(reverse('change_password'), {
            'current_password': 'pw-testing-123', 'new_password': 'brand-new-pw-9876',
        })
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brand-new-pw-9876'))

    def test_rejects_wrong_current_password(self):
        res = self.client.post(reverse('change_password'), {
            'current_password': 'not-my-password', 'new_password': 'brand-new-pw-9876',
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('current_password', res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('pw-testing-123'))

    def test_rejects_weak_new_password(self):
        res = self.client.post(reverse('change_password'), {
            'current_password': 'pw-testing-123', 'new_password': 'password',
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('new_password', res.data)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        res = self.client.post(reverse('change_password'), {
            'current_password': 'pw-testing-123', 'new_password': 'brand-new-pw-9876',
        })
        self.assertEqual(res.status_code, 401)
