# Secrets Standard

- plaintext secrets must not be committed to Git
- runtime secrets should be delivered through External Secrets Operator
- host-side secrets should come from approved secret sources or local secure configuration
- secret rotation should not require ad hoc code edits
