@echo off
setlocal EnableExtensions

if not defined RUNNER_TEMP (
  echo RUNNER_TEMP is not defined; cannot locate the pinned Flutter SDK. 1>&2
  exit /b 1
)

set "FLUTTER_ROOT=%RUNNER_TEMP%\flutter-3.44.7"
set "FLUTTER_BAT=%FLUTTER_ROOT%\bin\flutter.bat"
set "MINGIT_CMD=%RUNNER_TEMP%\spina-mingit-2.55.0.4\cmd"

if exist "%MINGIT_CMD%\git.exe" set "PATH=%MINGIT_CMD%;%PATH%"
if not exist "%FLUTTER_BAT%" (
  echo Pinned Flutter 3.44.7 SDK was not installed at %FLUTTER_ROOT%. 1>&2
  exit /b 1
)

call "%FLUTTER_BAT%" %*
exit /b %ERRORLEVEL%
