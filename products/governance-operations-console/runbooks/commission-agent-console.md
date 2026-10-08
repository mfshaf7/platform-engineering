# Commission Agent Console

This is the primary Platform operator surface for the Agent Console
dev-integration boundary. It reuses the registered `refinement-catalog`
composition; it does not create another runtime or grant stage or production
authority.

Validate source admission before activation:

```bash
make governance-console-agent-console ACTION=validate
```

Do not enable the OOS and CGG Agent Console profile bindings until Security
work item #1248 has accepted the exact CGG, OOS, Platform, Console, and
Workspace Governance revisions under
`gate:agent-console-operating-acceptance`. After that review and the matching
Workspace Governance composition bindings have landed, reconcile the existing
composition:

```bash
make devint-up COMPOSITION=refinement-catalog
make devint-status COMPOSITION=refinement-catalog
```

Acquire both positive and negative live evidence through the bounded OOS,
CGG, and governed AI path:

```bash
make governance-console-agent-console ACTION=verify-operating
```

The verifier opens temporary loopback port-forwards, reads the existing
operator-private Console caller binding without printing it, creates and
closes one synthetic Agent Console session, verifies the governed model audit,
proves an unauthorized task/caller/schema request is denied, and writes a
credential-free receipt under
`~/.local/state/platform-engineering/agent-console/agent-console/receipts/`.

Rollback uses the existing composition lifecycle:

```bash
make devint-down COMPOSITION=refinement-catalog
make devint-status COMPOSITION=refinement-catalog
```

Rollback must remove the OOS and CGG Agent Console credentials. Preserve the
credential-free operating receipt for Review Packet evidence.
