# Startup cleanup Waves 90–91

Wave 89 established `spina_app.features.startup_runtime` as the final owner of desktop startup.

Wave 90 removed the compatibility entry-point code that became dead:

- the original module-level `main()` implementation
- the earlier placeholder `if __name__ == '__main__': pass` block
- the later placeholder `if __name__ == '__main__': pass` block

The final `if __name__ == '__main__': main()` call remains at the end of the desktop file. At import time, Wave 89 installs the runtime-owned `main` function before that final call can execute.

Wave 91 completes the transition by deleting the temporary Wave 90 cleanup generator and converting its workflow into permanent, read-only startup architecture validation.

## Permanent validation boundary

The Wave 91 workflow:

- checks out the exact pull-request commit
- uses `contents: read`
- disables persisted GitHub credentials
- never generates, stages, commits, or pushes files
- verifies the reduced desktop entry point and Wave 89 runtime owner
- runs Waves 91, 90, and 89 startup regressions
- retains login-cancellation, Tk shutdown, account/header, sidebar/navigation, architecture-map, and clean-tree checks

The Wave 91 guard fails if the temporary generator returns, workflow write permission is restored, credentials are persisted, or branch mutation commands are reintroduced.

## Preserved behavior

- Tk root creation remains owned by Wave 89
- cancelled login returns without entering the main loop
- unexpected startup errors still propagate
- direct-integration attachment remains best-effort and logged
- account, sidebar, and later feature installers still load before startup
- Tk shutdown behavior remains unchanged
