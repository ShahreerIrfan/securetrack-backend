# SecureTrack — Backend

Django REST Framework API for SecureTrack, a vulnerability/incident report
tracking system with JWT authentication and 4 user roles: User, Analyst,
Developer, Admin.

Paired frontend: https://github.com/ShahreerIrfan/securetrack-frontend

## Stack

- Django + Django REST Framework
- djangorestframework-simplejwt (JWT auth)
- django-cors-headers
- django-filter
- SQLite (local dev)

## Local setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API runs at `http://localhost:8000/`. CORS is configured to allow requests
from `http://localhost:3000` (the frontend dev server).

The superuser created above starts with `role="user"` (Django's
`createsuperuser` has no notion of this app's roles). Promote it to admin
so it can reach the admin-only endpoints and the frontend's User
Management page:

```bash
python manage.py shell -c "
from accounts.models import CustomUser
u = CustomUser.objects.get(username='<your-superuser-username>')
u.role = 'admin'
u.save()
"
```

## Environment variables

None are required for local development - every setting below falls back
to a value that works against local SQLite with `DEBUG=True`. See
`.env.example` for the full list with descriptions.

| Variable | Local default | Set in production to |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | a real secret (`get_random_secret_key()`) |
| `DJANGO_DEBUG` | `True` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | your API's domain(s) |
| `DATABASE_URL` | unset (uses SQLite) | your Postgres connection string |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | your deployed frontend's origin(s) |
| `CSRF_TRUSTED_ORIGINS` | unset | same as above, only needed for Django admin |

## Deployment (Docker / Dokploy)

The repo ships a production `Dockerfile` + `entrypoint.sh`: on container
start it runs migrations, collects static files, then serves via
gunicorn. In Dokploy:

1. Create the app as a **Dockerfile**-type deployment pointing at this repo.
2. Add a Postgres database (Dokploy can provision one) and copy its
   connection string into `DATABASE_URL`.
3. Set the other environment variables from the table above -
   `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` must match the real
   domains you deploy to, or the frontend won't be able to reach the API
   and Django will reject the Host header.
4. `GET /healthz/` returns `{"status": "ok"}` - point Dokploy's health
   check at it.

No build-time secrets are needed - migrations and `collectstatic` both
run at container start, once real env vars are available.

## API surface

- `/api/auth/` — register, login, refresh, me, admin-only user management
- `/api/reports/` — CRUD, status transitions, comments, activity log
- `/api/dashboard/` — role-aware stats and recent-reports endpoints

See `accounts/TESTING.md` and `reports/TESTING.md` for manually-verified
checklists covering auth and the full report lifecycle.
