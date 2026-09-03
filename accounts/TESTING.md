# accounts — manual testing checklist

Run the dev server first: `python manage.py runserver`

- [ ] **Register a user** — `POST /api/auth/register/` with
  `username`, `email`, `password`. No auth header required. Response is
  `201` with `role: "user"` even if `role` is included in the body.
- [ ] **Log in** — `POST /api/auth/login/` with that user's
  `username`/`password`. Response is `200` with `access` and `refresh`
  tokens.
- [ ] **Fetch `/api/auth/me/`** — `GET` with
  `Authorization: Bearer <access>`. Response is `200` with
  `id`/`username`/`email`/`role` matching the registered user.
- [ ] **Non-admin gets 403 on `/api/auth/users/`** — `GET` with the same
  user's token. Response is `403`.
- [ ] **Create a superuser** — `python manage.py createsuperuser` from the
  terminal (interactive) or non-interactively with `DJANGO_SUPERUSER_*`
  env vars. Defaults to `role="user"`.
- [ ] **Promote to admin via shell**:
  ```python
  python manage.py shell -c "
  from accounts.models import CustomUser
  u = CustomUser.objects.get(username='<superuser-username>')
  u.role = 'admin'
  u.save()
  "
  ```
- [ ] **Admin can access `/api/auth/users/`** — log in as the superuser,
  `GET /api/auth/users/` with their token. Response is `200` with the
  user list.

## Result

All eight steps passed against a live `runserver` instance on
2026-09-03. See the commit for the exact curl commands and responses.
