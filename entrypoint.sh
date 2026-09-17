#!/usr/bin/env bash
set -e

echo "[*] Inicializando daemon strongSwan (charon)..."
mkdir -p /var/run /etc/swanctl/conf.d
/usr/lib/ipsec/charon &
CHARON_PID=$!

# Aguardar socket VICI
echo "[*] Aguardando criação do socket VICI (/var/run/charon.vici)..."
for i in $(seq 1 15); do
    if [ -S /var/run/charon.vici ]; then
        echo "[✓] Socket VICI disponível."
        break
    fi
    sleep 0.5
done

# Carregar configurações se existirem
if [ -f /etc/swanctl/conf.d/forti.conf ]; then
    echo "[*] Carregando configurações iniciais do swanctl..."
    swanctl --load-all 2>/dev/null || true
fi

# Tratamento de encerramento limpo
cleanup() {
    echo "[*] Encerrando túneis e daemon..."
    swanctl --terminate --ike forticlient 2>/dev/null || true
    kill $CHARON_PID 2>/dev/null || true
    wait $CHARON_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

echo "[*] Inicializando aplicação VPN..."
python3 /app/vpn-gui.py

cleanup
