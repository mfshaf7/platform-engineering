#!/usr/bin/env python3
"""Qualify the pinned chart's in-cluster frontend addresses for gRPC clients."""

import argparse
import sys

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("namespace")
    namespace = parser.parse_args().namespace
    short_addresses = {"temporal-frontend:7233", f"temporal-frontend.{namespace}.svc:7233"}
    full_address = f"temporal-frontend.{namespace}.svc.cluster.local:7233"

    resources = [item for item in yaml.safe_load_all(sys.stdin) if item]
    for resource in resources:
        template = resource.get("spec", {}).get("template", {}).get("spec", {})
        for container in template.get("initContainers", []) + template.get("containers", []):
            for variable in container.get("env", []):
                if (
                    variable["name"] in {"TEMPORAL_ADDRESS", "TEMPORAL_CLI_ADDRESS"}
                    and variable.get("value") in short_addresses
                ):
                    variable["value"] = full_address

    yaml.safe_dump_all(resources, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()
