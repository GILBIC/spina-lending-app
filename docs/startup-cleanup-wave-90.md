# Startup cleanup Wave 90

Wave 89 established `spina_app.features.startup_runtime` as the final owner of desktop startup.

Wave 90 removes the compatibility entry-point code that is now dead:

- the original module-level `main()` implementation
- the earlier placeholder `if __name__ == '__main__': pass` block
- the later placeholder `if __name__ == '__main__': pass` block

The final `if __name__ == '__main__': main()` call remains at the end of the desktop file. At import time, Wave 89 installs the runtime-owned `main` function before that final call can execute.

## Preserved behavior

- Tk root creation remains owned by Wave 89
- cancelled login returns without entering the main loop
- unexpected startup errors still propagate
- direct-integration attachment remains best-effort and logged
- account, sidebar, and later feature installers still load before startup
- Tk shutdown behavior remains unchanged

## Validation

The self-hosted Windows workflow applied the cleanup to the actual desktop file, compiled the reduced application, and passed Waves 90 and 89 startup tests, protected login-cancellation and Tk-shutdown tests, account/header compatibility, Waves 86–88 sidebar and navigation tests, the permanent architecture map, and generated-diff validation before committing the desktop cleanup to the pull-request branch.

The owner-authored validation commit preserves that generated desktop result and allows the normal protected workflows to run against the exact cleaned head.
