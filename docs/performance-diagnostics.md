# SPINA performance diagnostics

This document explains the safe performance-testing workflow for SPINA.

## Current approach

The repository includes `tools/add_optional_performance_logs.py`, a guarded injector that can add optional timing wrappers to the SPINA desktop source.

The timing block is off by default. Normal users will not see timing logs unless the Windows environment variable below is set:

```bat
set SPINA_PERF_LOG=1
set SPINA_PERF_THRESHOLD=0.25
```

## How to test locally

From the repository folder:

```bat
python tools\add_optional_performance_logs.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
set SPINA_PERF_LOG=1
set SPINA_PERF_THRESHOLD=0.25
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then open the screens that feel slow: Dashboard, Clients, Data Bank, Reports, Cash Control, and Collector Route.

The console will show lines like:

```text
[SPINA][PERF] App.refresh_clients took 0.823s
```

## Safety notes

- This PR does not modify the main SPINA desktop source.
- The tool is compiled by GitHub Actions.
- Actual performance changes should be done later in one-screen PRs.
- Do not optimize loan calculations, balances, or report math without a separate validation plan.
