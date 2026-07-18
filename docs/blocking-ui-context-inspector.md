# Blocking UI Context Inspector

This read-only tool shows the surrounding source lines for each potentially blocking call found in the SPINA desktop app.

## Why

The first blocking UI audit only reports call locations, for example `time.sleep` or `subprocess.run`. Before changing app behavior, we need to see the nearby code so we can tell whether the call is in UI flow, backup flow, a helper, or an existing worker/background path.

## Safety

The tool does not edit the main app source. It only reads the source file and writes a JSON report.

It should not be used to justify automatic edits to:

- reports or PDFs
- payments, balances, 7x7, interest, or principal calculations
- renewals
- collectors or route ledgers
- database migrations
- cash-control logic
- notes or transaction logic

## Local use

From the repository root:

```bat
python tools\inspect_blocking_ui_context.py --json blocking-ui-context-report.json
```

For a larger context window:

```bat
python tools\inspect_blocking_ui_context.py --context 20 --json blocking-ui-context-report.json
```

Upload the JSON report before any app-source cleanup is attempted.
