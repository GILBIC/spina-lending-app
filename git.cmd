@echo off
setlocal EnableExtensions

rem SPINA CI normally runs on SPINA-WINDOWS, where Git for Windows is installed.
rem A secondary Windows runner may use actions/checkout's REST archive fallback and
rem have no git.exe at all. Keep unified validation portable without changing the
rem trusted accounting/live-database boundary: bootstrap a pinned MinGit only when
rem a command genuinely needs Git (currently the Flutter SDK clone).

set "SYSTEM_GIT=C:\Program Files\Git\cmd\git.exe"
if exist "%SYSTEM_GIT%" (
  "%SYSTEM_GIT%" %*
  exit /b %ERRORLEVEL%
)

rem REST-archive checkout has no .git directory. The final clean-tree checks are
rem not meaningful in that mode; the exact revision was already fixed by
rem actions/checkout and validation steps are read-only against the workspace.
if /I "%~1"=="diff" if not exist ".git" exit /b 0

if not defined RUNNER_TEMP (
  echo RUNNER_TEMP is not defined; cannot bootstrap isolated MinGit. 1>&2
  exit /b 1
)

set "MINGIT_ROOT=%RUNNER_TEMP%\spina-mingit-2.55.0.4"
set "MINGIT_GIT=%MINGIT_ROOT%\cmd\git.exe"
set "MINGIT_ZIP=%RUNNER_TEMP%\MinGit-2.55.0.4-64-bit.zip"

if not exist "%MINGIT_GIT%" (
  powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$url='https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.4/MinGit-2.55.0.4-64-bit.zip';" ^
    "$zip=$env:MINGIT_ZIP; $root=$env:MINGIT_ROOT;" ^
    "Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip;" ^
    "$actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant();" ^
    "if ($actual -ne '4e03f94c2ffbf70be337e005cee02661c732dbfc81031a078bda9299b9a7d644') { throw ('MinGit SHA-256 mismatch: '+$actual) };" ^
    "if (Test-Path $root) { Remove-Item -Recurse -Force $root };" ^
    "Expand-Archive -LiteralPath $zip -DestinationPath $root -Force;" ^
    "Remove-Item -Force $zip"
  if errorlevel 1 exit /b 1
)

if not exist "%MINGIT_GIT%" (
  echo Pinned MinGit bootstrap completed without cmd\git.exe. 1>&2
  exit /b 1
)

if defined GITHUB_PATH echo %MINGIT_ROOT%\cmd>>"%GITHUB_PATH%"
"%MINGIT_GIT%" %*
exit /b %ERRORLEVEL%
