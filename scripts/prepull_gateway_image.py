#!/usr/bin/env python3
import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml


ENV_TO_NAMESPACE = {
    "stage": "openclaw-stage",
    "prod": "openclaw",
}


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        check=True,
        capture_output=True,
    )


def image_ref_from_values(values: dict) -> str:
    image = values["image"]
    repository = image["repository"]
    digest = image.get("digest")
    if digest:
        return f"{repository}@{digest}"
    return f"{repository}:{image['tag']}"


def build_manifest(name: str, namespace: str, image_ref: str) -> str:
    return textwrap.dedent(
        f"""\
        apiVersion: apps/v1
        kind: DaemonSet
        metadata:
          name: {name}
          namespace: {namespace}
          labels:
            app.kubernetes.io/name: gateway-image-prepull
            openclaw.io/prepull-target: {name}
        spec:
          selector:
            matchLabels:
              app.kubernetes.io/name: gateway-image-prepull
              openclaw.io/prepull-target: {name}
          template:
            metadata:
              labels:
                app.kubernetes.io/name: gateway-image-prepull
                openclaw.io/prepull-target: {name}
            spec:
              terminationGracePeriodSeconds: 0
              containers:
                - name: warm
                  image: {image_ref}
                  imagePullPolicy: IfNotPresent
                  command: ["sh", "-lc", "trap 'exit 0' TERM INT; sleep infinity & wait"]
                  resources:
                    requests:
                      cpu: 10m
                      memory: 32Mi
                    limits:
                      cpu: 50m
                      memory: 128Mi
        """
    )


def prepull_image(
    environment: str,
    *,
    image_ref: str,
    kubectl: str = "k3s kubectl",
    timeout: str = "90m",
) -> str:
    namespace = ENV_TO_NAMESPACE[environment]
    image_identity = image_ref.rsplit("@", 1)[-1] if "@" in image_ref else image_ref.rsplit(":", 1)[-1]
    image_identity = image_identity.replace("sha256:", "")[:12]
    name = f"openclaw-gateway-prepull-{environment}-{image_identity}"
    manifest = build_manifest(name, namespace, image_ref)
    kubectl_cmd = kubectl.split()

    print(f"Pre-pulling {image_ref} into namespace {namespace}", file=sys.stderr)
    run([*kubectl_cmd, "apply", "-f", "-"], input_text=manifest)
    try:
        run(
            [
                *kubectl_cmd,
                "-n",
                namespace,
                "rollout",
                "status",
                f"daemonset/{name}",
                f"--timeout={timeout}",
            ]
        )
        return image_ref
    finally:
        run([*kubectl_cmd, "-n", namespace, "delete", "daemonset", name, "--ignore-not-found"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-pull the target gateway image onto every schedulable node before rollout."
    )
    parser.add_argument("environment", choices=sorted(ENV_TO_NAMESPACE))
    parser.add_argument(
        "--image-ref",
        help="Explicit image reference to warm, for example ghcr.io/org/repo@sha256:...",
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    parser.add_argument(
        "--kubectl",
        default="k3s kubectl",
        help="kubectl command prefix used to access the cluster",
    )
    parser.add_argument(
        "--timeout",
        default="90m",
        help="How long to wait for the daemonset rollout",
    )
    args = parser.parse_args()

    image_ref = args.image_ref
    if not image_ref:
        env_root = args.repo_root / "environments" / args.environment
        values = load_yaml(env_root / "values" / "openclaw-gateway.yaml")
        image_ref = image_ref_from_values(values)

    print(
        prepull_image(
            args.environment,
            image_ref=image_ref,
            kubectl=args.kubectl,
            timeout=args.timeout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
