# accounts — manual testing checklist

Run the dev server first: `python manage.py runserver`

- [ ] **Register a user** — `POST /api/auth/register/` with
  `email`, `first_name`, `last_name`, `password`. No auth header
  required. Response is `201` with `role: "user"` even if `role` is
  included in the body.
- [ ] **Log in** — `POST /api/auth/login/` with that user's
  `email`/`password` (this model has no `username` field — email is
  `USERNAME_FIELD`). Response is `200` with `access` and `refresh`
  tokens.
- [ ] **Fetch `/api/auth/me/`** — `GET` with
  `Authorization: Bearer <access>`. Response is `200` with
  `id`/`email`/`first_name`/`last_name`/`role` matching the registered
  user.
- [ ] **Non-admin gets 403 on `/api/auth/users/`** — `GET` with the same
  user's token. Response is `403`.
- [ ] **Create a superuser** — `python manage.py createsuperuser` from
  the terminal (interactive, will prompt for email/first name/last
  name/password) or non-interactively with `DJANGO_SUPERUSER_EMAIL`,
  `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_FIRST_NAME`,
  `DJANGO_SUPERUSER_LAST_NAME`. Defaults to `role="user"`.
- [ ] **Promote to admin via shell**:
  ```python
  python manage.py shell -c "
  from accounts.models import CustomUser
  u = CustomUser.objects.get(email='<superuser-email>')
  u.role = 'admin'
  u.save()
  "
  ```
- [ ] **Admin can access `/api/auth/users/`** — log in as the superuser,
  `GET /api/auth/users/` with their token. Response is `200` with the
  user list.

## Result

All eight steps re-verified live against the email-based CustomUser
model (username removed, first_name/last_name required) on 2026-09-03,
including confirming a login attempt using the old `username` field
name is correctly rejected with a 400.
