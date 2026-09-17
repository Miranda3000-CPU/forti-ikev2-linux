FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive

# Instalação do strongSwan, swanctl, Python, Tkinter e utilitários de rede
RUN apt-get update && apt-get install -y --no-install-recommends \
    strongswan \
    strongswan-swanctl \
    charon-systemd \
    libstrongswan-extra-plugins \
    libcharon-extra-plugins \
    python3 \
    python3-tk \
    curl \
    iproute2 \
    iptables \
    ca-certificates \
    x11-utils \
    xclip \
    && rm -rf /var/lib/apt/lists/*

# Cria wrapper transparente para sudo caso o script chame 'sudo'
RUN echo '#!/bin/sh\nexec "$@"' > /usr/local/bin/sudo && chmod +x /usr/local/bin/sudo

WORKDIR /app

# Copia código da aplicação e entrypoint
COPY app/ /app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/*.py

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
