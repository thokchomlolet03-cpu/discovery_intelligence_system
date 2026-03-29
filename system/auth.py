from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse

from system.db.repositories import UserRepository, WorkspaceRepository


SESSION_SECRET_ENV = "DISCOVERY_SESSION_SECRET"
BOOTSTRAP_EMAIL_ENV = "DISCOVERY_BOOTSTRAP_EMAIL"
BOOTSTRAP_PASSWORD_ENV = "DISCOVERY_BOOTSTRAP_PASSWORD"
BOOTSTRAP_WORKSPACE_ENV = "DISCOVERY_BOOTSTRAP_WORKSPACE"
BOOTSTRAP_NAME_ENV = "DISCOVERY_BOOTSTRAP_NAME"
SESSION_COOKIE_NAME_ENV = "DISCOVERY_SESSION_COOKIE_NAME"
SESSION_SECURE_ENV = "DISCOVERY_SESSION_SECURE"
SESSION_MAX_AGE_ENV = "DISCOVERY_SESSION_MAX_AGE_SECONDS"
SESSION_SAME_SITE_ENV = "DISCOVERY_SESSION_SAME_SITE"

SESSION_USER_ID_KEY = "user_id"
SESSION_WORKSPACE_ID_KEY = "workspace_id"
SESSION_CSRF_TOKEN_KEY = "csrf_token"
SESSION_AUTHENTICATED_AT_KEY = "authenticated_at"

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390000
DEFAULT_SESSION_COOKIE_NAME = "discovery_session"
DEFAULT_SESSION_MAX_AGE = 60 * 60 * 8
DEFAULT_SESSION_SAME_SITE = "strict"
VALID_SAME_SITE_VALUES = {"strict", "lax", "none"}
DEFAULT_SESSION_SECRET_PATH = Path(__file__).resolve().parents[1] / "data" / ".session_secret"


def get_session_secret() -> str:
    configured = os.getenv(SESSION_SECRET_ENV, "").strip()
    if configured:
        return configured
    DEFAULT_SESSION_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DEFAULT_SESSION_SECRET_PATH.exists():
        return DEFAULT_SESSION_SECRET_PATH.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    DEFAULT_SESSION_SECRET_PATH.write_text(secret, encoding="utf-8")
    try:
        os.chmod(DEFAULT_SESSION_SECRET_PATH, 0o600)
    except OSError:
        pass
    return secret


def get_session_cookie_name() -> str:
    return os.getenv(SESSION_COOKIE_NAME_ENV, DEFAULT_SESSION_COOKIE_NAME).strip() or DEFAULT_SESSION_COOKIE_NAME


def get_session_max_age() -> int:
    try:
        value = int(os.getenv(SESSION_MAX_AGE_ENV, str(DEFAULT_SESSION_MAX_AGE)).strip())
    except ValueError:
        value = DEFAULT_SESSION_MAX_AGE
    return max(300, value)


def get_session_same_site() -> str:
    value = os.getenv(SESSION_SAME_SITE_ENV, DEFAULT_SESSION_SAME_SITE).strip().lower() or DEFAULT_SESSION_SAME_SITE
    return value if value in VALID_SAME_SITE_VALUES else DEFAULT_SESSION_SAME_SITE


def get_session_https_only() -> bool:
    return os.getenv(SESSION_SECURE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def get_session_middleware_options() -> dict[str, Any]:
    return {
        "secret_key": get_session_secret(),
        "session_cookie": get_session_cookie_name(),
        "same_site": get_session_same_site(),
        "https_only": get_session_https_only(),
        "max_age": get_session_max_age(),
    }


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def hash_password(password: str) -> str:
    text = str(password or "")
    if not text:
        raise ValueError("Password is required.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", text.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_text, salt_text, digest_text = str(password_hash or "").split("$", 3)
    except ValueError:
        return False
    if scheme != PASSWORD_SCHEME:
        return False
    iterations = int(iterations_text)
    salt = _b64decode(salt_text)
    expected = _b64decode(digest_text)
    actual = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


@dataclass(frozen=True)
class AuthContext:
    user: dict[str, Any]
    workspace: dict[str, Any]
    membership: dict[str, Any]
    workspace_options: list[dict[str, Any]]

    @property
    def user_id(self) -> str:
        return str(self.user["user_id"])

    @property
    def workspace_id(self) -> str:
        return str(self.workspace["workspace_id"])


class AuthenticationService:
    def __init__(
        self,
        *,
        user_repository: UserRepository | None = None,
        workspace_repository: WorkspaceRepository | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository()
        self.workspace_repository = workspace_repository or WorkspaceRepository()

    def ensure_bootstrap_identity(self) -> None:
        if self.user_repository.count_users() > 0:
            return
        email = os.getenv(BOOTSTRAP_EMAIL_ENV, "admin@example.com").strip().lower() or "admin@example.com"
        password = os.getenv(BOOTSTRAP_PASSWORD_ENV, "change-me-now").strip() or "change-me-now"
        workspace_name = os.getenv(BOOTSTRAP_WORKSPACE_ENV, "Default Workspace").strip() or "Default Workspace"
        display_name = os.getenv(BOOTSTRAP_NAME_ENV, "Admin").strip() or "Admin"

        user = self.user_repository.create_user(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            is_active=True,
        )
        workspace = self.workspace_repository.create_workspace(
            name=workspace_name,
            owner_user_id=user["user_id"],
            plan_tier="internal",
            plan_status="active",
        )
        self.workspace_repository.add_membership(
            workspace_id=workspace["workspace_id"],
            user_id=user["user_id"],
            role="owner",
        )

    def authenticate(self, *, email: str, password: str) -> AuthContext:
        try:
            user_record = self.user_repository.get_user_credentials_by_email(email)
        except FileNotFoundError as exc:
            raise ValueError("Invalid email or password.") from exc
        if not user_record.get("is_active", True):
            raise ValueError("This user account is inactive.")
        if not verify_password(password, user_record.get("password_hash", "")):
            raise ValueError("Invalid email or password.")
        return self._resolve_context(user_id=user_record["user_id"], workspace_id=None)

    def _resolve_context(self, *, user_id: str, workspace_id: str | None) -> AuthContext:
        user = self.user_repository.get_user(user_id)
        if not user.get("is_active", True):
            raise ValueError("This user account is inactive.")
        workspace_entries = self.workspace_repository.list_user_workspaces(user_id)
        if not workspace_entries:
            raise ValueError("This user does not belong to any workspace.")

        selected = None
        if workspace_id:
            for entry in workspace_entries:
                if entry["workspace"]["workspace_id"] == workspace_id:
                    selected = entry
                    break
            if selected is None:
                raise ValueError("Requested workspace is not available to this user.")
        else:
            selected = workspace_entries[0]

        workspace_options = [
            {
                **entry["workspace"],
                "role": entry["membership"]["role"],
            }
            for entry in workspace_entries
        ]
        return AuthContext(
            user=user,
            workspace=selected["workspace"],
            membership=selected["membership"],
            workspace_options=workspace_options,
        )

    def resolve_context(self, *, user_id: str, workspace_id: str | None) -> AuthContext:
        return self._resolve_context(user_id=user_id, workspace_id=workspace_id)


auth_service = AuthenticationService()


def get_or_create_csrf_token(request: Request) -> str:
    token = str(request.session.get(SESSION_CSRF_TOKEN_KEY) or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    request.session[SESSION_CSRF_TOKEN_KEY] = token
    return token


def require_csrf(request: Request, submitted_token: str | None = None) -> str:
    expected = str(request.session.get(SESSION_CSRF_TOKEN_KEY) or "").strip()
    provided = str(
        submitted_token
        or request.headers.get("x-csrf-token")
        or request.headers.get("x-csrf")
        or ""
    ).strip()
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")
    return expected


def login_user(request: Request, *, user_id: str, workspace_id: str) -> None:
    request.session.clear()
    request.session[SESSION_USER_ID_KEY] = user_id
    request.session[SESSION_WORKSPACE_ID_KEY] = workspace_id
    request.session[SESSION_AUTHENTICATED_AT_KEY] = int(time.time())
    request.session[SESSION_CSRF_TOKEN_KEY] = secrets.token_urlsafe(32)


def logout_user(request: Request) -> None:
    request.session.clear()


def get_optional_auth_context(request: Request) -> AuthContext | None:
    user_id = str(request.session.get(SESSION_USER_ID_KEY) or "").strip()
    if not user_id:
        return None
    try:
        authenticated_at = int(request.session.get(SESSION_AUTHENTICATED_AT_KEY) or 0)
    except (TypeError, ValueError):
        authenticated_at = 0
    if authenticated_at <= 0 or (int(time.time()) - authenticated_at) > get_session_max_age():
        request.session.clear()
        return None
    workspace_id = str(request.session.get(SESSION_WORKSPACE_ID_KEY) or "").strip() or None
    try:
        context = auth_service.resolve_context(user_id=user_id, workspace_id=workspace_id)
    except (FileNotFoundError, ValueError):
        request.session.clear()
        return None
    request.session[SESSION_USER_ID_KEY] = context.user_id
    request.session[SESSION_WORKSPACE_ID_KEY] = context.workspace_id
    request.session[SESSION_AUTHENTICATED_AT_KEY] = int(time.time())
    get_or_create_csrf_token(request)
    return context


def require_auth_context(request: Request) -> AuthContext:
    context = get_optional_auth_context(request)
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return context


def _next_target(request: Request) -> str:
    path = request.url.path or "/"
    if request.url.query:
        return f"{path}?{request.url.query}"
    return path


def login_redirect(request: Request) -> RedirectResponse:
    target = quote(_next_target(request), safe="/?=&")
    return RedirectResponse(url=f"/login?next={target}", status_code=status.HTTP_303_SEE_OTHER)


def require_page_auth_context(request: Request) -> AuthContext | RedirectResponse:
    context = get_optional_auth_context(request)
    if context is not None:
        return context
    return login_redirect(request)


def build_template_auth_context(request: Request) -> dict[str, Any]:
    context = get_optional_auth_context(request)
    csrf_token = get_or_create_csrf_token(request)
    if context is None:
        return {
            "current_user": None,
            "current_workspace": None,
            "current_membership": None,
            "workspace_options": [],
            "csrf_token": csrf_token,
        }
    return {
        "current_user": context.user,
        "current_workspace": context.workspace,
        "current_membership": context.membership,
        "workspace_options": context.workspace_options,
        "csrf_token": csrf_token,
    }
