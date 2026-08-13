# ECL Forward-Looking Evidence Governance

## Scope

This document defines the frozen SPINA V1 A2 boundary for authoritative forward-looking economic evidence used by quantitative ECL readiness and later read-only measurement.

This policy does **not** calculate ECL, does not post account `1190 Allowance for Expected Credit Loss`, does not execute write-off accounting, and does not enable automatic source posting.

## Required authoritative evidence fields

Every forward-looking evidence version must retain, at minimum:

- an immutable evidence identifier and version;
- source name / issuing organization;
- observation or forecast period covered by the source;
- retrieval date/time;
- effective date for SPINA use;
- retained source reference sufficient to identify the exact source version used;
- Management interpretation describing why the evidence is relevant to the lending portfolio and what it supports;
- Management approval identity and authoritative approval timestamp;
- supersession linkage when a later approved evidence version replaces an earlier one;
- an explicit status showing whether the evidence is current, superseded, stale, revoked, or otherwise not usable for new ECL measurements.

Free-text notes by themselves are not accounting evidence and cannot satisfy the protected readiness gate.

## Versioning and historical reproducibility

Forward-looking evidence is append-only/versioned. A later forecast or Management interpretation must never rewrite an earlier approved evidence version or silently change a prior ECL measurement.

A quantitative ECL measurement must retain the exact approved forward-looking evidence identifiers/versions it used. When evidence is later superseded, prior measurements remain reproducible from their retained evidence references.

## Stale and superseded behavior

A later approved evidence version may supersede an earlier version for **future** measurements only. Supersession does not mutate prior measurements.

Evidence is not usable for a new authoritative ECL measurement when its protected status is stale, superseded, revoked, unapproved, outside its applicable period, or otherwise no longer current under the approved policy.

The readiness gate must expose the exact forward-looking blocker rather than substitute a newer forecast into an older measurement or a default assumption into a missing one.

## Scenario probabilities, multipliers, and overlays

SPINA must not invent or default any scenario probability, economic multiplier, management overlay, PD, LGD, cure rate, recovery rate, or similar numeric assumption merely to make ECL run.

A scenario probability, multiplier, or overlay may be used only when all of the following are true:

1. the numeric value is supported by retained authoritative evidence;
2. the evidence source and exact version are retained;
3. Management explicitly approves both the value and its interpretation/application;
4. the value is versioned and historically reproducible;
5. the quantitative ECL measurement snapshots the exact approved value/version used.

If those conditions are not met, the applicable numeric input remains absent and the readiness gate stays blocked.

## Protected workflow boundary

The implementation should follow this sequence:

1. record immutable source/evidence version;
2. record Management interpretation and explicit approval;
3. derive protected current/stale/superseded readiness without mutating prior versions;
4. expose exact blocker codes to the quantitative ECL input-readiness gate;
5. later read-only ECL measurement may reference only exact approved current evidence versions;
6. posting remains a separate later protected Management-confirmed stage.

`ecl_calculation_enabled=false`, `account_1190_posting_enabled=false`, and `automatic_source_posting=false` remain the V1 safety boundary until their later frozen Master #296 stages are separately proven.