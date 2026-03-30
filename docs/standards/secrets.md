# Secrets Standard

- plaintext secrets must not be committed to Git
- runtime secrets should be delivered through External Secrets Operator
- Vault is the default cluster secret source of truth
- host-side secrets should come from approved secret sources or local secure configuration
- secret rotation should not require ad hoc code edits
