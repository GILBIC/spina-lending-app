# Accounting migration integration

The October 5 accounting branch and the current Office-signature/client-photo
branch independently used migration numbers above 0139. The October 10
integration preserves current 0140–0143 and gives each incoming migration its
own filename. Apply the installed filenames in sorted order.

| October 5 filename prefix | Installed prefix | Purpose |
| --- | --- | --- |
| 0140 | 0144 | Book identity |
| 0142 | 0145 | Treasury receipt accounting |
| 0143 | 0146 | Legacy source completeness |
| 0144 | 0147 | Liability control schedule |
| 0145 | 0148 | Composed source controls |
| 0146 | 0149 | Treasury applications |
| 0147 | 0150 | Reporting evidence |
| 0148 | 0151 | Retained cutoff assessments |
| 0149 | 0152 | Proven-source assessment composition |
| 0150 | 0153 | Treasury transfer accounting |
| 0151 | 0154 | Retained period-review manifests |
| 0152 | 0155 | Collector liability accounting |
| 0153 | 0156 | Elapsed period assessments |
| 0154 | 0157 | Loan payout accounting |
| 0155 | 0158 | Regular Treasury applications |
| 0156 | 0159 | Native Regular origin |
| 0157 | 0160 | Collector credit application |
| 0158 | 0161 | Journal disclosure reviews |

Current 0141 retains the complete close source inventory and its later
concurrency/privacy repairs. The overlapping accounting-branch 0141 is not
installed a second time. Current 0140 Office signatures, 0142 tax lock ordering
and 0143 private client photos remain intact.

The integration additions use 0163 for native original assessment/activation/tax
admission, 0164 for bounded close lock waits, 0165 for chronological payments,
0166 for renewal completion/lineage, 0167 for payoff and closed-term reviews,
0168 for retained credit-risk assessments, 0169 for impaired cash-day measurement
reviews, 0170 for reporting source proof, and 0171 for source-bound current credit-risk
reviews. Prefix 0162 remains reserved and does not represent an uninstalled
migration. Runners enumerate actual numbered SQL files in filename order;
the bootstrap completeness check permits only this documented gap and still
rejects missing required migrations.

Historical review ledgers and captured database metadata retain their original
numbers and verified scope. Versioned helper names inside SQL likewise retain
their names. Neither changes the installed filename order or permits replaying
an older close stack over the integrated schema.

This map records integration order. It is not a statement that a proposed
migration has completed verification or been deployed.
