# Desktop smoke test: extracted date helpers

After checking out the pull-request branch, launch the SPINA desktop application and verify:

1. The application opens and login behaves normally.
2. Dashboard date-based cards or filters load without an error.
3. Cash Control opens and accepts its existing date value.
4. Entering or loading a valid `YYYY-MM-DD` date continues to display the same date.
5. No report, balance, payment, collector, or database action needs to be performed for this extraction.

The automated regression suite already covers valid, invalid, empty, malformed, `date`, and `datetime` inputs. This desktop check is limited to confirming the extracted module imports correctly in the packaged application environment.
