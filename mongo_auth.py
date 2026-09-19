"""
Nobi MongoDB Auth Module
Replaces PostgreSQL/SQLAlchemy for user authentication.
Uses Motor (async MongoDB driver) — works on Vercel serverless.
"""
import os
import re
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import motor.motor_asyncio
from pymongo import ASCENDING, IndexModel
from dotenv import load_dotenv

load_dotenv(override=True)

# ── MongoDB Connection ────────────────────────────────────────────────────────
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://vishal:GPZT7pqswsRE5r1Y@test.jogzeev.mongodb.net/?appName=test"
)
MONGODB_DB = os.getenv("MONGODB_DB", "nobi")

_mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
_accounts_col = None
_indexes_created = False


def get_mongo_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
    return _mongo_client


def get_accounts_collection():
    """Return the nobi_accounts Motor collection (lazy-initialized)."""
    global _accounts_col
    if _accounts_col is None:
        client = get_mongo_client()
        db = client[MONGODB_DB]
        _accounts_col = db["nobi_accounts"]
    return _accounts_col


async def ensure_indexes():
    """Create unique index on email (idempotent — safe to call multiple times)."""
    global _indexes_created
    if _indexes_created:
        return
    try:
        col = get_accounts_collection()
        await col.create_index(
            [("email", ASCENDING)],
            unique=True,
            name="uq_nobi_accounts_email"
        )
        _indexes_created = True
        print("[MongoDB] Unique index on email ensured.")
    except Exception as e:
        print(f"[MongoDB] Index creation note: {e}")


# ── Password Helpers ──────────────────────────────────────────────────────────
def hash_password_mongo(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 + random salt."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000
    )
    return f"pbkdf2:sha256:{salt}:{pw_hash.hex()}"


def verify_password_mongo(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        parts = stored_hash.split(":")
        if len(parts) != 4 or parts[0] != "pbkdf2" or parts[1] != "sha256":
            return False
        _, _, salt, expected_hex = parts
        pw_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000
        )
        return pw_hash.hex() == expected_hex
    except Exception:
        return False


def normalize_email_mongo(email: Optional[str]) -> str:
    """Normalize email: strip + lowercase."""
    return (email or "").strip().lower()


# ── Document → Dict Serializer ────────────────────────────────────────────────
def user_doc_to_dict(doc: dict) -> dict:
    """Convert a MongoDB document to a safe JSON-serializable user dict."""
    return {
        "id": str(doc.get("_id", "")),
        "username": doc.get("username", ""),
        "email": doc.get("email", ""),
        "full_name": doc.get("full_name", ""),
        "role": doc.get("role", "user"),
        "is_active": doc.get("is_active", True),
        "subscription_status": doc.get("subscription_status", "free_trial"),
        "plan": doc.get("plan", "trial"),
        "billing_cycle": doc.get("billing_cycle", "monthly"),
        "trial_start": doc.get("trial_start", datetime.utcnow()).isoformat() if doc.get("trial_start") else None,
        "trial_end": doc.get("trial_end", datetime.utcnow()).isoformat() if doc.get("trial_end") else None,
        "created_at": doc.get("created_at", datetime.utcnow()).isoformat() if doc.get("created_at") else None,
    }

