@echo off
REM Compila apenas o executavel da GUI no Windows (para uso com Python nativo).
REM O pacote completo (motor strongSwan + instalador) e gerado por build_windows.sh
REM a partir do Linux. Este .bat existe para builds locais rapidos.
setlocal
cd /d "%~dp0.."

echo Instalando dependencias...
pip install pyinstaller pillow || goto :erro

echo Limpando artefatos anteriores do PyInstaller...
if exist build\output rmdir /s /q build\output
if exist dist\FortiClient-VPN.exe del /q dist\FortiClient-VPN.exe

echo Gerando build_info.py...
python build\gen_build_info.py || goto :erro

echo Executando PyInstaller...
pyinstaller --noconfirm --distpath build\output --workpath build\output\work "build\FortiClient-VPN.spec" || goto :erro

echo.
echo Compilacao concluida: build\output\FortiClient-VPN.exe
echo Para gerar o instalador, compile build\FortiClient-VPN-Setup.iss com o Inno Setup.
goto :fim

:erro
echo.
echo FALHA na compilacao.
exit /b 1

:fim
endlocal
exit /b 0
