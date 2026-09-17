#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiClient VPN Manager - Interface Gráfica Multiplataforma (Linux & Windows)
Conecta a VPNs corporativas FortiGate IKEv2 (EAP-MSCHAPv2 + PSK).
"""

import sys
import os
import json
import time
import re
import socket
import threading
import subprocess
import webbrowser
import ssl
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

# Tratamento de caminhos para executáveis empacotados (PyInstaller / CX_Freeze)
def get_resource_path(relative_path):
    """Obtém o caminho absoluto para recursos, funcionando em dev e PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    full_path = os.path.join(base_path, relative_path)
    if os.path.exists(full_path):
        return full_path
    
    # Fallback para instalação padrão Linux (/usr/share/forticlient-vpn/assets)
    system_path = os.path.join("/usr/share/forticlient-vpn", relative_path)
    if os.path.exists(system_path):
        return system_path

    return full_path

# Suporte ao Pillow para manipulação do ícone circular
try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

CONF_FILE_LINUX = "/etc/swanctl/conf.d/forti.conf"
CHILD_NAME = "forticlient"
VPN_NAME_WIN = "FortiClient-VPN"
WEB_URL = "https://10.64.10.1:6464/login?redir=%2F"


def get_default_local_ip(target_gw="198.51.100.100"):
    """Detecta automaticamente o IP local roteado para o Gateway."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect((target_gw, 500))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def make_round_image(pil_img, size):
    """
    Recorta qualquer imagem em formato quadrado e aplica máscara circular
    com antialiasing (supersampling) para garantir que seja perfeitamente redonda.
    """
    w, h = pil_img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    cropped = pil_img.crop((left, top, left + min_dim, top + min_dim))

    scale = 4
    mask_dim = (size[0] * scale, size[1] * scale)
    mask = Image.new("L", mask_dim, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, mask_dim[0], mask_dim[1]), fill=255)
    mask = mask.resize(size, Image.Resampling.LANCZOS)

    resized = cropped.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    resized.putalpha(mask)
    return resized


class VpnApp:
    def __init__(self, root):
        self.root = root
        os_label = "Windows" if IS_WINDOWS else "Linux"
        self.root.title(f"FortiClient VPN - DTIC / PRODEPA ({os_label})")
        self.root.geometry("630x740")
        self.root.resizable(False, False)
        self.root.configure(bg="#f1f5f9")

        self.setup_window_icon()

        # Cabeçalho Superior com Logo Circular
        header_frame = tk.Frame(root, bg="#0f172a", height=85)
        header_frame.pack(fill="x")

        header_content = tk.Frame(header_frame, bg="#0f172a")
        header_content.pack(pady=12, padx=15)

        # Imagem redonda do logo DTIC no cabeçalho
        self.logo_label = None
        if HAS_PIL and hasattr(self, "header_img_tk") and self.header_img_tk:
            self.logo_label = tk.Label(header_content, image=self.header_img_tk, bg="#0f172a")
            self.logo_label.pack(side="left", padx=(0, 12))
        else:
            lbl_badge = tk.Label(header_content, text="🛡️", font=("Helvetica", 24), bg="#0f172a", fg="#ffffff")
            lbl_badge.pack(side="left", padx=(0, 10))

        title_container = tk.Frame(header_content, bg="#0f172a")
        title_container.pack(side="left")

        lbl_title = tk.Label(
            title_container,
            text="FortiClient VPN Manager",
            font=("Helvetica", 16, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            title_container,
            text=f"Rede Corporativa DTIC • Conexão Segura IKEv2 / IPsec ({os_label})",
            font=("Helvetica", 9),
            fg="#94a3b8",
            bg="#0f172a"
        )
        lbl_sub.pack(anchor="w")

        # Status Visual no topo
        status_bar = tk.Frame(root, bg="#ffffff", bd=1, relief="solid")
        status_bar.pack(fill="x", padx=20, pady=(12, 8))

        self.lbl_status_icon = tk.Label(status_bar, text="●", font=("Helvetica", 22), fg="#ef4444", bg="#ffffff")
        self.lbl_status_icon.pack(side="left", padx=(15, 5), pady=6)

        self.lbl_status_text = tk.Label(status_bar, text="DESCONECTADO", font=("Helvetica", 12, "bold"), fg="#ef4444", bg="#ffffff")
        self.lbl_status_text.pack(side="left", pady=6)

        self.lbl_ip_info = tk.Label(status_bar, text="", font=("Helvetica", 9), fg="#64748b", bg="#ffffff")
        self.lbl_ip_info.pack(side="right", padx=15, pady=6)

        # Card de Configurações Editáveis
        config_card = tk.LabelFrame(
            root,
            text=" Configurações de Conexão ",
            font=("Helvetica", 10, "bold"),
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=10
        )
        config_card.pack(fill="x", padx=20, pady=4)

        # Grid de entradas
        tk.Label(config_card, text="Gateway VPN:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_gateway = tk.Entry(config_card, font=("Monospace", 9), width=20)
        self.entry_gateway.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="IP Local:", font=("Helvetica", 9), bg="#ffffff", fg="#334155").grid(row=0, column=2, sticky="w", pady=4)
        self.entry_local_ip = tk.Entry(config_card, font=("Monospace", 9), width=18)
        self.entry_local_ip.grid(row=0, column=3, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="Usuário (EAP):", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_user = tk.Entry(config_card, font=("Monospace", 9), width=20)
        self.entry_user.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="Senha:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=1, column=2, sticky="w", pady=4)
        self.entry_pass = tk.Entry(config_card, font=("Monospace", 9), show="•", width=18)
        self.entry_pass.grid(row=1, column=3, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="Chave PSK:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=2, column=0, sticky="w", pady=4)
        self.entry_psk = tk.Entry(config_card, font=("Monospace", 9), show="•", width=20)
        self.entry_psk.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="IP Virtual:", font=("Helvetica", 9), bg="#ffffff", fg="#64748b").grid(row=2, column=2, sticky="w", pady=4)
        lbl_vip_info = tk.Label(config_card, text="Dinâmico (CPRP / FortiGate)", font=("Helvetica", 9, "italic"), bg="#ffffff", fg="#059669")
        lbl_vip_info.grid(row=2, column=3, sticky="w", padx=6, pady=4)

        # Opções de visualização de senhas e salvar
        options_frame = tk.Frame(config_card, bg="#ffffff")
        options_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 2))

        self.var_show_pwd = tk.BooleanVar(value=False)
        chk_show_pwd = tk.Checkbutton(
            options_frame,
            text="Mostrar senhas",
            variable=self.var_show_pwd,
            command=self.toggle_show_passwords,
            bg="#ffffff",
            fg="#475569",
            activebackground="#ffffff",
            font=("Helvetica", 8)
        )
        chk_show_pwd.pack(side="left")

        self.var_save_creds = tk.BooleanVar(value=True)
        chk_save = tk.Checkbutton(
            options_frame,
            text="Salvar dados neste computador",
            variable=self.var_save_creds,
            bg="#ffffff",
            fg="#475569",
            activebackground="#ffffff",
            font=("Helvetica", 8)
        )
        chk_save.pack(side="left", padx=10)

        btn_save = tk.Button(
            options_frame,
            text="💾 Salvar Configurações",
            font=("Helvetica", 8, "bold"),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.save_user_config
        )
        btn_save.pack(side="right")

        # Botões Principais de Conectar / Desconectar
        btn_frame = tk.Frame(root, bg="#f1f5f9")
        btn_frame.pack(fill="x", padx=20, pady=8)

        self.btn_connect = tk.Button(
            btn_frame,
            text="▶ CONECTAR VPN",
            font=("Helvetica", 11, "bold"),
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            activeforeground="#ffffff",
            relief="flat",
            height=2,
            cursor="hand2",
            command=self.on_connect
        )
        self.btn_connect.pack(side="left", padx=3, expand=True, fill="x")

        self.btn_disconnect = tk.Button(
            btn_frame,
            text="⏹ DESCONECTAR",
            font=("Helvetica", 11, "bold"),
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            relief="flat",
            height=2,
            cursor="hand2",
            command=self.on_disconnect
        )
        self.btn_disconnect.pack(side="right", padx=3, expand=True, fill="x")

        # Barra de Ações Rápidas (Painel Web e Validação de Rede)
        action_bar = tk.Frame(root, bg="#f1f5f9")
        action_bar.pack(fill="x", padx=20, pady=4)

        btn_open_web = tk.Button(
            action_bar,
            text="🌐 Abrir Painel Web (10.64.10.1:6464)",
            font=("Helvetica", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=self.open_web_panel
        )
        btn_open_web.pack(side="left", padx=3, expand=True, fill="x")

        btn_test_web = tk.Button(
            action_bar,
            text="🔍 Validar Conexão Web (HTTP)",
            font=("Helvetica", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=self.on_test_web
        )
        btn_test_web.pack(side="right", padx=3, expand=True, fill="x")

        # Caixa de Log e Diagnóstico
        log_frame = tk.Frame(root, bg="#f1f5f9")
        log_frame.pack(fill="both", padx=20, pady=(8, 14), expand=True)

        log_header = tk.Frame(log_frame, bg="#f1f5f9")
        log_header.pack(fill="x", pady=(0, 4))
        tk.Label(log_header, text="📋 Log de Atividades e Diagnóstico:", font=("Helvetica", 9, "bold"), bg="#f1f5f9", fg="#334155").pack(side="left")

        btn_clear = tk.Button(log_header, text="Limpar", font=("Helvetica", 8), bg="#e2e8f0", fg="#334155", relief="flat", command=self.clear_log)
        btn_clear.pack(side="right")

        self.log_text = tk.Text(log_frame, height=9, font=("Monospace", 8), bg="#0f172a", fg="#e2e8f0", bd=0, padx=8, pady=8)
        self.log_text.pack(fill="both", expand=True)

        self.log(f"FortiClient VPN Manager iniciado no {os_label}.")
        self.load_initial_config()
        self.update_status()
        self.start_auto_refresh()

    def setup_window_icon(self):
        """Carrega a imagem de dtic-logo-whasapp.jpeg recortada redonda como ícone do app e janela."""
        possible_images = [
            get_resource_path("assets/dtic-logo-whasapp.jpeg"),
            get_resource_path("assets/icon.png"),
            "/usr/share/pixmaps/forticlient-vpn.png",
            "/usr/share/forticlient-vpn/assets/dtic-logo-whasapp.jpeg"
        ]

        img_path = None
        for p in possible_images:
            if os.path.exists(p):
                img_path = p
                break

        if img_path and HAS_PIL:
            try:
                base_img = Image.open(img_path)
                # Sempre aplicar recorte redondo para garantir conformidade
                round_ico_img = make_round_image(base_img, (64, 64))
                self.icon_photo = ImageTk.PhotoImage(round_ico_img)
                self.root.iconphoto(True, self.icon_photo)

                round_header_img = make_round_image(base_img, (50, 50))
                self.header_img_tk = ImageTk.PhotoImage(round_header_img)
            except Exception as e:
                print(f"Aviso ao carregar ícone redondo: {e}")
        elif img_path:
            try:
                self.icon_photo = tk.PhotoImage(file=img_path)
                self.root.iconphoto(True, self.icon_photo)
            except Exception:
                pass

        # No Windows, define também iconbitmap se existir arquivo .ico
        if IS_WINDOWS:
            ico_path = get_resource_path("assets/icon.ico")
            if os.path.exists(ico_path):
                try:
                    self.root.iconbitmap(ico_path)
                except Exception:
                    pass

    def get_config_dir(self):
        if IS_WINDOWS:
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
            path = os.path.join(base, "FortiClientVPN")
        else:
            path = os.path.expanduser("~/.config/forticlient-vpn")
        os.makedirs(path, exist_ok=True)
        return path

    def get_config_path(self):
        return os.path.join(self.get_config_dir(), "config.json")

    def toggle_show_passwords(self):
        char = "" if self.var_show_pwd.get() else "•"
        self.entry_pass.config(show=char)
        self.entry_psk.config(show=char)

    def log(self, message):
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def load_initial_config(self):
        # 1. Tenta carregar do arquivo de configuração do usuário (~/.config/forticlient-vpn/config.json)
        cfg_path = self.get_config_path()
        loaded = False

        default_gw = "198.51.100.100"
        detected_ip = get_default_local_ip(default_gw)

        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.entry_gateway.delete(0, tk.END)
                self.entry_gateway.insert(0, cfg.get("gateway", default_gw))

                self.entry_local_ip.delete(0, tk.END)
                self.entry_local_ip.insert(0, cfg.get("local_ip", detected_ip))

                self.entry_user.delete(0, tk.END)
                self.entry_user.insert(0, cfg.get("user", ""))

                self.entry_pass.delete(0, tk.END)
                self.entry_pass.insert(0, cfg.get("password", ""))

                self.entry_psk.delete(0, tk.END)
                self.entry_psk.insert(0, cfg.get("psk", ""))

                self.var_save_creds.set(cfg.get("save_credentials", True))
                loaded = True
                self.log("Configurações salvas do usuário carregadas com sucesso.")
            except Exception as e:
                self.log(f"Aviso ao ler configurações salvas: {e}")

        # Se não tiver arquivo de config, preenche campos padrão de rede
        if not loaded:
            self.entry_gateway.delete(0, tk.END)
            self.entry_gateway.insert(0, default_gw)

            self.entry_local_ip.delete(0, tk.END)
            self.entry_local_ip.insert(0, detected_ip)

            # Fallback opcional no Linux: ler swanctl existente sem expor credenciais
            if IS_LINUX and os.path.exists(CONF_FILE_LINUX):
                try:
                    with open(CONF_FILE_LINUX, "r", encoding="utf-8") as f:
                        content = f.read()
                    gw = re.search(r"remote_addrs\s*=\s*([^\s\n]+)", content)
                    if gw and not self.entry_gateway.get():
                        self.entry_gateway.insert(0, gw.group(1))
                    usr = re.search(r'eap-forticlient\s*\{[^}]*id\s*=\s*([^\s\n]+)', content)
                    if usr and not self.entry_user.get():
                        self.entry_user.insert(0, usr.group(1))
                except Exception:
                    pass

        self.lbl_ip_info.config(text=f"Origem: {self.entry_local_ip.get()}")

    def save_user_config(self, notify=True):
        if not self.var_save_creds.get():
            cfg_path = self.get_config_path()
            if os.path.exists(cfg_path):
                try:
                    os.remove(cfg_path)
                except Exception:
                    pass
            if notify:
                messagebox.showinfo("Configurações", "Opção de salvar desmarcada. Dados anteriores removidos.")
            return

        cfg = {
            "gateway": self.entry_gateway.get().strip(),
            "local_ip": self.entry_local_ip.get().strip(),
            "user": self.entry_user.get().strip(),
            "password": self.entry_pass.get().strip(),
            "psk": self.entry_psk.get().strip(),
            "save_credentials": True
        }

        try:
            cfg_path = self.get_config_path()
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            
            # No Linux, restringir permissões para 0600 (apenas o próprio usuário pode ler)
            if IS_LINUX:
                os.chmod(cfg_path, 0o600)

            if notify:
                self.log("✓ Configurações e credenciais salvas localmente com sucesso.")
                messagebox.showinfo("Configurações", "Configurações salvas localmente com sucesso!")
        except Exception as e:
            self.log(f"Erro ao salvar configurações locais: {e}")
            if notify:
                messagebox.showerror("Erro", f"Falha ao salvar configurações: {e}")

    def open_web_panel(self):
        self.log(f"Abrindo navegador padrão em: {WEB_URL}")
        self.root.clipboard_clear()
        self.root.clipboard_append(WEB_URL)
        webbrowser.open(WEB_URL)

    def is_connected(self):
        if IS_WINDOWS:
            try:
                out = subprocess.check_output(["rasdial"], stderr=subprocess.STDOUT, text=True)
                return VPN_NAME_WIN.lower() in out.lower(), "Ativo"
            except Exception:
                return False, None
        else:
            try:
                out = subprocess.check_output(["sudo", "swanctl", "--list-sas"], stderr=subprocess.STDOUT, text=True)
                if "ESTABLISHED" in out and CHILD_NAME in out:
                    vip_match = re.search(r"local.*?\[([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\]", out)
                    if not vip_match:
                        vip_match = re.search(r"local\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)/32", out)
                    vip = vip_match.group(1) if vip_match else "Ativo"
                    return True, vip
                return False, None
            except Exception:
                return False, None

    def update_status(self):
        res = self.is_connected()
        connected = res[0] if isinstance(res, tuple) else res
        vip = res[1] if isinstance(res, tuple) else "Ativo"

        if connected:
            self.lbl_status_icon.config(fg="#16a34a")
            self.lbl_status_text.config(text=f"CONECTADO (IP: {vip})", fg="#16a34a")
            self.lbl_ip_info.config(text=f"VIP Atribuído: {vip}")
            self.btn_connect.config(state="disabled", bg="#94a3b8")
            self.btn_disconnect.config(state="normal", bg="#dc2626")
        else:
            self.lbl_status_icon.config(fg="#ef4444")
            self.lbl_status_text.config(text="DESCONECTADO", fg="#ef4444")
            self.lbl_ip_info.config(text=f"Origem: {self.entry_local_ip.get()}")
            self.btn_connect.config(state="normal", bg="#16a34a")
            self.btn_disconnect.config(state="disabled", bg="#94a3b8")

    def start_auto_refresh(self):
        def loop():
            while True:
                time.sleep(4)
                try:
                    self.root.after(0, self.update_status)
                except Exception:
                    break
        threading.Thread(target=loop, daemon=True).start()

    def save_conf_linux(self):
        gw = self.entry_gateway.get().strip()
        local_ip = self.entry_local_ip.get().strip()
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()
        psk = self.entry_psk.get().strip()

        conf_content = f"""connections {{
    forticlient {{
        version  = 2
        remote_addrs = {gw}
        local_addrs  = {local_ip}
        proposals    = aes256-sha256-modp8192, aes256-sha256-modp4096, aes128-sha256-modp4096, aes256-sha256-modp2048, aes256-sha1-modp2048, aes128-sha256-modp2048
        encap        = yes
        mobike       = no
        dpd_delay    = 5s
        keyingtries  = 0
        rekey_time   = 86400s

        vips = 0.0.0.0

        local {{
            auth     = eap-mschapv2
            id       = {user}
            eap_id   = {user}
        }}

        remote {{
            auth = psk
            id   = %any
        }}

        children {{
            forticlient {{
                remote_ts     = 0.0.0.0/0
                local_ts      = dynamic
                esp_proposals = aes256-sha256-modp8192, aes256-sha1-modp8192, aes128-sha256-modp8192, aes256-sha256, aes128-sha256
                dpd_action    = restart
                mode          = tunnel
                rekey_time    = 43200s
            }}
        }}
    }}
}}

secrets {{
    ike-forticlient {{
        secret = "{psk}"
    }}
    eap-forticlient {{
        id     = {user}
        secret = "{pwd}"
    }}
}}
"""
        subprocess.run(["sudo", "mkdir", "-p", "/etc/swanctl/conf.d"], capture_output=True)
        subprocess.run(["sudo", "tee", CONF_FILE_LINUX], input=conf_content, text=True, capture_output=True)
        subprocess.run(["sudo", "chmod", "600", CONF_FILE_LINUX], capture_output=True)
        subprocess.run(["sudo", "swanctl", "--load-all"], capture_output=True)

    def ensure_windows_vpn_configured(self, gw):
        """Garante que a conexão IKEv2 no Windows está criada com cifras apropriadas."""
        ps_check = f"(Get-VpnConnection -Name '{VPN_NAME_WIN}' -ErrorAction SilentlyContinue) -ne $null"
        check_proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_check], capture_output=True, text=True)
        if "True" not in check_proc.stdout:
            self.log(f"Criando conexão VPN '{VPN_NAME_WIN}' no Windows...")
            ps_cmd = f"""
            Add-VpnConnection -Name '{VPN_NAME_WIN}' -ServerAddress '{gw}' -TunnelType 'IKEv2' -AuthenticationMethod 'EAP' -EncryptionLevel 'Required' -SplitTunneling $true -Force
            Set-VpnConnectionIPsecConfiguration -ConnectionName '{VPN_NAME_WIN}' -AuthenticationTransformConstants GCMAES256 -CipherTransformConstants GCMAES256 -EncryptionMethod AES256 -IntegrityCheckMethod SHA256 -DHGroup Group18 -PfsGroup PFS2048 -Force
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)

    def on_connect(self):
        gw = self.entry_gateway.get().strip()
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()
        psk = self.entry_psk.get().strip()

        if not user or not pwd:
            messagebox.showwarning("Campos Obrigatórios", "Por favor, preencha Usuário e Senha para conectar.")
            return

        if self.var_save_creds.get():
            self.save_user_config(notify=False)

        self.log(f"Iniciando conexão para Gateway {gw} (Usuário: {user})...")
        self.btn_connect.config(state="disabled")

        def run():
            if IS_WINDOWS:
                try:
                    self.ensure_windows_vpn_configured(gw)
                    cmd = ["rasdial", VPN_NAME_WIN, user, pwd]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode == 0:
                        self.root.after(0, lambda: self.log("✓ SUCESSO: VPN CONECTADA no Windows!"))
                    else:
                        out = proc.stdout.strip() or proc.stderr.strip()
                        self.root.after(0, lambda: self.log(f"✗ Falha Windows: {out[:120]}"))
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"✗ Erro Windows: {e}"))
            else:
                self.save_conf_linux()
                subprocess.run(["sudo", "ip", "rule", "add", "lookup", "220", "pref", "220"], capture_output=True)
                proc = subprocess.run(["sudo", "swanctl", "--initiate", "--child", CHILD_NAME], capture_output=True, text=True)
                output = proc.stdout + proc.stderr
                lines = [l for l in output.splitlines() if "agent plugin" not in l and "plugin 'agent'" not in l]
                clean_output = "\n".join(lines)

                res = self.is_connected()
                connected = res[0] if isinstance(res, tuple) else res
                vip = res[1] if isinstance(res, tuple) else "Ativo"
                if proc.returncode == 0 and connected:
                    self.root.after(0, lambda: self.log(f"✓ SUCESSO: VPN CONECTADA! IP Virtual atribuído: {vip}"))
                else:
                    if "retransmit" in clean_output.lower():
                        self.root.after(0, lambda: self.log(f"✗ Timeout: Sem resposta do Gateway {gw} na porta 500."))
                    elif "NO_PROPOSAL_CHOSEN" in clean_output:
                        self.root.after(0, lambda: self.log("✗ FortiGate respondeu NO_PROPOSAL_CHOSEN."))
                    elif "AUTHENTICATION_FAILED" in clean_output:
                        self.root.after(0, lambda: self.log("✗ Falha de autenticação: Verifique usuário, senha ou PSK."))
                    else:
                        self.root.after(0, lambda: self.log(f"✗ Retorno swanctl: {clean_output.strip()[:140]}"))

            self.root.after(0, self.update_status)

        threading.Thread(target=run, daemon=True).start()

    def on_disconnect(self):
        self.log("Desconectando da VPN...")
        self.btn_disconnect.config(state="disabled")

        def run():
            if IS_WINDOWS:
                subprocess.run(["rasdial", VPN_NAME_WIN, "/disconnect"], capture_output=True)
            else:
                subprocess.run(["sudo", "swanctl", "--terminate", "--ike", CHILD_NAME], capture_output=True)

            self.root.after(0, lambda: self.log("✓ VPN Desconectada."))
            self.root.after(0, self.update_status)

        threading.Thread(target=run, daemon=True).start()

    def on_test_web(self):
        self.log("Testando acesso ao Painel Web FortiOS (https://10.64.10.1:6464)...")
        def run():
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(WEB_URL, headers={"User-Agent": "Mozilla/5.0"})
                code = None
                try:
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        code = resp.getcode()
                except urllib.error.HTTPError as e:
                    code = e.code # 401, 403, 405 indicam que o servidor web está online!

                if code in (200, 401, 403, 405):
                    self.root.after(0, lambda: self.log(f"✓ ACESSO CONFIRMADO! Código HTTP {code} OK (Painel FortiOS online)"))
                elif code:
                    self.root.after(0, lambda: self.log(f"✓ Servidor respondeu com código HTTP {code}"))
                else:
                    self.root.after(0, lambda: self.log("✗ Não foi possível carregar a página (verifique se a VPN está conectada)."))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"✗ Erro no teste de rede: {e}"))

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = VpnApp(root)
    root.mainloop()
