<#
.SYNOPSIS
    Script de Instalação e Configuração da VPN FortiClient IKEv2 para Windows
.DESCRIPTION
    Configura a conexão VPN nativa do Windows compatível com o FortiGate
    (IKEv2, Diffie-Hellman Group 18, AES-256, SHA-256 e EAP-MSCHAPv2).
#>

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Instalador FortiClient VPN IKEv2 para Windows        " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$VpnName = "FortiClient-VPN"
$ServerAddress = "198.51.100.100"

# 1. Verificar se está rodando como Administrador (solicitar elevação automática se necessário)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[*] Solicitando permissões de Administrador do Windows..." -ForegroundColor Yellow
    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        exit 0
    } catch {
        Write-Host "[!] Não foi possível elevar automaticamente. Execute o PowerShell como Administrador." -ForegroundColor Red
        pause
        exit 1
    }
}

# 2. Criar ou atualizar a Conexão VPN nativa do Windows no catálogo global (All Users)
Write-Host "`n[*] Configurando Conexão VPN: $VpnName (Servidor: $ServerAddress)..." -ForegroundColor Yellow

$existingVpnAll = Get-VpnConnection -Name $VpnName -AllUserConnection -ErrorAction SilentlyContinue
$existingVpnUser = Get-VpnConnection -Name $VpnName -ErrorAction SilentlyContinue

if ($existingVpnAll) {
    Write-Host "[*] Conexão global existente encontrada. Atualizando catálogo..." -ForegroundColor Yellow
    Remove-VpnConnection -Name $VpnName -AllUserConnection -Force -Confirm:$false -ErrorAction SilentlyContinue
}
if ($existingVpnUser) {
    Remove-VpnConnection -Name $VpnName -Force -Confirm:$false -ErrorAction SilentlyContinue
}

Add-VpnConnection -Name $VpnName `
    -ServerAddress $ServerAddress `
    -TunnelType "IKEv2" `
    -AuthenticationMethod "EAP" `
    -EncryptionLevel "Required" `
    -SplitTunneling $true `
    -AllUserConnection `
    -Force

# 3. Configurar parâmetros de criptografia IPsec requeridos pelo FortiGate (MODP_8192 / Group 18)
Write-Host "[*] Aplicando cifras IPsec: AES256 / SHA256 / DH Group 18 (MODP_8192)..." -ForegroundColor Yellow
Set-VpnConnectionIPsecConfiguration -ConnectionName $VpnName `
    -AuthenticationTransformConstants GCMAES256 `
    -CipherTransformConstants GCMAES256 `
    -EncryptionMethod AES256 `
    -IntegrityCheckMethod SHA256 `
    -DHGroup Group18 `
    -PfsGroup PFS2048 `
    -AllUserConnection `
    -Force

# 4. Criar atalho na Área de Trabalho com o ícone oficial DTIC
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$DesktopPath\FortiClient VPN.lnk"

$cmdCandidate = "$PSScriptRoot\iniciar_vpn.cmd"
$exeCandidate1 = "$PSScriptRoot\dist\FortiClient-VPN.exe"
$exeCandidate2 = "$PSScriptRoot\FortiClient-VPN.exe"
$IconPath = "$PSScriptRoot\assets\icon.ico"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

if (Test-Path $cmdCandidate) {
    $Shortcut.TargetPath = $cmdCandidate
    $Shortcut.WorkingDirectory = "$PSScriptRoot"
} elseif (Test-Path $exeCandidate1) {
    $Shortcut.TargetPath = $exeCandidate1
    $Shortcut.WorkingDirectory = "$PSScriptRoot\dist"
} elseif (Test-Path $exeCandidate2) {
    $Shortcut.TargetPath = $exeCandidate2
    $Shortcut.WorkingDirectory = "$PSScriptRoot"
} else {
    $Shortcut.TargetPath = "pythonw.exe"
    $Shortcut.Arguments = "`"$PSScriptRoot\vpn-gui.py`""
    $Shortcut.WorkingDirectory = "$PSScriptRoot"
}

if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
}

$Shortcut.Description = "FortiClient VPN Manager (DTIC)"
$Shortcut.Save()

Write-Host "`n[✓] Configuração concluída com sucesso!" -ForegroundColor Green
Write-Host "Você pode conectar de duas formas no Windows:" -ForegroundColor Cyan
Write-Host "  1. Pelo Executável ou Interface Gráfica: Abra o atalho 'FortiClient VPN' na Área de Trabalho."
Write-Host "  2. Pelo Painel do Windows: Clique no ícone de Rede perto do relógio -> FortiClient-VPN -> Conectar."
Write-Host ""
