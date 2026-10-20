# Synthetic model-profile behavior fixtures

Frozen public, credential-free inputs for policy, resolver and lifecycle unit
tests, initially copied from Platform commit `84bf3cb`. These are not deployed,
operating evidence, or a claim that any profile is currently active. Runtime
launchers always read canonical `security/` configuration, never this folder.

Behavior tests need deliberate active/inactive profiles independent of later
operator lifecycle decisions. Actual source is separately checked by the native
profile validator and generic rendered-registry conformance. The lifecycle
matrix uses the real mutator, validator, resolver, launcher and policy in a
disposable copy, including retirement and all-inactive launch refusal.
