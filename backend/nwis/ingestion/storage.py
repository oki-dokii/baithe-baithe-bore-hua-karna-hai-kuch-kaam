import hashlib
import os
from pathlib import Path
from uuid import uuid4

from nwis.config import get_settings


def path_for(key: str) -> Path:
    root = get_settings().storage_root.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Invalid storage key")
    return path


def store_blob(key: str, content: bytes) -> None:
    path = path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(content).digest():
            raise ValueError("Immutable storage object has different contents")
        return
    temporary = path.with_name(f".{uuid4()}.upload")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
