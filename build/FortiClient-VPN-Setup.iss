; Instalador Windows do FortiClient VPN Manager (DTIC).
;
; Gera: dist\FortiClient-VPN-Setup.exe
; Compilar (no Linux, via Wine):
;   wine "$ISCC" build/FortiClient-VPN-Setup.iss
;
; O pacote inclui o motor strongSwan para Windows (vendor\windows), que é o que
; permite IKEv2 + PSK + EAP-MSCHAPv2 sem depender do FortiClient.

[Setup]
AppName=FortiClient VPN - DTIC
AppVersion=2.1.3
AppPublisher=Jeiel Miranda (DTIC)
DefaultDirName={autopf}\FortiClient-VPN
DefaultGroupName=FortiClient VPN
UninstallDisplayIcon={app}\FortiClient-VPN.exe
OutputDir=dist
OutputBaseFilename=FortiClient-VPN-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
; Instalar o serviço do motor exige administrador.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Caminhos abaixo são relativos à raiz do repositório (um nível acima de build\).
SourceDir=..

[Files]
Source: "build\output\FortiClient-VPN.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Motor strongSwan para Windows (charon-svc.exe, swanctl.exe, strongswan.conf).
Source: "vendor\windows\*"; DestDir: "{app}\vendor\windows"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FortiClient VPN"; Filename: "{app}\FortiClient-VPN.exe"
Name: "{commondesktop}\FortiClient VPN"; Filename: "{app}\FortiClient-VPN.exe"
Name: "{group}\Desinstalar FortiClient VPN"; Filename: "{uninstallexe}"

[Run]
; Registra/atualiza o serviço do motor IKE (idempotente: apaga antes de criar).
Filename: "{sys}\sc.exe"; Parameters: "stop ""strongSwan IKE service"""; Flags: runhidden; StatusMsg: "Parando serviço anterior..."
Filename: "{sys}\sc.exe"; Parameters: "delete ""strongSwan IKE service"""; Flags: runhidden
Filename: "{sys}\sc.exe"; Parameters: "create ""strongSwan IKE service"" binPath= ""{app}\vendor\windows\charon-svc.exe"" start= demand DisplayName= ""strongSwan IKE service"""; Flags: runhidden; StatusMsg: "Registrando o serviço strongSwan..."
Filename: "{sys}\sc.exe"; Parameters: "start ""strongSwan IKE service"""; Flags: runhidden; StatusMsg: "Iniciando o serviço strongSwan..."
; Libera as portas UDP 500/4500 já na instalação, para a primeira conexão não
; precisar de outra elevação. O IKEEXT é restaurado na desinstalação.
Filename: "{sys}\sc.exe"; Parameters: "stop IKEEXT"; Flags: runhidden; StatusMsg: "Liberando as portas IKE (UDP 500/4500)..."
Filename: "{app}\FortiClient-VPN.exe"; Parameters: "--cleanup"; Flags: runhidden; StatusMsg: "Removendo resíduos de versões anteriores..."

[UninstallRun]
; Remove o serviço e devolve o IKEEXT ao estado normal.
Filename: "{sys}\sc.exe"; Parameters: "stop ""strongSwan IKE service"""; Flags: runhidden; RunOnceId: "StopIkeService"
Filename: "{sys}\sc.exe"; Parameters: "delete ""strongSwan IKE service"""; Flags: runhidden; RunOnceId: "DeleteIkeService"
Filename: "{sys}\sc.exe"; Parameters: "start IKEEXT"; Flags: runhidden; RunOnceId: "RestoreIkext"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\vendor"
