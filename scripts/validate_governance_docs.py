#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


ADR_FILENAME_RE = re.compile(r"ADR-\d{3}-[a-z0-9-]+\.md$")
CHANGE_RECORD_RE = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")

ADR_REQUIRED_HEADINGS = {
    "## Status",
    "## Context",
    "## Decision",
    "## Consequences",
}

CHANGE_RECORD_REQUIRED_HEADINGS = {
    "## Summary",
    "## Classification",
    "## Ownership",
    "## Root Cause",
    "## Source Changes",
    "## Artifact And Deployment Evidence",
    "## Live Verification",
    "## Follow-Up",
}

PR_TEMPLATE_REQUIRED_HEADINGS = {
    "## Summary",
    "## Governance Declaration",
    "## Documentation Updates",
    "## Validation",
    "## Review Gates",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_adr_files(errors: list[str], adr_dir: Path) -> None:
    if not adr_dir.exists():
        errors.append(f"{adr_dir}: missing ADR directory")
        return

    for path in sorted(adr_dir.glob("*.md")):
        if path.name in {"README.md", "TEMPLATE.md"}:
            continue
        if not ADR_FILENAME_RE.fullmatch(path.name):
            errors.append(f"{path}: invalid ADR filename")
            continue
        text = read_text(path)
        missing = sorted(heading for heading in ADR_REQUIRED_HEADINGS if heading not in text)
        if missing:
            errors.append(f"{path}: missing ADR headings: {', '.join(missing)}")


def validate_change_records(errors: list[str], records_dir: Path) -> None:
    if not records_dir.exists():
        errors.append(f"{records_dir}: missing change-record directory")
        return

    for path in sorted(records_dir.glob("*.md")):
        if path.name in {"README.md", "TEMPLATE.md"}:
            continue
        if not CHANGE_RECORD_RE.fullmatch(path.name):
            errors.append(f"{path}: invalid change-record filename")
            continue
        text = read_text(path)
        missing = sorted(heading for heading in CHANGE_RECORD_REQUIRED_HEADINGS if heading not in text)
        if missing:
            errors.append(f"{path}: missing change-record headings: {', '.join(missing)}")


def validate_pr_template(errors: list[str], template_path: Path) -> None:
    if not template_path.exists():
        errors.append(f"{template_path}: missing PR template")
        return

    text = read_text(template_path)
    missing = sorted(heading for heading in PR_TEMPLATE_REQUIRED_HEADINGS if heading not in text)
    if missing:
        errors.append(f"{template_path}: missing PR template headings: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ADR and change-record governance docs.")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    errors: list[str] = []

    validate_adr_files(errors, repo_root / "docs" / "decisions" / "adr")
    validate_change_records(errors, repo_root / "docs" / "records" / "change-records")
    validate_pr_template(errors, repo_root / ".github" / "pull_request_template.md")

    if errors:
        raise SystemExit("\n".join(errors))

    print("platform-engineering governance docs valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
