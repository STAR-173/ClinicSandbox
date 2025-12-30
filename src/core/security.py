from cryptography.fernet import Fernet
import base64
import hashlib
from src.core.config import settings

class DataEncryption:
    _cipher_suite = None

    @classmethod
    def get_cipher(cls) -> Fernet:
        if cls._cipher_suite is None:
            # Generate a 32-byte key from the secret setting
            # We use SHA256 to ensure the key is exactly 32 bytes URL-safe base64
            key = hashlib.sha256(settings.WEBHOOK_SECRET.encode()).digest()
            key_b64 = base64.urlsafe_b64encode(key)
            cls._cipher_suite = Fernet(key_b64)
        return cls._cipher_suite

    @classmethod
    def encrypt(cls, data: str) -> str:
        if not data:
            return ""
        return cls.get_cipher().encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, token: str) -> str:
        if not token:
            return ""
        return cls.get_cipher().decrypt(token.encode()).decode()