import os

TRUE = {"1", "true", "yes", "on"}
public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
public_flag = os.environ.get("SHISHA_PUBLIC_GO_LIVE", "").strip().lower() in TRUE
auth_mode = os.environ.get("SHISHA_AUTH_MODE", "local-bearer").strip().lower()

if (public_domain or public_flag) and auth_mode != "oidc":
    raise SystemExit("Public production requires OIDC authentication")

if auth_mode == "oidc":
    required = [
        "SHISHA_OIDC_PROVIDER_ID",
        "SHISHA_OIDC_ISSUER",
        "SHISHA_OIDC_AUDIENCE",
        "SHISHA_OIDC_JWKS_URL",
    ]
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise SystemExit("Missing OIDC configuration: " + ",".join(missing))
