"""개인 사이트 접근 코드 검증 — 원문 대신 SHA-256 해시만 코드에 둔다."""

import hashlib
import hmac
import os

DEFAULT_SITE_ACCESS_HASH = "2156aefb8c63d4b601f8354ea392867fd552dae01233f8efd5f739e3e1cdeb5b"


def valid_site_access(value: str | None) -> bool:
    if not value or len(value) > 256:
        return False
    expected = os.environ.get("SITE_ACCESS_HASH", DEFAULT_SITE_ACCESS_HASH).strip().lower()
    candidate = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, expected)
