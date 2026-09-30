"""Local account registration and password verification for the desktop app."""

import hashlib
import hmac
import os
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from solar_forge_desktop.storage import Profile, Storage

USERNAME = re.compile(r"^[a-z0-9_.-]{3,80}$")
INVALID_LOGIN = "Invalid username or password."


def _password_hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"scrypt:16384:8:1${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt:16384:8:1":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        if len(salt) != 16 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class AuthService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def has_accounts(self) -> bool:
        with self.storage.sessions() as session:
            account = session.scalar(
                select(Profile.id).where(Profile.username.is_not(None)).limit(1)
            )
            return account is not None

    def register(self, username: str, password: str) -> int:
        clean = (username or "").strip().lower()
        if not USERNAME.fullmatch(clean):
            raise ValueError("Use 3–80 letters, numbers, dots, hyphens, or underscores.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        password_hash = _password_hash(password)
        try:
            with self.storage.sessions.begin() as session:
                if session.scalar(select(Profile.id).where(Profile.username == clean)) is not None:
                    raise ValueError("That username is already taken.")
                unclaimed = session.scalars(
                    select(Profile).where(Profile.username.is_(None)).order_by(Profile.id)
                ).all()
                if len(unclaimed) == 1:
                    profile = unclaimed[0]
                    profile.name = clean
                    profile.username = clean
                    profile.password_hash = password_hash
                else:
                    profile = Profile(name=clean, username=clean, password_hash=password_hash)
                    session.add(profile)
                session.flush()
                return profile.id
        except IntegrityError as exc:
            raise ValueError("That username is already taken.") from exc

    def login(self, username: str, password: str) -> int:
        clean = (username or "").strip().lower()
        with self.storage.sessions() as session:
            profile = session.scalar(select(Profile).where(Profile.username == clean))
            if profile is None or not profile.password_hash:
                raise ValueError(INVALID_LOGIN)
            if not _verify_password(password or "", profile.password_hash):
                raise ValueError(INVALID_LOGIN)
            return profile.id
