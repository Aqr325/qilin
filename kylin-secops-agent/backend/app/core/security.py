"""Security utilities: JWT, password hashing, token management."""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import bcrypt as _bcrypt
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Password Hashing ──
# Use bcrypt directly (passlib 1.7.4 is incompatible with bcrypt >= 4.1)


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return _bcrypt.hashpw(
        password.encode("utf-8"), _bcrypt.gensalt(settings.BCRYPT_ROUNDS)
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password,
    )


# ── JWT Token Management ──

def _get_jwt_algorithm() -> str:
    """Auto-detect JWT algorithm based on available keys.

    RS256 requires a real RSA keypair; HS256 works with a symmetric secret.
    This prevents the mismatch where config says RS256 but only a secret key
    is available (fallback path that actually uses HS256 signing).
    """
    private_key = settings.JWT_PRIVATE_KEY
    public_key = settings.JWT_PUBLIC_KEY

    if private_key and public_key:
        return settings.JWT_ALGORITHM  # RS256 (as configured)

    if settings.JWT_PRIVATE_KEY_PATH and settings.JWT_PUBLIC_KEY_PATH:
        try:
            with open(settings.JWT_PRIVATE_KEY_PATH, "r"):
                pass
            with open(settings.JWT_PUBLIC_KEY_PATH, "r"):
                pass
            return settings.JWT_ALGORITHM  # RS256 (as configured)
        except FileNotFoundError:
            logger.warning("JWT key files not found, falling back to HS256")

    # Fallback: no RSA keys → HS256 with symmetric secret
    logger.info("Using HS256 JWT signing (development mode)")
    return "HS256"


def _get_jwt_key() -> Tuple[str, str]:
    """Get signing/verification keys and algorithm.

    Priority:
    1. From environment variables (JWT_PRIVATE_KEY / JWT_PUBLIC_KEY)
    2. From file paths (JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH)
    3. Fallback to HS256 with JWT_SECRET_KEY for development
    """
    private_key = settings.JWT_PRIVATE_KEY
    public_key = settings.JWT_PUBLIC_KEY

    if private_key and public_key:
        return private_key, public_key

    if settings.JWT_PRIVATE_KEY_PATH and settings.JWT_PUBLIC_KEY_PATH:
        try:
            with open(settings.JWT_PRIVATE_KEY_PATH, "r") as f:
                private_key = f.read()
            with open(settings.JWT_PUBLIC_KEY_PATH, "r") as f:
                public_key = f.read()
            return private_key, public_key
        except FileNotFoundError:
            logger.warning("JWT key files not found, falling back to HS256")

    # Fallback: use HS256 with secret key
    return settings.JWT_SECRET_KEY, settings.JWT_SECRET_KEY


def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a JWT access token (short-lived)."""
    key, _ = _get_jwt_key()
    algorithm = _get_jwt_algorithm()
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "token_type": settings.JWT_TOKEN_TYPE,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, key, algorithm=algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a JWT refresh token (long-lived)."""
    key, _ = _get_jwt_key()
    algorithm = _get_jwt_algorithm()
    expires_delta = timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
        "token_type": settings.JWT_TOKEN_TYPE,
    }
    return jwt.encode(payload, key, algorithm=algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT token."""
    _, public_key = _get_jwt_key()
    algorithm = _get_jwt_algorithm()
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[algorithm],
            options={"verify_exp": True},
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise


def create_token_pair(
    user_id: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create both access and refresh tokens."""
    access_token = create_access_token(user_id, extra_claims)
    refresh_token = create_refresh_token(user_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": settings.JWT_TOKEN_TYPE,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
    }


def verify_token_type(token: str, expected_type: str) -> bool:
    """Verify the token type (access vs refresh)."""
    try:
        payload = decode_token(token)
        return payload.get("type") == expected_type
    except JWTError:
        return False


def is_token_expired(token: str) -> bool:
    """Check if a token is expired."""
    try:
        decode_token(token)
        return False
    except JWTError:
        return True


# ── Random Token Generation ──
import secrets


def generate_agent_token() -> str:
    """Generate a secure random token for Agent authentication."""
    return f"kylin_agent_{secrets.token_urlsafe(32)}"


def generate_mfa_secret() -> str:
    """Generate a TOTP secret for MFA."""
    return secrets.token_hex(20)


# ── API Key Encryption ──
import base64
from cryptography.fernet import Fernet


def get_encryption_key() -> bytes:
    """从环境变量获取加密密钥，若不存在则使用项目固定密钥。"""
    key = os.environ.get("AI_API_KEY_ENCRYPTION_KEY")
    if not key:
        key = "kylin-secops-ai-key-2026-0708-32bytes!"
    return base64.urlsafe_b64encode(key.ljust(32).encode()[:32])


_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_api_key(plain_text: str) -> str:
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_api_key(cipher_text: str) -> str:
    return _get_fernet().decrypt(cipher_text.encode()).decode()
