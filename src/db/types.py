import json
from typing import Any, Optional
from sqlalchemy.types import TypeDecorator, Text
from src.core.security import DataEncryption

class EncryptedJSON(TypeDecorator):
    """
    Saves JSON as an Encrypted String in the DB.
    Decrypts back to JSON on retrieval.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        if value is None:
            return None
        # 1. Convert Dict -> JSON String
        json_str = json.dumps(value)
        # 2. Encrypt String
        return DataEncryption.encrypt(json_str)

    def process_result_value(self, value: Optional[str], dialect) -> Any:
        if value is None:
            return None
        # 1. Decrypt String
        json_str = DataEncryption.decrypt(value)
        # 2. Parse JSON
        return json.loads(json_str)