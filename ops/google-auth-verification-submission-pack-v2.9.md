# Google Auth verification submission pack v2.9

Date: 2026-09-16
Status: draft content prepared; URLs/domain must be replaced with final verified production values before submission

## App identity

App name: `Shisha Advisor`

Suggested short description:

> Shisha Advisor provides authenticated access to shisha flavor information, recommendation/advice features, and related user-specific application functions. Google Sign-In is used only to authenticate the user and associate requests with the correct account identity.

Do not claim features on the public homepage that are not actually present in the released application.

## Google user-data purpose

Suggested verification explanation:

> Shisha Advisor uses Google OpenID Connect only for user authentication. The application validates Google-issued ID tokens and uses the resulting account identity to authenticate requests. Google identity data is not used for advertising, sold to third parties, or used to access a user's Google Drive, Gmail, Calendar, or other Google Workspace content. Production backups use a separate service-owned Google Cloud Storage HMAC path and do not rely on end-user Google OAuth grants.

Before submission, make this text match the final requested scopes exactly.

## Scope declaration

Target scope set:

```text
openid
email      # only when needed by the final login/account UX
profile    # only when needed by the final user-facing UX
```

Do not include:

```text
https://www.googleapis.com/auth/drive.file
```

or other Workspace scopes unless a separate, real user-facing feature is deliberately introduced and reviewed.

## Homepage content checklist

The public homepage should visibly include:

- `Shisha Advisor` name
- a plain-language description of the service
- core user-facing functionality
- an explanation that Google Sign-In is used for authentication
- a visible Privacy Policy link
- support/contact information or a support path
- no requirement to sign in merely to read this information

Suggested authentication disclosure:

> Google Sign-In is used to confirm your identity and protect account-specific application data. Shisha Advisor does not request access to your Google Drive, Gmail, Calendar, or other Google Workspace content as part of sign-in.

## Privacy policy minimum disclosures

The published privacy page should cover at least:

1. Responsible application/operator identity.
2. What Google identity information is processed.
3. Why it is processed: authentication, access control, and account association.
4. Whether email/profile data is requested by the final client.
5. Token handling: ID/bearer tokens are used for authentication and must not be intentionally written to application logs.
6. Application data storage and retention at a high level.
7. Backup handling: application backups are stored separately in service-owned Google Cloud Storage; this does not grant access to the user's Google Drive.
8. Third-party sharing, if any.
9. User contact/request process for privacy questions and deletion requests.
10. Effective date and update process.

Do not publish generic privacy-template claims that are broader or narrower than the actual implementation.

## Verification demo script

If Google requests an app-functionality demo video, record the real production-candidate flow in this order:

1. Show the public Shisha Advisor homepage on the final verified domain.
2. Show the Privacy Policy link and page.
3. Start Google Sign-In.
4. Show the complete Google authorization/consent screen in English.
5. Show the exact scopes requested.
6. Complete authentication using a reviewer-accessible/test account where appropriate.
7. Show the authenticated Shisha Advisor function that depends on sign-in.
8. Explain that Google identity is used for authentication/account association only.
9. State that production backups are independent GCS HMAC backups, not user Google Drive access.
10. Do not expose tokens, client secrets, HMAC credentials, or private production configuration in the recording.

## Google Auth Platform field checklist

Branding:

- App name: `Shisha Advisor`
- Support email: final monitored operator address
- Homepage: `https://<OWNED_DOMAIN>/...`
- Privacy policy: `https://<OWNED_DOMAIN>/...`
- Terms: `https://<OWNED_DOMAIN>/...` if used
- Developer contact: final monitored operator address

Audience:

- User type: External
- Publishing status: In production when ready for general external users

Data Access:

- retain only minimum OIDC/Google Sign-In scopes needed by the final application
- remove stale Drive scopes from the public sign-in client

Clients:

- use the production OAuth Web client
- Authorized JavaScript origins: only final production HTTPS origins
- Authorized redirect URIs: only final production HTTPS callbacks actually used
- remove OAuth Playground redirect after temporary validation is no longer needed
- remove staging/development URLs from the production client

Authorized domains:

- final root domain must be added
- ownership must be verified in Search Console

Verification Center:

- confirm Branding status
- confirm Data Access status
- submit any requested verification material
- resolve findings before public go-live

## Submission acceptance criteria

The public-auth blocker can be marked complete only when all of these are recorded:

- dedicated production Google Cloud project confirmed;
- External audience configured;
- final owned domain verified;
- homepage publicly accessible and compliant;
- privacy policy publicly accessible and compliant;
- minimal scopes confirmed;
- production OAuth client contains only required origins/redirects;
- Branding verification complete/published as required;
- Data Access has no unresolved verification requirement;
- real production-client OIDC positive/negative acceptance test passes against private production;
- `SHISHA_PUBLIC_GO_LIVE` remains false until the final go-live decision.
