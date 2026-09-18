@echo off
chcp 65001 >nul 2>nul
setlocal EnableDelayedExpansion

echo ========================================================
echo   Build FortiClient-VPN.exe (Windows)  v1.0.0
echo ========================================================
echo.

:: ==========================================================
:: 1. Verificar Python no PATH
:: ==========================================================
echo [1/5] Verificando instalacao do Python...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no PATH do Windows.
    echo.
    echo Solucao:
    echo   1. Baixe e instale Python 3.10+ em https://www.python.org/downloads/
    echo   2. Na instalacao, marque "Add python.exe to PATH"
    echo   3. Reinicie este terminal e tente novamente
    echo.
    pause
    exit /b 1
)

:: Verificar versao minima do Python (>= 3.8)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python encontrado: %PYVER%

:: ==========================================================
:: 2. Instalar dependencias
:: ==========================================================
echo.
echo [2/5] Instalando dependencias (Pillow, PyInstaller)...

python -m pip install --upgrade pip --quiet 2>nul
if %errorlevel% neq 0 (
    echo [AVISO] Falha ao atualizar pip. Continuando...
)

python -m pip install Pillow pyinstaller --quiet 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias Python.
    echo Execute manualmente: python -m pip install Pillow pyinstaller
    pause
    exit /b 1
)

echo   Dependencias OK

:: ==========================================================
:: 3. Gerar icones circulares
:: ==========================================================
echo.
echo [3/5] Gerando icones circulares DTIC...

if not exist "assets\dtic-logo-whasapp.jpeg" (
    echo [AVISO] Logo DTIC nao encontrada em assets\dtic-logo-whasapp.jpeg
    echo         Usando icones existentes se disponiveis...
    goto :skip_icons
)

python -c "from PIL import Image, ImageDraw; import os, sys; src='assets/dtic-logo-whasapp.jpeg'; img=Image.open(src).convert('RGBA'); w,h=img.size; m=min(w,h); c=img.crop(((w-m)//2, (h-m)//2, (w-m)//2+m, (h-m)//2+m)); mask=Image.new('L', (m*4, m*4), 0); ImageDraw.Draw(mask).ellipse((0,0,m*4,m*4), fill=255); mask=mask.resize((m,m), Image.Resampling.LANCZOS); c.putalpha(mask); c.save('assets/icon.png', 'PNG', optimize=True); c.save('assets/icon.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('  Icones gerados com sucesso.')"

if %errorlevel% neq 0 (
    echo [AVISO] Falha ao gerar icones. Usando existentes se disponiveis...
)

:skip_icons

:: ==========================================================
:: 4. Verificar arquivos necessarios
:: ==========================================================
echo.
echo [4/5] Verificando arquivos do projeto...

if not exist "vpn-gui.py" (
    echo [ERRO] Arquivo vpn-gui.py nao encontrado!
    echo Certifique-se de executar este script na raiz do projeto.
    pause
    exit /b 1
)

if not exist "FortiClient-VPN.spec" (
    echo [ERRO] Arquivo FortiClient-VPN.spec nao encontrado!
    pause
    exit /b 1
)

:: Verificar se pelo menos um icone existe
if not exist "assets\icon.ico" (
    if not exist "assets\icon.png" (
        echo [AVISO] Nenhum icone encontrado em assets\. O executavel sera gerado sem icone.
    )
)

echo   Arquivos OK

:: ==========================================================
:: 5. Compilar com PyInstaller
:: ==========================================================
echo.
echo [5/5] Compilando FortiClient-VPN.exe com PyInstaller...
echo       Isso pode levar alguns minutos...
echo.

:: Limpar builds anteriores
if exist "build\FortiClient-VPN" rd /s /q "build\FortiClient-VPN" 2>nul

pyinstaller --clean --noconfirm FortiClient-VPN.spec

echo.

:: ==========================================================
:: Resultado final
:: ==========================================================
if exist "dist\FortiClient-VPN.exe" (
    :: Obter tamanho do arquivo
    for %%A in ("dist\FortiClient-VPN.exe") do set FILESIZE=%%~zA

    echo ========================================================
    echo   [SUCESSO] Executavel gerado com sucesso!
    echo ========================================================
    echo.
    echo   Arquivo:   dist\FortiClient-VPN.exe
    echo   Tamanho:   !FILESIZE! bytes
    echo.
    echo   O executavel eh totalmente portatil e pode ser executado
    echo   em qualquer maquina Windows 10/11 sem necessidade de
    echo   instalar Python ou qualquer dependencia.
    echo.
    echo   Para distribuir, copie apenas o arquivo:
    echo     dist\FortiClient-VPN.exe
    echo.
) else (
    echo ========================================================
    echo   [ERRO] Falha ao gerar o executavel!
    echo ========================================================
    echo.
    echo   Verifique os logs do PyInstaller acima para detalhes.
    echo   Possiveis causas:
    echo     - Antivirus bloqueando a compilacao
    echo     - Falta de permissao na pasta dist\
    echo     - Dependencia Python incompativel
    echo.
)

pause
endlocal
