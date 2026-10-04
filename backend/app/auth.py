"""Database-backed, revocable operator sessions. No development bypass or default account."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math
import re
import secrets
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import OperatorAccount, OperatorSession
from backend.app.settings import Settings
from contracts.models import OperatorView, SessionView

COOKIE_NAME = "sigap_session"
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def error(status: int, code: str, message: str, **headers):
    return HTTPException(status_code=status, detail={"code": code, "message": message}, headers=headers)


def unavailable():
    return error(503, "AUTH_UNAVAILABLE", "Layanan akun belum tersedia. Coba lagi setelah layanan pulih.")


def normalize_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", value):
        raise ValueError("Nama pengguna harus 3–80 karakter: huruf, angka, titik, garis bawah, atau tanda hubung.")
    return value


def validate_password(value: str, *, allow_short: bool = False) -> str:
    if not (1 if allow_short else 15) <= len(value) <= 128 or not value.strip():
        raise ValueError("Gunakan kata sandi atau frasa sandi sepanjang 15–128 karakter.")
    return value


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def csrf_token(raw: str) -> str:
    return hmac.new(raw.encode("utf-8"), b"sigap-session-csrf-v1", hashlib.sha256).hexdigest()


def utc(value: datetime) -> datetime:
    # SQLite in unit tests omits timezone information; PostgreSQL stores timestamptz.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    username: str = Field(min_length=3, max_length=80)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def username_format(cls, value):
        return normalize_username(value)


@dataclass(frozen=True)
class Principal:
    operator: OperatorView
    token_hash: str
    expires_at: datetime


class LoginLimiter:
    """Bounded, process-local attempt windows; paired with a hashing concurrency cap."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.entries = {}
        self.lock = threading.Lock()

    def consume(self, address: str, username: str):
        now = self.clock()
        with self.lock:
            for key in list(self.entries):
                queue = self.entries[key]
                while queue and queue[0] <= now - 60:
                    queue.popleft()
                if not queue:
                    del self.entries[key]
            limits = [("all", 40), (f"ip:{address}", 10), (f"name:{token_hash(username)}", 5)]
            if len(self.entries) > 2045 or any(len(self.entries.get(key, ())) >= limit for key, limit in limits):
                raise error(429, "LOGIN_RATE_LIMITED", "Terlalu banyak percobaan. Tunggu satu menit lalu coba lagi.", **{"Retry-After": "60"})
            for key, _ in limits:
                self.entries.setdefault(key, deque()).append(now)


class AuthService:
    def __init__(self, engine: Engine | None, settings: Settings, *, now=None):
        self.engine, self.settings = engine, settings
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.limiter = LoginLimiter()
        self.hash_slots = threading.BoundedSemaphore(2)

    def database(self):
        if self.engine is None:
            raise unavailable()
        return Session(self.engine)

    def current(self, raw: str | None) -> Principal:
        if not raw or not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw):
            raise error(401, "SESSION_REQUIRED", "Sesi tidak valid atau sudah berakhir. Silakan masuk kembali.")
        try:
            with self.database() as db:
                result = db.execute(select(OperatorSession, OperatorAccount).join(
                    OperatorAccount, OperatorAccount.id == OperatorSession.operator_id).where(
                    OperatorSession.token_hash == token_hash(raw), OperatorSession.expires_at > self.now(),
                    OperatorAccount.is_active.is_(True))).first()
                if result is None:
                    raise error(401, "SESSION_REQUIRED", "Sesi tidak valid atau sudah berakhir. Silakan masuk kembali.")
                session, account = result
                operator = OperatorView(id=account.id, username=account.username, display_name=account.display_name)
                return Principal(operator, session.token_hash, utc(session.expires_at))
        except SQLAlchemyError:
            raise unavailable() from None

    def view(self, principal: Principal, raw: str) -> SessionView:
        remaining = math.ceil((principal.expires_at - self.now()).total_seconds())
        if remaining <= 0:
            raise error(401, "SESSION_REQUIRED", "Sesi sudah berakhir. Silakan masuk kembali.")
        return SessionView(operator=principal.operator, expires_at=principal.expires_at,
                           remaining_seconds=remaining, csrf_token=csrf_token(raw))

    def login(self, payload: LoginInput, address: str, old_cookie: str | None):
        self.limiter.consume(address, payload.username)
        if not self.hash_slots.acquire(blocking=False):
            raise error(429, "LOGIN_BUSY", "Layanan sedang memeriksa akun lain. Coba lagi sebentar.", **{"Retry-After": "2"})
        try:
            with self.database() as db, db.begin():
                account = db.scalar(select(OperatorAccount).where(func.lower(OperatorAccount.username) == payload.username).with_for_update())
                encoded = account.password_hash if account else DUMMY_HASH
                try:
                    matches = PASSWORD_HASHER.verify(encoded, payload.password.get_secret_value())
                except (VerificationError, InvalidHashError):
                    matches = False
                if not matches or account is None or not account.is_active:
                    raise error(401, "INVALID_CREDENTIALS", "Nama pengguna atau kata sandi salah.")
                if PASSWORD_HASHER.check_needs_rehash(account.password_hash):
                    account.password_hash = PASSWORD_HASHER.hash(payload.password.get_secret_value())
                now = self.now()
                expires = now + timedelta(seconds=self.settings.sigap_session_seconds)
                raw = secrets.token_urlsafe(32)
                db.execute(delete(OperatorSession).where(OperatorSession.expires_at <= now))
                if old_cookie and len(old_cookie) <= 256:
                    db.execute(delete(OperatorSession).where(OperatorSession.token_hash == token_hash(old_cookie)))
                db.add(OperatorSession(token_hash=token_hash(raw), operator_id=account.id, created_at=now, expires_at=expires))
                principal = Principal(OperatorView(id=account.id, username=account.username,
                    display_name=account.display_name), token_hash(raw), expires)
            return raw, self.view(principal, raw)
        except SQLAlchemyError:
            raise unavailable() from None
        finally:
            self.hash_slots.release()

    def logout(self, principal: Principal):
        try:
            with self.database() as db, db.begin():
                db.execute(delete(OperatorSession).where(OperatorSession.token_hash == principal.token_hash))
        except SQLAlchemyError:
            raise unavailable() from None


def require_operator(request: Request) -> Principal:
    principal = request.app.state.auth.current(request.cookies.get(COOKIE_NAME))
    if "monitor:read" not in principal.operator.permissions:
        raise error(403, "ACCESS_DENIED", "Akun tidak memiliki akses pemantauan.")
    return principal


def require_origin(request: Request):
    if request.headers.get("origin") not in request.app.state.auth.settings.sigap_allowed_origins or request.headers.get("x-sigap-request") != "1":
        raise error(403, "REQUEST_REJECTED", "Permintaan tidak diizinkan dari halaman ini.")


router = APIRouter(prefix="/api/auth", tags=["Akun operator"])


@router.post("/login", response_model=SessionView, dependencies=[Depends(require_origin)])
def login(payload: LoginInput, request: Request, response: Response):
    service = request.app.state.auth
    raw, view = service.login(payload, request.client.host if request.client else "unknown", request.cookies.get(COOKIE_NAME))
    response.set_cookie(COOKIE_NAME, raw, max_age=service.settings.sigap_session_seconds,
                        httponly=True, secure=service.settings.sigap_cookie_secure, samesite="strict", path="/api")
    return view


@router.get("/session", response_model=SessionView)
def session(request: Request, principal: Principal = Depends(require_operator)):
    return request.app.state.auth.view(principal, request.cookies[COOKIE_NAME])


@router.post("/logout", status_code=204, dependencies=[Depends(require_origin)])
def logout(request: Request, principal: Principal = Depends(require_operator)):
    expected = csrf_token(request.cookies[COOKIE_NAME])
    supplied = request.headers.get("x-csrf-token", "")
    if not re.fullmatch(r"[a-f0-9]{64}", supplied) or not hmac.compare_digest(expected, supplied):
        raise error(403, "CSRF_REJECTED", "Sesi halaman berubah. Muat ulang halaman sebelum keluar.")
    request.app.state.auth.logout(principal)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/api", httponly=True,
                           secure=request.app.state.auth.settings.sigap_cookie_secure, samesite="strict")
    return response
