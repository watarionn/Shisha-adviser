# Google Auth public site v2.9

Purpose: static, domain-independent public pages prepared for Google OAuth brand verification.

Files:
- `index.html`: public Shisha Advisor homepage
- `privacy.html`: privacy policy
- `terms.html`: optional terms page

## Deployment rule

Deploy all three files under the same owned and Google-verified production domain. Keep the relative links unchanged or preserve equivalent same-domain links.

Example final layout after the owned domain is selected:

```text
https://<owned-domain>/                -> index.html
https://<owned-domain>/privacy.html    -> privacy.html
https://<owned-domain>/terms.html      -> terms.html
```

A subdomain may be used for the application, but the registrable/root domain must be owned and verifiable in Google Search Console and registered in Google Auth Platform Authorized domains.

## Pre-verification checks

- Homepage returns HTTP 200 without authentication.
- Privacy page returns HTTP 200 without authentication.
- Terms page returns HTTP 200 without authentication.
- No page redirects to a different registrable domain.
- Homepage clearly identifies Shisha Advisor and describes its function.
- Homepage links visibly to the privacy policy.
- Privacy URL configured in Google Auth Platform is exactly the published privacy page.
- Content accurately reflects the final Google scopes and production behavior.
- Public Google sign-in does not request Google Drive access.
- No token, client secret, refresh token, HMAC secret, internal hostname, or production credential appears in these files.

## Before final publication

Review the privacy-policy deletion/support wording against the final account/data deletion workflow. If a public support contact is added, use only an address intentionally approved for public disclosure.

Do not attach a temporary Railway public domain merely to host these files. Publish them only after the final owned production domain has been selected.
