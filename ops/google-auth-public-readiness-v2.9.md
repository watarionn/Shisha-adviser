# Google Auth public-user readiness v2.9

Date: 2026-09-16
Status: prepared / external Google Auth Platform actions still required
Scope: public-user Google authentication only

## Goal

Close the final public go-live blocker for Shisha Advisor without weakening the already-validated private production controls.

Current production authentication is Google OpenID Connect and has already passed private live validation. Production backup is independently handled by Google Cloud Storage via `gcs-hmac`; Google Drive OAuth is not part of the canonical production backup path.

## Current production facts

- Railway service: `advisor-production`
- Railway public/custom domains: 0
- `SHISHA_AUTH_MODE=oidc`
- `SHISHA_PUBLIC_GO_LIVE=false`
- Google OIDC signature/JWKS/issuer/audience validation: PASS
- Missing/invalid/wrong-audience token rejection: PASS
- Current Google Auth Platform publishing state: `Testing`
- Production alert delivery: PASS
- GCS backup and retention verification: PASS
- Railway isolation requirement: satisfied by explicit documented waiver

## Google production-readiness requirements

The following requirements are mandatory before general external Google sign-in is accepted for public production.

### 1. Dedicated production Google Cloud project

Google's OAuth production-readiness guidance requires development/testing and production to use separate Cloud projects. The production OAuth client must belong to the production-tier project used for the public application.

Do not reuse a staging/test-only Google Cloud project as the long-term public production identity boundary.

### 2. External audience and In production status

The Google Auth Platform Audience configuration must be `External` and the publishing status must be moved from `Testing` to `In production` before general external users are accepted.

Keep production private until the remaining items in this document are complete.

### 3. Minimal authentication scopes only

The public authentication path must request only the minimum Google Sign-In/OIDC scopes needed by the application.

Allowed baseline:

```text
openid
email        # only if the final user-facing flow actually needs email
profile      # only if the final UI actually needs profile data
```

The production authentication flow must not request `drive.file` or another Google Workspace scope merely because an older backup implementation used Google Drive. Canonical backup is GCS HMAC and is independent of end-user Google authorization.

Before verification submission, confirm the Google Auth Platform Data Access page contains no unused sensitive or restricted scopes.

### 4. Verified owned domain

A production OAuth app must use an owned domain that can be verified through Google Search Console.

Before verification:

- verify the root domain as a Search Console Domain property using a Google account that is also an Owner/Editor of the Google Cloud project, preferably a Project Owner;
- add the verified root domain to Google Auth Platform Authorized domains;
- use HTTPS for all production application origins and redirect URIs;
- do not rely on a shared third-party hostname that cannot be verified as owned by the application operator.

### 5. Public application homepage

The homepage used for Google verification must:

- be publicly accessible without login;
- be hosted on the verified owned domain;
- clearly identify `Shisha Advisor`;
- describe what the application does;
- explain why Google authentication is used;
- link visibly to the privacy policy;
- not be only a login page;
- not redirect to a different domain.

### 6. Public privacy policy

The privacy policy must:

- be a dedicated HTML page on the owned/verified domain;
- be linked from the homepage and from the Google Auth Platform Branding configuration;
- identify Shisha Advisor or its responsible developer/operator;
- describe how Google identity data is accessed, used, stored, and shared;
- describe retention/deletion behavior for account-linked data;
- accurately reflect the final OIDC scopes and implementation;
- remain consistent with the actual application behavior.

Terms of Service may also be published and linked. If the Google Auth Platform UI requests a Terms URL for the final production configuration, use a page on the same verified domain.

### 7. Branding configuration

Configure Google Auth Platform Branding with production values:

- App name: `Shisha Advisor`
- User support email: monitored address controlled by the operator
- Developer contact email: monitored address controlled by the operator
- Homepage URL: final HTTPS homepage on the verified domain
- Privacy policy URL: final HTTPS privacy page on the verified domain
- Terms of Service URL: final HTTPS terms page when used
- App logo: optional until a final production asset is selected; if supplied, it must accurately represent the app

Avoid changing branding while Google verification is in progress.

### 8. OAuth client cleanup

For the public production OAuth client:

- keep only required HTTPS Authorized JavaScript origins;
- keep only required HTTPS Authorized redirect URIs;
- remove temporary OAuth Playground redirect URIs when no longer needed;
- remove unrelated development/staging origins from the production client;
- never expose the OAuth client secret in GitHub, logs, chat, or public assets.

### 9. Brand verification

Once domain, homepage, privacy policy, audience, client URLs, and scopes are final:

1. open Google Auth Platform -> Verification Center;
2. run/submit Brand verification when offered;
3. provide the requested app-functionality demonstration material;
4. ensure any demo shows the real end-to-end Google authentication flow, the consent screen, the final branding, and the scopes actually requested;
5. resolve any verification findings before public routing is enabled;
6. after approval, publish approved branding within Google's permitted publication window.

If Data Access shows only basic Google Sign-In/OIDC scopes, do not add sensitive/restricted scopes solely to make the configuration look more complete.

### 10. Post-publication authentication acceptance test

After the Google Auth Platform production configuration is approved/published, but before attaching the final public Railway domain:

1. obtain a real Google-issued ID token using the production OAuth client;
2. verify signature using Google's JWKS;
3. verify issuer;
4. verify audience matches the production OAuth client ID;
5. verify expiry and required claims;
6. confirm valid-token request succeeds against private production;
7. confirm missing token fails closed;
8. confirm malformed token fails closed;
9. confirm wrong-audience token fails closed;
10. confirm no raw token or OAuth secret is logged.

Only after that acceptance test passes may the public-routing gate be reconsidered.

## Execution order

Use this order to avoid unnecessary exposure:

1. Confirm/create the dedicated Google Cloud production project.
2. Select the final owned production domain.
3. Verify root-domain ownership in Search Console.
4. Prepare and host public homepage + privacy policy (+ terms if used).
5. Configure Authorized domains, Branding, Audience, Data Access, and production OAuth client URLs.
6. Verify that only minimal OIDC scopes are requested.
7. Move Audience from `Testing` to `In production` at the appropriate verification step.
8. Complete Google verification and publish the approved branding.
9. Repeat the real OIDC positive/negative validation on private production.
10. Re-evaluate `SHISHA_PUBLIC_GO_LIVE` and public Railway domain attachment only after all checks pass.

## Current blocking inputs

The repository and Railway runtime are prepared, but the following Google/external infrastructure items are not yet recorded as complete:

- dedicated production Google Cloud project confirmation;
- final owned production domain;
- Search Console ownership verification;
- public homepage URL;
- public privacy policy URL;
- production Branding/Audience/Verification Center completion.

Because production currently has zero public domains, none of these missing items should be bypassed by attaching a temporary public Railway domain.

## Safety constraints

- Keep `SHISHA_PUBLIC_GO_LIVE=false` until the entire public-user auth gate is complete.
- Keep Railway production domains at 0 during verification preparation.
- Do not alter the validated GCS HMAC backup path as part of Google sign-in publishing.
- Do not restore Google Drive OAuth as a production-backup dependency.
- Do not commit or echo OAuth client secrets, refresh tokens, ID tokens, bearer tokens, HMAC secrets, or equivalent credentials.
- Do not broaden requested Google scopes without a concrete user-facing requirement.
