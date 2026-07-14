"""Validate release-version declarations and documentation hygiene."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote


RELEASE_HEADING_RE = re.compile(
    r"^##\s+v?(?P<version>\d+\.\d+\.\d+)\s+-\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
TAG_RE = re.compile(r"v(?P<version>\d+\.\d+\.\d+)")
HARDCODED_INSTALLER_RE = re.compile(
    r"VeinServerManagement-Setup-v\d+\.\d+\.\d+\.exe"
)
MARKDOWN_LINK_RE = re.compile(
    r"(?<!!)\[[^\]]*\]\((?P<target><[^>]+>|[^\s)]+)"
    r"(?:\s+[\"'][^\"']*[\"'])?\)"
)


@dataclass(frozen=True)
class VersionDeclaration:
    path: str
    pattern: re.Pattern[str]
    description: str


CURRENT_VERSION_DECLARATIONS = (
    VersionDeclaration(
        "README.md",
        re.compile(
            r"current stable release is \*\*v(?P<version>\d+\.\d+\.\d+)\*\*",
            re.IGNORECASE,
        ),
        "current stable release",
    ),
    VersionDeclaration(
        "ROADMAP.md",
        re.compile(r"Released through `v(?P<version>\d+\.\d+\.\d+)`"),
        "roadmap current baseline",
    ),
    VersionDeclaration(
        "RELEASING.md",
        re.compile(
            r"current release baseline is `v(?P<version>\d+\.\d+\.\d+)`",
            re.IGNORECASE,
        ),
        "release baseline",
    ),
    VersionDeclaration(
        "Docs/_index.md",
        re.compile(
            r"\*\*Version baseline:\*\* v(?P<version>\d+\.\d+\.\d+)",
            re.IGNORECASE,
        ),
        "documentation-index baseline",
    ),
    VersionDeclaration(
        "Docs/docs_for_codex.md",
        re.compile(
            r"current stable baseline is v(?P<version>\d+\.\d+\.\d+)",
            re.IGNORECASE,
        ),
        "AI project-guide baseline",
    ),
)


def _version_key(version: str) -> tuple[int, int, int]:
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"Invalid semantic version: {version}")
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{path}: could not be read as UTF-8: {exc}")
        return ""


def _release_sections(changelog: str) -> list[tuple[str, int, int]]:
    matches = list(RELEASE_HEADING_RE.finditer(changelog))
    sections: list[tuple[str, int, int]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        sections.append((match.group("version"), match.end(), end))
    return sections


def _check_changelog(changelog: str, errors: list[str]) -> str | None:
    sections = _release_sections(changelog)
    if not sections:
        errors.append(
            "CHANGELOG.md: no dated release heading found; expected "
            "'## X.Y.Z - YYYY-MM-DD'"
        )
        return None

    versions = [version for version, _, _ in sections]
    duplicates = sorted({version for version in versions if versions.count(version) > 1})
    if duplicates:
        errors.append(
            "CHANGELOG.md: duplicate release headings: " + ", ".join(duplicates)
        )

    if [_version_key(version) for version in versions] != sorted(
        (_version_key(version) for version in versions), reverse=True
    ):
        errors.append("CHANGELOG.md: release headings are not in descending version order")

    current, body_start, body_end = sections[0]
    body = changelog[body_start:body_end]
    if not re.search(r"^\s*-\s+\S", body, re.MULTILINE):
        errors.append(f"CHANGELOG.md: release {current} has no bullet release notes")
    return current


def _check_declarations(root: Path, expected: str, errors: list[str]) -> None:
    for declaration in CURRENT_VERSION_DECLARATIONS:
        path = root / declaration.path
        text = _read(path, errors)
        if not text:
            continue
        matches = list(declaration.pattern.finditer(text))
        if len(matches) != 1:
            errors.append(
                f"{declaration.path}: expected exactly one "
                f"{declaration.description} declaration, found {len(matches)}"
            )
            continue
        actual = matches[0].group("version")
        if actual != expected:
            errors.append(
                f"{declaration.path}: {declaration.description} is v{actual}; "
                f"CHANGELOG.md expects v{expected}"
            )


def _markdown_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        if any(part in {".git", ".venv", "build", "dist"} for part in path.parts):
            continue
        yield path


def _check_generic_examples(root: Path, errors: list[str]) -> None:
    for path in _markdown_files(root):
        text = _read(path, errors)
        for match in HARDCODED_INSTALLER_RE.finditer(text):
            relative = path.relative_to(root)
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"{relative}:{line}: generic installer example hardcodes "
                f"'{match.group(0)}'; use VeinServerManagement-Setup-vX.Y.Z.exe"
            )


def _check_relative_links(root: Path, errors: list[str]) -> None:
    for path in _markdown_files(root):
        text = _read(path, errors)
        for match in MARKDOWN_LINK_RE.finditer(text):
            raw = match.group("target").strip("<>")
            if not raw or raw.startswith("#"):
                continue
            target = unquote(raw.split("#", 1)[0].split("?", 1)[0])
            if not target or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            candidate = (path.parent / target).resolve()
            if candidate.exists():
                continue
            relative = path.relative_to(root)
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"{relative}:{line}: relative Markdown link target does not "
                f"exist: {raw}"
            )


def check_documentation(root: Path, *, tag: str | None = None) -> list[str]:
    """Return human-readable consistency errors for a repository root."""

    root = root.resolve()
    errors: list[str] = []
    changelog = _read(root / "CHANGELOG.md", errors)
    expected = _check_changelog(changelog, errors) if changelog else None
    if expected:
        _check_declarations(root, expected, errors)

    if tag is not None:
        tag_match = TAG_RE.fullmatch(tag.strip())
        if not tag_match:
            errors.append(
                f"Release tag '{tag}' is invalid; expected vMAJOR.MINOR.PATCH"
            )
        elif expected and tag_match.group("version") != expected:
            errors.append(
                f"Release tag {tag} does not match newest CHANGELOG.md release "
                f"v{expected}"
            )

    _check_generic_examples(root, errors)
    _check_relative_links(root, errors)
    return errors


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check changelog ordering, current-version declarations, release tag "
            "consistency, and generic documentation examples."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (defaults to this module's repository)",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional release tag to require, formatted vMAJOR.MINOR.PATCH",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    errors = check_documentation(args.root, tag=args.tag)
    if errors:
        print("Documentation/version consistency check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Documentation/version consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
