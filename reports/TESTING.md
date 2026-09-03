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
  `GET /api/reports/{id}/activity/`. Expect exactly 4 entries, in
  order: verify, assign, resolve, close — each with the correct actor
  and an old-status → new-status detail message. (Creation itself is
  not a status transition, so it does not appear as an activity log
  entry — only the four `PATCH .../status/` calls do.)

## Result

Ran the full sequence live against a `runserver` instance on
2026-09-03. All 6 steps passed; the activity log contained exactly the
4 expected entries in the correct order with the correct actors. No
issues found — nothing needed fixing.
