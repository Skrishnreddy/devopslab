import hashlib
import secrets


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
