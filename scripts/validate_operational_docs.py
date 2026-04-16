#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


DATE_PATTERNS = {
    Path("docs/architecture/current-platform-topology.md"): re.compile(
        r"Last validated against the live local cluster on `\d{4}-\d{2}-\d{2}`\."
    ),
    Path("docs/runbooks/access-platform-uis.md"): re.compile(
        r"Last access verification update: `\d{4}-\d{2}-\d{2}`\."
    ),
}

WORKFLOW_REQUIRED_HEADINGS = {
    "## Purpose",
    "## Trigger",
    "## Inputs Or Parameters",
    "## Permissions And Approval Surface",
    "## Outputs And Side Effects",
    "## Operator Evidence",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_date_markers(errors: list[str], repo_root: Path) -> None:
    for relative_path, pattern in DATE_PATTERNS.items():
        path = repo_root / relative_path
        if not path.exists():
            errors.append(f"{path}: missing required operational doc")
            continue
        text = read_text(path)
        if not pattern.search(text):
            errors.append(f"{path}: missing required freshness marker")


def validate_workflow_docs(errors: list[str], repo_root: Path) -> None:
    workflow_dir = repo_root / ".github" / "workflows"
    docs_dir = repo_root / "docs" / "workflows"

    if not workflow_dir.exists():
        errors.append(f"{workflow_dir}: missing workflow directory")
        return
    if not docs_dir.exists():
        errors.append(f"{docs_dir}: missing workflow docs directory")
        return

    for workflow_path in sorted(workflow_dir.glob("*.yaml")):
        doc_path = docs_dir / f"{workflow_path.stem}.md"
        if not doc_path.exists():
            errors.append(f"{doc_path}: missing workflow doc for {workflow_path.name}")
            continue

        text = read_text(doc_path)
        missing = sorted(heading for heading in WORKFLOW_REQUIRED_HEADINGS if heading not in text)
        if missing:
            errors.append(f"{doc_path}: missing workflow doc headings: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate workflow docs coverage and operational doc freshness markers."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    errors: list[str] = []

    validate_date_markers(errors, repo_root)
    validate_workflow_docs(errors, repo_root)

    if errors:
        raise SystemExit("\n".join(errors))

    print("platform-engineering operational docs valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
