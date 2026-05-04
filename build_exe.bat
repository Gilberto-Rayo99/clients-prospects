@echo off
REM Build del .exe de Prospector Web

echo.
echo ===========================================
echo   Construyendo Prospector Web .exe
echo ===========================================
echo.

REM Verificar PyInstaller
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller...
    python -m pip install pyinstaller
)

REM Limpiar builds previos
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Construir
python -m PyInstaller build_exe.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ❌ Build fallido. Revisa los errores arriba.
    pause
    exit /b 1
)

echo.
echo ===========================================
echo   ✅ Build completo
echo ===========================================
echo.
echo Ejecutable: dist\ProspectorWeb\ProspectorWeb.exe
echo.
echo Siguiente paso: ejecutar crear_acceso_directo.bat
echo para colocar un icono en tu escritorio.
echo.
pause
