# Record Gateway Image

Use this after the governed gateway image build publishes a new tag and digest.

## Purpose

Update the environment contract and the two runtime-facing values files in one
pass, without hand-editing YAML.

## Command

Example for `prod`:

```bash
TAG="$(python scripts/compute_gateway_publish_tag.py prod)"

python scripts/record_gateway_image.py prod \
  --tag "$TAG" \
  --digest sha256:replace-with-build-output
```

This updates:

- `environments/prod/versions.yaml`
- `environments/prod/values/openclaw-gateway.yaml`
- `environments/prod/values/platform-version.yaml`

## Required Follow-up

After recording the image metadata, validate the contract:

```bash
python scripts/validate_environment_contract.py prod
```

Then commit the resulting source-of-truth change and let Argo CD reconcile the
updated digest normally.
