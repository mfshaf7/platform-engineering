# Stage Environment

This directory holds the staged Argo CD overlays and application set for the
non-production rehearsal environment.

The stage environment is intended to:

- validate Argo CD reconciliation
- validate Helm values against a second namespace set
- rehearse image/version promotion before touching `prod`

Stage is suspended by default in source control. Bring it up only when you are
actively testing a candidate change, then suspend it again after promotion.

Available stage components:

- `gateway`
- `secrets`
- `version`
- `observability`
- `dashboards`

Dependency rules:

- resuming `gateway` also resumes `secrets`
- resuming `dashboards` also resumes `observability`
- suspending `secrets` also suspends `gateway`
- suspending `observability` also suspends `dashboards`

Normal gateway validation should resume only `gateway,version`, which produces
an active stage lane of `gateway + secrets + version`.

Promotion policy:

- stage is off by default
- every stage lifecycle change resets promotion readiness to `pending` or `inactive`
- every stage lifecycle change also resets stage verification to `pending`
- prod promotion is blocked until the current stage candidate is explicitly approved
- the approval must still match `environments/stage/release-candidate.yaml` and `environments/stage/verification.yaml` at promotion time
- after a successful prod promotion, suspend stage again unless there is an explicit reason to keep testing
