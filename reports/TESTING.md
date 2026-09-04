# reports — manual testing checklist

Run the dev server first: `python manage.py runserver`. Needs one user
of each role: `user`, `analyst`, `developer`, `admin` (see
`accounts/TESTING.md` for how to create/promote them).

Full lifecycle, one report:

- [ ] **Create as a user** — `POST /api/reports/` with the user's token.
  Response `201`, `status: "new"`, `created_by` is the requester
  regardless of anything else in the body.
- [ ] **Verify as an analyst** — `PATCH /api/reports/{id}/status/` with
  `{"status": "verified"}` using the analyst's token. Response `200`.
- [ ] **Assign to a developer as an admin** —
  `PATCH /api/reports/{id}/status/` with
  `{"status": "assigned", "assigned_to": <developer id>}` using the
  admin's token. Response `200`, `assigned_to` now shows the developer.
- [ ] **Resolve as that developer** — same endpoint,
  `{"status": "resolved"}`, using the assigned developer's token.
  Response `200`. A different developer, or a developer with no
  assignment, gets `404` (the report isn't in their scoped queryset at
  all — see reports/views.py `get_queryset`).
- [ ] **Close as an admin** — `{"status": "closed"}` with the admin's
  token. Response `200`.
- [ ] **Confirm the activity log recorded every step** —
  `GET /api/reports/{id}/activity/`. Expect exactly 5 entries, in
  order: created, verify, assign, resolve, close — each with the
  correct actor. The four status-change entries carry an old-status →
  new-status detail message; the creation entry does not.

## Editing (PUT/PATCH /api/reports/{id}/)

Only `title`/`description`/`severity`/`priority`/`category`/`due_date`
are writable here — `status` and `assigned_to` are structurally absent
from this serializer, so including them in the request body is
silently ignored rather than applied.

- [ ] **Creator can edit while status is "new"** — `PATCH` with a new
  `title` using the creator's token, on a fresh report. `200`, title
  updated, and an `edited` entry appears in the activity log.
- [ ] **Creator is blocked once status moves on** — verify the report
  as an analyst first, then retry the same `PATCH` as the creator.
  `403`.
- [ ] **A role that can't see the report at all gets `404`, not
  `403`** — e.g. a `user` who didn't create it, or a `developer` it
  isn't assigned to. This mirrors the existing `set_status` visibility
  behavior above.
- [ ] **Admin can edit regardless of status** — `PATCH` as admin on a
  `closed` report. `200`.
- [ ] **Status/assigned_to in the body have no effect** — `PATCH` with
  `{"title": "x", "status": "closed", "assigned_to": <id>}` as the
  creator. `200`, title changes, status and assigned_to do not.

## Comments (PATCH/DELETE /api/reports/{id}/comments/{comment_id}/)

- [ ] **Author can edit their own comment** — `200`, `updated_at`
  changes, a `comment_edited` activity entry appears.
- [ ] **Author can delete their own comment** — `204`.
- [ ] **A non-author, non-admin gets `403`** on both edit and delete
  (assuming they can see the report at all — otherwise it's `404`,
  same visibility rule as above).
- [ ] **Admin can edit or delete any comment** — `200`/`204`.

## Result

Ran the full lifecycle sequence live against a `runserver` instance on
2026-09-03. All 6 steps passed; the activity log contained exactly the
4 expected status-change entries in the correct order with the correct
actors. No issues found.

Automated coverage for all of the above (visibility, create, the
edit-authorization fix, delete, the full status lifecycle, and
comments) now lives in `reports/tests.py` — 25 tests, all passing.
