#!/usr/bin/env python3
import argparse
import hashlib
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute the governed gateway publish tag for an environment from versions.yaml."
    )
    parser.add_argument("environment", help="Environment name, for example prod or stage")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root",
    )
    args = parser.parse_args()

    versions_path = args.repo_root / "environments" / args.environment / "versions.yaml"
    with versions_path.open("r", encoding="utf-8") as fh:
      data = yaml.safe_load(fh)

    source_bundle = "|".join(
        [
            data["environment"],
            data["sourceRepos"]["telegramEnhanced"]["commit"],
            data["sourceRepos"]["hostBridge"]["commit"],
            data["sourceRepos"]["isolatedDeployment"]["commit"],
            data["gateway"]["build"]["baseImage"],
            data["gateway"]["build"]["dockerfile"],
        ]
    )
    source_bundle_ref = hashlib.sha256(source_bundle.encode("utf-8")).hexdigest()[:12]
    publish_tag = f"{data['gateway']['publish']['tagPrefix']}-{source_bundle_ref}"
    print(publish_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
