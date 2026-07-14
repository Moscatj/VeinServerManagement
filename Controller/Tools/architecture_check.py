"""Validate the subsystem registry and high-value architecture boundaries."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable

import yaml


ALLOWED_RISKS = {"low", "medium", "high"}
REQUIRED_SUBSYSTEM_FIELDS = {"risk", "source", "tests", "docs", "invariants"}
DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
CONFIG_EDITOR_CONSUMERS = {
    "Controller/GUI/server_config_view.py",
    "Controller/Tools/server_quickstart.py",
}


def _read_ast(path: Path, errors: list[str], root: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append(f"{path.relative_to(root)}: could not parse Python source: {exc}")
        return None


def _string_literals(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _check_registry(root: Path, errors: list[str]) -> dict[str, Any] | None:
    path = root / "Docs" / "subsystems.yaml"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        errors.append(f"Docs/subsystems.yaml: could not load registry: {exc}")
        return None
    if not isinstance(payload, dict) or payload.get("version") != 1:
        errors.append("Docs/subsystems.yaml: registry version must be 1")
        return None
    subsystems = payload.get("subsystems")
    if not isinstance(subsystems, dict) or not subsystems:
        errors.append("Docs/subsystems.yaml: subsystems must be a non-empty mapping")
        return None

    for name, entry in subsystems.items():
        if not isinstance(entry, dict):
            errors.append(f"Docs/subsystems.yaml: {name} must be a mapping")
            continue
        missing = sorted(REQUIRED_SUBSYSTEM_FIELDS - set(entry))
        if missing:
            errors.append(
                f"Docs/subsystems.yaml: {name} is missing fields: {', '.join(missing)}"
            )
        if entry.get("risk") not in ALLOWED_RISKS:
            errors.append(
                f"Docs/subsystems.yaml: {name}.risk must be low, medium, or high"
            )
        for field in ("source", "tests", "docs", "invariants"):
            values = entry.get(field)
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                errors.append(
                    f"Docs/subsystems.yaml: {name}.{field} must be a non-empty string list"
                )
                continue
            if field == "invariants":
                continue
            for value in values:
                candidate = (root / value).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    errors.append(
                        f"Docs/subsystems.yaml: {name}.{field} escapes repository: {value}"
                    )
                    continue
                if not candidate.exists():
                    errors.append(
                        f"Docs/subsystems.yaml: {name}.{field} path does not exist: {value}"
                    )
    return payload


def _excluded(relative: str, patterns: list[str]) -> bool:
    path = PurePosixPath(relative)
    for pattern in patterns:
        if any(character in pattern for character in "*?["):
            if path.match(pattern):
                return True
        elif relative == pattern or relative.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def _owned_by_registry(root: Path, relative: str, entries: set[str]) -> bool:
    candidate = (root / relative).resolve()
    for entry in entries:
        owner = (root / entry).resolve()
        if candidate == owner:
            return True
        if owner.is_dir():
            try:
                candidate.relative_to(owner)
                return True
            except ValueError:
                pass
    return False


def _check_reverse_coverage(
    root: Path, registry: dict[str, Any], errors: list[str]
) -> None:
    coverage = registry.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("Docs/subsystems.yaml: coverage must be a mapping")
        return
    source_roots = coverage.get("source_roots")
    test_roots = coverage.get("test_roots")
    exclusions = coverage.get("exclude")
    for field, values in (
        ("source_roots", source_roots),
        ("test_roots", test_roots),
        ("exclude", exclusions),
    ):
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            errors.append(
                f"Docs/subsystems.yaml: coverage.{field} must be a string list"
            )
            return

    subsystems = registry["subsystems"]
    owned_sources = {
        value
        for entry in subsystems.values()
        if isinstance(entry, dict)
        for value in entry.get("source", [])
        if isinstance(value, str)
    }
    owned_tests = {
        value
        for entry in subsystems.values()
        if isinstance(entry, dict)
        for value in entry.get("tests", [])
        if isinstance(value, str)
    }

    for root_value in source_roots:
        scan_root = (root / root_value).resolve()
        if not scan_root.is_dir():
            errors.append(
                f"Docs/subsystems.yaml: coverage source root does not exist: {root_value}"
            )
            continue
        for path in scan_root.rglob("*.py"):
            relative = path.relative_to(root).as_posix()
            if _excluded(relative, exclusions):
                continue
            if not _owned_by_registry(root, relative, owned_sources):
                errors.append(f"Docs/subsystems.yaml: unowned source module: {relative}")

    for root_value in test_roots:
        scan_root = (root / root_value).resolve()
        if not scan_root.is_dir():
            errors.append(
                f"Docs/subsystems.yaml: coverage test root does not exist: {root_value}"
            )
            continue
        for path in scan_root.rglob("test_*.py"):
            relative = path.relative_to(root).as_posix()
            if _excluded(relative, exclusions):
                continue
            if not _owned_by_registry(root, relative, owned_tests):
                errors.append(f"Docs/subsystems.yaml: unowned test module: {relative}")


def _check_legacy_utils(root: Path, errors: list[str]) -> None:
    legacy = root / "Controller" / "utils.py"
    if legacy.exists():
        errors.append("Controller/utils.py must not be recreated")
    for path in (root / "Controller").rglob("*.py"):
        tree = _read_ast(path, errors, root)
        if tree is None:
            continue
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            if any(module == "utils" or module.endswith(".utils") for module in modules):
                errors.append(
                    f"{path.relative_to(root)}:{node.lineno}: imports removed utils module"
                )


def _check_absolute_paths(root: Path, errors: list[str]) -> None:
    for path in (root / "Controller").rglob("*.py"):
        tree = _read_ast(path, errors, root)
        if tree is None:
            continue
        for value in _string_literals(tree):
            if DRIVE_PATH_RE.match(value):
                errors.append(
                    f"{path.relative_to(root)}: hardcoded drive path literal is forbidden"
                )
                break


def _check_gui_process_control(root: Path, errors: list[str]) -> None:
    gui_root = root / "Controller" / "GUI"
    for path in gui_root.rglob("*.py"):
        tree = _read_ast(path, errors, root)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                is_os_kill = (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "kill"
                )
                if is_os_kill:
                    signal = node.args[1] if len(node.args) > 1 else None
                    if not isinstance(signal, ast.Constant) or signal.value != 0:
                        errors.append(
                            f"{path.relative_to(root)}:{node.lineno}: GUI os.kill is only "
                            "allowed for a signal-0 liveness probe"
                        )
                elif node.func.attr in {"kill", "terminate"}:
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: GUI process termination "
                        "must delegate to shared lifecycle logic"
                    )
            if isinstance(node, ast.Constant) and node.value == "taskkill":
                errors.append(
                    f"{path.relative_to(root)}:{node.lineno}: GUI taskkill use is forbidden"
                )


def _check_config_editor_ownership(root: Path, errors: list[str]) -> None:
    editor = "Controller/Tools/server_config_editor.py"
    for path in (root / "Controller").rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        tree = _read_ast(path, errors, root)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "apply_server_config_edits"
                and relative != editor
            ):
                errors.append(
                    f"{relative}:{node.lineno}: guarded config writer must be owned by {editor}"
                )
            if isinstance(node, ast.ImportFrom):
                imported = {alias.name for alias in node.names}
                if "apply_server_config_edits" in imported and relative not in CONFIG_EDITOR_CONSUMERS:
                    errors.append(
                        f"{relative}:{node.lineno}: unapproved guarded config-writer consumer"
                    )


def check_architecture(root: Path) -> list[str]:
    """Return architecture and registry violations for a repository root."""

    root = root.resolve()
    errors: list[str] = []
    registry = _check_registry(root, errors)
    if registry is not None:
        _check_reverse_coverage(root, registry, errors)
    _check_legacy_utils(root, errors)
    _check_absolute_paths(root, errors)
    _check_gui_process_control(root, errors)
    _check_config_editor_ownership(root, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root",
    )
    args = parser.parse_args(argv)
    errors = check_architecture(args.root)
    if errors:
        print("Architecture check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Architecture and subsystem registry checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
