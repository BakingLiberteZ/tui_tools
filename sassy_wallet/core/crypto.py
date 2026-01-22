import os
import base64
from dataclasses import dataclass
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EncryptedBlob:
    salt_b64: str
    nonce_b64: str
    ct_b64: str


def _kdf(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2**15,
        r=8,
        p=1,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_secret(secret: str, passphrase: str) -> EncryptedBlob:
    salt = os.urandom(16)
    key = _kdf(passphrase, salt)

    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, secret.encode("utf-8"), None)

    return EncryptedBlob(
        salt_b64=base64.b64encode(salt).decode("utf-8"),
        nonce_b64=base64.b64encode(nonce).decode("utf-8"),
        ct_b64=base64.b64encode(ct).decode("utf-8"),
    )


def decrypt_secret(blob: EncryptedBlob, passphrase: str) -> str:
    salt = base64.b64decode(blob.salt_b64)
    nonce = base64.b64decode(blob.nonce_b64)
    ct = base64.b64decode(blob.ct_b64)

    key = _kdf(passphrase, salt)
    aes = AESGCM(key)
    pt = aes.decrypt(nonce, ct, None)

    return pt.decode("utf-8")
