# Security policy

## Supported version

Security fixes target the latest `0.x` release on the default branch.

## Reporting

Do not open a public issue for suspected credentials, private infrastructure details,
benchmark-answer leakage, sandbox escape, or unauthorized side effects. Use GitHub private
vulnerability reporting for this repository.

Include the affected commit, minimal reproduction, impact, and whether any real data or
credential was exposed. Do not include active secrets in the report.

## Before making a repository public

This harness was designed for a fresh public history. Keep the production `epic-intel`
repository private. Before publishing or importing additional material:

1. rotate every credential ever written to production documentation or Git history;
2. scan every branch, tag, deleted commit, and large object with at least two secret
   scanners;
3. exclude deployment IPs, hostnames, usernames, paths, incident reports, `.env` files,
   database dumps, logs, and screenshots with operational metadata;
4. copy only audited generic code into this clean repository;
5. run `scripts/security_scan.py` and review its output manually.

Removing a secret from the current tree does not remove it from history. Treat a committed
secret as disclosed and rotate it.

