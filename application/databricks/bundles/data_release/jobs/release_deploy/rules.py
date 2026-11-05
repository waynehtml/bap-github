import os
from pathlib import Path
from dataclasses import dataclass

DEPLOYMENT_STEPS = (
    ("Dimensions", "tables/dimensions"),
    ("Facts", "tables/facts"),
    ("Views", "views"),
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


def get_step(release_version: str, stage_name: str) -> Step:
    release_root = _release_root(release_version)
    validate_release(release_root)

    for name, folder in DEPLOYMENT_STEPS:
        if name == stage_name:
            sql_files = get_sql_files(release_root / folder)
            return Step(name=name, folder=folder, files=sql_files)

    valid_names = [s[0] for s in DEPLOYMENT_STEPS]
    raise ValueError(f"Unknown stage '{stage_name}'. Valid stages: {valid_names}")