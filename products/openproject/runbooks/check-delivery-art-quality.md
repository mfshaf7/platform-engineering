# Check Delivery ART Quality

## Purpose

Keep the established Platform command for checking Delivery ART quality while
using `operator-orchestration-service` as the only ART semantic evaluator.

This command is a broker-projection adapter. It does not load ART taxonomy,
narrative, blocker, lineage, planning, or closeout rules locally.

## Read Modes

The command performs exactly one broker read per invocation:

- with `TARGET_EPIC_ID`, it reads
  `GET /v1/delivery-initiatives/{delivery_id}/review-pack`
- without `TARGET_EPIC_ID`, it reads
  `GET /v1/delivery-session/workflow-health`

The scoped mode reports the OOS-owned `quality_drift` projection unchanged and
fails when that projection contains findings. The unscoped mode reports the
OOS-owned roadmap and PM2 projection-health result unchanged and follows its
`healthy` decision.

Platform remains responsible for OpenProject runtime, compatible views, and
projection repair. OOS remains responsible for ART workflow meaning and
semantic validation.

## Normal Sequence

For active work, use:

1. broker workflow health
2. scoped broker-projected quality
3. Platform view repair only when projection drift exists

```bash
cd /home/mfshaf7/projects/operator-orchestration-service
npm run art -- workflow-health

cd /home/mfshaf7/projects/platform-engineering
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=698
```

For a portfolio projection check, omit `TARGET_EPIC_ID`:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7
```

## Result

The command prints one JSON report containing:

- the source broker workflow id
- scoped initiative or portfolio-projection mode
- broker-projected quality or projection-health data
- compact issue counts
- one trusted `healthy` result

Exit status is:

- `0` when the source broker projection is healthy
- `1` when the source broker projection reports quality or projection drift
- non-zero with an error when the broker is unavailable or returns an
  unexpected contract

The wrapper does not repair ART state. Use broker mutation commands for ART
workflow corrections and
`make openproject-sync-delivery-art-views` for OpenProject projection repair.

## Related References

- [check-delivery-art-workflow-health.md](check-delivery-art-workflow-health.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [openproject-platform-admin-surface.md](openproject-platform-admin-surface.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
