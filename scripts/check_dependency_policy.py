#!/usr/bin/env python3
"""Enforce dependency pinning and provenance policy for runtime dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None  # type: ignore[assignment]


PIN_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?)\s*==\s*([A-Za-z0-9+!._-]+)\s*$"
)


def normalize_package_name(spec_name: str) -> str:
    base = spec_name.split("[", 1)[0]
    return re.sub(r"[-_.]+", "-", base).lower()


def strip_marker(spec: str) -> str:
    return spec.split(";", 1)[0].strip()


def has_forbidden_source(spec: str) -> bool:
    lowered = spec.lower()
    return (
        "://" in lowered
        or "git+" in lowered
        or "file:" in lowered
        or "path:" in lowered
        or "@" in lowered
    )


def parse_pinned_specs(specs: Iterable[str], *, context: str, failures: list[str]) -> set[str]:
    normalized_names: set[str] = set()
    for raw in specs:
        spec = strip_marker(raw)
        if not spec:
            continue
        if has_forbidden_source(spec):
            failures.append(f"{context}: forbidden direct source in dependency '{raw}'")
            continue
        match = PIN_RE.match(spec)
        if not match:
            failures.append(f"{context}: dependency must be exact-pinned with '==': '{raw}'")
            continue
        normalized_names.add(normalize_package_name(match.group(1)))
    return normalized_names


def load_runtime_dependencies(pyproject_path: Path, failures: list[str]) -> set[str]:
    try:
        text = pyproject_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        failures.append(f"Missing {pyproject_path}")
        return set()

    if tomllib is not None:
        try:
            data = tomllib.loads(text)
            deps = (((data.get("project") or {}).get("dependencies")) or [])
            if not isinstance(deps, list):
                failures.append("[project].dependencies must be a list in pyproject.toml")
                return set()
            return parse_pinned_specs((str(dep) for dep in deps), context="pyproject.toml", failures=failures)
        except Exception as e:  # pragma: no cover - defensive parse guard
            failures.append(f"Failed to parse {pyproject_path}: {e}")
            return set()

    # Fallback parser for Python 3.10 without tomllib/tomli.
    in_project = False
    in_deps = False
    deps: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_project = line == "[project]"
            in_deps = False
            continue
        if in_project and line.startswith("dependencies"):
            in_deps = True
            continue
        if in_project and in_deps:
            if line.startswith("]"):
                break
            match = re.match(r'^"([^"]+)"\s*,?\s*$', line)
            if match:
                deps.append(match.group(1))
    if not deps:
        failures.append("Failed to read [project].dependencies from pyproject.toml")
        return set()
    return parse_pinned_specs(deps, context="pyproject.toml", failures=failures)


def load_requirements(requirements_path: Path, failures: list[str]) -> set[str]:
    names: set[str] = set()
    try:
        lines = requirements_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        failures.append(f"Missing {requirements_path}")
        return names

    req_specs: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("-", "--")):
            failures.append(f"requirements.txt: unsupported directive '{stripped}'")
            continue
        spec = stripped.split("#", 1)[0].strip()
        if spec:
            req_specs.append(spec)
    names = parse_pinned_specs(req_specs, context="requirements.txt", failures=failures)
    return names


def main() -> int:
    failures: list[str] = []
    repo_root = Path(__file__).resolve().parents[1]
    pyproject_path = repo_root / "pyproject.toml"
    requirements_path = repo_root / "requirements.txt"
    uv_lock_path = repo_root / "uv.lock"

    pyproject_names = load_runtime_dependencies(pyproject_path, failures)
    requirements_names = load_requirements(requirements_path, failures)

    missing_from_requirements = sorted(pyproject_names - requirements_names)
    if missing_from_requirements:
        failures.append(
            "requirements.txt missing runtime packages from pyproject.toml: "
            + ", ".join(missing_from_requirements)
        )

    extra_in_requirements = sorted(requirements_names - pyproject_names)
    if extra_in_requirements:
        failures.append(
            "requirements.txt has packages not declared in pyproject runtime dependencies: "
            + ", ".join(extra_in_requirements)
        )

    if not uv_lock_path.exists():
        print(
            "Warning: uv.lock is not committed yet. Generate one with `uv lock` for fully reproducible builds.",
            file=sys.stderr,
        )

    if failures:
        print("Dependency policy check failed:", file=sys.stderr)
        for issue in failures:
            print(f"- {issue}", file=sys.stderr)
        return 1

    print("Dependency policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
