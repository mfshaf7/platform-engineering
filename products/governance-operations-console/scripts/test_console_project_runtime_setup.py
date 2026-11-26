"""Project setup checks using an exact real Git tree and private owner state."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Barrier
import unittest

from platform_operation_provider import OperationStore
from console_project_runtime_setup import CommittedSource, ProjectSetupError, ProjectSetupStore


class ProjectRuntimeSetupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Project Setup Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "app").mkdir()
        (self.repo / "app/index.html").write_text("<main>Admitted app</main>")
        (self.repo / "app/package.json").write_text(
            '{"scripts":{"build":"touch ../executed","start":"touch ../executed"}}',
        )
        (self.repo / "app/package-lock.json").write_text('{"lockfileVersion":3,"packages":{}}')
        (self.repo / "docs.md").write_text("A separately admitted workspace dependency.")
        self.commit = self.commit_all("Admitted source")
        self.operations = OperationStore(self.root / "owner-state")
        self.store = ProjectSetupStore(self.operations)
        self.scope = {
            "installation_id": "installation:test", "project_custody_ref": "project:test",
            "repository_id": 1234, "app_root": "app", "dependency_paths": ["docs.md"],
            "environment_ref": "devint:local",
        }

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.repo, stdout=subprocess.PIPE, check=True).stdout.decode().strip()

    def commit_all(self, message):
        self.git("add", "--all")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def save(self, *, recipe="node-frontend", revision=None, app_root="app", scope=None, commit=None):
        return self.store.save(
            self.scope if scope is None else scope, requested_app_root=app_root,
            recipe_id=recipe, expected_revision=revision, source=CommittedSource(self.repo, commit or self.commit),
        )

    def test_canonical_source_is_inspected_without_project_execution(self):
        (self.repo / "app/package.json").write_text("changed in the working tree")
        saved = self.save()
        self.assertEqual(saved["inspection"], {"base_commit": self.commit, "recipe_id": "node-frontend"})
        self.assertEqual(self.save(revision=saved["setup"]["configuration_revision"]), saved)
        self.assertEqual(ProjectSetupStore(OperationStore(self.operations.root)).read(self.scope), saved)
        self.assertEqual({file.stat().st_mode & 0o777 for file in self.store.directory.iterdir()}, {0o600})
        self.assertFalse((self.repo / "executed").exists())

    def test_unauthorized_root_and_unsupported_recipes_preserve_current_setup(self):
        approved = self.save(recipe="static")
        revision = approved["setup"]["configuration_revision"]
        with self.assertRaisesRegex(ProjectSetupError, "differs from the current source authorization"):
            self.save(revision=revision, app_root=".")
        with self.assertRaisesRegex(ProjectSetupError, "supported Dev Integration recipe"):
            self.save(revision=revision, recipe="arbitrary-command")
        with self.assertRaisesRegex(ProjectSetupError, "missing or unsupported"):
            self.save(revision=revision, scope={**self.scope, "dependency_paths": ["missing"]})
        with self.assertRaisesRegex(ProjectSetupError, "needs review"):
            self.store.read({**self.scope, "repository_id": 5678})
        self.assertEqual(self.store.read(self.scope), approved)

    def test_paired_node_setup_requires_frontend_and_api_start_scripts(self):
        with self.assertRaisesRegex(ProjectSetupError, "needs a start:frontend"):
            self.save(recipe="node-frontend-api")
        package = self.repo / "app/package.json"
        manifest = json.loads(package.read_text())
        manifest["scripts"].update({"start:frontend": "node frontend.mjs", "start": "node api.mjs"})
        package.write_text(json.dumps(manifest))
        saved = self.save(recipe="node-frontend-api", commit=self.commit_all("Declare both runtime roles"))
        self.assertEqual(saved["setup"]["recipe_id"], "node-frontend-api")
        self.assertFalse((self.repo / "executed").exists())

    def test_linked_or_malformed_manifests_do_not_become_setup(self):
        package = self.repo / "app/package.json"
        package.unlink()
        package.symlink_to("../docs.md")
        with self.assertRaisesRegex(ProjectSetupError, "manifest and lockfile"):
            self.save(commit=self.commit_all("Linked manifest"))
        package.unlink()
        package.write_text('{"scripts": {}, "scripts": {"build": "false"}}')
        with self.assertRaisesRegex(ProjectSetupError, "not valid JSON"):
            self.save(commit=self.commit_all("Ambiguous manifest"))
        with self.assertRaisesRegex(ProjectSetupError, "exact Git checkout"):
            CommittedSource(self.repo / "app", self.commit)
        self.assertIsNone(self.store.read(self.scope))

    def test_two_writers_from_the_same_revision_cannot_both_apply(self):
        first = self.save()
        revision = first["setup"]["configuration_revision"]
        start = Barrier(2)

        def update(recipe):
            start.wait(timeout=5)
            try:
                return self.save(recipe=recipe, revision=revision)
            except ProjectSetupError as error:
                self.assertIn("changed", str(error))
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ["static", "no-runtime"]))
        self.assertEqual([result for result in results if result], [self.store.read(self.scope)])
        self.assertEqual(self.store.read(self.scope)["revision"], 2)

    def test_docs_setup_does_not_require_app_runtime_files(self):
        scope = {**self.scope, "app_root": ".", "dependency_paths": []}
        saved = self.save(recipe="no-runtime", app_root=".", scope=scope)
        self.assertEqual(saved["setup"]["recipe_id"], "no-runtime")
        self.assertFalse((self.repo / "executed").exists())


if __name__ == "__main__":
    unittest.main()
