#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiClient VPN Manager - Container Edition
Suporta Interface Gráfica Tkinter (Desktop X11) e Web UI (http://localhost:8080)
"""

import os
import sys
import time
import re
import threading
import subprocess
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

CONF_FILE = "/etc/swanctl/conf.d/forti.conf"
CHILD_NAME = "forticlient"
WEB_URL = "https://10.64.10.1:6464/login?redir=%2F"
HTTP_PORT = 8080

activity_logs = []
logs_lock = threading.Lock()

def add_log(msg):
    with logs_lock:
        timestamp = time.strftime('%H:%M:%S')
        entry = f"[{timestamp}] {msg}"
        activity_logs.append(entry)
        if len(activity_logs) > 100:
            activity_logs.pop(0)
    print(entry, flush=True)

def get_vpn_info():
    try:
        out = subprocess.check_output(["swanctl", "--list-sas"], stderr=subprocess.STDOUT, text=True)
        if "ESTABLISHED" in out and CHILD_NAME in out:
            # Extrair IP virtual atribuído
            vip_match = re.search(r"local.*?\[([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\]", out)
            if not vip_match:
                vip_match = re.search(r"local\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)/32", out)
            vip = vip_match.group(1) if vip_match else "Ativo"
            return True, vip
        return False, None
    except Exception:
        return False, None

def read_config_values():
    defaults = {
        "gateway": "198.51.100.100",
        "local_ip": "203.0.113.7",
        "user": "miranda",
        "password": "REDACTED-CREDENTIAL",
        "psk": "REDACTED-PSK"
    }
    if not os.path.exists(CONF_FILE):
        return defaults
    try:
        with open(CONF_FILE, "r") as f:
            content = f.read()
        gw = re.search(r"remote_addrs\s*=\s*([^\s\n]+)", content)
        if gw: defaults["gateway"] = gw.group(1)
        lip = re.search(r"local_addrs\s*=\s*([^\s\n]+)", content)
        if lip: defaults["local_ip"] = lip.group(1)
        usr = re.search(r'id\s*=\s*([^\s\n]+)', content)
        if usr: defaults["user"] = usr.group(1)
        psk = re.search(r'secret\s*=\s*"([^"]+)"', content)
        if psk: defaults["psk"] = psk.group(1)
        pwd = re.search(r'eap-forticlient[^{]*\{[^}]*secret\s*=\s*"([^"]+)"', content, re.DOTALL)
        if pwd: defaults["password"] = pwd.group(1)
    except Exception as e:
        add_log(f"Aviso ao ler config: {e}")
    return defaults

def save_config_values(gw, local_ip, user, pwd, psk):
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
    ike-forticlient-alt {{
        secret = "REDACTED-PSK"
    }}
    eap-forticlient {{
        id     = {user}
        secret = "{pwd}"
    }}
    eap-forticlient-alt {{
        id     = {user}
        secret = "REDACTED-CREDENTIAL"
    }}
}}
"""
    os.makedirs(os.path.dirname(CONF_FILE), exist_ok=True)
    with open(CONF_FILE, "w") as f:
        f.write(conf_content)
    os.chmod(CONF_FILE, 0o600)
    subprocess.run(["swanctl", "--load-all"], capture_output=True)

def connect_vpn():
    add_log("Iniciando conexão à VPN FortiGate...")
    proc = subprocess.run(["swanctl", "--initiate", "--child", CHILD_NAME], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    lines = [l for l in output.splitlines() if "agent plugin" not in l and "plugin 'agent'" not in l]
    clean_output = "\n".join(lines)

    connected, vip = get_vpn_info()
    if proc.returncode == 0 and connected:
        add_log(f"✓ SUCESSO: VPN CONECTADA! IP Virtual atribuído: {vip}")
        return True, vip
    else:
        if "retransmit" in clean_output.lower():
            add_log("✗ Timeout: Sem resposta do Gateway na porta 500.")
        elif "NO_PROPOSAL_CHOSEN" in clean_output:
            add_log("✗ FortiGate respondeu NO_PROPOSAL_CHOSEN.")
        else:
            add_log(f"✗ Retorno: {clean_output.strip()[:120]}")
        return False, None

def disconnect_vpn():
    add_log("Desconectando da VPN...")
    subprocess.run(["swanctl", "--terminate", "--ike", CHILD_NAME], capture_output=True)
    add_log("✓ VPN Desconectada.")

def test_web():
    add_log("Testando acesso ao Painel Web FortiOS (https://10.64.10.1:6464)...")
    try:
        cmd = ["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--connect-timeout", "5", WEB_URL]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        code = proc.stdout.strip()
        if code == "200":
            add_log(f"✓ ACESSO CONFIRMADO! Código HTTP {code} OK (Painel FortiOS online)")
            return True, code
        elif code:
            add_log(f"✓ Servidor respondeu com código HTTP {code}")
            return True, code
        else:
            add_log("✗ Não foi possível carregar a página (verifique se a VPN está conectada).")
            return False, "Sem resposta"
    except Exception as e:
        add_log(f"✗ Erro no teste: {e}")
        return False, str(e)

# ==========================================
# WEB SERVER (Disponível em http://localhost:8080)
# ==========================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FortiClient VPN Manager</title>
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #0284c7;
            --success: #16a34a;
            --danger: #dc2626;
            --border: #334155;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 680px; }
        .header { text-align: center; margin-bottom: 20px; padding: 15px; border-radius: 12px; background: #0b1120; border: 1px solid var(--border); }
        .header h1 { font-size: 1.5rem; margin-bottom: 5px; color: #38bdf8; }
        .header p { font-size: 0.85rem; color: var(--text-muted); }
        .status-card { background: var(--card-bg); padding: 15px 20px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; border: 1px solid var(--border); }
        .status-badge { display: flex; align-items: center; gap: 10px; font-weight: bold; font-size: 1.1rem; }
        .dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; }
        .dot.connected { background: var(--success); box-shadow: 0 0 10px var(--success); }
        .dot.disconnected { background: var(--danger); box-shadow: 0 0 10px var(--danger); }
        .config-card { background: var(--card-bg); padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid var(--border); }
        .config-card h2 { font-size: 1rem; margin-bottom: 15px; color: #cbd5e1; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .form-group { display: flex; flex-direction: column; gap: 5px; }
        .form-group label { font-size: 0.8rem; color: var(--text-muted); font-weight: 500; }
        .form-group input { background: #0f172a; border: 1px solid var(--border); color: #f8fafc; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; font-family: monospace; }
        .btn-group { display: flex; gap: 12px; margin-bottom: 15px; }
        button { flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: bold; font-size: 0.95rem; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .btn-connect { background: var(--success); color: white; }
        .btn-connect:hover { background: #15803d; }
        .btn-connect:disabled { background: #475569; cursor: not-allowed; }
        .btn-disconnect { background: var(--danger); color: white; }
        .btn-disconnect:hover { background: #b91c1c; }
        .btn-disconnect:disabled { background: #475569; cursor: not-allowed; }
        .actions-group { display: flex; gap: 10px; margin-bottom: 20px; }
        .btn-web { background: var(--primary); color: white; text-decoration: none; padding: 10px; border-radius: 6px; flex: 1; text-align: center; font-weight: 600; font-size: 0.9rem; }
        .btn-web:hover { background: #0284c7; filter: brightness(1.1); }
        .btn-test { background: #334155; color: white; flex: 1; }
        .btn-test:hover { background: #475569; }
        .log-box { background: #090d16; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: monospace; font-size: 0.8rem; height: 160px; overflow-y: auto; color: #a5b4fc; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ FortiClient VPN Manager</h1>
            <p>Rede Corporativa • Container Edition (Web & Desktop)</p>
        </div>

        <div class="status-card">
            <div class="status-badge">
                <span id="status-dot" class="dot disconnected"></span>
                <span id="status-text">DESCONECTADO</span>
            </div>
            <div id="vip-text" style="color: #94a3b8; font-size: 0.85rem;">Origem: 203.0.113.7</div>
        </div>

        <div class="config-card">
            <h2>Configurações da Conexão (IPs Privados)</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Gateway VPN:</label>
                    <input type="text" id="cfg-gw" value="198.51.100.100">
                </div>
                <div class="form-group">
                    <label>Meu IP Local (Origem):</label>
                    <input type="text" id="cfg-lip" value="203.0.113.7">
                </div>
                <div class="form-group">
                    <label>Usuário (EAP):</label>
                    <input type="text" id="cfg-user" value="miranda">
                </div>
                <div class="form-group">
                    <label>Senha:</label>
                    <input type="password" id="cfg-pass" value="REDACTED-CREDENTIAL">
                </div>
                <div class="form-group">
                    <label>Chave PSK:</label>
                    <input type="text" id="cfg-psk" value="REDACTED-PSK">
                </div>
                <div class="form-group">
                    <label>IP Virtual:</label>
                    <input type="text" value="Dinâmico (DHCP FortiGate)" disabled style="color: #10b981; font-style: italic;">
                </div>
            </div>
        </div>

        <div class="btn-group">
            <button id="btn-connect" class="btn-connect" onclick="doConnect()">▶ CONECTAR VPN</button>
            <button id="btn-disconnect" class="btn-disconnect" onclick="doDisconnect()" disabled>⏹ DESCONECTAR</button>
        </div>

        <div class="actions-group">
            <a href="https://10.64.10.1:6464/login?redir=%2F" target="_blank" class="btn-web">🌐 Abrir Painel Web (10.64.10.1:6464)</a>
            <button class="btn-test" onclick="doTest()">🔍 Validar Conexão Web</button>
        </div>

        <div style="font-size: 0.85rem; margin-bottom: 5px; color: var(--text-muted);">📋 Logs de Atividades:</div>
        <div id="log-container" class="log-box"></div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                const vip = document.getElementById('vip-text');
                const btnC = document.getElementById('btn-connect');
                const btnD = document.getElementById('btn-disconnect');

                if (data.connected) {
                    dot.className = "dot connected";
                    text.innerText = "CONECTADO (IP: " + (data.vip || "Ativo") + ")";
                    text.style.color = "#16a34a";
                    vip.innerText = "VIP Atribuído: " + data.vip;
                    btnC.disabled = true;
                    btnD.disabled = false;
                } else {
                    dot.className = "dot disconnected";
                    text.innerText = "DESCONECTADO";
                    text.style.color = "#ef4444";
                    vip.innerText = "Origem: " + document.getElementById('cfg-lip').value;
                    btnC.disabled = false;
                    btnD.disabled = true;
                }

                const logBox = document.getElementById('log-container');
                logBox.innerHTML = data.logs.join('<br>');
                logBox.scrollTop = logBox.scrollHeight;
            } catch (e) {
                console.error(e);
            }
        }

        async function doConnect() {
            const btn = document.getElementById('btn-connect');
            btn.disabled = true;
            btn.innerText = "Conectando...";
            const body = {
                gw: document.getElementById('cfg-gw').value,
                local_ip: document.getElementById('cfg-lip').value,
                user: document.getElementById('cfg-user').value,
                pass: document.getElementById('cfg-pass').value,
                psk: document.getElementById('cfg-psk').value
            };
            await fetch('/api/connect', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
            btn.innerText = "▶ CONECTAR VPN";
            fetchStatus();
        }

        async function doDisconnect() {
            const btn = document.getElementById('btn-disconnect');
            btn.disabled = true;
            await fetch('/api/disconnect', { method: 'POST' });
            fetchStatus();
        }

        async function doTest() {
            await fetch('/api/test', { method: 'POST' });
            fetchStatus();
        }

        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
"""

class VpnHttpHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Silenciar logs de requests normais

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif self.path == "/api/status":
            connected, vip = get_vpn_info()
            with logs_lock:
                logs_snapshot = list(activity_logs)
            resp = {
                "connected": connected,
                "vip": vip,
                "logs": logs_snapshot
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        
        if self.path == "/api/connect":
            try:
                data = json.loads(post_body.decode("utf-8"))
                save_config_values(data.get("gw", "198.51.100.100"),
                                   data.get("local_ip", "203.0.113.7"),
                                   data.get("user", "miranda"),
                                   data.get("pass", "REDACTED-CREDENTIAL"),
                                   data.get("psk", "REDACTED-PSK"))
            except Exception as e:
                add_log(f"Erro ao salvar: {e}")
            threading.Thread(target=connect_vpn, daemon=True).start()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"connecting"}')
        elif self.path == "/api/disconnect":
            threading.Thread(target=disconnect_vpn, daemon=True).start()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"disconnecting"}')
        elif self.path == "/api/test":
            threading.Thread(target=test_web, daemon=True).start()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"testing"}')
        else:
            self.send_response(404)
            self.end_headers()

def start_web_server():
    server = HTTPServer(("0.0.0.0", HTTP_PORT), VpnHttpHandler)
    add_log(f"Interface Web iniciada e disponível em: http://localhost:{HTTP_PORT}")
    server.serve_forever()

# ==========================================
# DESKTOP GUI (Tkinter)
# ==========================================
def run_desktop_gui():
    try:
        import tkinter as tk
    except ImportError:
        add_log("Tkinter não disponível. Apenas a Interface Web estará ativa.")
        return

    root = tk.Tk()
    root.title("FortiClient VPN - DTIC / PRODEPA (Container)")
    root.geometry("620x700")
    root.resizable(False, False)
    root.configure(bg="#f1f5f9")

    # Cabeçalho
    header_frame = tk.Frame(root, bg="#0f172a", height=80)
    header_frame.pack(fill="x")

    lbl_title = tk.Label(
        header_frame,
        text="🛡️ FortiClient VPN Manager",
        font=("Helvetica", 17, "bold"),
        fg="#f8fafc",
        bg="#0f172a"
    )
    lbl_title.pack(pady=(14, 2))

    lbl_sub = tk.Label(
        header_frame,
        text="Rede Privada Corporativa • Container Edition (X11 + Web)",
        font=("Helvetica", 9),
        fg="#94a3b8",
        bg="#0f172a"
    )
    lbl_sub.pack(pady=(0, 12))

    # Status Visual no topo
    status_bar = tk.Frame(root, bg="#ffffff", bd=1, relief="solid")
    status_bar.pack(fill="x", padx=20, pady=(15, 10))

    lbl_status_icon = tk.Label(status_bar, text="●", font=("Helvetica", 22), fg="#ef4444", bg="#ffffff")
    lbl_status_icon.pack(side="left", padx=(15, 5), pady=8)

    lbl_status_text = tk.Label(status_bar, text="DESCONECTADO", font=("Helvetica", 13, "bold"), fg="#ef4444", bg="#ffffff")
    lbl_status_text.pack(side="left", pady=8)

    cfg = read_config_values()
    lbl_ip_info = tk.Label(status_bar, text=f"Origem: {cfg['local_ip']}", font=("Helvetica", 9), fg="#64748b", bg="#ffffff")
    lbl_ip_info.pack(side="right", padx=15, pady=8)

    # Card de Configurações Editáveis
    config_card = tk.LabelFrame(root, text=" Configurações de Conexão (IPs Privados) ", font=("Helvetica", 10, "bold"), bg="#ffffff", fg="#1e293b", padx=15, pady=12)
    config_card.pack(fill="x", padx=20, pady=5)

    tk.Label(config_card, text="Gateway VPN (IP Privado):", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=0, column=0, sticky="w", pady=5)
    entry_gateway = tk.Entry(config_card, font=("Monospace", 9), width=20)
    entry_gateway.insert(0, cfg["gateway"])
    entry_gateway.grid(row=0, column=1, sticky="w", padx=8, pady=5)

    tk.Label(config_card, text="Meu IP Local:", font=("Helvetica", 9), bg="#ffffff", fg="#334155").grid(row=0, column=2, sticky="w", pady=5)
    entry_local_ip = tk.Entry(config_card, font=("Monospace", 9), width=16)
    entry_local_ip.insert(0, cfg["local_ip"])
    entry_local_ip.grid(row=0, column=3, sticky="w", padx=8, pady=5)

    tk.Label(config_card, text="Usuário (EAP):", font=("Helvetica", 9, "bold"), bg="#ffffff", fg="#334155").grid(row=1, column=0, sticky="w", pady=5)
    entry_user = tk.Entry(config_card, font=("Monospace", 9), width=20)
    entry_user.insert(0, cfg["user"])
    entry_user.grid(row=1, column=1, sticky="w", padx=8, pady=5)

    tk.Label(config_card, text="Senha:", font=("Helvetica", 9), bg="#ffffff", fg="#334155").grid(row=1, column=2, sticky="w", pady=5)
    entry_pass = tk.Entry(config_card, font=("Monospace", 9), show="•", width=16)
    entry_pass.insert(0, cfg["password"])
    entry_pass.grid(row=1, column=3, sticky="w", padx=8, pady=5)

    tk.Label(config_card, text="Chave PSK:", font=("Helvetica", 9), bg="#ffffff", fg="#334155").grid(row=2, column=0, sticky="w", pady=5)
    entry_psk = tk.Entry(config_card, font=("Monospace", 9), width=20)
    entry_psk.insert(0, cfg["psk"])
    entry_psk.grid(row=2, column=1, sticky="w", padx=8, pady=5)

    tk.Label(config_card, text="IP Virtual:", font=("Helvetica", 9), bg="#ffffff", fg="#64748b").grid(row=2, column=2, sticky="w", pady=5)
    lbl_vip_info = tk.Label(config_card, text="Dinâmico (DHCP FortiGate)", font=("Helvetica", 9, "italic"), bg="#ffffff", fg="#059669")
    lbl_vip_info.grid(row=2, column=3, sticky="w", padx=8, pady=5)

    btn_frame = tk.Frame(root, bg="#f1f5f9")
    btn_frame.pack(fill="x", padx=20, pady=10)

    btn_connect = tk.Button(
        btn_frame,
        text="▶ CONECTAR VPN",
        font=("Helvetica", 11, "bold"),
        bg="#16a34a",
        fg="#ffffff",
        height=2,
        relief="flat",
        cursor="hand2"
    )
    btn_connect.pack(side="left", padx=4, expand=True, fill="x")

    btn_disconnect = tk.Button(
        btn_frame,
        text="⏹ DESCONECTAR",
        font=("Helvetica", 11, "bold"),
        bg="#dc2626",
        fg="#ffffff",
        height=2,
        relief="flat",
        cursor="hand2"
    )
    btn_disconnect.pack(side="right", padx=4, expand=True, fill="x")

    action_bar = tk.Frame(root, bg="#f1f5f9")
    action_bar.pack(fill="x", padx=20, pady=4)

    def on_open_web():
        root.clipboard_clear()
        root.clipboard_append(WEB_URL)
        add_log(f"Link do Painel copiado: {WEB_URL}")
        try:
            subprocess.run(["xdg-open", WEB_URL], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except Exception:
            pass

    btn_open_web = tk.Button(
        action_bar,
        text="🌐 Abrir Painel Web (10.64.10.1:6464)",
        font=("Helvetica", 9, "bold"),
        bg="#0284c7",
        fg="#ffffff",
        pady=6,
        relief="flat",
        cursor="hand2",
        command=on_open_web
    )
    btn_open_web.pack(side="left", padx=4, expand=True, fill="x")

    btn_test_web = tk.Button(
        action_bar,
        text="🔍 Validar Conexão Web (HTTP)",
        font=("Helvetica", 9),
        bg="#e2e8f0",
        pady=6,
        relief="flat",
        cursor="hand2",
        command=lambda: threading.Thread(target=test_web, daemon=True).start()
    )
    btn_test_web.pack(side="right", padx=4, expand=True, fill="x")

    log_frame = tk.Frame(root, bg="#f1f5f9")
    log_frame.pack(fill="both", padx=20, pady=(10, 15), expand=True)

    log_header = tk.Frame(log_frame, bg="#f1f5f9")
    log_header.pack(fill="x", pady=(0, 4))
    tk.Label(log_header, text="📋 Log de Atividades e Diagnóstico:", font=("Helvetica", 9, "bold"), bg="#f1f5f9", fg="#334155").pack(side="left")

    log_text = tk.Text(log_frame, height=10, font=("Monospace", 8), bg="#0f172a", fg="#e2e8f0", bd=0, padx=8, pady=8)
    log_text.pack(fill="both", expand=True)

    def update_ui_status():
        connected, vip = get_vpn_info()
        if connected:
            lbl_status_icon.config(fg="#16a34a")
            lbl_status_text.config(text=f"CONECTADO (IP: {vip})", fg="#16a34a")
            lbl_ip_info.config(text=f"VIP: {vip}")
            btn_connect.config(state="disabled", bg="#94a3b8")
            btn_disconnect.config(state="normal", bg="#dc2626")
        else:
            lbl_status_icon.config(fg="#ef4444")
            lbl_status_text.config(text="DESCONECTADO", fg="#ef4444")
            lbl_ip_info.config(text=f"Origem: {entry_local_ip.get()}")
            btn_connect.config(state="normal", bg="#16a34a")
            btn_disconnect.config(state="disabled", bg="#94a3b8")

        with logs_lock:
            current_logs = "\n".join(activity_logs)
        log_text.delete("1.0", tk.END)
        log_text.insert(tk.END, current_logs + "\n")
        log_text.see(tk.END)

    def on_btn_connect():
        save_config_values(entry_gateway.get().strip(),
                           entry_local_ip.get().strip(),
                           entry_user.get().strip(),
                           entry_pass.get().strip(),
                           entry_psk.get().strip())
        threading.Thread(target=connect_vpn, daemon=True).start()

    def on_btn_disconnect():
        threading.Thread(target=disconnect_vpn, daemon=True).start()

    btn_connect.config(command=on_btn_connect)
    btn_disconnect.config(command=on_btn_disconnect)

    def poll_loop():
        while True:
            time.sleep(3)
            try:
                root.after(0, update_ui_status)
            except Exception:
                break

    threading.Thread(target=poll_loop, daemon=True).start()
    update_ui_status()
    root.mainloop()

if __name__ == "__main__":
    add_log("Iniciando FortiClient VPN Manager (Container)...")
    # Iniciar servidor Web em thread separada
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    # Verificar se temos display para a GUI Tkinter
    display = os.environ.get("DISPLAY")
    if display:
        add_log(f"DISPLAY encontrado ({display}). Inicializando Interface Gráfica Desktop...")
        try:
            run_desktop_gui()
        except Exception as e:
            add_log(f"Erro ao iniciar Tkinter: {e}. Mantendo servidor Web ativo.")
            while True: time.sleep(3600)
    else:
        add_log("Nenhum DISPLAY configurado. Operando exclusivamente via Web UI (http://localhost:8080).")
        while True:
            time.sleep(3600)
