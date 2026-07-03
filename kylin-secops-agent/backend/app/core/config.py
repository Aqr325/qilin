"""Application Configuration Management."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # ── Application Info ──
    PROJECT_NAME: str = "麒麟OS安全智能运维Agent"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # ── CORS ──
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000"]

    # ── Database ──
    # Optional explicit database file path (desktop mode). If set, DATABASE_URL
    # is ignored in favour of sqlite+aiosqlite:///DB_PATH
    DB_PATH: Optional[str] = None

    # SQLite for desktop/local; PostgreSQL for production
    DATABASE_URL: str = "sqlite+aiosqlite:///kylin_secops.db"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "kylin_secops"
    DB_PASSWORD: str = "kylin_secops_2026"
    DB_NAME: str = "kylin_secops"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── Redis ──
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SENTINEL: bool = False
    REDIS_SENTINEL_MASTER: str = "mymaster"
    REDIS_SENTINEL_HOSTS: List[str] = []

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── JWT ──
    JWT_SECRET_KEY: str = ""  # MUST be set via env var JWT_SECRET_KEY or config
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY_PATH: Optional[str] = None
    JWT_PUBLIC_KEY_PATH: Optional[str] = None
    JWT_PRIVATE_KEY: Optional[str] = None
    JWT_PUBLIC_KEY: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 15 minutes
    REFRESH_TOKEN_EXPIRE_HOURS: int = 24   # 24 hours
    JWT_TOKEN_TYPE: str = "bearer"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v:
            import secrets
            v = secrets.token_hex(32)
            print("[WARN] JWT_SECRET_KEY not configured, using random temporary key")
        return v

    # ── Auth ──
    BCRYPT_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    PASSWORD_MIN_LENGTH: int = 12
    MFA_ENABLED: bool = False

    # ── Agent ──
    AGENT_HEARTBEAT_TIMEOUT: int = 30  # seconds
    AGENT_HEARTBEAT_INTERVAL: int = 10  # seconds
    AGENT_OFFLINE_THRESHOLD: int = 30
    AGENT_TOKEN_EXPIRE_HOURS: int = 720  # 30 days

    # ── WebSocket ──
    WS_MAX_CONNECTIONS: int = 5000
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_HEARTBEAT_TIMEOUT: int = 60

    # ── Rate Limit ──
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: int = 5     # per minute
    RATE_LIMIT_DEFAULT: int = 60  # per minute

    # ── Celery ──
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── Logging ──
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # ── Storage ──
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # ── AI Service ──
    AI_API_URL: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    AI_MODEL: str = "qwen2.5-7b"
    AI_TIMEOUT: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        if v not in allowed:
            raise ValueError(f"JWT algorithm must be one of {allowed}")
        return v


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
