"""Synthetic behavior-test inputs; never runtime configuration or acceptance evidence."""
from pathlib import Path
import shutil
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "scripts/fixtures/governed-ai"


def contract_source(relative_path: Path | str) -> Path:
    fixture = FIXTURE_ROOT / relative_path
    return fixture if fixture.is_file() else REPO_ROOT / relative_path


def prepare_contracts(root: Path) -> None:
    shutil.copytree(REPO_ROOT / "security", root / "security", dirs_exist_ok=True)
    shutil.copytree(FIXTURE_ROOT / "security", root / "security", dirs_exist_ok=True)
    (root / "docs").symlink_to(REPO_ROOT / "docs", target_is_directory=True)
    (root / "dev-integration").symlink_to(REPO_ROOT / "dev-integration", target_is_directory=True)


def fixture_selections() -> dict:
    # Import after callers install the runtime module path.
    from model_profile_resolver import resolve_model_profile_registry
    with tempfile.TemporaryDirectory(prefix="synthetic-governed-ai-") as directory:
        root = Path(directory)
        prepare_contracts(root)
        return resolve_model_profile_registry(
            root / "security/governed-ai-model-profiles.yaml",
            root / "security/governed-ai-access-plane.yaml",
            environment="dev-integration",
        )
