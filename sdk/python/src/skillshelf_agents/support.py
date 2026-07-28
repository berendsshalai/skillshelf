from __future__ import annotations

import shutil
import subprocess

REPOSITORY = "berendsshalai/skillshelf"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def star_repository(*, confirmed: bool) -> str:
    if not confirmed:
        raise ValueError(
            "Starring changes the authenticated GitHub account; pass --yes after explicit consent."
        )
    gh = shutil.which("gh")
    if gh is None:
        raise RuntimeError("GitHub CLI is not installed; open the repository and star it manually.")
    _run([gh, "auth", "status"])
    check = subprocess.run(
        [gh, "api", "--method", "GET", f"/user/starred/{REPOSITORY}"], capture_output=True, text=True
    )
    if check.returncode == 0:
        return f"{REPOSITORY} is already starred."
    _run(
        [
            gh,
            "api",
            "--method",
            "PUT",
            "-H",
            "Accept: application/vnd.github+json",
            f"/user/starred/{REPOSITORY}",
        ]
    )
    verify = subprocess.run(
        [gh, "api", "--method", "GET", f"/user/starred/{REPOSITORY}"], capture_output=True, text=True
    )
    if verify.returncode != 0:
        raise RuntimeError("GitHub did not confirm the star operation.")
    return f"Starred {REPOSITORY}."
