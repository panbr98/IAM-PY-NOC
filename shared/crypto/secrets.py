from __future__ import annotations

import base64
import hashlib
import os


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def encode_secret(value: str) -> str:
    key = _secret_key()
    payload = value.encode("utf-8")
    encrypted = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(payload))
    return "v2:" + base64.b64encode(encrypted).decode("ascii")


def decode_secret(value: str) -> str:
    if not value.startswith("v2:"):
        return base64.b64decode(value.encode("ascii")).decode("utf-8")
    key = _secret_key()
    payload = base64.b64decode(value[3:].encode("ascii"))
    decrypted = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(payload))
    return decrypted.decode("utf-8")


def _secret_key() -> bytes:
    raw = os.getenv("NOCTRIX_SECRET_ENCRYPTION_KEY") or os.getenv("NOCTRIX_JWT_SECRET") or "change-me-in-production-32-byte-key"
    return hashlib.sha256(raw.encode("utf-8")).digest()
