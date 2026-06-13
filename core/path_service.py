import os
from dataclasses import dataclass
from pathlib import Path

from .path_resolver import resolver_caminho
from .validators import validate_save_path


@dataclass(frozen=True)
class SavePathValidationResult:
    invalid_lines: tuple[int, ...]
    valid_paths: tuple[str, ...]

    @property
    def has_valid_paths(self):
        return bool(self.valid_paths)

    @property
    def is_valid(self):
        return not self.invalid_lines and self.has_valid_paths


@dataclass(frozen=True)
class AppendSavePathsResult:
    paths: tuple[str, ...]
    added_count: int
    changed: bool


@dataclass(frozen=True)
class OpenPathResult:
    opened_count: int
    opened_paths: tuple[str, ...]


def resolve_path(path_value):
    return str(Path(resolver_caminho(path_value)))


def validate_save_path_lines(path_lines):
    invalid_lines = []
    valid_paths = []

    for line_number, path in path_lines:
        try:
            valid_paths.append(validate_save_path(path))
        except ValueError:
            invalid_lines.append(line_number)

    return SavePathValidationResult(
        invalid_lines=tuple(invalid_lines),
        valid_paths=tuple(valid_paths),
    )


def append_save_directories(existing_paths, candidate_paths):
    paths = list(existing_paths or [])
    resolved_existing = {resolve_path(path) for path in paths}
    added_count = 0

    for path in candidate_paths or ():
        cleaned = str(path or "").strip().strip("{").strip("}")
        if not cleaned:
            continue

        resolved = Path(resolver_caminho(cleaned))
        if not resolved.is_dir():
            continue

        resolved_str = str(resolved)
        if resolved_str in resolved_existing:
            continue

        resolved_existing.add(resolved_str)
        paths.append(cleaned)
        added_count += 1

    return AppendSavePathsResult(
        paths=tuple(paths),
        added_count=added_count,
        changed=added_count > 0,
    )


def _open_with_system(path):
    os.startfile(str(path))


def open_save_directories(paths, opener=None):
    opener = opener or _open_with_system
    opened_paths = []

    for path in paths or ():
        resolved_path = Path(resolver_caminho(path))
        opener(resolved_path)
        opened_paths.append(str(resolved_path))

    return OpenPathResult(opened_count=len(opened_paths), opened_paths=tuple(opened_paths))


def open_save_directory(path_value, opener=None):
    normalized = validate_save_path(path_value)
    return open_save_directories([normalized], opener=opener)


__all__ = [
    "AppendSavePathsResult",
    "OpenPathResult",
    "SavePathValidationResult",
    "append_save_directories",
    "open_save_directories",
    "open_save_directory",
    "resolve_path",
    "validate_save_path_lines",
]
