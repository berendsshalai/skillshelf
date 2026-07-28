from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

from pydantic import BaseModel


class RepositoryPathViolation(PermissionError):
    pass


class TextFileResult(BaseModel):
    path: str
    content: str
    sha256: str
    size_bytes: int


class BinaryMetadataResult(BaseModel):
    path: str
    sha256: str
    size_bytes: int
    media_type: str = "application/octet-stream"


class FileWriteResult(BaseModel):
    path: str
    sha256_before: str | None
    sha256_after: str
    size_bytes: int
    backup_path: str | None


class SearchMatch(BaseModel):
    path: str
    line: int
    text: str


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class RepositoryFilesystem:
    """Filesystem operations confined to one repository and immutable-source boundaries."""

    def __init__(self, root: Path, backup_root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.backup_root = backup_root.expanduser().resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(self.root)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.submodule_roots = self._submodule_roots()

    def _submodule_roots(self) -> tuple[Path, ...]:
        manifest = self.root / ".gitmodules"
        if not manifest.is_file():
            return ()
        roots: list[Path] = []
        for match in re.finditer(r"(?m)^\s*path\s*=\s*(.+?)\s*$", manifest.read_text(encoding="utf-8")):
            roots.append((self.root / match.group(1)).resolve())
        return tuple(roots)

    @staticmethod
    def _is_reparse(path: Path) -> bool:
        try:
            value = path.lstat()
        except FileNotFoundError:
            return False
        attributes = getattr(value, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return path.is_symlink() or bool(attributes & reparse_flag)

    def resolve(self, relative: str | Path, *, write: bool = False) -> Path:
        value = Path(relative)
        if value.is_absolute():
            candidate = value
        else:
            candidate = self.root / value

        # Inspect every existing lexical component before resolve follows a link/junction.
        lexical = Path(os.path.abspath(candidate))
        try:
            lexical.relative_to(self.root)
        except ValueError as exc:
            raise RepositoryPathViolation("path escapes the authorised repository") from exc
        current = self.root
        for part in lexical.relative_to(self.root).parts:
            current = current / part
            if current.exists() and self._is_reparse(current):
                raise RepositoryPathViolation("symlink or reparse-point paths are not authorised")

        resolved = candidate.resolve()
        try:
            relative_path = resolved.relative_to(self.root)
        except ValueError as exc:
            raise RepositoryPathViolation("path escapes the authorised repository") from exc

        if write:
            lowered = {part.casefold() for part in relative_path.parts}
            if lowered.intersection({".git", "vendor", "upstream"}):
                raise RepositoryPathViolation(
                    "writes to Git metadata or immutable vendor sources are forbidden"
                )
            if any(
                resolved == submodule or submodule in resolved.parents for submodule in self.submodule_roots
            ):
                raise RepositoryPathViolation("writes inside submodules are forbidden")
        return resolved

    def read_text_file(self, path: str) -> TextFileResult:
        resolved = self.resolve(path)
        content = resolved.read_bytes()
        return TextFileResult(
            path=resolved.relative_to(self.root).as_posix(),
            content=content.decode("utf-8"),
            sha256=_sha256(content),
            size_bytes=len(content),
        )

    def read_binary_metadata(self, path: str) -> BinaryMetadataResult:
        resolved = self.resolve(path)
        content = resolved.read_bytes()
        return BinaryMetadataResult(
            path=resolved.relative_to(self.root).as_posix(),
            sha256=_sha256(content),
            size_bytes=len(content),
        )

    def list_directory(self, path: str = ".") -> list[str]:
        resolved = self.resolve(path)
        if not resolved.is_dir():
            raise NotADirectoryError(path)
        return sorted(item.name for item in resolved.iterdir())

    def search_text(self, query: str, path: str = ".", max_results: int = 100) -> list[SearchMatch]:
        if not query:
            raise ValueError("query cannot be empty")
        if max_results < 1 or max_results > 1000:
            raise ValueError("max_results must be between 1 and 1000")
        base = self.resolve(path)
        files = [base] if base.is_file() else base.rglob("*")
        matches: list[SearchMatch] = []
        for candidate in files:
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(self.root)
            if {part.casefold() for part in relative.parts}.intersection({".git", "vendor", "upstream"}):
                continue
            try:
                text = candidate.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                if query.casefold() in line.casefold():
                    matches.append(SearchMatch(path=relative.as_posix(), line=line_number, text=line[:1000]))
                    if len(matches) >= max_results:
                        return matches
        return matches

    def _backup(self, target: Path) -> str | None:
        if not target.is_file():
            return None
        relative = target.relative_to(self.root)
        destination = self.backup_root / uuid.uuid4().hex / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        return str(destination)

    def write_text_file(self, path: str, content: str) -> FileWriteResult:
        target = self.resolve(path, write=True)
        before = target.read_bytes() if target.is_file() else None
        backup = self._backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return FileWriteResult(
            path=target.relative_to(self.root).as_posix(),
            sha256_before=_sha256(before) if before is not None else None,
            sha256_after=_sha256(encoded),
            size_bytes=len(encoded),
            backup_path=backup,
        )

    def create_directory(self, path: str) -> str:
        target = self.resolve(path, write=True)
        target.mkdir(parents=True, exist_ok=True)
        return target.relative_to(self.root).as_posix()

    def apply_unified_patch(self, patch: str) -> list[FileWriteResult]:
        paths = re.findall(r"(?m)^\+\+\+ b/(.+)$", patch)
        if not paths:
            raise ValueError("patch does not contain repository-relative targets")
        targets = [self.resolve(path.strip(), write=True) for path in paths if path.strip() != "/dev/null"]
        before = {
            target: (target.read_bytes() if target.is_file() else None, self._backup(target))
            for target in targets
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".patch",
            dir=self.backup_root,
            delete=False,
        ) as stream:
            stream.write(patch)
            patch_path = Path(stream.name)
        try:
            check = subprocess.run(
                ["git", "apply", "--check", "--whitespace=nowarn", str(patch_path)],
                cwd=self.root,
                capture_output=True,
                text=True,
                shell=False,
            )
            if check.returncode:
                raise ValueError(check.stderr.strip() or "patch check failed")
            applied = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(patch_path)],
                cwd=self.root,
                capture_output=True,
                text=True,
                shell=False,
            )
            if applied.returncode:
                raise RuntimeError(applied.stderr.strip() or "patch apply failed")
        finally:
            patch_path.unlink(missing_ok=True)
        results = []
        for target in targets:
            old, backup = before[target]
            current = target.read_bytes() if target.is_file() else b""
            results.append(
                FileWriteResult(
                    path=target.relative_to(self.root).as_posix(),
                    sha256_before=_sha256(old) if old is not None else None,
                    sha256_after=_sha256(current),
                    size_bytes=len(current),
                    backup_path=backup,
                )
            )
        return results
