#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiClient VPN Manager - Interface Gráfica Multiplataforma (Linux & Windows)
Compatível com VPNs FortiGate IKEv2 (EAP-MSCHAPv2 + PSK).
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

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Flags de processo para Windows (execução silenciosa sem janela preta de cmd)
WIN_CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

CONF_FILE_LINUX = "/etc/swanctl/conf.d/forti.conf"
CHILD_NAME = "forticlient"
VPN_NAME_WIN = "FortiClient-VPN"
WEB_URL = "https://10.64.10.1:6464/login?redir=%2F"


def get_resource_path(relative_path):
    """Obtém caminho absoluto para recursos, funcionando em ambiente de dev e executável PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    full_path = os.path.join(base_path, relative_path)
    if os.path.exists(full_path):
        return full_path

    if IS_LINUX:
        system_path = os.path.join("/usr/share/forticlient-vpn", relative_path)
        if os.path.exists(system_path):
            return system_path

    return full_path


try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    Image = None
    ImageDraw = None
    HAS_PIL = False

try:
    from PIL import ImageTk
    HAS_IMAGETK = True
except ImportError:
    ImageTk = None
    HAS_IMAGETK = False


def detect_local_ip(target_gw="198.51.100.100"):
    """
    Detecta automaticamente o IP local roteado para o Gateway VPN.
    Funciona de forma 100% nativa em Python tanto no Windows quanto no Linux,
    sem recorrer a comandos de shell como ip, ifconfig ou cat.
    """
    # Método 1: Socket UDP voltado para o Gateway (não envia pacotes)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect((target_gw, 500))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # Método 2: Socket UDP em direção à rota padrão
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # Método 3: Resolução de hostname
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    return "127.0.0.1"


def make_round_image(pil_img, size):
    """
    Recorta qualquer imagem em formato circular com antialiasing (supersampling),
    garantindo que o ícone do DTIC seja sempre perfeitamente redondo.
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
        self.root.geometry("640x750")
        self.root.resizable(False, False)
        self.root.configure(bg="#f1f5f9")

        # Rastreia se o usuário alterou o IP local manualmente
        self.user_manually_edited_ip = False

        self.setup_window_icon()

        # Cabeçalho Superior com Logo Circular Oficial
        header_frame = tk.Frame(root, bg="#0f172a", height=85)
        header_frame.pack(fill="x")

        header_content = tk.Frame(header_frame, bg="#0f172a")
        header_content.pack(pady=12, padx=15)

        if HAS_PIL and HAS_IMAGETK and hasattr(self, "header_img_tk") and self.header_img_tk:
            self.logo_label = tk.Label(header_content, image=self.header_img_tk, bg="#0f172a")
            self.logo_label.pack(side="left", padx=(0, 14))
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

        # Barra de Status no Topo
        status_bar = tk.Frame(root, bg="#ffffff", bd=1, relief="solid")
        status_bar.pack(fill="x", padx=20, pady=(12, 8))

        self.lbl_status_icon = tk.Label(status_bar, text="●", font=("Helvetica", 22), fg="#ef4444", bg="#ffffff")
        self.lbl_status_icon.pack(side="left", padx=(15, 5), pady=6)

        self.lbl_status_text = tk.Label(status_bar, text="DESCONECTADO", font=("Helvetica", 12, "bold"), fg="#ef4444", bg="#ffffff")
        self.lbl_status_text.pack(side="left", pady=6)

        self.lbl_ip_info = tk.Label(status_bar, text="", font=("Helvetica", 9), fg="#64748b", bg="#ffffff")
        self.lbl_ip_info.pack(side="right", padx=15, pady=6)

        # Card de Configurações de Rede e Credenciais
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

        # 1. Gateway VPN
        tk.Label(config_card, text="Gateway VPN:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_gateway = tk.Entry(config_card, font=("Monospace", 9), width=20)
        self.entry_gateway.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        self.entry_gateway.bind("<FocusOut>", lambda e: self.on_gateway_changed())

        # 2. IP Local com botão de detecção automática
        tk.Label(config_card, text="Meu IP Local:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=2, sticky="w", pady=4)
        ip_frame = tk.Frame(config_card, bg="#ffffff")
        ip_frame.grid(row=0, column=3, sticky="w", padx=6, pady=4)

        self.entry_local_ip = tk.Entry(ip_frame, font=("Monospace", 9), width=15)
        self.entry_local_ip.pack(side="left")
        self.entry_local_ip.bind("<Key>", lambda e: self.on_ip_manually_edited())

        btn_refresh_ip = tk.Button(
            ip_frame,
            text="🔄",
            font=("Helvetica", 8),
            bg="#e2e8f0",
            relief="flat",
            cursor="hand2",
            command=self.refresh_auto_ip,
            title="Redetectar IP Local automaticamente" if hasattr(tk.Button, "title") else None
        )
        btn_refresh_ip.pack(side="left", padx=(3, 0))

        # 3. Usuário EAP
        tk.Label(config_card, text="Usuário (EAP):", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_user = tk.Entry(config_card, font=("Monospace", 9), width=20)
        self.entry_user.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        # 4. Senha
        tk.Label(config_card, text="Senha:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=1, column=2, sticky="w", pady=4)
        self.entry_pass = tk.Entry(config_card, font=("Monospace", 9), show="•", width=18)
        self.entry_pass.grid(row=1, column=3, sticky="w", padx=6, pady=4)

        # 5. Chave PSK
        tk.Label(config_card, text="Chave PSK:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=2, column=0, sticky="w", pady=4)
        self.entry_psk = tk.Entry(config_card, font=("Monospace", 9), show="•", width=20)
        self.entry_psk.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        # 6. Informação de IP Virtual
        tk.Label(config_card, text="IP Virtual:", font=("Helvetica", 9), bg="#ffffff", fg="#64748b").grid(row=2, column=2, sticky="w", pady=4)
        lbl_vip_info = tk.Label(config_card, text="Dinâmico (CPRP / FortiGate)", font=("Helvetica", 9, "italic"), bg="#ffffff", fg="#059669")
        lbl_vip_info.grid(row=2, column=3, sticky="w", padx=6, pady=4)

        # Barra de Opções e Salvamento Local
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

        # Barra de Ações Rápidas (Painel Web e Validação HTTP)
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

        # Caixa de Log e Diagnóstico em Tempo Real
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
        """Carrega e aplica a imagem oficial DTIC recortada redonda como ícone do app e janela."""
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

        if img_path and HAS_PIL and HAS_IMAGETK:
            try:
                base_img = Image.open(img_path)
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

        if IS_WINDOWS:
            ico_path = get_resource_path("assets/icon.ico")
            if os.path.exists(ico_path):
                try:
                    self.root.iconbitmap(ico_path)
                except Exception:
                    pass

    def get_config_dir(self):
        """Retorna o caminho seguro do diretório de configurações conforme o SO."""
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

    def on_ip_manually_edited(self):
        self.user_manually_edited_ip = True

    def on_gateway_changed(self):
        if not self.user_manually_edited_ip:
            self.refresh_auto_ip()

    def refresh_auto_ip(self):
        gw = self.entry_gateway.get().strip() or "198.51.100.100"
        detected_ip = detect_local_ip(gw)
        self.entry_local_ip.delete(0, tk.END)
        self.entry_local_ip.insert(0, detected_ip)
        self.user_manually_edited_ip = False
        self.lbl_ip_info.config(text=f"Origem: {detected_ip} (Automático)")
        self.log(f"IP local detectado automaticamente: {detected_ip}")

    def load_initial_config(self):
        """
        Carrega as credenciais e configurações salvas do usuário.
        O IP local é sempre obtido automaticamente por padrão, a menos que
        o usuário tenha definido explicitamente um IP customizado.
        """
        cfg_path = self.get_config_path()
        default_gw = "198.51.100.100"

        # 1. Obter IP local automaticamente na primeira instância
        detected_ip = detect_local_ip(default_gw)

        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                gw = cfg.get("gateway", default_gw)
                self.entry_gateway.delete(0, tk.END)
                self.entry_gateway.insert(0, gw)

                # Se o usuário salvou uma personalização explícita de IP manual:
                saved_manual_ip = cfg.get("custom_local_ip")
                if saved_manual_ip:
                    self.entry_local_ip.delete(0, tk.END)
                    self.entry_local_ip.insert(0, saved_manual_ip)
                    self.user_manually_edited_ip = True
                    self.lbl_ip_info.config(text=f"Origem: {saved_manual_ip} (Manual)")
                else:
                    self.entry_local_ip.delete(0, tk.END)
                    self.entry_local_ip.insert(0, detected_ip)
                    self.user_manually_edited_ip = False
                    self.lbl_ip_info.config(text=f"Origem: {detected_ip} (Automático)")

                self.entry_user.delete(0, tk.END)
                self.entry_user.insert(0, cfg.get("user", ""))

                self.entry_pass.delete(0, tk.END)
                self.entry_pass.insert(0, cfg.get("password", ""))

                self.entry_psk.delete(0, tk.END)
                self.entry_psk.insert(0, cfg.get("psk", ""))

                self.var_save_creds.set(cfg.get("save_credentials", True))
                self.log("Configurações salvas do usuário carregadas com sucesso.")
                return
            except Exception as e:
                self.log(f"Aviso ao ler configurações salvas: {e}")

        # Primeira execução (sem config prévia salva)
        self.entry_gateway.delete(0, tk.END)
        self.entry_gateway.insert(0, default_gw)

        self.entry_local_ip.delete(0, tk.END)
        self.entry_local_ip.insert(0, detected_ip)
        self.user_manually_edited_ip = False
        self.lbl_ip_info.config(text=f"Origem: {detected_ip} (Automático)")
        self.log(f"IP local detectado automaticamente na inicialização: {detected_ip}")

    def save_user_config(self, notify=True):
        if not self.var_save_creds.get():
            cfg_path = self.get_config_path()
            if os.path.exists(cfg_path):
                try:
                    os.remove(cfg_path)
                except Exception:
                    pass
            if notify:
                messagebox.showinfo("Configurações", "Opção de salvar desmarcada. Dados locais anteriores removidos.")
            return

        cfg = {
            "gateway": self.entry_gateway.get().strip(),
            "user": self.entry_user.get().strip(),
            "password": self.entry_pass.get().strip(),
            "psk": self.entry_psk.get().strip(),
            "save_credentials": True,
            # Se o usuário editou manualmente, salva o IP; caso contrário salva vazio para manter auto-detecção
            "custom_local_ip": self.entry_local_ip.get().strip() if self.user_manually_edited_ip else ""
        }

        try:
            cfg_path = self.get_config_path()
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            if IS_LINUX:
                os.chmod(cfg_path, 0o600)

            if notify:
                self.log("✓ Configurações salvas com sucesso.")
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
        """Verifica o status da VPN de forma nativa e isolada por sistema operacional."""
        if IS_WINDOWS:
            try:
                out = subprocess.check_output(
                    ["rasdial"],
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    creationflags=WIN_CREATE_NO_WINDOW
                )
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
            mode = "Manual" if self.user_manually_edited_ip else "Auto"
            self.lbl_ip_info.config(text=f"Origem: {self.entry_local_ip.get()} ({mode})")
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
        """Gera configuração swanctl exclusiva para Linux, apenas com credenciais fornecidas na GUI."""
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
        """
        Configura o perfil nativo IKEv2 no Windows utilizando PowerShell nativo,
        sem comandos bash ou utilitários Unix (como cat ou tee).
        """
        ps_script = f"""
        $ErrorActionPreference = 'SilentlyContinue'
        $existing = Get-VpnConnection -Name '{VPN_NAME_WIN}'
        if (-not $existing) {{
            Add-VpnConnection -Name '{VPN_NAME_WIN}' -ServerAddress '{gw}' -TunnelType 'IKEv2' -AuthenticationMethod 'EAP' -EncryptionLevel 'Required' -SplitTunneling $true -Force
            Set-VpnConnectionIPsecConfiguration -ConnectionName '{VPN_NAME_WIN}' -AuthenticationTransformConstants GCMAES256 -CipherTransformConstants GCMAES256 -EncryptionMethod AES256 -IntegrityCheckMethod SHA256 -DHGroup Group18 -PfsGroup PFS2048 -Force
        }}
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=WIN_CREATE_NO_WINDOW
        )

    def on_connect(self):
        gw = self.entry_gateway.get().strip()
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()

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
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        errors="replace",
                        creationflags=WIN_CREATE_NO_WINDOW
                    )
                    if proc.returncode == 0:
                        self.root.after(0, lambda: self.log("✓ SUCESSO: VPN CONECTADA no Windows!"))
                    else:
                        out = proc.stdout.strip() or proc.stderr.strip()
                        self.root.after(0, lambda: self.log(f"✗ Falha Windows: {out[:120]}"))
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"✗ Erro de execução no Windows: {e}"))
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
                    lower_output = clean_output.lower()
                    if "authentication_failure" in lower_output or "authentication failed" in lower_output or "eap_mschapv2 method failed" in lower_output or "auth_failed" in lower_output:
                        self.root.after(0, lambda: self.log("✗ Falha de Autenticação: Verifique sua senha (sem caracteres adicionais como #) ou usuário."))
                    elif "retransmit" in lower_output or "timed out" in lower_output:
                        self.root.after(0, lambda: self.log(f"✗ Timeout: Sem resposta do Gateway {gw} na porta 500."))
                    elif "no_proposal_chosen" in lower_output:
                        self.root.after(0, lambda: self.log("✗ FortiGate respondeu NO_PROPOSAL_CHOSEN."))
                    else:
                        err_lines = [l.strip() for l in lines if l.strip() and not l.startswith("[NET]") and not l.startswith("[ENC]")]
                        last_err = " | ".join(err_lines[-3:]) if err_lines else clean_output.strip()[:140]
                        self.root.after(0, lambda: self.log(f"✗ Falha ao conectar: {last_err[:160]}"))

            self.root.after(0, self.update_status)

        threading.Thread(target=run, daemon=True).start()

    def on_disconnect(self):
        self.log("Desconectando da VPN...")
        self.btn_disconnect.config(state="disabled")

        def run():
            if IS_WINDOWS:
                subprocess.run(
                    ["rasdial", VPN_NAME_WIN, "/disconnect"],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    creationflags=WIN_CREATE_NO_WINDOW
                )
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
                    code = e.code # Códigos HTTP como 401, 403 indicam que o servidor web interno respondeu

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
