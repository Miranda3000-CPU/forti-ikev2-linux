@echo off
:: ============================================================================
:: FortiClient VPN Manager — Inicializador Seguro Multiplataforma (Windows)
:: Execucao a partir do codigo-fonte com elevacao UAC e resolucao de dependencias
:: ============================================================================
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title FortiClient VPN - Inicializador Seguro

:: 1. Garantir que o diretorio de trabalho eh a raiz do projeto
cd /d "%~dp0"

:: 2. Verificacao e Solicitacao de Privilegios de Administrador (UAC)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================================
    echo   FortiClient VPN — Solicitando Modo Administrador
    echo ========================================================
    echo.
    echo [*] Conexoes de rede IKEv2 e rasdial requerem privilegios administrativos.
    echo [*] Solicitando autorizacao do Windows (UAC)...
    echo.

    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    if %errorlevel% equ 0 (
        exit /b 0
    ) else (
        echo [!] A elevacao de administrador foi recusada ou falhou.
        echo Pressione qualquer tecla para sair...
        pause >nul
        exit /b 1
    )
)

:: --- Execucao com Privilegios de Administrador Confirmada ---
cls
echo ========================================================
echo   FortiClient VPN Manager — Ambiente Seguro Windows
echo ========================================================
echo.

:: 3. Localizar interpretador Python
echo [1/4] Verificando instalador do Python...
set "PY_CMD="

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    :: Tentar caminhos padrao do Python no Windows
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
    if not defined PY_CMD (
        for /d %%D in ("%ProgramFiles%\Python3*") do (
            if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
        )
    )
    if not defined PY_CMD (
        for /d %%D in ("C:\Python3*") do (
            if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
        )
    )
)

if not defined PY_CMD (
    echo.
    echo [ERRO] Python 3 nao foi localizado neste computador.
    echo.
    echo Deseja tentar instalar o Python automaticamente via winget? (S/N)
    set /p RESP="> "
    if /i "!RESP!"=="S" (
        echo [*] Baixando e instalando Python via winget...
        winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
        echo.
        echo Python instalado. Reinicie este atalho para continuar.
        pause
        exit /b 0
    ) else (
        echo Instale o Python 3.10+ manualmente em https://www.python.org/
        echo Lembre-se de marcar a opcao "Add Python to PATH" na instalacao.
        pause
        exit /b 1
    )
)

for /f "tokens=2 delims= " %%v in ('"%PY_CMD%" --version 2^>^&1') do set "PY_VERSION=%%v"
echo   [OK] Python detectado: %PY_VERSION% (%PY_CMD%)

:: 4. Satisfazer dependencias Python automaticamente (Pillow, etc.)
echo.
echo [2/4] Verificando dependencias do projeto...
"%PY_CMD%" -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [*] Instalando modulos necessarios (Pillow)...
    "%PY_CMD%" -m pip install -r "%~dp0requirements.txt" --quiet
    if %errorlevel% neq 0 (
        echo   [!] Tentando instalar Pillow diretamente...
        "%PY_CMD%" -m pip install Pillow --quiet
    )
)
echo   [OK] Dependencias satisfeitas.

:: 5. Garantir perfil nativo VPN IKEv2 configurado no Windows
echo.
echo [3/4] Verificando perfil de conexao VPN no Windows...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$v = Get-VpnConnection -Name 'FortiClient-VPN' -ErrorAction SilentlyContinue; if (-not $v) { Add-VpnConnection -Name 'FortiClient-VPN' -ServerAddress '198.51.100.100' -TunnelType 'IKEv2' -AuthenticationMethod 'EAP' -EncryptionLevel 'Required' -SplitTunneling $true -Force; Set-VpnConnectionIPsecConfiguration -ConnectionName 'FortiClient-VPN' -AuthenticationTransformConstants GCMAES256 -CipherTransformConstants GCMAES256 -EncryptionMethod AES256 -IntegrityCheckMethod SHA256 -DHGroup Group18 -PfsGroup PFS2048 -Force }" >nul 2>&1
echo   [OK] Perfil IKEv2 / IPsec Group18 verificado.

:: 6. Iniciar Aplicacao Grafica
echo.
echo [4/4] Inicializando interface grafica FortiClient VPN...
echo ========================================================
echo.

"%PY_CMD%" "%~dp0vpn-gui.py"

if %errorlevel% neq 0 (
    echo.
    echo [AVISO] O programa encerrou com codigo %errorlevel%.
    echo Pressione qualquer tecla para fechar...
    pause >nul
)

exit /b 0
