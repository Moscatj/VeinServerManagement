@echo off
setlocal EnableExtensions

rem --- Resolve roots ---
pushd "%~dp0\.." >nul 2>&1
set "VEIN_MGMT_ROOT=%CD%"
set "VEIN_MGMT_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"
set "VEIN_MGMT_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json"
set "PYEXE=py -3"

if not defined VEIN_CONFIG if exist "%VEIN_MGMT_CONFIG%" set "VEIN_CONFIG=%VEIN_MGMT_CONFIG%"

echo [env] VEIN_MGMT_ROOT=%VEIN_MGMT_ROOT%
echo [env] VEIN_MGMT_CONTROLLER=%VEIN_MGMT_CONTROLLER%
echo [env] VEIN_CONFIG=%VEIN_CONFIG%
echo [env] PYEXE=%PYEXE%

set "GUI=%VEIN_MGMT_CONTROLLER%\vein_manager.py"
echo [INFO] Launching: %GUI%
popd >nul 2>&1

rem ---- Windowless launch with verification (no double start) ----
powershell -NoProfile -WindowStyle Hidden -Command ^
  "$script = '%GUI%';" ^
  "$p = Start-Process -FilePath 'pyw' -ArgumentList '-3',('""'+$script+'""') -PassThru;" ^
  "Start-Sleep -Milliseconds 900;" ^
  "if ($p.HasExited) { " ^
  "  Write-Host '[WARN] Windowless launch failed quickly. Falling back to console...';" ^
  "  & py -3 $script;" ^
  "  pause" ^
  "}"

endlocal
