# Reviewed secret-scan false positives

The October 10 integration extends Gitleaks 8.30.1's default rules with exact
public identifier and exact file-path pairs in .gitleaks.toml. Each exception
applies only to generic-api-key; all other rules remain active. The retained
scanner-baseline.json is unchanged.

The merge-history scan added 50 findings beyond that baseline. Source review
established that they are public identifiers:

- 32 occurrences of transaction UUIDs in the two explicitly synthetic_only
  Collector backend fixture captures.
- Eight historical occurrences of the same mobile router test transaction UUID,
  used as client_transaction_id in an in-memory TestClient.
- Three fixture borrower identifiers in Dart tests.
- Seven literal chart-account or accounting-source names in SQL and tests.

The SQL path rules include both the original migration names and their exact
reconciled names. This preserves detection for every other value and path,
including new credentials in the same fixture files. No directory, file,
commit, provider rule or general UUID format is excluded.

Validation must run the full merge history and staged/unstaged changes with
redacted output, compare remaining historical fingerprints to the retained
baseline, and confirm that a different candidate secret in an allowed path
and the same public value in an unrelated path remain detectable. Passing
these checks is not a security clearance for existing baseline findings.

## Recorded verification

The reviewed merge-history scan reports three retained baseline findings and
zero new fingerprints. The current staged and unstaged scans report zero
findings. They used the pinned 8.30.1 binary with fully redacted reports; the
final staged bytes and resulting merge commit still need a fresh scan.

The actual scanner accepted the 13 exact identifier/path pairs. It detected all
13 different high-entropy candidate values at those same paths, and all 13
original values at unrelated paths. The unextended default scanner also detected
all 13 changed candidate values. The control probes are synthetic and grant no
access. Existing baseline findings remain recorded as debt.
