# Bootstrap Transit Vault With Temporary Windows Trust Root

## Purpose

This runbook defines the temporary fully automated workstation path:

- Windows protected secret storage
- `Platform-Transit` dedicated transit Vault
- `Platform-Core` workload Vault using `seal "transit"`

## Scope

This runbook is the temporary local-budget model only.

It is not the final enterprise-grade trust-root design.

## Trust chain

The temporary trust chain is:

1. Windows logon/startup bootstrap runs
2. Windows releases a TPM/DPAPI-protected secret for the transit Vault only
3. `Platform-Transit` starts and unseals transit Vault
4. `Platform-Core` starts
5. workload Vault auto-unseals through transit
6. `make verify-restart-survival` runs

## Required boundary

Windows may help unseal transit Vault.

Windows must not directly unseal the workload Vault.

That boundary is what keeps the temporary model cleaner than a direct
host-to-workload unseal shortcut.

## Required implementation pieces

1. a clean `Platform-Transit` distro
2. transit Vault service provisioned there
3. transit Vault initialized and configured with the transit secrets engine
4. workload Vault configured with `seal "transit"`
5. Windows bootstrap that can:
   - start `Platform-Transit`
   - release the protected transit-only secret
   - trigger transit Vault unseal
   - start `Platform-Core`
   - verify restart survival

## Source-backed bootstrap artifacts

The governed bootstrap now expects two generated Windows artifacts:

1. `openclaw-host-stack-windows-bootstrap.ps1`
2. `openclaw-transit-vault-unseal.ps1`

Render them with:

```bash
ansible-playbook ansible/playbooks/render-windows-bootstrap.yml
```

The transit helper is intentionally separate from the host bootstrap so the
Windows trust-rooted secret handling stays narrow and auditable.

## Secret-handling rule

Use Windows protected storage only for the transit Vault unseal path.

Preferred order:

1. TPM-backed Windows key protection
2. DPAPI-backed Windows protection
3. Credential Manager only as a wrapper around one of the above

Do not:

- store plaintext recovery keys in Git
- place plaintext unseal keys in scheduled-task arguments
- reuse the same host secret as a direct workload Vault unseal credential

## Platform note

This workstation currently reports a usable TPM. That makes TPM-backed
protection the preferred temporary implementation rather than plain DPAPI-only
release.

The intended Windows-side implementation is:

1. create a non-exportable certificate using `Microsoft Platform Crypto Provider`
2. encrypt the transit Vault init bundle with `Protect-CmsMessage`
3. store only the encrypted CMS bundle on disk
4. let `openclaw-transit-vault-unseal.ps1` decrypt it with
   `Unprotect-CmsMessage`
5. use the recovered transit unseal keys only to unseal `Platform-Transit`

Example certificate bootstrap:

```powershell
$cert = New-SelfSignedCertificate `
  -Subject 'CN=Platform Transit Vault Unseal' `
  -CertStoreLocation 'Cert:\CurrentUser\My' `
  -Provider 'Microsoft Platform Crypto Provider' `
  -KeyAlgorithm RSA `
  -KeyLength 2048 `
  -KeyExportPolicy NonExportable `
  -KeyUsage KeyEncipherment, DataEncipherment `
  -Type DocumentEncryptionCert
```

Example bundle encryption after the one-time transit Vault init:

```powershell
New-Item -ItemType Directory -Force 'C:\Users\Sevensoul\AppData\Local\OpenClaw\transit-vault' | Out-Null
Protect-CmsMessage `
  -To $cert `
  -Path .\transit-init.json `
  -OutFile 'C:\Users\Sevensoul\AppData\Local\OpenClaw\transit-vault\transit-init.cms'
```

After the CMS bundle is verified, remove the plaintext init file from the
Windows side and keep the original operator recovery material outside Git.

## Operational modes

### Warm transit

- transit Vault stays online
- best fit for unattended restart recovery

### Cold transit

- transit Vault is started only for the unseal window
- can still support automated startup if Windows starts and unseals it first
- may be stopped again after the workload Vault is confirmed unsealed

## Verification

The platform is only considered recovered when:

```bash
make verify-restart-survival
```

passes after the automated chain completes.

## Transit init bundle format

The encrypted JSON bundle should contain the standard Vault init output fields,
including at least one of:

- `unseal_keys_b64`
- `unseal_keys_hex`

The helper expects at least three keys so it can satisfy the current Shamir
threshold for the dedicated transit Vault.

## Migration note

This model should remain clearly labeled as temporary until replaced by a
stronger external trust root.
