"""Scan prospective repository content for secrets and private local markers."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable


PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[^\s\"']+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"G:[\\/]"),
    re.compile(r"REPLACE_WITH_STRONG_SECRET_KEY"),
    re.compile(r"\bRHG\b"),
    re.compile(r"Red Head Software"),
)

IGNORED_PREFIXES = (
    "Controller/Tools/source_hygiene_check.py",
    "Config/Backup/",
    "Controller/Legacy/WebAdmin/user_accounts.json",
)

BINARY_SUFFIXES = {
    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".exe", ".dll",
    ".pyd", ".pyc", ".zip",
}


def _prospective_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    )
    return [root / line for line in result.stdout.splitlines() if line.strip()]


def scan_paths(root: Path, paths: Iterable[Path]) -> list[str]:
    """Return findings for the supplied repository-relative or absolute paths."""

    root = root.resolve()
    findings: list[str] = []
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        try:
            relative = candidate.resolve().relative_to(root).as_posix()
        except ValueError:
            findings.append(f"{candidate}: path is outside the repository")
            continue
        if relative.startswith(IGNORED_PREFIXES):
            continue
        if candidate.suffix.lower() in BINARY_SUFFIXES or not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for pattern in PATTERNS:
            if pattern.search(content):
                findings.append(f"{relative}: matched restricted pattern {pattern.pattern}")
    return findings


def check_repository(root: Path) -> list[str]:
    return scan_paths(root, _prospective_files(root.resolve()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root",
    )
    args = parser.parse_args(argv)
    try:
        findings = check_repository(args.root)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Source hygiene check could not run: {exc}")
        return 1
    if findings:
        print("Source hygiene check failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("Source hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
