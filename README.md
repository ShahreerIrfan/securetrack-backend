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
