#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiClient VPN Manager - Interface Gráfica Multiplataforma (Linux & Windows)
Compatível com VPNs FortiGate IKEv2 (EAP-MSCHAPv2 + PSK).

O motor é o strongSwan nos dois sistemas operacionais (ver `vpn_engine`).
No Windows os binários são vendorizados em `vendor/windows/`.
"""

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
import ssl
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

import vpn_config as cfgstore
from vpn_engine import VpnEngine, Status

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

try:
    import build_info as _build_info

    DEFAULT_WEB_URL = getattr(_build_info, "WEB_URL", "") or ""
except Exception:
    DEFAULT_WEB_URL = ""

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


def get_resource_path(relative_path):
    """Caminho absoluto para recursos, funcionando em dev e no PyInstaller."""
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


def detect_local_ip(target_gw=cfgstore.DEFAULT_GATEWAY):
    """
    Detecta o IP local roteado para o Gateway VPN, de forma nativa, sem
    depender de comandos de shell (ip/ifconfig).
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        sock.connect((target_gw, 500))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

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
    width, height = pil_img.size
    min_dim = min(width, height)
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
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
        self.root.geometry("660x800")
        self.root.resizable(False, False)
        self.root.configure(bg="#f1f5f9")

        self.logger = cfgstore.setup_logging()
        self.store = cfgstore.ConfigStore()
        self.engine = VpnEngine(logger=self.logger)
        self.user_manually_edited_ip = False
        self._busy = False
        self._running = True
        self._last_status = Status(False, None, "", "")

        self.setup_window_icon()
        self._build_header(os_label)
        self._build_status_bar()
        self._build_config_card()
        self._build_buttons()
        self._build_action_bar()
        self._build_log_box()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.log(f"FortiClient VPN Manager iniciado no {os_label} (versao {cfgstore.app_version()}).")
        available, detail = self.engine.availability()
        if available:
            self.log(f"Motor VPN: {detail}")
        else:
            self.log(f"AVISO: {detail}")
        self.load_initial_config()
        self.start_auto_refresh()
        self._maybe_cleanup_on_first_run()

    # ───────────────────────────────────────────────────────── construção da UI
    def _build_header(self, os_label):
        header_frame = tk.Frame(self.root, bg="#0f172a", height=85)
        header_frame.pack(fill="x")

        header_content = tk.Frame(header_frame, bg="#0f172a")
        header_content.pack(pady=12, padx=15)

        if HAS_PIL and HAS_IMAGETK and getattr(self, "header_img_tk", None):
            tk.Label(header_content, image=self.header_img_tk, bg="#0f172a").pack(side="left", padx=(0, 14))
        else:
            tk.Label(header_content, text="🛡️", font=("Helvetica", 24), bg="#0f172a", fg="#ffffff").pack(
                side="left", padx=(0, 10)
            )

        title_container = tk.Frame(header_content, bg="#0f172a")
        title_container.pack(side="left")

        tk.Label(
            title_container,
            text="FortiClient VPN Manager",
            font=("Helvetica", 16, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
        ).pack(anchor="w")

        tk.Label(
            title_container,
            text=f"Rede Corporativa DTIC • Conexão Segura IKEv2 / IPsec ({os_label})",
            font=("Helvetica", 9),
            fg="#94a3b8",
            bg="#0f172a",
        ).pack(anchor="w")

    def _build_status_bar(self):
        status_bar = tk.Frame(self.root, bg="#ffffff", bd=1, relief="solid")
        status_bar.pack(fill="x", padx=20, pady=(12, 8))

        self.lbl_status_icon = tk.Label(status_bar, text="●", font=("Helvetica", 22), fg="#ef4444", bg="#ffffff")
        self.lbl_status_icon.pack(side="left", padx=(15, 5), pady=6)

        self.lbl_status_text = tk.Label(
            status_bar, text="DESCONECTADO", font=("Helvetica", 12, "bold"), fg="#ef4444", bg="#ffffff"
        )
        self.lbl_status_text.pack(side="left", pady=6)

        self.lbl_ip_info = tk.Label(status_bar, text="", font=("Helvetica", 9), fg="#64748b", bg="#ffffff")
        self.lbl_ip_info.pack(side="right", padx=15, pady=6)

    def _build_config_card(self):
        config_card = tk.LabelFrame(
            self.root,
            text=" Configurações de Conexão ",
            font=("Helvetica", 10, "bold"),
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=10,
        )
        config_card.pack(fill="x", padx=20, pady=4)

        tk.Label(config_card, text="Gateway VPN:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self.entry_gateway = tk.Entry(config_card, font=("Monospace", 9), width=24)
        self.entry_gateway.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        self.entry_gateway.bind("<FocusOut>", lambda event: self.on_gateway_changed())

        tk.Label(
            config_card, text="Chave PSK (Pre-Shared Key):", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155"
        ).grid(row=1, column=0, sticky="w", pady=4)
        self.entry_psk = tk.Entry(config_card, font=("Monospace", 9), show="•", width=20)
        self.entry_psk.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="Usuário (EAP):", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self.entry_user = tk.Entry(config_card, font=("Monospace", 9), width=20)
        self.entry_user.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        tk.Label(config_card, text="Senha:", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(
            row=2, column=2, sticky="w", pady=4
        )
        self.entry_pass = tk.Entry(config_card, font=("Monospace", 9), show="•", width=18)
        self.entry_pass.grid(row=2, column=3, sticky="w", padx=6, pady=4)

        options_frame = tk.Frame(config_card, bg="#ffffff")
        options_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 4))

        self.var_show_pwd = tk.BooleanVar(value=False)
        tk.Checkbutton(
            options_frame,
            text="Mostrar senhas",
            variable=self.var_show_pwd,
            command=self.toggle_show_passwords,
            bg="#ffffff",
            fg="#475569",
            activebackground="#ffffff",
            font=("Helvetica", 8),
        ).pack(side="left")

        self.var_save_creds = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame,
            text="Salvar credenciais neste computador",
            variable=self.var_save_creds,
            bg="#ffffff",
            fg="#475569",
            activebackground="#ffffff",
            font=("Helvetica", 8),
        ).pack(side="left", padx=10)

        tk.Button(
            options_frame,
            text="💾 Salvar Configurações",
            font=("Helvetica", 8, "bold"),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.save_user_config,
        ).pack(side="right")

        self.adv_expanded = False
        self.btn_toggle_adv = tk.Button(
            config_card,
            text="▶ Opções Avançadas (IP Local, VIP)",
            font=("Helvetica", 8, "bold"),
            bg="#f1f5f9",
            fg="#475569",
            activebackground="#e2e8f0",
            activeforeground="#1e293b",
            relief="groove",
            cursor="hand2",
            padx=8,
            pady=3,
            command=self.toggle_advanced,
        )
        self.btn_toggle_adv.grid(row=4, column=0, columnspan=4, sticky="w", pady=(6, 2))

        self.frame_advanced = tk.Frame(config_card, bg="#f8fafc", bd=1, relief="solid", padx=10, pady=8)

        tk.Label(
            self.frame_advanced, text="Meu IP Local:", font=("Helvetica", 9, "bold"), bg="#f8fafc", fg="#334155"
        ).grid(row=0, column=0, sticky="w", pady=4)
        ip_frame = tk.Frame(self.frame_advanced, bg="#f8fafc")
        ip_frame.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        self.entry_local_ip = tk.Entry(ip_frame, font=("Monospace", 9), width=15)
        self.entry_local_ip.pack(side="left")
        self.entry_local_ip.bind("<Key>", lambda event: self.on_ip_manually_edited())

        tk.Button(
            ip_frame,
            text="🔄",
            font=("Helvetica", 8),
            bg="#e2e8f0",
            relief="flat",
            cursor="hand2",
            command=self.refresh_auto_ip,
        ).pack(side="left", padx=(3, 0))

        tk.Label(self.frame_advanced, text="IP Virtual:", font=("Helvetica", 9), bg="#f8fafc", fg="#64748b").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self.lbl_vip_val = tk.Label(
            self.frame_advanced,
            text="Dinâmico (CPRP / FortiGate)",
            font=("Helvetica", 9, "italic"),
            bg="#f8fafc",
            fg="#059669",
        )
        self.lbl_vip_val.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        tk.Label(self.frame_advanced, text="Estratégia VIP:", font=("Helvetica", 9), bg="#f8fafc", fg="#64748b").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self.var_vip_strategy = tk.StringVar(value="auto")
        ttk.Combobox(
            self.frame_advanced,
            textvariable=self.var_vip_strategy,
            values=("auto", "none"),
            state="readonly",
            width=10,
            font=("Monospace", 9),
        ).grid(row=2, column=1, sticky="w", padx=6, pady=4)

    def _build_buttons(self):
        btn_frame = tk.Frame(self.root, bg="#f1f5f9")
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
            command=self.on_connect,
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
            command=self.on_disconnect,
        )
        self.btn_disconnect.pack(side="right", padx=3, expand=True, fill="x")

    def _build_action_bar(self):
        action_bar = tk.Frame(self.root, bg="#f1f5f9")
        action_bar.pack(fill="x", padx=20, pady=2)

        tk.Button(
            action_bar,
            text="🌐 Abrir Painel Web",
            font=("Helvetica", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=self.open_web_panel,
        ).pack(side="left", padx=2, expand=True, fill="x")

        tk.Button(
            action_bar,
            text="🔍 Validar HTTP",
            font=("Helvetica", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=self.on_test_web,
        ).pack(side="left", padx=2, expand=True, fill="x")

        tools_bar = tk.Frame(self.root, bg="#f1f5f9")
        tools_bar.pack(fill="x", padx=20, pady=(2, 4))

        tk.Button(
            tools_bar,
            text="🧾 Exportar diagnóstico",
            font=("Helvetica", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            pady=5,
            cursor="hand2",
            command=self.on_export_diagnostics,
        ).pack(side="left", padx=2, expand=True, fill="x")

        tk.Button(
            tools_bar,
            text="🧹 Limpar conflitos",
            font=("Helvetica", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief="flat",
            pady=5,
            cursor="hand2",
            command=self.on_cleanup_conflicts,
        ).pack(side="left", padx=2, expand=True, fill="x")

    def _build_log_box(self):
        log_frame = tk.Frame(self.root, bg="#f1f5f9")
        log_frame.pack(fill="both", padx=20, pady=(4, 14), expand=True)

        log_header = tk.Frame(log_frame, bg="#f1f5f9")
        log_header.pack(fill="x", pady=(0, 4))
        tk.Label(
            log_header,
            text="📋 Log de Atividades e Diagnóstico:",
            font=("Helvetica", 9, "bold"),
            bg="#f1f5f9",
            fg="#334155",
        ).pack(side="left")

        tk.Button(
            log_header,
            text="Limpar",
            font=("Helvetica", 8),
            bg="#e2e8f0",
            fg="#334155",
            relief="flat",
            command=self.clear_log,
        ).pack(side="right")

        self.log_text = tk.Text(
            log_frame, height=10, font=("Monospace", 8), bg="#0f172a", fg="#e2e8f0", bd=0, padx=8, pady=8
        )
        self.log_text.pack(fill="both", expand=True)

    def setup_window_icon(self):
        """Aplica a imagem oficial DTIC recortada redonda como ícone do app e janela."""
        possible_images = [
            get_resource_path("assets/icon.png"),
            get_resource_path("assets/dtic-logo-whasapp.jpeg"),
            "/usr/share/pixmaps/forticlient-vpn.png",
            "/usr/share/forticlient-vpn/assets/dtic-logo-whasapp.jpeg",
        ]

        img_path = None
        for path in possible_images:
            if os.path.exists(path):
                img_path = path
                break

        if img_path and HAS_PIL and HAS_IMAGETK:
            try:
                base_img = Image.open(img_path)
                self.icon_photo = ImageTk.PhotoImage(make_round_image(base_img, (64, 64)))
                self.root.iconphoto(True, self.icon_photo)
                self.header_img_tk = ImageTk.PhotoImage(make_round_image(base_img, (50, 50)))
            except Exception as exc:
                self._safe_print(f"Aviso ao carregar ícone redondo: {exc}")
        elif img_path:
            try:
                self.icon_photo = tk.PhotoImage(file=img_path)
                self.root.iconphoto(True, self.icon_photo)
                self.header_img_tk = self.icon_photo
            except Exception:
                pass

        if IS_WINDOWS:
            ico_path = get_resource_path("assets/icon.ico")
            if os.path.exists(ico_path):
                try:
                    self.root.iconbitmap(ico_path)
                except Exception:
                    pass

    def _safe_print(self, message):
        try:
            print(message)
        except Exception:
            pass

    # ───────────────────────────────────────────────────────────── log
    def log(self, message):
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.logger.info(message)

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    # ────────────────────────────────────────────── configurações
    def toggle_show_passwords(self):
        char = "" if self.var_show_pwd.get() else "•"
        self.entry_pass.config(show=char)
        self.entry_psk.config(show=char)

    def toggle_advanced(self):
        self.adv_expanded = not self.adv_expanded
        if self.adv_expanded:
            self.frame_advanced.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 2))
            self.btn_toggle_adv.config(text="▼ Ocultar Opções Avançadas")
        else:
            self.frame_advanced.grid_remove()
            self.btn_toggle_adv.config(text="▶ Opções Avançadas (IP Local, VIP)")

    def on_ip_manually_edited(self):
        self.user_manually_edited_ip = True

    def on_gateway_changed(self):
        if not self.user_manually_edited_ip:
            self.refresh_auto_ip()

    def refresh_auto_ip(self):
        gateway = self.entry_gateway.get().strip() or cfgstore.DEFAULT_GATEWAY
        detected = detect_local_ip(gateway)
        self.entry_local_ip.delete(0, tk.END)
        self.entry_local_ip.insert(0, detected)
        self.user_manually_edited_ip = False
        self.lbl_ip_info.config(text=f"Origem: {detected} (Automático)")
        self.log(f"IP local detectado automaticamente: {detected}")

    def _current_config(self):
        return {
            "gateway": self.entry_gateway.get().strip(),
            "user": self.entry_user.get().strip(),
            "password": self.entry_pass.get().strip(),
            "psk": self.entry_psk.get().strip(),
            "save_credentials": bool(self.var_save_creds.get()),
            "custom_local_ip": self.entry_local_ip.get().strip() if self.user_manually_edited_ip else "",
            "vip_strategy": self.var_vip_strategy.get(),
        }

    def load_initial_config(self):
        """
        Carrega as credenciais salvas. O IP local é sempre automático por
        padrão, a menos que o usuário tenha definido um IP customizado.
        """
        cfg = self.store.load_plain()
        gateway = cfg.get("gateway") or cfgstore.DEFAULT_GATEWAY
        detected = detect_local_ip(gateway)

        self.entry_gateway.delete(0, tk.END)
        self.entry_gateway.insert(0, gateway)

        saved_manual_ip = cfg.get("custom_local_ip")
        if saved_manual_ip:
            self.entry_local_ip.delete(0, tk.END)
            self.entry_local_ip.insert(0, saved_manual_ip)
            self.user_manually_edited_ip = True
            self.lbl_ip_info.config(text=f"Origem: {saved_manual_ip} (Manual)")
        else:
            self.entry_local_ip.delete(0, tk.END)
            self.entry_local_ip.insert(0, detected)
            self.user_manually_edited_ip = False
            self.lbl_ip_info.config(text=f"Origem: {detected} (Automático)")

        self.entry_user.delete(0, tk.END)
        self.entry_user.insert(0, cfg.get("user", ""))
        self.entry_pass.delete(0, tk.END)
        self.entry_pass.insert(0, cfg.get("password", ""))
        self.entry_psk.delete(0, tk.END)
        self.entry_psk.insert(0, cfg.get("psk", ""))
        self.var_save_creds.set(bool(cfg.get("save_credentials", True)))
        self.var_vip_strategy.set(cfg.get("vip_strategy", "auto"))
        self.log("Configurações salvas carregadas.")

    def save_user_config(self, notify=True):
        if not self.var_save_creds.get():
            self.store.delete()
            if notify:
                messagebox.showinfo(
                    "Configurações", "Opção de salvar desmarcada. Dados locais anteriores removidos."
                )
            return

        try:
            path = self.store.save(self._current_config())
            self.log(f"Configurações salvas em {path}")
            if notify:
                messagebox.showinfo("Configurações", "Configurações salvas localmente com sucesso!")
        except Exception as exc:
            self.log(f"Erro ao salvar configurações locais: {exc}")
            if notify:
                messagebox.showerror("Erro", f"Falha ao salvar configurações: {exc}")

    # ───────────────────────────────────────────────────────── status
    def start_auto_refresh(self):
        def loop():
            while self._running:
                try:
                    status = self.engine.status()
                except Exception as exc:
                    status = Status(False, None, "", str(exc))
                try:
                    self.root.after(0, lambda s=status: self.apply_status(s))
                except Exception:
                    break
                time.sleep(4)

        threading.Thread(target=loop, daemon=True).start()

    def apply_status(self, status):
        self._last_status = status
        connected = bool(status.connected)
        vip = status.vip or "Ativo"

        if connected:
            self.lbl_status_icon.config(fg="#16a34a")
            self.lbl_status_text.config(text=f"CONECTADO (IP: {vip})", fg="#16a34a")
            self.lbl_ip_info.config(text=f"VIP Atribuído: {vip}")
            self.lbl_vip_val.config(text=vip, fg="#16a34a")
        else:
            self.lbl_status_icon.config(fg="#ef4444")
            self.lbl_status_text.config(text="DESCONECTADO", fg="#ef4444")
            mode = "Manual" if self.user_manually_edited_ip else "Auto"
            self.lbl_ip_info.config(text=f"Origem: {self.entry_local_ip.get()} ({mode})")
            self.lbl_vip_val.config(text="Dinâmico (CPRP / FortiGate)", fg="#059669")

        if not self._busy:
            if connected:
                self.btn_connect.config(state="disabled", bg="#94a3b8")
                self.btn_disconnect.config(state="normal", bg="#dc2626")
            else:
                self.btn_connect.config(state="normal", bg="#16a34a")
                self.btn_disconnect.config(state="disabled", bg="#94a3b8")

    # ───────────────────────────────────────────────────── conexão
    def _settings_for_engine(self):
        cfg = self._current_config()
        return {
            "gateway": cfg["gateway"],
            "local_ip": self.entry_local_ip.get().strip(),
            "user": cfg["user"],
            "password": cfg["password"],
            "psk": cfg["psk"],
            "vip_strategy": cfg["vip_strategy"],
        }

    def on_connect(self):
        settings = self._settings_for_engine()

        if not settings["gateway"]:
            messagebox.showwarning("Campos Obrigatórios", "Informe o Gateway VPN.")
            return

        missing = []
        if not settings["user"]:
            missing.append("Usuário")
        if not settings["password"]:
            missing.append("Senha")
        if not settings["psk"]:
            missing.append("Chave PSK")
        if missing:
            messagebox.showwarning(
                "Campos Obrigatórios", "Preencha: " + ", ".join(missing) + "."
            )
            return

        if self.var_save_creds.get():
            self.save_user_config(notify=False)

        self._busy = True
        self.btn_connect.config(state="disabled", bg="#94a3b8")
        self.log(f"Iniciando conexão para o Gateway {settings['gateway']} (Usuário: {settings['user']})...")

        def run():
            try:
                status = self.engine.connect(settings)
            except Exception as exc:
                status = Status(False, None, "", f"Erro inesperado: {exc}")
            self._busy = False
            if status.connected:
                self.root.after(0, lambda s=status: self.log(f"✓ SUCESSO: VPN CONECTADA! {s.detail}"))
            else:
                self.root.after(0, lambda s=status: self.log(f"✗ {s.error}"))
                if status.detail:
                    self.root.after(0, lambda s=status: self.log(f"   Detalhe: {s.detail[:400]}"))
                self.root.after(0, lambda: messagebox.showerror("Falha na conexão", status.error))
            self.root.after(0, lambda s=status: self.apply_status(s))

        threading.Thread(target=run, daemon=True).start()

    def on_disconnect(self):
        self._busy = True
        self.btn_disconnect.config(state="disabled", bg="#94a3b8")
        self.log("Desconectando da VPN...")

        def run():
            try:
                status = self.engine.disconnect()
            except Exception as exc:
                status = Status(False, None, "", f"Erro inesperado: {exc}")
            self._busy = False
            self.root.after(0, lambda: self.log("✓ Desconectado."))
            self.root.after(0, lambda s=status: self.apply_status(s))

        threading.Thread(target=run, daemon=True).start()

    # ─────────────────────────────────────────────────── ferramentas
    def _web_url(self):
        """URL do Painel FortiOS embutida no build (via FCT_WEB_URL), se houver."""
        return DEFAULT_WEB_URL

    def open_web_panel(self):
        url = self._web_url()
        if not url:
            self.log("Painel Web não configurado neste build. Nenhum endereço interno é embutido no app.")
            return
        self.log(f"Abrindo navegador padrão em: {url}")
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        webbrowser.open(url)

    def on_test_web(self):
        url = self._web_url()
        if not url:
            self.log("Painel Web não configurado neste build. O atalho fica disponível ao compilar com FCT_WEB_URL.")
            return
        self.log(f"Testando acesso ao Painel Web FortiOS ({url})...")

        def run():
            try:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                code = None
                try:
                    with urllib.request.urlopen(request, timeout=5, context=context) as response:
                        code = response.getcode()
                except urllib.error.HTTPError as exc:
                    code = exc.code

                if code in (200, 401, 403, 405):
                    message = f"✓ ACESSO CONFIRMADO! Código HTTP {code} (Painel FortiOS online)"
                elif code:
                    message = f"✓ Servidor respondeu com código HTTP {code}"
                else:
                    message = "✗ Sem resposta (verifique se a VPN está conectada)."
            except Exception as exc:
                message = f"✗ Erro no teste de rede: {exc}"
            self.root.after(0, lambda: self.log(message))

        threading.Thread(target=run, daemon=True).start()

    def on_export_diagnostics(self):
        self.log("Coletando diagnóstico...")

        def run():
            try:
                info = self.engine.diagnose()
                path = cfgstore.build_diagnostics(
                    cfg=self.store.load(), extra_text=info, log_file=cfgstore.log_path()
                )
                message = f"Diagnóstico salvo em:\n{path}"
                self.log(f"✓ Diagnóstico salvo em: {path}")
            except Exception as exc:
                message = f"Falha ao gerar diagnóstico: {exc}"
                self.log(f"✗ {message}")
            self.root.after(0, lambda: messagebox.showinfo("Diagnóstico", message))

        threading.Thread(target=run, daemon=True).start()

    def _maybe_cleanup_on_first_run(self):
        """
        Remove resíduos de versões antigas no primeiro arranque após atualizar.

        Feito no processo do usuário (não no instalador) para que as chaves de
        HKCU e o perfil RAS corretos sejam os do próprio usuário.
        """
        marker = os.path.join(cfgstore.state_dir(), ".cleanup-v2.done")
        if os.path.exists(marker):
            return

        def run():
            try:
                removed = self.engine.cleanup_conflicts()
                if removed:
                    self.root.after(0, lambda r=removed: self.log("Limpeza automática: " + ", ".join(r)))
            except Exception as exc:
                self.logger.warning("Limpeza automática falhou: %s", exc)
            try:
                cfgstore.ensure_dir(cfgstore.state_dir())
                with open(marker, "w", encoding="utf-8") as handle:
                    handle.write(cfgstore.app_version())
            except OSError:
                pass

        threading.Thread(target=run, daemon=True).start()

    def on_cleanup_conflicts(self):
        self.log("Procurando resíduos de versões anteriores...")

        def run():
            try:
                removed = self.engine.cleanup_conflicts()
            except Exception as exc:
                removed = []
                self.log(f"✗ Falha na limpeza: {exc}")
            if removed:
                message = "Removido:\n- " + "\n- ".join(removed)
                self.log("✓ Limpeza concluída: " + ", ".join(removed))
            else:
                message = "Nenhum resíduo encontrado (ou nada a remover nesta plataforma)."
                self.log("✓ " + message)
            self.root.after(0, lambda: messagebox.showinfo("Limpar conflitos", message))

        threading.Thread(target=run, daemon=True).start()

    def on_close(self):
        self._running = False
        try:
            self.root.destroy()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════ modo CLI

def _cli_settings(store):
    cfg = store.load_plain()
    gateway = cfg.get("gateway") or cfgstore.DEFAULT_GATEWAY
    return {
        "gateway": gateway,
        "local_ip": cfg.get("custom_local_ip") or detect_local_ip(gateway),
        "user": cfg.get("user", ""),
        "password": cfg.get("password", ""),
        "psk": cfg.get("psk", ""),
        "vip_strategy": cfg.get("vip_strategy", "auto"),
    }


def run_cli(args):
    """
    Modo sem interface gráfica: essencial no Windows, onde o executável é GUI
    e uma falha sem log é impossível de investigar.
    """
    logger = cfgstore.setup_logging()
    store = cfgstore.ConfigStore()
    engine = VpnEngine(logger=logger)
    logger.info("CLI: %s", vars(args))

    if args.diagnose:
        info = engine.diagnose()
        path = cfgstore.build_diagnostics(cfg=store.load(), extra_text=info, log_file=cfgstore.log_path())
        print(f"Diagnostico salvo em: {path}")
        print(f"Log: {cfgstore.log_path()}")
        return 0

    if args.cleanup:
        removed = engine.cleanup_conflicts()
        print("Removido: " + (", ".join(removed) if removed else "nada"))
        return 0

    settings = _cli_settings(store)
    if args.connect:
        if not settings["user"] or not settings["password"] or not settings["psk"]:
            print("Erro: usuario, senha e PSK precisam estar salvos (use a interface grafica).")
            return 2
        status = engine.connect(settings)
        if status.connected:
            print(f"OK: conectado ({status.detail})")
            return 0
        print(f"ERRO: {status.error}")
        if status.detail:
            print(f"Detalhe: {status.detail}")
        return 1

    if args.disconnect:
        engine.disconnect()
        print("OK: desconectado")
        return 0

    print("Nada a fazer. Use --connect, --disconnect, --diagnose ou --cleanup.")
    return 2


def build_parser():
    parser = argparse.ArgumentParser(description="FortiClient VPN Manager (DTIC/PRODEPA)")
    parser.add_argument("--connect", action="store_true", help="conecta usando as credenciais salvas")
    parser.add_argument("--disconnect", action="store_true", help="desconecta a VPN")
    parser.add_argument("--diagnose", action="store_true", help="gera pacote de diagnostico e sai")
    parser.add_argument("--cleanup", action="store_true", help="remove residuos de versoes anteriores e sai")
    return parser


def main():
    args = build_parser().parse_args()
    if args.connect or args.disconnect or args.diagnose or args.cleanup:
        return run_cli(args)

    cfgstore.setup_logging()
    root = tk.Tk()
    VpnApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
