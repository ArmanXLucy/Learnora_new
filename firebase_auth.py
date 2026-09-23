"""
Firebase Admin SDK helpers for Learnora.

Supports:
- Local development: FIREBASE_SERVICE_ACCOUNT_PATH=serviceAccountKey.json
- Vercel/production: FIREBASE_SERVICE_ACCOUNT_JSON=<complete JSON>

The Admin SDK is initialized once per Python process. The service-account
project is checked against FIREBASE_PROJECT_ID so a key from the wrong
Firebase project fails with a clear configuration error.
"""
import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials


BASE_DIR = Path(__file__).resolve().parent


def get_firebase_app():
    """Return the initialized Firebase Admin app."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    service_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    service_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    expected_project = os.environ.get("FIREBASE_PROJECT_ID", "").strip()

    if service_json:
        try:
            service_info = json.loads(service_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from exc
        if not isinstance(service_info, dict):
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON must contain a JSON object.")

        service_project = str(service_info.get("project_id", "")).strip()
        if expected_project and service_project and service_project != expected_project:
            raise RuntimeError(
                "Firebase project mismatch: FIREBASE_PROJECT_ID is "
                f"'{expected_project}', but the service-account JSON belongs to "
                f"'{service_project}'. Generate the service-account key from "
                "the same Firebase project."
            )

        private_key = service_info.get("private_key")
        if isinstance(private_key, str):
            service_info["private_key"] = private_key.replace("\\n", "\n")

        cred = credentials.Certificate(service_info)
        project_id = expected_project or service_project
    else:
        if not service_path:
            raise RuntimeError(
                "Firebase Admin is not configured. For Vercel set "
                "FIREBASE_SERVICE_ACCOUNT_JSON. For local development set "
                "FIREBASE_SERVICE_ACCOUNT_PATH=serviceAccountKey.json."
            )

        path = Path(service_path)
        if not path.is_absolute():
            path = BASE_DIR / path

        if not path.exists():
            raise RuntimeError(
                f"Firebase service-account file was not found: {path}"
            )

        try:
            service_info = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Firebase service-account file is not valid JSON: {path}"
            ) from exc

        service_project = str(service_info.get("project_id", "")).strip()
        if expected_project and service_project and service_project != expected_project:
            raise RuntimeError(
                "Firebase project mismatch: FIREBASE_PROJECT_ID is "
                f"'{expected_project}', but the local service-account file belongs "
                f"to '{service_project}'."
            )

        cred = credentials.Certificate(service_info)
        project_id = expected_project or service_project

    options = {}
    if project_id:
        options["projectId"] = project_id

    return firebase_admin.initialize_app(cred, options)


def verify_id_token(id_token):
    """Verify a Firebase ID token and return its decoded claims."""
    if not id_token or not isinstance(id_token, str):
        raise ValueError("Missing Firebase ID token.")

    app = get_firebase_app()
    return auth.verify_id_token(id_token, app=app, check_revoked=False)
