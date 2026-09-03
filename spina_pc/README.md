# Spina for Windows

Spina opens the secure company portal in Microsoft Edge or Google Chrome app mode. Staff can launch it from the Desktop or Start Menu without using a normal browser tab.

Web, Windows, Android, and iOS use the same FastAPI service and PostgreSQL/Supabase authority. Windows does not keep a separate lending database.

## Install

Open PowerShell in this directory:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_spina_pc.ps1 -PortalUrl "https://YOUR-SPINA-PORTAL.example" -StartAfterInstall
```

The installer:

- requires HTTPS except on localhost;
- uses Microsoft Edge or Google Chrome;
- creates `Spina.lnk` on the Desktop and Start Menu;
- stores no password, token, database URL, or Supabase secret;
- never intentionally caches authenticated API responses.

## Uninstall

```powershell
.\uninstall_spina_pc.ps1
```

The uninstaller removes only the two Spina shortcuts. It does not delete browser or server data.

## Company-use gate

Use company records only after Management completes security, migration, reconciliation, backup, rollback, role-permission, and release acceptance checks.

Collector payment entry is online-only. After an uncertain submission, refresh the authoritative server state before trying again.
