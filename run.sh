#!/usr/bin/env bash
# Script para iniciar o FortiClient VPN em Container

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Habilitar conexões X11 para o display do Docker
if [ -n "$DISPLAY" ]; then
    xhost +local:root >/dev/null 2>&1 || true
fi

# 2. Assegurar arquivo de configuração inicial
mkdir -p config
if [ ! -f config/forti.conf ]; then
    if [ -f /etc/swanctl/conf.d/forti.conf ]; then
        echo "[*] Sincronizando configurações existentes do host para o container..."
        sudo cp /etc/swanctl/conf.d/forti.conf config/forti.conf
        sudo chown $(id -u):$(id -g) config/forti.conf
    else
        echo "[*] Criando config/forti.conf a partir do modelo..."
        cp config/forti.conf.example config/forti.conf
    fi
    chmod 600 config/forti.conf
fi

echo "[*] Iniciando FortiClient VPN no Docker..."
echo "    • Interface Desktop : janela Tkinter na tela"
echo "    • Interface Web     : http://localhost:8080"
echo ""

docker compose up
