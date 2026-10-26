#!/usr/bin/env python3
"""Artifact integrity, isolated source export and build custody regression cases."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import console_frontend_artifact as frontend
import console_cross_domain_activation as activation


class FrontendArtifactTests(unittest.TestCase):
    def artifact(self, root):
        files = {"server.js": "// synthetic server", ".next/BUILD_ID": "fixture",
                 "package.json": "{}", ".next/static/test.js": "// synthetic static"}
        for name, body in files.items():
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(body)
        manifest = {"schema_version": 1, "source_revision": "a" * 40,
                    "node_version": "v22.0.0", "files": frontend.inventory(root)}
        (root / frontend.MANIFEST).write_text(json.dumps(manifest))
        return manifest

    def test_complete_artifact_binds_exact_source_toolchain_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.artifact(root)
            self.assertEqual(len(frontend.validate_artifact(root, "a" * 40, "v22.0.0")["files"]), 4)
            for revision, version in [("b" * 40, "v22.0.0"), ("a" * 40, "v22.1.0")]:
                with self.assertRaises(frontend.FrontendArtifactError):
                    frontend.validate_artifact(root, revision, version)
            (root / "server.js").write_text("changed source")
            with self.assertRaises(frontend.FrontendArtifactError):
                frontend.validate_artifact(root, "a" * 40, "v22.0.0")

    def test_missing_static_files_extra_code_and_private_environment_fail_closed(self):
        for mode in ["missing-static", "extra-code", "environment", "symlink"]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.artifact(root)
                if mode == "missing-static": (root / ".next/static/test.js").unlink()
                if mode == "extra-code": (root / "injected.js").write_text("unreviewed")
                if mode == "environment": (root / ".env.local").write_text("SYNTHETIC=private")
                if mode == "symlink": (root / "link").symlink_to(root / "server.js")
                with self.assertRaises(frontend.FrontendArtifactError):
                    frontend.validate_artifact(root, "a" * 40, "v22.0.0")

    def test_only_framework_runtime_cache_is_mutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.artifact(root)
            (root / ".next/cache").mkdir(); (root / ".next/cache/data").write_text("runtime cache")
            route = root / ".next/server/route-cache/APP_PAGE/synthetic"
            route.mkdir(parents=True); (route / "index.html").write_text("cached response")
            (route / "index.meta").write_text("{}")
            (route / "index.rsc").write_text("cached flight data")
            frontend.validate_artifact(root, "a" * 40, "v22.0.0")
            (route / "injected.js").write_text("unexpected code")
            with self.assertRaises(frontend.FrontendArtifactError):
                frontend.validate_artifact(root, "a" * 40, "v22.0.0")

    def test_build_does_not_inherit_live_credentials_or_debug_options(self):
        with patch.dict(os.environ, {"OOS_CALLER_SECRET": "synthetic-secret", "NODE_OPTIONS": "--inspect", "NEXT_PUBLIC_SECRET": "synthetic-private"}):
            env = frontend.build_environment()
        self.assertNotIn("OOS_CALLER_SECRET", env)
        self.assertNotIn("NEXT_PUBLIC_SECRET", env)
        self.assertEqual(env["NODE_OPTIONS"], "--max-old-space-size=4096")

    def test_failed_build_kills_compiler_process_group(self):
        with patch.object(frontend.subprocess, "Popen") as popen, patch.object(frontend.os, "killpg") as kill:
            process = popen.return_value; process.pid = 1234; process.wait.side_effect = [subprocess.TimeoutExpired("npm", 900), 0]
            with self.assertRaises(frontend.FrontendArtifactError):
                frontend.build_command(["npm", "run", "build"], Path("/synthetic"), {}, None)
            kill.assert_called_once_with(1234, frontend.signal.SIGKILL)
            self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_prepare_exports_only_committed_source_and_leaves_owner_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "owner"; source.mkdir()
            def git(*args):
                return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()
            git("init", "-b", "main")
            (source / ".gitignore").write_text(".env.local\n.next/\n")
            (source / "package-lock.json").write_text("{}")
            (source / "package.json").write_text("{}")
            git("add", "."); git("-c", "user.name=Synthetic fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
            revision = git("rev-parse", "HEAD")
            (source / ".env.local").write_text("SYNTHETIC_PRIVATE=do-not-export")
            (source / ".next").mkdir(); (source / ".next/served.txt").write_text("original runtime")
            seen = []
            def build(args, exported, env, log):
                self.assertNotEqual(exported, source)
                self.assertFalse((exported / ".env.local").exists())
                seen.append(args)
                if args[-1] == "build":
                    target = exported / ".next/standalone"; target.mkdir(parents=True)
                    self.artifact(target)
                    (target / frontend.MANIFEST).unlink()
                    static = exported / ".next/static"; static.mkdir(); (static / "test.js").write_text("// original static")
            with patch.object(frontend, "toolchain", return_value=("/tools/node", "/tools/npm", "v22.0.0")), patch.object(frontend, "build_command", side_effect=build):
                artifact = frontend.prepare(source, revision, root / "artifacts")
                frontend.validate_artifact(artifact, revision, "v22.0.0")
                self.assertEqual(frontend.prepare(source, revision, root / "artifacts"), artifact)
            self.assertEqual(len(seen), 2)
            self.assertEqual((source / ".next/served.txt").read_text(), "original runtime")
            self.assertEqual(git("status", "--porcelain"), "")
            self.assertFalse((artifact / ".git").exists())

    @unittest.skipUnless(shutil.which("node"), "Node is required for real process-title readback")
    def test_status_uses_real_process_cwd_executable_and_environment_after_node_renames_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.artifact(root)
            (root / "server.js").write_text("process.title='next-server (synthetic)'; setTimeout(()=>{}, 30000);\n")
            manifest = json.loads((root / frontend.MANIFEST).read_text())
            manifest["files"] = frontend.inventory(root)
            (root / frontend.MANIFEST).write_text(json.dumps(manifest))
            node = shutil.which("node")
            env = dict(frontend.build_environment(), NODE_ENV="production", HOSTNAME="127.0.0.1", PORT="3317", NODE_OPTIONS="--max-old-space-size=2048")
            process = subprocess.Popen([node, str(root / "server.js")], cwd=root, env=env)
            try:
                time.sleep(0.15)
                reply = subprocess.CompletedProcess([], 0, stdout=f"MainPID={process.pid}\nWorkingDirectory={root}\nMemoryHigh={3*1024**3}\nMemoryMax={4*1024**3}\n")
                def response(args, **kwargs):
                    return subprocess.CompletedProcess([], 0, stdout=str(process.pid)) if "--value" in args else reply
                with patch.object(activation, "run", side_effect=response), patch.object(activation, "console_source_revision", return_value="a"*40), patch.object(frontend, "toolchain", return_value=(node, "npm", "v22.0.0")), patch.object(frontend, "artifact_path", return_value=root):
                    self.assertEqual(activation.frontend_runtime_status({"console": {"port": 3317}})["mode"], "standalone")
                    with self.assertRaises(activation.ActivationError):
                        activation.frontend_runtime_status({"console": {"port": 4317}})
            finally:
                process.terminate(); process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
