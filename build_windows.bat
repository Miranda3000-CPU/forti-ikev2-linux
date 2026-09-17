@echo off
chcp 65001 >nul
echo ========================================================
echo   Compilador de Executavel Windows (FortiClient-VPN)
echo ========================================================
echo.

:: 1. Verificar instalacao do Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no PATH do Windows.
    echo Instale o Python 3.10+ em https://www.python.org/downloads/
    echo Certifique-se de marcar "Add python.exe to PATH".
    pause
    exit /b 1
)

echo [*] Instalando/Verificando dependencias (Pillow, PyInstaller)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo.
echo [*] Gerando icones circulares se necessario...
python -c "from PIL import Image, ImageDraw; import os; src='assets/dtic-logo-whasapp.jpeg'; img=Image.open(src).convert('RGBA'); w,h=img.size; m=min(w,h); c=img.crop(((w-m)//2, (h-m)//2, (w-m)//2+m, (h-m)//2+m)); mask=Image.new('L', (m*4, m*4), 0); ImageDraw.Draw(mask).ellipse((0,0,m*4,m*4), fill=255); mask=mask.resize((m,m), Image.Resampling.LANCZOS); c.putalpha(mask); c.save('assets/icon.png', 'PNG'); c.save('assets/icon.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo.
echo [*] Compilando FortiClient-VPN.exe via PyInstaller...
pyinstaller --clean --noconfirm FortiClient-VPN.spec

if exist "dist\FortiClient-VPN.exe" (
    echo.
    echo ========================================================
    echo   [SUCESSO] Executavel gerado com sucesso!
    echo ========================================================
    echo Localizacao: dist\FortiClient-VPN.exe
    echo.
    echo O programa e totalmente portatil e pode ser executado
    echo em qualquer maquina Windows sem necessidade de Python.
) else (
    echo.
    echo [ERRO] Falha ao gerar o executavel. Verifique os logs acima.
)

pause
