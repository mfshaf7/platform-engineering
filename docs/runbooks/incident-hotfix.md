# Incident Hotfix Runbook

1. record the incident and emergency change
2. make the minimum required live remediation
3. backport the fix to the canonical source repo
4. rebuild and publish the approved artifact
5. update the platform environment pin
6. reconcile runtime back to approved state
7. close the incident only after drift returns to `green`
