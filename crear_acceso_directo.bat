@echo off
REM Crea un acceso directo en el escritorio que apunta al ProspectorWeb.exe

set EXE_PATH=%~dp0dist\ProspectorWeb\ProspectorWeb.exe
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Prospector Web.lnk

if not exist "%EXE_PATH%" (
    echo.
    echo ❌ No encuentro %EXE_PATH%
    echo Ejecuta primero build_exe.bat
    echo.
    pause
    exit /b 1
)

REM Usar PowerShell para crear el .lnk
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$sc = $ws.CreateShortcut('%SHORTCUT%');" ^
    "$sc.TargetPath = '%EXE_PATH%';" ^
    "$sc.WorkingDirectory = '%~dp0dist\ProspectorWeb';" ^
    "$sc.Description = 'Prospector Web - RAIO Development';" ^
    "$sc.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo ===========================================
    echo   ✅ Acceso directo creado en tu escritorio
    echo ===========================================
    echo.
    echo "%SHORTCUT%"
    echo.
    echo Ya puedes hacer doble click ahí para abrir la app.
    echo.
) else (
    echo.
    echo ❌ No pude crear el acceso directo
    echo.
)

pause
