import os
from pathlib import Path
from dataclasses import dataclass

# Default execution order, used when no folder list is supplied.
DEFAULT_FOLDERS = (
    "tables/dimensions",
    "tables/facts",
    "views",
)

@dataclass(frozen=True)
class Step:
    name: str
    folder: str
    files: list[str]


def get_sql_files(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return sorted(str(f) for f in folder.glob("*.sql"))


def validate_release(release_root: Path):
    if not release_root.exists():
        raise FileNotFoundError(f"Release folder does not exist: {release_root}")


def _release_root(release_version: str) -> Path:
    return (
        Path(__file__).parent / ".." / ".." / "releases" / release_version
    ).resolve()


def parse_folders(folders: str | None) -> list[str]:
    """Parse a comma-separated folder list, e.g. 'tables/dimensions,tables/facts,views'.

    Empty / None falls back to DEFAULT_FOLDERS.
    """
    if not folders or not folders.strip():
        return list(DEFAULT_FOLDERS)
    return [
        f.strip().replace("\\", "/").strip("/")
        for f in folders.split(",")
        if f.strip()
    ]


def get_steps(release_version: str, folders: list[str] | None = None) -> list[Step]:
    """Return deployment steps in the given folder order (defaults to DEFAULT_FOLDERS)."""
    release_root = _release_root(release_version)
    validate_release(release_root)

    steps = []
    for folder in (folders or DEFAULT_FOLDERS):
        path = (release_root / folder).resolve()
        if release_root not in path.parents:
            raise ValueError(f"Folder '{folder}' is outside release root {release_root}")
        steps.append(Step(name=folder, folder=folder, files=get_sql_files(path)))
    return steps
