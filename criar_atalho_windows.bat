@echo off
:: ============================================================================
:: FortiClient VPN Manager — Criador de Atalho na Area de Trabalho (Windows)
:: Cria o atalho oficial com icone DTIC para iniciar em Modo Administrador
:: ============================================================================
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title FortiClient VPN - Criador de Atalho

cd /d "%~dp0"

echo ========================================================
echo   FortiClient VPN — Criador de Atalho Oficial DTIC
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
:: Remover barra invertida final se existir
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "TARGET_CMD=%SCRIPT_DIR%\iniciar_vpn.cmd"
set "ICON_FILE=%SCRIPT_DIR%\assets\icon.ico"

if not exist "%TARGET_CMD%" (
    echo [ERRO] O arquivo iniciar_vpn.cmd nao foi encontrado em:
    echo   %TARGET_CMD%
    pause
    exit /b 1
)

echo [*] Criando atalho na Area de Trabalho...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$shortcutPath = Join-Path $desktop 'FortiClient VPN.lnk'; " ^
    "$s = $ws.CreateShortcut($shortcutPath); " ^
    "$s.TargetPath = '%TARGET_CMD%'; " ^
    "$s.WorkingDirectory = '%SCRIPT_DIR%'; " ^
    "$s.Description = 'FortiClient VPN Manager (Modo Administrador) - DTIC/PRODEPA'; " ^
    "if (Test-Path '%ICON_FILE%') { $s.IconLocation = '%ICON_FILE%,0' }; " ^
    "$s.Save(); " ^
    "Write-Host '  [OK] Atalho criado em:' $shortcutPath -ForegroundColor Green;"

echo.
echo ========================================================
echo   [SUCESSO] Atalho criado na sua Area de Trabalho!
echo ========================================================
echo.
echo   Basta dar um duplo clique no atalho 'FortiClient VPN':
echo   1. O Windows solicitara a confirmacao de Administrador (UAC).
echo   2. O terminal verificara e instalara dependencias faltantes.
echo   3. A conexao VPN abrira pronta para uso e imune a bloqueios de antivirus.
echo.
pause
exit /b 0
