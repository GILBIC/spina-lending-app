# SPINA PC MVP

SPINA PC is the installable Windows presentation of the SPINA progressive web app. It opens the responsive four-role portal in Microsoft Edge or Google Chrome **app mode**, so staff can launch it from the Desktop or Start Menu without using an ordinary browser tab.

It is not a second backend and it does not contain a local lending database. Web, PC, Android, and iOS use the same FastAPI service and the same PostgreSQL/Supabase authority for roles, permissions, clients, loans, routes, balances, receipts, reviews, and audit evidence.

## Install

Open PowerShell in this directory and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_spina_pc.ps1 -PortalUrl "https://YOUR-SPINA-PORTAL.example" -StartAfterInstall
```

The installer:

- requires HTTPS except for `localhost` or `127.0.0.1` development;
- prefers Microsoft Edge, then Google Chrome;
- creates only `SPINA Lending.lnk` on the Desktop and Start Menu;
- stores the portal URL, not a password, token, database URL, or Supabase secret;
- uses the portal service worker only for static shell assets. Authenticated API responses are never intentionally cached.

## Uninstall

```powershell
.\uninstall_spina_pc.ps1
```

The uninstaller removes only the two SPINA-owned shortcuts. It does not delete the browser profile or any server record.

## Security and usage boundary

This MVP is for controlled/demo data until Management completes security, role, database, and release acceptance. It is **not authorized for real money**, actual borrower records, legal-book posting, tax filing, or production accounting merely because the shortcut launches successfully.

Collector payment entry is online-only. If the connection is uncertain after a submission, the portal locks financial entry and requires an authoritative refresh before another attempt.
