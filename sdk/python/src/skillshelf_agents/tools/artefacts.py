from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path

from pydantic import BaseModel


class StoredArtifact(BaseModel):
    artifact_id: str
    path: str
    media_type: str
    sha256: str
    size_bytes: int


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store_bytes(
        self,
        content: bytes,
        *,
        suffix: str = ".bin",
        media_type: str | None = None,
    ) -> StoredArtifact:
        artifact_id = f"artifact-{uuid.uuid4().hex}"
        path = self.root / f"{artifact_id}{suffix}"
        path.write_bytes(content)
        return StoredArtifact(
            artifact_id=artifact_id,
            path=str(path),
            media_type=media_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )

    def store_text(self, content: str, *, suffix: str = ".txt") -> StoredArtifact:
        return self.store_bytes(content.encode("utf-8"), suffix=suffix, media_type="text/plain")

    def path_for(self, artifact_id: str) -> Path:
        matches = list(self.root.glob(f"{artifact_id}.*"))
        if len(matches) != 1:
            raise KeyError(artifact_id)
        return matches[0]
