import os
import base64
from dataclasses import dataclass
from typing import Any, Optional
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EncryptedBlob:
    salt_b64: str
    nonce_b64: str
    ct_b64: str
    # Optional KDF work factor. Missing => legacy default for backward compatibility.
    kdf_n: Optional[int] = None


_LEGACY_KDF_N = 2**15
_DEFAULT_KDF_N = 2**16
_MIN_KDF_N = 2**15
_MAX_KDF_N = 2**18


def _normalize_kdf_n(value: Any, *, default: int) -> int:
    if value is None:
        return default
    try:
        kdf_n = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError("Invalid scrypt parameter n") from e
    # Enforce bounded power-of-two values to avoid malformed/DoS-heavy parameters.
    if kdf_n < _MIN_KDF_N or kdf_n > _MAX_KDF_N or (kdf_n & (kdf_n - 1)) != 0:
        raise ValueError("Unsupported scrypt parameter n")
    return kdf_n


def _kdf(passphrase: str, salt: bytes, *, n: int) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=n,
        r=8,
        p=1,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_secret(secret: str, passphrase: str) -> EncryptedBlob:
    salt = os.urandom(16)
    key = _kdf(passphrase, salt, n=_DEFAULT_KDF_N)

    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, secret.encode("utf-8"), None)

    return EncryptedBlob(
        salt_b64=base64.b64encode(salt).decode("utf-8"),
        nonce_b64=base64.b64encode(nonce).decode("utf-8"),
        ct_b64=base64.b64encode(ct).decode("utf-8"),
        kdf_n=_DEFAULT_KDF_N,
    )


def decrypt_secret(blob: EncryptedBlob, passphrase: str) -> str:
    salt = base64.b64decode(blob.salt_b64)
    nonce = base64.b64decode(blob.nonce_b64)
    ct = base64.b64decode(blob.ct_b64)

    kdf_n = _normalize_kdf_n(blob.kdf_n, default=_LEGACY_KDF_N)
    key = _kdf(passphrase, salt, n=kdf_n)
    aes = AESGCM(key)
    pt = aes.decrypt(nonce, ct, None)

    return pt.decode("utf-8")
