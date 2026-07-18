# Bare except context audit

This read-only audit reports every bare `except:` block in the SPINA desktop app.

## Why

The quality report still shows a small number of bare `except:` handlers. Those should not be changed blindly because some may sit inside protected application logic.

## Local use

```bat
python tools\audit_bare_except_context.py --json bare-except-context-report.json
```

Upload `bare-except-context-report.json` before any cleanup is attempted.

## Safety

- read-only only
- does not edit the app source
- reports surrounding context
- marks protected-looking areas for manual review
- any later cleanup should be one narrow site or one narrow family at a time
