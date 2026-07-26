@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_AI4MS.ps1" %*
set "AI4MS_EXIT_CODE=%ERRORLEVEL%"
if not "%AI4MS_EXIT_CODE%"=="0" (
  echo.
  echo AI4MS failed to start. Review the error above.
  pause
)
exit /b %AI4MS_EXIT_CODE%
