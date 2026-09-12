# Prototype Closure Identity

The [identity definition](../../../security/prototype-closure-identity.yaml) is
the Platform source for a future, dedicated Prototype Closure GitHub App. It is
**defined but inactive**. No App, installation, key, token, runtime mount, or
closure write is authorized by this change.

Validate the definition locally:

```sh
python3 scripts/prototype_closure_identity.py
python3 scripts/test_prototype_closure_identity.py
```

The eventual App is restricted to the Studio repository, a closure branch,
`prototypes.yaml`, and `records/prototype-closures/**`. It cannot borrow the
Landing or Maturity identity, mutate prototype source content, write a durable
owner repository, merge to `main`, or create a repository. OOS is the intended
consumer in the accepted-idea-delivery `dev-integration` profile; it has no
enabled Closure workflow or credential projection yet.

Security's implementation review in #1106 must accept the exact definition
before Studio source work. Normal availability requires #1140. Platform may
commission and project the identity only through #1107 after those gates and
the required provider, session, rotation, rollback, and revocation evidence.
Revocation targets only exact active incubation resources; an absent resource
must be reported as absent, not described as revoked. Landing and Maturity
identities remain unchanged.
