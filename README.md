# Shisha-adviser

Railway staging source for Shisha Advisor v1.7.

The service exposes `/healthz`, `/readyz`, and `/metrics`. Session APIs use owner-scoped bearer authentication.

For this staging deployment the SQLite database is intentionally ephemeral (`/tmp/shisha/shisha_advisor.db`) because a Railway persistent volume has not yet been attached. Canonical flavor CSV files remain read-only application inputs.

Health check: `/healthz`
