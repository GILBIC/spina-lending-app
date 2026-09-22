# Android photo recovery

Android can stop Spina while the system photo picker or camera is open. On the
next launch, Spina checks the image-picker plugin once after restoring the login
session. A recovered photo appears in a notice. Return to the original form and
tap its photo button to review the image, keep it for later, or discard it.

Recovery uses one encrypted metadata record written before opening the picker.
It records the account, current roles and permissions, server address,
installation, purpose, and destination. A recovered image can only be used by
the matching form. Another form requires explicit discard before a new photo
selection. Logging out or changing authorization invalidates pending recovery.
Unmatched, malformed, missing, or expired results cannot become form evidence.
Metadata expires after 24 hours, including when accepting an image without
restarting the app again.

Supported destinations:

- Client payment proof: loan, existing proof ID and version for corrections.
- Collector renewal handover: request, client, loan and locked release context.
- Collector remittance handover: remittance, collector, recipient and submission.
- Office review: client, CIF/application versions, snapshot and privacy choice.
- Office first-loan evidence: client, application, loan and packet; cash evidence
  additionally binds the release authorization.

Recovered photos go through each form's normal byte-size and image checks. No
upload happens at startup. Client, remittance and office forms still require
their submit action; the two Collector renewal flows require an explicit
**Upload recovered photo** confirmation. Witness and cash receipt confirmations
are not restored, and recovery does not post payments or change balances.

This recovers a camera/picker result, not general form fields, an upload interrupted
after submission, or a financial offline queue. Notes and other form choices may
need entering again. The image remains in the plugin's temporary storage; if
Android has removed it, select or take another photo. Clearing recovery metadata
does not promise erasure of the plugin cache or user-saved gallery files.

## Verification

The controller tests exercise destructive lost-data retrieval, persistence across
a second restart, destination and authorization separation, cancellation,
storage failures, expiry, concurrent selection and logout races. Widget tests
exercise recovery review and explicit submission, office witness reset, account
startup gating and stale device-identity completions.

Physical acceptance uses an isolated application ID and disposable backend.
Open the native camera/picker, run `adb shell am kill <test-package>` while that
external activity is foreground, verify the old process is gone, and complete
the selection. This differs from force-stopping the app or only destroying an
activity. Verify a new process, the recovery notice, the matching form's preview,
and zero backend writes until the explicit submit action. Repeat with gallery,
a second restart, cancellation and logout/account changes. Do not kill or clear
an app containing unsynchronized business records for this test.
