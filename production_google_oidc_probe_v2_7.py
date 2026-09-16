from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt

TOKEN_URI = "https://oauth2.googleapis.com/token"


def _emit(status: str, **fields):
    print(
        json.dumps(
            {"event": "google_oidc_live_probe", "status": status, **fields},
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required OIDC probe configuration: {name}")
    return value


def _refresh_id_token() -> tuple[str, dict]:
    client_id = _required("GOOGLE_DRIVE_CLIENT_ID")
    client_secret = _required("GOOGLE_DRIVE_CLIENT_SECRET")
    refresh_token = _required("GOOGLE_DRIVE_REFRESH_TOKEN")

    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": "openid",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URI,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Google token refresh failed with HTTP {exc.code}") from exc

    id_token = response.get("id_token")
    if not id_token:
        scopes = set(str(response.get("scope", "")).split())
        raise RuntimeError(
            "Google refresh response did not include id_token; re-authorize the refresh token with openid scope"
            + ("" if "openid" in scopes else " (openid scope not present in refreshed grant)")
        )
    return id_token, response


def _validate_id_token(id_token: str) -> dict:
    issuer = _required("SHISHA_OIDC_ISSUER")
    audience = _required("SHISHA_OIDC_AUDIENCE")
    jwks_url = _required("SHISHA_OIDC_JWKS_URL")

    jwks = jwt.PyJWKClient(jwks_url)
    signing_key = jwks.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )

    wrong_audience_rejected = False
    try:
        jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience + ".wrong-audience-probe",
            issuer=issuer,
        )
    except jwt.InvalidAudienceError:
        wrong_audience_rejected = True
    if not wrong_audience_rejected:
        raise RuntimeError("Wrong-audience negative validation unexpectedly succeeded")

    return claims


def _http_status(path: str, token: str | None = None) -> int:
    port = os.environ.get("PORT", "8789")
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", headers=headers, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code


def _wait_healthy(timeout_seconds: int = 45) -> None:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        try:
            last_status = _http_status("/healthz")
            if last_status == 200:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Local service did not become healthy; last_status={last_status}")


def main():
    if os.environ.get("SHISHA_AUTH_MODE", "").strip().lower() != "oidc":
        raise RuntimeError("OIDC probe requires SHISHA_AUTH_MODE=oidc")
    if os.environ.get("SHISHA_METRICS_MODE", "").strip().lower() != "authenticated":
        raise RuntimeError("OIDC probe requires SHISHA_METRICS_MODE=authenticated")

    id_token, refresh_response = _refresh_id_token()
    claims = _validate_id_token(id_token)
    _wait_healthy()

    missing_status = _http_status("/metrics")
    invalid_status = _http_status("/metrics", "not.a.valid.jwt")
    valid_status = _http_status("/metrics", id_token)

    if missing_status not in {401, 403}:
        raise RuntimeError(f"Missing-token request was not rejected: HTTP {missing_status}")
    if invalid_status not in {401, 403}:
        raise RuntimeError(f"Invalid-token request was not rejected: HTTP {invalid_status}")
    if valid_status != 200:
        raise RuntimeError(f"Valid Google ID token was not accepted: HTTP {valid_status}")

    sub_digest = hashlib.sha256(str(claims["sub"]).encode("utf-8")).hexdigest()[:16]
    granted_scopes = set(str(refresh_response.get("scope", "")).split())
    _emit(
        "PASS",
        issuer=claims["iss"],
        audience_match=claims["aud"] == _required("SHISHA_OIDC_AUDIENCE"),
        subject_sha256_prefix=sub_digest,
        refresh_openid_scope="openid" in granted_scopes,
        valid_token_http_status=valid_status,
        missing_token_http_status=missing_status,
        invalid_token_http_status=invalid_status,
        wrong_audience_rejected=True,
        raw_token_logged=False,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _emit(
            "FAIL",
            error_type=type(exc).__name__,
            message=str(exc)[:300],
            raw_token_logged=False,
        )
        raise
