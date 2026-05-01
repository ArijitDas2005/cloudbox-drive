import secrets
from pathlib import Path


class CloudStorage:
    """
    Small storage abstraction used as the cloud layer in this demo app.
    The backing implementation writes to disk so the project stays runnable
    without external dependencies, but the interface is intentionally simple
    enough to swap for Firebase Storage or Amazon S3 later.
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, original_name: str, content: bytes) -> str:
        suffix = Path(original_name).suffix
        stored_name = f"{secrets.token_hex(16)}{suffix}"
        path = self.root / stored_name
        path.write_bytes(content)
        return stored_name

    def read_bytes(self, stored_name: str) -> bytes:
        path = self.root / stored_name
        return path.read_bytes()
