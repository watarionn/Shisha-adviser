# Production public guest policy v3.0

Date: 2026-09-16
Status: public-beta go-live policy

## Purpose

Shisha Advisor may be publicly usable before an operator-owned domain is available by using a server-issued anonymous guest identity. Google OIDC remains configured and validated, but general external Google sign-in remains deferred until the owned-domain / Google Auth Platform work is complete.

## Authentication boundary

- Production keeps `SHISHA_AUTH_MODE=oidc`.
- Public beta enables `SHISHA_PUBLIC_GUEST_ENABLED=true`.
- `/v1/guest` issues a cryptographically random opaque bearer token and a dedicated principal.
- Guest bearer tokens are accepted only by the hybrid public web layer; non-guest JWTs continue through the existing Google OIDC verifier.
- Session ownership remains principal-scoped; cross-principal session access returns 404.
- Raw bearer tokens are never written to structured request logs.

## Abuse controls

- Guest registrations per apparent client address: 8 per hour.
- Guest registrations globally: 240 per hour.
- Active principal safety cap: 5000.
- Existing per-principal request rate limiting remains enabled.
- The guest registration endpoint returns 429 or 503 instead of creating additional principals when a limit is reached.

## Public web surface

- The production service serves the browser UI and API from the same Railway origin.
- No CORS widening is required.
- The UI stores only the anonymous guest bearer token in browser local storage.
- Security headers include CSP, frame denial, MIME sniffing prevention, no-referrer, and no-store caching.
- The public UI includes an adult-use / legal-compliance notice and does not claim health safety.

## Google OIDC transition

Guest access is a bridge, not a replacement for the validated OIDC path. After an operator-owned domain is available, complete Search Console ownership and Google Auth Platform production configuration, add the Google sign-in UI, then decide whether guest access remains available.

## Rollback

For an immediate public-access rollback:
1. set `SHISHA_PUBLIC_GUEST_ENABLED=false`;
2. set `SHISHA_PUBLIC_GO_LIVE=false`;
3. remove the Railway public domain if external reachability must stop;
4. retain the production volume and canonical GCS backups.

Canonical backup remains GCS HMAC with 14-generation retention. Secrets, OAuth credentials, ID tokens, guest bearer tokens, and HMAC secrets must never be committed or logged.
