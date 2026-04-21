# Complete Delivery Work Item

## Purpose

Mark one delivery work item complete through the supported operator surface and
record explicit completion proof in the work item itself.

Use this when:

- a child delivery item is truly finished
- the work item should move to `done`
- the completion must remain attributable and reviewable from the OpenProject
  record itself

This workflow is intentionally separate from
[update-delivery-work-item.md](update-delivery-work-item.md).

`done` is not treated as a generic status edit. It is a completion-attestation
step that must also write:

- `Completion Summary`
- `Changed Surfaces`
- `Test Result Evidence`
- `Validation Evidence`

When the work produced a real test output or report file, this workflow should
also attach that artifact to the work item record.

Section intent:

- `Completion Summary`
  - outcome only
  - do not duplicate the file or endpoint inventory here
- `Changed Surfaces`
  - concrete changed files, contracts, docs, endpoints, or runtime surfaces
- `Test Result Evidence`
  - short statement of the actual test result, plus any attached raw artifact
- `Validation Evidence`
  - broader validation commands and checks beyond the discrete test result

## Command

Run from `platform-engineering/`:

```bash
make openproject-complete-delivery-work-item \
  TARGET_WORK_PACKAGE_ID=55 \
  COMPLETION_SUMMARY="Implemented the first broker-owned execution summary read surface." \
  CHANGED_SURFACES="- operator-orchestration-service/src/openproject-client.js\n- operator-orchestration-service/src/delivery-service.js\n- operator-orchestration-service/src/app.js" \
  TEST_RESULT_EVIDENCE="- PASS: npm test completed with all suites green\n- Attached artifact: operator-orchestration-service-npm-test.txt" \
  TEST_RESULT_ARTIFACT_FILE=/abs/path/operator-orchestration-service-npm-test.txt \
  TEST_RESULT_ARTIFACT_DESCRIPTION="Raw npm test output captured at completion time." \
  VALIDATION_EVIDENCE="- npm test\n- validate_governance_docs.py\n- validate_change_record_requirement.py --against-ref origin/main\n- git diff --check" \
  COMPLETION_NOTE="Recorded completion after source tests and contract/doc updates passed."
```

For longer evidence bodies, use the file-backed form:

```bash
make openproject-complete-delivery-work-item \
  TARGET_WORK_PACKAGE_ID=55 \
  COMPLETION_SUMMARY_FILE=/abs/path/completion-summary.md \
  CHANGED_SURFACES_FILE=/abs/path/changed-surfaces.md \
  TEST_RESULT_EVIDENCE_FILE=/abs/path/test-result-evidence.md \
  VALIDATION_EVIDENCE_FILE=/abs/path/validation-evidence.md
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-complete-delivery-work-item \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_WORK_PACKAGE_ID=55 \
  COMPLETION_SUMMARY="..." \
  CHANGED_SURFACES="..." \
  TEST_RESULT_EVIDENCE="..." \
  VALIDATION_EVIDENCE="..."
```

## Rules

- `COMPLETION_SUMMARY` or `COMPLETION_SUMMARY_FILE` is required
- `CHANGED_SURFACES` or `CHANGED_SURFACES_FILE` is required
- `TEST_RESULT_EVIDENCE` or `TEST_RESULT_EVIDENCE_FILE` is required
- `VALIDATION_EVIDENCE` or `VALIDATION_EVIDENCE_FILE` is required
- inline and file forms for the same field are mutually exclusive
- `TEST_RESULT_ARTIFACT_FILE` is optional and should be used when a real test
  output or report file exists
- active blocker state must already be cleared before completion
- the helper sets:
  - `status = done`
  - `remaining work = 0`
  - `% complete = 100`
- the helper leaves `work` intact as the estimate-of-record

If some evidence dimension is genuinely not applicable, say that explicitly in
the supplied value instead of leaving it empty. For example:

- `TEST_RESULT_EVIDENCE="Not applicable. This design-only task had no discrete test surface beyond the validations below."`

## Expected Outcome

- the work item is `done`
- `remaining work` is `0`
- `% complete` is `100`
- the description contains explicit completion-evidence sections
- the description contains an explicit `Test Result Evidence` section
- an optional completion note is written through the supported note path
- when `TEST_RESULT_ARTIFACT_FILE` is supplied, the work item has an attached
  artifact in the OpenProject UI

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target work item
- confirm `Status = done`
- confirm `Remaining work = 0`
- confirm `% complete = 100`
- confirm the description contains:
  - `Completion Summary`
  - `Changed Surfaces`
  - `Test Result Evidence`
  - `Validation Evidence`
- if `TEST_RESULT_ARTIFACT_FILE` was supplied, confirm the attachment is
  visible on the work item

If `COMPLETION_NOTE` was supplied, confirm the note appears either in the
activity history or in the `Operator work notes` description section.

## Related References

- [update-delivery-work-item.md](update-delivery-work-item.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [close-delivery-initiative.md](close-delivery-initiative.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
