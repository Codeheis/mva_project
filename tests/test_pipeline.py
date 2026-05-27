"""
End-to-end integration smoke test for the YouTube-clone backend pipeline.

Runs against the local Nginx gateway on localhost:80 and performs:
1) Register (best-effort) + Login to obtain JWT access token
2) Locate ./sample.mp4 (next to where you run this script)
3) Upload the video via the upload service (multipart form)

Usage:
  python tests/test_pipeline.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


GATEWAY_BASE_URL = os.environ.get("GATEWAY_BASE_URL", "http://localhost")

AUTH_REGISTER_URL = f"{GATEWAY_BASE_URL}/api/auth/register"
AUTH_LOGIN_URL = f"{GATEWAY_BASE_URL}/api/auth/login"

UPLOAD_URL = f"{GATEWAY_BASE_URL}/api/upload/upload"


def _print_stage(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _safe_json(response: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"_non_dict_json": data}
    except ValueError:
        return None


def _print_response(label: str, response: requests.Response) -> None:
    print(f"{label} status={response.status_code}")
    data = _safe_json(response)
    if data is not None:
        print(f"{label} json:\n{json.dumps(data, indent=2, sort_keys=True)}")
    else:
        text = (response.text or "").strip()
        print(f"{label} text:\n{text[:2000]}")


def _register_then_login(username: str, password: str, email: str) -> str:
    _print_stage("1) Auto-Register/Login")
    print(f"Gateway base URL: {GATEWAY_BASE_URL}")

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    # 1a) Register (best-effort)
    print(f"Registering user at: {AUTH_REGISTER_URL}")
    try:
        reg_resp = session.post(
            AUTH_REGISTER_URL,
            json={"username": username, "email": email, "password": password},
            timeout=10,
        )
        _print_response("REGISTER", reg_resp)
        if reg_resp.status_code >= 500:
            reg_resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"WARNING: Register request failed: {exc}")
        print("Continuing to login anyway (user may already exist).")

    # 1b) Login (OAuth2PasswordRequestForm expects form-encoded fields)
    print(f"Logging in at: {AUTH_LOGIN_URL}")
    login_resp = session.post(
        AUTH_LOGIN_URL,
        data={"username": username, "password": password},
        timeout=10,
    )
    _print_response("LOGIN", login_resp)
    login_resp.raise_for_status()

    payload = _safe_json(login_resp) or {}
    token = (
        payload.get("access_token")
        or payload.get("token")
        or payload.get("jwt")
        or payload.get("accessToken")
    )
    if not token or not isinstance(token, str):
        raise RuntimeError(
            "Login succeeded but no access token found in response JSON. "
            f"Keys present: {sorted(payload.keys())}"
        )

    print("Successfully obtained access token.")
    return token


def _locate_sample_video() -> Path:
    _print_stage("2) Prepare a Small Test Video")
    path = Path("sample.mp4")
    print(f"Looking for sample video at: {path.resolve()}")
    if not path.exists():
        print(
            "WARNING: 'sample.mp4' not found in the current directory.\n"
            "Please place a small test .mp4 named 'sample.mp4' next to where you run this script,\n"
            "then re-run: python tests/test_pipeline.py"
        )
        raise SystemExit(1)
    if not path.is_file():
        print("WARNING: 'sample.mp4' exists but is not a file.")
        raise SystemExit(1)
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Found sample.mp4 ({size_mb:.2f} MiB).")
    return path


def _upload_video(token: str, sample_path: Path) -> Dict[str, Any]:
    _print_stage("3) Execute the Upload")
    print(f"Uploading to: {UPLOAD_URL}")

    headers = {"Authorization": f"Bearer {token}"}
    form = {
        "title": "Test Architecture Video",
        "description": "Testing the automated pipeline",
    }

    # The upload service expects the file field name "video".
    with sample_path.open("rb") as f:
        files = {"video": (sample_path.name, f, "video/mp4")}
        resp = requests.post(
            UPLOAD_URL,
            headers=headers,
            data=form,
            files=files,
            timeout=120,
        )

    _print_response("UPLOAD", resp)
    resp.raise_for_status()

    payload = _safe_json(resp)
    if payload is None:
        raise RuntimeError("Upload succeeded but response was not JSON.")

    return payload


def main() -> int:
    # Keep user dummy but stable across runs to simplify local testing.
    username = os.environ.get("E2E_USERNAME", "cursor_e2e_user")
    password = os.environ.get("E2E_PASSWORD", "cursor_e2e_password")
    email = os.environ.get("E2E_EMAIL", "cursor_e2e_user@example.com")

    started = time.time()
    try:
        token = _register_then_login(username=username, password=password, email=email)
        sample_path = _locate_sample_video()
        upload_payload = _upload_video(token=token, sample_path=sample_path)
    except Exception as exc:
        _print_stage("FAILED")
        print(f"Error: {exc}")
        return 1

    _print_stage("SUCCESS")
    print("Upload service response payload:")
    print(json.dumps(upload_payload, indent=2, sort_keys=True))
    print(f"Total elapsed: {time.time() - started:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
