# Android photo recovery

Android can stop Spina while the system photo picker or camera is open. On the
next launch, Spina checks the image-picker plugin after restoring the login
session. A pending selection is checked again when Spina resumes and before a
form opens its photo picker, because Android can deliver the result after the
app has restarted. One coordinator serializes these reads. An empty early result
keeps the pending context until explicit discard, logout or expiry. An interrupted
selection must be kept for another check or explicitly discarded before choosing
a new photo, including when the user visits a different form.
A recovered photo appears in a notice. Return to the original form and
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
need entering again. A recovered result is copied into Spina's private application
support directory before its path is journaled. This private copy preserves a
reviewable selection across another restart even if Android clears the plugin's
cache. A normal picker result still follows the form's existing byte-reading path.

The private store owns only copies it creates under
`spina_recovered_images_v1/pick_*/photo`, with a matching ownership marker. It
checks the directory and file types without following symbolic links. Cleanup
does not recurse, and refuses unrecognized entries. Picker, gallery, download
and server evidence paths never authorize deletion.

Preview reads, accepting the recovered bytes and cleanup are serialized. On
acceptance, bytes are detached into memory before the private disk copy is
removed; existing form submission and uncertain-upload retry behavior retains
those bytes. Discard, logout, authorization changes and the existing 24-hour
expiry invalidate the journal before removing eligible private copies. Expiry
is checked when restoring or accepting a recovered photo, not by a background
timer. A failed journal invalidation preserves the private copy. Failed cleanup
is reported and retried on the next recovery initialization; clearing metadata
alone is not proof of file removal. Startup also removes eligible orphaned copies
while preserving the current journaled photo.

This does not establish erasure of the image-picker plugin's cache, gallery
originals, user-saved downloads, device backups, or finalized server evidence.

## Verification

The controller tests exercise destructive lost-data retrieval, persistence across
a second restart, destination and authorization separation, cancellation,
storage failures, expiry, concurrent selection, late native results and logout
races. Widget tests
exercise recovery review and explicit submission, office witness reset, account
startup gating and stale device-identity completions.
Private-store integration tests use synthetic files for copy ownership,
second-restart survival, consumption/discard/logout/expiry cleanup, deletion
failure and read/cleanup races. Symbolic-link coverage may be skipped on a
Windows host that disallows link creation; Linux CI must exercise that case.

Physical acceptance uses an isolated application ID and disposable backend.
Open the native camera, run `adb shell am kill <test-package>` while that
external activity is foreground, verify the old process is gone, and complete
the capture. For a gallery picker that keeps its caller visible, press Home,
wait for the task to become backgrounded, then kill the test process. Resume the
test task through Recents and finish selecting the synthetic gallery photo.
This also tests Spina restarting before the picker delivers its result.
These checks differ from force-stopping the app or only destroying an activity.
Verify a new process, the recovery notice, the matching form's preview,
and zero backend writes until the explicit submit action. Repeat with gallery,
a second restart, cancellation and logout/account changes. Do not kill or clear
an app containing unsynchronized business records for this test.
