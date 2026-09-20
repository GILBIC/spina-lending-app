# Candidate and submitted-version control

The offline package identifies an engineering candidate. It does not create a registered version merely by hashing source files. Keep four facts separate: the source candidate; the reviewed package; any actual submitted package; and any actual BIR acknowledgement. The [registration checklist](registration-checklist.md) records the evidence still needed.

## Create and retain a candidate

Run the [offline builder](../../tools/build_bir_registration_package.py) against a clean checkout with its explicit full SHA, a new outside-repository output directory and individually supplied private evidence. Record the resulting source SHA/tree, package/component versions, module/schema inventory, source-file hashes, evidence hashes and accounting-export manifest when supplied. Keep the builder output and original records under authorized access with the applicable retention/hold policy.

A filename, Git branch, package version or local success label does not identify a submitted artifact on its own. Copying an older source SHA into a report cannot make newly changed files part of that source. Dirty, mismatched, unsafe or oversized inputs must fail rather than produce a misleading version-bound packet.

If the owner later submits a package, retain that exact package unchanged with the real submission date/reference and subsequent genuine BIR record. Do not overwrite it with a regenerated draft or quietly replace supplied signed forms. The software creates no Git tag, signing key, approval, certificate or QR.

## Compare a later proposal

Pass the prior retained manifest through `--compare-manifest PRIOR_JSON` while creating a **new** output directory. The comparison records added, removed and changed financial modules, schema and related assets. The prior manifest and its files remain unchanged.

For every relevant change, the responsible reviewer should record the old/new source and package hashes, affected financial calculations or reports, source/control/schema changes, migration/data effects, test evidence, rollout/rollback plan and whether previously supplied forms/samples/policies remain accurate. A renamed or removed file also needs review; “no changed files” does not settle new legal or operational facts.

RMO 9-2021 distinguishes changes requiring updated registration from minor improvements requiring notification. The tool does not decide the legal major/minor category. An accountant/authorized owner must determine the applicable process and retain the actual notice/update/acknowledgement evidence before representing the new deployment as covered. [RMO 9-2021, section V](https://bir-cdn.bir.gov.ph/local/pdf/RMO%20No.%209-2021.pdf).

`DRAFT_PENDING_INPUTS` and `DRAFT_FOR_OWNER_REVIEW` are completeness labels only. Every generated package remains `registration_verified: false` and `filing_ready: false`, including one with supplied files labelled signed or reviewed. Annual books registration and electronic invoice/reporting decisions stay separate from this source-version comparison.
